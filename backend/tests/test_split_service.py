import pytest
from fastapi import HTTPException

from app.models import SplitType
from app.schemas import SplitParticipantIn
from app.services.split_service import compute_split_amounts


def test_equal_split_preserves_cents_and_order_rule():
    parts = [
        SplitParticipantIn(user_id=3),
        SplitParticipantIn(user_id=1),
        SplitParticipantIn(user_id=2),
    ]
    result = compute_split_amounts(100, SplitType.equal, parts)
    assert sum(r[1] for r in result) == 100
    by_user = {uid: amt for uid, amt, _ in result}
    assert by_user == {1: 34, 2: 33, 3: 33}


def test_equal_split_single_participant():
    result = compute_split_amounts(999, SplitType.equal, [SplitParticipantIn(user_id=7)])
    assert result == [(7, 999, None)]


def test_equal_split_divisible():
    parts = [SplitParticipantIn(user_id=i) for i in (1, 2, 4)]
    result = compute_split_amounts(300, SplitType.equal, parts)
    assert all(amt == 100 for _, amt, _ in result)


def test_shares_split_preserves_cents():
    parts = [
        SplitParticipantIn(user_id=1, shares=1),
        SplitParticipantIn(user_id=2, shares=2),
    ]
    result = compute_split_amounts(100, SplitType.shares, parts)
    assert sum(r[1] for r in result) == 100
    by_user = {uid: amt for uid, amt, _ in result}
    assert by_user[1] == 33
    assert by_user[2] == 67


def test_shares_split_keeps_input_order():
    parts = [
        SplitParticipantIn(user_id=5, shares=1),
        SplitParticipantIn(user_id=2, shares=1),
    ]
    result = compute_split_amounts(3, SplitType.shares, parts)
    assert [uid for uid, _, _ in result] == [5, 2]
    assert sum(amt for _, amt, _ in result) == 3


def test_exact_split_ok():
    parts = [
        SplitParticipantIn(user_id=1, amount_cents=40),
        SplitParticipantIn(user_id=2, amount_cents=60),
    ]
    result = compute_split_amounts(100, SplitType.exact, parts)
    assert sum(r[1] for r in result) == 100


def test_exact_split_mismatch_raises():
    parts = [
        SplitParticipantIn(user_id=1, amount_cents=40),
        SplitParticipantIn(user_id=2, amount_cents=50),
    ]
    with pytest.raises(HTTPException) as exc:
        compute_split_amounts(100, SplitType.exact, parts)
    assert exc.value.status_code == 400
    assert "!= expense amount" in str(exc.value.detail)


def test_reject_non_positive_amount():
    with pytest.raises(HTTPException) as exc:
        compute_split_amounts(0, SplitType.equal, [SplitParticipantIn(user_id=1)])
    assert exc.value.status_code == 400


def test_reject_empty_participants():
    with pytest.raises(HTTPException) as exc:
        compute_split_amounts(100, SplitType.equal, [])
    assert exc.value.status_code == 400


def test_reject_duplicate_participants():
    parts = [SplitParticipantIn(user_id=1), SplitParticipantIn(user_id=1)]
    with pytest.raises(HTTPException) as exc:
        compute_split_amounts(100, SplitType.equal, parts)
    assert "Duplicate" in str(exc.value.detail)


def test_reject_missing_shares():
    parts = [SplitParticipantIn(user_id=1, shares=None), SplitParticipantIn(user_id=2, shares=1)]
    with pytest.raises(HTTPException) as exc:
        compute_split_amounts(100, SplitType.shares, parts)
    assert "shares" in str(exc.value.detail).lower()
