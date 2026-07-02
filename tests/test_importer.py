"""D3 importer tests: all-or-nothing validation, drafts only, idempotent
re-runs that never touch certified rows, and the empty-gloss certification
guard."""

import openpyxl
import pytest

from app import db
from app.auth import create_staff
from app.importer import (ImportValidationError, import_words,
                          parse_interlinear, seed_ladder)
from app.models import Word
from app.services import certify

HEADER = ["Reference", "Ch", "V", "Word #", "Hebrew (WLC)",
          "Hebrew (consonantal)", "Prefix(es)", "Lemma (Strong's #)",
          "Dictionary form", "Translit.", "Shoresh",
          "Literal English — DRAFT (shared gloss)", "Morphology"]

ROWS = [
    ["Bereishis 6:9", 6, 9, 1, "אֵלֶּה", "אלה", None, "428", "אֵלֶּה", "el", "אלה", "these", "H"],
    ["Bereishis 6:9", 6, 9, 2, "תּוֹלְדֹת", "תולדת", None, "8435", "x", "t", "ילד", "generations of", "H"],
    ["Bereishis 6:9", 6, 9, 3, "נֹחַ", "נח", None, "5146", "x", "n", "נח", "Noach", "H"],
    ["Bereishis 6:10", 6, 10, 1, "וַיּוֹלֶד", "ויולד", "and", "3205", "x", "v", "ילד", "and he fathered", "H"],
    ["Bereishis 6:10", 6, 10, 2, "לְךָ", "לך", "to", None, None, "l", None, None, "HR/Sp2ms"],
    ["Bereishis 7:1", 7, 1, 1, "וַיֹּאמֶר", "ויאמר", "and", "559", "x", "v", "אמר", "and He said", "H"],
]


def make_xlsx(path, rows=None, header=None):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Interlinear"
    ws.append(header or HEADER)
    for r in (rows if rows is not None else ROWS):
        ws.append(r)
    wb.save(path)
    return str(path)


@pytest.fixture()
def xlsx(tmp_path):
    return make_xlsx(tmp_path / "corpus.xlsx")


def test_parse_maps_columns_and_structure(xlsx):
    words, empty_gloss = parse_interlinear(xlsx)
    assert len(words) == 6
    assert words[0] == {"ref": "Bereishis 6:9", "pasuk_index": 1, "position": 1,
                        "hebrew": "אֵלֶּה", "translation": "these",
                        "shoresh": "אלה", "aliyah": 1}
    assert [w["pasuk_index"] for w in words] == [1, 1, 1, 2, 2, 3]
    assert words[5]["aliyah"] == 2  # 7:1 opens the second aliyah
    assert empty_gloss == [(6, "Bereishis 6:10", 2)]


def test_missing_column_imports_nothing(app, tmp_path):
    path = make_xlsx(tmp_path / "bad.xlsx",
                     header=[h for h in HEADER if h != "Shoresh"],
                     rows=[r[:10] + r[11:] for r in ROWS])
    with pytest.raises(ImportValidationError) as e:
        parse_interlinear(path)
    assert "Shoresh" in str(e.value)


def test_bad_row_reports_exact_row_and_imports_nothing(app, tmp_path):
    rows = [list(r) for r in ROWS]
    rows[2][4] = None       # empty Hebrew on sheet row 4
    rows[4][1] = "six"      # non-numeric Ch on sheet row 6
    path = make_xlsx(tmp_path / "bad.xlsx", rows=rows)
    with pytest.raises(ImportValidationError) as e:
        parse_interlinear(path)
    msg = str(e.value)
    assert "row 4" in msg and "row 6" in msg
    assert Word.query.count() == 0


def test_import_is_draft_only_and_idempotent(app, xlsx):
    seed_ladder()
    words, _ = parse_interlinear(xlsx)
    unit, counts = import_words(words)
    assert counts == {"inserted": 6, "updated": 0, "unchanged": 0,
                      "skipped_certified": 0}
    assert Word.query.filter_by(certified=True).count() == 0

    unit, counts = import_words(words)  # re-run: pure no-op
    assert counts == {"inserted": 0, "updated": 0, "unchanged": 6,
                      "skipped_certified": 0}


def test_rerun_updates_drafts_never_certified(app, xlsx, tmp_path):
    seed_ladder()
    words, _ = parse_interlinear(xlsx)
    unit, _ = import_words(words)

    editor = create_staff("E", "e@example.org", "long-enough", "editor")
    w1 = Word.query.filter_by(unit_id=unit.id, position=1).one()
    certify.approve_word(w1, editor)
    db.session.commit()

    rows = [list(r) for r in ROWS]
    rows[0][11] = "THESE CHANGED"       # certified row: must be skipped
    rows[1][11] = "generations of (r2)"  # draft row: must update
    words2, _ = parse_interlinear(make_xlsx(tmp_path / "v2.xlsx", rows=rows))
    unit, counts = import_words(words2)
    assert counts["skipped_certified"] == 1
    assert counts["updated"] == 1
    assert Word.query.filter_by(position=1).one().translation == "these"
    assert Word.query.filter_by(position=2).one().translation == "generations of (r2)"


def test_empty_gloss_cannot_certify(app, xlsx):
    seed_ladder()
    words, empty = parse_interlinear(xlsx)
    unit, _ = import_words(words)
    editor = create_staff("E", "e@example.org", "long-enough", "editor")
    blank = Word.query.filter_by(unit_id=unit.id, position=5).one()
    assert blank.translation == ""

    with pytest.raises(ValueError):
        certify.approve_word(blank, editor)
    with pytest.raises(ValueError):        # bulk path refuses the whole pasuk
        certify.certify_pasuk(unit.id, blank.pasuk_index, editor)
    assert Word.query.filter_by(pasuk_index=blank.pasuk_index,
                                certified=True).count() == 0

    # Editor writes the gloss at the desk; now the pasuk certifies.
    certify.edit_gloss(blank, editor, "to you")
    assert certify.certify_pasuk(unit.id, blank.pasuk_index, editor) == 2


def test_real_workbook_imports_1862_words(app):
    """The committed master workbook parses clean: 1,862 words, 153 pesukim,
    22 empty glosses, aliyah structure complete."""
    words, empty_gloss = parse_interlinear("data/noach_interlinear.xlsx")
    assert len(words) == 1862
    assert len({w["pasuk_index"] for w in words}) == 153
    assert words[0]["ref"] == "Bereishis 6:9"
    assert words[-1]["ref"] == "Bereishis 11:32"
    assert len(empty_gloss) == 22
    assert all(w["aliyah"] in range(1, 8) for w in words)

    seed_ladder()
    unit, counts = import_words(words)
    assert counts["inserted"] == 1862
    assert Word.query.filter_by(unit_id=unit.id, certified=True).count() == 0
