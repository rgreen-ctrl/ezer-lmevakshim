# The Parsha Pipeline — Runbook

The exact sequence that built Noach, written down so parsha 3 never
rediscovers what parsha 1 learned. Every step, in order, with the traps.
Nothing here certifies anything, ever. Certification is Rabbi Green's, at the
Desk, word by word.

## Step 0 — Verify the sources exist and are kosher (BEFORE any work)

- **Magil**: RESOLVED (2026-07-17) — `magilslinearscho00magirich` is the
  **complete 5-in-1 Chumash** (HathiTrust 102776770: "5 volumes in 1"; the
  item's own OCR contains all five books — Bamidbar running heads incl.
  Balak). Genesis sits at the HIGH leaf numbers (RTL: Noach = 512–500);
  Shemos→Devarim continue at lower leaves. Map each sefer's leaf range from
  the OCR before capturing. TRAP: archive.org's on-demand `_medium`
  derivatives are flaky — a 1.6KB placeholder does NOT mean the leaf doesn't
  exist; only uncached leaves fail. Download originals, don't probe derivatives.
- **Sefaria licenses are PER VERSION.** Always `GET /api/texts/versions/<index>`
  and check `license` in-body on EVERY fetch. The forbidden CC-BY-NC
  Metsudah/Sifsei Chachomim sit under the same slugs as the PD versions.
- **Forbidden sources, by name, no exceptions**: ArtScroll/Schottenstein,
  Kehati, Steinsaltz, Blackman, Metsudah, Sifsei Chachomim, Klein,
  **Etheridge English** (PD but ruled out), Zondervan Englishman's.
- **R-S Rashi English**: PD for **Bereishis + Shemos only** (1929/1930
  volumes). Vayikra/Bamidbar/Devarim are NOT PD until ~2028–2030 — those
  sefarim get **Rashi Hebrew with no English**, flagged plainly in the Desk,
  never patched with a forbidden translation.
- Onkelos Aramaic: pin `hebrew|Onkelos Genesis`-style versionTitle
  (toratemetfreeware, license "Public Domain"); Jastrow: "London, Luzac, 1903".

## Step 1 — Magil page identification

Hebrew-bound (RTL) IA scan: **higher leaf number = earlier text**. Map
leaf → pesukim range first (read the running heads). Download every page
image to the working dir; they are also the cached Desk scans later
(`scripts/cache_pages.py`, 1700px wide, served from our origin — archive.org
`_medium` is unreadable and filters block hotlinks).

## Step 2 — Vision capture: LINES, Hebrew as anchor

Magil's unit is the **printed line**: one English phrase paired to the Hebrew
words on that line. Capture per pasuk, per page, into
`data/magil_lines/n<leaf>.json`:

```json
"6:9": {"leaf":512,"lines":[["These [are] the generations of Noah.",3], ...],
        "footnotes":{"1":"Or. upright"}}
```

- English **verbatim**: brackets `[..]`, parens `(..)`, footnote markers ¹²³.
- Never transcribe the Hebrew — count it. The Hebrew is morphhb's.
- A pasuk split across a page boundary is captured in both files; the merge
  sums them (mark `"partial"`).
- Bank page-by-page. A crash must never lose a read page.

## Step 3 — The count gate (non-negotiable)

`scripts/verify_lines.py`: every pasuk's line word-counts must sum to the
morphhb token count or the build refuses it. This gate caught a page-boundary
split AND the 8:17 ketiv/qere. **Trap**: morphhb counts ketiv and qere as two
tokens. Ruling on record: only the **qere** is a drillable word — flag any
ketiv for Rabbi Green; do not silently include or delete.

## Step 4 — Span rules (all confirmed rulings)

- Brackets/parens = supplied English; **never map to a Hebrew word**, never
  count in alignment, never offered as a literal.
- Per-word literal from a line ONLY when the line covers **exactly one**
  Hebrew word ("Magil (split)"). A count match does NOT prove alignment —
  "a just man" over נח איש צדיק yields איש="just". **Silence beats a guess.**
- Ellipsis collapse ("Magil (ellipsis collapsed)") only when exactly one word
  remains to receive it; cap 4 English words (grouped spans put sentences on
  every word).
- Footnotes: `Heb./H.` = literal (feeds Layer 2, only when its marker is cited
  once and sits on a one-word line); `Or./As.` = variant (reference only).

## Step 5 — Clean roots (Layer 1)

