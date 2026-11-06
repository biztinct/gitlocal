# VIFIX P1 — audit of the Vietnamese across Payobook (handover for Opus)

Read `VIFIX_PROGRAM.md` (standing rules and verified translation facts) and `VIFIX_LEDGER.md` first. Work in your own
git worktree, on branch `vifix-p1` from the 19.1 tip. **No product string changes in this phase.** You build tools and
a report; the fixes come in later phases from your wave plan. No deploy, no push.

## 0. Design bar (verbatim, binding)
"Extreme WOW, intuitive, out-of-this-world experience, best in class." The audit is the foundation of that. Its
measure is that the later fix waves can be done without anyone re-discovering anything: every finding has a module, a
file:line or a screen location, the English, the current Vietnamese and a proposed Vietnamese.

## 1. Scope
- **A. Static .po scan** (`tools/vifix_po_scan.py`, offline). For every module of ours (`pb_*`, `biz_*`,
  `biztinct_*`, not the vendored standard addons; split with the CLAUDE.md rule) report:
  - msgstr identical to the English, minus an allowlist (VF1);
  - one English msgid translated several different ways across modules (terminology drift; the top 100 by how often
    the term shows);
  - suspicious literal translations, from a seed list you extend as you go: cú đấm, hết tiền, trần nhà, bề mặt,
    giao diện tìm kiếm, any "Odoo";
  - msgstr with an English word of 4 or more letters inside a Vietnamese sentence (mixed language);
  - entries missing one of the three required markers (memory `po-translation-loading-rules`);
  - placeholder mismatches (`%s`, `%(name)s`, `{name}`, `{{…}}` differing between msgid and msgstr), which would crash
    or garble at runtime.
- **B. Unextracted literals** (`tools/vifix_literal_scan.py`, offline). User-facing English in `static/src/**/*.xml`
  text nodes and attributes (`title`, `placeholder`, `aria-label`, `string`, `help`) and in JS strings rendered to
  the screen, that has no matching msgid in that module's `.po`/`.pot`. Report a count per module, plus the file:line
  list. Watch for strings built by concatenation, which can never be translated whole.
- **C. Live Vietnamese sweep** on a dump-based clone of payobook (AI off, jobs off). Use the QA user on the clone
  only, set its language to vi_VN on the clone, with default company 5 "Payobook Vietnam JSC" (the demo world). Visit
  every sidebar entry and every hub tab, the main detail drawers (employee, contract, pay run, payslip, approval
  request), and the Settings cards. On each one collect the visible text nodes that are still English or Latin-script
  outside the allowlist, plus a screenshot. Headless Chrome on a fresh port, sign in via fetch. Output one row per
  screen: the screen path as the menu shows it, the count, the strings, and the screenshot name. Also note anything
  that reads as clearly wrong Vietnamese.
- **D. Glossary draft** (`docs/handovers/vifix/VIFIX_GLOSSARY.md`). For the 150 most-used payroll and HR terms: the
  English, the ONE Vietnamese to use, the current variants found (from A), and a one-line reason. Start from the
  terms `pb_learn` and `pb_hr_payroll_vietnam` already use (Vietnamese payroll vocabulary: BHXH, BHYT, BHTN, thuế TNCN,
  người phụ thuộc, lương gross/net, and so on). Mark every choice you are unsure of for the owner's review.
- **E. Replica drift report** (LEARNREV leftover #4). Run the replica half of `pb_learn/tests/guide_truth.py` against
  every replica screen in `docs/tutorial_poc/author/practice-data.js` / `pb_learn/static/src/engine/fixture.js`, not
  only the 16 manifest screens. For each replica, list headers and labels that no longer exist on the real screen
  (read the real screen's template). Report only; no fixes.
- **F. Wave plan.** Group the findings into fix waves of about 1–2 days each, ordered by how many people see the
  screen: Home, Pay Run, People and Lifecycle, Time and leave, then Settings and the rest. For each wave give the
  modules, the counts, how much needs code changes (`_t()` wrapping) versus .po edits, how much needs a stored-term
  update at deploy (model terms) and its risk.

## 2. Binding non-goals
No change to any product .po, template or JS in this phase (tools and docs only). No Learn content (LEARNREV owns
it). No deploy. Never run `gen_learn_data.py`. Do not touch abm.

## 3. Verified plumbing (do not re-derive)
- Translation loading rules, code vs model terms, overwrite guard: `VIFIX_PROGRAM.md` "Translation facts".
- The PO reader: `odoo.tools.translate.PoFileReader` (on the server, `sys.path.insert(0, "/odoo/odoo-server")`;
  locally the vendored copy of `odoo/tools/translate.py` may differ, so prefer running the scan against the server
  copy, or use `polib`).
- Standard vs ours: `git -C /odoo/odoo-server ls-files addons | cut -d/ -f2 | sort -u` on the server is the standard
  set (CLAUDE.md).
- Clone recipe and browser-walk lessons: `docs/handovers/learnrev/LEARNREV_LEDGER.md` LR17, LR26, LR60–LR62, LR79,
  LR80 (reach a screen the way a user does, through the menu). The QA login is in memory `payobook-qa-login`; never
  write its password into the repo.
- Replica gate: `pb_learn/tests/guide_truth.py` `replica_region` / `check_replica` (lines ~389–460).

## 4. Tests
- **T1** each tool runs offline on the repo in under 5 minutes and is deterministic (same output twice).
- **T2** spot check: the tools find the known bad examples ("Thiếu cú đấm", "Hết tiền") and the about 80 Lifecycle
  labels; if they do not, fix the tool, not the expectation.
- **T3** the live sweep covers every sidebar entry and hub tab. List any you could not open and why.

## 5. Report
`docs/handovers/vifix/VIFIX_P1_REPORT.md`:
- the totals per scan;
- the top modules per scan;
- the live sweep table and the glossary summary (how many unsure);
- the replica drift table;
- the wave plan;
- new ledger rows (VF2…);
- open questions for the owner, written as real-world choices.

Screenshots go in the scratchpad (path in the report). Commits: tools, glossary and report, with explicit paths,
ending `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Commit early; if your budget runs low, write the
report with what you have first.
