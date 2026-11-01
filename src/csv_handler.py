"""
CSV input/output handler.
"""

import csv
import sys
from pathlib import Path
from src.models import Company


class CSVHandler:
    def __init__(self, path: str, company_col: str = "company", website_col: str = "website"):
        self.path = Path(path)
        self.company_col = company_col
        self.website_col = website_col

    def load(self) -> list[Company]:
        if not self.path.exists():
            print(f"[ERROR] File not found: {self.path}", file=sys.stderr)
            sys.exit(1)

        companies = []
        with open(self.path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []

            # Flexible column matching (case-insensitive)
            col_map = {h.lower().strip(): h for h in headers}
            company_col = col_map.get(self.company_col.lower()) or col_map.get("name") or col_map.get("company_name")
            website_col = col_map.get(self.website_col.lower()) or col_map.get("url") or col_map.get("site")

            if not company_col:
                print(f"[ERROR] Could not find company column. Available columns: {headers}", file=sys.stderr)
                print(f"  Tip: Use --company-col to specify the correct column name.", file=sys.stderr)
                sys.exit(1)

            if not website_col:
                print(f"[ERROR] Could not find website column. Available columns: {headers}", file=sys.stderr)
                print(f"  Tip: Use --website-col to specify the correct column name.", file=sys.stderr)
                sys.exit(1)

            for i, row in enumerate(reader, start=2):
                name = row.get(company_col, "").strip()
                website = row.get(website_col, "").strip()

                if not name and not website:
                    continue  # skip blank rows

                # Normalize website URL
                if website and not website.startswith(("http://", "https://")):
                    website = "https://" + website

                extra = {k: v for k, v in row.items() if k not in (company_col, website_col)}
                companies.append(Company(name=name or website, website=website, extra_fields=extra))

        if not companies:
            print("[ERROR] No companies found in CSV file.", file=sys.stderr)
            sys.exit(1)

        return companies
