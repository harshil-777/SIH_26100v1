"""Make msme_eligibility a mandatory criterion on MSME-reserved tenders

A reservation bars non-MSME bidders outright, so ineligibility must disqualify the bid with that
reason rather than lower a weighted score (seed bid B010's expected ground truth). New tenders get
this from build_eligibility_rules_typed; this rewrites the configs already stored.

Revision ID: 0002
Revises: 0001
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_GRADED_WEIGHT = 0.20  # what build_eligibility_rules_typed used before this change


def _rewrite(to_type: str) -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT tender_id, eligibility_rules_json FROM tenders WHERE eligibility_rules_json IS NOT NULL")
    ).all()
    for tender_id, rules in rows:
        rules = rules if isinstance(rules, dict) else json.loads(rules)
        changed = False
        for criterion in rules.get("criteria", []):
            if criterion.get("id") != "msme_eligibility" or criterion.get("type") == to_type:
                continue
            criterion["type"] = to_type
            if to_type == "mandatory":
                criterion.pop("weight", None)
            else:
                criterion["weight"] = _GRADED_WEIGHT
            changed = True
        if changed:
            conn.execute(
                sa.text("UPDATE tenders SET eligibility_rules_json = CAST(:rules AS JSONB) WHERE tender_id = :tender_id"),
                {"rules": json.dumps(rules), "tender_id": tender_id},
            )


def upgrade() -> None:
    _rewrite("mandatory")


def downgrade() -> None:
    _rewrite("graded")
