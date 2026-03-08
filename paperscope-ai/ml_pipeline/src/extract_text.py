from pathlib import Path
import json
from src.utils import clean_text, ensure_dir

IN_FILE = Path("data/processed/linked.jsonl")
OUT_FILE = Path("data/processed/text_dataset.jsonl")

def main():
    ensure_dir(OUT_FILE.parent)

    n = 0
    with IN_FILE.open("r", encoding="utf-8") as fin, OUT_FILE.open("w", encoding="utf-8") as fout:
        for line in fin:
            row = json.loads(line)
            title = clean_text(row.get("title", ""))
            abstract = clean_text(row.get("abstract", ""))
            label = int(row.get("label", 0))

            text = f"{title}. {abstract}".strip()
            fout.write(json.dumps({"text": text, "label": label}) + "\n")
            n += 1

    print(f"✅ Text dataset: {OUT_FILE} ({n} rows)")

if __name__ == "__main__":
    main()