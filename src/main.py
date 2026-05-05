import argparse
import sys

from models import Company
from services import EmailGenerator, EmailSender, SMTPConfig, OutreachOrchestrator
from utils import load_partners, CSVExporter


# Company Configuration

MY_COMPANY = Company(
    name="Acme Corp",
    sender_name="Alex Chen",
    sender_role="Partnerships Manager",
    sender_email="alex@acmecorp.com",
    value_proposition=(
        "We help SaaS companies grow revenue through channel partnerships — "
        "our partners see an average 30% lift in qualified pipeline within 90 days."
    ),)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI-powered partner outreach email agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--csv",    help="Path to input CSV (name, email, industry)")
    parser.add_argument("--output", help="Path for results CSV (default: timestamped)")
    parser.add_argument("--send",   action="store_true", help="Send emails via SMTP (default: dry-run)")
    parser.add_argument("--quiet",  action="store_true", help="Suppress email previews")
    return parser.parse_args()


def main():
    args = parse_args()

    # 1. Load partners
    partners = load_partners(args.csv)

    # 2. Set up services
    generator = EmailGenerator(company=MY_COMPANY)

    smtp_config = SMTPConfig.from_env()
    sender = EmailSender(
        company=MY_COMPANY,
        config=smtp_config,
        dry_run=not args.send,
    )

    orchestrator = OutreachOrchestrator(
        company=MY_COMPANY,
        generator=generator,
        sender=sender,
        verbose=not args.quiet,
    )

    # 3. Run the pipeline
    emails = orchestrator.run(partners, send=args.send)

    # 4. Export results
    exporter = CSVExporter(args.output)
    output_path = exporter.export(emails)
    print(f"  Results saved → {output_path}")


if __name__ == "__main__":
    main()
