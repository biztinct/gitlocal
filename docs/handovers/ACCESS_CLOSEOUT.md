# ACCESS — closeout

Status: **COMPLETE 2026-09-02.** Six phases, nine commits, none pushed.
Read with `ACCESS_PROGRAM.md` (the vision, the owner rulings and the full A–F ledger).

---

## 1. What you got, in plain words

Before this programme, "who can do what" lived in three places and none of them
was readable: a board behind the Settings cog, two raw tables of permission-group
names, and an unused third-party app nobody had opened.

Now there is **one Access home**, and it answers the three questions people
actually ask:

| Lens | The question it answers |
|---|---|
| **Roles** | What does this role let somebody do, what does it open on the left menu, and who holds it? |
| **People** | What does *this person* have — drawn as the left menu they actually see — and why do they have it? |
| **Screens** | Who can see this entry on the left menu, and through which role? |
| **Hand-overs** | Who is covering for whom, until when, and what exactly was lent? |

Plus a **role builder** that shows the outcome while you build it, and a
**"See it as…"** picker in the header that repaints every lens as somebody
else's reality without changing anything.

**No permission-group name appears anywhere on it.** A role is a name, one
honest sentence, and a list of things somebody will be able to *do*.

---

## 2. What to press to see it

1. Sign in to **payobook.com**.
2. Left menu → **Settings** → **Access & delegation**.
3. You land on the **Roles** lens. Click any card to open it out into three
   columns: what it opens, what it lets them do, who holds it.
4. The four tabs under the numbers switch lenses. **Screens** is the left menu
   drawn as the left menu, and it is the only place a gate is edited.
5. **New role** (top right) opens the builder. Tick things; the miniature menu
   beside you lights up, and a line tells you how what you are building differs
   from a role that already exists.
6. **Hand my access over** is for everybody, not just administrators — it is
   what somebody presses the day before they go on leave.
7. `⌘K` finds all of it by name ("Access", "Roles", "The left menu",
   "Hand my access to somebody", "Access history").

---

## 3. What shipped, phase by phase

| Phase | What it delivered | Commit |
|---|---|---|
| **P1** | A role became a **bundle of plain-English abilities** rather than one raw permission. 35 abilities seeded, 23 roles rebuilt on top, migration invisible on the board. The permanent tripwire (Rail B) that fails if any seeded ability can ever reach the system-administrator permission. | `a347407a` |
| **P2** | The **Access home**: a lens bar, role cards that open out into the three questions, and the **role builder** with a live miniature of the left menu. | `b83ecf42` |
| **P3** | The **People lens** — a person's passport, their left menu drawn as they see it, every role and the reason they hold it — and the **"See it as…"** spectacles. | `86cafc69` |
| **P4** | The **Screens lens**, and the live re-gate: the left menu drawn as itself with its gates on it, editable as roles. 7 entries gated, 28 role links, proven to take a door from nobody. | `2f7a7a4a` |
| **P5** | **Tenant rails.** Developer mode blocked server-side for anyone but the platform administrator; the Settings hub split so platform-only cards fail *closed*; the **Tenant administrator** role bundle; the demotion switch, built and left unfired. | `f53d9d2e`, `cc58cf34` |
| **P6** | **The generic split** (`biz_access` + the Payobook overlay), the **retirement of the third-party access app**, and the debt sweep. | `3d43001b`, `d68ed290`, `4457756c` |

**All nine commits are on branch `19.1` and NONE has been pushed** (owner
decision — see §7).

---

## 4. P6 in detail

### 4.1 The generic split

`biz_access` is now a product-agnostic module: the models, the facade, the home,
the role lane on the left menu, the two hand-over mails, the revert job and the
Rail B harness. `pb_vendor_access` keeps the vendor register and became the
**Payobook overlay**: the whole seeded catalogue, the area vocabulary, the
screen-gate map and the Tenant administrator bundle.

