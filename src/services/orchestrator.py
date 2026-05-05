import time

from models.partner import Company, Partner, OutreachEmail, EmailStatus
from services.email_generator import EmailGenerator, EmailGenerationError
from services.email_sender import EmailSender


class OutreachOrchestrator:
    """
    Coordinates the full outreach pipeline:
      1. Generate emails for each partner (via OpenAI)
      2. Preview each email in the terminal
      3. Optionally send via SMTP
    """

    RATE_LIMIT_DELAY = 0.5  # seconds between API calls

    def __init__(
        self,
        company: Company,
        generator: EmailGenerator,
        sender: EmailSender,
        verbose: bool = True,
    ):
        self.company = company
        self.generator = generator
        self.sender = sender
        self.verbose = verbose

    def _log(self, msg: str):
        if self.verbose:
            print(msg)

    def run(self, partners: list[Partner], send: bool = False) -> list[OutreachEmail]:
        total = len(partners)
        results: list[OutreachEmail] = []

        self._log(f"\n{'═' * 66}")
        self._log(f"  Partner Outreach Agent  ·  {self.company.name}")
        self._log(f"  {total} partner{'s' if total != 1 else ''} to process")
        self._log(f"  Send mode: {'LIVE' if send else 'dry-run'}")
        self._log(f"{'═' * 66}\n")

        for i, partner in enumerate(partners, start=1):
            self._log(f"  [{i}/{total}] Generating email for {partner.name} ({partner.industry})… ", )

            try:
                email = self.generator.generate(partner)
                self._log("✓")
                if self.verbose:
                    print(email.preview())
                results.append(email)

            except EmailGenerationError as e:
                self._log(f"✗\n  [error] {e}")
                results.append(OutreachEmail(
                    partner=partner,
                    subject="ERROR",
                    body="",
                    error=str(e),
                ))
                partner.status = EmailStatus.FAILED
                continue

            if send:
                self._log(f"  Sending to {partner.email}… ", )
                try:
                    self.sender.send(email)
                    self._log("✓ sent")
                except Exception as e:
                    self._log(f"✗ {e}")

            if i < total:
                time.sleep(self.RATE_LIMIT_DELAY)

        self._print_summary(results)
        return results

    def _print_summary(self, results: list[OutreachEmail]):
        generated = sum(1 for e in results if e.is_valid)
        sent      = sum(1 for e in results if e.partner.status == EmailStatus.SENT)
        failed    = sum(1 for e in results if not e.is_valid)

        self._log(f"\n{'═' * 66}")
        self._log(f"  Summary")
        self._log(f"  Generated : {generated}")
        self._log(f"  Sent      : {sent}")
        self._log(f"  Failed    : {failed}")
        self._log(f"{'═' * 66}\n")
