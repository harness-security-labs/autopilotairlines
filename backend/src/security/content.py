import re


_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CARD = re.compile(r"\b(?:\d[ -]*?){13,19}\b")


def sanitize_chat_content(content: str, mode: str) -> str:
    if mode == "none":
        return content

    limit = 20_000 if mode == "basic" else 8_000
    sanitized = _CONTROL_CHARS.sub("", content).strip()
    if len(sanitized) > limit:
        raise ValueError(f"Message exceeds the {limit}-character limit")
    return sanitized


def redact_pii(content: str) -> str:
    content = _SSN.sub("[REDACTED_SSN]", content)
    return _CARD.sub("[REDACTED_CARD]", content)
