from datetime import date, timedelta

from app.models import SettlementStatus
from app.services.balance_service import (
    compute_net_balances,
    group_balances_payload,
    oldest_debt_age_days,
    simplify_debts,
    user_balances_across_groups,
)
from tests.helpers import add_equal_expense, add_settlement


def test_simplify_debts_minimal_transfers():
    nets = {1: 50, 2: -30, 3: -20}
    transfers = simplify_debts(nets)
    assert sum(t[2] for t in transfers) == 50
    assert sum(nets.values()) == 0
    assert len(transfers) <= 2


def test_simplify_debts_already_settled():
    assert simplify_debts({1: 0, 2: 0}) == []


def test_simplify_debts_two_people():
    transfers = simplify_debts({1: 100, 2: -100})
    assert transfers == [(2, 1, 100)]


def test_net_balances_sum_to_zero(db, users, group_with_members):
    alice, bob, cara = users
    g = group_with_members
    add_equal_expense(
        db,
        group_id=g.id,
        payer_id=alice.id,
        amount_cents=10000,
        participant_ids=[alice.id, bob.id, cara.id],
    )
    nets = compute_net_balances(db, g.id)
    assert sum(nets.values()) == 0
    assert nets[alice.id] > 0
    assert nets[bob.id] < 0
    assert nets[cara.id] < 0


def test_pending_settlement_does_not_change_balance(db, users, group_with_members):
    alice, bob, cara = users
    g = group_with_members
    add_equal_expense(
        db,
        group_id=g.id,
        payer_id=alice.id,
        amount_cents=3000,
        participant_ids=[alice.id, bob.id, cara.id],
    )
    before = compute_net_balances(db, g.id)
    add_settlement(
        db,
        group_id=g.id,
        from_user_id=bob.id,
        to_user_id=alice.id,
        amount_cents=1000,
        status=SettlementStatus.pending,
    )
    after = compute_net_balances(db, g.id)
    assert after == before


def test_confirmed_settlement_reduces_debt(db, users, group_with_members):
    alice, bob, cara = users
    g = group_with_members
    add_equal_expense(
        db,
        group_id=g.id,
        payer_id=alice.id,
        amount_cents=3000,
        participant_ids=[alice.id, bob.id, cara.id],
    )
    before = compute_net_balances(db, g.id)
    add_settlement(
        db,
        group_id=g.id,
        from_user_id=bob.id,
        to_user_id=alice.id,
        amount_cents=1000,
        status=SettlementStatus.confirmed,
    )
    after = compute_net_balances(db, g.id)
    assert after[bob.id] == before[bob.id] + 1000
    assert after[alice.id] == before[alice.id] - 1000
    assert sum(after.values()) == 0


def test_delete_expense_effect_via_recompute(db, users, group_with_members):
    alice, bob, cara = users
    g = group_with_members
    expense = add_equal_expense(
        db,
        group_id=g.id,
        payer_id=alice.id,
        amount_cents=9000,
        participant_ids=[alice.id, bob.id, cara.id],
    )
    assert any(v != 0 for v in compute_net_balances(db, g.id).values())
    db.delete(expense)
    db.commit()
    nets = compute_net_balances(db, g.id)
    assert all(v == 0 for v in nets.values())


def test_group_balances_payload_structure(db, users, group_with_members):
    alice, bob, cara = users
    g = group_with_members
    add_equal_expense(
        db,
        group_id=g.id,
        payer_id=alice.id,
        amount_cents=1001,
        participant_ids=[alice.id, bob.id, cara.id],
    )
    payload = group_balances_payload(db, g)
    assert payload["sum_check"] == 0
    assert payload["currency"] == "USD"
    assert len(payload["nets"]) == 3
    assert payload["suggested_transfers"]


def test_user_balances_across_groups(db, users, group_with_members):
    alice, bob, cara = users
    g = group_with_members
    add_equal_expense(
        db,
        group_id=g.id,
        payer_id=alice.id,
        amount_cents=3000,
        participant_ids=[alice.id, bob.id, cara.id],
    )
    items = user_balances_across_groups(db, bob.id)
    assert len(items) == 1
    assert items[0]["group_id"] == g.id
    assert items[0]["balance_cents"] < 0


def test_oldest_debt_age_days(db, users, group_with_members):
    alice, bob, _cara = users
    g = group_with_members
    old = date.today() - timedelta(days=12)
    add_equal_expense(
        db,
        group_id=g.id,
        payer_id=alice.id,
        amount_cents=3000,
        participant_ids=[alice.id, bob.id],
        expense_date=old,
    )
    age = oldest_debt_age_days(db, g.id, bob.id, alice.id)
    assert age == 12
    assert oldest_debt_age_days(db, g.id, alice.id, bob.id) is None
