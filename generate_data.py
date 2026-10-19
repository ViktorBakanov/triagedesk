import csv
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 42
TOTAL_ROWS = 9_800
DUPLICATES = 900
NEGATIVE_RATE = 0.06

OUTPUT_FILE = Path("tickets_export.csv")

TEAMS = [
    "Support",
    " support",
    "SUPPORT ",
    "Sales",
    " sales ",
    "SALES",
    "Billing",
    " billing ",
    "BILLING",
]

TIMESTAMP_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%dT%H:%M:%S%z",
]


def format_timestamp(value: datetime, fmt: str) -> str:
    if fmt == TIMESTAMP_FORMATS[2]:
        value = value.replace(tzinfo=timezone.utc)

    return value.strftime(fmt)


def main():
    random.seed(SEED)

    unique_count = TOTAL_ROWS - DUPLICATES
    start = datetime(2026, 9, 1)
    rows = []

    negative_count = round(unique_count * NEGATIVE_RATE)
    negative_ids = set(
        random.sample(range(unique_count), negative_count)
    )

    for i in range(unique_count):
        received_at = start + timedelta(
            minutes=random.randint(0, 14 * 24 * 60 - 1)
        )

        received_at = received_at.replace(tzinfo=timezone.utc)

        # Большинство обращений маршрутизируется за 1–60 минут.
        duration_minutes = random.randint(1, 60)

        # Около 6% записей получат отрицательную длительность.
        if i in negative_ids:
            duration_minutes = -random.randint(1, 30)

        routed_at = received_at + timedelta(
            minutes=duration_minutes
        )

        fmt = random.choice(TIMESTAMP_FORMATS)

        rows.append({
            "ticket_id": f"T-{i + 1:05d}",
            "received_at": format_timestamp(received_at, fmt),
            "routed_at": format_timestamp(routed_at, fmt),
            "assigned_team": random.choice(TEAMS),
        })

    # Имитируем повторный экспорт: копируем 900 существующих записей.
        # Добавляем 20 обращений без времени маршрутизации.
    missing_routed = []

    for i in range(20):
        missing_routed.append({
            "ticket_id": f"MISSING-{i + 1:03d}",
            "received_at": "2026-09-10 12:00:00",
            "routed_at": "",
            "assigned_team": "Support",
        })

    rows.extend(missing_routed)

    # Добавляем 20 обращений с нераспознаваемым временем поступления.
    invalid_received = []

    for i in range(20):
        invalid_received.append({
            "ticket_id": f"INVALID-{i + 1:03d}",
            "received_at": "not-a-timestamp",
            "routed_at": "2026-09-10 12:30:00",
            "assigned_team": "Sales",
        })

    rows.extend(invalid_received)

    # Имитируем повторный экспорт: копируем 900 существующих записей.
    duplicates = random.sample(rows[:unique_count], DUPLICATES)
    rows.extend(duplicates)

    # Перемешиваем строки, чтобы дубликаты не шли подряд.
    random.shuffle(rows)

    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "ticket_id",
                "received_at",
                "routed_at",
                "assigned_team",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV created: {OUTPUT_FILE}")
    print(f"Total rows: {len(rows)}")
    print(f"Unique records before duplication: {unique_count}")
    print(f"Duplicate rows added: {DUPLICATES}")


if __name__ == "__main__":
    main()