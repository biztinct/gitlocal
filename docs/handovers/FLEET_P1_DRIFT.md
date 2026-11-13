# FLEET P1 — Drift, update, and the release stamp

Program doc: `docs/handovers/FLEET_PROGRAM.md` (READ FIRST: rulings, verified plumbing, rails,
design bar, ledger). Strategy source: `docs/SAAS_RELEASE_STRATEGY.html` gaps 3 and 4.
Runbook: `docs/SAAS_RUNBOOK.md` ("Bringing a tenant DB up to the apex's module set" is the manual
procedure this phase turns into a button).

## What this phase makes true (plain words, the owner will read the report)

1. The "In step with master" screen tells the truth: a customer that has a part of the product at an
   older version than the master shows as **behind**, with the version it has and the version it
   should have. Today it shows green.
2. One press brings a customer in step: refresh its list of available parts, install what is
   missing, **update what is stale**, re-read the access catalogue, and prove nothing was skipped.
3. The golden template sits on the same screen as a special row and can be brought in step the
   same way (it is 21 modules behind today; every new customer inherits that).
4. The master has a named **release** (cut from what the master runs right now), and every customer
   carries a stamp saying which release they are on. The fleet header says "Release 2026.09.03 —
   1 of 1 customers on it". That sentence is the hero moment.
5. A nightly check records drift per customer so tomorrow's screens (P2/P3) can act on it.

## Binding NON-goals

- No rings, no queued rollout job, no maintenance banner, no tenant-side module — P2.
- No alerts/emails — P3. P1 only RECORDS drift on the tenant record.
- No feature switches, plans, billing, suspend — P4/P5.
- No change to provisioning steps, backups, domains, certs, rails.
- Do not touch `pb_sidebar`, `pb_settings`, `pb_vendor_access` code. (Their VERSIONS on abm will
  move because you update them there — that is the point — but no source edits.)
- Do not drop `p9clone`. Do not touch `acme` (decommissioned).
- No "remove from a tenant what the master lacks" — taking away is never a sync (existing rule).

## Verified facts specific to this phase

- `ir_module_module` per DB: `name`, `state`, `latest_version` (the version INSTALLED in that DB,
  series-prefixed e.g. `19.0.1.7.0`), `installed_version` (computed from the manifest on disk —
  in the ORM only, not a column). Series prefix must be normalised (F1). Use
  `odoo.tools.parse_version` or an int-tuple after stripping a leading `19.0.`.
- Master read: ORM `self.env['ir.module.module'].sudo().search([('state','=','installed')])`
  reading `name`, `shortdesc`, `latest_version`, `installed_version`.
- Tenant read: `_installed_on(dbname)` at `service.py:1102` (raw SQL, names only) — extend to
  return `{name: latest_version}`.
- Install on tenant: `_sync_install` :1193 (`button_immediate_install` on `mods`, then a FRESH
  env for `pb.access.reseed_catalogue()` — F4). Upgrade = `button_immediate_upgrade` on the same
  model; it cascades to reverse dependencies (W120) — say so in the dry run.
