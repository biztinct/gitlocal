# NEWHIRE P5a — languages, lessons, and ready-to-merge

Read first: `NEWHIRE_LEDGER.md` (binding), the P3b and P4 reports, `NEWHIRE_FACTS_ONBOARD.md` §L (Learn hits — file:line,
**do not re-derive**) and §M (deploy conventions, for context only — P5a deploys NOTHING).

Work ONLY in `/Users/adity/Documents/GitHub/gitlocal-worktrees/newhire` (branch `newhire`). No deploy, no server access,
no push.

**Non-goals (binding):** no new features; no behaviour change in the studio beyond what is listed here; no deploy.

## 1. Bring the branch up to date (do this FIRST)
`git fetch origin && git merge origin/19.1` into `newhire` (merge, not rebase — the branch is pushed). Other sessions ship
to 19.1 all day; expect conflicts in `pb_learn` content and in the modules P1/P2 factored out (`pb_scheme_map`,
`pb_probation`, `pb_hr_payroll_formula`, `pb_people`). Resolve keeping BOTH sides' intent; if a manifest version we
bumped was also bumped upstream, take the higher and bump ours once more. Re-run the full `pb_new_hire` suite and the
suites of every module we extend after the merge; record before/after counts. If a conflict is not mechanical, stop and
report rather than guess.

## 2. Languages — vi_VN and id_ID
- `pb_new_hire/i18n/pb_new_hire.pot`, `vi_VN.po`, `id_ID.po` covering EVERY user-visible string: XML views/data, Python
  `_()` strings (reasons, fixes, notes, toasts, leg rows, mail bodies, the `/my/welcome` page), JS/XML templates
  (`_t`), paper and item names seeded as data.
- Obey the three PO loading rules in memory/ledger (PO translation loading rules: correct `#:` reference comment /
  module header, exact msgid incl. whitespace, file named for the lang code) and run the repo's PO parse gate.
- LOOK rule: a translation fix is TWO fixes — the `.po` AND any value already stored. Seeded translatable data
  (`pb.new.hire.paper` names, item labels) must be translatable fields loaded from the `.po`; prove with a test that a
  `vi_VN` user reads Vietnamese names.
- P3b open question 1 — DECIDED: asked items are shown in the READER's language. Store the item key, render the label at
  display time (welcome page, New joiners list, emails use the recipient's language). Migrate rows that stored a label.
  Test: approver in English, employee in Vietnamese → Vietnamese on `/my/welcome`.
- Emails: rendered in the recipient's language (employee: their `lang`; HR notes: the HR user's).
- White-label: no "Odoo" in any msgid or msgstr. Add a static test that greps every `pb_new_hire` user-visible source
  and both `.po` files.
- Translation quality: natural HR wording a Vietnamese / Indonesian payroll officer would use; keep the product's
  existing terms (grep the other `pb_*/i18n/vi_VN.po` / `id_ID.po` for "pay scheme", "pay run", "Country of work",
  "trial period", "New joiners" and reuse those exact translations).
- Shared-module strings added in P1/P2 (`pb_people` etc.): add to those modules' `.po` files too.

## 3. Lessons follow the screen (FACTS_ONBOARD §L lists every hit)
- Add `data-coach` anchors to the studio: the step rail, each step's main card, the record panel, the payslip example,
  the Send button, the source tiles. Register them in `pb_learn/static/src/anchors.json` with truthful texts.
- Rewrite the `pe-head` anchor text, the `addperson` intent, and lesson `sc_people` "Add your first employee" for the
  seven-step screen (three required steps, the rest have sensible answers already filled in; a second person approves).
  Replace the `rep-newemp-*` replica (`screens.js newEmployeeHTML`, `fixture.js`) with a faithful small replica of the
  studio's first three steps + Check and add; update `pb_learn/tests/test_scenario.py` accordingly.
- Every other hit in §L (`learn_content.json` lines, `pb_people/learn_manifest.py` comment) updated.
- **Trap**: the Learn generator wipes `pb_learn/i18n/vi_VN.po` — back it up before, restore/merge after, and prove the
  line count did not drop. Add vi/id for every new lesson string.
- Run the whole `pb_learn` test suite; walk the lesson in the browser end to end in English and Vietnamese.

## 4. The old window's dependants (§L "Code that inherits it")
`pb_pay_scales/models/joiners.py:86` + `joiner_hint.xml:41`, `pb_orgchart/models/onboard_fill.py:20` +
`orgchart_edit.js:360`, `pb_updates/models/updates_joiners.py:824`. For each: state what it gave the old window, whether
the studio already gives the same (P1–P4 reports), and close any gap INSIDE `pb_new_hire` (optional-dependency pattern:
feature-check the model, no hard `depends`). Org chart "add a person here" must open the studio with the manager and
team prefilled. Where `pb_new_hire` is NOT installed, the old window must keep working untouched — prove with a test
or a walk on a database without the module.

## 5. Ready-to-go-live checklist (write it, do not run it)
In the report, a table for the deploy phase: every module with a changed manifest version (old → new), which of the
five live databases have it installed (FACTS_ONBOARD §M3), whether it carries JS/SCSS (asset purge needed), every data
file with `noupdate`, every scheduled job the install creates (and its default on/off — on databases with outgoing
email off on purpose the reminder job must do no harm; prove in a test), every migration script, and anything that
writes on install to existing records (must be nothing; prove it).

## Tests and walks
T1 PO parse gate both languages; T2 no-"Odoo" static test; T3 vi reader sees vi paper/item names; T4 cross-language
asked items; T5 email language; T6 learn scenario tests; T7 dependants (§4) each; T8 studio absent → old window works.
Walks (Claude-in-Chrome, NH17): W1 whole studio in Vietnamese, W2 in Indonesian (no English leftovers, no clipped
labels at 340 px — longer words!), W3 `/my/welcome` in both at phone width, W4 the lesson in en + vi, W5 org chart add,
W6 console clean.

## Report back — `NEWHIRE_P5A_REPORT.md`
Sections as before + the merge notes (conflicts and how resolved), string counts per language, the §5 table. Commits
feature-scoped with explicit paths (merge commit; languages; lessons; dependants; docs). Do not push.
