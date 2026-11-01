# Department Club Task Assignment Mobile Application

A clean, premium, minimal Flutter mobile application for managing departmental club tasks and member assignments. Built to connect seamlessly with the departmental Flask REST API backend.

---

## 1. Visual Design & Interface

- **Color Palette**:
  - Background: Pure White (`#FFFFFF`)
  - Primary Text: Solid Black (`#111111`)
  - Secondary Text: Slate Gray (`#6B7280`)
  - Borders: Thin Light Gray (`#E5E7EB`)
  - Accent / Primary Gradient: Subtle black-to-dark-gray (`#111111` to `#2E2E2E`)
- **Cards & Controls**: Minimal 8px rounded corners with 1px border lines.
- **Typography**: Clean, sans-serif typography with strict typographic hierarchy.
- **Form & Navigation**: Mobile-first, one-hand friendly layouts with keyboard overlap handling and clean validation feedback.

---

## 2. Architecture & Tech Stack

- **Framework**: Flutter 3.47+ (Dart 3.13+)
- **Networking**: `http` with centralized `ApiClient` (session expiration handling, error mapping, timeout controls)
- **Local Storage**: `sqflite` SQLite cache with table migrations for offline resilience
- **Credential Storage**: `flutter_secure_storage` for revocable Bearer tokens (never in SQLite)
- **WhatsApp Integration**: `url_launcher` for official prefilled `wa.me` links
- **Push Notifications**: `firebase_core` & `firebase_messaging` for Firebase Cloud Messaging (FCM)
- **Date Formatting**: `intl`

---

## 3. Screen Workflows

```
┌─────────────────────┐
│  1. Select Event    │ ── GET /api/v1/events (persists selected event locally)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  2. Select Team     │ ── GET /api/v1/events/{id}/teams (4 team rows with member counts)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 3. Member Directory │ ── GET /api/v1/teams/{id}/members (search by name/reg, multi-select)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 4. Create Task      │ ── POST /api/v1/events/{id}/tasks (title, description, priority, deadline)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 5. WhatsApp Message │ ── POST /api/v1/assignments/{id}/whatsapp-link & message-action
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 6. Track Assignment │ ── GET /api/v1/assignments & PATCH status transitions
└─────────────────────┘
```

### Screen Details

1. **Screen 1 — Select Event**: Small header `Club Tasks`, interactive event selector, available events list with dates and status badges, primary `Continue` button.
2. **Screen 2 — Select Team**: Displays exactly four team rows: *Volunteering*, *Documentation*, *Media*, and *Registration* (or dynamic 4th configured team). Shows live member counts and chevrons.
3. **Screen 3 — Member Directory**: Team header, search bar by name and registration number, member checkboxes preserving selections across filtering, member details (Name, Reg No, Class & Section, authorized phone numbers), and bottom `Assign Task (N)` button.
4. **Screen 4 — Create Assignment**: Displays selected event, team, and reviewable member chips. Form fields for Task Title, Description, Priority selector (Low, Medium, High, Urgent), and Date/Time picker for deadline. Validates inputs and prevents duplicate submissions.
5. **Screen 5 — Assignment Message**: Formatted task summary, plain-text preview of the server-generated WhatsApp notification, `Open WhatsApp` button (via `url_launcher`), and `Mark as Sent` button. Supports multi-member assignment tabs to open each conversation independently.
6. **Screen 6 — Assignment Tracking**: Three main filter tabs (*Pending*, *In Progress*, *Completed*), plus an *Overdue only* toggle with clear red `OVERDUE` badges. Displays member name, task title, event name, deadline, and status. Tapping opens detailed status transitions following backend RBAC rules.

---

## 4. Setup & Running Instructions

