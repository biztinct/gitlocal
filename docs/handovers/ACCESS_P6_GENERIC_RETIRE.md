# ACCESS P6 — Generic layer, Cybrosys retirement, closeout

STATUS: FINAL — P5 deltas appended at the bottom. Build on: pb_vendor_access 19.0.1.5.0,
pb_sidebar 19.0.3.1.0, pb_settings 19.0.1.6.0, biz_theme 19.0.1.5.0, pb_tenants 19.0.1.3.0
(commits a347407a, b83ecf42, 86cafc69, 2f7a7a4a, f53d9d2e, cc58cf34 — none pushed).

Read FIRST: `docs/handovers/ACCESS_PROGRAM.md` (rulings 2 + 3 are this phase's charter; the
FULL ledger A-E binds), then the P1-P5 handovers.

Design bar (verbatim, binding): **extreme WOW, intuitive, out-of-this-world, best in class**.
White-label rule (binding): "Odoo" never in a user-visible string; plain English only.

## Scope

1. **Generic/product split (owner ruling 3).** Split pb_vendor_access into:
   - **`biz_access`** (generic): the models (role profile, ability, delegation), facades,
     the Access home cockpit (all three lenses + composer + simulator), the pb_sidebar
     role-lane extension, Rail B test harness. Neutral strings only ("this product" never
     "Payobook"); NO seeded catalogue, NO area vocabulary beyond a neutral default; soft
     registration points for: ability/role catalogue, area labels, settings-category keys.
   - **`pb_vendor_access`** (Payobook overlay): keeps the vendors panel + the Payobook
     catalogue seeds (abilities, roles, screen gates, Tenant administrator bundle), area
     labels, and anything Payobook-specific. It depends on biz_access.
   Mechanics: this is a RENAME-heavy refactor on a live DB — models keep their `_name`s
   (pb.role.* etc. stay; renaming models buys nothing and risks everything — the generic
   module owns them under their existing names; note the pb_ prefix is cosmetic and
   acceptable, decide and defend if you disagree). Data (ir.model.data) must follow the
   moved definitions: plan the module split so xmlids move via a migration that re-homes
   `ir_model_data.module` for moved records — rehearse on a clone (ledger A8), prove zero
   orphaned xmlids and a byte-identical board after the split.
2. **Retire Cybrosys `access_roles` (owner ruling 2 — owner directed uninstall).**
   - Verify one final time on EVERY DB that nothing references it (models in use, users with
     access_role_id set, role.management records with menu hides/domains/restrictions that
     are actually doing something).
   - Take a DB backup per database FIRST (this is the phase's one destructive step).
   - Uninstall via the registry (proper module uninstall so its models/columns/views are
     removed cleanly), then delete the module directory from the repo + server.
   - The boot-time `_update_role_groups_view` cost and its registry-reload patches disappear
     with it — confirm boot time before/after and report the delta.
3. **Debt sweep** (each: fix, or record as explicit post-program owner debt with a sentence):
   - C6: the 2 pb_sidebar data-assertion failures on payobook_template.
   - D9-adjacent: pb_learn anchor-registry failure on live.
   - The audit-residue rows (B9/C7 class) — leave (by design), just list them.
   - Composer "differences vs role X" comparison (P2 deferral) — build it now if small
     (the diff of two roles' abilities/opens is derivable from existing RPCs), else debt.
   - Section create/edit in the Screens lens (P4 deferral) — assess cost; build or debt.
4. **Closeout**: write `docs/handovers/ACCESS_CLOSEOUT.md` — what shipped per phase, the
   full commit list (all unpushed), owner debts (incl. A9 tenant install state, the P5 flip
   switch + how to run it, the two payroll ladders, country toggles, uncovered groups),
   logins/how-to-verify, and the "what to press to see it" tour in plain English.
5. **Program memory + prototype note**: confirm the prototype artifact link and the Access
   home converge (the artifact stays as the design record; no code references it).

## Binding NON-goals

- Do NOT push any commits (owner decision, listed in closeout).
- Do NOT run the P5 existing-tenant flip (stays owner-triggered).
- Do NOT rename model `_name`s or break any RPC shape — the split is invisible to the browser.
- No new features beyond the two small debt items if they fit; no ladder unification.

## Numbered test cases

1. Post-split: full suite green on payobook; get_board()/passport()/screens_board() byte-
   identical before vs after the split (captured diff); zero orphaned ir_model_data rows;
   the board, composer, passport, Screens lens all work live (Chrome MCP pass).
2. A fresh install of biz_access alone on a scratch DB boots with an EMPTY, working Access
   home (neutral strings, no seeds) — the generic-reusability proof. Screenshot it.
3. pb_vendor_access on top restores the exact Payobook catalogue (count + spot checks).
4. Cybrosys gone: uninstall clean on every DB where it was installed (list them first);
   no orphaned columns/views/crons; boot-time delta reported; repo directory removed;
   backups taken and named in the report.
5. Debt items: each either green (with its test) or written down in the closeout.
6. Full 4-DB deploy verification table (hashes + latest_version per module per DB) +
   B5 asset ritual where JS moved.
7. Chrome MCP final tour: all three lenses + composer + a grant + a hand-over on live
   payobook, screenshots for the closeout.
8. Copy audit of every string that moved into biz_access: neutral, plain, no product name
   baked in (Payobook branding comes only from the overlay), no "Odoo".

## Deploy + verify + report

Same contract (CLAUDE.md; B5; D2/D4 rules if any gates move; ledger A8 clone hygiene —
the split rehearsal clone AND the uninstall rehearsal clone both dropped promptly).
Commits: split into logical units (split / retire / debts / closeout), no push.
Report: per-test evidence, the xmlid re-homing method, the uninstall verification per DB,
boot-time delta, the debt table as it landed in the closeout.

## P5 deltas (binding facts — see program ledger E1-E8)

- The split now covers MORE than pb_vendor_access: the Tenant administrator bundle seed and
  provisioning hooks are Payobook/platform-specific (stay in pb_vendor_access/pb_tenants);
  Rails A (biz_theme) and C (pb_settings resolve_gates) are ALREADY generic — leave them
  where they are, they are not part of the extraction.
- pb_vendor_access is now installed on payobook AND payobook_template (E4) — your split
  migration must be rehearsed against clones of BOTH (their catalogues differ: 35 vs
  template's smaller ability set where modules are missing).
- Seeding is create-only (E3) — the split migration must preserve that property.
- The template now has an active passwordless recovery admin (E5) — do not archive it.
- Rail C absent on acme (pb_settings not installed there) — record in the closeout's debt
  table; installing it there is part of the owner's flip decision (E6), not this phase.
- Closeout must include: the flip runbook (E6 verbatim: dry-run first, what it refuses),
  the open owner decisions (E6 flip timing, E7 company rename), the residue list
  (B9/C7/E8), and the remaining single template test failure (E4).
- Cybrosys final-check detail: also verify no res.users.access_role_id set anywhere and no
  role.management record with menu hides/domains actually active — on ALL 4 DBs, before
  uninstalling (it may only be installed on some; list where).
