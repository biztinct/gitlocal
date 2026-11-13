# VIFIX — Payobook reads as natural Vietnamese everywhere (program)

Owner request 2026-10-21 ("All of it" on the LEARNREV leftovers): clean up the English and poor machine Vietnamese on
the screens outside Learn, and check the practice copies (replicas) against the real screens. The work is phased:
Fable designs, Opus builds, reviews and tests each phase (owner's standing workflow).

## Standing rules (verbatim into every handover)
- **White label:** never the word "Odoo" in any user-visible string, including every Vietnamese msgstr. Technical
  identifiers, code comments and docs keep the real name.
- **Design bar:** "Extreme WOW, intuitive, out-of-this-world experience, best in class." For Vietnamese this means it
  reads as if a Vietnamese payroll professional wrote it: the screen's own terms, one term per concept, correct
  diacritics, no mixed-language sentences, no word-for-word machine output.
- **Plain screen words** in every user-facing sentence, in both languages.
- **The repo is public:** never commit a credential; scan each diff before committing.
- **Deploys** follow CLAUDE.md (one addons directory, per-module rsync, every active DB: payobook, payobook_template,
  p0clone, rize; never abm), `/opt/deploy-notes.md` START/DONE lines, flock `/tmp/payobook-studio-deploy.lock`,
  peer-session notices, job snapshot before/after, one warm-up curl per site after the restart (LEARNREV LR79).
  Builders do not deploy; Fable does.
- **Clone tests:** dump-based clone of payobook, AI connection OFF, scheduled jobs OFF, server jobs via
  `sudo systemd-run --unit=<unique>`, unique file names, remote scripts in files, drop the clone (`dropdb --force` +
  filestore) at the end. Clones are reachable from the internet: never leave a clone login active.
- **PayAI** must never reach Settings › Access and delegations.

## Translation facts (verified, do not re-derive)
- Memory `po-translation-loading-rules`: a PO entry needs `#. module:`, `#. odoo-python`/`#. odoo-javascript` and a
  `#: code:addons/<m>/<path>:0` occurrence, or it crashes the upgrade or silently stays English. The `.pot` is merged
  into the `.po`. Run the PO parse gate before any deploy wave.
- **Code terms** (`code:` occurrences, from `_t()`/`_()`/QWeb text) are read from the .po at service start; a
  restart is enough. **Model terms** (field labels, help, selection names, menu and action names, view arch) are
  STORED per database: a plain `-u` fills missing Vietnamese but never replaces existing stored values (LEARNREV
  LR20). Replacing them needs an overwrite load guarded by `docs/handovers/learnrev/tools/vi_overwrite_guard.py` /
  `vi_overwrite_load.py` (LR29), or a targeted SQL update where only the old value is replaced (P5A_DEPLOY.md).
- A JS literal that is not wrapped in `_t()` is never extracted, so it is English in every language. Example fixed:
  the Connections tab names (`pb_formula_studio/static/src/xml/connection_desk.xml`, LEARNREV P5a commit `cf2a2445c`).
- `pb_learn` content is generated (`docs/tutorial_poc/author/tools/gen_learn_data.py`). Running it merges into
  `pb_learn/i18n/vi_VN.po`: always diff that file after a run. Learn is OUT of scope here; it was reviewed in
  LEARNREV P5b.
- The terminology the Learn pass used: `pb_learn/i18n/vi_VN.po`, `pb_learn/static/src/engine/glossary.js`.
- Repo scan 2026-10-21: 124 of our modules have `vi_VN.po`, 27,426 entries, 0 empty msgstr, 271 msgstr identical to
  the English. 14 custom modules have no `vi_VN.po`. So the gaps are (a) text never extracted and (b) poor or
  inconsistent translations, not missing entries.
- Known bad examples (from LEARNREV P5b): about 80 untranslated labels on the Lifecycle boards; "Thiếu cú đấm" for a
  missing punch-out (punch = a blow); "Hết tiền" ("out of money") for money out; earlier "Trần nhà" for a contribution
  ceiling and "Tìm kiếm bề mặt" for search surfaces (both fixed in LEARNREV).

## PICK-UP NOTE: start here in a new session (status 2026-10-21, ON HOLD by the owner)
The owner paused the clean-up after the audit: "Will do that later — just put some note somewhere so it's easy to
pick up in some other session." Nothing in the product has changed yet. To resume:
1. Read this file, `VIFIX_LEDGER.md` (VF1–VF10) and `VIFIX_P1_REPORT.md`, especially "F. Wave plan" (9 waves, 46
   pieces of 1–2 days, about 70 working days in all) and "Open questions for the owner".
2. **Ask the owner first** (AskUserQuestion cards) how much to do. The options offered on 2026-10-21 were:
   - the most-used areas first: W1 Home/app frame/employee pages, W2 Approvals and W3 Running payroll, about 14 days;
   - all 9 areas;
   - only the worst machine words.
3. Then ask the decisions still open from the report's list:
   - #4 division "Khối" vs "Bộ phận";
   - #5 overtime "Tăng ca" vs "làm thêm giờ";
   - #6 English loanwords;
   - #7 Vietnamese date style (needs code);
   - #8 pay-run names in the company's language and renaming existing ones;
   - #9 the tenant console (911 strings);
   - #10 making the product match practice copies whose Vietnamese is better;
   - the 25 glossary terms marked for review in `VIFIX_GLOSSARY.md`.
4. Re-run the P1 tools first (`docs/handovers/vifix/tools/`, all offline, under 60 s). Other sessions keep changing
   screens, so the 2026-10-21 baseline in `p1_out/` goes stale. Then write `VIFIX_P2_HANDOVER.md` for the first wave
   and launch Opus.

**Owner decisions already made (2026-10-21), binding on every wave:**
| Topic | Decision | Notes |
|---|---|---|
| Pay run | **đợt lương** everywhere | Learn's "đợt tính lương" changes to match. "kỳ lương" stays only for the pay PERIOD. |
| People menu | **Nhân sự** (was "Con người") | Lesson breadcrumbs must follow, so regenerate Learn and diff `pb_learn/i18n/vi_VN.po`. |
| Workforce menu | **Chấm công** (was "Lực lượng lao động") | Same Learn follow-up. Menu names are stored terms: overwrite per database with the guard (LR29) or a targeted update. |

## Phases
| Phase | What | Status |
|---|---|---|
| P1 | Audit: static .po scan, unextracted-literal scan, live Vietnamese sweep of every screen on a clone, glossary draft, replica drift report, wave plan. No product string changes. | **DONE** 2026-10-21 (branch `vifix-p1`, merged 75d221b71, pushed). Report `VIFIX_P1_REPORT.md`. |
| P2…Pn | Fix waves by product area, as P1's wave plan proposes | **ON HOLD** (owner): see the pick-up note above |

Ledger: `VIFIX_LEDGER.md` (rows VF1…). Every handover references it; add a row for every new gotcha.
