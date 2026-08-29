# RECORDS — conventions + gotcha ledger

**Program (started 2026-08-29):** one-time pay data + the Records Desk (bulk update · export ·
import) over the pay scheme's MAPPED record fields. Owner-approved brief:
`~/.claude/plans/i-want-you-to-peaceful-popcorn.md`. Phases: **R1** "This run only" pay data ·
**R2** Records Desk (grid, filters, apply/undo, People door) · **R3** export/import round trip +
remaining doors · **R4** (conditional) defect round + close-out.

Module versions at program start: **pb_hr_payroll_formula 19.0.1.100.0 · pb_payrun_wizard
19.0.1.13.0 · pb_import_batch 19.0.2.0.0 · pb_formula_studio (see manifest) · pb_people (see
manifest)**. `om_hr_payroll` stays untouched (CR1).

**`C18` (docs/FORMULA_ENGINE_CONVENTIONS.md), `MJ1–MJ52`, `S1–S20`, `CR1–CR33`, `MF1–MF41` STILL
BIND.** This file adds `RD`-numbered entries and restates only the rules that are load-bearing
every single time.

---

## Standing rules (bind every phase)

- **The design bar is binding and is scored in every phase report** (C18.145): *extreme WOW,
  intuitive, out-of-this-world, best in class* — a named hero moment; zero dead-ends (empty,
  loading, error, partial, huge states all designed; every failure names its reason and its next
  step); plain language over code vocabulary; motion with purpose; keyboard + bulk ergonomics
  where rows are involved; measured against the best SaaS tool in the category, not stock Odoo.
  Lucide/SVG icons, never emoji.
- **White-label absolute.** No user-visible string may contain "Odoo" — labels, chips, tooltips,
  help text, placeholders, empty states, error/toast messages, menu and action names, field
  `string=`/`help=`, selection labels, reports, exported files, `.po` msgstr. Use **Payobook** or a
  neutral term. Never rewrite technical identifiers (`from odoo import`, model/XML ids, `odoo-bin`,
  addon names, log messages, code comments, engineering docs including this one).
- **Neutrality rail on every phase that touches the batch.** A normal (non-one-time) batch must
  produce byte-identical `formula_input_values` before and after; prove it with an md5 in the
  test AND a "branch never entered" counter (S3/J9 pattern, `_sourcing_*_counter` precedent in
  `payroll_import_batch.py`).
- **Never call `action_process` in a test against live data.** Writeback code is exercised on
  records the transaction created (J3/J10 rule).
- **Terse output.** One-line bash where possible; never dump file contents into the chat.
- **Commit per phase**, explicit file staging (never `git add .` — `ABM/*.xlsx` are the owner's
  working files and stay unstaged), reviewer-focused message, **do not push**.
- **Asset cache.** Any JS / SCSS / OWL-XML change ⇒ bump that module's manifest version and `-u`
  it; a manifest `assets` list change needs a full service RESTART (C18.53); SCSS errors surface
  only at page load (MF12). Clear `/web/assets/%` per DB after JS/SCSS changes.
- **Deploy contract** (CLAUDE.md): ONE addons dir `/odoo/odoo-server/addons`; clean staging dir
  first; per-module `rsync --delete` scoped to the module dir, NEVER to the addons root. Deploy
  **abm first**, validate there, then **payobook + payobook_template**. **acme is excluded**
  (owner ruling 2026-08-26). Verify tree hashes AND `ir_module_module.latest_version` per DB.
- **Tests run scoped**: `-u <mods> --test-enable --test-tags /<mod>,/<mod> --stop-after-init`
  (C18.40), backgrounded, poll the log, kill by PID (C18.54). Take the baseline yourself first
  (MJ11); 3 pre-existing reds are known (`TestBankDestinations.test_09`,
  `TestEndpointFieldCatalogue.test_05c`, pb_integrations `TestLedgers.test_the_ledgers_never_sudo`).
- **Live validation uses abm.** Login ash@biztinct.com / J5validate!2026 (verify first; the
  documented apex password does not authenticate over RPC — CR33 — so drive live checks through
  the authenticated Chrome-MCP session, `fetch('/web/dataset/call_kw', …)` from inside the page).
- **Plain English on every surface** — the screen's vocabulary, not the code's.

## RD ledger

(Entries added by each phase report. Numbering continues across phases.)

### R1 (2026-08-29)

1. **`hr.contract.create` already gives a new contract one advantage line per EXISTING
   template** (`om_hr_payroll/models/hr_contract.py:107-113`). A fixture that creates the
   template and then creates its OWN `hr.contract.advantage` line ends up with TWO lines for
   one code; `_get_contract_advantage_map` keys by code and the reader silently picks one of
   them. Create the template FIRST, create the contract, then WRITE the amount onto the line
   the contract already has. (Cost one red test on the first live run.)
2. **The baseline md5 has to be taken with the SAME test file, on the pre-change checkout.**
   The R1 test imports `ONE_TIME_NO_EMPLOYEE` from the model, which does not exist at HEAD, so
   the file cannot simply be run there. The working recipe: generate a *probe* copy (strip the
   import, keep only the neutrality case, log the md5 with `_logger`, never `print` — stdout
   goes to `/dev/null` when odoo-bin is backgrounded with `--logfile`), drop it into the
   server's `tests/` with one appended `from . import …` line, take the baseline run, then
   restore `tests/__init__.py` from the backup and delete the probe. Recorded md5 for R1:
   `78b40cab23740f61b20629a9be9fd4df`.
3. **Never `pkill`/`pgrep -f` a pattern that appears in your own remote command line.**
   `ssh host 'pkill -f stop-after-init'` matches the remote shell running that very command and
   kills the ssh session: the symptom is a bare `Exit code 255` with nothing done. Capture the
   PID in a separate call and `kill -9 <pid>` (C18.54 with the extra clause).
4. **`odoo-bin -u` refuses more than one database**: `-d payobook,payobook_template -u …` exits
   2 with "Cannot use -i/--init or -u/--update with multiple databases". One `-u` run per DB.
   Worse, when the invocation is backgrounded with `nohup … &` the failure is invisible — no
   logfile is ever created and the site stays DOWN. Run deploy upgrades through a **foreground**
   ssh (backgrounded on the *local* side) so the exit code and usage error come back.
5. **A `<odoo>` root element is not a white-label violation**, and neither is `✕` (U+2715, the
   close button) or `→`. A "no Odoo / no emoji" source assertion must strip the document element
   and XML comments first, and must define emoji as the pictograph planes + anything followed by
   U+FE0F + a named list — not "the whole symbol block". The broad version fails on the wizard's
   own close button and only teaches the next engineer to delete the assertion.
6. **On abm, a spreadsheet row matches an employee by `identification_id`/`barcode`, not by the
   source system's code.** Employees carry `pb_source_ref = '3:<zoho id>'` but an *excel* batch
   does not produce that ref (the config's `connector_id` is unset — the standing owner debt
   from JOURNEY), so a file keyed on the Zoho Employee Code matches nobody. In a one-time run
   that is *correct behaviour* and it lands as the R1 exception sentence; for live validation,
   key the file on `identification_id`.
7. **The pay-run wizard's employment-status panel ("Run for just a few people…") does not always
   render** — on one reload abm showed 42 eligible with the status chips, on the next 152 with
   no chips and no picker. Pre-existing (VALUEKIND P4 surface), unrelated to R1, but it means a
   UI-driven live validation can suddenly be about to compute the whole workforce. Drive
   `attach_spreadsheet` through `call_kw` on a run you created yourself when you need a
   one-person blast radius.
