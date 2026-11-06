# LEARNREV P4 — deploy record (by Fable, 2026-10-18 01:30–02:05 Sydney)

The Opus builder's session allowance ran out before its report; the Opus deployer was unavailable for the same
reason, so Fable ran the P1–P3 ritual directly: `/tmp/lrp4_deploy.sh` (a copy of P3's script with the module list
changed), as systemd unit `lrp4-deploy` under `flock -n /tmp/payobook-studio-deploy.lock`, staged from
`git archive HEAD` (7a3189e99) of the three changed modules into a clean `/tmp/deployP4`.

## Clone test before the deploy (`lrp4clone`, dump-based, AI off, jobs off, staged addons path)
513 tests, 2 failed, 0 errors — both known baselines (`pb_hub test_static` palette test with a partial stage, LR50;
`pb_learn test_questions.test_07b`, jobs off). `test_learnrev_p4`, `test_guide_truth`, `test_scenario` green.
Clone dropped with `--force`; filestore and staging removed. (Two earlier launches died with the ssh session —
see LR60.)

## Deploy
| Step | UTC |
|---|---|
| Lock taken | 13:29:01 |
| Service stopped | 13:29:13 |
| payobook / rize / payobook_template / abm `-u` | 13:29:14 / 13:30:05 / 13:30:43 / 13:31:20, all EXIT=0 |
| Service started | 13:31:57 |
**Downtime 2 min 44 s.** 0 ERROR/CRITICAL in the four upgrade logs and the service log after start.

| Module | all 4 DBs before → after |
|---|---|
| pb_learn | 19.0.20.5.8 → 19.0.20.5.9 |
| pb_formula_studio | 19.0.1.201.34 → 19.0.1.201.35 |
| pb_payruns | 19.0.3.0.3 → 19.0.3.0.4 |
Live trees hash-identical to the stage (sha1 of every file). Assets purged + version bumped + signalling row per DB.
Jobs: payobook 37 → 37, rize 69 → 69; abm (17) and payobook_template (20) re-enabled by the upgrade and switched
back off → 0. Guide switch True/True/True/unset, `payai.voice_enabled` True — untouched. No reworded Vietnamese in
the range → no overwrite load. payobook.com and rize.payobook.com HTTP 200.

## Live walk (payobook.com, QA Test, headless Chrome, 1440×900)
- Component treatment → Guide docked; Understand › **Start the lesson** → "Pay role · Step 1 of 7", the four lines
  (Look at / It means / It affects / Press) in the panel, the real "Pay role" header highlighted, nothing covered
  (`scratchpad/walk/p4live_lesson.png`).
- Right now, (i) buttons, path chips unchanged from P2/P3.
- Console: only the old brand-icon size warning.
Not walked live: checked Try (the QA user is not in the demo group on live — by design), the Indonesia variant
(needs a company country change), the replica fallback. All three were walked on the clone by the builder (B3, B4,
B6).

## Gotchas (ledger)
LR60 `nohup … &` inside an ssh one-liner is killed by SIGHUP when the ssh exits — run server jobs with
`sudo systemd-run --unit=<name>`; LR61 `/tmp/lrp4_test.done` / `.log` from an earlier run were owned by root/odoo, so
`rm`/`touch` failed silently and a waiter keyed on the marker fired at once — use unique file names per run; LR62 zsh
expands `[n]` patterns inside long ssh one-liners ("no matches found") — put remote scripts in files and `scp` them.
