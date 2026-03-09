import json
import re
from pathlib import Path


def ensure_dir(path: Path) -> None:
   path.mkdir(parents=True, exist_ok=True)


def write_jsonl(path: Path, rows) -> None:
   ensure_dir(path.parent)
   with path.open("w", encoding="utf-8") as f:
       for row in rows:
           f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path):
   rows = []
   if not path.exists():
       return rows
   with path.open("r", encoding="utf-8") as f:
       for line in f:
           line = line.strip()
           if not line:
               continue
           rows.append(json.loads(line))
   return rows


def clamp(x, lo, hi):
   return max(lo, min(hi, x))


def clean_text(text: str) -> str:
   text = text or ""
   text = text.replace("\x00", " ")
   text = re.sub(r"\s+", " ", text)
   return text.strip()


def normalize_title(title: str) -> str:
   title = clean_text(title).lower()
   title = re.sub(r"[^a-z0-9 ]+", " ", title)
   title = re.sub(r"\s+", " ", title).strip()
   return title


def unwrap_openreview_value(v):
   # OpenReview often stores values as {"value": ...}
   if isinstance(v, dict) and "value" in v:
       return unwrap_openreview_value(v["value"])
   if isinstance(v, list):
       out = []
       for item in v:
           val = unwrap_openreview_value(item)
           if isinstance(val, str):
               out.append(val)
           elif isinstance(val, list):
               out.extend([str(x) for x in val])
           elif val is not None:
               out.append(str(val))
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
   if not text:
       return ""
   m = _ARXIV_NEW.search(text)
   if m:
       return m.group("id")
   m = _ARXIV_OLD.search(text)
   if m:
       return m.group("id")
   return ""


def safe_filename(text: str) -> str:
   text = normalize_title(text)
   text = text.replace(" ", "_")
   return text[:120] if text else "paper"
