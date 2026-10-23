# NAV P3a — Hiring: APPLICANTS and OFFERS registers

Read first: `docs/handovers/NAV_LEDGER.md` (R1–R13 + gotchas), `docs/handovers/NAV_P2A_REPORT.md` §1 (Hiring hub as built:
`pb_hiring/static/src/js/hiring_hub.js`, lenses overview / interviews / bank over `PbHiringBoard` with `startTab`).
Design of record: `docs/design/payobook-navigation-review-20261019.html` §12.4 (Hiring rail) and §13 (Hiring rows:
OVERVIEW tiles "Offers awaiting action" and "Joining soon" are New; APPLICANTS and OFFERS are New registers over existing
records). Owner decisions 2026-10-21: P3 includes this sub-phase first. Implementer: Opus. Deploy: normal tier, announced.

## 1. Goal

Two new rail items on Hiring, between OVERVIEW and INTERVIEWS:
- **APPLICANTS** (full name "Applications across jobs"): one pipeline and one list of every application the person may see,
  across all roles, with the same cards, drawer, moves and bulk actions the role board has.
- **OFFERS** (full name "Offers and joining checks"): a register of every offer the person may see, across roles, with
  state, documents in/wanted, background check, joining date, and the existing offer actions.
Plus two OVERVIEW tiles that open OFFERS pre-filtered: **Offers waiting on you** and **Joining soon**.

Rail after P3a: OVERVIEW · APPLICANTS · OFFERS · INTERVIEWS · TALENT POOL (edit the inline lens list in `hiring_hub.js:71-84`;
registry lenses come after the built-ins, so these two are built-ins).

## 2. Verified plumbing (do not re-derive)