Nothing changed in the browser. Model `_name`s, client-action tags, RPC shapes
and CSS class names are all untouched — deliberately: renaming them buys nothing
and risks everything.

**Three soft registration points** replaced three hard-coded lists:

| Registration | Replaces | Called from |
|---|---|---|
| `register_areas([...], default=…)` | the five Payobook areas hard-coded in the model's Selection | `pb_vendor_access/models/vendor_common.py` |
| `register_manager_groups(…)` / `registerAccessManagerGroups(…)` | `pb_lifecycle.group_lifecycle_admin` written into the facade and the palette | the overlay, server **and** browser |
| `register_catalogue(fn)` | the seeded catalogue imported by the generic layer | `pb_vendor_access/hooks.py` |

**How the external ids moved.** Every record that changed owner already existed
on four databases marked as belonging to the old module. Left alone, the install
would have created a *second* access-team permission with nobody in it and then
swept the real one away as stale. The re-homing is therefore a `pre_init_hook`,
which is the only moment that can do it: it fires on INSTALL, before the models
are reflected and before a single data file is read (a migration script only runs
on an UPGRADE — far too late). It moves 28 named records, the model/field/
constraint ids of the four moved models, the one field this module adds to
somebody else's model, and the six relation tables an uninstall would drop. It is
a no-op on a database that never had the old module.

**Proof it was invisible.** `get_board`, `composer_options`, `screens_board`,
`people`, `passport`, `user_options`, `role_detail` (×22), the whole catalogue,
every rail gate and every user's permission list were captured on a clone of the
live database before and after. **Every one is identical** except a single string
that nothing renders — the frozen legacy `group` label, whose permission-group
category is now "Access" rather than "Vendors and Access".

### 4.2 The retirement

`access_roles` (Cybrosys) was installed on all four databases and used by nobody.
It was not harmless: applying one of its roles **hard-sets** a user's permissions
(wiping everything held outside the role), its own ACL granted every internal
user full create/write/delete on the two models that decide who can do what, and
it rebuilt a view on every registry load.

**Final check before anything was removed** (all four databases):

| | payobook | template | abm | acme |
|---|---|---|---|---|
| `role.management` rows | 0 | 0 | 0 | 0 |
| `access.role` rows | 1 ("Payroll", 36 permissions) | 0 | 0 | 0 |
| users with a role set | 2 | 0 | 0 | 0 |
| menu hides / injected domains | none | none | none | none |

**Backups first.** `/var/backups/access_p6/<db>_pre_access_roles_uninstall_20260902T043739Z.dump`
for all four, each verified readable with `pg_restore -l` (19 725–22 100 objects).

**What the uninstall did**, measured before and after on each database: 23 tables
dropped, the `res_users.access_role_id` column dropped, **0** external ids left,
no view, cron, menu or model orphaned, and the 4 leftover registry-signature
settings rows deleted by hand. Two permission groups disappeared — its own two —
and **nobody lost an effective permission that was not one of them**.

**Boot time on live payobook:** 7.45 s → 6.66 s wall clock (best of three);
registry load 5.60 s → 5.14 s. A small delta on purpose: the expensive part of
this module had already been gated behind a signature check months ago.

The module directory is gone from the repository and from the server.

### 4.3 The debt sweep

| Debt | Outcome |
|---|---|
| Composer "differences vs role X" (P2 deferral) | **BUILT.** The builder now says *"Next to Payroll manager: this also lets somebody Read the audit trail"*, or warns in amber *"This is exactly Payroll manager again"*. Derived entirely in the browser from what the builder already read — no new call, no new shape. |
| C6 — sidebar data-assertion failure on the template | **FIXED.** The import claim moved to the Pay Run hub, which the template does not ship; the test now skips where that entry does not exist and asserts exactly as before where it does. |
| D9 — pb_learn anchor-registry failure | **FIXED.** Five anchors laid in the pay-run wizard by a later phase were never registered. Added as `reserved`, the registry's own word for "laid ahead of its content". |
| Section create / rename / move in the Screens lens (P4 deferral) | **DEBT.** Not small: three new server methods, write access on the section model, a dialog, drag-between-sections and its tests. Sections are still edited on the plain table behind Settings → Navigation. |
| Audit residue (B9 / C7 / E8) | **LEFT, by design.** See §6. |

