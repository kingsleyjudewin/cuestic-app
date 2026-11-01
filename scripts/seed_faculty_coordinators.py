"""
Seed script for provisioning the initial 24 Faculty Coordinator accounts.
Department: Electronics and Communication Engineering
Idempotent: running again will not duplicate or overwrite existing accounts/passwords.
"""
import os
import re
import sys
import secrets
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app, db
from app.models.user import User
from app.models.research import FacultyProfile

FACULTY_SEED_DATA = [
    {
        "full_name": "Dr Ambily Babu",
        "specialization": "Electrical & Electronics Engineering Sciences",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E7053.jpg",
    },
    {
        "full_name": "Dr Arunraja A",
        "specialization": "Electronics and Communication Engineering",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E6776.jpg",
    },
    {
        "full_name": "Dr Chaitanya Kumar M V",
        "specialization": "Electronics & Computer Engineering",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E7424.jpg",
    },
    {
        "full_name": "Dr Chidambaram S",
        "specialization": "Hyperspectral Image Processing",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E2886.jpg",
    },
    {
        "full_name": "Dr Delson T R",
        "specialization": "Electronics and Communications",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E1890.jpg",
    },
    {
        "full_name": "Dr Eldho Paul",
        "specialization": "Deep Learning",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E6901.jpg",
    },
    {
        "full_name": "Dr Gokuraju Thriveni",
        "specialization": "Theoretical Modeling of Nanoelectronic Devices",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E5155.jpg",
    },
    {
        "full_name": "Dr Hari Murthy",
        "specialization": "Material Science",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E2996.jpg",
    },
    {
        "full_name": "Dr Inbanila K",
        "specialization": "Electronics and Communication Engineering",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E730.jpg",
    },
    {
        "full_name": "Jai Govind P",
        "specialization": "Electronics and Communication Engineering",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E5738.jpg",
    },
    {
        "full_name": "Dr Jesuwanth Sugesh R G",
        "specialization": "Optical Devices, Silicon Photonics",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E6380.jpg",
    },
    {
        "full_name": "Dr Jyotirmoy Pathak",
        "specialization": "Electronics and Communication Engineering",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E6792.jpg",
    },
    {
        "full_name": "Dr Kishorekumar R",
        "specialization": "Remote Sensing, VLSI Design",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E2460.jpg",
    },
    {
        "full_name": "Dr Mahipathi Ashoka Chakravarthi",
        "specialization": "Radar Signal Processing",
        "profile_image_url": "https://kp.christ.university.in/KnowledgePro/images/EmployeePhotos/E8327.jpg",
    },
    {
        "full_name": "Dr Naveen Kumar",
        "specialization": "Electronics and Communication Engineering",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E5606.jpg",
    },
    {
        "full_name": "Dr Praghash K",
        "specialization": "Wireless Sensor Networks and IoT",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E5933.jpg",
    },
    {
        "full_name": "Dr Ramkumar K",
        "specialization": "Semiconductor Device Modeling",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E8333.jpg",
    },
    {
        "full_name": "Dr Ranjith R",
        "specialization": "Electronics and Communication",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E4873.jpg",
    },
    {
        "full_name": "Dr Rusan Kumar Barik",
        "specialization": "RF and Microwave Engineering",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E10349.jpg",
    },
    {
        "full_name": "Dr Senthilnathan S",
        "specialization": "Electronics Engineering",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E6775.jpg",
    },
    {
        "full_name": "Dr Shashikumar D",
        "specialization": "Electronics and Communications",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E732.jpg",
    },
    {
        "full_name": "Dr Sourav Roy",
        "specialization": "Oxide-Based Resistive Switching Memory",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E5140.jpg",
    },
    {
        "full_name": "Dr Sujatha S",
        "specialization": "Wireless Communication",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E2782.jpg",
    },
    {
        "full_name": "Sushanth G",
        "specialization": "Digital Communication",
        "profile_image_url": "https://kp.christuniversity.in/KnowledgePro/images/EmployeePhotos/E1869.jpg",
    },
]

DEPARTMENT = "Electronics and Communication Engineering"