### Prerequisites
- Flutter SDK (version 3.24 or newer): [flutter.dev](https://flutter.dev)
- Running Flask backend instance

### Installation

```bash
cd frontend
flutter pub get
```

### Running the App

```bash
# Web
flutter run -d chrome

# Android Emulator
flutter run -d emulator-5554

# Physical Device
flutter run -d <device_id>
```

---

## 5. API Base URL Configuration

The mobile app includes a configurable server base URL setting directly on the Login screen:

- **Local Machine / Web**: `http://127.0.0.1:5000/api/v1`
- **Android Emulator**: `http://10.0.2.2:5000/api/v1` (maps to computer localhost)
- **Physical Phone (Wi-Fi)**: `http://192.168.1.X:5000/api/v1` (replace with computer local LAN IP)

Default setting is `http://127.0.0.1:5000/api/v1`. The configured URL is persisted in secure storage.

---

## 6. Firebase Cloud Messaging (FCM) Configuration

### Mobile Configuration
1. Create a Firebase project in the [Firebase Console](https://console.firebase.google.com/).
2. Add an Android app with package name `edu.university.club.mobile`.
3. Download `google-services.json` and place it in:
   ```
   mobile/android/app/google-services.json
   ```
4. For iOS: Download `GoogleService-Info.plist` and place it in:
   ```
   mobile/ios/Runner/GoogleService-Info.plist
   ```
5. The application gracefully initializes Firebase. If credentials are not present during initial local development, the app continues to operate normally in mock/development mode.

### Server-Side Push Delivery
The Flask server is the trusted sender:
- Device tokens are registered via `POST /api/v1/notifications/device-token`.
- Supply server credentials via environment variable:
  ```bash
  export FIREBASE_CREDENTIALS_PATH="/path/to/service-account.json"
  # or
  export FIREBASE_SERVICE_ACCOUNT_JSON='{"type": "service_account", ...}'
  ```
- When a task assignment is created or a status updates, the backend dispatches a push notification to the member's registered device.
- Tapping the push notification navigates directly to the assignment details screen.

---

## 7. SQLite Offline Caching

The app includes a local SQLite database (`department_club_cache.db`):
- **Cached Models**: Events, Teams, Members, Assignments, and Sync Timestamps.
- **Offline Banner**: App displays a subtle offline indicator (`Offline — Viewing cached records`) when the network is unreachable.
- **Source of Truth**: The Flask backend remains the source of truth for authorization and shared assignments. Mutation requests (creating assignments, updating statuses) explain when a connection is required.
- **Security**: Authentication tokens are **never** stored in SQLite; they reside solely in device secure storage (`FlutterSecureStorage`).

---

## 8. Running Automated Tests

Run the complete test suite:

```bash
cd frontend

# Run all unit, service, sqlite and widget tests
flutter test

# Run code analysis
flutter analyze
```

### Test Coverage Summary:
- `models_test.dart`: Serialization, deserialization, and state transition validation.
- `api_client_test.dart`: Consistent JSON parsing, 401 session expiration, 403, 404, 500 handling without leaking server traces.
- `storage_service_test.dart`: SQLite tables, schema migrations, member search filtering, assignment status filtering.
- `sync_service_test.dart`: Network fallback to SQLite cache, online sync, and offline mutation protection.
- `widget_workflow_test.dart`: Interactive widget tests across all screens (Event selection, 4-team row rendering, Member directory search preservation, Create assignment validation, WhatsApp message preview, Tracking filter tabs and overdue labels).

---

## 9. Troubleshooting

| Problem | Cause | Solution |
| :--- | :--- | :--- |
| `Unable to connect to the club server` | Physical device cannot reach `127.0.0.1` | Expand `Server API URL` on login screen and enter your computer's local Wi-Fi IP address (e.g. `http://192.168.1.50:5000/api/v1`) or `http://10.0.2.2:5000/api/v1` on Android emulator. |
| `Session expired` | Authentication token expired or revoked | The app will automatically prompt for login. Log in with admin or team leader credentials. |
| WhatsApp does not open | WhatsApp application is not installed | Tapping `Open WhatsApp` launches the official web/external app. Install WhatsApp or verify web launcher support. |
| Push notifications not received | Device token not registered or Firebase credentials missing on server | Ensure `FIREBASE_CREDENTIALS_PATH` is set on the Flask server and device permissions are granted. |