---

## 5. Verification

**Deploy — module trees byte-identical repo ↔ server** (skipping `__pycache__`,
`*.pyc`, `.DS_Store`):

| Module | sha256 (both sides) | files |
|---|---|---|
| `biz_access` | `6a903296cb7379ce…` | 27 |
| `pb_vendor_access` | `0bec32c70e5532bb…` | 28 |
| `pb_sidebar` | `37c082d92a90f314…` | 20 |
| `pb_learn` | `3938fb5560e3a899…` | 70 |

**Versions vs manifests, per database:**

| Module | payobook | payobook_template | abm | acme |
|---|---|---|---|---|
| `biz_access` 19.0.1.0.0 | installed ✓ | installed ✓ | not installed | not installed |
| `pb_vendor_access` 19.0.1.6.0 | installed ✓ | installed ✓ | not installed | not installed |
| `pb_sidebar` 19.0.3.1.0 | ✓ | ✓ | ✓ | ✓ |
| `pb_settings` 19.0.1.6.0 | ✓ | ✓ | ✓ | not installed |
| `access_roles` | **uninstalled** | **uninstalled** | **uninstalled** | **uninstalled** |

Asset ritual (ledger B5) applied to all four: `/web/assets/%` attachments purged
(77 / 74 / 74 / 74) **and** `web.assets.version` bumped.

**Tests.** On a clone of live payobook: **517 tests, 0 failed, 0 errors**
(biz_access 152, pb_vendor_access 89, pb_learn 288, pb_sidebar 48, pb_settings 40,
pb_tenants 22). On a clone of the template with the final code: **494/499** —
biz_access 152/152, pb_vendor_access 89/89, pb_sidebar 48/48, pb_settings 40/40,
and 5 pre-existing pb_learn failures that are module-set drift on the template and
were failing before this phase.

**The generic-reusability proof.** `biz_access` was installed *alone*, with no
product overlay, on a clone of a tenant that has never had `pb_vendor_access`.
It boots to a working, empty, product-neutral Access home: "No roles have been
written down yet", 0 roles, 0 abilities, all four lenses answering, and the
Screens lens drawing that database's own left menu. Screenshots:
`docs/handovers/access_p6_shots/T2_generic_empty_home.png`,
`T2_generic_screens_lens.png`.

**The live tour**, on payobook after the split — Roles lens, a card opened out,
People passport, Screens lens, the builder with the new comparison line, a role
**granted** and a hand-over **created**, then both put back so the live state is
exactly as it was. Screenshots: `T7_live_roles.png`, `T7_live_role_expanded.png`,
`T7_live_people.png`, `T7_live_screens.png`, `T7_composer_same.png`,
`T7_composer_diff.png`, `T7_grant_dialog.png`, `T7_grant_done.png`,
`T7_handover_dialog.png`, `T7_handover_done.png`.

