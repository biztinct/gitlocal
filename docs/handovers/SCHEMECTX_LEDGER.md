# SCHEMECTX — conventions and gotcha ledger

Programme opened 2026-09-19. Three owner findings on `rize.payobook.com`:

| Phase | Finding | Handover |
|---|---|---|
| 1 | An India scheme pays in dong — currency must follow the scheme's country | `SCHEMECTX_PHASE_1_HANDOVER.md` |
| 2 | Every contract carries every scheme's components — they must follow the person's scheme and country, and analytics must group/filter by both | `SCHEMECTX_PHASE_2_HANDOVER.md` |
| 3 | The studio Settings tab must open the guided journey in edit mode, pre-filled, Active schemes included | `SCHEMECTX_PHASE_3_HANDOVER.md` |

The approved plan is `/Users/adity/.claude/plans/1-when-a-new-twinkling-llama.md`.

## 0. Binding rules for every phase

Rules 1–6 of `docs/handovers/RUNSRC_LEDGER.md` §0 bind here **verbatim** (plain
English + never "Odoo" in a user-visible string; the design bar — extreme WOW,
intuitive, out-of-this-world, best in class, Lucide not emoji; browser
validation mandatory with the console read; commit per feature, explicit
staging, no push; the ONE-addons-directory deploy contract across the SIX
databases `payobook`, `abm`, `payobook_template`, `rize`, `rztest`, `p9clone`;
tests reported by number with evidence). Read that section before anything else.

Additional, programme-specific:

7. **Never edit `pb_formula_studio/models/pb_formula_studio.py`.** Extend with
   `_inherit = 'pb.formula.studio'` (BLUEPRINT ledger rule 7). Its JS/XML may
   be edited.
8. **A read RPC never writes** (BP53). Adoption, lazy line creation, clean-up —
   all of them are explicit write calls.
9. **Never activate a currency** to make a lookup work. Activating one flips
   the multi-currency group for every user. Look it up with
   `active_test=False` and carry its symbol in the payload.
10. **Owner rulings 2026-09-19, do not re-litigate**: (a) every Settings field
    moves into the journey and the old panel is retired; (b) out-of-scheme
    contract lines are hidden, and the zero-value ones are deleted after a
    backup — a non-zero line is NEVER deleted and never silently hidden;
    (c) the journey opens for Active schemes, with safety locks.
11. **Validate on `rize.payobook.com`** — the two schemes there are not live
    and no parent/group is in use; the owner has cleared free testing there.
    Run destructive or fixture-heavy tests on `rztest`. `abm` is retired
    (still upgraded, never used for validation). The rize login is NOT in any
    document — if no session is open in Chrome, say so in the report; do not
    guess or reset a password.
12. **PO rules**: read memory `po-translation-loading-rules` facts as restated
    in `APPROVAL_MATRIX_CLOSEOUT.md`; run the PO parse gate before a deploy
    wave. New strings ship EN + VI.
13. **Test recipe**: `odoo-bin -c /etc/odoo-server.conf -d rztest -u <module>
    --test-enable --test-tags /<module> --stop-after-init --max-cron-threads=0
    --http-port=8199 --gevent-port=8198 '--db-filter=.*' --logfile=…`. Never
    `--test-tags` without a scoping `-u`. Deploy upgrades run in a detached
    `systemd-run` unit with a sentinel file; never `pkill -f odoo-bin`; after
    JS/SCSS purge `/web/assets/%` AND bump `web.assets.version` per DB.

## 1. Inherited facts — do NOT re-derive

* Scheme model `hr.formula.config`: `pb_hr_payroll_formula/models/formula_config.py:27`;
  `country_code` Selection `:104-113`; stored computed `country_id` `:115-120`,
  `currency_id` `:122-127`; computes `:836-864`.
* Person → scheme: `hr.employee.pb_paid_by_id` (`pb_scheme_map/models/hr_employee.py:47-60`);
  `pb.scheme.map.resolve` `pb_scheme_map/models/pb_scheme_map.py:271`, `resolve_many :336`, `coverage :458`.
* rize schemes: `Rize Vietnam` (3921), `Rize Vietnam Payroll` (3938), plus `Rize India Payroll` (RS3).
* Journey: tag `pb_blueprint`, arrival params `config_id/step/task` `pb_blueprint/static/src/js/blueprint.js:209-222`;
  URL state needs `router.pushState` + `onMounted` re-assert (BP14/BP38).

## 2. Gotchas (append here as SC<n>)

**SC1 — INR (and most non-company currencies) ship `active=False`.** A plain
`res.currency.search([('name','=',…)])` returns nothing and any `or company
currency` fallback then silently lies. Every currency lookup by name or by
country uses `.with_context(active_test=False)`.

**SC2 — the web client's session currency map holds active currencies only.**
A stock Monetary widget pointed at an inactive currency renders a bare number.
Scheme amounts are formatted from a currency dict carried in the payload
(`{id, name, symbol, position, decimals}`), never from the session map.

**SC3 — carry the SYMBOL from `res.currency`, never the POSITION.** Base data
records VND as written *after* the number (`position: 'after'`, 0 decimals).
Every Payobook screen — studio, payslip, results, wizard — has always written
the sign in front. Honouring the stored side would have flipped every
Vietnamese amount in the product while fixing India. Phase 1's `formatMoney`
therefore takes `symbol` from the payload and always prefixes it; the dict
still carries `position` for anything that genuinely needs it.

