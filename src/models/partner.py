from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class EmailStatus(Enum):
    PENDING = "pending"
    GENERATED = "generated"
    SENT = "sent"
    FAILED = "failed"


@dataclass
class Company:
    name: str
    sender_name: str
    sender_role: str
    sender_email: str
    value_proposition: str

    def __str__(self) -> str:
        return f"{self.sender_name}, {self.sender_role} at {self.name}"


@dataclass
class Partner:
    name: str
    email: str
    industry: str
    website: str = ""
    status: EmailStatus = EmailStatus.PENDING
    generated_at: datetime | None = None

    def __str__(self) -> str:
        return f"{self.name} ({self.industry}) — {self.email}"


@dataclass
class OutreachEmail:
    partner: Partner
    subject: str
    body: str
    generated_at: datetime = field(default_factory=datetime.now)
    sent_at: datetime | None = None
    error: str | None = None

    @property
    def is_valid(self) -> bool:
        return bool(self.subject and self.body and not self.error)

    def preview(self, width: int = 66) -> str:
        sep = "─" * width
        lines = [
            sep,
            f"  To:       {self.partner.email}",
            f"  Name:     {self.partner.name}  ·  {self.partner.industry}",
            f"  Subject:  {self.subject}",
            sep,
        ]
        words, line = self.body.split(), ""
        for word in words:
            if len(line) + len(word) + 1 > width - 4:
                lines.append(f"  {line}")
                line = word
            else:
                line = f"{line} {word}".strip()
        if line:
            lines.append(f"  {line}")
        lines.append(sep)
        return "\n".join(lines)
