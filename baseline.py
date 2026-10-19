import duckdb
import json
from pathlib import Path
from datetime import datetime

FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%dT%H:%M:%S%z",
]


def parse_ts(value):
    if not value:
        return None

    value = value.strip()

    for fmt in FORMATS:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=None)
        except ValueError:
            continue

    return None

def percentage(part, total):
    if total == 0:
        return 0.0
    return round(part / total * 100, 2)

con = duckdb.connect()

con.create_function(
    "parse_ts",
    parse_ts,
    ["VARCHAR"],
    "TIMESTAMP",
    null_handling="special",
)

con.sql("""
    CREATE VIEW raw AS
    SELECT *
    FROM read_csv_auto(
        'tickets_export.csv',
        header=true,
        all_varchar=true
    )
""")

con.sql("""
    CREATE VIEW typed AS
    SELECT
        trim(ticket_id) AS ticket_id,
        received_at AS raw_received_at,
        routed_at AS raw_routed_at,
        assigned_team AS raw_assigned_team,
        parse_ts(received_at) AS received_at,
        parse_ts(routed_at) AS routed_at,
        lower(trim(assigned_team)) AS team
    FROM raw
""")

con.sql("""
    CREATE VIEW deduplicated AS
    SELECT
        ticket_id,
        raw_received_at,
        raw_routed_at,
        raw_assigned_team,
        received_at,
        routed_at,
        team
    FROM typed
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY ticket_id, received_at
        ORDER BY ticket_id
    ) = 1
""")

con.sql("""
    CREATE VIEW quarantined_negative_duration AS
    SELECT
        ticket_id,
        raw_received_at,
        raw_routed_at,
        raw_assigned_team,
        received_at,
        routed_at,
        team,
        date_diff('second', received_at, routed_at) / 60.0
            AS routing_minutes,
        'negative_duration' AS quarantine_reason
    FROM deduplicated
    WHERE received_at IS NOT NULL
      AND routed_at IS NOT NULL
      AND routed_at < received_at
""")

con.sql("""
    CREATE VIEW eligible AS
    SELECT
        ticket_id,
        received_at,
        routed_at,
        team,
        date_diff('second', received_at, routed_at) / 60.0
            AS routing_minutes
    FROM deduplicated
    WHERE received_at IS NOT NULL
      AND routed_at IS NOT NULL
      AND routed_at >= received_at
""")

# === DATA QUALITY REPORT ===

rows_in = con.sql(
    "SELECT COUNT(*) FROM raw"
).fetchone()[0]

rows_after_dedup = con.sql(
    "SELECT COUNT(*) FROM deduplicated"
).fetchone()[0]

duplicates_removed = rows_in - rows_after_dedup

unparseable_received = con.sql("""
    SELECT COUNT(*)
    FROM deduplicated
    WHERE received_at IS NULL
""").fetchone()[0]

not_yet_routed = con.sql("""
    SELECT COUNT(*)
    FROM deduplicated
    WHERE received_at IS NOT NULL
      AND routed_at IS NULL
""").fetchone()[0]

negative_duration = con.sql("""
    SELECT COUNT(*)
    FROM quarantined_negative_duration
""").fetchone()[0]

eligible_rows = con.sql(
    "SELECT COUNT(*) FROM eligible"
).fetchone()[0]

data_quality_report = {
    "rows_in": rows_in,
    "duplicates_removed": {
        "count": duplicates_removed,
        "pct_of_input": percentage(duplicates_removed, rows_in),
    },
    "rows_after_deduplication": rows_after_dedup,
    "unparseable_received": {
        "count": unparseable_received,
        "pct_of_unique": percentage(
            unparseable_received, rows_after_dedup
        ),
    },
    "not_yet_routed": {
        "count": not_yet_routed,
        "pct_of_unique": percentage(
            not_yet_routed, rows_after_dedup
        ),
    },
    "negative_duration": {
        "count": negative_duration,
        "pct_of_unique": percentage(
            negative_duration, rows_after_dedup
        ),
    },
    "eligible_for_routing_metrics": {
        "count": eligible_rows,
        "pct_of_input": percentage(eligible_rows, rows_in),
        "pct_of_unique": percentage(
            eligible_rows, rows_after_dedup
        ),
    },
}

print("\n=== DATA QUALITY REPORT ===")
print(json.dumps(data_quality_report, indent=2, sort_keys=True))

