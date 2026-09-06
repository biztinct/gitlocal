# ACCESS P8 — Bring AB Mauri into sync, and make tenant sync a standing rule

Read FIRST: `ACCESS_PROGRAM.md` (ledger A1-F6 binds), `ACCESS_CLOSEOUT.md`, and P7's report
(module/manifest changes may have landed — reconcile before deploying).

**abm is PRODUCTION**: 155 employees, 36 pay runs, 206 MB, one active internal user
(`ash@biztinct.com`, the owner). Treat every step as production work.

Design bar (verbatim, binding): **extreme WOW, intuitive, out-of-this-world, best in class**.
White-label rule: "Odoo" never in a user-visible string; plain English only.

## Owner decisions this phase implements (2026-09-02)

1. Install on `abm` everything the master has, **except** the platform cockpit, demo data and
   the public marketing site.
2. **Standing rule, owner's words**: *"From now on all tenant databases should get installed
   once master gets it, except anything related to the platform cockpit or anything which can
   interfere or be misused against the master tenant / platform functions."* This phase must
   turn that sentence into something durable, not a one-off install.

## Scope

### 1. The install list — 14 modules (verified missing from abm on 2026-09-02)

| Install | Why |
|---|---|
| `biz_access`, `pb_vendor_access` | the Access home |
| `pb_assets`, `pb_budget`, `pb_lifecycle` | its dependency chain + the lifecycle spine |
| `pb_onboarding`, `pb_offboarding`, `pb_probation`, `pb_pip`, `pb_rnr`, `pb_comp_ben`, `pb_contract_lifecycle` | the HR lifecycle family |
| `pb_zoho_bridge`, `pb_zoho_sso` | owner asked for both (they already run `pb_integrations`) |

**NEVER install on any tenant (the deny-list):**

| Excluded | Why |
|---|---|
| `pb_tenants` | the platform cockpit — it manages the whole fleet; inside a customer database it is a fleet-control surface in the wrong hands |
| `pb_demo`, `pb_demo_portal` | fake employees and demo journeys inside a real customer's payroll |
| `pb_website` | the public marketing site; a tenant is not the product's shop window |

Resolve the real dependency closure before running — the list above is what is *missing*; Odoo
will pull in anything else these need. **Report the full computed closure before installing**,
and stop if it drags in a deny-listed module (that would be a dependency bug worth reporting,
not something to force through).

### 2. The standing rule, made durable

- A single authoritative **deny-list constant** in `pb_tenants` (the platform cockpit is the
  right home — tenants never read it) with the reason per entry in plain English, and a comment
  block quoting the owner's rule verbatim.
- A **drift report** in the Tenants cockpit: for each tenant, what the master has that the
  tenant does not, split into *"should be installed"* and *"never installed (and why)"*.
  Read-only reporting plus a clearly-labelled action to install the safe set for one tenant.
  Do NOT build silent automatic installation on master upgrade — a customer database must not
  gain modules without somebody pressing something. Say so in the UI copy.
- A short runbook section in the closeout: how the owner syncs a tenant, and what is never synced.

### 3. Post-install correctness on abm

- The P4 screen gates and the role catalogue land on abm through the install — verify they did
  (ledger A2: seeds ride migrations; check the gates actually applied, and run the second
  `-u pb_demo` pass rule **only if applicable** — pb_demo is deny-listed on abm, so the D4
  hazard does not apply; confirm that reasoning holds).
- **Before/after visibility diff for every abm user × every rail entry** (as P4 did on
  payobook). abm's only internal user holds the master key, so the expected answer is "nothing
  changes for anybody" — prove it rather than assume it.
- abm's payroll data must be untouched: 155 employees, 36 pay runs, contracts, and the
  Integrations/Zoho configuration all intact and byte-identical in count before/after.

## Binding NON-goals

- Do NOT run the tenant flip on abm. It correctly refuses today: abm's only administrator is
  the owner's protected login (proven by dry-run 2026-09-02, `applied: false`, reason "This
  login is on the protected list"). Nothing in this phase changes that.
- Do NOT create users on abm. Do NOT touch abm's company record (that is P9).
- Do NOT install anything on `payobook_template` in this phase.
- Do NOT push.

## Numbered test cases

1. **Backup first**: a verified `pg_dump` of abm exists BEFORE anything is installed
   (`pg_restore -l` confirms it is readable). Name it in the report.
2. **Rehearse on a clone of abm** end to end (ledger A8: drop it promptly). Capture the install
   exit code and every error; only proceed to live when the clone is clean.
3. Live install on abm: exit 0, registry loads, site healthy on abm's hostname.
4. Data integrity: employees/pay runs/contracts/partners counts identical before and after;
   the Integrations configuration still present; abm's owner login still works.
5. Visibility diff (every abm user × every rail entry) — produced, and any change explained.
6. The Access home works on abm: roles catalogue seeded, all three lenses open, the composer
   opens. Chrome MCP screenshots at 1440.
7. Drift report: shows abm as in-sync afterwards, shows the deny-list with reasons, and its
   install action is gated to the platform administrator only.
8. Suites: run on abm; compare the failure count against a pre-install baseline you capture
   yourself (do not inherit payobook's baseline — different module set).
9. Copy audit on all new user-visible strings.

## Deploy + verify

CLAUDE.md contract authoritative. ⚠ **F6: every `odoo-bin` run passes `--http-port` (free port)
or `--no-http`.** Asset ritual (purge + bump `web.assets.version`) on abm since new JS lands
there. Verify per DB: module tree hashes repo↔server, and `latest_version` vs manifest for
every module installed.

## Report back

1. The computed dependency closure actually installed (and anything unexpected in it).
2. Backup name + restore-listing proof; clone rehearsal outcome.
3. The before/after data-integrity table and the user × entry visibility diff.
4. Access-home-on-abm evidence (screenshots) and the drift report evidence.
5. Deploy verification per DB; suite counts vs your own baseline.
6. Anything you chose beyond the spec; anything left out and why.
7. Commits (feature-scoped, module files only, Claude co-author line, **not pushed**).
