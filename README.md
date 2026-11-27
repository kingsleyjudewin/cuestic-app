# Cuestic

**A task and event management app for university department clubs.** Leaders assign tasks to student members, track progress, and send WhatsApp reminders, all in one place.

<p>
  <a href="https://cuestic-six.vercel.app/"><img alt="Open Web App" src="https://img.shields.io/badge/Open%20Web%20App-000000?style=for-the-badge&logo=vercel&logoColor=white"></a>
  <a href="https://github.com/kingsleyjudewin/cuestic-app/releases/latest"><img alt="Download APK" src="https://img.shields.io/badge/Download%20APK-3DDC84?style=for-the-badge&logo=android&logoColor=white"></a>
</p>

| Platform | Link |
|---|---|
| 🌐 Web app | https://cuestic-six.vercel.app/ |
| 📱 Android APK | [Latest release](https://github.com/kingsleyjudewin/cuestic-app/releases/latest). Download the `.apk` under **Assets**. |

> **Installing the APK:** open the downloaded file on your phone and allow "Install from unknown sources" if Android asks.

### 👀 Try it as a visitor

| Username | Password |
|---|---|
| `visitor` | `Visitor@2026` |

The visitor login opens the full **admin** app on a fresh, empty workspace. You can open every screen and portal, but you won't see any real club data, and nothing you do is saved.

---

## Features

- **Role-based dashboards** for Faculty, Volunteers, Media, Documentation, MC and Student Researchers
- **Events:** create events, pick teams, and follow each event from planning to archive
- **Task assignment:** give a task to one or many members, with priority and deadline
- **Assignment tracking:** members confirm, submit and complete tasks, and leaders see live status
- **WhatsApp messages:** ready-to-send `wa.me` links with prefilled text (no paid APIs)
- **Smart reminders** for unconfirmed, nearly due and overdue tasks
- **Member directory:** manage teams and members, with phone numbers masked for privacy
- **Documentation portal:** activity report editor and Word/Excel report export
- **Media folders:** upload and organise event photos and files
- **MC script editor** for event hosts
- **Community, notifications and reports** with completion rates
- **Visitor mode:** a shared demo login that explores the admin app on an empty, read-only workspace
- **Security:** token auth, rate limiting, a forced password change on first login, and audit logs

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Flutter (Web + Android) |
| Backend | Python, Flask REST API, SQLAlchemy, Alembic, Marshmallow |
| Database | PostgreSQL (Neon) |
| File storage | Firebase Storage |
| Scheduler | APScheduler (reminders) |
| Hosting | Vercel (web), Render (API), GitHub Releases (APK) |
| CI/CD | GitHub Actions |

## Run Locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in your values
flask db upgrade
bash scripts/run_localhost.sh
```

- Web app: http://localhost:8080
- API: http://127.0.0.1:5000 (Swagger docs at `/api/v1/docs/`)

More detail: [start.md](start.md) (local setup) · [DEPLOYMENT.md](DEPLOYMENT.md) (production deployment)
