# PAY RUN SCREEN (PRS) — conventions + gotcha ledger

Shared by every PRS handover. Read it before coding; append a numbered row
(PRS-Gn) whenever you hit a new trap. Never delete a row — strike it through
with a dated note if it stops being true.

Programme: premium redesign of the ONE pay run screen (`hr.payslip.run` form).
Owner approved the mock-up 2026-11-03:
https://claude.ai/artifact/FQ8Gdp8PAKEfij7brmm892 — file copy
`docs/design/payrun-screen-prototype.html` (6 "moments" via the bottom-left
control). The mock-up is the visual + behavioural spec. Where a handover and
the mock-up disagree, the handover wins (it carries the verified facts).

## Binding conventions

C1. **White-label.** The word "Odoo" never appears in anything a user can see
    or receive: labels, tooltips, toasts, errors, dialog titles, exported
    files, `.po` msgstr. Use "Payobook", "the system" or a neutral word.
    Technical identifiers (`from odoo import`, xml ids, module names, log lines,
    comments) are NOT rewritten.
C2. **Plain English on screen.** Screen words, never code words: "pay run",
    "take-home", "pay data file", "who signs it off". No rule codes, no field
    names, no "batch", no "state". Sentences are built server-side as whole
    msgids (`self.env._("…%(x)s…", x=…)`) so a translator sees whole lines.
C3. **One pay-band rule.** Gross / Deductions / Net / Employer cost come from
    the shared bucket SQL `hr.payslip.run._pb_bucket_sql` (run level) and its
    ORM twin `om_hr_payroll/models/pay_bands.py` (`hr.payslip.pb_pay_totals`).
    Never re-derive a band from `hr_salary_rule_category.code` yourself.
    `pb_payruns/tests/test_pay_bands.py` tests 14–16 hold the two together.
