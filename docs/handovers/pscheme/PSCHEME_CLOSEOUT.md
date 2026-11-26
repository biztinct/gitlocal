# PSCHEME — closeout ("the pay scheme belongs to the person")

Programme 26–27 Nov 2026 (P1, P2a, P2b, P3). Engineering document: real technical names; counts only — no client
names or figures. Ledger: `PSCHEME_LEDGER.md` (rulings R1–R10, decisions A1–A15, gotchas PS0–PS9, PS-a1..a9,
PS-b1..b8, PS-c1..c5). Phase reports: P1, P2a, P2b (on their branches, merged), P3.

## 1. What is live (all five: payobook, payobook_template, p0clone, rize, sudima; never abm)

Commit `209907ade` on `19.1`, released 26 Nov 2026 20:12–20:23 UTC (629 s down), eleven modules `-u` everywhere:
pb_scheme_map 19.0.2.8.0, pb_hr_payroll_formula 19.0.1.176.0, pb_contracts 19.0.1.17.0, pb_import_batch 19.0.2.2.3,
pb_import_wizard 19.0.1.4.2, pb_job_change 19.0.1.1.0, pb_new_hire 19.0.1.8.1, pb_pay_package 19.0.1.1.1,
pb_payrun_wizard 19.0.1.49.0, pb_updates 19.0.1.9.0, pb_learn 19.0.20.11.0. One new daily job
(`pb_scheme_map.cron_person_scheme_boundaries`).

On screen: each person can have their own pay scheme from a date (side panel › Pay & tax › Pay scheme, Change pay
scheme); Add employee pre-fills it from Country of work; Mapping shows each team's USUAL scheme, "N have their own",
the banner and "Give everyone their own pay scheme" (+ Undo this fill), "Set for everyone in this team…", the list of
people paid by another country's scheme; Country of work changes ask to change the pay scheme; Change job, Updates
sheets ("Upload sheet" source), hiring offers and pay-data-file joiners follow the person's scheme; the contract follows
a scheme change (currency note). Lessons teach the same (en + vi). Every new string in vi_VN and id_ID.

## 2. The one-time fill (owner decisions, 27 Nov)

Applied with `ps3_fill.sh <db> apply` (START/DONE in the deploy notes, dump first, undo list), Ready + From Country of
work only, from 1 Nov 2026 (the fill's date = the first day of the current month), `source = fill`.

| Database / company | People | Given their own scheme | Rows written | Left as they are (why) |
|---|---:|---:|---:|---|
| rize / 1 | 231 | **227** | 227 (main only — no real advance) | 4: no Country of work (left for HR, owner) |
| payobook / 5 | 4,554 | **4,510** | 9,020 (main + its real mid-month advance each, A13) | 44: their country has several schemes and their team has NO usual scheme (23 have no team; 21 are in 5 teams with no map line) — the owner's rule "give them the team's usual scheme" had nothing to give, so all 44 left |
| payobook / 2 | 7 | 0 (**waiting for approval**) | 0 | 7: the company has a second approver — request `SM00009` "Sent for approval" to the demo approver; rows are written when it is approved in Approvals |
| payobook / 1 | 21 | 0 | 0 | 21: no active scheme for their country in that company (owner: stay) |
| sudima / 1 | 678 | not run | — | its only scheme is still a draft (owner: wait) |
| payobook_template, p0clone | 1 / 12 | not run | — | owner: not these |

"Fill empty Country of Work" was NOT run anywhere.

**Verification after the fill (read-only, `ps3_fillcheck.py`, before vs after):**

| Check | rize | payobook |
|---|---|---|
| Rows = plan | 227 rows / 227 people | 9,020 rows / 4,510 people (company 5) |
| "Who pays them" — main answer changed | 0 | 0 (all companies) |
| Real mid-month advance changed | 0 | 0 |
| Advance display artefact dropped (PS6 / A13: a team line "for any run" used to answer the advance question with the main scheme) | 227 (expected; nobody was ever paid an advance by it) | 0 |
| Next month's pay runs: in two main runs / missing / moved | 0 / 0 / 0 | 0 / 0 / 0 |
| "Paid by" settled | settled with Mapping's "Work it out again" (`recompute`): 227 stored advance artefacts cleared, stored main unchanged, 0 left to work out | settled the same way (payobook's daily recompute job is off by design): 1 person whose stored "Paid by" was still empty got the scheme the map already gave them; 0 left |
| Mapping banner | 231 people, 227 own, 4 still follow their team | company 5: 4,554 / 4,510 own / 44; companies 1 and 2 unchanged (21, 7) |
| Server log since the release | 0 ERROR / CRITICAL (a few WARNING tracebacks of other modules — probation, insights, portal landing — none from the pay-scheme modules) | same |

