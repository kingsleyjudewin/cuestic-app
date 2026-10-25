import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

from app import create_app
from app.services.reminder_service import ReminderService


def main():
    """Manual CLI process to scan and generate due reminders."""
    app = create_app()
    with app.app_context():
        print("Starting reminder processing job...")
        stats = ReminderService.scan_and_generate_reminders()
        print("Reminder processing completed:")
        for k, v in stats.items():
            print(f"  - {k}: {v}")

        due = ReminderService.get_due_reminders()
        print(f"\nTotal reminders currently due for action: {len(due)}")
        for r in due:
            print(f"  [Reminder #{r.id}] Type: {r.reminder_type} | Assignment #{r.assignment_id} | Due: {r.scheduled_at}")


if __name__ == "__main__":
    main()
