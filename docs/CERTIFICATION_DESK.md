# The Certification Desk — Editor Review, Approval & Corpus Load

Repo: rgreen-ctrl/ezer-lmevakshim · Status: approved work order, 2026-07-02 ·
Sessions: D1 → D2 → D3, one at a time, standing discipline applies (named
restore-point branch pushed to origin, one commit per logical piece, CI green
on both backends, no tag pushes, no simultaneous sessions).

## 1. What this is

The learner app already refuses to serve any word that is not certified. This
module builds the other half of that rule: the place where certification
happens. Editors sign in to the regular app, and a Review area appears for
them that no learner ever sees. In it they walk the parsha pasuk by pasuk,
correct any draft gloss that needs correcting, and approve word by word.
Every approval is a certification; every correction is logged with who and
when. The moment a pasuk's last word is certified, that pasuk becomes
servable to learners — the certified frontier moves forward one pasuk at a
time, staying ahead of the boys climbing behind it.

This module also loads the real corpus: the Noach interlinear workbook
(1,862 words, Bereishis 6:9–11:32) imported as draft glosses, ready for the
editors to certify in order.

## 2. Roles and access

- Two kinds of accounts, one app. Learners stay as they are (email-only for
  the pilot). Editors get real accounts in the staff table with a role
  column: editor or admin. Admin can create editor accounts and do everything
  an editor can.
- Editors get passwords. Editors are writers — they change what every learner
  will be taught — so email-only is not acceptable for them even in the
  pilot. Minimum: bcrypt-hashed password login for editor/admin accounts,
  session cookie, logout. (Cloudflare Zero Trust Access may be layered in
  front of /desk at domain time; the in-app password ships now and does not
  wait for the domain.)
- The Review area. Signed-in editors see a Review tab (route prefix /desk).
  Every /desk route and every certification API endpoint checks the role
  server-side. A learner token hitting a desk endpoint gets 403 — and there
  is a test proving it.

## 3. Data model deltas

- words: carries certification status plus certified_by (editor id) and
  certified_at. Status moves draft→certified only through the desk endpoint;
  the importer never sets certified.
- gloss_revisions: word_id, old_gloss, new_gloss, editor_id, created_at.
  Every gloss edit writes a row — the permanent audit trail. Nothing is ever
  edited in place without a revision row.
- word_flags: word_id, raised_by (learner or editor), note, status
  (open/resolved), resolved_by, resolved_at. The reader-flag healing loop.
- Correction semantics (locked): editing a draft word just updates the draft.
  Editing a certified word takes effect immediately, logs a revision, and the
  word stays certified — corrections never yank pesukim away from learners
  mid-parsha. Decertify exists as a deliberate admin-only action for a
  genuinely wrong word, with a required reason, and it pulls the owning pasuk
  off the servable frontier.

## 4. The desk — what the editor sees

- Pick a unit; progress meters everywhere: words certified / total, pesukim
  complete / total.
- Interlinear review view: one pasuk at a time — Hebrew word with its draft
  gloss under it, right-to-left, the same rendering the learner will get.
- Word actions: Approve (certifies), Edit gloss (writes the revision), Flag
  (goes to the flag queue for a second opinion).
- Certify pasuk: one button certifies every remaining word in it.
  Deliberately pasuk-sized, never chapter-sized.
- The frontier: the desk shows the last fully-certified pasuk.
- Flag queue: open flags with word, context pasuk, note, raiser. Resolve =
  edit-and-certify or dismiss-with-note.

## 5. Corpus load

- Source of truth: data/noach_interlinear.xlsx — 1,862 words, Bereishis
  6:9–11:32, one row per word, gloss on the shoresh, literal pshat.
- The importer maps the Interlinear sheet's columns (reference, Hebrew word,
  gloss, shoresh) into words, all status = draft. If any expected column is
  missing or any row fails to parse, the importer reports the exact rows and
  imports nothing — no partial silent loads.
- Idempotent: re-running updates draft rows in place, never touches certified
  rows, and prints inserted / updated / skipped-certified.
- Certification budget (planning): 153 pesukim ≈ 8–10 editor-hours total;
  only the first two aliyos (≈20 pesukim ≈ 10 lessons) must be certified
  before a pilot boy can start.
- Next in line: Lech Lecha arrives through the pipeline as drafts into this
  same desk; then Avos; then the Eilu Metzios reconciliation.

## 6. Work orders

- **D1 — Roles, auth, and schema.** Done when: an editor can sign in and
  reach an empty /desk; a learner token gets 403 on every desk route
  (tested); migrations run clean on SQLite and Postgres; CI green.
- **D2 — The desk itself.** Done when: against the dev sample, an editor can
  edit a gloss (revision row written), certify word-by-word and pasuk-level,
  and the learner API begins serving a pasuk at the exact moment its last
  word is certified — proven by a test; a certification path from any learner
  endpoint is impossible (tested); CI green.
- **D3 — Noach corpus import.** Done when: ~1,862 draft words are in the
  database with correct pasuk boundaries; re-running the import is a no-op on
  certified rows; the desk shows Noach at 0% certified and the learner app
  correctly serves nothing until certification begins; CI green.

## 7. Never-do guardrails (also in CLAUDE.md)

- Never certify a word from anywhere but the desk endpoints.
- Never change a gloss without writing a gloss_revisions row.
- Never let a learner session reach a /desk route or certification endpoint.
- Never bulk-certify above pasuk granularity.
- Never delete revision or flag rows.

## 8. Open decisions (human)

- Who the editor accounts are (names + emails).
- Solo certification vs. second-eye on corrections (pilot default: solo,
  second-eye only on flag resolutions).
