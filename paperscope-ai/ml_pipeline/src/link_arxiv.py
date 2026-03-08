"""
Placeholder: in a real pipeline, you'd link OpenReview papers to arXiv IDs.

For now, we simply copy the raw dataset forward.
"""

from pathlib import Path
import shutil

RAW = Path("data/raw/openreview_raw.jsonl")
OUT = Path("data/processed/linked.jsonl")

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(RAW, OUT)
    print(f"✅ Linked dataset created: {OUT}")

if __name__ == "__main__":
    main()