- Refresh a tenant's list of available modules: `env['ir.module.module'].update_list()` inside
  `_tenant_env` (the runbook's step 1; NEVER `-u base`).
- "Skipped" detection after a registry rebuild: on the tenant env, compare the set of modules the
  registry actually loaded against installed names. Verify the attribute on the server copy
  (`sudo grep -n "_init_modules\|def load_modules\|loaded_modules" /odoo/odoo-server/odoo/orm/registry.py
  /odoo/odoo-server/odoo/modules/loading.py`) and use what exists; fall back to grepping the
  server log for `<db>.*some depends are not loaded` if the registry offers nothing. Whatever you
  pick, put the fact in the ledger (F7).
- Template crons: after installing on `payobook_template`, new crons the installed modules
  created are ACTIVE. Rail R8: disable every active cron on the template and append their ids to
  `pb_tenants.template_active_crons` (comma-separated ids; provisioning `_step_configure` :725
  re-enables from it and blanks it on the clone). Decision as a pure function (T6).
- Today's numbers for your acceptance checks: master 224 installed; abm 220 installed, 2 stale
  (`pb_settings`, `pb_vendor_access` 19.0.1.6.0 → 19.0.1.7.0), 0 missing (its 4 missing are the
  never-list); template 203 installed, 21 behind (some of those 21 are the never-list — your dry
  run says how many are real).
- `pb.tenant` has no release/drift fields yet. `pb.tenants._cron_health` :1646 is the precedent
  for a per-tenant cron loop with `self.env.cr.commit()` per tenant.

## Architecture

### 1. Pure decisions (new file `pb_tenants/models/sync_rules.py`, imported by service.py)

- `norm_version(v) -> tuple[int, ...]` — strips a leading series prefix (`19.0.`) if the string has
  ≥ 5 dotted parts, then int-tuples; non-numeric parts compare as 0. `'19.0.1.7.0' == '1.7.0'`.
- `sync_diff(master: dict[name, ver], tenant: dict[name, ver]) -> dict` with keys
  `to_install` (sorted names), `to_update` (list of `{module, have, want}`), `held_back` (sorted
  names, never-list — from BOTH lists), `ahead` (tenant newer than master — reported, never
  touched). Keep `sync_split` as a thin wrapper over `sync_diff` so its tests still pass, or update
  them — your call, say which.
- `release_state(snapshot: dict, tenant: dict, never: set) -> 'on' | 'behind' | 'none'` — `on` when
  every module in the snapshot outside the never-list is present on the tenant at ≥ that version;
  `none` when the tenant has fewer than half of them (a database that has never been synced);
  otherwise `behind`.
- `master_behind_files(rows: list[(name, latest_version, installed_version)]) -> list[name]` — the
  master's own modules whose installed DB version is older than the manifest on disk. Non-empty
  means "upgrade the master first" (rail R3) and BLOCKS cutting a release and updating tenants.
- `release_name(today: date, existing: list[str]) -> str` — `2026.09.03`, then `2026.09.03-2`, …
- `template_cron_plan(active_ids: list[int], recorded: str) -> (to_disable: list[int], new_param: str)`
  — every active id not already recorded gets disabled and appended, order preserved, no dupes.

### 2. Models (`pb_tenants/models/tenant.py` + new `release.py`)

- `pb.release`: `name` (Char, required, unique), `captured_at` (Datetime), `notes` (Text — "what
  changed", optional, plain English, shown to tenants in P2), `snapshot` (Json/Text of
  `{name: version}` for every installed module on the master at cut time, never-list included so
  the reader sees the whole master), `module_count` (Integer), `is_current` (Boolean — exactly one
  true; cutting a new one clears the others), `cut_by` (M2o res.users). ACL `base.group_system`.
- `pb.tenant` gains: `release_id` (M2o pb.release), `release_state` (Selection on/behind/none/
  unknown, default unknown), `behind_count`, `stale_count`, `skipped_count` (Integers),
  `drift_checked` (Datetime), `last_sync_at` (Datetime), `last_sync_result` (Text JSON of the last
  plan+outcome, for the detail screen).

### 3. Facade (`service.py`)

- `_installed_on(db)` → `{name: latest_version}`. Add `_master_modules()` → dict of
  `name → {'label', 'have': latest_version, 'file': installed_version}`.
- `_target_versions()` → the version dict tenants are measured against: the CURRENT release
  snapshot if one exists, else the live master (with `report['no_release'] = True`).
- `sync_report()` → per tenant AND a `template` row (`slug = payobook_template`, name "Golden
  template", flagged `is_template: True`): `to_install`, `to_update`, `held_back`, `ahead`,
  `in_step`, counts; plus top-level `release` (current name/date/count or null),
  `master_behind_files` (list; when non-empty the screen shows the red "Upgrade the master first"
  card and disables Cut/Bring-in-step), `master_ahead_of_release` (count of master modules newer
  than the snapshot → amber "master has moved past the current release").
- `sync_bring_in_step(tenant_id | 'template', dry_run=True)` → the unit, in this order, each step a
  log line in the returned `plan['log']` and in `provision_log` via `_log_line` (step key `sync`):
  1. refuse: master DB itself; decommissioned; `master_behind_files` non-empty; never-list re-check
     on the literal lists (third guard, as today).
  2. `update_list()` on the target (fresh env).
  3. install `to_install` (fresh env), 4. upgrade `to_update` (fresh env), 5. reseed access catalogue
     (fresh env, as today), 6. skipped check (fresh env), 7. for the template: `template_cron_plan`
     → disable + write param (fresh env), 8. re-read versions, compute `release_state`, write the
     tenant fields (`last_sync_at`, `last_sync_result`, counts, `release_id` = current when state is
     `on`), 9. for a tenant: `_refresh_one(t)` so health is current.
  Dry run returns the same `plan` with `dry_run: True` and nothing written anywhere. Keep
  `sync_install` working (wrapper that calls the unit with installs only) — nothing else calls it
  but the old tests may.
- `release_cut(notes='')` → refuses when `master_behind_files`; writes `pb.release`, clears
  `is_current` on others, recomputes every live tenant's `release_state` (read-only on tenants),
  returns the new report.
- `_cron_drift()` daily 02:30 (`data/cron.xml`, `noupdate="1"` — so ADD a new record, do not edit
  the existing ones): per live tenant + template, recompute counts/`release_state`, write
  `drift_checked`, commit per tenant. Read-only on tenants (rail R1).

### 4. Screen (`tenants.js`, `tenants.xml`, `tenants.scss`)

**Hero moment:** the Sync screen opens on a release banner — "Release 2026.09.03 · cut Tuesday
14:02 · 224 parts — 1 of 1 customers on it" with a soft progress ring; when no release exists, the
banner is the invitation: "No release has been cut yet. You are comparing against the master as
it is right now — cut one so every customer aims at the same target." with the Cut button inline.

- Fleet head: "In step with master" button gets a count chip (behind + stale across the fleet)
  when non-zero; each fleet card shows a release chip (`on` green "2026.09.03", `behind` amber
  "behind 2026.09.03", `none`/`unknown` muted "no release").
- Sync table: Customer · Release · Status · Has · To install · To update · actions. The
  template row is first, visually distinct (eyebrow "Every new customer starts here"). Row detail
  expands into four columns: Install / Update (have → want per module, the version delta in
  tabular numerals) / Never here (with reasons, as today) / Ahead (muted, "newer than the master —
  left alone"). "Show the detail" toggles remain.
- "Bring in step" button → confirmation dialog listing "N to install, M to update (and anything
  that depends on them), then a check that nothing was skipped" and, for the template, "and the
  template's scheduled jobs will be switched off again afterwards". Progress: the button shows the
  step names as they happen (the RPC is one call — show a stepper that ticks on an estimated
  cadence and snaps to the result; be honest in the copy: "This takes a minute or two").
- Result panel (animates in): installed / updated / skipped (red, with "what to do": "Open the
  server log for `<db>.*some depends are not loaded`") / catalogue re-read / release stamp.
- "Upgrade the master first" card (red) when `master_behind_files`: lists the modules and the
  exact command (`-u <mods> -d payobook`) — this is the one place a command is allowed on screen,
  because the only reader is the platform owner and there is no button that can do it from inside
  the running server.
- "Cut a release" card: notes textarea ("What changed, in a sentence or two — customers will read
  this in a later phase"), Cut button; when the master has moved past the current release, an amber
  line says so with the count.
- Detail → Overview: "Release" row (chip + last in-step check time) and a "Last sync" row that
  opens the stored `last_sync_result` in a slide-over (reuse the kit drawer if pb_import_kit has
  one; otherwise a `pbim-card` toggle). Zero dead-ends: every empty/error state has a sentence and
  a next step.
- Keyboard: `r` re-checks, `Esc` closes detail/expanded row. New glyphs in `TIC`.

### 5. Tests (numbered; commit WITH the feature)

- **T1** `norm_version`: prefix stripped only with ≥ 5 parts; `'19.0.1.7.0' == '1.7.0'`;
  `'1.10.0' > '1.9.0'`; `'19.0.1.7.0-rc1'` does not crash.
- **T2** `sync_diff`: install / update / held (both lists) / ahead; a never-listed module present
  on the master and stale on a tenant is `held_back`, not `to_update`.
- **T3** `release_state`: on / behind / none / never-list ignored / tenant newer still `on`.
- **T4** `master_behind_files` with equal-after-normalisation rows → empty.
- **T5** `release_name` suffixing; **T6** `template_cron_plan` (no dupes, order, empty param).
- **T7** `test_tenant_sync.py` existing assertions still pass (or are updated and say why).
- **T8** `release_cut` refuses when the master is behind its files (monkeypatch
  `_master_modules`); creates the record; only one `is_current`.
- **T9** `sync_bring_in_step(<master db>)` refuses; dry run on a non-existent DB names it.

### 6. Live validation (report with evidence)

- **L1** Deploy `pb_tenants` to the master only; `-u pb_tenants -d payobook`; asset ritual; tests
  green (`--test-tags /pb_tenants`, scoped `-u`, side port).
- **L2** Sync screen on abm shows **2 to update, 0 to install**; template shows its real numbers
  after the never-list; master-behind-files is EMPTY (if not, STOP and report — that is a real
  finding and the owner decides).
- **L3** Rehearsal (rail R4): restore abm to `abm-staging` from its latest backup (cockpit →
  Backups → Restore to staging), run Bring-in-step on the staging DB by calling the facade with
  the staging name (add `dry_run=False` support for a `-staging` slug in the facade for exactly
  this use — refuse any other non-tenant name), verify 0 stale, 0 skipped, cron window clean.
  Drop staging afterwards.
- **L4** Real: Bring abm in step. After: abm 0 stale / 0 skipped; `pb_settings`,
  `pb_vendor_access` at 19.0.1.7.0; 15-minute cron window with zero `ERROR abm` lines; the access
  home on abm opens.
- **L5** Template: `pg_dump` the template first (`/odoo/backups/tenants/_template/<date>.dump`),
  dry run, then Bring-in-step; verify installed count, ALL crons inactive afterwards, param
  extended, registry loads clean. Prove the template still provisions: NOT required in P1 (no
  new tenant is created) — say so in the report as a known un-run check.
- **L6** Cut release "2026.09.03" with a note. abm stamps `on`; fleet card chips; banner sentence.
- **L7** Chrome-MCP walkthrough: every state (no release, release, behind, in step, master behind
  files — simulate the last by monkeypatching in a shell or by temporarily returning a fake in a
  dry-run flag, then remove), the dialog, the result panel, keyboard shortcuts. Screenshots to
  `docs/handovers/fleet_p1_shots/`.

## Design (verbatim bar)

"Extreme WOW, intuitive, out-of-this-world experience, best in class." Hero moment named above.
Zero dead-ends. Plain language (say "part of the product", "version", "behind", "in step", "release";
never "module registry", "latest_version", "cascade"). Motion with purpose (banner ring, result
panel enter, stepper ticks). Keyboard ergonomics as listed. Measured against Vercel's deployments
list and Linear's release notes, not stock Odoo. No "Odoo" in any user-visible string.

## Deploy + verify

Repo `CLAUDE.md` deploy contract is authoritative (clean staging dir, per-module scoped rsync,
never `--delete` into the addons dir, one addons dir). Master only for `pb_tenants`. Asset purge +
`web.assets.version` bump on `payobook`. Hash parity repo↔server for `pb_tenants`. Manifest
version bump to 19.0.1.5.0.

## Report back

1. The diff-decision functions and their tests (counts, pass/fail output).
2. L2 numbers before; L4/L5 numbers after; the skipped-check mechanism you used (ledger F7).
3. Rehearsal (L3) outcome, including anything the clone caught.
4. Release cut evidence; fleet chips; screenshots.
5. Self-score against the design bar, honestly, with what you would do with one more day.
6. Anything you chose beyond the spec; anything left out and why.
7. New ledger entries appended to `docs/handovers/FLEET_PROGRAM.md` (F7+).
8. Commits (feature-scoped, module files + docs only, Claude co-author line, **not pushed**).