| Fact | Where |
|---|---|
| The candidate drawer is a template drawn by `PbHiringBoard` (`pb_hiring.P1Overlays`, `hiring_board_p1.xml:260-395`), called at the board root (`hiring_board.xml:1016-1021`) so it works on the home view too; it reads `state.cand` only; `openCand(id)` → `pb.hiring.get_candidate` (`hiring_board.js:1863`, patched `hiring_p6.js:125-145`); the payload carries its own `can_recruit`/`can_move`. **It cannot be reused from a separate component.** So both registers are new **home tabs of `PbHiringBoard`**, exposed as lenses with `startTab:"applicants"` / `"offers"` exactly like interviews/bank (`hiring_board.js:284-293`, `setTab` `:914`). | agent fact-find 2026-10-21 |
| Drawer verbs that depend on the role page: `stepCand`, `advance(candCard())`, `runNextBox('advance')`, `reloadRole()` use `state.drawer`; off a role page they find nothing. Moves from the drawer on the new tab must call the new tab's reload instead. | `hiring_board.js` |
| Every stage move goes through `pb.hiring.act` → `_act_journey_stage` (`board_p1.py:261-345`): payload `applicant_ids|applicant_id, key|stage_id, reason, hold_until, send_email, undo`; refuses `joined`; per-applicant `_applicant(id, for_move=True)` → `_require_move(req)`. Returns `{moved:[…], note, interview_prompt?}`. JS: `moveTo` (`:1666`), `undoToast` (`:1704`), `openOutcome/saveOutcome` (`:1759-1775`), `pickMove` (`:1788`). Bulk bar verbs (`hiring_board_p1.xml:165-173`): `openMoveMenuSel, openShareSel, startMessageSel, bulkNotThisTime, clearSel`. | |
| Card builder `_card(app, ivs, doc_count, req, now, today, can_recruit)` (`board_p1.py:488-589`) needs a role object; later phases add fields (`forms_p2.py:1406`, `facade_p5.py:163`, `facade_p6.py:267`, `facade_p7.py:513`, `facade_p4.py:270-324` incl. `_mask_card` for non-team readers). Stage lookup `Stage._pb_stage(key)`; stage keys/families in `journey.py:20-46,171-197` (`open` family: screening, shortlist, panel_review, phone, assignment, discussion_1/2/3, reference, offer, post_offer; `done`: joined; `closed`: outcomes). | |
| Visibility: `pb.hiring.requisition` rules `rule_requisition_own` (`pb_hiring_security.xml:228-238`: requested_by, reporting manager, recruiter, asked_user, non-confidential department head) OR `rule_requisition_all` for `group_hiring_user`. Applicants are read as system after the role check (`board_p1.py:239-258`, P4 shares `facade_p4.py:177-188`). Offers: `rule_offer_own` (`:352-356`) / `rule_offer_all` (`:359-363`); money fields carry `groups='pb_hiring.group_hiring_user'` and `_offer_row` blanks totals for non-team readers (`facade_p4.py:216-225`). Covers: `pb_hiring_a3.py:40-112`. | |
| No cross-role applicant loader exists. `_candidates(req)` (`board_p1.py:458-485`) searches `job_id = req.job_id`, `active_test=False`, cap 600. Glance `candidates` = sum of `_pipeline(req)` (`pb_hiring.py:327-346`). | |
| `offer_rows` already loaded company-wide into `state.offerRows` (`pb_hiring_a3.py:143,157-161`, as the user, limit 200, `id desc`) with `_offer_row(offer, full=False)` fields: `id, name, requisition_id, role, applicant_id, candidate, state, state_label, start_date, monthly_total, annual_total, currency, decision, decision_label, comment, signed_on, closed_on, has_letter, has_signed` + P6 `expected_join_date, expected_words, joined_on, join_status(_label), drop_words, doc_count`. **No template draws it.** KPIs `offers_out`, `filled_month` (`:164-172`). | |
| Offer states `OFFER_STATES` (`hiring_common.py:371-392`): draft → submitted → manager_ok → hr_ok → sent → accepted \| declined → signed → joined \| dropped, plus refused. `OFFER_LIVE` (`:464`). Approval rungs `offer_approval.py:183-191`. Transitions: `action_submit :502`, `action_manager_agree :520`, `action_hr_agree :525`, `action_refuse :530`, `action_send_to_candidate :598`, `record_decision :710`, `action_record_signed :766`, `action_confirm_joined` (`offer_closure.py:70`), `action_did_not_join` (`joining_p6.py:1102`), `action_change_join_date` (`:1064`). | |
| Offer verbs reachable through `pb.hiring.act` (all gated by `_require_recruit(offer.requisition_id)`): `open_bgv, set_bgv_item, bgv_override, request_documents, remind_documents, copy_doc_link, draft_offer, offer_set, offer_line, prepare_letter/offer_letter, submit_offer, send_offer, copy_offer_link, record_signed, close_offer/confirm_joined, did_not_join, change_join_date, prejoin_*, doc_add/doc_remove, week_send, open_offer, open_employee, open_package, open_case, open_letter` (`pb_hiring_a3.py:462-680`, `facade_p6.py:364-560`). | |
| Docreq fields `state, in_count, wanted_count, deadline, sent_on, last_reminder_on` (`docreq.py:75-116`); BGV keyed on requisition+applicant: `state, pending_count, flag_count, override_*` (`bgv.py:74-109`). | |
| **Bug to fix:** `offer_views.xml:43` list decoration and `:205-206` filter `f_joined` still test `state == 'closed'`; the state is `joined`. | |
| Overview strip: `glance` (`hiring_board.js:504-518`), drawn `hiring_board.xml:98-106`; "Offers out" (`:516`, `run:null`), "Joined this month" (`:518`, `run:null`). KPIs `_kpis` (`pb_hiring.py:417-441`) + `facade_p3.py:103` + `pb_hiring_a3.py:164-171`. | |
| Look: `.pbhr` root; QuietGlance/QuietSteps are `t-call` templates from `pb_import_kit` (`quiet_board.xml:26,38`) used on the role page (`hiring_board_p1.xml:69-72`); icons via `ic` from `@pb_import_kit/js/import_icons`; phase scss files `hiring_pN.scss` listed in the manifest; dark tokens mixin `hiring_board_p1.scss:20-78`. | |
| Learn: new `data-coach` anchors must be registered in `pb_learn/static/src/anchors.json` (`"reserved": true` until a lesson uses them) or `test_anchor_registry.py` tests 05/08 fail. Hub screens live in `docs/tutorial_poc/author/data.js` (hub_hiring tabs) and practice `MENU` in `practice-data.js`; regenerate with `gen_learn_data.py` (safe for the .po, still diff it). | ledger P2 rows |
| Insights numbers to stay consistent with: funnel `analytics_p6.py:156-246` (offered/accepted/signed/joined definitions), time to fill/offer `analytics.py:227-260`. | |

