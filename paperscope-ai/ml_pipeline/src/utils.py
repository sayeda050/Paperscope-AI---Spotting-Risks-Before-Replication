import re
import json
from pathlib import Path
from typing import Iterable, List

import nltk
from nltk.corpus import stopwords

STOPWORDS = set(stopwords.words("english"))

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def save_json(path: Path, data) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def clean_text(text: str) -> str:
    text = text or ""
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text

def simple_tokenize(text: str) -> List[str]:
    text = clean_text(text).lower()
    # Keep words/numbers, drop punctuation
    tokens = re.findall(r"[a-z0-9]+", text)
    tokens = [t for t in tokens if t not in STOPWORDS and len(t) > 2]
    return tokens

def join_tokens(tokens: Iterable[str]) -> str:
    return " ".join(tokens)