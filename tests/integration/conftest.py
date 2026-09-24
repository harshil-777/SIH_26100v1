"""Integration fixtures: a throwaway Postgres database, migrated and seeded from the fixtures.

Point TEST_DATABASE_URL at a database whose name ends in "_test" (tests/conftest.py refuses
anything else, because seeding wipes it). With the Compose stack's local Postgres:

    docker compose up -d postgres
    TEST_DATABASE_URL=postgresql+asyncpg://gem:gem@localhost:5433/gem_compliance_test pytest

The database is created if missing. Without TEST_DATABASE_URL these tests are skipped.
"""
import csv
import os
import subprocess
import sys
from urllib.parse import urlparse, urlunparse

import asyncpg
import pytest

from tests.conftest import REPO_ROOT, TEST_DATABASE_URL

def pytest_collection_modifyitems(config, items):
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL not set (see tests/integration/conftest.py)")
    for item in items:
        if "tests/integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)  # so `pytest -m "not integration"` works
            if not TEST_DATABASE_URL:
                item.add_marker(skip)


async def _create_database_if_missing() -> None:
    parts = urlparse(TEST_DATABASE_URL.replace("+asyncpg", ""))
    name = parts.path.lstrip("/")
    admin = await asyncpg.connect(urlunparse(parts._replace(path="/postgres")))
    try:
        if not await admin.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", name):
            await admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        await admin.close()


@pytest.fixture(scope="session")
async def migrated_db():
    await _create_database_if_missing()
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="module")
async def seeded_db(migrated_db):
    """Fresh fixture data for each test module, so modules can't affect each other."""
    from app.config import get_settings
    from app.db.seed import seed
    from app.db.session import SessionLocal

    async with SessionLocal() as session:
        await seed(session, get_settings().seed_data_dir)


@pytest.fixture(scope="session")
def seed_bids() -> list[dict]:
    """Every seed bid with its scenario_tag and expected_ground_truth, from dummy_bidders.csv."""
    with (REPO_ROOT / "WORKING DOCUMENTS" / "dummy_bidders.csv").open(newline="") as f:
        rows = csv.DictReader(line for line in f if not line.startswith("#"))
        return [
            {**row, "bid_id": f"BID-{row['bidder_id']}-{row['target_tender_id']}"}
            for row in rows
            if row.get("scenario_tag")
        ]