## 3. Design

Design bar (R11, owner's words): "extreme WOW, intuitive, out-of-this-world experience, best in class." Lucide only. No "Odoo".

### 3.1 APPLICANTS tab (`startTab:"applicants"`)

- **Hero moment:** one glance line that reads as a sentence: "**128 people** in play across **27 roles** · **9 waiting on you** · **4 opinions late**", each number a filter chip (QuietGlance). Below it, the pipeline: one column per stage key in journey order (open family only; closed outcomes in a folded right rail as the role board does), each column header showing count and average days in stage. A card is the existing card markup (`hiring_board.xml` card partial used by the role board, incl. flags iv/waiting/late/offer/duplicate/joining/agency), with one extra line: the **role name** (chip) because the column mixes roles.
- **Board / List toggle** (same control as the Payroll board): list columns Name · Role · Stage · Days in stage · Next interview · Opinions · Waiting on · Applied. Sort by any column; default stage then days in stage desc.
- **Filters** (chips above, persisted in localStorage `pbhr.applicants.v1`): Role (search-select over the roles I can see), Recruiter, Stage family (In play / Offer / Joined / Closed), "Waiting on you", "Opinions late", "Interview this week", "Possible duplicate", text search (name, email, role). Status words are filters, never tabs (D12).
- **Actions:** card click → `openCand(id)` (drawer). Multi-select → the existing bulk bar (Move to, Share with, Send an email, Not this time, Clear). "Move to" uses `pickMove` with the role's allowed stages for that applicant (ask the server per applicant via the existing move validation; if a mixed selection cannot share a target, say so in one sentence). Drawer moves and bulk moves call `reloadApplicants()` instead of `reloadRole()`.
- **Empty states:** no roles visible → "You are not on any role yet. Ask a recruiter to share one with you." with the door to Overview; filters empty → "Nobody matches these filters" + Clear. Loading skeleton. Cap: server returns at most 600 cards and says "Showing the newest 600 of N" like the role board (`BOARD_CANDIDATES`).
- **Privacy:** non-team readers get `_mask_card` cards; money never appears here.

Server: new `pb.hiring.get_applicants(filters=None, cursor=None)` in a new file `pb_hiring/models/registers_p9.py` (follow the `facade_pN.py` pattern and `_inherit = 'pb.hiring'`): (1) roles = `pb.hiring.requisition.search([('company_id','in',co_ids)])` as the caller (rules apply) + covers; (2) applicants as sudo with `job_id in roles.job_id`, `active_test=False`, family filter, cap 600, ordered `date_last_stage_update desc`; (3) build cards with `_card(...)` per applicant using its own role (pre-fetch interviews per role as `_board` does; reuse `_candidates`' interview/doc batching — refactor into a helper if needed, do not duplicate 100 lines); (4) mask per role with `_is_hiring_reader`; (5) return `{columns:[{key, label, family, count, avg_days}], cards, total, capped, roles:[{id,name}], recruiters:[…], glance:{in_play, roles, waiting_mine, opinions_late}}`. `waiting_mine` here keeps the role board's existing meaning of "waiting on you": a first look or an interview outcome is owed on that person (card flag `waiting`) — decision 2026-10-21; the role's request sign-off stays on the Overview figure.

### 3.2 OFFERS tab (`startTab:"offers"`)

- **Hero moment:** QuietSteps strip that tells the story left to right: **In approval** (submitted/manager_ok/hr_ok) · **With the candidate** (sent) · **Accepted and signing** (accepted/signed) · **Joining soon** (accepted/signed with `expected_join_date` within 30 days, shown as a sub-count and a filter) · **Joined** · **Did not happen** (declined/dropped/refused). Each step is a filter; "waiting on you" count (my open seat on the offer approval route) lit in the brand tint on the In approval step.
- **Register rows** (one per offer; list only, no board): Candidate (avatar, name) · Role · State (pill, with "waiting on you" when my seat) · Documents ("3 of 5 in", amber when deadline passed) · Check ("clear" / "2 flags" / "pending", via the role+applicant BGV) · Joining (expected date + words "in 12 days"; "joined 3 Oct"; "did not join: reason") · Signed on · Owner (recruiter). Money columns **only** for `group_hiring_user` (already masked server-side; also hide the columns in the template for non-team).
- **Filters:** step (above), Role, Recruiter, "Waiting on you", "Documents overdue", "Check flagged", "Joining in 30 days", search. Persist in `pbhr.offers.v1`.
- **Row actions (⋯ menu, each gated the way the Details panel gates them):** Open candidate (drawer), Open offer (`open_offer`), Remind about documents (`remind_documents`), Record signed (`record_signed`), Change joining date (`change_join_date`), Confirm joined (`confirm_joined`), Did not join (`did_not_join`), Open joining checklist (`open_case`) when `case_id`. Joined rows show a "Handed to People › Joiners" link that opens `pb_people_hub` lens `newjoiners` with `pb_focus` the employee id (use `openHub` from `hub_nav.js`).
- **Empty states:** no offers → "No offers yet. Offers are made from a role's Offer & joining panel." with a door to Overview; filtered empty → sentence + Clear.

Server: `pb.hiring.get_offers(filters=None)` in the same file: reuse `_offer_rows` logic but with filters and `full=False`, add per row `waiting_mine` (my open seat on the offer's approval request: reuse the `_chain_my_seat` pattern from `pb_hiring.py:301-324` for offers, via `offer_approval.py`), `docreq` summary `{in, wanted, deadline, overdue}`, `bgv` summary `{state, flags, pending}` (lookup by requisition+applicant), `recruiter`, `joining_soon` boolean. Keep the 200 cap but order by `expected_join_date` nulls last then `id desc` when the Joining filter is on. Masking as `_offer_row` does.

### 3.3 OVERVIEW tiles

Replace the count-only "Offers out" tile with **"Offers waiting on you"** (`run` → `setTab("offers")` + filter waiting_mine) and add **"Joining soon"** (`run` → offers + Joining-in-30-days filter). Keep "Joined this month" but give it `run` → offers filtered Joined this month. Source counts in `_kpis` / `pb_hiring_a3.py:164-172`: `offers_waiting_mine`, `joining_soon`. Strip stays ≤ 10 tiles: drop "Offers out".

### 3.4 Lenses

`hiring_hub.js` built-in list: overview, **applicants** (icon `columns`, label `_t("Applicants")`, title `_t("Applications across jobs")`, gate `HIRING_HUB_GATE`, probe `can_open`, `props:{startTab:"applicants", placeLens:"applicants"}`), **offers** (icon `send`, label `_t("Offers")`, title `_t("Offers and joining checks")`, same gate/probe, `props:{startTab:"offers", placeLens:"offers"}`), interviews, bank. Place reporting `pb_hiring_hub:applicants` / `:offers`. HUB_LENS_GATES updated. Palette rows: "Applicants" (keywords: applications, candidates, pipeline, ứng viên), "Offers" (keywords: offer letters, joining, lời mời, nhận việc). VI labels: Applicants = Ứng viên; Offers = Lời mời — the module's existing word, decision 2026-10-21 (full names: "Hồ sơ ứng tuyển theo mọi vị trí", "Lời mời và kiểm tra trước ngày vào").

### 3.5 Learn (R7) and Access (R8)

- Anchors: `hi-applicants`, `hi-applicants-board`, `hi-offers`, `hi-offers-steps`, `hi-offer-row` (`repeats`), registered `"reserved": true` in `anchors.json`.
- `data.js` hub_hiring tabs: add applicants ("Applicants" / "Ứng viên", line: one pipeline across every role) and offers ("Offers" / "Lời mời", line: every offer, its papers, its check and its joining date) between overview and interviews; `practice-data.js` MENU hub hiring tabs likewise (quiet tabs, no replica); station `hiring` outline: one sentence each for the two tabs (EN+VI). Regenerate; `--check`; diff the .po (must be unchanged); bump `pb_learn` patch.
- Access: no sidebar change; the Screens lens is unaffected. Confirm by opening it after deploy.

## 4. Non-goals

No new models or fields (except the two KPI keys). No drag-and-drop across roles (Move to… menu only). No change to the role page, the drawer verbs, offer approval routes, or privacy rules. No Insights changes. No employee-portal changes.

## 5. Tests

Python (`pb_hiring/tests/test_registers_p9.py`, new, cloning the fixtures of `test_hiring.py` / `test_offer.py`):
1. `get_applicants` as hiring user returns cards from ≥2 roles; columns ordered by journey order; counts match `_pipeline` sums.
2. As a requester (base user) returns only their own roles' applicants; a masked card has only name, stage, interview dates.
3. Filters: family, role, recruiter, waiting_mine, late, search; cap at 600 with `capped=True` and `total` correct.
4. A move from the register via `journey_stage` works and refuses `joined`; mixed-role bulk move to a stage one role lacks returns a one-sentence refusal.
5. `get_offers`: steps counts; `waiting_mine` true for my open seat; docreq/bgv summaries; `joining_soon` window = 30 days inclusive; money absent for a non-team reader.
6. Overview KPIs `offers_waiting_mine`, `joining_soon` equal the register's filtered counts.
7. `offer_views.xml` `f_joined` filter now matches `state = joined` (regression for the bug).
8. Existing suites `test_hiring.py`, `test_offer.py`, `test_privacy_p4`, `test_joining_p6` still pass.
Chrome (local, then one walk on payobook.com after deploy by Fable): rail order; APPLICANTS board with ≥2 roles mixed, role chip visible, drawer opens from a card, bulk Move to works and the board refreshes, filters persist across reload; OFFERS strip and rows, a row's ⋯ menu shows only allowed verbs, "Joining soon" filter, Handed-to-Joiners link lands on People › Joiners; Overview tiles open OFFERS pre-filtered; Vietnamese labels fit two lines; console clean; `pb_learn` anchor tests pass.

## 6. Deploy (after Fable's go) — NORMAL tier

`-u pb_hiring,pb_learn` on p0clone first, then payobook, payobook_template, rize (service stop ~1–2 min; announce first via Fable). PO parse gate on the staged `.po` files. Per DB: asset signal + purge + version bump; **warm each bundle with one curl of the login page per DB after start** (ledger P2 deploy row). Cron snapshot before/after per DB; expected active counts payobook 37, rize 69, p0clone 26, payobook_template 0. Verify `latest_version`, served JS contains `startTab:"applicants"`. Push 19.1 after a clean deploy.

## 7. Report back

`docs/handovers/NAV_P3A_REPORT.md`: diff summary per file; test counts; Chrome evidence; Learn regen summary and .po diff; deviations; gotchas appended to the ledger; R11 self-score; the exact `-u` list; stop at the deploy gate first and return the report, then deploy on the go.
