# Quick Start Guide: Run on Localhost

This document provides instant, copy-paste instructions to run the entire platform (Flask Backend + Flutter Web Client) locally in seconds.

---

## 1. Instant 1-Command Startup

From the project root directory:

```bash
bash scripts/run_localhost.sh
```

This automated script:
1. Clears existing processes on ports `5000` and `8080`.
2. Verifies the Flutter Web bundle (or builds it if missing).
3. Starts the Flask backend on `http://127.0.0.1:5000`.
4. Starts the Flutter web server on `http://localhost:8080`.
5. Verifies backend health and prints live status.

---

## 2. Manual Startup (Step-by-Step)

If you prefer running the servers in separate terminals:

### Terminal 1: Backend API (Port 5000)
```bash
cd "/home/kingsley-judewin/cuestic vp app"
.venv/bin/python wsgi.py
```
* **API Root**: [http://127.0.0.1:5000](http://127.0.0.1:5000)
* **Health Check**: [http://127.0.0.1:5000/health](http://127.0.0.1:5000/health)
* **Interactive Swagger Docs**: [http://127.0.0.1:5000/api/v1/docs/](http://127.0.0.1:5000/api/v1/docs/)

### Terminal 2: Frontend Web Client (Port 8080)
```bash
cd "/home/kingsley-judewin/cuestic vp app"
.venv/bin/python -m http.server 8080 --directory frontend/build/web --bind 0.0.0.0
```
* **Frontend Web App**: [http://localhost:8080](http://localhost:8080)

> [!TIP]
> If developing Flutter code and you want hot reload:
> ```bash
> cd frontend
> /home/kingsley-judewin/flutter/bin/flutter run -d chrome
> ```

---

## 3. Verified Login Credentials (1 Real Account Per Role)

All credentials are tested and active:

| Role | Name | Username | Password | Team / Department |
| :--- | :--- | :--- | :--- | :--- |
| **President** | Club Executive Admin | `clubadmin` | `AdminPass123!Secure` | Executive Admin |
| **Admin** | Admin Staff | `admin_staff` | `AdminStaff2026!` | Department Office |
| **Team Leader** | John Victor | `john.victor` | `MemberPass2026!` | **MC Team** (Lead) |
| **Member (MC Anchor)** | Merrick | `merrick` | `MemberPass2026!` | **MC Team** (Anchor) |
| **Member (Volunteer)** | Jayani CU | `jayani.cu` | `jayani.cu@123` | Volunteering Team |
| **Faculty Coordinator** | Dr Chidambaram S | `chidambaram.s` | `Research2026!Chidambaram` | Hyperspectral Image Processing |
| **Student Researcher** | Vikram Aditya | `vikram.aditya` | `StudentPass2026!` | Hyperspectral Image Processing Lab |

---

## 4. Database Selection (`.env`)

Configure the database inside `.env`:

### Option A: Local SQLite (Fastest for Offline / Local Dev)
```bash
DATABASE_URL="sqlite:////home/kingsley-judewin/cuestic vp app/instance/department_club.db"
```

### Option B: Real Neon Cloud PostgreSQL
```bash
DATABASE_URL="postgresql://neondb_owner:<your-neon-password>@ep-soft-lab-b5wjojj5-pooler.c-7.us-east-2.aws.neon.tech/neondb?channel_binding=require&sslmode=require"
```

---

## 5. Rebuilding the Frontend Bundle

If you make modifications to files inside `frontend/lib/`, rebuild the web distribution:

```bash
cd "/home/kingsley-judewin/cuestic vp app/frontend"
/home/kingsley-judewin/flutter/bin/flutter build web
```

---

## 6. Stopping the Services

To shut down both servers running on ports 5000 and 8080:

```bash
fuser -k 5000/tcp 8080/tcp
```
