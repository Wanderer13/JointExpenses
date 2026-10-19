"""Expense split helpers.

Equal-split leftover-cent rule:
- Work in integer cents.
- base = total // n, remainder = total % n
- Participants are sorted by user_id ascending.
- The first `remainder` participants each get base + 1; the rest get base.
This is deterministic and always sums to the expense total.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from app.models import SplitType
from app.schemas import SplitParticipantIn


def compute_split_amounts(
    amount_cents: int,
    split_type: SplitType,
    participants: list[SplitParticipantIn],
) -> list[tuple[int, int, int | None]]:
    """Return list of (user_id, amount_cents, shares)."""
    if amount_cents <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    if not participants:
        raise HTTPException(status_code=400, detail="At least one participant required")

    user_ids = [p.user_id for p in participants]
    if len(user_ids) != len(set(user_ids)):
        raise HTTPException(status_code=400, detail="Duplicate participants")

    if split_type == SplitType.equal:
        ordered = sorted(participants, key=lambda p: p.user_id)
        n = len(ordered)
        base = amount_cents // n
        remainder = amount_cents % n
        result: list[tuple[int, int, int | None]] = []
        for i, p in enumerate(ordered):
            extra = 1 if i < remainder else 0
            result.append((p.user_id, base + extra, None))
        return result

    if split_type == SplitType.shares:
        shares_list = []
        for p in participants:
            if p.shares is None or p.shares < 1:
                raise HTTPException(status_code=400, detail="Each participant needs shares >= 1")
            shares_list.append((p.user_id, p.shares))
        total_shares = sum(s for _, s in shares_list)
        # Allocate floor first, then distribute leftover cents by fractional remainder desc, tie by user_id
        provisional: list[tuple[int, int, int, float]] = []
        allocated = 0
        for user_id, shares in shares_list:
            exact = amount_cents * shares / total_shares
            floor = int(exact)
            provisional.append((user_id, floor, shares, exact - floor))
            allocated += floor
        leftover = amount_cents - allocated
        provisional.sort(key=lambda x: (-x[3], x[0]))
        amounts = {user_id: floor for user_id, floor, _, _ in provisional}
        for i in range(leftover):
            amounts[provisional[i][0]] += 1
        return [(uid, amounts[uid], shares) for uid, shares in shares_list]

    if split_type == SplitType.exact:
        total = 0
        result = []
        for p in participants:
            if p.amount_cents is None or p.amount_cents < 0:
                raise HTTPException(status_code=400, detail="Exact split needs non-negative amount_cents")
            total += p.amount_cents
            result.append((p.user_id, p.amount_cents, None))
        if total != amount_cents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Exact split sum {total} != expense amount {amount_cents}",
            )
        return result

    raise HTTPException(status_code=400, detail="Unknown split type")