Strong's via OpenScriptures `HebrewStrong.xml`: use the first `<def>` in
`<meaning>` — **never** `<usage>` (the KJV comma-dumps: "cruel-ty, damage").
Keep an existing gloss when it is already a clean single sense; relex only
junk. Alternates become "Other sense (Strong's)" chips.

## Step 6 — Compose + prefill

- Morphology chips are **visibly raw** ("and + fill") — no inflection engine
  (ruling: measure after ~50 certified pesukim first).
- Hebrew-grounded alternates: root + binyan + person templates, **inflect or
  propose nothing** (curated `INFLECT` table in
  `build_hebrew_alternates.py`).
- **Magil wins on conflict**: prefill L1 where his chip reduces to one content
  word; L2 from split/collapse chips. Certified words: flag, never write.
  All prefill writes GlossRevision rows.

## Step 7 — Name map

Apply the approved transliteration table to **Magil's English only** (lines,
chips, contextual) + Strong's name entries. Never Hebrew/Aramaic/Rashi
Hebrew. **Never R-S English — it is a citation.** Possessives map; divine
names excluded (separate ruling). Report list + counts BEFORE applying.

## Step 8 — Targum & Meforshim

Onkelos per pasuk (Aramaic only — the English is Rabbi Green's to write, with
the Jastrow tap-lookup assisting). Rashi Hebrew with דיבור המתחיל split; R-S
English beside it only where PD (see Step 0). Panel label is
"Targum & Meforshim" — they are not "sources".

## Step 9 — Confidence + seed

Line-covered word = HIGH; Onkelos-recast pesukim + ketiv = MEDIUM; uncovered =
LOW. Confidence ORDERS review; it never approves. Seed order is always
**migrate → deploy → seed** (seeders read the container's data files).
Seeders: idempotent, skip/flag certified, never invent.

## Step 10 — Verify like it matters

CI green on BOTH backends (SQLite + Postgres 16). Then **a human loads the
rendered production page** — DB reads and served-file checks all passed while
the Desk was broken (filter block, cached redirect, lazy-load, .ctx crash).
The Desk never fails silently; every error path prints what happened.

## Trap log (what broke and WHY — append as it happens)

- **Verified-while-broken, three times (2026-07-16).** DB reads, served-file
  checks, and local replicas all passed while the user's Desk was broken: a
  content filter categorized the domain "Religion" mid-day (triggered by the
  Torah content itself going live); a cached redirect survived hard-refresh;
  `loading="lazy"` deferred a below-the-fold image forever. WHY it stuck:
  every check ran on the server side of the user's network. RULE: only a
  human reading the rendered production page verifies a Desk change.
- **archive.org hotlinks:** `/download/` 302s to a different origin — filters
  kill it silently, and `_medium` is unreadable anyway. Cache scans locally.
- **Sefaria per-tap fetches:** cross-refs are signposts ("v. X"), internal
  links are relative (404 on our domain). Sweep + resolve at build time,
  serve from our origin (`jastrow_noach.json`).
- **DOM refactors orphan selectors:** the line-model rewrite removed `.ctx`
  spans; `saveContextual` crashed mid-save, which also suppressed follow-up
  UI (the global-shoresh offer). Guard every querySelector in save paths.
- **Count parity ≠ alignment:** "a just man" over נח איש צדיק is 3-for-3 and
  still wrong (English fronts the adjective). Only a one-word line proves a
  per-word mapping.
- **Composers must be re-run after their inputs change:** Binyan/Morphology
  chips kept "was accomplish, confirm" because they were built before the
  root reseed. A derived artifact is stale the moment its source improves.
- **Grouped spans assign a whole phrase to every covered word** — collapsing
  them puts a sentence under one word. Cap per-word offers (4 English words).
- **Never push before reading the test line.** A transient Postgres-container
  readiness race showed "56 passed, 1 error" AFTER a push had already gone
  out (2026-07-17). Rerun distinguishes transient from real — but the order
  is: read results, then push. Chaining `test && push` in one command invites
  exactly this.
- **Craft/connector outages:** bank every unpostable log entry to a file
  immediately (`scratchpad/craft_pending_deploy_log.md` pattern); a record
  that waits for the connector dies with the session.

## What stays human

Vision capture (Step 2) is careful reading, not OCR — budget ~13 pages/parsha.
The count gate makes it safe; nothing else does. Rulings (ketiv, divine names,
place-name categories, register) are Rabbi Green's. And certification is the
learning: 3 of 1,861 is the number that matters.
