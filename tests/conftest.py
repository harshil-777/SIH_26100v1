"""Test-wide safety setup. Runs before any test module imports the app.

app.db.session builds its engine from DATABASE_URL at import time, and the app's .env points at
the team's shared database. So before anything imports the app, DATABASE_URL is forced to
TEST_DATABASE_URL (a throwaway database, used only by tests/integration) or, when that is unset,
to an address nothing listens on. A test can therefore never reach a real database by accident.
"""
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
UNREACHABLE_DB = "postgresql+asyncpg://nobody:nothing@127.0.0.1:9/not_a_database"

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_DATABASE_URL:
    # The seeder wipes every table it loads. Refuse anything not obviously disposable.
    db_name = urlparse(TEST_DATABASE_URL.replace("+asyncpg", "")).path.lstrip("/")
    if not db_name.endswith("_test"):
        raise RuntimeError(
            f"TEST_DATABASE_URL must name a database ending in '_test' (got {db_name!r}); "
            "the integration tests wipe and reseed it."
        )

# Environment variables take precedence over .env in pydantic-settings.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL or UNREACHABLE_DB
os.environ["REDIS_URL"] = "redis://127.0.0.1:9/0"  # nothing listens: enqueue() fails fast
os.environ["SEED_DATA_DIR"] = str(REPO_ROOT / "WORKING DOCUMENTS")
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(prefix="gem-test-storage-")
os.environ["ADAPTER_MODE"] = "mock"
