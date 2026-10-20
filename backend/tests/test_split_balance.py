"""Kept for backward compatibility; covered in dedicated modules."""

from app.models import SplitType
from app.schemas import SplitParticipantIn
from app.services.balance_service import simplify_debts
from app.services.split_service import compute_split_amounts


def test_equal_split_preserves_cents():
    parts = [
        SplitParticipantIn(user_id=3),
        SplitParticipantIn(user_id=1),
        SplitParticipantIn(user_id=2),
    ]
    result = compute_split_amounts(100, SplitType.equal, parts)
    assert sum(r[1] for r in result) == 100


def test_simplify_debts_minimal():
    nets = {1: 50, 2: -30, 3: -20}
    transfers = simplify_debts(nets)
    assert sum(t[2] for t in transfers) == 50
    assert len(transfers) <= 2
