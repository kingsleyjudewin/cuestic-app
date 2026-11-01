import os
import re
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, BinaryIO
import requests
from app.extensions import db
from app.models.media import GoogleDriveIntegration
from app.utils.datetime_utils import utc_now, format_iso_utc
from app.utils.errors import ValidationError, NotFoundError, PermissionDeniedError

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
GOOGLE_DRIVE_UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/userinfo.email",
]


class GoogleDriveService:
    """Service handling official Google OAuth 2.0 authorization, Drive folder linking, and file operations."""

    @classmethod
    def get_client_config(cls) -> tuple[Optional[str], Optional[str], str]:
        """Fetch client ID, secret, and redirect URI from environment."""
        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        redirect_uri = os.environ.get(
            "GOOGLE_REDIRECT_URI",
            "http://localhost:5000/api/v1/media/drive/callback"
        )
        return client_id, client_secret, redirect_uri

    @classmethod
    def is_configured(cls) -> bool:
        """Check if Google OAuth credentials are set in environment."""
        client_id, client_secret, _ = cls.get_client_config()
        return bool(client_id and client_secret and "your-google" not in client_id)

    @classmethod
    def get_auth_url(cls, user_id: int, redirect_uri: Optional[str] = None) -> str:
        """
        Generate Google OAuth 2.0 authorization consent URL.
        Embeds user_id in the state parameter for secure callback resolution.
        """
        client_id, client_secret, default_redirect = cls.get_client_config()
        if not client_id or not client_secret:
            raise ValidationError(
                "Google Drive integration is not yet configured. "
                "Please configure GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in the server environment (.env).",
                details={"setup_required": ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"]}
            )

        active_redirect = redirect_uri or default_redirect
        state_data = json.dumps({"user_id": user_id, "timestamp": int(utc_now().timestamp())})

        params = {
            "client_id": client_id,
            "redirect_uri": active_redirect,
            "response_type": "code",
            "scope": " ".join(DEFAULT_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state_data,
        }
        query_string = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
        return f"{GOOGLE_AUTH_URL}?{query_string}"

    @classmethod
    def handle_oauth_callback(
        cls,
        code: str,
        state_str: str,
        redirect_uri: Optional[str] = None
    ) -> GoogleDriveIntegration:
        """
        Exchange authorization code for tokens and save/update user's GoogleDriveIntegration.
        """
        if not code:
            raise ValidationError("Authorization code is missing from Google callback.")

        try:
            state_data = json.loads(state_str)
            user_id = int(state_data.get("user_id"))
        except Exception:
            raise ValidationError("Invalid or tampered OAuth state parameter.")

        client_id, client_secret, default_redirect = cls.get_client_config()
        active_redirect = redirect_uri or default_redirect

        token_payload = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": active_redirect,
            "grant_type": "authorization_code",
        }

        token_resp = requests.post(GOOGLE_TOKEN_URL, data=token_payload, timeout=15)
        if token_resp.status_code != 200:
            logger.error("Google token exchange failed: %s", token_resp.text)
            raise ValidationError(
                f"Failed to exchange authorization code with Google ({token_resp.status_code}).",
                details={"response": token_resp.text}
            )

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        scope = token_data.get("scope")
        token_expiry = utc_now() + timedelta(seconds=int(expires_in))

        # Retrieve connected Google user's email
        google_email = None
        google_user_id = None
        try:
            userinfo_resp = requests.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10
            )
            if userinfo_resp.status_code == 200:
                info = userinfo_resp.json()
                google_email = info.get("email")
                google_user_id = info.get("id")
        except Exception as e:
            logger.warning("Could not fetch Google user info: %s", e)

        # Upsert GoogleDriveIntegration record
        integration = GoogleDriveIntegration.query.filter_by(user_id=user_id).first()
        if not integration:
            integration = GoogleDriveIntegration(user_id=user_id)
            db.session.add(integration)

        integration.access_token = access_token
        if refresh_token:
            integration.refresh_token = refresh_token
        integration.token_expiry = token_expiry
        integration.scope = scope
        integration.google_email = google_email
        integration.google_user_id = google_user_id
        integration.is_active = True
        integration.updated_at = utc_now()

        db.session.commit()
        logger.info("Google Drive connected successfully for User ID %s (%s)", user_id, google_email)
        return integration

    @classmethod
    def extract_folder_id(cls, folder_id_or_url: str) -> str:
        """Extract Google Drive folder ID from a raw ID or full Google Drive URL."""
        if not folder_id_or_url:
            return ""
        clean = folder_id_or_url.strip()
        # Matches https://drive.google.com/drive/folders/<id> or https://drive.google.com/drive/u/0/folders/<id>
        match = re.search(r"folders/([a-zA-Z0-9_\-]+)", clean)
        if match:
            return match.group(1)
        # Matches ?id=<id>
        match_id = re.search(r"[?&]id=([a-zA-Z0-9_\-]+)", clean)
        if match_id:
            return match_id.group(1)
        return clean

    @classmethod
    def get_service_account_token(cls) -> Optional[str]:
        """Fetch Google Drive access token using service account credentials if available."""
        cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")
        if cred_path and not os.path.isabs(cred_path):
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            cred_path = os.path.join(base_dir, cred_path)
        if cred_path and os.path.exists(cred_path):
            try:
                from google.oauth2 import service_account
                from google.auth.transport.requests import Request
                cred = service_account.Credentials.from_service_account_file(
                    cred_path,
                    scopes=["https://www.googleapis.com/auth/drive"]
                )
                cred.refresh(Request())
                return cred.token
            except Exception as e:
                logger.warning("Could not obtain service account Drive token: %s", e)
        return None

    @classmethod
    def get_valid_token(cls, user_id: Optional[int] = None) -> str:
        """
        Get valid access token for user, automatically refreshing it if expired,
        or falling back to service account credentials.
        """
        if user_id:
            integration = GoogleDriveIntegration.query.filter_by(user_id=user_id, is_active=True).first()
            if integration:
                now = utc_now()
                if integration.token_expiry and integration.token_expiry > (now + timedelta(minutes=2)):
                    return integration.access_token

                if integration.refresh_token:
                    client_id, client_secret, _ = cls.get_client_config()
                    refresh_payload = {
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": integration.refresh_token,
                        "grant_type": "refresh_token",
                    }
                    try:
                        refresh_resp = requests.post(GOOGLE_TOKEN_URL, data=refresh_payload, timeout=15)
                        if refresh_resp.status_code == 200:
                            refresh_data = refresh_resp.json()
                            integration.access_token = refresh_data["access_token"]
                            expires_in = refresh_data.get("expires_in", 3600)
                            integration.token_expiry = utc_now() + timedelta(seconds=int(expires_in))
                            db.session.commit()
                            return integration.access_token
                        else:
                            logger.warning("Failed to refresh Google token for user %s: %s", user_id, refresh_resp.text)
                    except Exception as e:
                        logger.warning("Error refreshing Google token: %s", e)

        # Fallback to service account token
        sa_token = cls.get_service_account_token()
        if sa_token:
            return sa_token

        raise PermissionDeniedError(
            "Google Drive is not connected. Either connect Google Drive via OAuth or configure a shared folder with the service account."
        )

    @classmethod
    def get_connection_status(cls, user_id: int) -> dict:
        """Get status of Google Drive integration for user."""
        integration = GoogleDriveIntegration.query.filter_by(user_id=user_id, is_active=True).first()
        is_conf = cls.is_configured()

        if not integration:
            return {
                "is_connected": False,
                "is_configured": is_conf,
                "google_email": None,
                "token_expiry": None,
            }

        return {
            "is_connected": True,
            "is_configured": is_conf,
            "google_email": integration.google_email,
            "token_expiry": format_iso_utc(integration.token_expiry) if integration.token_expiry else None,
            "connected_at": format_iso_utc(integration.created_at),
        }

    @classmethod
    def disconnect(cls, user_id: int) -> bool:
        """Revoke token and mark Google Drive integration inactive."""
        integration = GoogleDriveIntegration.query.filter_by(user_id=user_id).first()
        if not integration:
            return True

        if integration.access_token:
            try:
                requests.post(
                    GOOGLE_REVOKE_URL,
                    params={"token": integration.access_token},
                    headers={"content-type": "application/x-www-form-urlencoded"},
                    timeout=5
                )
            except Exception as e:
                logger.debug("Notice revoking token: %s", e)

        integration.is_active = False
        integration.access_token = ""
        integration.refresh_token = None
        db.session.commit()
        return True

    # -------------------------------------------------------------------------
    # Drive API Operations
    # -------------------------------------------------------------------------
    @classmethod
    def list_folders(cls, user_id: int, query: Optional[str] = None) -> list[dict]:
        """List folders in user's Google Drive."""
        token = cls.get_valid_token(user_id)
        q = "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if query:
            clean_q = query.replace("'", "\\'")
            q += f" and name contains '{clean_q}'"

        url = f"{GOOGLE_DRIVE_API_BASE}/files"
        params = {
            "q": q,
            "fields": "files(id, name, webViewLink, modifiedTime)",
            "pageSize": 50,
            "orderBy": "name",
        }
        headers = {"Authorization": f"Bearer {token}"}

        resp = requests.get(url, params=params, headers=headers, timeout=15)
        if resp.status_code != 200:
            logger.error("Drive list folders error (%d): %s", resp.status_code, resp.text)
            raise ValidationError(f"Google Drive API error ({resp.status_code}): {resp.text}")

        files = resp.json().get("files", [])
        return [
            {
                "id": f["id"],
                "name": f["name"],
                "web_view_link": f.get("webViewLink"),
                "modified_time": f.get("modifiedTime"),
            }
            for f in files
        ]

    @classmethod
    def create_folder(cls, user_id: int, folder_name: str, parent_id: Optional[str] = None) -> dict:
        """Create a new folder in Google Drive."""
        token = cls.get_valid_token(user_id)
        url = f"{GOOGLE_DRIVE_API_BASE}/files"
        body = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            body["parents"] = [parent_id]

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        resp = requests.post(
            url,
            data=json.dumps(body),
            headers=headers,
            params={"fields": "id, name, webViewLink"},
            timeout=15
        )
        if resp.status_code not in (200, 201):
            logger.error("Drive create folder error (%d): %s", resp.status_code, resp.text)
            raise ValidationError(f"Failed to create Google Drive folder: {resp.text}")

        data = resp.json()
        return {
            "id": data["id"],
            "name": data["name"],
            "web_view_link": data.get("webViewLink"),
        }

    @classmethod
    def list_folder_files(
        cls,
        user_id: int,
        drive_folder_id: str,
        category_filter: Optional[str] = None,
        query: Optional[str] = None
    ) -> list[dict]:
        """List files located inside a linked Google Drive folder."""
        token = cls.get_valid_token(user_id)
        q = f"'{drive_folder_id}' in parents and trashed = false"

        if query:
            clean_q = query.replace("'", "\\'")
            q += f" and name contains '{clean_q}'"

        url = f"{GOOGLE_DRIVE_API_BASE}/files"
        params = {
            "q": q,
            "fields": "files(id, name, mimeType, size, webViewLink, thumbnailLink, modifiedTime, createdTime)",
            "pageSize": 100,
            "orderBy": "createdTime desc",
        }
        headers = {"Authorization": f"Bearer {token}"}

        resp = requests.get(url, params=params, headers=headers, timeout=15)
        if resp.status_code != 200:
            logger.error("Drive list folder files error (%d): %s", resp.status_code, resp.text)
            raise ValidationError(f"Failed to list Google Drive files ({resp.status_code}): {resp.text}")

        files = resp.json().get("files", [])
        results = []
        for f in files:
            mime = f.get("mimeType", "")
            size_val = int(f.get("size", 0)) if f.get("size") else None

            # Infer category
            if mime.startswith("image/"):
                cat = "photos"
            elif mime.startswith("video/"):
                cat = "videos"
            elif "pdf" in mime or "illustrator" in mime or "photoshop" in mime:
                cat = "posters"
            else:
                cat = "posters"

            if category_filter and cat != category_filter:
                continue

            results.append({
                "id": f["id"],
                "name": f["name"],
                "mime_type": mime,
                "file_size": size_val,
                "category": cat,
                "web_view_link": f.get("webViewLink"),
                "thumbnail_link": f.get("thumbnailLink"),
                "modified_time": f.get("modifiedTime"),
            })
        return results

    @classmethod
    def get_file_metadata(cls, user_id: int, drive_file_id: str) -> dict:
        """Fetch metadata for a single Google Drive file."""
        token = cls.get_valid_token(user_id)
        url = f"{GOOGLE_DRIVE_API_BASE}/files/{drive_file_id}"
        params = {"fields": "id, name, mimeType, size, webViewLink, thumbnailLink, modifiedTime"}
        headers = {"Authorization": f"Bearer {token}"}

        resp = requests.get(url, params=params, headers=headers, timeout=15)
        if resp.status_code != 200:
            raise NotFoundError(f"Google Drive file '{drive_file_id}' not found or inaccessible.")

        f = resp.json()
        return {
            "id": f["id"],
            "name": f["name"],
            "mime_type": f.get("mimeType"),
            "file_size": int(f.get("size", 0)) if f.get("size") else None,
            "web_view_link": f.get("webViewLink"),
            "thumbnail_link": f.get("thumbnailLink"),
            "modified_time": f.get("modifiedTime"),
        }

    @classmethod
    def upload_file_to_drive(
        cls,
        user_id: int,
        drive_folder_id: str,
        file_obj: BinaryIO,
        filename: str,
        mime_type: Optional[str] = None
    ) -> dict:
        """Upload file directly to a Google Drive folder."""
        token = cls.get_valid_token(user_id)
        upload_url = f"{GOOGLE_DRIVE_UPLOAD_BASE}/files?uploadType=multipart"

        metadata = {
            "name": filename,
            "parents": [drive_folder_id],
        }

        # Multi-part form payload with JSON metadata and file binary
        pos = file_obj.tell() if hasattr(file_obj, "tell") else 0
        file_content = file_obj.read()
        if hasattr(file_obj, "seek"):
            file_obj.seek(pos)

        files = {
            "data": ("metadata", json.dumps(metadata), "application/json; charset=UTF-8"),
            "file": (filename, file_content, mime_type or "application/octet-stream"),
        }
        headers = {"Authorization": f"Bearer {token}"}

        resp = requests.post(upload_url, headers=headers, files=files, timeout=60)
        if resp.status_code not in (200, 201):
            logger.error("Drive upload file error (%d): %s", resp.status_code, resp.text)
            raise ValidationError(f"Failed to upload file to Google Drive: {resp.text}")

        data = resp.json()
        # Fetch webViewLink
        meta = cls.get_file_metadata(user_id, data["id"])
        return meta