No service stop was needed.

## 3. How to undo

- **On screen**: Mapping › Who is paid by what › **Pay scheme fill** › **Undo this fill** (the latest fill of a
  company; takes off the rows the fill gave, keeps anybody changed since; rehearsed on the rize copy: back to before).
- **Undo lists**: `/odoo/backups/pscheme-p3-20261126T2005Z/fill/run-<db>-apply-<time>/person_scheme_fill_<db>.csv`
  (one `unlink` line per created row).
- **Dumps taken right before each fill**: same folder, `<db>-before-fill.dump`; release dumps
  `/odoo/backups/pscheme-p3-20261126T2005Z/{<db>.dump, golive-<db>.dump}`.
- **The waiting payobook company 2 request**: decline it in Approvals (nothing was written).

## 4. Open items

1. **sudima**: run the fill once its pay scheme is switched on (`ps3_fill.sh sudima dry`, then `apply`).
2. **rize: 4 people with no Country of work** — left for HR (list only in the main checkout's `outputs/`); then
   Change pay scheme on each, or run "Give everyone their own pay scheme" again (it lists only those still without).
3. **payobook company 1: 21 people** — no active scheme for their country there (demo); stay as they are.
4. **payobook company 5: 44 people** — no team usual scheme to give (§2); someone picks in the fill drawer, or their
   teams get a usual line on Mapping.
5. **payobook company 2: 7 people** — request `SM00009` waits for the demo approver.
6. **The owner's two-minute look on payobook.com** has not been done (the release engineer does not sign in to a live
   site): one person's Pay & tax › Pay scheme, Mapping banner, Change pay scheme opened and closed.
7. **Backup folder**: the weekly prune (Mondays 16:40 UTC; entries older than 3 days, keeps the newest 5) may remove
   `/odoo/backups/pscheme-p3-20261126T2005Z/` (dumps, undo lists, the fill tool) from **Mon 30 Nov 2026**. The tool is
   also in the repo (`docs/handovers/pscheme/p3/`); copy the undo lists elsewhere first if they must be kept longer.
8. **The three "known" ERROR lines** on every upgrade: `odoo.schema: column "country" / "date_from" / "date_to" of
   relation "payroll_analytics" contains null values` — pre-existing (other module), seen in every release.
9. **Untranslated leftovers** (not this programme's strings, all of which are in vi + id): Indonesian catalogues are
   partial in `pb_hr_payroll_formula` (51 entries), `pb_updates` (68), `pb_payrun_wizard` (13), `pb_contracts` (2) and
   absent in `pb_import_batch`, `pb_import_wizard`; `pb_learn` content is English + Vietnamese only (NH70).
10. ~~Small wording: "Since 1 Dec 2026" in Mapping's "have their own" list~~ — **closed**: commit `9c88dfcd4` (reads
    "From <date>"; dead "Since %s" msgid dropped), released looks-only 26 Nov 2026 21:35 UTC on all five (files +
    asset purge, no -u, no restart, 0 s down; served bundle checked ×5, version unchanged 19.0.2.8.0).
11. Earlier owner questions still open in the phase reports: P1 §10, P2a §12, P2b §10.

## 5. Can be removed

