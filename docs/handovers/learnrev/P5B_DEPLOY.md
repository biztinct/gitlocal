# LEARNREV P5b — deploy record (2026-10-20 21:59–22:03 Sydney)

Merged `learnrev-p5b` (23 commits) into 19.1 at 39352e267. One conflict, in `pb_payai_actions/tests/test_payai_p4.py`:
both PayAI's test_08 update and P5b rewrote the same lines. They are now one `said(step, lang)` helper, checked
against the merged content. Versions were bumped at 1bb63c26f. The 12 modules were staged from `git archive HEAD`
into a clean `/tmp/deployP5b`. The deploy ran `/tmp/lrp5b_deploy.sh` as unit `lrp5b-deploy` under
`flock -n /tmp/payobook-studio-deploy.lock`. Peer sessions gitlocal-19, gitlocal-94 and gitlocal-b6 were told before
and after. gitlocal-19 (PayAI) reviewed the pb_payai_actions change (test + manifest only) and cleared it.

**Databases (new rule, CLAUDE.md 2026-10-20):** payobook, rize, payobook_template, p0clone. ABM is retired and was
not touched.

Dry-run (LR33): the server differed in exactly P5b's 34 files plus the 12 manifests. No server-only file would have
been deleted.

| Step | UTC |
|---|---|
| Lock taken | 10:59:10 |
| Service stopped | 10:59:30 |
| `-u` on payobook | 10:59:31, EXIT=0 |
| `-u` on rize | 11:00:27, EXIT=0 |
| `-u` on payobook_template | 11:01:14, EXIT=0 |
| `-u` on p0clone | 11:01:59, EXIT=0 |
| Service started | 11:02:47 |

**Downtime 3 min 17 s.** There were 0 ERROR/CRITICAL lines in the four upgrade logs or the service log afterwards.
The live trees are sha1-identical to the stage.

Versions on all four databases:

| Module | Version |
|---|---|
| pb_approval_config | 19.0.1.6.5 |
| pb_formula_studio | 19.0.1.202.9 |
| pb_insights | 19.0.5.3.1 |
| pb_learn | 19.0.20.5.11 |
| pb_pay | 19.0.3.6.2 |
| pb_payai_actions | 19.0.4.2.2 |
| pb_payrun_ledgers | 19.0.1.3.4 |
| pb_people | 19.0.1.2.7 |
| pb_records | 19.0.1.5.2 |
| pb_settings | 19.0.1.9.2 |
| pb_statutory | 19.0.1.4.3 |
| pb_workforce_insights | 19.0.1.1.2 |

**Vietnamese:** every changed msgstr is a `code:` term, which is read from the .po when the service starts, so no
overwrite load was needed. pb_learn's vi_VN.po was untouched.

**Scheduled jobs:** the guard now restores each database's own pre-upgrade set.

| Database | Jobs before → after |
|---|---|
| payobook | 37 → 37 |
| rize | 69 → 69 |
| p0clone | 26 → 26 |
| payobook_template | 0 → 0 |

The upgrade re-enabled 24 jobs on payobook_template; the guard switched them back off.

**Settings:** the Guide switch and every `payai.*` / `pb_payai*` parameter were diffed before and after on all four
databases and are identical. `payai.voice_enabled` is still True.

**Live check** (payobook.com, QA user, headless Chrome at 1440×900):

| Check | Result |
|---|---|
| Served `learn_content.json` | 42 lessons, 297 steps. The only steps without top-level four lines are the 3 country-variant steps, which carry them inside `variants`, and the 3 steps of the retired `sc_mapping`. |
| Approvals tip | reads "gõ DUYỆT trên thẻ của nó" |
| People › Employees, Guide › Understand › Start the lesson | "Step 1 of 9": the four lines beside the highlighted real numbers line, plus a "Was this helpful?" thumbs pair |
| Same step in Vietnamese ("Hiểu rõ", "Bước 1 trên 9") | correct |
| Console, after a reload | no errors |

Screenshots: `scratchpad/walk/p5b_live_lesson.png`, `p5b_live_lesson_vi.png`.
