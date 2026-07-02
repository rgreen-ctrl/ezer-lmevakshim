"""Import the interlinear workbook into the corpus as DRAFT words.

Usage:
    python3 scripts/import_corpus.py                         # data/noach_interlinear.xlsx -> Noach
    python3 scripts/import_corpus.py --xlsx path.xlsx --track chumash --unit Noach

Validation is all-or-nothing: any missing column or unparseable row is
reported with its exact row number and NOTHING is imported. Re-runs are
idempotent: drafts update in place, certified rows are never touched, and
the summary prints inserted / updated / unchanged / skipped-certified.
This script NEVER sets certified — certification is human work at the desk.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.importer import (ImportValidationError, import_words,
                          parse_interlinear, seed_ladder)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xlsx", default="data/noach_interlinear.xlsx")
    parser.add_argument("--track", default="chumash")
    parser.add_argument("--unit", default="Noach")
    parser.add_argument("--kind", default="parsha")
    args = parser.parse_args()

    try:
        words, empty_gloss = parse_interlinear(args.xlsx)
    except ImportValidationError as e:
        print(e)
        sys.exit(1)

    app = create_app()
    with app.app_context():
        seed_ladder()
        unit, counts = import_words(words, args.track, args.unit, args.kind)
        pesukim = len({w["pasuk_index"] for w in words})
        print(f"{unit.name}: {len(words)} words across {pesukim} pesukim "
              f"({words[0]['ref']} – {words[-1]['ref']}), all drafts.")
        print("  " + " · ".join(f"{k.replace('_', '-')}: {v}"
                                for k, v in counts.items()))
        if empty_gloss:
            print(f"  NOTE: {len(empty_gloss)} words have EMPTY draft glosses "
                  f"(source column blank) and cannot be certified until an "
                  f"editor writes them at the desk:")
            for rownum, ref, word_n in empty_gloss:
                print(f"    sheet row {rownum}: {ref} word #{word_n}")


if __name__ == "__main__":
    main()
