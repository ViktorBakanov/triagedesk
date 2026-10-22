"""Create deterministic demo data when the source export cannot be shared."""
import csv
import random
from pathlib import Path


ROOT = Path(__file__).parent / "data"
RNG = random.Random(20261019)
ACCOUNTS = [
    (f"A-{number:03d}", f"customer{number}.example", tier)
    for number, tier in enumerate(("platinum", "gold", "silver", "bronze") * 5, start=1)
]
TEMPLATES = {
    "billing_dispute": ("Invoice appears wrong", "We were double billed for the last shipment. Please arrange a refund."),
    "delivery_delay": ("Where is my delivery?", "The shipment is late and has not arrived. Please provide an update."),
    "damage_claim": ("Damaged shipment", "The package arrived broken and the contents were damaged."),
    "customs": ("Customs clearance question", "Customs has requested the HS code and duty information."),
    "quote_request": ("Request for a quote", "How much to ship our pallets next week? Please send pricing."),
}
UNMATCHED = [
    ("Portal access", "I cannot update the notification preferences in the customer portal."),
    ("Change pickup contact", "Please change the collection contact for tomorrow."),
    ("Packing guidance", "Which label should I put on the outer carton?"),
]


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    with (ROOT / "accounts.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["account_id", "domain", "tier"])
        writer.writeheader()
        writer.writerows({"account_id": account, "domain": domain, "tier": tier} for account, domain, tier in ACCOUNTS)

    categories = list(TEMPLATES)
    with (ROOT / "tickets.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["ticket_id", "subject", "body", "from_email"])
        writer.writeheader()
        for number in range(1, 801):
            known = RNG.random() < 0.78
            account_id, domain, _ = RNG.choice(ACCOUNTS)
            sender_domain = domain if known else f"external{number}.example"
            if RNG.random() < 0.76:
                category = RNG.choice(categories)
                subject, body = TEMPLATES[category]
                if RNG.random() < 0.18:
                    body += " This is urgent; please escalate immediately."
            else:
                subject, body = RNG.choice(UNMATCHED)
            writer.writerow({
                "ticket_id": f"SYN-{number:04d}",
                "subject": subject,
                "body": body,
                "from_email": f"contact{number}@{sender_domain}",
            })


if __name__ == "__main__":
    main()
