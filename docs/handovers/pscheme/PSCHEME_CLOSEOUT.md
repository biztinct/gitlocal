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

## 7. P4 — rize fill re-run, "Usual pay scheme by country", the empty card (owner card, 27 Nov)

### A. rize — the fill again (the 26 Nov staff refresh was planned)
`ps3_fill.sh rize apply` at 22:37 UTC (dump first, START/DONE, undo list
`/odoo/backups/pscheme-p3-20261126T2005Z/fill/run-rize-apply-20261126T2237Z/`): **23** people given their own pay scheme
(23 rows); the 215 who had one untouched; **4** left — no Country of work (left for HR). Before/after: who-pays-them
(main + real advance) unchanged for everyone; next month nobody in two main runs, nobody missing, nobody moved;
"Work it out again": 0 left to work out; banner 238 of 242 have their own. The 12 archived people keep their rows
(history) and are reached by no scheme's pay run; 3 of them still have a running contract (a data item for HR).

### B. Mapping › Who is paid by what › "Usual pay scheme by country"
- A section below the banner, above the teams (collapsible, remembers its state, opens by itself when there is a
  hole): one line per Country of work with people or an active scheme — "Vietnam · 70 people · 0 rely on this today",
  the scheme as a chip; **not set** is grey unless somebody relies on nothing ("2 people here have no pay scheme and
  nothing catches them", amber, with Choose); a country without an active scheme says so with "Add a pay scheme".
- Choose / Change / Remove inline: radio cards (arrow keys, Enter, Escape, Ctrl+Enter), "Show pay schemes of other
  countries (N)" with a required "This pay scheme is of another country" tick, one live sentence of consequence, Save
  (fast lane) or "Ask for this change" (second approver).
- "Other rules (N)": each rule in plain words ("A list of 2 named people → <scheme>", "People matching a special
  rule"), "Reaches N today · Set up by support"; Remove only when nobody would be left uncaught, otherwise the reason.
- Server: new approval kind `country_set` (set / change / remove a country line; remove an other rule) — Mapping
  route, fast lane or second approver, re-check (refused in plain words when the line moved meanwhile), audit,
  proposer rights as `person_set`, carry-out gate unchanged. A new line is written after the company's other rules
  (a named-people rule keeps winning); each write reports who was caught / moved / lost. Refusals: not active, other
  company, mid-month advance, not monthly, another country unconfirmed, already the same, nothing to remove.
- The "not covered" list gains "Choose a usual pay scheme for <country>"; a person caught by a country line reads
  "From the usual pay scheme of <country>" on their panel (was "From a rule on the map").
- One lesson sentence (Mapping "Who is paid by what", en + vi). `pb_learn` 19.0.20.12.0.

### C. The empty card
"Everyone is paid by their own pay scheme — Giving a team a usual pay scheme is optional. It pre-fills new people in
that team." (+ "Suggest who pays each team") when 2 % or fewer still have none; otherwise "N people have no pay scheme
of their own yet" with "Give everyone their own pay scheme". The old card's msgids and 7 other dead msgids removed.

### Tests and walks
- `test_pscheme_p4` T1–T10 pass (12 tests, incl. second approver + re-check). Suites
  `/pb_scheme_map,/pb_hr_payroll_formula,/pb_formula_studio,/pb_new_hire,/pb_learn` before (`a2549f35e`) / after:
  1,962 → 1,973 tests, the failing lines **identical** (17 failed + 2 errors pre-existing on this base);
  `pb_scheme_map` 112/112. P2a's msgid list updated deliberately (the not-covered sentence). `gen_learn_data --check`
  clean, `pb_learn` vi_VN.po untouched; parse gate; placeholders kept; 0 vendor word.
- Local walks (en + vi, console clean after the fix of a template-variable clash found on the first walk): the amber
  Vietnam hole → Choose → Save → grey, "not covered" 4 → 2; Remove → amber again; set again; second-approver company →
  "Ask for this change" → "Sent for approval to …"; Other rules disclosure with the reason; a new person with
  Country of work Vietnam and no scheme → answered by the line ("From the usual pay scheme of Vietnam"); the empty
  card's "N people have no pay scheme of their own yet" state (the other state by test T8); 500 px (the browser's
  narrowest): nothing overflows. vi and id read at the source (screen strings and server sentences).

### Release ×5 (normal tier + dumps)
Commit `3935840ee` on `19.1`; `pb_scheme_map` 19.0.2.10.0, `pb_learn` 19.0.20.12.0. 26 Nov 23:47:53–23:56:14 UTC,
**502 s down**; dumps ×5 right before the stop (`/odoo/backups/pscheme-p4-20261127P4/`).

| Database | `-u` | Jobs active before → after |
|---|---|---|
| payobook_template | 0 / 80 s / 0 ERROR | 41 → 41 |
| p0clone | 0 / 77 s / 0 ERROR | 50 → 50 |
| sudima | 0 / 79 s / 0 ERROR | 92 → 92 |
| rize | 0 / 81 s / 0 ERROR | 93 → 93 |
| payobook | 0 / 98 s / 0 ERROR | 60 → 60 (job 156 still off) |

Trees = commit; versions = manifests ×5; no job re-activated; 0 ERROR / Traceback since the stop; sites 200 ×5.
Read-only look per database (counts): **rize** 4 of 4 countries set (Indonesia 137 people, Vietnam 70, India 29,
Singapore 2), **0 holes**, 1 other rule (the Vietnam named-people list, reaches 70, can now be taken off — the
Vietnam line pays them the same way); **payobook** company 5: Vietnam not set, 44 holes (the 44 people of P3 who
need a choice), company 1: 21 people and no active Vietnam scheme, company 2: 7 people all caught; **sudima**: 678
holes — its only scheme is still a draft; **payobook_template**, **p0clone**: nothing to show.

### Anything unexpected
- First walk: the chooser crashed (a method named like the template's loop variable); renamed, re-walked clean.
- sudima's section opens in amber ("678 people have no pay scheme and nothing catches them") — true until its pay
  scheme is switched on; nothing to do now.

### Open items
- A waiting `country_set` request is not yet shown on its country line (the chooser says "Sent for approval"; the
  line stays "Not set" until approved).
- rize's Vietnam named-people rule is now redundant (the Vietnam line covers the same 70 people the same way) and can
  be taken off on screen — the owner's call.
- payobook: Vietnam country line not chosen (company 5 has seven Vietnam schemes); company 1 has no active scheme.
- Earlier open items (§4, §6) stand: sudima fill, rize's 4 without Country of work, payobook's 44 / 21 / 7, the owner's
  two-minute look, backup pruning, the three known analytics ERROR lines, partial Indonesian catalogues elsewhere.
