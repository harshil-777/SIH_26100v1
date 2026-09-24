"""Walk the whole audit_log and confirm every bid's hash chain is unbroken.

Run from the repo root (reads DATABASE_URL from .env like the app does):
    python scripts/verify_audit_chain.py

Talks to the database directly rather than through the API, so the check doesn't depend on
the service it is auditing. Exits 1 if any chain is broken. The same walk backs GET /audit/verify.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal  # noqa: E402
from app.services.audit import verify_all_chains  # noqa: E402


async def main() -> int:
    async with SessionLocal() as session:
        result = await verify_all_chains(session)

    print(f"Checked {result['entries_checked']} entries across {result['chains_checked']} bid chains.")
    if result["valid"]:
        print("OK: every chain verifies -- no edited, inserted, reordered or removed mid-chain entries.")
        return 0
    for found in result["breaks"]:
        print(f"BROKEN  {found['bid_id']}  log_id={found['log_id']}: {found['problem']}")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
