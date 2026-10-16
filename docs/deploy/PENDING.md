# Pending deploys

Owner ruling 2026-10-11: ship every change to **payobook** (payobook.com, the
demo database) first and check it there. The other databases (`rize`,
`payobook_template`, `abm`) are upgraded in ONE batch when the owner says so.

- Add a row here when a change goes to payobook only. Remove it after the batch.
- `python3 tools/deploy_status.py` is the check that this list is complete — it
  compares the repo's version with each database's installed version, so a row
  forgotten here still shows up there.
- One addons directory serves every database: new Python/JS already reaches the
  other databases at the next restart. What waits is the per-database upgrade
  (views, data, translations, new fields). **A change that adds a new stored
  field cannot wait** — the other databases would error until upgraded; upgrade
  them in the same deploy.
- Batch recipe: the "normal" tier in the repo CLAUDE.md deploy contract,
  `-u <modules>` on each remaining database one at a time, asset purge +
  `web.assets.version` bump on each, then `deploy_status.py` must say nothing
  is pending. abm is retired: its upgrade turns its scheduled jobs back on —
  switch them off again after (see memory `abm-tenant-retired`).

The formerly frozen T3a/T3b/T3c entries are deployed on all five databases,
verified on 16 October 2026. The owner-approved demo account migration is also
complete. See [the close-out](2026-10-16-pending-work-closeout.md).

A concurrent performance change, `3c204362f` (`pb_formula_studio` 1.201.14 and
`pb_hr_payroll_formula` 1.148.10), entered deployment while this close-out ran.
The owner confirmed that the other session handles this deployment. Its rollout
covers all five databases; its own receipt closes those two module versions.
The completed tiers rollout does not overwrite or take over that work.

| Date | Module → version | What changed | Status |
|---|---|---|---|
| 2026-10-16 | biz_access → 19.0.1.6.1 | TIERS follow-up: the Employee/Staff switch refuses a person with a permission given by hand (mirrors `tools/tiers_switchover.py`). `-u biz_access` on all five databases in one run, asset purge + version bump each; abm jobs re-checked. | Deployed on all five 2026-10-16 (this session) |

## Completed batch — 16 October 2026

| Modules | Result |
|---|---|
| 2026-10-16 | pb_payroll_ai_insights, pb_payai_actions (screen files only, versions unchanged) | PayAI flicker while recording: the level meter and clock now redraw on their own (PayaiRecMeter), and unchanged helper turns and card icons keep their drawn copy instead of being re-inserted on every redraw. Looks-only tier on payobook: files + asset purge + `orm_signaling_assets` + `web.assets.version`, no restart; live check: 43 screen changes in 5 s of recording, none of them turns or icons (was 681 in 0.4 s). | Deployed on all databases 2026-10-16: payobook live-checked; rize, payobook_template, abm asset refresh (signaling + version bump), each bundle confirmed to carry the fix. |
| pb_me_portal_comm 1.0.0, pb_ask_hr 1.0.0 | Installed on all five targets, including missing glue/dependencies. |
| pb_me_portal 3.3.0, pb_ess_workforce 1.2.0, pb_onboarding 1.1.1, pb_rnr 1.2.0, pb_pay 3.6.0, pb_timeoff 1.6.0 | Queued portal updates and held QWeb/style edits reloaded on all five. |
| pb_training 1.2.5 | Upgraded everywhere already installed; remains absent on retired ABM. |
| biz_mail_debrand 1.1.0, pb_payroll_templates 1.0.2 | Combined-state reload and regression checks passed on all five. |

414 targeted deployed tests passed, plus four local migration guard tests.
Demo-first Chrome walk passed. The approved 12 demo conversions and five joiner
links are complete; the other four databases needed no account changes.

## Completed batch — 15 October 2026

The entries below are retained as rollout history; their former gates are closed.

| Date | Module → version | What changed | Status |
|---|---|---|---|
| 2026-10-15 | pb_payroll_ai_insights → 19.0.3.12.2, pb_learn → 19.0.20.5.4 | PayAI voice: the "Send recordings for transcription?" card and its Yes / No buttons are removed (owner ruling). The first tap on the microphone saves the agreement and records at once; "Use my voice" in the More menu turns the microphone back on without a card. Server gate unchanged. Voice switch description reworded. Normal tier: `-u pb_payroll_ai_insights,pb_learn` on payobook, asset purge + version bump; live bundle checked. No new stored field. | The batch |
| 2026-10-15 | pb_payroll_templates → 19.0.1.0.0 (new) | Approved template workspace: current employee records, two-tab monthly workbook, layout configurator, reviewed patch imports and Pay Run integration. Installed/tested on payobook; 18 server checks and Chrome draft payroll round trip pass. New tables belong to this module only; no new fields on existing models. Install with `-i pb_payroll_templates` on each rollout DB, then purge assets and bump `web.assets.version`. See `2026-10-15-payroll-template-workspace.md`. | Deployed on all five databases; see batch report |
| 2026-10-15 | pb_me_portal → 19.0.3.1.0, biz_access → 19.0.1.6.0, pb_zoho_bridge → 19.0.1.2.0, pb_demo → (bumped), pb_ess_workforce → 19.0.1.1.0 | TIERS T2 + T2b, portal accounts: every My Payobook page works for an employee login (share user) — sudo after an ownership guard, tokened downloads, own-photo route; Access screen Employee/Staff switch (`pb.access.set_account_type`); joiners' automatic accounts also become `hr.employee.user_id`; demo generator makes employee logins; leave apply + timesheet fix under sudo; fence now also keeps the backend for a hand-given permission (ledger T22). Normal tier: `-u pb_me_portal,biz_access,pb_zoho_bridge,pb_demo,pb_ess_workforce` on payobook, asset purge + version bump. No new stored field. pb_demo is payobook-only (not on tenants). Live walk done 2026-10-15: ess2.demo flipped to an employee login on the Access screen; as that login all 13 `/my` pages render, payslip page + PDF 200, photo 200, backend address → `/my`. | Deployed on all five databases; see batch report |
| 2026-10-15 | pb_me_portal → 19.0.2.2.0, pb_me_portal_website → 19.0.1.0.0 (new, auto-install) | TIERS T1, the fence: a plain employee (no role, no reports, no open approval seat) is bounced from `/bizapp`, `/web` and `/` to `/my`; the nine-dots corner shortcut and the "Apps" menu entry are not drawn for them (`docs/handovers/tiers/`). Normal tier: `-u pb_me_portal -i pb_me_portal_website` on payobook, asset purge + version bump. No new stored field. Batch needs the same `-i` on each DB. Live walk done 2026-10-15 (ess2.demo bounced, links gone; admin and ess1 — who has a direct report — keep the backend). | Deployed on all five databases; see batch report |
| 2026-10-14/15 | pb_me_portal → 19.0.2.1.1, pb_import_kit → 19.0.1.22.0 | MEHOME: the employee home (/my) redesign — greeting + sentence, Pay / Leave / This week cards, Needs you, grouped tiles with icons, Inter on the portal, VI (`docs/handovers/mehome/`). Normal tier: upgraded on payobook, asset purge + version bump done. No new stored field. | Deployed on all five databases; see batch report |
| 2026-10-15 | pb_learn → 19.0.20.5.4, pb_payroll_ai_insights → 19.0.3.12.2 | Subsequent concurrent PayAI/Learn demo updates included in the final combined rollout; two PayAI Actions test files synchronized as well. | Deployed on all five databases; see batch report |
