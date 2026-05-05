import csv
from datetime import datetime
from pathlib import Path

from models.partner import OutreachEmail


EXPORT_FIELDS = [
    "name", "email", "industry", "website",
    "subject", "body", "status",
    "generated_at", "sent_at", "error",
]


class CSVExporter:
    def __init__(self, output_path: str | None = None):
        if output_path:
            self.path = Path(output_path)
        else:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.path = Path(f"outreach_results_{stamp}.csv")

    def export(self, emails: list[OutreachEmail]) -> Path:
        with open(self.path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=EXPORT_FIELDS)
            writer.writeheader()
            for e in emails:
                writer.writerow({
                    "name":         e.partner.name,
                    "email":        e.partner.email,
                    "industry":     e.partner.industry,
                    "website":      e.partner.website,
                    "subject":      e.subject,
                    "body":         e.body,
                    "status":       e.partner.status.value,
                    "generated_at": e.generated_at.isoformat() if e.generated_at else "",
                    "sent_at":      e.sent_at.isoformat() if e.sent_at else "",
                    "error":        e.error or "",
                })
        return self.path
