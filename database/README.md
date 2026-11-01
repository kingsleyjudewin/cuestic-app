# Database Architecture & Management

This directory contains database management assets, version-controlled migrations, automated backups, and initial seed datasets for the Department Club platform.

---

## Directory Structure

```
database/
├── migrations/          # Alembic / Flask-Migrate database migrations
│   ├── alembic.ini      # Alembic configuration
│   ├── env.py           # Migration runtime environment
│   ├── script.py.mako   # Migration revision template
│   └── versions/        # Versioned migration scripts
├── backups/             # Point-in-time SQLite database backups
│   └── department_club_backup_*.sqlite
├── seeds/               # Initial data feeds and volunteer manifests
│   └── volunteers_input.json
└── README.md            # This documentation
```

---

## Database Systems

1. **Cloud PostgreSQL (Neon)**:
   - Configured via `DATABASE_URL` in `.env`.
   - Used for staging and production deployments.
   - Fully supports concurrent connections with connection pooling.

2. **Local SQLite (`instance/department_club.db`)**:
   - Zero-dependency local fallback when `DATABASE_URL` is omitted.
   - Automated point-in-time backups managed via `python scripts/backup_database.py`.

---

## Common Database Commands

### Apply Migrations
```bash
flask db upgrade
```

### Create a New Migration
```bash
flask db migrate -m "Description of changes"
```

### Create an Offline SQLite Backup
```bash
python scripts/backup_database.py
```

### Restore an SQLite Backup
```bash
python scripts/backup_database.py --restore database/backups/department_club_backup_<TIMESTAMP>.sqlite
```

### Seed Development Data
```bash
python scripts/seed_data.py
```
