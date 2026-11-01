import io
import logging
from flask import Blueprint, request, g, send_file, Response, redirect, render_template_string
from app.services.media_service import MediaService
from app.services.google_drive_service import GoogleDriveService
from app.services.firebase_storage_service import FirebaseStorageService
from app.models.media import MediaFile
from app.utils.permissions import token_required
from app.utils.errors import success_response, ValidationError, NotFoundError

logger = logging.getLogger(__name__)

media_bp = Blueprint("media", __name__)


# -----------------------------------------------------------------------------
# Event Folders Endpoints
# -----------------------------------------------------------------------------
@media_bp.route("/folders", methods=["GET"])
@token_required
def list_folders():
    """List event folders for the Media team."""
    search_q = request.args.get("q")
    data = MediaService.list_folders_data(g.current_user, search_query=search_q)
    return success_response(data=data)


@media_bp.route("/folders", methods=["POST"])
@token_required
def create_folder():
    """Create a new event folder."""
    data = request.get_json(silent=True) or {}
    folder = MediaService.create_folder(data, g.current_user)
    return success_response(
        data=folder.to_dict(),
        message="Event folder created successfully.",
        status_code=201
    )


@media_bp.route("/folders/<int:folder_id>", methods=["GET"])
@token_required
def get_folder(folder_id: int):
    """Get event folder details and media counts."""
    include_media = request.args.get("include_media", "false").lower() == "true"
    folder = MediaService.get_folder_by_id(folder_id, g.current_user)
    return success_response(data=folder.to_dict(include_media=include_media))


@media_bp.route("/folders/<int:folder_id>", methods=["DELETE"])
@token_required
def delete_folder(folder_id: int):
    """Delete event folder and all its associated media files."""
    MediaService.delete_folder(folder_id, g.current_user)
    return success_response(message="Event folder deleted successfully.")


# -----------------------------------------------------------------------------
# Media Files & Uploads
# -----------------------------------------------------------------------------
@media_bp.route("/folders/<int:folder_id>/upload", methods=["POST"])
@token_required
def upload_file(folder_id: int):
    """Upload a media file (geotagged photo, normal photo, video, or poster)."""
    if "file" not in request.files:
        raise ValidationError("No file was uploaded in the 'file' field.")

    uploaded_file = request.files["file"]
    if not uploaded_file.filename:
        raise ValidationError("Uploaded file has no filename.")

    category = request.form.get("category", MediaFile.CATEGORY_PHOTOS)
    destination = request.form.get("destination", "firebase")

    media_file = MediaService.upload_media(
        folder_id=folder_id,
        file_obj=uploaded_file.stream,
        filename=uploaded_file.filename,
        category=category,
        user=g.current_user,
        destination=destination,
        mime_type=uploaded_file.content_type
    )

    return success_response(
        data=media_file.to_dict(),
        message=f"File uploaded successfully to {media_file.storage_provider}.",
        status_code=201
    )


@media_bp.route("/folders/<int:folder_id>/files", methods=["GET"])
@token_required
def list_files(folder_id: int):
    """List media files inside an event folder, optionally filtered by category."""
    category = request.args.get("category")
    files = MediaService.list_folder_media(folder_id, g.current_user, category=category)
    return success_response(data=[f.to_dict() for f in files])


@media_bp.route("/files/<int:file_id>", methods=["GET"])
@token_required
def get_file(file_id: int):
    """Get metadata for a single media file."""
    media_file = MediaService.get_media_file(file_id, g.current_user)
    return success_response(data=media_file.to_dict())


@media_bp.route("/files/<int:file_id>/download", methods=["GET"])
@token_required
def download_file(file_id: int):
    """Download media file bytes or redirect to storage URL."""
    media_file = MediaService.get_media_file(file_id, g.current_user)

    if media_file.storage_provider == MediaFile.PROVIDER_GOOGLE_DRIVE:
        if media_file.drive_web_view_link:
            return redirect(media_file.drive_web_view_link)
        raise NotFoundError("Google Drive web link not available for this file.")

    # Firebase or local storage
    if not media_file.storage_path:
        raise NotFoundError("File storage path is missing.")

    file_bytes = FirebaseStorageService.get_file_bytes(media_file.storage_path)
    return send_file(
        io.BytesIO(file_bytes),
        mimetype=media_file.mime_type or "application/octet-stream",
        as_attachment=True,
        download_name=media_file.original_filename
    )


@media_bp.route("/files/<int:file_id>", methods=["DELETE"])
@token_required
def delete_file(file_id: int):
    """Delete or unlink a media file."""
    MediaService.delete_media_file(file_id, g.current_user)
    return success_response(message="Media file removed successfully.")


# -----------------------------------------------------------------------------
# Google Drive OAuth & Linking Endpoints
# -----------------------------------------------------------------------------
@media_bp.route("/drive/status", methods=["GET"])
@token_required
def drive_status():
    """Get Google Drive connection status for the authenticated user."""
    status = GoogleDriveService.get_connection_status(g.current_user.id)
    return success_response(data=status)


@media_bp.route("/drive/auth-url", methods=["GET"])
@token_required
def drive_auth_url():
    """Get Google OAuth 2.0 authorization URL."""
    redirect_uri = request.args.get("redirect_uri")
    auth_url = GoogleDriveService.get_auth_url(g.current_user.id, redirect_uri=redirect_uri)
    return success_response(data={"auth_url": auth_url})


