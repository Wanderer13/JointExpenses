from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, joinedload

from app.models import Group, GroupMember, GroupStatus, ReminderSent, User
from app.services.balance_service import group_balances_payload, oldest_debt_age_days
from app.services.mail_stub import send_email


def process_debt_reminders(db: Session) -> int:
    """Send at most one reminder per debtor-creditor pair per week for overdue debts."""
    sent_count = 0
    groups = db.query(Group).filter(Group.status == GroupStatus.open).all()
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    for group in groups:
        payload = group_balances_payload(db, group)
        for transfer in payload["suggested_transfers"]:
            debtor_id = transfer["from_user_id"]
            creditor_id = transfer["to_user_id"]
            amount = transfer["amount_cents"]
            age = oldest_debt_age_days(db, group.id, debtor_id, creditor_id)
            if age is None or age < group.reminder_days:
                continue

            existing = (
                db.query(ReminderSent)
                .filter(
                    ReminderSent.group_id == group.id,
                    ReminderSent.debtor_id == debtor_id,
                    ReminderSent.creditor_id == creditor_id,
                )
                .first()
            )
            if existing and existing.sent_at:
                sent_at = existing.sent_at
                if sent_at.tzinfo is None:
                    sent_at = sent_at.replace(tzinfo=timezone.utc)
                if sent_at > week_ago:
                    continue

            debtor = db.get(User, debtor_id)
            creditor = db.get(User, creditor_id)
            if not debtor or not creditor:
                continue

            amount_major = amount / 100
            send_email(
                to=debtor.email,
                subject=f"Reminder: debt in group «{group.name}»",
                body=(
                    f"Hello {debtor.name},\n\n"
                    f"You still owe {creditor.name} {amount_major:.2f} {group.currency} "
                    f"in group «{group.name}» (debt older than {group.reminder_days} days).\n"
                ),
                meta={
                    "group_id": group.id,
                    "debtor_id": debtor_id,
                    "creditor_id": creditor_id,
                    "amount_cents": amount,
                },
            )
            if existing:
                existing.sent_at = now
            else:
                db.add(
                    ReminderSent(
                        group_id=group.id,
                        debtor_id=debtor_id,
                        creditor_id=creditor_id,
                        sent_at=now,
                    )
                )
            sent_count += 1

    if sent_count:
        db.commit()
    return sent_count


def send_group_close_report(db: Session, group: Group) -> None:
    members = (
        db.query(GroupMember)
        .options(joinedload(GroupMember.user))
        .filter(GroupMember.group_id == group.id)
        .all()
    )
    payload = group_balances_payload(db, group)
    lines = ["Final balances:"]
    for net in payload["nets"]:
        lines.append(f"- {net['name']}: {net['balance_cents'] / 100:.2f} {group.currency}")
    lines.append("")
    lines.append("Suggested transfers:")
    if not payload["suggested_transfers"]:
        lines.append("- all settled")
    else:
        for t in payload["suggested_transfers"]:
            lines.append(
                f"- {t['from_name']} → {t['to_name']}: {t['amount_cents'] / 100:.2f} {group.currency}"
            )
    body = "\n".join(lines)
    for member in members:
        send_email(
            to=member.user.email,
            subject=f"Group «{group.name}» closed — final report",
            body=body,
            meta={"group_id": group.id, "event": "group_closed"},
        )