def normalize_to_username(name: str) -> str:
    """
    Generate normalized lowercase username from faculty name.
    e.g. 'Dr Ambily Babu' -> 'ambily.babu'
         'Dr Chaitanya Kumar M V' -> 'chaitanya.kumar.mv'
    """
    cleaned = re.sub(r'^(Dr\.?|Prof\.?|Mr\.?|Mrs\.?|Ms\.?)\s+', '', name, flags=re.IGNORECASE)
    cleaned = cleaned.strip().lower()
    cleaned = re.sub(r'[^a-z0-9\s]+', '', cleaned)
    parts = cleaned.split()
    username = '.'.join(parts)
    return username


def generate_temp_password(faculty_name: str) -> str:
    """
    Generates a secure, deterministic or unique temporary password.
    For standard initial seeding, uses format: Research2026!<CleanShortName>
    """
    clean = re.sub(r'^(Dr\.?|Prof\.?|Mr\.?|Mrs\.?|Ms\.?)\s+', '', faculty_name, flags=re.IGNORECASE).strip()
    first_word = clean.split()[0].capitalize()
    return f"Research2026!{first_word}"


def seed_faculty(app=None):
    if app is None:
        app = create_app(os.getenv("FLASK_ENV", "development"))

    created_accounts = []
    skipped_accounts = []

    with app.app_context():
        for item in FACULTY_SEED_DATA:
            full_name = item["full_name"]
            specialization = item["specialization"]
            image_url = item["profile_image_url"]
            base_username = normalize_to_username(full_name)

            # Check if faculty profile already exists
            existing_profile = FacultyProfile.query.filter_by(full_name=full_name).first()
            if existing_profile:
                skipped_accounts.append({
                    "full_name": full_name,
                    "username": existing_profile.user.username if existing_profile.user else base_username,
                    "status": "already_exists",
                })
                continue

            # Ensure unique username
            username = base_username
            suffix = 1
            while User.query.filter_by(username=username).first():
                suffix += 1
                username = f"{base_username}{suffix}"

            # Designate temporary password
            temp_password = generate_temp_password(full_name)

            # Create User
            user = User(
                username=username,
                role=User.ROLE_FACULTY_COORDINATOR,
                is_active=True,
                credential_setup_status="pending",
            )
            user.set_password(temp_password)
            db.session.add(user)
            db.session.flush()

            # Create FacultyProfile
            designation = "Associate Professor" if "Dr " in full_name else "Assistant Professor"
            profile = FacultyProfile(
                user_id=user.id,
                full_name=full_name,
                department=DEPARTMENT,
                designation=designation,
                specialization=specialization,
                profile_image_url=image_url,
                must_change_password=True,
            )
            db.session.add(profile)
            created_accounts.append({
                "id": user.id,
                "full_name": full_name,
                "username": username,
                "temp_password": temp_password,
                "specialization": specialization,
            })

        db.session.commit()

        print(f"\n--- FACULTY SEEDING SUMMARY ---")
        print(f"Created: {len(created_accounts)} accounts")
        print(f"Skipped (already present): {len(skipped_accounts)} accounts")

        # Save secure admin credential reference file (restricted permissions)
        admin_creds_path = Path(__file__).resolve().parent / "faculty_initial_credentials.txt"
        with open(admin_creds_path, "w") as f:
            f.write("# Confidential Faculty Coordinator Initial Credentials\n")
            f.write("# Admin reference only. Force password change is active for all accounts.\n\n")
            for acc in created_accounts:
                f.write(f"Name: {acc['full_name']}\n")
                f.write(f"Username: {acc['username']}\n")
                f.write(f"Temp Password: {acc['temp_password']}\n")
                f.write(f"Specialization: {acc['specialization']}\n")
                f.write("-" * 40 + "\n")
        try:
            os.chmod(admin_creds_path, 0o600)
        except Exception:
            pass

        print(f"Admin initial credential reference saved securely to: {admin_creds_path}")
        return created_accounts, skipped_accounts


if __name__ == "__main__":
    seed_faculty()
