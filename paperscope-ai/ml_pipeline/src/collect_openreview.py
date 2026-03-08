"""
Creates a starter dataset in data/raw/openreview_raw.jsonl

For now, we generate a small labeled dataset from a few example abstracts.
Later you can replace this with true OpenReview API collection.
"""

from pathlib import Path
import json
from src.utils import ensure_dir

RAW_DIR = Path("data/raw")
OUT_FILE = RAW_DIR / "openreview_raw.jsonl"

SAMPLES = [
    # label 1 = "relevant / good fit" (example)
    {"title": "Efficient Transformers for Long-Context Retrieval", "abstract": "We propose a transformer architecture optimized for long context and retrieval tasks...", "label": 1},
    {"title": "Neural Ranking Models for Scholarly Search", "abstract": "A learning-to-rank approach for academic paper retrieval and recommendation...", "label": 1},
    {"title": "Open-domain QA with Dense Passage Retrieval", "abstract": "We investigate dense retrieval methods for open-domain question answering...", "label": 1},

    # label 0 = "not relevant" (example)
    {"title": "A Survey of Graph Coloring Algorithms", "abstract": "This paper surveys classical graph coloring algorithms and complexity bounds...", "label": 0},
    {"title": "Quantum Circuits for Factoring", "abstract": "We present quantum circuit optimizations for integer factoring...", "label": 0},
    {"title": "Improving GAN Stability with Spectral Normalization", "abstract": "We study GAN training stability via spectral normalization and regularization...", "label": 0},
]

def main():
    ensure_dir(RAW_DIR)
    with OUT_FILE.open("w", encoding="utf-8") as f:
        for row in SAMPLES:
            f.write(json.dumps(row) + "\n")
    print(f"✅ Wrote demo dataset: {OUT_FILE} ({len(SAMPLES)} rows)")

if __name__ == "__main__":
    main()