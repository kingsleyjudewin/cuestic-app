"""Seed MC Team accounts and members idempotently."""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.team import Team
from app.models.member import Member
from app.services.member_service import MemberService
from app.api.teams import invalidate_teams_cache
from app.api.members import invalidate_members_cache

MC_MEMBERS = [
    {
        "full_name": "John Victor",
        "username": "john.victor",
        "email": "john.victor@gmail.com",
        "role": User.ROLE_TEAM_LEADER,
        "password": "MemberPass2026!",
        "phone_number": "+919986383984",
        "registration_number": "MC2026001",
        "section": "Lead",
    },
    {
        "full_name": "MC Lead Anchor",
        "username": "mc_lead",
        "email": "mc.lead@cuestic.edu",
        "role": User.ROLE_TEAM_LEADER,
        "password": "MemberPass2026!",
        "phone_number": "+919876500051",
        "registration_number": "MC2026002",
        "section": "Lead",
    },
    {
        "full_name": "Alex Rivera",
        "username": "mc_anchor",
        "email": "mc.anchor@cuestic.edu",
        "role": User.ROLE_MEMBER,
        "password": "MemberPass2026!",
        "phone_number": "+919876500052",
        "registration_number": "MC2026003",
        "section": "Host / MC",
    },
    {
        "full_name": "Merrick",
        "username": "merrick",
        "email": "merrick@gmail.com",
        "role": User.ROLE_MEMBER,
        "password": "MemberPass2026!",
        "phone_number": "+919022469808",
        "registration_number": "MC2026004",
        "section": "Anchor",
    },
    {
        "full_name": "Afra",
        "username": "afra",
        "email": "afra@gmail.com",
        "role": User.ROLE_MEMBER,
        "password": "MemberPass2026!",
        "phone_number": "+919845314703",
        "registration_number": "MC2026005",
        "section": "Anchor",
    },
    {
        "full_name": "Abishek Cu",
        "username": "abishek.cu",
        "email": "abishek.cu@gmail.com",
        "role": User.ROLE_MEMBER,
        "password": "MemberPass2026!",
        "phone_number": "+917338796125",
        "registration_number": "MC2026006",
        "section": "Anchor",
    },
    {
        "full_name": "Prarthana Venkatesh",
        "username": "prarthana.venkatesh",
        "email": "prarthana.venkatesh@gmail.com",
        "role": User.ROLE_MEMBER,
        "password": "MemberPass2026!",
        "phone_number": "+919964697363",
        "registration_number": "MC2026007",
        "section": "Anchor",
    },
]

def seed_mc_accounts():
    app = create_app("development")
    with app.app_context():
        # 1. Ensure MC Team exists
        mc_team = Team.query.filter((Team.slug == "mc") | (Team.name.ilike("%MC%"))).first()
        if not mc_team:
            mc_team = Team(
                name="MC Team",
                slug="mc",
                description="Master of Ceremonies and Event Hosting Team",
                is_active=True,
            )
            db.session.add(mc_team)
            db.session.commit()
            print(f"Created MC Team with ID {mc_team.id}")
        else:
            print(f"Found existing MC Team with ID {mc_team.id}")

        # 2. Create or update each account
        created_count = 0
        updated_count = 0
        admin_user = User.query.filter_by(role=User.ROLE_PRESIDENT).first()
        actor_id = admin_user.id if admin_user else 1

        for rec in MC_MEMBERS:
            user = User.query.filter(
                (User.username == rec["username"]) | (User.email == rec["email"])
            ).first()

            if not user:
                member_data = {
                    "full_name": rec["full_name"],
                    "username": rec["username"],
                    "email": rec["email"],
                    "password": rec["password"],
                    "role": rec["role"],
                    "team_id": mc_team.id,
                    "phone_number": rec["phone_number"],
                    "registration_number": rec["registration_number"],
                    "section": rec.get("section"),
                }
                member, user = MemberService.create_member_account(
                    data=member_data,
                    actor_user_id=actor_id,
                    commit=False,
                )
                created_count += 1
                print(f" [+] Created user '{user.username}' and linked member '{member.full_name}'")
            else:
                # Update existing user role and password
                user.role = rec["role"]
                user.set_password(rec["password"])
                user.is_active = True
                user.credential_setup_status = "completed"
                # Check member link
                if not user.linked_member:
                    member = Member(
                        full_name=rec["full_name"],
                        email=rec["email"],
                        registration_number=rec["registration_number"],
                        section=rec.get("section"),
                        phone_number=rec["phone_number"],
                        country_code="+91",
                        team_id=mc_team.id,
                        linked_user_id=user.id,
                        whatsapp_opt_in=True,
                        is_active=True,
                    )
                    db.session.add(member)
                else:
                    user.linked_member.team_id = mc_team.id
                    user.linked_member.full_name = rec["full_name"]
                    user.linked_member.email = rec["email"]
                    user.linked_member.is_active = True
                updated_count += 1
                print(f" [*] Updated user '{user.username}' and linked to MC Team")

        # Set MC Team leader if not set
        john = User.query.filter_by(username="john.victor").first()
        if john and not mc_team.leader_user_id:
            mc_team.leader_user_id = john.id
            print(f"Assigned John Victor ({john.id}) as leader of MC Team")

        db.session.commit()
        invalidate_teams_cache()
        invalidate_members_cache()
        print(f"\nCompleted! Created: {created_count}, Updated: {updated_count}")
        print(f"MC Team now has {mc_team.members.count()} members.")

if __name__ == "__main__":
    seed_mc_accounts()