'''
print("\n=== NORMALIZED DATA ===")
print(
    con.sql("""
        SELECT ticket_id, received_at, routed_at, team
        FROM typed
        LIMIT 5
    """).fetchall()
)

print("\n=== UNPARSEABLE DATES ===")
print(
    con.sql("""
        SELECT COUNT(*)
        FROM typed
        WHERE received_at IS NULL
    """).fetchone()[0]
)

print("\n=== DATA QUALITY COUNTS ===")

print(
    "Total rows:",
    con.sql("SELECT COUNT(*) FROM raw").fetchone()[0],
)

print(
    "Rows with missing routed_at:",
    con.sql("""
        SELECT COUNT(*)
        FROM typed
        WHERE routed_at IS NULL
    """).fetchone()[0],
)

print(
    "Rows with negative duration:",
    con.sql("""
        SELECT COUNT(*)
        FROM typed
        WHERE received_at IS NOT NULL
          AND routed_at IS NOT NULL
          AND routed_at < received_at
    """).fetchone()[0],
)

print(
    "Duplicate rows:",
    con.sql("""
        SELECT COUNT(*) - COUNT(DISTINCT (ticket_id, received_at))
        FROM typed
    """).fetchone()[0],
)

print("\n=== DEDUPLICATION CHECK ===")

print(
    "Rows before deduplication:",
    con.sql("SELECT COUNT(*) FROM typed").fetchone()[0],
)

print(
    "Rows after deduplication:",
    con.sql("SELECT COUNT(*) FROM deduplicated").fetchone()[0],
)

print("\n=== ELIGIBLE RECORDS ===")

print(
    "Eligible rows:",
    con.sql("SELECT COUNT(*) FROM eligible").fetchone()[0],
)

print(
    "Excluded after deduplication:",
    con.sql("""
        SELECT COUNT(*) FROM deduplicated
    """).fetchone()[0]
    - con.sql("""
        SELECT COUNT(*) FROM eligible
    """).fetchone()[0],
)

print("\n=== ROUTING TIME BASELINE ===")

print(
    con.sql("""
        SELECT
            ROUND(quantile_cont(routing_minutes, 0.50), 2) AS p50_minutes,
            ROUND(quantile_cont(routing_minutes, 0.90), 2) AS p90_minutes,
            ROUND(AVG(routing_minutes), 2) AS mean_minutes
        FROM eligible
    """).fetchall()
)

print("\n=== DAILY TICKET VOLUME ===")

print(
    con.sql("""
        SELECT
            CAST(received_at AS DATE) AS day,
            COUNT(*) AS ticket_count
        FROM deduplicated
        WHERE received_at IS NOT NULL
        GROUP BY day
        ORDER BY day
    """).fetchall()
)

print("\n=== HOURLY TICKET DISTRIBUTION ===")

print(
    con.sql("""
        SELECT
            EXTRACT(HOUR FROM received_at) AS hour,
            COUNT(*) AS ticket_count
        FROM deduplicated
        WHERE received_at IS NOT NULL
        GROUP BY hour
        ORDER BY hour
    """).fetchall()
)
'''

# === BUILD BASELINE JSON ===

routing = con.sql("""
    SELECT
        ROUND(quantile_cont(routing_minutes, 0.50), 2),
        ROUND(quantile_cont(routing_minutes, 0.90), 2),
        ROUND(AVG(routing_minutes), 2)
    FROM eligible
""").fetchone()

daily_volume = con.sql("""
    SELECT
        CAST(received_at AS DATE) AS day,
        COUNT(*) AS ticket_count
    FROM deduplicated
    WHERE received_at IS NOT NULL
    GROUP BY day
    ORDER BY day
""").fetchall()

hourly_distribution = con.sql("""
    SELECT
        EXTRACT(HOUR FROM received_at) AS hour,
        COUNT(*) AS ticket_count,
        ROUND(
            quantile_cont(routing_minutes, 0.50),
            2
        ) AS p50_minutes
    FROM eligible
    GROUP BY hour
    ORDER BY hour
""").fetchall()

quality = {
    "rows_in": con.sql(
        "SELECT COUNT(*) FROM raw"
    ).fetchone()[0],

    "duplicates_removed": (
        con.sql("SELECT COUNT(*) FROM typed").fetchone()[0]
        - con.sql("SELECT COUNT(*) FROM deduplicated").fetchone()[0]
    ),

    "rows_after_deduplication": con.sql(
        "SELECT COUNT(*) FROM deduplicated"
    ).fetchone()[0],

    "unparseable_received": con.sql("""
        SELECT COUNT(*)
        FROM deduplicated
        WHERE received_at IS NULL
    """).fetchone()[0],

    "not_yet_routed": con.sql("""
        SELECT COUNT(*)
        FROM deduplicated
        WHERE received_at IS NOT NULL
          AND routed_at IS NULL
    """).fetchone()[0],

    "negative_duration": con.sql("""
        SELECT COUNT(*)
        FROM deduplicated
        WHERE received_at IS NOT NULL
          AND routed_at IS NOT NULL
          AND routed_at < received_at
    """).fetchone()[0],

    "eligible_for_routing_metrics": con.sql(
        "SELECT COUNT(*) FROM eligible"
    ).fetchone()[0],
}

