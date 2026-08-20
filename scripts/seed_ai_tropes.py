# SPDX-License-Identifier: MIT
"""Write seeds/ai_trope.parquet: the AI-writing tropes, for prose that argues rather
than instructs.

ASD-STE100 is a specification for technical documentation. It assumes the reader wants
a procedure and wants it unambiguous. An essay that works out what is true has a
different job, and STE gates the wrong things there: it objects to a semicolon in an
argument and says nothing about a paragraph that announces its own structure before
saying anything.

So this is a second seed table beside `trope.parquet`, not a replacement for it.

    trope.parquet      ASD-STE100        READMEs, procedures, reference, rules
    ai_trope.parquet   AI-writing tells  essays, design notes, logbook entries

Source: tropes.fyi, a directory of recurring patterns in machine-written prose,
by Ossama Ismail. That directory lists 49 tropes in six categories. The rows below
are the subset whose definitions are unambiguous enough to seed from, so the table
is partial by construction and says so in `coverage`. Adding a row needs the trope
named and an example, not a guess at what the category probably contains.

`detector` records how a row can be found:

    regex       deterministic, runs today
    classifier  needs the trained model; the pattern column is a weak proxy
    manual      no automatic detector, and pretending otherwise would be worse

A regex here is a screen, not a verdict. `Compulsive Counting` fires on the phrase
"three things", which is sometimes just three things.

trope_id is a UUIDv5 over the name with a fixed namespace, so re-running is idempotent.
"""
import os
import uuid

import pyarrow as pa
import pyarrow.parquet as pq

NAMESPACE = uuid.UUID("6f1b1c84-3a45-4b1e-9c7e-1d2a4f6b8c30")  # fixed; do not change
OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seeds", "ai_trope.parquet")

