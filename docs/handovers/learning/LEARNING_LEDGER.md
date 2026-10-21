# LEARNING programme — ledger

Programme: Rize Learning & Development as its own top-level menu. Design page:
`docs/design/rize-learning-blueprint.html` (owner-reviewed 2026-10-21). Fable designs,
Opus implements and tests each phase in the same session (no Fable bulk code review).

Every handover in `docs/handovers/learning/` references this file. Add a row whenever a
new gotcha, ruling or convention is hit. Rows are `LN` (ledger) and `LD` (owner decision).

## Owner decisions

| id | date | decision |
|---|---|---|
| LD1 | 2026-10-21 | Phased workflow: Fable designs, Opus builds+tests, phases L0→L7 back to back. |
| LD2 | 2026-10-21 | New root is **Learning** (VI **Học tập**). The `pb_learn` product-guide entry is renamed **Help** (VI **Trợ giúp**) — "Guide" was first chosen (14:15) then dropped (14:40) because the in-screen help panel is already called "Guide" ("Guide · Runs"; lessons say "press Understand in the Guide"). The panel keeps "Guide". xml id `pb_learn.item_learn_journey` unchanged. |
| LD3 | 2026-10-21 | Training leaves Talent completely. Talent keeps GOALS · GROWTH · PRAISE. A growth plan may link to a learning path (L3). |
| LD4 | 2026-10-21 15:40 | Country packs: **all four in L2** (Vietnam safety-training groups, India annual awareness session, Indonesia licence register, Singapore training hours) — not one at a time. |
| LD5–LD9 | open | Practical sign-off (L4), outside catalogue (L5), offline (L7), badges (L7), PayAI drafting (L7) — ask when the phase comes up (page §8). |

## Standing rules carried in (do not restate per phase; cite the row)

| id | rule |
|---|---|
| L1 | White label: no "Odoo" in any user-visible string (labels, help, selection values, mail, `.po`). Technical identifiers untouched. |
| L2 | Rail standard (NAV ledger R1/R2): 72 px sticky rail, 60 px buttons, 18 px icon over 9 px uppercase label, ≤2 lines in EN and VI, ten items target, twelve hard max, counts only on queue items, no hover-widening. |
| L3 | NAV ledger R7: Learn lessons, coaching, tours and training replicas updated in the same phase as any menu change; bump `pb_learn`. R8: Access and delegation screens must show the new menu after every phase. R10: old names stay as command-bar keywords. |
| L4 | Design mandate: hero moment named per screen; zero dead ends; Lucide icons only; quiet-board pattern (grey at zero, colour only to act); browser validation with Chrome before "done". |
| L5 | Deploy: one addons dir; tiered deploy rule (say the tier); read `/opt/deploy-notes.md` on Payobook19v2 first and append START/DONE; take `flock /tmp/payobook-studio-deploy.lock`; announce to peer sessions (ListAgents) before any `-u`/restart; active DBs payobook, payobook_template, p0clone, rize; never abm; warm each site with one curl after a restart; snapshot active cron ids per DB before/after (payobook 37, rize 69, p0clone 26, template 0). |
| L6 | Money: nothing in Learning writes a payslip. Claims and pre-approved requests become `pb.incentive` awards on the one-off lane only. |
| L7 | Commits: feature-scoped, explicit paths (never `git add .`), no credentials; push 19.1 only when the branch has no foreign unpushed commits above ours. |
| L8 | Plain English in every user-visible string and in every report to the owner; the screen's own words, never model or method names. |

## Gotchas and facts (append as found)

