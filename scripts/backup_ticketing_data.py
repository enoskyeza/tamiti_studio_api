"""Backup script for users and ticketing-related data.

Usage:
    python scripts/backup_ticketing_data.py

Creates a timestamped JSON file under ``backups/`` containing serialized
records for the critical authentication and ticketing models. The script can
be executed from the project root (the directory containing ``manage.py``).
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import django
from django.core import serializers


def setup_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
    django.setup()


def get_backup_path() -> str:
    backups_dir = os.path.join(os.path.dirname(__file__), "..", "backups")
    backups_dir = os.path.abspath(backups_dir)
    os.makedirs(backups_dir, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    filename = f"ticketing_backup_{timestamp}.json"
    return os.path.join(backups_dir, filename)


def serialize_queryset(queryset) -> list[dict]:
    """Return a list of plain dicts suitable for JSON serialization."""

    return json.loads(serializers.serialize("json", queryset))


def build_backup_payload() -> dict:
    from django.contrib.auth import get_user_model

    from ticketing.models import (
        Event,
        EventMembership,
        Batch,
        BatchMembership,
        Ticket,
        TicketType,
        ScanLog,
        TemporaryUser,
    )

    User = get_user_model()

    payload = {
        "users": serialize_queryset(User.objects.all()),
        "events": serialize_queryset(Event.objects.all()),
        "event_memberships": serialize_queryset(EventMembership.objects.all()),
        "batches": serialize_queryset(Batch.objects.all()),
        "batch_memberships": serialize_queryset(BatchMembership.objects.all()),
        "ticket_types": serialize_queryset(TicketType.objects.all()),
        "tickets": serialize_queryset(Ticket.objects.all()),
        "scan_logs": serialize_queryset(ScanLog.objects.all()),
        "temporary_users": serialize_queryset(TemporaryUser.objects.all()),
    }

    return payload


def write_backup(payload: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


def main() -> None:
    setup_django()
    payload = build_backup_payload()
    backup_path = get_backup_path()
    write_backup(payload, backup_path)
    print(f"Backup written to {backup_path}")


if __name__ == "__main__":
    main()
