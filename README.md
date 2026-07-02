# Zillim of Action

The learner website for **Ezer L'mevakshim** — climb a fixed ladder of Torah
texts, tested on every word at random, ten minutes a day.

Built on Rav Avigdor Miller's system for getting back into learning
("The Mitzvah of Happiness," Tape #529): two parshiyos of Chumash knowing
every word → six perakim of Pirkei Avos → Eilu Metzios word for word →
ready for Gemara. *"Nobody has to be a failure in learning."*

## How it works

- **Learn mode** — the parsha in order, tap to reveal a word's translation.
  Revealing a word automatically enters it into your drill pool.
- **Drill mode** — weak words dealt at random; claim "I know it," then
  confirm. Hesitation is measured by the clock. A word graduates only after
  fast-correct answers in two sessions on different days.
- **Verified test (Tester Mode)** — a human tester deals 25 random words on
  their own device and marks Pass / Hesitated / Fail. A rung is promoted only
  with zero fails and zero hesitations. Self-marks never promote.
- **The 10-Minute Seder** — sessions are time-fixed; content flexes. Lessons
  auto-size to ~2 pesukim and always end at a pasuk boundary.

## Stack

Flask + SQLAlchemy backend (SQLite in development, PostgreSQL in production
via `DATABASE_URL`), static HTML/JS front-end, corpus imported read-only from
the Ezer L'mevakshim interlinear store.

## Development

```bash
pip install -r requirements.txt
pytest                      # run the test suite
python3 scripts/import_corpus.py            # import data/noach_interlinear.xlsx as drafts
python3 scripts/create_staff.py --name "..." --email ... --role admin
flask --app app run         # learner app at /, Certification Desk at /desk.html
```

Words import as **drafts** and are served to learners only after a human
editor certifies them at the Certification Desk — see
`docs/CERTIFICATION_DESK.md`.

See `CLAUDE.md` for the program rules, locked design decisions, and the
never-do guardrails.