| id | date | fact |
|---|---|---|
| LN1 | 2026-10-21 | `pb_training` ships NO menu and NO rail item of its own (`views/training_views.xml:3-7`, test `tests/test_training.py:914`); it registers a Talent lens (`training_palette.js:56-63`, seq 30) and an Insights lens (:158-164, seq 40) and command-bar rows 3900–3970. |
| LN2 | 2026-10-21 | Internal staff reach "My training" only via the command bar; portal routes `/my/training…` (`pb_training/controllers/portal.py:109-415`) work for internal users too. |
| LN3 | 2026-10-21 | Stock `hr_skills_survey` writes a certification résumé line with `expiration_status` on a passed test (via `certificate.py:252` calling super); `survey.survey` carries validity months. Seed for L1. |
| LN5 | 2026-10-21 | PayAI (gitlocal-19) confirmed it does not depend on the "Learn" label or the Talent → Training path. Binding: `pb_learning_hub` must never open pb_learn lessons through a new tag/lens/focus format, and must have no Access tab (PayAI denies "station:access", "scenario:sc_access:*", "lesson:L23" by focus mark; a new hub screen listing Access content would have to be added to its deny-list first). Sidebar ids PayAI reads stay active: `pb_payhub.item_pay_run`, `pb_sidebar.item_pay_runs`, `pb_home_hub.item_home`, `pb_people_hub.item_people`, `pb_compliance_hub.item_compliance`, `pb_learn.item_learn_journey`. |
| LN6 | 2026-10-21 | Learn regeneration invariants (gitlocal-09 / gitlocal-b6): `pb_learn/i18n/vi_VN.po` must not lose or change any msgstr except the intended rename lines; "gõ DUYỆT" = 1 (297 steps); action tag `pb_payruns` present; 0 "These figures do not add up"; never reload translations with overwrite (LR29). |
| LN7 | 2026-10-21 | A renamed menu label is TWO fixes (LOOK programme rule): the `.po` msgstr AND the stored translated value on the `pb.sidebar.item` row (jsonb `name`). "Learn" → "Help" needs an in-place update of `pb_learn.item_learn_journey` name for en_US and vi_VN ("Trợ giúp") in a `pb_learn` migration or the generator's XML with noupdate=0 plus a post-migrate for vi_VN; verify on every DB after `-u`. |
| LN4 | 2026-10-21 | A new top-level entry = `pb.sidebar.item` in the owning module's `data/pb_sidebar.xml` + icon in the closed map `pb_sidebar/static/src/js/pb_sidebar.js:16` + `FEATURE_BY_TAG` (`pb_tenancy/models/pb_sidebar.py:62`) + `SCREEN_GATES` (`pb_vendor_access/hooks.py:778`) + migration + `pb_sidebar/tests/test_ia_c5.py` TARGET_RAIL. Precedent: NAV P2 A9 (`pb_talent_hub`). |
| LN8 | 2026-10-21 | **Plain employees never see the left menu.** pb_me_portal sends an internal user with an employee record and no HR / payroll / hiring access to `/my` for every back-office URL (NAV ledger P3d), so GROW › Learning and its "My learning" tab reach back-office staff only (HR, payroll, managers who are back-office users). Employees keep `/my/training` (their portal home shows overdue courses). Any phase that designs for "every employee" in the back office must design the portal side too. |
| LN9 | 2026-10-21 | **New `.po` entries do not show in an already-open browser** until the web client's translation hash changes; locally a server restart is not enough — clear the browser's cached translations (or upgrade the module, which live deploys do). `/web/webclient/translations?lang=vi_VN` shows what the server serves. |
| LN10 | 2026-10-21 | **pb_training's server words are English constants**, not `_()`: `due_words` ("3 days left"), `ASSIGN_REASONS` ("One-off"), `ASSIGN_STATES`, `duration_words` ("30 min"). Vietnamese readers see them in English on the old board and the portal. L0's My learning says due words and reasons from the date / key with `_t` (same whole sentences). Fix at source in a later phase (mail templates read them too — translate per recipient). |
| LN11 | 2026-10-21 | Talent's `SCREEN_GATES` row (pb_vendor_access) still lists the three training roles — L0's non-goal kept it. A person whose only role is a training role sees Talent with no tabs. Remove them in L1 (gates are additive: existing databases need the row edited too). |
| LN12 | 2026-10-21 | `ic()` (pb_import_kit) already has `user`, `target`, `home`, `award`, `helpCircle`, `layoutGrid`, `listChecks`, `fileCheck`, `bell`; it has no `layoutDashboard` / `lifeBuoy`. The Learn replica sprite (`pb_learn/static/src/journey/icons.xml`) has `target`, `help-circle`, `grad-cap`, no `life-buoy`. The sidebar ICONS set now has `target` and `life-buoy`. |
| LN13 | 2026-10-21 | **OWL template text is translated by its exact inner text** (only the ends are trimmed): a paragraph wrapped over several lines has a msgid with the newlines and indentation in it. Keep every translatable text node on one line. |
| LN14 | 2026-10-21 | The local test DBs (copies of `am_nav_*`) create users in Vietnamese, so facade tests that assert English sentences must force `lang='en_US'` on the class env (`cls.env = cls.env(context=dict(cls.env.context, lang='en_US'))`). |
| LN15 | 2026-10-21 | **Other deployers may ship our commits.** ChatGPT's combined deploy (START 07:50 UTC, commit `7db810a1e` on top of L0 commit (e)) carried L0 to the live databases under the owner's "combined deployment" instruction, before L0's own deploy gate. Read `/opt/deploy-notes.md` before planning, and plan only the delta that is not already live. |

## Phase log

| phase | status | handover | report |
|---|---|---|---|
| L0 The Learning menu | built + tested; at deploy gate (L0 a–e shipping inside ChatGPT combined deploy 07:50 UTC) | `L0_LEARNING_MENU.md` | `L0_REPORT.md` |
