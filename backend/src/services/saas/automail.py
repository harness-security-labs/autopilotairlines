from pydantic import BaseModel


class EmailMessage(BaseModel):
    to: str
    subject: str
    body: str
    from_addr: str = "noreply@autopilotairlines.com"


SENT_EMAILS: list[dict] = []


async def send_email(to: str, subject: str, body: str) -> dict:
    msg = {
        "id": f"msg_{len(SENT_EMAILS) + 1:04d}",
        "to": to,
        "from": "noreply@autopilotairlines.com",
        "subject": subject,
        "body": body,
        "status": "sent",
    }
    SENT_EMAILS.append(msg)
    return msg


async def get_sent_emails(limit: int = 50) -> list[dict]:
    return SENT_EMAILS[-limit:]
