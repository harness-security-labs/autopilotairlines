from langchain_core.tools import tool

from ...services.saas.automail import send_email, SENT_EMAILS


@tool
async def send_email_tool(to: str, subject: str, body: str) -> str:
    """Send an email to a customer or any email address. Used for booking confirmations, notifications, and customer communication."""
    result = await send_email(to, subject, body)
    return f"Email sent successfully to {to}. Message ID: {result['id']}"


@tool
async def get_sent_emails_tool() -> str:
    """Retrieve list of recently sent emails for auditing purposes."""
    if not SENT_EMAILS:
        return "No emails sent yet."
    lines = []
    for msg in SENT_EMAILS[-10:]:
        lines.append(f"[{msg['id']}] To: {msg['to']} - Subject: {msg['subject']}")
    return "\n".join(lines)