@media_bp.route("/drive/callback", methods=["GET"])
def drive_oauth_callback():
    """Handle Google OAuth 2.0 redirect callback."""
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    if error:
        return f"<h3>Google Authorization Cancelled or Failed: {error}</h3>", 400

    if not code or not state:
        return "<h3>Missing OAuth code or state parameter.</h3>", 400

    try:
        integration = GoogleDriveService.handle_oauth_callback(code, state)
        html_success = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Google Drive Connected</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #fafafa; }}
                .card {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); text-align: center; max-width: 400px; }}
                h2 {{ color: #111; margin-bottom: 12px; }}
                p {{ color: #666; font-size: 14px; line-height: 1.5; }}
                .email {{ font-weight: bold; color: #1a73e8; }}
                .btn {{ margin-top: 20px; display: inline-block; padding: 10px 20px; background: #111; color: white; border-radius: 6px; text-decoration: none; font-size: 14px; font-weight: 500; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h2>Google Drive Connected</h2>
                <p>Successfully linked Google Drive account: <br><span class="email">{integration.google_email or 'Authorized User'}</span></p>
                <p>You may now return to the Media Team dashboard in the app.</p>
                <a href="javascript:window.close()" class="btn">Close Window</a>
            </div>
        </body>
        </html>
        """
        return render_template_string(html_success)
    except Exception as e:
        logger.error("OAuth callback error: %s", e)
        return f"<h3>Google OAuth Error: {str(e)}</h3>", 400


@media_bp.route("/drive/disconnect", methods=["POST"])
@token_required
def drive_disconnect():
    """Disconnect and revoke Google Drive authorization."""
    GoogleDriveService.disconnect(g.current_user.id)
    return success_response(message="Google Drive disconnected successfully.")


@media_bp.route("/drive/folders", methods=["GET"])
@token_required
def drive_browse_folders():
    """Browse folders in user's authorized Google Drive."""
    query = request.args.get("q")
    folders = GoogleDriveService.list_folders(g.current_user.id, query=query)
    return success_response(data=folders)


@media_bp.route("/folders/<int:folder_id>/link-drive", methods=["POST"])
@token_required
def link_drive_folder(folder_id: int):
    """Link an existing Google Drive folder to an event folder."""
    data = request.get_json(silent=True) or {}
    drive_folder_id = data.get("drive_folder_id")
    drive_folder_name = data.get("drive_folder_name")
    web_view_link = data.get("web_view_link")

    folder = MediaService.link_drive_folder(
        folder_id=folder_id,
        drive_folder_id=drive_folder_id,
        drive_folder_name=drive_folder_name,
        web_view_link=web_view_link,
        user=g.current_user
    )
    return success_response(
        data=folder.to_dict(),
        message="Google Drive folder linked successfully."
    )


@media_bp.route("/folders/<int:folder_id>/unlink-drive", methods=["POST"])
@token_required
def unlink_drive_folder(folder_id: int):
    """Unlink Google Drive folder from an event folder."""
    folder = MediaService.unlink_drive_folder(folder_id, g.current_user)
    return success_response(
        data=folder.to_dict(),
        message="Google Drive folder unlinked successfully."
    )


@media_bp.route("/folders/<int:folder_id>/drive-files", methods=["GET"])
@token_required
def list_drive_folder_files(folder_id: int):
    """List files directly inside the linked Google Drive folder."""
    folder = MediaService.get_folder_by_id(folder_id, g.current_user)
    if not folder.linked_drive_folder_id:
        return success_response(data=[], message="No Google Drive folder linked.")

    category = request.args.get("category")
    query = request.args.get("q")
    files = GoogleDriveService.list_folder_files(
        user_id=g.current_user.id,
        drive_folder_id=folder.linked_drive_folder_id,
        category_filter=category,
        query=query
    )
    return success_response(data=files)


@media_bp.route("/folders/<int:folder_id>/link-drive-file", methods=["POST"])
@token_required
def link_drive_file(folder_id: int):
    """Link an existing Google Drive file into an event folder without copying bytes."""
    data = request.get_json(silent=True) or {}
    drive_file_id = data.get("drive_file_id")
    category = data.get("category")

    if not drive_file_id:
        raise ValidationError("Google Drive file ID is required.")

    media_file = MediaService.link_drive_file(
        folder_id=folder_id,
        drive_file_id=drive_file_id,
        user=g.current_user,
        category=category
    )
    return success_response(
        data=media_file.to_dict(),
        message="Google Drive file linked successfully.",
        status_code=201
    )


@media_bp.route("/folders/<int:folder_id>/upload-drive", methods=["POST"])
@token_required
def upload_drive(folder_id: int):
    """Upload a file directly to the event's linked Google Drive folder."""
    if "file" not in request.files:
        raise ValidationError("No file was uploaded in the 'file' field.")

    uploaded_file = request.files["file"]
    if not uploaded_file.filename:
        raise ValidationError("Uploaded file has no filename.")

    category = request.form.get("category", MediaFile.CATEGORY_PHOTOS)

    media_file = MediaService.upload_media(
        folder_id=folder_id,
        file_obj=uploaded_file.stream,
        filename=uploaded_file.filename,
        category=category,
        user=g.current_user,
        destination="google_drive",
        mime_type=uploaded_file.content_type
    )

    return success_response(
        data=media_file.to_dict(),
        message="File uploaded directly to Google Drive successfully.",
        status_code=201
    )
