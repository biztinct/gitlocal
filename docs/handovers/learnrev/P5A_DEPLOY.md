# LEARNREV P5a — deploy record (2026-10-18 09:38–09:43 Sydney)

Owner asked to deploy whatever was safe before their weekly limit ran out; P5b (Opus, lessons + Vietnamese) was still
building in its worktree and is NOT in this deploy. Staged from `git archive HEAD` (7e50bc1f4) of the 12 changed
modules into a clean `/tmp/deployP5`; `/tmp/lrp5_deploy.sh` (P4 script, module list changed, plus a targeted VI
fix) as systemd unit `lrp5-deploy` under `flock -n /tmp/payobook-studio-deploy.lock`. Peers gitlocal-d2 / gitlocal-48
told before and after.

Dry-run (LR33): `rsync -rcn` per module showed only P5a's files; no server-only file would be deleted.

| Step | UTC |
|---|---|
| Lock taken | 22:38:29 |
| Service stopped | 22:38:46 |
| payobook / rize / payobook_template / abm `-u` | 22:38:47 / 22:40:00 / 22:40:58 / 22:41:55, all EXIT=0 |
| Service started | 22:42:51 |
**Downtime ≈ 4 min 5 s.** 0 ERROR/CRITICAL in the four upgrade logs; service log after start only a `mail_presence`
concurrent-update line (unrelated, common).

Modules (all 4 DBs): pb_learn 19.0.20.5.10, pb_hub 19.0.1.11.4, pb_statutory 19.0.1.4.2, pb_people 19.0.1.2.6,
pb_import 19.0.1.6.2, pb_approval_config 19.0.1.6.4, pb_records 19.0.1.5.1, pb_pay 19.0.3.6.1,
pb_govt_reports 19.0.1.2.2, pb_time_hub 19.0.1.3.2, pb_formula_studio 19.0.1.201.36, pb_hr_payroll_formula
19.0.1.148.17. Live trees sha1-identical to the stage.

Vietnamese: instead of a module-wide overwrite load (LR20/LR29 risk), a targeted update per DB, only where the stored
value was still the old wording: `ir_model_fields.field_description` "Đã tính trong tổng khác" → "Đã tính trong một
tổng khác" (1 row/DB) and the same phrase inside the `net_role_source` help (1 row/DB). pb_hub's search strings are
code terms (read from the .po at runtime) → no DB load needed.

Jobs: payobook 37 → 37, rize 69 → 69; abm (21) and template (24) re-enabled by the upgrade, switched back off → 0.
Guide switch True/True/True/unset, `payai.voice_enabled` True — untouched. Assets purged + version bump + signalling.

Live check (payobook.com, QA user): `learn.guide.rpc_guide` answers for all 8 new screens (statutory, employees,
import, matrix, records, payreview, govreports, wftime) with fields + right-now (providers on statutory, import,
matrix, records); Statutory screen renders; top search reads "Search screens and actions…"; Learn page opens; console
clean apart from the usual info log. Not checked live: the feedback card (QA user is not an admin) — walked on the
clone (P5A_REPORT B3).

P5b deploys separately when it lands.
