"""Password policy shared by every endpoint that sets a user-chosen password.

The same rules are implemented client-side in frontend/lib/utils/password_policy.dart so users see
problems before submitting; the server is the authority.

Known-leaked passwords: set LEAKED_PASSWORD_HASHES_FILE to a file with one lowercase SHA-256 hex
digest per line (never commit plaintext leaked passwords). Create it from a plaintext list with:
    flask password-hashes --input leaked.txt --output /etc/secrets/leaked_password_hashes.txt
"""
import hashlib
import os
import re
import threading

MIN_LENGTH = 12
MAX_LENGTH = 128
SPECIAL_CHARS_PATTERN = re.compile(r"[^A-Za-z0-9\s]")

REQUIREMENTS = [
    f"At least {MIN_LENGTH} characters",
    "At least one uppercase letter",
    "At least one lowercase letter",
    "At least one number",
    "At least one special character (for example ! @ # $ %)",
]

# Small built-in deny-list of passwords that satisfy the character rules but are guessed first.
_COMMON = {
    "password123!", "password@123", "password1234!", "p@ssword1234", "p@ssw0rd1234", "qwerty123456!",
    "welcome@1234", "welcome123!", "admin@123456", "letmein12345!", "changeme123!", "iloveyou123!",
    "abcd@1234567", "abc@12345678", "qwerty@12345", "india@123456", "christ@12345", "christuniversity1!",
    "cuestic@1234", "cuestic@2026", "cuestic2026!", "password2026!", "welcome2026!",
}

_leaked_lock = threading.Lock()
_leaked_cache = {"path": None, "mtime": None, "hashes": frozenset()}


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _leaked_hashes() -> frozenset:
    path = os.environ.get("LEAKED_PASSWORD_HASHES_FILE", "").strip()
    if not path or not os.path.isfile(path):
        return frozenset()
    mtime = os.path.getmtime(path)
    with _leaked_lock:
        if _leaked_cache["path"] == path and _leaked_cache["mtime"] == mtime:
            return _leaked_cache["hashes"]
        with open(path, encoding="utf-8") as fh:
            hashes = frozenset(
                line.strip().lower() for line in fh if re.fullmatch(r"[0-9a-fA-F]{64}", line.strip())
            )
        _leaked_cache.update(path=path, mtime=mtime, hashes=hashes)
        return hashes


def is_known_leaked(password: str) -> bool:
    return password.lower() in _COMMON or _sha256(password) in _leaked_hashes()


def password_problems(password: str, username: str = None) -> list:
    """Return a list of human-readable problems; empty when the password is acceptable."""
    if not password:
        return ["Password is required."]
    problems = []
    if len(password) < MIN_LENGTH:
        problems.append(f"Must be at least {MIN_LENGTH} characters long.")
    if len(password) > MAX_LENGTH:
        problems.append(f"Must be at most {MAX_LENGTH} characters long.")
    if not re.search(r"[A-Z]", password):
        problems.append("Must contain an uppercase letter.")
    if not re.search(r"[a-z]", password):
        problems.append("Must contain a lowercase letter.")
    if not re.search(r"[0-9]", password):
        problems.append("Must contain a number.")
    if not SPECIAL_CHARS_PATTERN.search(password):
        problems.append("Must contain a special character.")
    if password != password.strip():
        problems.append("Must not start or end with a space.")
    if username:
        base = username.lower().split("@")[0].removesuffix(".cu")
        if len(base) >= 4 and base in password.lower():
            problems.append("Must not contain your username.")
    if not problems and is_known_leaked(password):
        problems.append("This password is too common or has appeared in a data leak. Choose a different one.")
    return problems
