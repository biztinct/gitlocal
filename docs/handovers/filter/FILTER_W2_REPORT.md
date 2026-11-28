# FILTER wave 2 — report (People lifecycle boards: Contract renewals, Probation, Exits)

Builder: Opus, worktree branch `worktree-agent-a0f8e85aa75f03464` (based on `19.1` @ `7fd77c7ad`).
Tested on the shared preview (`pbf_preview`, a copy of payobook) 2026-10-31, held as `w2`, released.
Nothing was deployed to live, no live database or `/opt/deploy-notes.md` was touched.

**Summary.** All three boards are on the shared filter panel and pass the test list
(T1–T22 + W2-T1…T4), with the exceptions marked n.a. below (no bulk action on these
boards; fewer rows on the copy than one page). Console clean on every screen; no
ERROR line in the preview log; upgrade rehearsal `EXIT=0`, `errors=0`.

---

## 1. Per screen

### 1.1 Contract renewals — `pb_contract_lifecycle` 19.0.1.3.0 (`pb_contractlife_board`)
- **Model** `pb.contractlife` + `pb.filter.mixin`, records `hr.contract`, screen `contractends`.
- **Base domain** = the old two searches as ONE domain: company + state draft/open +
  (end date set OR employee active and employment type intern/contractor/freelance/student/trainee).
  Note: the handover's literal domain left the state off the second branch; the old board
  required draft/open on both, so the union keeps it (W2-T4: union 9 = old board 9).
- **Records under sudo** only for readers the board lets in (`_can_read` AND `hr.contract`
  read), because the board always sudo-read employment type (behind `hr.group_hr_user`)
  and the decisions. `pbf_layout` refuses everyone else (`refused`), the board shows its
  own "Contracts are looked after by the HR team" panel. Cards are still read as the reader.
