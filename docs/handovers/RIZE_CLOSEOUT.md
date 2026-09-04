# RIZE Programme — Closeout (2026-09-02)

The RIZE HR blueprint (`docs/design/rize-hrms-blueprint.html`) is implemented end to end on the
live `payobook` database (https://payobook.com): all 10 modules, all 6 "Going further" wow
features, all 8 owner decisions as recommended, plus D9 (demo DB — test data kept).
Twelve phases, twelve Opus implementation cycles, each deployed, browser-validated and
committed; 123 gotchas recorded in `docs/handovers/RIZE_LEDGER.md` (R1–R123).

## What is live (module → where you see it)

| Phase | Module (19.0.1.0.x) | What it does | Where |
|---|---|---|---|
| P0 | pb_lifecycle | Journey checklists (templates/cases/tasks), check-ins, peer-feedback token forms, HR letter engine (PDF → vault), daily reminder/escalation job | New **Lifecycle** mission on the rail → Journeys lens; `/journey/t|f/<token>` pages |
| P1 | pb_zoho_bridge | Zoho→Payobook receiving door (`POST /api/zoho/webhook`), arrival rules, strict field whitelist, file-upload fallback, auto portal logins | Integrations connector "Zoho People — inbound" (id 1232); Arrivals list; ⌘K "Upload joiner file" |
| P2 | pb_assets | Asset register (physical + digital), per-country codes, handover history, approval-chained requests, exit return tasks, exports | People hub → **Assets** lens; `/my/assets` |
| P3 | pb_onboarding | Buddy programme w/ eligibility, HRBP rules, 9-step joiner journey w/ auto-steps (poster, day-1 ICS, credentials), orientation batches, 30-60-90 check-ins, new-hire pulse, **journey timeline**, **living org chart** | Lifecycle → **New joiners**; `/my/journey`, `/my/buddy`, `/my/orgchart` |
| P4 | pb_offboarding | Resignation (portal, manager→HR approval, notice policy), exit journey, KT items w/ 15-day pings, IT/HR/Finance/Admin clearances, **final-settlement guard**, experience letter, farewell | Lifecycle → **Exits**; `/my/resignation`; banner on the F&F form |
| P5 | pb_probation | Country policies → trial end, probation state on every employee, 3–5 peer evaluation w/ deadlines, consolidated report, 1:1, pass/extend/fail w/ letters, training gate | Lifecycle → **Probation**; card on `/my/journey` |
| P6 | pb_pip | Request → coaching → growth plan → check-ins → evaluation → outcome; strict PIP-only visibility; auto-close on resignation | Lifecycle → **Growth plans** (PIP groups only); `/my/growth` |
| P7 | pb_comp_ben | Pay packages (proposed lines, activate), awards ledger w/ approval + letters + **one-off pay-run feed**, payroll calendar w/ cut-off reminders, benefit plans, finance pack on final approval | Pay Run hub → **Calendar**, **Awards**; `/my/compensation` |
| P8 | pb_rnr | Values, praise nominations (manager agree → HR recognise), cash awards → P7 feed, quarterly winners, mood-board digest, **recognition wall**, **anniversary engine** | People hub → **Praise**; Home → **Wall**; `/my/recognition` |
| P9 | pb_budget | Budgets on `wfp.budget.actual` (D2): XLSX upload, auto-actuals mirroring the Cost Explorer, HR-ops/admin expenses, scoped visibility, **heat view**, XLSX/PDF | Insights hub → **Budget** |
| P10 | pb_contract_lifecycle | Intern/contractor typing, two-month decision workflow, extensions/conversions as NEW contracts (D1), conversion via probation engine, terminate → exit case | Lifecycle → **Contracts** |
| P11 | pb_vendor_access | Vendor register + agreements w/ renewal alerts, 23-role plain-English catalogue, access delegation (temporary auto-revert / permanent) w/ audit, exports | Settings → **Vendors**, **Access & delegation** |

Platform seams added on the way (all soft registries, test-enforced): `pb_lifecycle_lenses`,
`pb_payhub_lens`, `pb_home_hub_lens`, `pb_insights_hub_lens`, `pb_settings_category`
(pb_people_hub already had one). ⌘K blocks 2100–3240 used; next free 3300.

## Logins

- **Admin**: `ash@biztinct.com` / `Rize#Payobook2026` — reset in P0 under owner
  pre-authorization because the supplied password did not work. **Owner: change it.**
- Temporary validator (P0): `igc1.validator` / `RizeP0!2026` (uid 2065) — **deactivate**.
- Demo ESS logins given passwords for portal tests: `ess1.demo@payobook.com` / `RizeP7!2026`,
  `ess2.demo@payobook.com` / `RizeP2!2026` — originally passwordless by design; clear if wanted.
- Test actors (all @example.com, company 5 "Payobook Vietnam JSC"): `rize.p3.joiner` /
  `RizeP3!2026`; `rize.p4.boss|leaver|zoho` / `RizeP4!2026`; `rize.p6.hr|plain|alpha|lifecycle`
  / `RizeP6!2026`; `rize.p8.mate` / `RizeP8!2026`; `rize.p9.head|finance|plain|wfp|both` /
  `RizeP9!2026`. Keep as demo actors or remove.

## Switches worth knowing (config parameters, live values)

| On | Off (how to enable) |
|---|---|
| Onboarding: poster, pulse, buddy mails; auto-steps | — |
| Offboarding: `farewell_mail=1` (dept-only, cap 60) | — |
| Probation: `auto_trigger=1` (nightly review opening, cap 20) | — |
| Comp&Ben: `finance_pack=1`, `letter_send=1`, `calendar_reminders=1`; finance email is a test address `rize.p7.finance@example.com` → set the real one | — |
| Budget: `auto_actuals` on (daily) | — |
| Vendors: alerts on (45-day horizon), delegation mail on | — |
| Contracts: `auto_trigger=1` (60-day lead, cap 20) | — |
| — | RnR: `pb_rnr.digest_mail`, `anniv_mail`, `manager_mail`, `thanks_mail`, `hr_alert_mail` all **0**; to enable the mood board set `digest_mail=1` AND clear `digest_test_email` (currently `rize.p8.digest@example.com`); set a real `hr_alert_email` |
| — | PIP: `employee_view=1`, `manager_sees_own=1` (defaults; switchable) |

## Wiring the real Zoho later

Connector **id 1232** "Zoho People — inbound" (Integrations cockpit) holds the api key
(admin-only field). Zoho's webhook must POST to the PUBLIC hostname:

```
curl -X POST https://payobook.com/api/zoho/webhook -H "Content-Type: application/json" \
 -d '{"jsonrpc":"2.0","method":"call","params":{"connector_id":1232,"token":"<API KEY>",
 "data_type":"employee","records":[{"Zoho_ID":"…","EmployeeID":"…","FirstName":"…",
 "LastName":"…","EmailID":"…","Department":"…","Designation":"…","Dateofjoining":"YYYY-MM-DD",
 "Employeestatus":"Active","Employment Type":"Intern"}]}}'
```
Arrivals land in the connector's company (currently Payobook Vietnam JSC — editable field).
Rules table "Arrival rules" maps status words → onboard / offboard / update / review.

## Money path facts

- Awards/bonuses reach a payslip ONLY through the Awards lens "Queue" action (preview first);
  the target run must be draft/officer stage and its pay scheme must carry an input component
  coded **`INCENTV`** (Mapping screen) — otherwise the feed refuses and says why.
- Awards flip to Paid automatically when the run's final approval lands.
- Final settlement cannot be closed while assets are out, clearances pending, or blocking
  tasks open; the error names each blocker.

## Owner decisions still open

1. **Push**: 56+ commits unpushed on branch `19.1` (whole programme + earlier streams).
2. **Award month vs run month** (R81): the Awards queue dialog lists awards whose month matches
   the run; a September award can't be put into the August run from the screen.
3. **Nightly automations now real**: probation reviews and contract-decision reviews open
   themselves and email managers (`auto_trigger=1` in both) — confirm wanted.
4. **HR mail fallback**: `ash@biztinct.com` sits in the lifecycle-manager group and therefore
   receives every HR escalation; move that role to real HR people (`pb_offboarding.<dept>_user_id`,
   HR-partner rules, clearance owners currently fall back to uid 2065).
5. **Dark mode** on native list views is broken product-wide (biz_theme, pre-existing; R20).
6. Payobook→Zoho outbound deliberately not built (D8).

## Demo data left in place (D9)

Journey cases 2/3/16/19–27, probation reviews 1–4, PIP plans 1–6, settlements 82 (closed) /
83 (blocked example), pay runs 791/1396 (mutated: INCENTV lines) /1525, packages 1–5,
awards 1–9, nominations 1–8 + Q3 2026 winners, budget rows for company 5 (332) + 2 expenses,
contract reviews 1–10 + new contracts 14589–14592, vendors 11/12, assets VN-LT-00001…7,
test employees 17118–17148, test departments 656/657/658.

## Commits

P0 9989f7e8 29572b99 · P1 46e37131 35c1bb6e · P2 ae49df3e 2e6a24e9 · P3 738f85e5 ba04f9dc
7adf3b29 cdbc999e a386be80 · P4 fff7465e a3ea652a bf728c82 · P5 9cc0c2f9 ad862d93 83a14e3a
· P6 357cc2a3 ae900ec6 · P7 e1c67b05 aef0c2f2 · P8 339bc956 b21ddfab e7a88df1 · P9 3c8969db
8fbba339 e24963e3 1f46dd03 · P10 434c7d04 d9bc701b 492c3a2e 6ebc75ae · P11 3d5223dc f947ec65
(+ one ledger commit per phase). Design doc 9d8616a4; handovers 6727ac9a 4e96dade 3c16c2c0 4311af7b.
