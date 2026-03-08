from pathlib import Path
import json

IN_FILE = Path("data/processed/text_dataset.jsonl")
OUT_FILE = Path("data/processed/train.jsonl")

def main():
    n = 0
    with IN_FILE.open("r", encoding="utf-8") as fin, OUT_FILE.open("w", encoding="utf-8") as fout:
        for line in fin:
            row = json.loads(line)
            text = row.get("text", "")
            label = int(row.get("label", 0))
            if label not in (0, 1):
                continue
            fout.write(json.dumps({"text": text, "label": label}) + "\n")
            n += 1

    print(f"✅ Train dataset ready: {OUT_FILE} ({n} rows)")

if __name__ == "__main__":
    main()