- **Sections** (shown on the copy = ✔, hidden because one value or none = ✖):
  PIN Contract ends ✔ (date, future presets) · PIN Decision ✔ (not raised / opened, nobody asked /
  decision needed / extension requested / evaluation running / decided / ended undecided — literal
  `pb_review_ids any / not any` domains: live review, else latest) · PIN Department ✖ (one team on
  the copy) · Needs somebody ✔ (nobody has decided / ends within N days / ended undecided /
  intern or contractor with no end date / nothing needed — the old `needsAttention`, as a literal
  domain with the lead-days parameter baked in per request) · Where it stands ✔ (the 4 steps) ·
  Employment type ✔ (choice; the board's own words "Permanent / Intern / …") · Manager ✖ ·
  Contract status ✔ · Contract category ✔ · Started ✔.
  **No `domain_method` was needed** on this board: every fact is one SQL count.
- **Views**: All · Ending within <lead> days (a from/to range today → today+lead) · Nobody has
  decided · Waiting to be agreed · Interns and contractors.
- **Sorts**: Ending soonest first (default, `date_end nulls last`) · Ending latest first ·
  Name A–Z · Started most recently. **Page size** 60.
- **Numbers**: counted over the whole base (`get_board_head`); pressing one = `kit.toggleFilters`
  with exactly the view's filters (server sends `glance_filters`), so the tab lights too.
  "Made permanent this year" keeps its own count (R4) and does not filter.
- **Steps**: counted on the server for the panel's filters minus the step (R1), flags
  ("2 waiting for a sign-off", "ended with nothing decided", "need a decision") too; pressing a
  step = `kit.only('step', key)` (other filters kept), again = clear.
- **Removed**: search box, kind / attention / month / review-state / department chip rows,
  "Showing X of Y · press a step…" line, the 300 cap and its note.
- `get_board` kept unchanged for any old reader (R4).

### 1.2 Probation — `pb_probation` 19.0.1.5.0 (`pb_probation_board`)
- **Model** `pb.probation` + mixin, records `hr.employee`, screen `probation`, base = company +
  active + `pb_probation_state in (in_probation, extended)`.
- **Gate**: `_pr_may_list` = lifecycle tier AND read access to `pb_probation_state`
  (`groups='hr.group_hr_user'`). The old board searched that field as the reader, so a reader
  without it already saw nothing (an empty "Nobody is in a trial period" — misleading); now
  they get the board's own refusal. **W2-T2**: a lifecycle-only user (no HR group) created on
  the copy, signed in through the tunnel → "Trial periods are looked after by the HR team",
  no traceback, clean console; same user via shell: `pbf_layout` refused, head `allowed=False`,
  page empty. (User deactivated afterwards.)
- **Records under sudo** for those readers only: the trial end date is an
  `hr.group_hr_manager` field the board always read under sudo, and both its section and the
  default order use it.
- **Sections**: PIN Trial period ends ✔ · PIN Review step ✔ (the five numbered steps, literal
  `pb_probation_review_ids any` domains mirroring `for_employee` + `flowStepOf` incl. `pb_gate`) ·
  PIN Department ✔ · Review status ✔ (8 values) · Colleagues' answers ✖ (none overdue on the copy) ·
  Review round ✔ (first / second or later — the `round` hop is one2many, so a choice) ·
  Trial status ✔ · Country ✔ · Manager ✔ · Job position ✔ · Company ✖ · Joined ✔.
  No `domain_method` needed.
- **Views**: All in trial · Ending within 7 days (`{to: today+7}` — it has always counted a
  trial that already ran out too) · Waiting on a decision · Answers overdue · Extended.
- **Sorts**: Trial ends soonest first (default) · Trial ends latest first · Name A–Z ·
  Newest joiners first. **Page size** 60.
- **Numbers / steps**: as renewals (server counts, figures = view filters, steps follow filters).
- **Removed**: search box, review-state / department / country chips, "Needs somebody" chip
  (its training and red-flag halves are not searchable — debt, §4), showing line, cap.
- Arrival `person:<id>` → drawer logic untouched; drawer opens from the card (checked).

### 1.3 Exits — `pb_offboarding` 19.0.1.4.0 (`pb_exits_board`)
- **Model** `pb.exits` + mixin, records `pb.journey.case` (no sudo), screen `exits`, base =
  company + offboarding + draft/active/on hold + (no date or last day ≥ today−120).
- **The facts with no path** (settlement, items not back, the gate) come from ONE batch,
  `_ex_facts`: base cases → settlements by employee (the one `pb_gate_for` picks) → blocking
  steps → open clearances → tangible items, all sudo exactly as
  `hr.full.final.settlement._pb_blocker_list` reads them; cached on `env.cr.cache` for the
  request. `domain_method`s turn them into `[('id','in',ids)]`.
- **Sections**: PIN Last day ✔ (future presets: already passed / next 30 / next 90 / later /
  none) · PIN Department ✔ · PIN Clearances ✔ (still open / nothing open) · Where they are ✔
  (the 4 steps; notice / signing off = literal date + id-set, ready / settled = facts) ·
  Final settlement ✔ (ready / held up / worked out, to check / settled / none) · Held up ✔
  (the old "Something is holding it up" chip) · Items not back ✖ (nobody holds anything on
  the copy) · Desk still open ✔ (IT / HR / Finance / Admin) · Handover ✔ · Steps overdue ✔ ·
  Country ✔ · Manager ✔ · Checklist status ✖ · Checklist used ✔ · Started by ✔.
- **Views**: All leaving · Leaving this month (today → today+31, what the figure always
  counted; chip "31 Oct 2026 – 1 Dec 2026") · Last day has passed (preset "Already passed") ·
  Clearances still open · Ready to settle.
- **Sorts**: Last day soonest first (default) · Last day latest first · Name A–Z · Least done
  first. **Page size** 60.
- **Numbers**: all six counted over the whole board; "Clearances still open" and "Items not
  back yet" keep counting clearances / items (not people), and pressing them lists the people.
- **Removed**: search box, month / department / country chips, "Something is holding it up"
  chip (now a section), showing line, cap.

### Learn (`pb_learn` 19.0.20.6.4)
- Replicas `contractends()`, `probation()`, `exits()` draw the filter strip (view tabs,
  Filters, search) under the steps, bilingual, anchors `cl-filters`, `pr-filters`,
  `ex2-filters` registered (`reserved`: no lesson names them yet).
- Lessons: none changed. Every lesson ref on these screens names the numbers, the steps, the
  cards, the drawer or the decision controls — all kept with the same labels and anchors
  (grep of `learn_content.json` for the three screens' `cl-/pr-/ex2-` anchors and for the
  glance labels "Ending within a week", "Leaving this month": all still on screen).
- `tests/test_anchor_registry.py` test_01 now accepts the kit's `coach="'x'"` prop form
  (`pe-filters` from wave 0 was already failing it — see F13).

## 2. Test matrix (preview copy, Chrome, Mitchell Admin session on the copy, all companies)

| Test | Renewals | Probation | Exits |
|---|---|---|---|
| T1 open, counts, first tab, console | pass | pass | pass |
| T2 tick pinned value | pass (2 of 9, own counts kept, others recount, steps follow) | pass | pass |
| T3 OR within section | pass (2→3) | pass (10→12) | pass (2→7) |
| T4 AND across sections | pass (3→0) | pass (12→2) | pass (9→2) |
| T5 Only | pass | pass | pass |
| T6 find (match, Enter ticks first, Escape) | pass ("contractor") | pass ("sales") | pass (kit, same) |
| T7 find nonsense | pass | pass | pass (kit, same) |
| T8 date preset / range chip | pass (view range "31 Oct 2026 – 30 Dec 2026") | pass ("Until 7 Nov 2026") | pass ("Already passed", range chip) |
| T9 number section | n.a. (none) | n.a. | n.a. |
| T10 chip → section (panel scrolls, page does not), ×, Clear all | pass | pass | pass (×) |
| T11 search, "/", Escape | pass | pass | pass |
| T12 every sort | pass (4) | pass (4) | pass (4) |
| T13 paging | n.a. in UI (9 rows < 60); server paging verified by RPC (page 2 continues page 1, steps only on page 1) | n.a. (12) | n.a. (10) |
| T14 save private, rename, share toast, delete | pass (full) | pass (save + delete) | kit identical, not repeated |
| T15 built-in views | pass (5) | pass (5) | pass (5, Ready to settle → empty state) |
| T16 figures tick + light tab, press again | pass | pass (figure with no view keeps previous tab — kit gap K1) | pass (6 figures) |
| T17 hide filters + reload | pass | pass | pass |
| T18 `?pbf=` link | pass | pass | pass (domain_method sections) |
| T19 bulk / export | n.a. (none on these boards) | n.a. | n.a. |
| T20 empty state + show all | pass | pass | pass |
| T21 phone drawer | pass via `pbf--narrow` (panel `position: fixed`); the test browser would not resize the window, so the scrim (needs the kit's own narrow flag) was not seen | same | same |
| T22 Vietnamese layout (sections, views, sorts, option labels) | pass | pass | pass |
| Console errors | none | none | none |

W2 tests:
- **W2-T1 timing** — below.
- **W2-T2** — pass (see 1.2).
- **W2-T3** Exits "Ready to settle": panel 0 = manual `pb_gate_for` count 0; settled 1 = 1;
  to check 1 = 1 (the copy has no ready settlement; held 7, none 2).
- **W2-T4** Renewals union base 9 = old board 9 (old board not capped on the copy).

Screenshots (local, test browser):
`/var/folders/tl/jk1lq25507v_yj3394mz25x00000gp/T/claude-chrome-screenshots-7vHXhr/screenshot-1793409634633-1.jpg` (renewals),
`…-1793409634634-2.jpg` (probation), `…-1793409804600-3.jpg` (exits),
`…-1793410161787-4.jpg` (probation refusal for the lifecycle-only user).

### domain_method timing (W2-T1, `odoo-bin shell` on the preview, admin, all companies, best of 5, cache cleared each run)

| Board | Method | ms | count on copy |
|---|---|---|---|
| Exits | `_ex_facts` (the 5-query batch) | 6.1 | base 10 |
| Exits | `_pbf_dm_ff_ready` | 6.0 | 0 |
| Exits | `_pbf_dm_ff_held` | 6.0 | 7 |
| Exits | `_pbf_dm_ff_check` | 6.0 | 1 |
| Exits | `_pbf_dm_ff_closed` | 6.0 | 1 |
| Exits | `_pbf_dm_ff_none` | 6.0 | 2 |
| Exits | `_pbf_dm_assets_yes` / `_no` | 6.1 / 6.0 | 0 / 10 |
| Exits | `_pbf_dm_step_notice` / `_signoff` | 6.1 / 6.1 | 4 / 5 |
| Exits | `_pbf_dm_held_yes` / `_no` | 6.2 / 6.2 | 9 / 1 |
| Renewals, Probation | none (all literal domains) | — | — |

Whole calls: Exits `pbf_layout` 59 ms, `pbf_counts` (all sections) 107 ms, `get_board_head`
11 ms, `get_board_page` 219 ms · Renewals `pbf_layout` 193 ms, `pbf_counts` 270 ms,
`get_board_page` 161 ms · Probation `pbf_counts` 90 ms, `get_board_page` 216 ms (the page
time is the old per-card `_row` probes, unchanged).
Caveat: the copy holds 9 / 12 / 10 rows on these boards. `_ex_facts` is five queries whatever
the size (each `employee_id in …` over the leavers), so it grows with the number of leavers,
not per card; re-time on payobook after deploy.

## 3. Deploy evidence (preview rehearsal only — the live deploy is the coordinator's)
- Stage `/tmp/pbf_stage_w2`; `pbf_preview.sh upgrade pb_contract_lifecycle,pb_probation,pb_offboarding,pb_learn`
  → 268 modules loaded, **EXIT=0, errors=0**; later JS/XML/PO changes by `sync` + `restart`
  (two Python label changes also by restart: spec labels are computed per request).
- PO gate (ledger §5) on the box: all three `vi_VN.po` parse.
- **For the live batch**: sync AND `-u` `pb_contract_lifecycle`, `pb_probation`,
  `pb_offboarding` (new dependency on `pb_filter_kit` — every DB where they are installed) and
  `pb_learn` (bumped; F9: snapshot and restore crons). No new fields, no migrations, no data files.

## 4. Kit gaps and debts
Kit gaps (pb_filter_kit not changed):
- **K1** A figure whose filters match no view (Probation "Reviews running") leaves the
  previously lit tab lit (with its dirty dot): `_matchView` keeps the old `viewKey` when
  nothing matches. Expected: no tab lit. Cosmetic.
- **K2** The phone scrim exists only when the kit's own `matchMedia` says narrow; adding
  `pbf--narrow` (the test list's fallback) shows the drawer without a scrim.

Debts:
- **Probation**: training done / red flags raised at a check-in stay card badges, so the old
  "Needs somebody" chip has no filter equivalent (handover: debt). The refusal sentence tells a
  lifecycle-only reader to "ask to be added to the lifecycle team" — they are in it; what they
  lack is the HR officer group. Wording owned by the board, not changed here.
- **Renewals**: a contract with BOTH a decided and a later "ended undecided" review counts as
  Decided in the panel while its card says the latest; never seen on the copy (a decided
  contract gets no further review). The search is `ilike` (no accent folding).
- **Exits**: "Leaving this month" keeps the figure's meaning (next 31 days), so its chip is a
  date range rather than "This month".
- **Translations, pre-existing**: these modules' `vi_VN.po` lack Vietnamese for ~390 / ~560 /
  ~520 older strings (export entries with no msgstr). Not from this wave; only W2 strings added.
- **Not exercised**: T13 paging in the UI and the timing at payobook scale (copy too small).

## 5. Self-score (design bar)
| | Renewals | Probation | Exits |
|---|---|---|---|
| Hero moment | countdown cards + steps that now follow every filter | the five-stop rail + numbered steps | clearance lights; settlement facts are filters for the first time |
| Zero dead-ends | loading skeleton, empty board, empty filter (names the fix), failure toast, refusal | same + refusal instead of a silent empty board | same |
| Plain language | yes ("Opened, nobody asked yet", "Needs somebody") | yes ("Colleagues' answers: Overdue") | yes ("Held up: Something is holding it up") |
| Motion with purpose | pulse skeleton (reduced-motion safe) | same | same |
| Keyboard / bulk | kit keyboard (/, Escape, Enter); no bulk on these boards | same | same |

## 6. Commits (branch `worktree-agent-a0f8e85aa75f03464`, not pushed)
- `b76742e7e` Contract renewals on the panel (pb_contract_lifecycle)
- `11fdd055d` Probation on the panel (pb_probation)
- `46c25e9f1` Exits on the panel (pb_offboarding)
- `71659dc94` Learn follows the three boards (pb_learn)
- this report + ledger F13–F18 (docs)

Not committed: nothing of the wave. Modules touched: `pb_contract_lifecycle`, `pb_probation`,
`pb_offboarding`, `pb_learn`.

## 7. New gotchas → ledger §4 F13–F18.