# (name, category, detector, pattern, description, example_phrase)
TROPES = [
    # ---- sentence structure ----
    ("Negative Parallelism", "sentence-structure", "regex",
     r"\b(?:is|are|was|were|it'?s)\s+not\s+[^.;]{1,60}[,—-]\s*(?:it'?s|they'?re|but|rather)\b",
     "States what a thing is not, then what it is. Cut the first half and say the second.",
     "It is not a pipeline, it is a star."),
    ("Manufactured Emphasis Fragment", "sentence-structure", "regex",
     r"(?:^|\.\s)(?:That is (?:the|what|why|how)\b|Two boxes\b|Full stop\b)",
     "A sentence fragment placed after a claim to make it sound weighty.",
     "Two boxes. That is the whole gap."),
    ("Not X. Not Y. Just Z", "sentence-structure", "regex",
     r"\bNot\s+[^.]{1,40}\.\s*Not\s+[^.]{1,40}\.\s*(?:Just|Only)\b",
     "Escalating denial before an ordinary statement.",
     "Not a rewrite. Not a patch. Just a rename."),

    # ---- word choice ----
    ("Pompous Verb", "word-choice", "regex",
     r"\b(?:serves as|acts as|functions as|represents|constitutes|embodies|underscores|"
     r"highlights the fact|speaks to)\b",
     "A long verb where 'is' or 'shows' would do.",
     "The renderer serves as the bridge."),
    ("Invented Concept Label", "word-choice", "classifier",
     r"\bthe\s+\w+[- ]\w+\s+(?:problem|paradox|trap|tension|trade|failure)\b",
     "Naming an idea as though the name were established, when it was coined in the "
     "same sentence. The label then gets reused as if it explained something.",
     "That is the exposure-versus-independence trade."),
    ("Overused Adverb", "word-choice", "regex",
     r"\b(?:quietly|silently|carefully|precisely|genuinely|meaningfully|fundamentally|"
     r"crucially|notably|importantly)\b",
     "An adverb carrying emphasis the sentence has not earned.",
     "It quietly poisons the corpus."),

    # ---- composition ----
    ("Preamble Before Answer", "composition", "regex",
     r"(?:^|\n)\s*(?:Let me|I will|I'?ll|First,? let'?s|Before (?:I|we))\b",
     "Announcing the answer before giving it. Give it.",
     "Let me check that before answering."),
    ("Reasoning Leak", "composition", "regex",
     r"\b(?:which is why I|that is why I|I should (?:note|mention|flag)|"
     r"worth (?:noting|stating|mentioning|having|keeping))\b",
     "Narrating the writing process inside the writing.",
     "Worth noting that this is a judgement call."),
    ("Premise Stacking", "composition", "classifier",
     r"\b(?:given that|since we|because we|now that)\b[^.]{0,80}\b(?:and|then)\b",
     "Several unestablished premises assembled before a conclusion that depends on all "
     "of them.",
     "Given that A, and since B, then C follows."),
    ("Circular Fractal", "composition", "manual", "",
     "Every section restates the section above it, so the document says one thing many "
     "times at different scales.",
     ""),

    # ---- tone ----
    ("Compulsive Counting", "tone", "regex",
     r"\b(?:Two|Three|Four|Five|Six)\s+(?:things|reasons|caveats|ways|points|problems|"
     r"findings|corrections|observations)\b",
     "Announcing how many items follow, which commits the writer to padding to reach "
     "the number.",
     "Three things follow from this."),
    ("Stakes Inflation", "tone", "regex",
     r"\b(?:the whole (?:point|thing|problem)|precisely (?:the|what|why)|exactly the "
     r"(?:failure|problem|thing)|this is why .{0,30} exists)\b",
     "Ordinary observations described as decisive.",
     "That is exactly the failure this exists to prevent."),
    ("Vague Attribution", "tone", "regex",
     r"\b(?:experts (?:say|agree)|it is (?:widely|generally) (?:known|accepted)|"
     r"studies show|research suggests)\b",
     "An unnamed authority standing in for a citation.",
     "Studies show this approach works better."),
    ("False Vulnerability", "tone", "regex",
     r"\b(?:I(?:'| a)m not going to pretend|to be (?:honest|fair)|I could be wrong here|"
     r"full disclosure)\b",
     "Performed candour that concedes nothing.",
     "To be honest, this is the hard part."),

    # ---- formatting ----
    ("Em-Dash Addiction", "formatting", "regex", r"—",
     "Em-dashes chaining clauses that should be separate sentences.",
     "It works — mostly — but not always."),
    ("Unicode Decoration", "formatting", "regex", r"[→⇒✓✗•]",
     "Arrows, ticks and bullets used as ornament inside prose.",
     "input → output ✓"),
    ("Bolded Lead Clause", "formatting", "regex",
     r"(?:^|\n)\s*(?:<p[^>]*>\s*)?\*\*[^*]{10,90}\*\*",
     "Every paragraph opening in bold, which flattens emphasis into noise.",
     "**The point is this.** Then the paragraph."),
    ("Where/What/Why Header", "formatting", "regex",
     r"(?:^|\n)#{1,6}\s+(?:Where|What|Why|How)\s+(?:it|this|we|the)\b",
     "Headers templated from question words rather than naming the content.",
     "## Why it matters"),

    # ---- paragraph structure ----
    ("Enumeration As Prose", "paragraph-structure", "classifier",
     r"\b(?:First,|Second,|Third,)\b",
     "A list written as sentences, keeping the rigidity of a list and losing the "
     "scannability.",
     "First, we render. Second, we restyle. Third, we verify."),
    ("Symmetric Paragraph Length", "paragraph-structure", "manual", "",
     "Every paragraph the same size, which reads as generated rather than written.",
     ""),
]

SCHEMA = pa.schema([
    ("trope_id", pa.string()),
    ("name", pa.string()),
    ("category", pa.string()),
    ("detector", pa.string()),
    ("pattern", pa.string()),
    ("description", pa.string()),
    ("example_phrase", pa.string()),
    ("coverage", pa.string()),
])


def main() -> None:
    rows = []
    for name, category, detector, pattern, description, example in TROPES:
        rows.append({
            "trope_id": str(uuid.uuid5(NAMESPACE, name)),
            "name": name,
            "category": category,
            "detector": detector,
            "pattern": pattern,
            "description": description,
            "example_phrase": example,
            # Recorded per row rather than in a README, so a reader querying the table
            # sees the limitation without being told to go and look for it.
            "coverage": "partial: seeded from the tropes.fyi subset with unambiguous "
                        "definitions; that directory lists 49",
        })
    table = pa.Table.from_pylist(rows, schema=SCHEMA)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    pq.write_table(table, OUT, compression="zstd")
    by_det = {}
    for r in rows:
        by_det[r["detector"]] = by_det.get(r["detector"], 0) + 1
    print(f"wrote {OUT}: {len(rows)} tropes")
    for k, v in sorted(by_det.items()):
        print(f"  {v:3d}  {k}")


if __name__ == "__main__":
    main()
