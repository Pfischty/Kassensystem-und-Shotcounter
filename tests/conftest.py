import os
from pathlib import Path

# Ensure app import runs in test mode and skips runtime DB bootstrap.
os.environ.setdefault("KASSENSYSTEM_TESTING", "1")

# Ensure tests never touch the runtime instance database.
_repo_root = Path(__file__).resolve().parent.parent
_test_db = _repo_root / "instance" / "pytest-test.db"
os.environ.setdefault("SQLALCHEMY_DATABASE_URI", f"sqlite:///{_test_db}")
