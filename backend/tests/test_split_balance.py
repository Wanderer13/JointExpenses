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
    # sorted by user_id: 1,2,3 get 34,33,33
    by_user = {uid: amt for uid, amt, _ in result}
    assert by_user[1] == 34
    assert by_user[2] == 33
    assert by_user[3] == 33


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


def test_exact_split():
    parts = [
        SplitParticipantIn(user_id=1, amount_cents=40),
        SplitParticipantIn(user_id=2, amount_cents=60),
    ]
    result = compute_split_amounts(100, SplitType.exact, parts)
    assert sum(r[1] for r in result) == 100


def test_simplify_debts_minimal():
    # A +50, B -30, C -20
    nets = {1: 50, 2: -30, 3: -20}
    transfers = simplify_debts(nets)
    assert sum(t[2] for t in transfers) == 50
    assert sum(nets.values()) == 0
    assert len(transfers) <= 2
