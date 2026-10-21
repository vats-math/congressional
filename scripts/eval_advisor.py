"""Measure how well the barrier advisor (app/advisor.py) labels real-sounding messages.

    python scripts/eval_advisor.py                  # AI if GROQ_API_KEY is set, else keyword fallback
    python scripts/eval_advisor.py --mode keywords  # force the keyword fallback
    python scripts/eval_advisor.py --show           # also print every message it got wrong

Reads data/eval/barrier_messages.csv (expected labels written by a person, separated by "|").
Reports: exact-match accuracy (all labels right, no extras), micro precision/recall/F1 over labels,
per-label recall, and accuracy on "years since played". Put the numbers from a full AI run in the
submission, and say which mode produced them.
"""
from __future__ import annotations

import argparse
import logging
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import advisor  # noqa: E402

DATA = ROOT / "data" / "eval" / "barrier_messages.csv"


def load(path: Path = DATA) -> list[dict]:
    rows = []
    with path.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            labels = {t.strip() for t in r["expected_barriers"].split("|") if t.strip()}
            unknown = labels - set(advisor.BARRIERS)
            if unknown:
                raise ValueError(f"row {r['id']}: unknown labels {sorted(unknown)}")
            years = int(r["expected_years"]) if r["expected_years"].strip() else None
            rows.append({"id": r["id"], "message": r["message"], "labels": labels, "years": years})
    return rows


def detect(message: str, mode: str) -> tuple[set[str], int | None, str]:
    if mode == "keywords":
        det = advisor.keyword_detect(message)
        return {b.tag for b in det.barriers}, det.years_since_played, "keywords"
    out = advisor.detect_barriers(message)
    return {b["tag"] for b in out["barriers"]}, out["years_since_played"], out["source"]


def evaluate(rows: list[dict], mode: str) -> dict:
    tp = fp = fn = exact = years_ok = 0
    per_label_hit, per_label_total = Counter(), Counter()
    sources, misses = Counter(), []
    for r in rows:
        got, years, source = detect(r["message"], mode)
        sources[source] += 1
        want = r["labels"]
        tp += len(got & want)
        fp += len(got - want)
        fn += len(want - got)
        for label in want:
            per_label_total[label] += 1
            per_label_hit[label] += label in got
        exact += got == want
        years_ok += years == r["years"]
        if got != want or years != r["years"]:
            misses.append((r, got, years))
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "n": len(rows), "sources": dict(sources),
        "exact_accuracy": exact / len(rows), "precision": precision, "recall": recall, "f1": f1,
        "years_accuracy": years_ok / len(rows),
        "per_label_recall": {k: per_label_hit[k] / per_label_total[k] for k in sorted(per_label_total)},
        "misses": misses,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mode", choices=["auto", "keywords"], default="auto")
    ap.add_argument("--show", action="store_true", help="print every wrong answer")
    args = ap.parse_args(argv)
    logging.getLogger("advisor").setLevel(logging.ERROR)  # one "falling back" line per message is noise here

    res = evaluate(load(), args.mode)
    print(f"Messages: {res['n']}   answered by: {res['sources']}")
    print(f"Exact-match accuracy: {res['exact_accuracy']:.0%}  (every label right, no extras)")
    print(f"Label precision: {res['precision']:.0%}   recall: {res['recall']:.0%}   F1: {res['f1']:.2f}")
    print(f"Years-since-played accuracy: {res['years_accuracy']:.0%}")
    print("Recall by label: " + ", ".join(f"{k} {v:.0%}" for k, v in res["per_label_recall"].items()))
    if args.show:
        for r, got, years in res["misses"]:
            print(f"  #{r['id']}: expected {sorted(r['labels'])} / {r['years']}, got {sorted(got)} / {years}  - {r['message']}")
    if "keywords" in res["sources"] and args.mode == "auto":
        print("Note: some or all answers came from the keyword fallback (no GROQ_API_KEY or the API failed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
