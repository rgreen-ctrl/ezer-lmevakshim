# Zillim of Action — Agent Instructions

Zillim of Action is the learner-facing website for Ezer L'mevakshim: a public
site where a learner registers and climbs a fixed ladder of Torah texts,
tested on every word at random. It is built directly on Rav Miller's system
in "The Mitzvah of Happiness" (Tape #529): two parshiyos of Chumash knowing
every word → six perakim of Pirkei Avos → Eilu Metzios word for word → ready
for Gemara. The unit of mastery is the WORD.

## The ladder (locked — never reorder, never add a bypass)

1. Chumash — Noach + Lech Lecha, every word — gate: verified test, 100% known at random.
2. Pirkei Avos — six perakim, then fluent without nekudos — gate: clean run, no hesitation.
3. Eilu Metzios (Bava Metzia 21a–33b) — word for word, plainest pshat — gate: whole perek perfect.
4. → Gemara (unlocked by rung 3; Eilu Metzios IS the Gemara entry).

Rungs unlock strictly in order. There is NO "straight to Gemara" side door —
a genuinely ready learner passes the placement/verified tests in days. No
simultaneous rungs: extra time goes vertical (more sessions on the SAME rung,
config `sessions_per_day`, default 1, cap 3).

## Core mechanics (locked decisions)

- **Reveal-driven drilling.** Revealing a word's translation IS the flag: the
  word enters the drill pool automatically. No undo on reveals.
- **Claim-then-confirm.** In Drill mode the learner claims "I know it" first,
  then confirms right/wrong after seeing the translation.
- **Hesitation is measured by the clock**, not self-report: response time over
  the threshold (default 4000 ms, pilot-tunable) counts as hesitated.
- **Pool lifecycle:** retry same session → next day → 3 days → 7 days.
  Exit (graduation) = fast-correct in two sessions on DIFFERENT days.
- **Drill mix:** 40% new / 40% weak-pool / 20% maintenance sampling of
  graduated material.
- **Recall only, never multiple choice.** MC is permitted solely as a learning
  aid immediately after a word's first reveal in Learn mode; it never marks a
  word known and never graduates the pool.
- **Verified tests promote; self-marks never do.** The real test is in-person
  and oral: Tester Mode on the tester's device deals 25 random words; the
  tester marks Pass / Hesitated / Fail. Promotion = zero fails AND zero
  hesitations.
- **The 10-Minute Seder.** Time is fixed (10 min/day, hard gentle stop);
  content flexes. A lesson is ~18–30 new words (~2 pesukim), auto-sized,
  always ending at a pasuk boundary.
- **Happiness framing.** Failure marks are private. No leaderboards, no
  inter-learner comparison ever — personal bests and attendance streaks only.

## Never-do guardrails

- NEVER serve, drill, or test a word whose `certified` flag is false. The app
  reads only certified words; certification is done by human editors in the
  editor app, never here.
- NEVER touch certification status from this codebase.
- NEVER relax a gate: promotion thresholds (zero fails, zero hesitations),
  the two-different-days graduation rule, and the rung order are load-bearing.
- NEVER let self-marks promote a rung or graduate via any path other than the
  fast-correct/two-days rule.
- NEVER add leaderboards or any cross-learner comparison.
- NEVER scrape or embed copyrighted translations (ArtScroll, Kehati,
  Steinsaltz, Blackman). Corpus sources are public domain only (Strong's/BDB,
  Jastrow 1903, Magil's linear) plus the project's own certified glosses.
- NEVER push tags.
- Collect the minimum data on minors: name, cell, email, and learning marks —
  nothing else.

## Architecture

- Flask + SQLAlchemy. SQLite for development/tests; PostgreSQL (Railway) in
  production via `DATABASE_URL`.
- The interlinear store (Ezer L'mevakshim editor app) is the master corpus
  source; this app holds a read-only projection of words, imported by
  `scripts/import_corpus.py`. This app writes ONLY learner-progress data
  (learners, sessions, attempts, word_state, promotions).
- Tables: learners · tracks · units · words · sessions · attempts ·
  word_state · promotions. `attempts` is the permanent per-answer history —
  the core value of the backend. Marks are computed server-side from
  `revealed`, `correct`, and `response_ms`; never trust a client-sent mark
  except from an authenticated tester in a verified test.

## Working discipline

- One session per work order (letter), one commit per logical piece.
- CI must be green before a letter is considered done; each work order's
  "Done when" is the acceptance criterion.
- Run `pytest` before every commit.
- Develop on the designated feature branch; never force-push shared history.