over_1h = con.sql("""
    SELECT
        COUNT(*) FILTER (
            WHERE routing_minutes > 60
        ) AS tickets_over_1h,
        COUNT(*) AS eligible_tickets
    FROM eligible
""").fetchone()

pct_over_1h = percentage(over_1h[0], over_1h[1])

baseline = {
    "routing_time_minutes": {
        "p50": routing[0],
        "p90": routing[1],
        "mean": routing[2],
    },
    "daily_volume": [
        {"date": str(day), "count": count}
        for day, count in daily_volume
    ],
    "hourly_distribution": [
        {
            "hour": int(hour),
            "count": count,
            "p50_minutes": p50_minutes,
        }
        for hour, count, p50_minutes in hourly_distribution
    ],
    "data_quality": data_quality_report,
    "pct_over_1h": pct_over_1h,
    "source": "tickets_export.csv",
    "window_days": 14,
    "coverage_pct": percentage(
        quality["eligible_for_routing_metrics"],
        quality["rows_in"],
    ),
    "definitions": {
        "daily_volume": (
            "Unique records with a valid received_at timestamp, "
            "including records excluded from routing-time metrics."
        ),
        "hourly_distribution": (
            "Records eligible for routing-time metrics, grouped by "
            "the hour of received_at; count and p50 use this same cohort."
        ),
        "deduplication_key": ["ticket_id", "received_at"],
        "pct_over_1h": (
            "Percentage of eligible records with routing time strictly "
            "greater than 60 minutes."
        ),
    },
}

output_path = Path("baseline.json")
output_path.write_text(
    json.dumps(
        baseline,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ) + "\n",
    encoding="utf-8",
)

# === SLACK SUMMARY ===

summary = (
    f"Baseline from synthetic data ({quality['rows_in']} input rows): "
    f"routing p50 is {routing[0]} min, p90 is {routing[1]} min, "
    f"mean is {routing[2]} min, and {pct_over_1h}% of eligible "
    f"tickets took over 60 minutes. "
    f"Routing metrics use {quality['eligible_for_routing_metrics']} "
    f"eligible records ({baseline['coverage_pct']}% of input); "
    f"{quality['duplicates_removed']} duplicates were removed, while "
    f"{data_quality_report['unparseable_received']['count']} records "
    f"had invalid received timestamps, "
    f"{data_quality_report['not_yet_routed']['count']} had no routing "
    f"timestamp, and "
    f"{data_quality_report['negative_duration']['count']} "
    f"had negative durations, so validate these results against real data."
)

print("\n=== SLACK SUMMARY ===")
print(summary)

print("\n=== BASELINE JSON ===")
print(f"Saved: {output_path}")
print(f"Eligible records: {quality['eligible_for_routing_metrics']}")

print("\n=== NEGATIVE DURATION QUARANTINE ===")

print(
    "Quarantined rows:",
    con.sql("""
        SELECT COUNT(*)
        FROM quarantined_negative_duration
    """).fetchone()[0],
)

print(
    "Sample quarantined records:",
    con.sql("""
        SELECT
            ticket_id,
            raw_received_at,
            raw_routed_at,
            routing_minutes,
            quarantine_reason
        FROM quarantined_negative_duration
        ORDER BY ticket_id
        LIMIT 5
    """).fetchall(),
)

print("\n=== ROUTING OVER ONE HOUR ===")

print(
    con.sql("""
        SELECT
            COUNT(*) FILTER (
                WHERE routing_minutes > 60
            ) AS tickets_over_1h,
            COUNT(*) AS eligible_tickets,
            ROUND(
                100.0 * COUNT(*) FILTER (
                    WHERE routing_minutes > 60
                ) / NULLIF(COUNT(*), 0),
                2
            ) AS pct_over_1h
        FROM eligible
    """).fetchall()
)

print("\n=== HOURLY ROUTING P50 ===")

print(
    con.sql("""
        SELECT
            EXTRACT(HOUR FROM received_at) AS hour,
            COUNT(*) AS ticket_count,
            ROUND(
                quantile_cont(routing_minutes, 0.50),
                2
            ) AS p50_minutes
        FROM eligible
        GROUP BY hour
        ORDER BY hour
    """).fetchall()
)