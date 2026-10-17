# FLEET program — closeout (2026-09-04)

Status: **COMPLETE.** Six phases (P1, P2A, P2B, P3, P4, P5, P6) designed by Fable, built and
validated by Opus agents, all live on the platform. Source gap list: `docs/SAAS_RELEASE_STRATEGY.html`
("Shipping to the Fleet"). Program doc + ledger F1–F68: `docs/handovers/FLEET_PROGRAM.md`.
Read this file first in any future session on the platform.

## What is live (in the owner's words)

| Gap from the strategy doc | What the platform does now |
|---|---|
| 3 · Sync added but never updated | "In step with master" compares versions; one button installs AND updates, refreshes the list of parts first, proves nothing was skipped, and the golden template sits on the same screen |
| 4 · No version per customer | Releases are cut from the master; every customer carries a release stamp; the screen opens on "Release X — N of N databases are on it"; a nightly check keeps it honest |
| 9 · No customer communication | Every customer database has the Platform Link (`pb_tenancy`): a notice bar before/during updates, a release toast, Settings → About Payobook → What's new; the owner can send notices fleet-wide or per customer, optionally on the public status page |
| (Wave B) rollout | A release walks the fleet in waves: rehearsal on a restored copy → template → canary → early → everyone, each customer in their own night-time window and time zone, automatic notices, a worker with lock/retry/health gate, and Pause / Continue now / Retry / Skip / Abort |
| 5 · Nothing wakes a human | Alerts by email within 15 minutes, one per problem, reminders, a morning summary, an Alerts view, "Send a test email", the outgoing-mail check made real |
| 8 · Memory ceiling | "Room for N more customers" gauge, provisioning refuses at zero, `docs/SAAS_RESIZE_RUNBOOK.md` |
| 9 · Status page | `https://payobook.com/status` served by nginx from a file, no customer names, self-declared staleness |
| 6 · No feature switches | A 10-part catalogue, per-customer on/off (hide or lock) with a live menu preview and bulk columns; reaches the customer's screens within a minute |
| 7 · Plans, billing, suspend | Plans with all three price structures, trial / paused / pending-deletion states, nightly meter, preview-before-create invoices (PDF, email, mark paid), reminders, optional auto-suspend (OFF), seat limit, trial bar, customer "Plan & usage" card |
| 10 · Support access without a trail | "Open as support" with a required reason and a time box, a one-time link, a rose bar with countdown, every session written on the customer's side under Settings → About Payobook → Support access, with a switch to refuse support entirely |

Versions at closeout: `pb_tenants` 19.0.2.1.0 (master only), `pb_tenancy` 19.0.1.4.0 (master,
template, abm). Current release **2026.09.03-6** on all three databases. Tests at the last run: 454
green across the touched modules (517 at P5, the largest run). Commits: **51 unpushed on `19.1`.**

## Owner decisions open (nothing here is done without you)

1. ~~Push~~ **DONE 2026-09-04** — `19.1` pushed (52 commits).
2. ~~The validator account~~ **DONE 2026-09-04** — `igc1.validator` archived, password scrambled,
   login with the old password proven refused; one active system administrator remains.
3. ~~Static IP~~ **DONE 2026-09-04** — the owner attached a Lightsail static IP; the address is now
   **`3.104.113.197`** (was `3.25.57.42`), DNS `@`/`*` repointed at Mat Bao, ssh alias updated.
   Nothing on the box named the old address (nginx routes by `server_name`, the cockpit resolves the
   domain), so no server change was needed.
4. ~~Emails received?~~ **CONFIRMED by the owner 2026-09-04.**
5. **AB Mauri's plan** is **Enterprise** (Growth would bill ₫0 — all 36 payslips are drafts;
   Starter's 50-employee limit would lock a 153-employee customer). Confirm or change.
6. **Prices, VAT, bank details.** Seeded prices are placeholders (Starter 30,000 ₫/employee,
   Growth 25,000 ₫/payslip, Enterprise 6m/12m/30m ₫ by band); VAT 0 %; bank details, company
   address and tax number are blank until filled under Billing → Settings.
7. **Canary.** AB Mauri is the canary customer with a 22:00–01:00 Vietnam window. Say if not.
8. **Release notes visible to AB Mauri.** Releases 2026.09.03-2 … -6 carry validation notes readable
   under What's new (one says it was cut to prove a rollout stops safely). Cutting a fresh release
   with real notes puts yours on top.
9. **`p9clone`** (1.7 GB leftover clone from ACCESS P9) still sits on the box. Drop when no longer
   needed — it counts against disk and the capacity gauge.
10. **The three excluded gaps** remain: off-box backups (1), a proved restore drill (2), per-customer
    sandbox (11). Gap 1 is still the single most dangerous thing on the platform.

## Debts and things to know

- Auto-suspend for unpaid invoices ships OFF (Billing → Settings, red explanation).
- The status page reads "planned maintenance" during the 24 h canary watch after every rollout.
- A rollout's rehearsal restores the canary's latest backup to `<slug>-staging` and drops it; no
  backup + a live customer = refusal to start (rail R4 enforced).
- Support sessions: a browser that opened one remembers the recovery account on that customer's
  login picker (that browser only). One browser holds one session per customer.
- The tenant-side poll updates VISIBLE tabs only (F14); background tabs catch up on focus.
- Health-gate log ignore list `pb_tenants.health_ignore` (vendor_license_core noise, F25).
- The pre-existing ACCESS-stream working-tree changes (pb_settings company profile,
  pb_vendor_access migration) were left untouched and uncommitted by this program. The company
  profile screen nevertheless reached template + abm through the sync (it was on the master).
- Every phase's screenshots: `docs/handovers/fleet_p*_shots/`.
- Validation on live abm was limited to reversible actions (features flipped back on, notices
  cleared, sessions ended). Pausing, seat limits and trials ran on `abm-staging` only.

## How to keep working on it

Fable designs → Opus builds, one handover per phase, ledger appended, rails R1–R8 binding. If an
Opus subagent is shed by API overload repeatedly, spawn a FRESH one that resumes from the working
tree rather than re-sending to the old one (P4 lesson).
