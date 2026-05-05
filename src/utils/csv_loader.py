import csv
import sys
from pathlib import Path

from models.partner import Partner


REQUIRED_COLUMNS = {"name", "email", "industry"}
OPTIONAL_COLUMNS = {"website"}

SAMPLE_PARTNERS = [
    Partner(name="Lena Torres",  email="lena@growthloop.io",   industry="B2B SaaS",    website="growthloop.io"),
    Partner(name="Marcus Webb",  email="marcus@finflux.com",   industry="Fintech",     website="finflux.com"),
    Partner(name="Priya Nair",   email="priya@healthbridge.co",industry="HealthTech",  website="healthbridge.co"),
    Partner(name="Dani Kim",     email="dani@retailstack.io",  industry="Retail Tech", website="retailstack.io"),
    Partner(name="Sam Okafor",   email="sam@eduflow.com",      industry="EdTech",      website="eduflow.com"),
]


class CSVLoader:
    def __init__(self, path: str):
        self.path = Path(path)

    def _validate_headers(self, fieldnames: list[str]):
        headers = {h.lower().strip() for h in fieldnames}
        missing = REQUIRED_COLUMNS - headers
        if missing:
            print(f"[error] CSV is missing required columns: {', '.join(missing)}")
            print(f"        Required: {', '.join(REQUIRED_COLUMNS)}")
            sys.exit(1)

    def load(self) -> list[Partner]:
        if not self.path.exists():
            print(f"[error] File not found: {self.path}")
            sys.exit(1)

        partners = []
        with open(self.path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self._validate_headers(reader.fieldnames or [])
            for row in reader:
                row = {k.lower().strip(): v.strip() for k, v in row.items()}
                partners.append(Partner(
                    name=row["name"],
                    email=row["email"],
                    industry=row["industry"],
                    website=row.get("website", ""),
                ))

        print(f"  Loaded {len(partners)} partners from {self.path.name}")
        return partners


def load_partners(csv_path: str | None) -> list[Partner]:
    if csv_path:
        return CSVLoader(csv_path).load()
    print(f"  No CSV provided — using {len(SAMPLE_PARTNERS)} built-in sample partners.")
    return list(SAMPLE_PARTNERS)