**Copy audit.** Every string that moved into the generic module was checked, and
four that named the product were rewritten ("a full login", "inside this
application", and the two hand-over sentences). There is now a test that reads
the source of every model, template and browser file in `biz_access` and fails if
a product name appears in user-facing copy.

---

## 6. Owner debts, carried forward

| # | Debt | Why it matters |
|---|---|---|
| **D1** | **The Access home is on payobook and the golden template only.** `abm` and `acme` do not have it. New tenants cloned from the template get it; the two existing ones need it installed. *Product decision.* | Those two customers cannot see roles in plain English yet. |
| **D2** | **`pb_settings` is not installed on `acme`**, so the server-side Settings split (Rail C) is absent there. | Part of the same decision as D1. |
| **D3** | **A brand-new database cannot be built from this repository.** Found while proving the generic module stands alone. Three separate pre-existing breakages, none of them this programme's: `hr_contract` ships *real* data pointing at a *demo* record; `om_hr_payroll` needs `report_xlsx` without declaring it; and `om_hr_payroll` references `pb_hr_flow.action_hr_flow_wizard`, a module that depends on it — a loop no fresh install can resolve. | This blocks reusing the Access home in another application, which was the reason for splitting it. Worth its own small phase. |
| **D4** | **The generic module still depends on the Payobook chassis** (`pb_settings`, `pb_sidebar`, `pb_hub`, `pb_import_kit`), and `pb_settings` drags the whole payroll stack in. | Same goal as D3: to lift `biz_access` into another product, the chassis has to stop being payroll-shaped. |
| **D5** | **Section create / rename / move** is still only on the plain table behind Settings → Navigation. | Small gap in an otherwise complete lens. |
| **D6** | **Two payroll permission ladders** still exist side by side and neither implies the other. Abilities cover both; nothing unifies them. | Carried from P1. |
| **D7** | **Country "Enabled" toggles, growth-plan AI, demo and driver groups** are still outside the ability catalogue. | Carried from P1. |
| **D8** | **Only two accounts hold "Access team" on payobook**, so everybody else sees Settings as a locked teaser. Granting it is two clicks in the People lens. | Deliberate from P4; flagged because it surprises people. |
| **D9** | **5 pb_learn test failures on the golden template** (stations and a cron pointing at cockpits the template does not ship). Pre-existing. | Not this programme's; recorded so nobody re-discovers it. |
| **D10** | **A stray empty database `Payobook19v2`** is still on the cluster from the rename, and something probes it every minute and logs an error. | Cosmetic, but it fills the log. |

### Residue (by design, cosmetic)

The audit trail has **no delete button, for anybody** — that is the point of it.
So the validation rows from P2, P3, RIZE P6 and this phase's live tour stay:
a granted-and-taken-back "Recognition", one created-and-revoked hand-over, and
the throwaway accounts `p5.tenantadmin@` / `p5.systemadmin@` (archived) and the
"IG-C1 validation (temporary)" account. Nothing hands out a permission.

---

## 7. Decisions only you can make

1. **Push, or not.** 74 commits sit unpushed on `19.1`, nine of them this
   programme's. Everything is live on the server; the repository history is the
   only thing waiting.
2. **The tenant flip.** New tenants get the restricted administrator by default.
   The two existing ones (`abm`, `acme`) are untouched until you say so. How to
   run it, from the platform database:

   ```
   env['pb.tenants'].apply_tenant_admin_rails('acme', dry_run=True)
   ```

   Dry run first — it prints exactly what it would change. It **refuses** the
   platform database, the golden template, protected logins (your own address —
   on `abm` that *is* the customer's administrator), and any database without the
   Access home. Rehearsed on a clone of `acme`; the real ones are untouched, and
   proven so: payobook's 326 user-permission links are byte-identical and no
   administrator's record moved.
3. **Installing the Access home on `abm` and `acme`** (debts D1/D2) — same
   conversation as the flip.
4. **Company rename** (E7). Companies & Tenants stays platform-only, so a tenant's
   administrator cannot rename their own company. Revisit if a customer asks.

---

## 8. How to check any of this yourself

- **Live:** payobook.com → Settings → Access & delegation.
- **Backups before the retirement:** `/var/backups/access_p6/` on the server.
- **The design record:** the prototype the owner chose Option A from —
  https://claude.ai/code/artifact/fdd1a0ca-d731-4481-ac8f-4492bff0953c — still
  matches what shipped: one home, three lenses, a builder and the "See it as…"
  picker. No code references it; it stays as the record of the decision.
- **The engineering detail:** `ACCESS_PROGRAM.md` (ledger A1–F12) and the six
  phase handovers beside it.
