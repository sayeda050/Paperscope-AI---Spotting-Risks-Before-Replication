
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
WS_RE = re.compile(r"\s+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])")
PAGE_NUMBER_RE = re.compile(r"^\s*\d{1,4}\s*$")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any, indent: int = 2) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=indent), encoding="utf-8")


def safe_read_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def clean_text(text: str) -> str:
    text = str(text or "")
    text = text.replace("\ufeff", " ").replace("\x00", " ")
    text = text.replace("\r", "\n")
    text = CONTROL_RE.sub(" ", text)
    text = WS_RE.sub(" ", text)
    return text.strip()


def clean_multiline_text(text: str) -> str:
    text = str(text or "")
    text = text.replace("\ufeff", " ").replace("\x00", " ")
    text = text.replace("\r", "\n")
    text = re.sub(r"([A-Za-z])-\n([A-Za-z])", r"\1\2", text)
    text = re.sub(r"(?<=\w)\n(?=\w)", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = []
    for line in text.splitlines():
        line = clean_text(line)
        if not line:
            continue
        if PAGE_NUMBER_RE.fullmatch(line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def normalize_title(title: str) -> str:
    title = clean_text(title).lower()
    title = re.sub(r"[^a-z0-9 ]+", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def safe_filename(text: str, fallback: str = "file") -> str:
    text = normalize_title(text)
    text = text[:120].strip().replace(" ", "_")
    return text or fallback


def sentence_split(text: str, max_sentences: int | None = None) -> list[str]:
    text = clean_multiline_text(text)
    if not text:
        return []
    parts = [clean_text(x) for x in SENTENCE_SPLIT_RE.split(text) if clean_text(x)]
    if max_sentences is not None:
        return parts[:max_sentences]
    return parts


def normalize_boolish_state(value: Any) -> str:
    value = str(value or "").strip().upper()
    mapping = {
        "YES": "YES",
        "NO": "NO",
        "PARTIAL": "PARTIAL",
        "SUPPORTED": "YES",
        "NOT_FOUND": "NO",
        "MISSING": "NO",
    }
    return mapping.get(value, value)


def risk_label_from_score(score: float) -> str:
    score = float(score)
    if score < 35.0:
        return "LOW"
    if score < 65.0:
        return "MEDIUM"
    return "HIGH"


def repro_label_from_score(score: float, yes_threshold: float = 70.0, no_threshold: float = 30.0) -> str | None:
    score = float(score)
    if score >= yes_threshold:
        return "YES"
    if score <= no_threshold:
        return "NO"
    return None


def unwrap_openreview_value(v):
    if isinstance(v, dict) and "value" in v:
        return unwrap_openreview_value(v["value"])
    if isinstance(v, list):
        out = []
        for item in v:
            val = unwrap_openreview_value(item)
            if isinstance(val, list):
                out.extend(val)
            elif val is not None:
                out.append(val)
        return out
    return v


def get_openreview_content_value(content: dict, key: str, default=""):
    if not isinstance(content, dict):
        return default
    if key not in content:
        return default
    val = unwrap_openreview_value(content.get(key))
    if isinstance(val, list):
        return " ".join([str(x) for x in val if x is not None]).strip()
    if val is None:
        return default
    return str(val).strip()


def flatten_openreview_content(content: dict) -> str:
    if not isinstance(content, dict):
        return ""
    pieces = []
    for _, raw_v in content.items():
        v = unwrap_openreview_value(raw_v)
        if isinstance(v, list):
            for item in v:
                if item is not None:
                    pieces.append(str(item))
        elif v is not None:
            pieces.append(str(v))
    return clean_text(" ".join(pieces))


_ARXIV_NEW = re.compile(r"(?:arxiv\.org/(?:abs|pdf)/)?(?P<id>\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?", re.I)
_ARXIV_OLD = re.compile(r"(?:arxiv\.org/(?:abs|pdf)/)?(?P<id>[a-z\-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?(?:\.pdf)?", re.I)


def extract_arxiv_id(text: str):
    text = str(text or "")
    m = _ARXIV_NEW.search(text)
    if m:
        return m.group("id")
    m = _ARXIV_OLD.search(text)
    if m:
        return m.group("id")
    return ""


def dedupe_keep_order(items: Iterable[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        item = str(item or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def find_pattern_snippets(
    text: str,
    patterns: Iterable[re.Pattern],
    *,
    max_snippets: int = 3,
    max_chars: int = 220,
) -> list[str]:
    text = clean_multiline_text(text)
    if not text:
        return []
    snippets: list[str] = []
    for sentence in sentence_split(text, max_sentences=800):
        low = sentence.lower()
        matched = False
        for pattern in patterns:
            if pattern.search(sentence):
                matched = True
                break
        if matched:
            s = clean_text(sentence)
            if len(s) > max_chars:
                s = s[: max_chars - 3].rstrip() + "..."
            if s not in snippets:
                snippets.append(s)
            if len(snippets) >= max_snippets:
                break
    return snippets


def count_pattern_hits(text: str, patterns: Iterable[re.Pattern], max_hits: int = 100) -> int:
    text = clean_multiline_text(text)
    if not text:
        return 0
    hits = 0
    for sentence in sentence_split(text, max_sentences=1200):
        if any(p.search(sentence) for p in patterns):
            hits += 1
            if hits >= max_hits:
                break
    return hits


def ngrams_present(text: str, patterns: Iterable[re.Pattern]) -> set[str]:
    text = clean_multiline_text(text)
    found: set[str] = set()
    for pattern in patterns:
        for m in pattern.finditer(text):
            grp = clean_text(m.group(0))
            if grp:
                found.add(grp.lower())
    return found


def maybe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def minmax_scale(values: list[float]) -> list[float]:
    vals = [float(v) for v in values]
    if not vals:
        return []
    lo = min(vals)
    hi = max(vals)
    if math.isclose(lo, hi):
        return [0.0 for _ in vals]
    return [(v - lo) / (hi - lo) for v in vals]