- Worktree `gitlocal-worktrees/pscheme`; branches `pscheme`, `pscheme-p2a`, `pscheme-p2b` (all merged into `19.1`).
- Local databases `ps_base`, `ps2b_base` (superseded by `p3_base`, which can stay as the live-like base).
- Server evidence `/tmp/pscheme-p3-20261126T2005Z/` (after the owner's look).

## 6. Follow-ups F1 and F2 (owner card, 27 Nov)

### F2 — Mapping "Who is paid by what" reads mapping a team as optional (wording; NORMAL tier ×5)
Commit `757c16793` on `19.1`; `pb_scheme_map` 19.0.2.9.0, `pb_formula_studio` 19.0.1.217.0.
- Strip under the arrow: the board's own sentence "N of M have their own pay scheme" + " · K teams have a usual
  scheme" when team lines exist (was "0 mapped", the studio's generic wire count). Handed over through the board's
  existing `onLoaded` prop (`pb_mapping_boards` seam; `pb_formula_studio` still does not depend on `pb_scheme_map`).
- Chips (lane-specific, only the scheme lane's case in `mapping_studio.js`): "Teams" / "Teams with people" and
  "Pay schemes" / "A team's usual pay scheme (optional)". No shared label was touched.
- Right-panel help opens with "Optional: drag a team onto a pay scheme to make it that team's usual scheme. It
  pre-fills new people and covers anyone without a pay scheme of their own." (hover / pull / keyboard hints kept).
- vi_VN + id_ID for all 8 new strings; replaced msgids removed (`pb_scheme_map` help; the four old studio chip
  words). Parse gate passes, no vendor word. Tests `/pb_scheme_map,/pb_formula_studio`: failing lines identical
  before/after (11 pre-existing `pb_formula_studio` failures on this base; `pb_scheme_map` 99/99). Local walk en + vi
  on a company with team lines and one without, console clean.
- Release 26 Nov 22:16:53–22:25:13 UTC, **501 s down**: `-u` exit 0 and 0 ERROR on all five (payobook_template 81 s,
  p0clone 76 s, sudima 79 s, rize 80 s, payobook 96 s); trees = commit; versions = manifests ×5; jobs identical ×5
  (none re-activated, nothing new; payobook 156 still off); 0 ERROR / Traceback in the server log since the stop;
  sites 200 ×5.

### F1 — rize: the Vietnam scheme's fallback rule follows Country of work (data, owner-ordered)
- New map line id 316: rule `[('company_id', '=', 1), ('payroll_country', '=', 'VN')]` → the Vietnam scheme, the exact
  shape of the India / Singapore / Indonesia rules (kind of run regular, sequence 10, source manual). Written through
  the map line model's own create (constraints + "Paid by needs working out again"). START/DONE in the deploy notes,
  dump `/odoo/backups/pscheme-f1-20261127/apply/rize-before-rule.dump`, undo record `rize_vn_rule_undo.txt` beside it.
- Checks (every active person, 242): with the person rule 0 changed (main + advance); without it 0 changed — every
  person with Country of work Vietnam (70) is already on the Vietnam code-list rule, so nobody moved from "nobody" to
  the Vietnam scheme today; the 4 without Country of work unchanged; code-list people whose Country of work is not
  Vietnam: 0, so the code-list rules (309, and 313 which only covered August) were left in place; a throwaway new
  person with Country of work Vietnam and no row is answered by the Vietnam scheme by the rule (rolled back).
  "Work it out again" afterwards: 0 left to work out.
- **Screen twin: no.** The Mapping screen shows and edits team and division lines only; a by-country rule line can
  be neither created, seen nor removed on screen, and the approval route has no kind for it. Open item (not built).
- Undo: `env["pb.scheme.board"].with_context(pb_schememap_approved_write=True).detach(316, 1)` in an `odoo-bin shell`
  on rize (or restore the dump), then Mapping › Work it out again.

### Found during the follow-ups (not caused by this work)
- **rize data changed by another process at 22:10:56 UTC** (one transaction, the admin login, a separate process; no
  deploy-notes line): 83 employee records created (23 active) and 72 archived. Of the 227 people the fill gave a scheme,
  12 are now archived; the 23 new active people have no scheme of their own. Rize's banner now reads 215 of 242.
  "Work it out again" filled the new people's "Paid by". Someone should confirm this was an intended data refresh; the
  new people can be given their scheme with "Give everyone their own pay scheme" (it lists only those without one).
- The bottom card "Nothing is attached to a scheme yet — You have been paying people for months, so the map already
  exists…" (company with no team lines) still reads as if something were missing; not in F2's scope.
- The interruption on 27 Nov (network error) hit only the local browser walk; nothing on the server was started.