C4. **Money carries its own currency.** A run's money is `run.pb_currency_id`
    (the scheme's currency, SCHEMECTX P1), never the company's. Format with the
    currency's own decimals: VND / IDR / KHR show NO ".00". No total ever adds
    two currencies.
C5. **Design system (locked).** Primary `#5A4BB0` (hover `#4A3D96`, soft
    `#EDEAF8`), money/success `#0F7B4F`-family green, amber `#B45309`, rose
    `#DC2655`, canvas `#F4F5FB`, ink `#1E1B2E`, border `#E4E5F1`. ONE solid
    primary button per screen; everything else outline or ghost; danger = rose
    text. No gradients except the faint hero wash already in the mock-up. Lucide
    icons only (the app ships them via `pb_import_kit`'s `ic()` registry) —
    never emoji. Light-only product.
C6. **Design bar (owner's words, binding):** "extreme WOW, intuitive,
    out-of-this-world experience, best in class." Every surface needs a hero
    moment; zero dead-ends (every state — empty, loading, error, partial, huge —
    designed, every failure names its reason and its next step); plain language
    over code vocabulary; motion with purpose; keyboard + bulk ergonomics where
    rows are involved; measured against the best SaaS tool in the category, not
    stock Odoo. Each phase report scores itself against this bar.
C7. **Never break inheritors.** Ten view layers extend
    `om_hr_payroll.hr_payslip_run_form` (list below). Their `<header>` buttons
    and `<sheet>` xpaths must keep resolving — hide, never delete, nodes other
    modules anchor on.
C8. **Learn follows screens.** A screen change updates any Learn lesson, tour,
    coach text or practice replica that points at it, EN + VI, in the same work
    (`pb_learn/static/src/anchors.json`, `pb_learn/static/content/learn_content.json`,
    `pb_learn/static/src/engine/{screens,fixture}.js`). If nothing is affected,
    say so in the report.
C9. **Translations.** New user strings get vi_VN entries in the module's
    `i18n/vi_VN.po` AND its `.pot` if one exists. Every entry needs
    `#. module: <m>`, `#. odoo-python` or `#. odoo-javascript`, and
    `#: code:addons/<m>/<path>:0`. Run the PoFileReader gate on the box before
    deploying (see memory po-translation-loading-rules).
C10. **Commits.** One feature-scoped commit per phase on branch `19.1`, explicit
    paths only (never `git add .`/`-A`; other sessions' WIP is in the tree).
    Message = problem → fix → decisions; end with
    `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No passwords in
    the repo (it is public). Fable pushes; subagents do not.
C11. **Deploy contract** = repo `CLAUDE.md` (one addons dir, clean staging dir,
    per-module scoped `rsync --delete`, never `--delete` into the addons root,
    never deploy vendored standard addons, all four DBs `payobook`,
    `payobook_template`, `p0clone`, `rize` — NEVER `abm`). Before any deploy:
    `ssh Payobook19v2 cat /opt/deploy-notes.md`, wait if a START has no DONE,
    append START/DONE lines (`sudo tee -a`), take
    `flock /tmp/payobook-studio-deploy.lock`, announce to other live sessions
    (ListAgents → SendMessage) before any `-u`/restart. Snapshot active cron ids
    per DB before/after with `id||','||active::text` (PRS-G4); compare counts
    with the last DONE line.
C12. **Browser proof is mandatory.** No UI is "done" until it has been opened
    in Chrome MCP, every control clicked, and the console read for errors.
    payobook.com walk with the QA login (see memory payobook-qa-login; never
    write its password into the repo). Rize run 1591 may be OPENED to look, but
    nothing on rize is changed, submitted or recalculated (owner ruling below).
C13. **Header-button guard (P2).** The pay run screen hides the form's native
    `<header>`. Every `<header><button name=…>` in the COMPOSED form must be
    offered by `get_run_screen` (primary, Downloads or More) or listed in
    `RETIRED` in `pb_payruns/tests/test_run_screen.py` with a one-line reason.
    `test_t14_every_header_button_is_offered_or_retired` fails otherwise, so a
    module that adds a header button can never vanish silently behind the new
    screen. Generate Payslips lives on as the primary "Make payslips" (empty
    run) and More › "Add or remake payslips" (run with payslips).

## Owner rulings (do not re-ask)

R1. Phased build; mock-up approved as shown (2026-11-03).
R2. Rize run 1591 "Rize Vietnam Payroll · October 2026" covers 1–30 Sep. Owner
    says that is a mistake but: **change nothing on it** — ask Rize first. The
    new screen must show a plain warning when a run's name names a different
    month from its dates, so Rize sees it themselves.
R3. "Compared with last month" shows only when an earlier run on the same
    scheme exists; otherwise the screen says so plainly (Rize's VN scheme has
    no earlier run today).
R4. (2026-11-04) A scheme with NO sign-off (fast lane, e.g. Rize VN) shows the
    route check as AMBER, not green: "No sign-off is set for this scheme.
    Sending it approves it straight away." The Send button's confirm says the
    same. Amber does not make the run unready and does not add to the
    primary's warn badge (that counts rose rows only).
R5. (2026-11-04) "Compared with" = ONLY the run of the SAME KIND (end of
    month vs mid-month / same run type the scheme map uses) for the CALENDAR
    MONTH JUST BEFORE this run's month, same scheme + division + currency, with
    payslips. None → compare None + "nothing to compare with yet". This
    narrows R3 and drives the per-person "changed" flags too.
R6. (2026-11-04) "Compared with" counts only an APPROVED (done) run of the
    same kind for the month just before. Top-up runs only ever compare with
    top-ups, never with a full month — using the existing notion of kind; do
    not invent one. A draft or pending earlier run → nothing to compare with
    yet. (P2 follow-up 1: the approved-only half is built. NO existing field
    tells a top-up apart — payobook's top-up / awards / bonus runs carry the
    same scheme and the same scheme cycle type as the full month — so the
    top-up half waits for a decision; see PRS_P2_REPORT "Follow-up 1".)
R7. (2026-11-04) "Recalculate everyone" and bulk Recalculate ask first:
    "Recalculate 63 payslips? Their figures may change." (1/N variants), OK
    "Recalculate", cancel "Not now". Not a danger style.

## The ten view layers on the pay run form (verified 2026-11-03, rize)

| module.xml id | what it adds |
|---|---|
| om_hr_payroll.hr_payslip_run_form (base) | header: Download Excel, Generate Payslips, Set to Draft, Submit, tier buttons, Reject, Mail Batch Payslips, statusbar; sheet: name, period, credit_note, slip_ids |
| pb_hr_payroll_formula.view_hr_payslip_run_form_formula_recompute | Recompute Formulas (after Download Excel) |
| pb_hr_payroll_formula.view_hr_payslip_run_form_std_work_days | pb_std_work_days + note, before credit_note |
| pb_hr_payroll_formula.view_run_application_certification | "Application data review" group (only when application_data_mode) |
| pb_hr_workforce.view_hr_payslip_run_form_inherit_workforce | Payroll Report (after Download Excel) |
| om_hr_payroll_account.hr_payslip_run_form_inherit | journal_id before credit_note |
| pb_comp_ben.view_hr_payslip_run_form_pack | "Finance pack" group (only when pb_pack_note) |
| pb_payroll_templates.run_input_review_button | Input changes |
| pb_payruns.hr_payslip_run_form_pb_enhance (prio 30) | Submit for approval, Reject (asks why), Print Payslips, Split Into Review Groups, Delete Draft Payslips, vu_progress_rail, route/rejected/sent-back/no-data/unbalanced alerts, KPI band, slip list |
| pb_source_atlas.hr_payslip_run_form_source_atlas (prio 40) | Where the numbers come from |

The "R2 / DRAFT" card at the top is the VU form engine's auto hero
(`biz_theme/static/src/js/vu_form_compiler.js:45` `buildHero`).

## Gotchas

PRS-G1. OWL `t-portal` takes an EXPRESSION: `t-portal="'body'"`. Bare `body`
        is a variable → "invalid portal target" blanks the screen.
PRS-G2. `t-call` params must not reuse a component getter name (prefix them,
        e.g. `qRows`) — `t-set` onto a getter name crashes.
PRS-G3. Asset cache: after JS/SCSS deploy, per DB `INSERT INTO
        orm_signaling_assets DEFAULT VALUES`, then
        `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'`, then bump
        `web.assets.version`. Without the signalling row the bundle URL hash
        stays the same and browsers keep old CSS for up to 2 days.
PRS-G4. Cron snapshot: `psql id||','||active` prints `true`/`false`, not `t`/`f`.
        `-u` of a module re-imports its dependents' cron data ACTIVE.
PRS-G5. SQL readers must `flush_model([...])` the fields they read first; a
        recompute triggered by a write that has not landed is the normal case.
PRS-G6. Odoo wraps every `<field>` in its own div; inside a flex `alert` a
        sentence with a field in the middle becomes side-by-side columns. Wrap
        the sentence in ONE child element.
PRS-G7. `<field nolabel="1"/>` inside a `<group>` takes the narrow label cell
        unless it also has `colspan="2"`.
PRS-G8. A JS service listing a non-service in `dependencies` (e.g. `"rpc"`)
        stops the WHOLE web client mounting with only a console line as
        evidence. Read the console every time.
PRS-G9. Deleting a pay run used to leave its draft payslips loose for the next
        run to adopt. Never "take a payslip off a run" by clearing
        `payslip_run_id` — delete the draft payslip instead (the same rule as
        `action_pb_delete_draft_payslips`).
PRS-G10. (P1, 2026-11-04) The RUN's gross and a PAYSLIP's gross use the same
        rule at different levels: "the GROSS lines, else basic + allowances".
        On a run where some payslips have a GROSS line and others only basic +
        allowances, the run's gross is the GROSS lines alone, so the people
        table's gross column does not add up to the run's gross. Kept exactly
        as it was (P1's zero-change rule; the ORM twin `pb_pay_totals` does the
        same). Net, deductions and employer cost always add up. Fable decides
        whether to change the run rule.
PRS-G11. The `payrun` approval process row is DATA of `pb_approval_config`
        (data/processes.xml), not of pb_payruns. A test database without
        pb_approval_config skips every approval test SILENTLY ("the approval
        catalogue is not installed here") — test_approval_engine included.
        Install pb_approval_config (and pb_pay_delivery, pb_source_atlas,
        pb_payroll_templates, pb_payslip for the menus) in the scratch DB.
PRS-G12. The local `am_tpl` template is stale (no `hr_payroll_period_input`
        table, no `res_users.pb_access_ready`), so `runtests.sh pb_payruns`
        fast mode dies at registry load. What works: a fresh DB,
        `-i pb_payruns --without-demo=all` (~2 min, 102 modules), then
        `-i pb_approval_config,pb_pay_delivery,pb_source_atlas,
        pb_payroll_templates,pb_payslip` (~30 s); clone it per run with
        `createdb -T`. Re-runs: `-u pb_payruns --test-enable --test-tags
        /pb_payruns` on the clone (~40 s).
PRS-G13. Odoo 19 job and team are on the employee's VERSION. `employees.read(
        ['job_title','department_id'])` computes the version per person and a
        classic read adds a display name per many2one: ~1 s on a 520-person
        run. Read `current_version_id` (stored), then `hr.version` with
        `read(..., load=None)`, then the department/job names once
        (`_screen_employee_rows`).
PRS-G14. biz_access wraps record attribute access (`studio_policy.__getattribute__`):
        a 520-payslip run made 728,000 such calls when payslips were looped as
        records. Anything per row reads dicts (one SQL pass or `read(load=None)`),
        never `for slip in slips: slip.x`.
PRS-G15. On a database without biz_debrand the system account is still called
        "OdooBot", and a run it created says "Prepared by OdooBot". Live DBs
        rename it to the brand (biz_debrand res_config_settings, "OdooBot →
        brand bot"). Tests that walk a payload for the vendor name rename
        `base.partner_root` first, as live does.
PRS-G16. Measuring NEW server code on a live database without deploying it:
        stage the module in `/tmp/<x>/addons/`, then as the odoo user
        `odoo-bin shell -c /etc/odoo-server.conf -d <db>
        --addons-path=/tmp/<x>/addons,/odoo/odoo-server/addons --no-http
        < script.py`, script ends with `env.cr.rollback()`. The running server
        is untouched; remove `/tmp/<x>` afterwards. `/odoo` is not readable by
        `ubuntu` — hash it under `sudo bash -c`.
PRS-G17. `_pb_overtime_included` matches its tokens as SUBSTRINGS of the code,
        so any code containing "OT" (TOTAL…, TOTALDED) counts as overtime. An
        old quirk, kept identical when P1 moved it to one grouped read.
PRS-G18. (Finding, 2026-11-04) Rize run 1591's route resolves to a FAST lane
        ("No approval needed", binding 3, scope `scheme:4760`). Pressing Send
        for approval would approve it at once — nobody signs it off. The run's
        scheme is named "Rize Vietnam Payroll — archived master-data scheme".
        Nothing was changed (R2); the owner should know before anyone presses
        it.
PRS-G19. (P2) `invisible="1"` removes a node from the rendered form, so no CSS
        class can ever bring it back. The "Show the classic layout" escape hatch
        needs the old pieces RENDERED and hidden by a class (`pb-prs-legacy`,
        shown again under `body.pb-prs-classic`).
PRS-G20. (P2) An xpath `position="move"` only works as a DIRECT child of a spec.
        To move a node into a NEW wrapper, insert the wrapper in one spec, then
        move into it with a second spec (`//div[hasclass('pb-prs-lower')]`
        inside → `//sheet/group[...]` move). After the move `//sheet/group`
        no longer finds Run settings: later views must use
        `//group[hasclass('pb-prs-settings')]` or a field name.
PRS-G21. (P2) `journal_id` comes from om_hr_payroll_account, which pb_payruns
        does not depend on. An xpath on it would break the view wherever
        accounting is absent, so its label is set in `hr.payslip.run._get_view`
        (only when the composed form carries it).
PRS-G22. (P2) A local scratch DB cloned before another session added a stored
        field fails 30+ tests with "column a.pb_fill does not exist" (their
        `_run_checks` advisory). `-u` the module that owns the column too
        (here pb_hr_payroll_formula) — it is a stale schema, not a bug.
PRS-G23. (P2) Odoo 19 JS `sprintf` with a keyed dict substitutes `%(x)s` only:
        a literal "%%" stays TWO characters. Write a bare "%" in a keyed `_t`
        sentence ("%(pct)s% of the total cost").
PRS-G24. (P2) `pb_std_work_days` ("Full month in working days") had no readonly
        rule at all — it could be changed on an approved run. The run screen's
        view now locks it outside draft, like every other run setting.

PRS-G25. (P2) A bubbling `keydown` listener on `window` never sees Escape in
        this web client — another window-level listener consumes it first. The
        screen listens in the CAPTURE phase (`useExternalListener(window,
        "keydown", fn, {capture: true})`) and steps aside whenever an Odoo
        dialog is open, so it never steals Escape from a dialog.
PRS-G26. (P2) Bootstrap owns `.row` (flex-wrap, negative margins, `> *`
        width 100%) and `.badge` (upper-case). A component class named `row`
        or `badge` inside a backend screen is silently re-laid out; prefix them
        (`prs-row`, `prs-badge`).
PRS-G27. (P2, local testing) A cloned scratch DB has no filestore, so its
        cached asset bundles 404 and the web client never boots. Purge
        `/web/assets/%` attachments (or copy the source filestore) after
        `createdb -T`, and insert an `orm_signaling_assets` row after a JS
        change on a running server, or the old bundle keeps being served.
PRS-G28. (P2) Timing the payload in an `odoo-bin shell` with repeated calls in
        ONE env is misleading: the second call reads a warm field cache. Each
        web request starts cold. On payobook run 2419 (520 payslips) as the QA
        user the shell said 0.56 s (main) where the browser saw ~4.0 s main +
        ~5.4 s route (server log: 2,060 and 3,160 queries). Time with
        `env.invalidate_all()` before each call, or read the werkzeug line's
        query count / time in the server log. The cost is biz_access: every
        field `__get__` on a guarded model runs `_studio_field_allowed` →
        `_studio_acl_sources`, an UNCACHED `ir.model.access` search. P2 removed
        the biggest pb_payruns hot spot (`_pb_overtime_included` read `state`
        per payslip); the rest is app-wide and belongs to biz_access (a cache
        on `_studio_acl_sources` per model/operation/request).
PRS-G29. (P2) The app-wide logo loader covers any screen while an ordinary
        `orm.call` is slow. A screen with its own skeletons must load with
        `orm.silent` or the loader hides them (seen over the money card).
PRS-G30. (P2, testing) The payobook QA account may not create pay runs ("This
        field cannot be supplied when creating this record: name") and there
        is no run waiting for approval in the demo world, so the empty-run and
        pending moments (B2, B3) cannot be walked there without submitting a
        demo run. They are covered by T2/T5 and the local smoke test.
