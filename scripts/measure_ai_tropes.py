# SPDX-License-Identifier: MIT
"""Run `seeds/ai_trope.parquet` over a corpus of markdown files, and report counts.

This is MEASUREMENT APPARATUS, not a gate. RFD 107c's rule in the RFD repository is
that a rule runs against the whole corpus before it becomes a rule, and a rule that
needs an exception does not ship. This script produces the counts that decision needs.

It owns no patterns and no parser. The patterns come from `seeds/ai_trope.parquet`,
written by `scripts/seed_ai_tropes.py`. The prose comes from `runtime/prose_nodes.py`.
A second copy of either would be the thing both files exist to prevent, and would drift.

WHAT IT FOUND, AND WHY THE `--audit` MODE IS NOT OPTIONAL. Two of the fifteen regex
detectors cannot fire against `prose_nodes` output at all. `Bolded Lead Clause` matches
`\\*\\*...\\*\\*` and `Where/What/Why Header` matches `#{1,6}`, and `prose_nodes` returns
the text a reader sees, with the emphasis markers and the hashes already removed. Both
report zero on every corpus, and zero reads exactly like a clean result.

So `--audit` feeds each pattern a string built from its own `example_phrase` and asserts
the pattern matches it after `prose_nodes` has run. A detector that cannot match its own
recorded example is reported as BROKEN rather than counted as clean.
"""
from __future__ import annotations

import argparse
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyarrow.parquet as pq  # noqa: E402

from runtime.prose_nodes import prose_blocks  # noqa: E402

SEEDS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "seeds", "ai_trope.parquet")


def load():
    """(name, detector, pattern, example) per row, patterns compiled where present."""
    t = pq.read_table(SEEDS).to_pylist()
    out = []
    for r in t:
        rx = re.compile(r["pattern"], re.I | re.M) if r["pattern"] else None
        out.append((r["name"], r["detector"], rx, r["example_phrase"]))
    return out


def prose(markdown: str) -> str:
    """One string per document, blocks joined, as `prose_nodes` hands them over."""
    return "\n".join(t for t, _line in prose_blocks(markdown))


def corpus(root: str):
    """Every `<hex>-slug/README.md` under root. The RFD layout, which is the corpus."""
    for d in sorted(os.listdir(root)):
        p = os.path.join(root, d, "README.md")
        if re.match(r"^[0-9a-f]{4}-", d) and os.path.isfile(p):
            with open(p, encoding="utf-8") as fh:
                yield d[:4], fh.read()


def audit(rows):
    """Assert each regex matches its own example AFTER prose extraction.

    A detector that cannot match its recorded example is broken, and its zero on a real
    corpus means nothing. Reporting that apart from a genuine zero is the whole point:
    a silent skip reads exactly like a pass.
    """
    broken, ok = [], []
    for name, det, rx, example in rows:
        if det != "regex" or rx is None:
            continue
        if not example:
            broken.append((name, "no example_phrase recorded, so nothing can be checked"))
            continue
        # The example as it would reach the detector through the gate.
        seen = prose(example)
        if rx.search(seen):
            ok.append(name)
        elif rx.search(example):
            broken.append((name, "matches raw markdown but NOT prose_nodes output"))
        else:
            broken.append((name, "does not match its own example_phrase"))
    return ok, broken


def compare(root):
    """Run BOTH tables over one corpus, through one extractor.

    RFD 107d rests on the contrast rather than on either number alone, so the two
    have to be taken the same way: same documents, same `prose_nodes` extraction, same
    raw-regex treatment. Running one through a classifier and the other through a
    screen would compare the instruments instead of the corpora.

    Neither column is a verdict. `seed_labels.PATTERNS` are the weak labels the STE
    classifier trains from, not the thresholds it ships with, and the AI-trope hits are
    all false positives on inspection. The magnitude is what the RFD uses.
    """
    from scripts.seed_labels import PATTERNS as STE

    ai = [(n, rx) for n, det, rx, _e in load() if det == "regex" and rx]
    docs = {"ai_trope.parquet": set(), "trope.parquet": set()}
    hits = collections.Counter()
    n = 0
    for num, text in corpus(root):
        n += 1
        body = prose(text)
        for name, rx in ai:
            if rx.search(body):
                docs["ai_trope.parquet"].add(num)
            hits["ai_trope.parquet"] += len(rx.findall(body))
        for name, rx in STE.items():
            if rx.search(body):
                docs["trope.parquet"].add(num)
            hits["trope.parquet"] += len(rx.findall(body))
    print(f"both tables over {n} documents, same extractor\n")
    print(f"{'table':<26}{'documents flagged':>19}{'hits':>8}")
    print("-" * 53)
    for k in ("ai_trope.parquet", "trope.parquet"):
        print(f"{k:<26}{f'{len(docs[k])} of {n}':>19}{hits[k]:>8}")
    print("\nNeither column is a verdict; see this function's docstring.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="measure ai_trope.parquet over a corpus")
    ap.add_argument("root", nargs="?", default="../.request_for_discussion")
    ap.add_argument("--inspect", action="store_true", help="print every hit in context")
    ap.add_argument("--audit", action="store_true", help="check each detector can fire")
    ap.add_argument("--compare", action="store_true",
                    help="run the ASD-STE100 table over the same corpus, for contrast")
    a = ap.parse_args()
    rows = load()

    if a.compare:
        return compare(a.root)

    if a.audit:
        ok, broken = audit(rows)
        for name in ok:
            print(f"  ok     {name}")
        for name, why in broken:
            print(f"  BROKEN {name}\n           {why}")
        print(f"\n{len(ok)} detectors can fire, {len(broken)} cannot.")
        return 1 if broken else 0

    docs, hits = collections.Counter(), collections.Counter()
    n = 0
    for num, text in corpus(a.root):
        n += 1
        body = prose(text)
        for name, det, rx, _ex in rows:
            if det != "regex" or rx is None:
                continue
            found = rx.findall(body)
            if found:
                docs[name] += 1
                hits[name] += len(found)
            if a.inspect:
                for m in rx.finditer(body):
                    ctx = body[max(0, m.start() - 40):m.end() + 30].replace("\n", " ")
                    print(f"{num}  {name:<30} ...{ctx.strip()}...")
    if a.inspect:
        return 0

    regex_rows = [r for r in rows if r[1] == "regex"]
    print(f"corpus: {n} documents, {len(regex_rows)} regex detectors from "
          f"{os.path.basename(SEEDS)}\n")
    print(f"{'trope':<32}{'docs':>6}{'share':>8}{'hits':>7}")
    print("-" * 53)
    for name, c in sorted(hits.items(), key=lambda kv: -kv[1]):
        print(f"{name:<32}{docs[name]:>6}{100 * docs[name] / n:>7.0f}%{c:>7}")
    clean = [r[0] for r in regex_rows if not hits[r[0]]]
    print(f"\nzero hits across all {n} ({len(clean)} of {len(regex_rows)}):")
    for c in clean:
        print(f"  {c}")
    by_det = collections.Counter(r[1] for r in rows)
    print(f"\ndetectors by kind: " + ", ".join(f"{v} {k}" for k, v in sorted(by_det.items())))
    # Derived, never written down. The first draft of this line said "Two detectors"
    # while --audit found three, which is the same drift a hardcoded count always has.
    _ok, _broken = audit(rows)
    if _broken:
        print(f"\n{len(_broken)} of these detectors CANNOT FIRE, so their zero above "
              f"means nothing:")
        for name, why in _broken:
            print(f"  {name}: {why}")
    print("Run --audit before trusting any zero.")
    print(f"Exact counts over a fixed, fully enumerated population of {n}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
