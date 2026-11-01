#!/usr/bin/env python3
"""
Standalone execution wrapper for the Volunteer Import Command.

Usage:
    python scripts/import_volunteers.py --dry-run
    python scripts/import_volunteers.py --confirm --operator clubadmin
    python scripts/import_volunteers.py --file scripts/volunteers_input.json --confirm
"""
import os
import sys

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.cli import import_volunteers_command


def main():
    app = create_app()
    with app.app_context():
        # Delegate directly to the Click command with sys.argv[1:]
        try:
            import_volunteers_command.main(args=sys.argv[1:], prog_name="python scripts/import_volunteers.py")
        except SystemExit as e:
            sys.exit(e.code)


if __name__ == "__main__":
    main()
