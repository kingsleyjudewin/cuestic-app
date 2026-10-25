# Department Club Task Assignment Backend API

A production-minded, secure, and maintainable RESTful API backend designed for university departmental clubs to assign responsibilities to student members for events, track confirmations, generate user-controlled click-to-chat WhatsApp assignment messages, and automate task follow-up reminders.

Built with Python 3, Flask, SQLAlchemy, Alembic, and Marshmallow.

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Architecture & Module Responsibilities](#2-architecture--module-responsibilities)
3. [System Prerequisites](#3-system-prerequisites)
4. [Virtual Environment Setup](#4-virtual-environment-setup)
5. [Dependency Installation](#5-dependency-installation)
6. [Environment Configuration](#6-environment-configuration)
7. [Database Migrations](#7-database-migrations)
8. [Administrator Initialization & Seed Data](#8-administrator-initialization--seed-data)
9. [Development Server Startup](#9-development-server-startup)
10. [Production Deployment Guidance](#10-production-deployment-guidance)
11. [API Endpoint Reference](#11-api-endpoint-reference)
12. [Authentication & Authorization Rules](#12-authentication--authorization-rules)
13. [WhatsApp Integration Philosophy & Limitations](#13-whatsapp-integration-philosophy--limitations)
14. [Reminder Engine & Background Scheduler](#14-reminder-engine--background-scheduler)
15. [Automated Testing & Coverage](#15-automated-testing--coverage)
16. [Database Backup & Restore Procedure](#16-database-backup--restore-procedure)
17. [Troubleshooting & FAQ](#17-troubleshooting--faq)

---

## 1. Project Overview

During university department symposiums and student club events, authorized team leaders and club presidents must coordinate dozens of tasks across specialized student committees. This backend provides:

- **Team & Membership Directory**: Centralized roster with academic details, phone number masking for privacy, and team allocations.
- **Configurable Four-Team Structure**: Seeds initial confirmed teams (*Volunteering*, *Documentation*, *Media*) while allowing dynamic addition or renaming of a fourth department-specific operational team (e.g. *Logistics*, *Catering*, or *Sponsorship*).
- **Multi-Member Task Assignment**: Assign tasks to one or several members simultaneously inside atomic database transactions.
- **User-Controlled WhatsApp Dispatch**: Generates localized, prefilled `https://wa.me/{phone}?text={encoded_message}` links. **Zero paid third-party APIs**, zero browser automation, zero fake message statuses. Delivery remains completely in the hands of the team leader.
- **Intelligent Reminder Engine**: Automatically identifies unconfirmed assignments, approaching deadlines, and overdue items with unique deduplication keys.
- **Audit Trails**: Full logging of administrative actions, task assignment lifecycle transitions, and message actions.

---

## 2. Architecture & Module Responsibilities

The application follows a modular Flask application factory design with strict separation of concerns:

```
cuestic-vp-app/
├── app/
│   ├── __init__.py           # Application factory (create_app)
│   ├── config.py             # Development, Testing, Production configurations
│   ├── extensions.py         # SQLAlchemy, Migrate, Limiter, CORS, Swagger
│   ├── models/               # SQLAlchemy ORM models
│   │   ├── user.py           # User & ApiToken (SHA-256 revocable tokens)
│   │   ├── team.py           # Departmental teams with slugs & leaders
│   │   ├── member.py         # Student members with phone normalization & privacy
│   │   ├── event.py          # Event model with state transition machine
│   │   ├── task.py           # Tasks with priority & deadlines
│   │   ├── task_assignment.py# Individual member assignment states
│   │   ├── message_log.py    # WhatsApp message drafts and user actions
│   │   ├── reminder.py       # Deduplicated reminders (due/scheduled/actioned)
│   │   └── activity_log.py   # Administrative audit logging
│   ├── api/                  # RESTful API Blueprints (/api/v1)
│   │   ├── auth.py           # Login, logout, /me
│   │   ├── dashboard.py      # Aggregated metrics & upcoming deadlines
│   │   ├── teams.py          # Team CRUD, configurable 4th team, membership
│   │   ├── members.py        # Member CRUD, phone normalization, soft deactivation
│   │   ├── events.py         # Event lifecycle, archive, event-teams
│   │   ├── tasks.py          # Multi-member assignment, cancellation
│   │   ├── assignments.py    # Confirm, submit, complete, block, decline
│   │   ├── whatsapp.py       # Personalized drafts, wa.me links, action tracking
│   │   ├── reminders.py      # Due reminders, manual schedule, scan triggers
│   │   └── reports.py        # Assignment reports with filtering & completion rates
│   ├── services/             # Pure business logic and database transaction management
│   │   ├── auth_service.py
│   │   ├── member_service.py
│   │   ├── task_service.py
│   │   ├── whatsapp_service.py
│   │   ├── reminder_service.py
│   │   └── audit_service.py
│   ├── schemas/              # Marshmallow request/response serialization & validation
│   └── utils/                # Helper utilities (permissions, phones, datetimes, errors)
├── migrations/               # Alembic database version control
├── tests/                    # 56 automated pytest unit & integration tests
├── scripts/
│   ├── seed_data.py          # Idempotent development seeder
│   ├── process_reminders.py  # CLI / Cron reminder runner
│   └── backup_database.py    # Atomic SQLite backup & restore with 0600 permissions
├── .env.example              # Sample environment template
├── requirements.txt          # Python dependencies
├── pyproject.toml            # Build metadata & pytest configuration
└── wsgi.py                   # WSGI application entrypoint
```

---

## 3. System Prerequisites

- **Operating System**: Linux (Ubuntu 22.04 / 24.04 LTS recommended), macOS, or Windows WSL2.
- **Python**: Python 3.12 or compatible (verified on Python 3.14.4).
- **SQLite**: SQLite 3.35+ (standard library).
- **Git**: Installed and configured.

---

## 4. Virtual Environment Setup

Create and activate an isolated Python virtual environment in the project root:

```bash
# Clone or enter the project directory
cd "/home/kingsley-judewin/cuestic vp app"

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate
```

---

## 5. Dependency Installation

With the virtual environment active, install all required dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 6. Environment Configuration

Copy `.env.example` to `.env` and configure parameters:

```bash
cp .env.example .env
```

Key environment variables:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `FLASK_ENV` | Environment mode (`development`, `testing`, `production`) | `development` |
| `SECRET_KEY` | Flask cryptographic secret key | Change in production |
| `DATABASE_URL` | SQLite database URI | `sqlite:///department_club.db` |
| `APP_TIMEZONE` | Club local timezone | `Asia/Kolkata` |
| `DEFAULT_COUNTRY_CODE`| Default phone region | `+91` |
| `TOKEN_EXPIRY_DAYS` | Mobile authentication token lifespan | `30` |
| `CONFIRMATION_REMINDER_HOURS` | Unconfirmed assignment threshold | `24` |
| `DEADLINE_REMINDER_HOURS` | Approaching deadline window | `24` |
| `ENABLE_BACKGROUND_SCHEDULER` | Run in-process APScheduler | `false` |
| `ADMIN_USERNAME` | Seed administrator username | `clubadmin` |
| `ADMIN_PASSWORD` | Seed administrator password | Set your secure password |
| `FOURTH_TEAM_NAME` | Configurable fourth team name | `Logistics` (or leave empty) |

---

## 7. Database Migrations

Database schema migrations are managed via Flask-Migrate (Alembic):

```bash
# Apply existing migrations to initialize the database
flask --app wsgi:app db upgrade

# To generate a new migration after editing models:
# flask --app wsgi:app db migrate -m "Description of model change"
```

---

## 8. Administrator Initialization & Seed Data

Run the idempotent seed script to create initial teams, the administrator account, sample members, and demo event tasks:

```bash
python scripts/seed_data.py
```

The seed script:
- Creates the 3 core teams (*Volunteering*, *Documentation*, *Media*) and the configurable 4th team if `FOURTH_TEAM_NAME` is set.
- Creates the President/Admin user with credentials from `.env` (or generates a secure temporary dev password).
- Creates a Team Leader user (`doc_leader`).
- Seeds 5 dummy members with synthetic phone numbers (`+91987650000X`).
- Seeds a demo event (`MAGNOVITE 2026`) and initial tasks with assignments.
- Is **100% idempotent** (safe to run repeatedly without duplicating records).

---

## 9. Development Server Startup

Run the development server via Flask CLI or Python:

```bash
# Option A: Python WSGI runner
python wsgi.py

# Option B: Flask CLI
flask --app wsgi:app run --host=0.0.0.0 --port=5000
```

The application will start on `http://127.0.0.1:5000`:
- **API Root**: `http://127.0.0.1:5000/`
- **Health Check**: `http://127.0.0.1:5000/health`
- **Interactive Swagger Documentation**: `http://127.0.0.1:5000/api/v1/docs/`

---

## 10. Production Deployment Guidance

1. **WSGI HTTP Server**: Run with Gunicorn behind Nginx:
   ```bash
   gunicorn --workers 4 --bind 127.0.0.1:8000 --access-logfile - wsgi:app
   ```
2. **Reverse Proxy (Nginx)**: Configure Nginx to forward requests, terminate SSL/TLS, and enforce request rate limits.
3. **Database Security**: Ensure the SQLite database file and directory permissions are restricted to `0600` and `0700` respectively.
4. **Environment Secrets**: Never commit `.env`. Ensure `SECRET_KEY` is a cryptographically strong random string (`openssl rand -hex 32`).

---

## 11. API Endpoint Reference

All endpoints are prefixed with `/api/v1`.

### Authentication
- `POST /api/v1/auth/login` — Authenticate credentials; returns revocable Bearer token.
- `POST /api/v1/auth/logout` — Revoke active token.
- `GET /api/v1/auth/me` — Return current authenticated user profile.

### Dashboard
- `GET /api/v1/dashboard/summary` — Aggregated metrics (active events, active members, assignments awaiting confirmation, overdue work, upcoming deadlines).

### Teams
- `GET /api/v1/teams` — List teams with live member counts.
- `GET /api/v1/teams/{team_id}` — Get team details.
- `POST /api/v1/teams` — Create a new team (e.g. configure fourth team).
- `PATCH /api/v1/teams/{team_id}` — Update team (rename or assign leader).
- `GET /api/v1/teams/{team_id}/members` — List members in team.

### Members
- `GET /api/v1/members` — Filter members by `team_id`, `search`, `class_name`, `is_active`, `page`, `per_page`.
- `GET /api/v1/members/{member_id}` — Member profile.
- `POST /api/v1/members` — Register member with phone validation and duplicate checks.
- `PATCH /api/v1/members/{member_id}` — Update details, team, or WhatsApp opt-in.
- `DELETE /api/v1/members/{member_id}` — Soft-deactivates if member has assignment history; hard-deletes if no history.

### Events
- `GET /api/v1/events` — List events with optional `status` filter.
- `GET /api/v1/events/{event_id}` — Get event details.
- `POST /api/v1/events` — Create event.
- `PATCH /api/v1/events/{event_id}` — Update event and validate status transitions.
- `POST /api/v1/events/{event_id}/archive` — Complete/archive event.
- `GET /api/v1/events/{event_id}/teams` — Load teams and member counts available for this event.

### Tasks
- `GET /api/v1/events/{event_id}/tasks` — List tasks for an event.
- `POST /api/v1/events/{event_id}/tasks` — Transactionally create task and assign to multiple members.
- `GET /api/v1/tasks/{task_id}` — Task details and assignment statuses.
- `PATCH /api/v1/tasks/{task_id}` — Update task details.
- `POST /api/v1/tasks/{task_id}/assignments` — Add more assignees to an active task.
- `POST /api/v1/tasks/{task_id}/cancel` — Cancel task and all active assignments/reminders.

### Task Assignments
- `GET /api/v1/assignments` — List and filter assignments by `event_id`, `team_id`, `member_id`, `status`, `overdue`.
- `GET /api/v1/assignments/{assignment_id}` — Assignment details.
- `PATCH /api/v1/assignments/{assignment_id}/status` — Update assignment status.
- `POST /api/v1/assignments/{assignment_id}/confirm` — Member accepts assignment.
- `POST /api/v1/assignments/{assignment_id}/submit` — Member submits completed work.
- `POST /api/v1/assignments/{assignment_id}/complete` — Authorized leader/admin approves completion.
- `POST /api/v1/assignments/{assignment_id}/decline` — Member declines assignment.
- `POST /api/v1/assignments/{assignment_id}/block` — Flag assignment as blocked.

### WhatsApp
- `POST /api/v1/assignments/{assignment_id}/message-draft` — Generate personalized draft text.
- `POST /api/v1/assignments/{assignment_id}/whatsapp-link` — Generate wa.me link with URL-encoded text.
- `POST /api/v1/assignments/{assignment_id}/message-action` — Record `link_opened`, `marked_sent`, `failed`.
- `GET /api/v1/assignments/{assignment_id}/message-history` — Audit trail of drafts and actions.

### Reminders & Reports
- `GET /api/v1/reminders` — List reminders.
- `GET /api/v1/reminders/due` — List reminders currently due.
- `POST /api/v1/reminders/process` — Trigger reminder scan.
- `POST /api/v1/reminders/{reminder_id}/actioned` — Mark reminder actioned.
- `POST /api/v1/assignments/{assignment_id}/reminders` — Schedule manual reminder.
- `GET /api/v1/reports/assignments` — Filterable assignment breakdown with completion rate metrics.

---

## 12. Authentication & Authorization Rules

### Token Authentication
- **Transport**: Standard HTTP `Authorization: Bearer <token>` header.
- **Storage**: Tokens are generated via `secrets.token_urlsafe(48)` and stored exclusively as SHA-256 hashes (`token_hash`) in the `api_tokens` database table. Plaintext tokens are never stored.
- **Revocation**: Logging out sets `is_revoked = True`. Expired or revoked tokens immediately fail authorization checks.

### Role-Based Access Control (RBAC)
- **President / Admin**: Full club-wide administrative control across all teams, members, events, and tasks.
- **Team Leader**: Restricted to their assigned teams. Can create tasks for and assign members of their own team, view team contact numbers, approve work submissions, and mark assignments completed. Cannot modify other teams.
- **Member**: Can log in to view their own profile and task assignments, confirm acceptance, submit progress, and flag blockers. **Cannot mark assignments completed** (requires leader approval) and **cannot view unmasked phone numbers** of other students.

---

## 13. WhatsApp Integration Philosophy & Limitations

The system strictly obeys university and WhatsApp policies:

1. **User-Controlled Action**: The application generates click-to-chat links (`https://wa.me/{normalized_phone}?text={encoded_message}`) that open WhatsApp on the administrator's phone or computer with a pre-filled draft. The administrator reviews the text and taps Send.
2. **Zero Paid APIs**: Does not require WhatsApp Business API or third-party messaging subscription charges.
3. **Zero Browser Automation**: Does not use unofficial headless scrapers, emulated clicks, or browser drivers.
4. **Honest Action Tracking**: Opening a link or marking a draft sent records an administrative intent in `MessageLog`. It **never claims verified delivery or read receipts**, and **never automatically marks an assignment as accepted**.
5. **Consent Enforcement**: Members who have withdrawn consent (`whatsapp_opt_in=False`) or who are inactive cannot be targeted for WhatsApp link generation.

---

## 14. Reminder Engine & Background Scheduler

The reminder engine enforces four core rules:
1. **Unconfirmed Assignments**: If an assignment remains in `awaiting_confirmation` after 24 hours, generates a `confirmation_reminder`.
2. **Approaching Deadlines**: If an active assignment is within 24 hours of its deadline, generates a `deadline_reminder`.
3. **Overdue Tasks**: If a deadline passes without completion, flags the task overdue and generates an `overdue_reminder`.
4. **Deduplication**: Reminders utilize strict composite deduplication keys (`f"{type}:{assignment_id}:{timestamp_bucket}"`). Re-running the scheduler multiple times will **never create duplicate reminders**.
5. **Terminal Cancellation**: Marking an assignment completed or cancelled immediately cancels any outstanding scheduled reminders.

### Running Reminders
- **CLI / Cron (Recommended)**:
  ```bash
  # Run manually or via crontab every 15 minutes:
  # */15 * * * * /path/to/.venv/bin/python /path/to/scripts/process_reminders.py >> /var/log/club_reminders.log 2>&1
  python scripts/process_reminders.py
  ```
- **API Trigger**: `POST /api/v1/reminders/process`
- **In-Process Scheduler**: Set `ENABLE_BACKGROUND_SCHEDULER=true` in `.env` to run APScheduler inside the Flask process.

---

## 15. Automated Testing & Coverage

The test suite runs against an isolated, temporary SQLite database and covers every endpoint, model, permission rule, and service.

```bash
# Run all tests
pytest

# Run tests with test coverage breakdown
pytest --cov=app tests/
```

### Verified Scenarios
- **Auth**: Token issuance, password hashing, token expiration, revocation on logout.
- **Members**: E.164 normalization, duplicate registration prevention, phone privacy masking, soft deactivation preserving historical assignments.
- **Teams**: Member counts, configurable 4th team creation and renaming.
- **Events & Tasks**: Atomic transaction rollback on partial assignment failure, date validation, state transitions.
- **WhatsApp**: URI encoding, opt-out enforcement, link-opened does not accept.
- **Permissions**: RBAC enforcement across President, Leader, and Member roles.
- **Reminders**: Confirmation, deadline, overdue detection, duplicate prevention on repeated runs, offline restart recovery.

---

## 16. Database Backup & Restore Procedure

The application includes an online, transaction-consistent SQLite backup script:

### Creating a Backup
```bash
python scripts/backup_database.py --backup
```
- Performs atomic backup using SQLite's online backup API without database locking.
- Creates timestamped file in `backups/department_club_backup_YYYYMMDD_HHMMSS.sqlite`.
- Enforces strict file permissions: directory `0700` and backup file `0600` (owner read/write only).

### Restoring from Backup
```bash
python scripts/backup_database.py --restore backups/department_club_backup_YYYYMMDD_HHMMSS.sqlite --db department_club.db
```

---

## 17. Troubleshooting & FAQ

**Q: Why do phone numbers appear as `+91*****43210`?**
A: To protect student privacy, phone numbers are masked when viewed by ordinary members or leaders of other teams. Only the club administrator or the team leader assigned to that member's team can view full contact numbers.

**Q: Can I add a fourth team with a custom name?**
A: Yes! Use the `POST /api/v1/teams` endpoint with `{"name": "Logistics"}` or configure `FOURTH_TEAM_NAME=Logistics` in `.env` prior to running `scripts/seed_data.py`.

**Q: What if a task assignment fails while creating a multi-member task?**
A: The backend wraps task creation and all assignee records in a single database transaction. If any selected member ID is invalid, inactive, or unauthorized, the entire transaction rolls back completely and no orphan records are created.

**Q: How do mobile applications connect?**
A: The mobile client issues a `POST /api/v1/auth/login` request, receives the Bearer token, stores it securely in device storage (e.g. Flutter Secure Storage / React Native Keychain), and includes it in the HTTP header:
`Authorization: Bearer <token>`.
