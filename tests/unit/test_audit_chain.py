"""Hash-chain verification over in-memory rows (no database)."""
from types import SimpleNamespace

from app.services.audit import compute_curr_hash, find_breaks, verify_chain


def chain(*payloads):
    rows, prev = [], None
    for log_id, payload in enumerate(payloads, start=1):
        curr = compute_curr_hash(prev, payload)
        rows.append(SimpleNamespace(log_id=log_id, prev_hash=prev, curr_hash=curr, payload_json=payload))
        prev = curr
    return rows


def test_untouched_chain_verifies():
    assert verify_chain(chain({"a": 1}, {"b": 2}, {"c": 3})) == (True, [])


def test_hash_covers_previous_hash_so_identical_payloads_hash_differently():
    first, second = chain({"same": 1}, {"same": 1})
    assert first.curr_hash != second.curr_hash


def test_edited_payload_is_caught_at_that_entry():
    rows = chain({"score": 40}, {"score": 76}, {"score": 100})
    rows[1].payload_json = {"score": 99}
    assert find_breaks(rows) == [{"log_id": 2, "problem": "curr_hash does not match this entry's payload"}]


def test_deleted_middle_entry_is_caught_at_the_next_one():
    rows = chain({"n": 1}, {"n": 2}, {"n": 3})
    del rows[1]
    assert [b["log_id"] for b in find_breaks(rows)] == [3]


def test_reordered_entries_are_caught():
    rows = chain({"n": 1}, {"n": 2}, {"n": 3})
    rows[1], rows[2] = rows[2], rows[1]
    assert not verify_chain(rows)[0]


def test_forged_entry_with_recomputed_hash_still_breaks_the_link_after_it():
    rows = chain({"n": 1}, {"n": 2}, {"n": 3})
    forged = {"n": 2, "decision": "qualify"}
    rows[1].payload_json, rows[1].curr_hash = forged, compute_curr_hash(rows[1].prev_hash, forged)
    assert [b["log_id"] for b in find_breaks(rows)] == [3]


def test_empty_prev_hash_on_the_first_entry_is_treated_as_genesis():
    rows = chain({"n": 1})
    rows[0].prev_hash = ""
    assert verify_chain(rows) == (True, [])


def test_broken_ids_are_reported_once_even_when_both_checks_fail():
    rows = chain({"n": 1}, {"n": 2})
    rows[1].prev_hash, rows[1].payload_json = "bogus", {"n": 9}
    assert verify_chain(rows) == (False, ["2"])