**SC4 — a stored compute only heals when something it depends on changes.**
`hr.formula.config.currency_id` depends on `country_code`, and a scheme's
country never changes again, so a row written while the lookup was broken
stays broken forever. The heal is `configs._compute_currency_id()` followed by
`configs.flush_recordset(['currency_id'])` in a migration — assigning inside
the compute marks the stored field dirty, which is what makes it land. Note
that `flush_recordset` flushes *everything* pending for that model, so a
compute that sets several fields writes all of them.

**SC5 — `/odoo` is `drwxr-x--- odoo:odoo`, so `postgres` cannot write a dump
there.** `sudo -u postgres pg_dump -f /odoo/backups/...` fails with "Permission
denied" even after `chown`, because the traverse fails one level up. Dump with
a root-owned redirection instead:
`sudo bash -c "sudo -u postgres pg_dump -Fc -d <db> > /odoo/backups/<dir>/<db>.dump"`.

**SC6 — `rztest` carries a June 2026 pay run, and 20 tests in
`pb_payrun_wizard` / `pb_hr_payroll_formula` are red there because of it**
(`prepare_run` answers `needs_confirmation` instead of `adopted`, and three
`TestStructurelessPayslip` cases plus `TestNetRoleClassifier.test_24`,
`TestJourneyJ10Writeback.test_13b`, `TestRd49SyncCost.test_01a`). Verified
identical on a clean worktree of `HEAD` — they are data-dependent on that
database, not a regression. Always take the baseline before blaming a phase.

**SC8 — a scheme's component scope is its DECLARED contract components PLUS
any other rule of that scheme whose code the catalogue already carries a row
for.** Phase 2's handover said the scope was `pb_records._component_rules`'s
domain alone (`is_contract_component` or `is_text_component`). That is the
right set in live data — `hr.contract.advantage.template` rows are only ever
made by `_get_or_create_advantage_template`, which is fed by exactly those
rules — but the two CAN drift: a rule that was a contract component once, a
template made by hand or by an older import. This list decides what a contract
is ALLOWED TO DISPLAY, so the safe direction is to show a component the scheme
has a rule for, never to hide one. The second half is bounded by the catalogue
(`code in` the scheme's own rule codes), so a code belonging only to ANOTHER
scheme is still out — which is the whole defect and is pinned by a test.

**SC9 — removing the create-time fan-out breaks every fixture that relied on
it.** `hr.contract.create` used to give a new contract one line per catalogue
row, and a dozen test suites make a template, make a contract and expect to
find a line. After Phase 2 the fixture has to lay the lines down itself
(`pb_contracts/tests/scheme_scope.py:catalogue_lines`) AND say who pays the
person (`paid_by`), because an `unassigned` person's drawer shows only the
lines that hold a value. Both are one call each; the suites that already wrote
"reuse the seeded line if there is one, else create it" (CR18's wording) needed
no change at all.

**SC10 — an Odoo shell runs as `odoo`, so a backup file must not go in
`/root`.** SC5 said `postgres` cannot write into `/odoo`; this is its twin at
the other end. `odoo-bin shell` runs as the `odoo` user, so a script whose undo
file defaults to `/root/...` dies with `PermissionError` — and if that write
had come AFTER the delete instead of before it, the delete would have happened
with no undo. Default to `/var/tmp`, and always write the rollback file before
touching a row.

**SC11 — most schemes on the demo databases declare NO contract components at
all, and that changes what the Components tab shows.** Verified 2026-09-19:
on `payobook` the six "Payobook <sector> — End-Month Payroll" schemes that pay
4,503 of the 4,523 people have `is_contract_component = False` on every one of
their ~53 rules, while the 26 catalogue templates come from the VPTQ schemes,
which declare 24 apiece and pay 7 people. On `rize` all 7 mapped people point
at `Rize India Payroll` (2 contract components) although their contracts carry
20 Vietnamese components each; the live Vietnamese scheme `Rize Vietnam
Payroll` declares only 1, and the one with 19 (`Rize Vietnam`) is ARCHIVED.
Consequence: after Phase 2 those people's Components tab is empty, correctly —
their scheme says nothing lives on a contract — and the P2 clean-up would
delete 117,058 zero-valued lines on `payobook` and 140 on `rize`. All of them
are empty, so no value is at risk, but this is demo-data drift and not a
product fault, and it is an OWNER decision, not an engineering one.

**SC12 — "enable part-month pay" is refused unless something is prorated.**
`hr.formula.config` constrains `use_proration` to require at least one
`proration_component_ids` row, and the refusal ("Select at least one prorated
component when proration is enabled.") arrives through
`save_config_settings`'s `msg`, not as a field error. Any card that offers the
toggle has to send the toggle AND the components in ONE save, and show that
sentence beside the picker rather than as a toast. Found by Phase 3 test 4.

**SC13 — `bp_components` was the one Pay rules tab with no `editable` flag.**
`bp_tax_data` and `bp_calendar_data` have always carried `editable` +
`readonly_reason`; the component list carried neither, because the journey only
ever opened it on a draft. Worse, `bp_component_save`, `bp_component_exclude`,
`bp_component_include`, `bp_component_restore_guided` and `bp_regenerate` had
no lock of any kind — tax and calendar refused on a non-draft, the components
did not. Phase 3 gates all five in BOTH modes and ships the flag, on the owner's
ruling of 2026-09-19. No existing test or live draft flow relied on the gap:
every create-mode suite writes to a draft with no payslips.

**SC7 — the "group totals will leave this out" hint needs a group.** Gate any
consolidation warning on `pb.fx.group_for(company)`: on a single-company
tenant `presentation_currency` still answers and `rate()` still says
`known: False` for all seven foreign currencies, which would paint seven amber
lines on a screen where nothing is wrong.
