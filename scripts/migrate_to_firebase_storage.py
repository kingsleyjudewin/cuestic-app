#!/usr/bin/env python3
"""
Utility script to migrate all locally stored documents and media files to Firebase Cloud Storage.
Ensures that all assets are uploaded to the cloud and updates database records accordingly.
"""
import os
import sys

# Ensure root directory is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db
from app.models.media import MediaFile
from app.models.documentation import FolderDocument
from app.services.firebase_storage_service import FirebaseStorageService


def migrate_to_firebase(delete_local_after: bool = False):
    app = create_app()

    with app.app_context():
        print("=" * 65)
        print(" Department Club OS — Firebase Cloud Storage Migration Tool")
        print("=" * 65)

        # 1. Initialize and verify Firebase Storage
        print("\n[1/4] Verifying Firebase Cloud Storage connection...")
        is_ready = FirebaseStorageService.initialize(force_refresh=True)

        if not is_ready or FirebaseStorageService._bucket is None:
            bucket_name = os.environ.get("FIREBASE_STORAGE_BUCKET", "club-management-cuestic.firebasestorage.app")
            print("\n❌ Firebase Cloud Storage is not yet accessible!")
            print(f"Target Bucket: {bucket_name}")
            print("\nTo activate Cloud Storage for your Firebase project:")
            print("1. Open: https://console.firebase.google.com/project/club-management-cuestic/storage")
            print("2. Click 'Get started'")
            print("3. Accept the default location (e.g. asia-south1 or nam5) and rules.")
            print("4. Click 'Done'.")
            print("5. Once activated, re-run this script to transfer all files automatically.\n")
            sys.exit(1)

        bucket = FirebaseStorageService._bucket
        print(f"✅ Connected to Firebase Storage bucket: {bucket.name}")

        local_storage_dir = FirebaseStorageService.get_local_storage_dir()
        print(f"📁 Local storage directory: {local_storage_dir}")

        # 2. Migrate Media Files
        print("\n[2/4] Checking Media Files...")
        local_media = MediaFile.query.filter_by(storage_provider="local").all()
        print(f"Found {len(local_media)} media files currently marked as 'local'.")

        migrated_media = 0
        for m in local_media:
            if not m.storage_path:
                continue
            local_file_path = os.path.join(local_storage_dir, m.storage_path)
            if not os.path.exists(local_file_path):
                print(f"  ⚠️ Warning: Local file not found: {local_file_path}")
                continue

            print(f"  ⬆️ Uploading media #{m.id} ({m.original_filename}) -> gs://{bucket.name}/{m.storage_path}...")
            blob = bucket.blob(m.storage_path)
            with open(local_file_path, "rb") as f_in:
                blob.upload_from_file(f_in, content_type=m.mime_type or "application/octet-stream")

            m.storage_provider = MediaFile.PROVIDER_FIREBASE
            migrated_media += 1

            if delete_local_after:
                try:
                    os.remove(local_file_path)
                except Exception as e:
                    print(f"    Notice deleting local file: {e}")

        db.session.commit()
        print(f"✅ Migrated {migrated_media} media files to Firebase Cloud Storage.")

        # 3. Migrate Documentation Files
        print("\n[3/4] Checking Documentation Files...")
        docs = FolderDocument.query.all()
        print(f"Found {len(docs)} folder documents to verify/upload.")

        migrated_docs = 0
        for d in docs:
            if not d.storage_path:
                continue
            local_file_path = os.path.join(local_storage_dir, d.storage_path)
            blob = bucket.blob(d.storage_path)

            if blob.exists():
                continue  # Already present in cloud storage

            if os.path.exists(local_file_path):
                print(f"  ⬆️ Uploading doc #{d.id} ({d.original_filename}) -> gs://{bucket.name}/{d.storage_path}...")
                with open(local_file_path, "rb") as f_in:
                    blob.upload_from_file(f_in, content_type=d.content_type or "application/octet-stream")
                migrated_docs += 1

                if delete_local_after:
                    try:
                        os.remove(local_file_path)
                    except Exception as e:
                        print(f"    Notice deleting local file: {e}")

        print(f"✅ Migrated {migrated_docs} documentation files to Firebase Cloud Storage.")

        # 4. Summary
        print("\n[4/4] Migration Complete!")
        print(f"  - Total Media Migrated: {migrated_media}")
        print(f"  - Total Documents Migrated: {migrated_docs}")
        print("  - All storage pointers are now active in Firebase Cloud Storage.")
        print("=" * 65)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Migrate local files to Firebase Cloud Storage")
    parser.add_argument("--delete-local", action="store_true", help="Delete local files after successful upload")
    args = parser.parse_args()

    migrate_to_firebase(delete_local_after=args.delete_local)
