from __future__ import annotations

import re

from .models import ErrorLog


CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _sanitize_log_text(value) -> str:
    text = str(value or "")
    text = text.replace("\x00", " ")
    text = CONTROL_RE.sub(" ", text)
    return text.strip()


def log_error(*, module_name: str, message: str, user=None, paper=None) -> ErrorLog:
    return ErrorLog.objects.create(
        user=user if getattr(user, "pk", None) else None,
        paper=paper if getattr(paper, "pk", None) else None,
        module_name=_sanitize_log_text(module_name)[:255],
        message=_sanitize_log_text(message),
    )