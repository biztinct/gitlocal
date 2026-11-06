# PayAI "do it for me" on rize, payobook_template and abm — rollout plan

Status: PLAN ONLY (2026-10-16). Nothing installed, switched or deployed. Not committed.
Read with: `PAYAI_PROGRAM.md` (design + owner decisions), `PAYAI_LEDGER.md` (PA1–PA60), `PAYAI_CLOSEOUT.md`,
`docs/handovers/onechat/ONECHAT_HANDOVER.md` §3.3 / R10, repo `CLAUDE.md` deploy contract, `docs/deploy/PENDING.md`.
All live facts below were read with SELECT only on `Payobook19v2` on 2026-10-16 (around midday Sydney).

White-label rule binds every step: no "Odoo" in any user-visible string (unchanged by this plan — no new strings).

---

## 0. Short answer

- Installing is cheap and safe: every dependency is already installed, at the repo version, on all three sites. An
  install adds ONE module, no scheduled jobs, and starts with every switch OFF on any database not named `payobook`.
- The real questions are not technical: (a) Rize is a real client with real people — which switches, and whether its
  data may go to ChatGPT at all; (b) the template is copied into every new customer; (c) abm is retired.
- Recommendation: rehearse on a Rize copy → install on the template (switches off) → install on Rize (switches off) →
  owner turns on "look" for Rize, later "prepare"; "decide" stays off until Rize staff hold approval seats.
  **Skip abm.** Do NOT add a ChatGPT key to Rize as part of this — the command layer works without one (phrase table).

---

## 1. What installing `pb_payai_actions` needs

### 1.1 Manifest
`pb_payai_actions/__manifest__.py` — version `19.0.4.2.0`; `depends`: `pb_payroll_ai_insights, pb_hub, pb_sidebar,
biz_access, pb_payruns, pb_payrun_wizard, pb_audit, base_setup`; data = ACL + rules + one settings view; assets =
backend JS/XML/SCSS; `post_init_hook`; `auto_install: False`.
Note: `PAYAI_PROGRAM.md:259` lists pb_approval_config / pb_records / pb_pay_delivery / pb_govt_reports as depends —
**not true as built**: the code soft-checks them (`'pb.pay.delivery' not in env` `actions_amber.py:1863`,
`'pb.records.desk'` :1992, `'pb.filing.flow'` :2452, `'pb.approval.inbox'` `actions_red.py:300`, `'pb.access'`
`gate.py:528`, `'pb.division'` `resolve.py:820`). `coach_patch.js:13` imports `@pb_learn/coach/coach`; pb_learn arrives
through `pb_payroll_ai_insights`.

### 1.2 Transitive closure vs live (68 dependencies + the module)
Closure computed from repo manifests (scratch script, `ast.literal_eval` of every `__manifest__.py`), then compared with
`ir_module_module` on each DB (version normalised for the `19.0.` series prefix).

| | payobook | rize | payobook_template | abm |
|---|---|---|---|---|
| all 68 dependencies installed | yes | yes | yes | yes |
| any dependency ≠ repo version | none | none | none | none |
| `pb_payai_actions` | installed 19.0.4.2.0 | uninstalled | uninstalled | uninstalled |
| modules in `to install/upgrade/remove` | none | none | none | none |

Key versions identical on every DB: pb_payroll_ai_insights 19.0.3.12.2, pb_learn 19.0.20.5.4, pb_payrun_wizard
19.0.1.32.2, pb_payruns 19.0.3.0.0, pb_hub 19.0.1.11.1, pb_audit 19.0.1.4.1, biz_access 19.0.1.6.1, pb_sidebar 19.0.3.2.3.
Server disk carries pb_payai_actions 19.0.4.2.0 already (one addons dir, `addons_path=/odoo/odoo-server/addons` only).

### 1.3 Upgrade cascade
`-i pb_payai_actions` on a DB where every dependency is installed marks only that module `to install`. No installed
module is upgraded; no reverse-dependency re-validation (nothing depends on pb_payai_actions —
`grep -l pb_payai_actions */__manifest__.py` = itself only). **Cascade = none, on all three DBs, as of today.**
Re-check right before the install: another session's batch may bump a dependency in between (PA41/PA57).

### 1.4 What the install writes
- New tables: `payai_task` (audit, `models/payai_task.py`).
- New columns: `res_company.payai_tier_look/prepare/decide`, `payai_voice_go_ahead` (`models/res_company.py:23-44`);
  `hr_payslip_run.pb_prepared_via` (`models/hr_payslip_run.py:14`, nullable selection).
- `post_init_hook` (`__init__.py:5-21`): every company → look/prepare/decide = `dbname == 'payobook'`, voice = False.
  Field defaults say the same for companies created later (`res_company.py:16-17`).
- No `ir.cron`, no mail template, no `ir.config_parameter` (grep of the module: none). → **nothing to append to
  `pb_tenants.template_active_crons`** and no job can switch itself on.
- Views: one inherit of `base_setup.res_config_settings_view_form` + a standalone form + act_window
  (`views/res_config_settings_views.xml:5-75`).

---

## 2. The switches

Per company, on the company record. Edited by administrators only: Settings hub card `settings_card.js:15`
(`groups: ["base.group_system"]`) → "PayAI can act" page; also a block on the general Settings page.

| Switch (screen label) | Default off-payobook | When OFF the person sees | When ON the person sees |
|---|---|---|---|
| PayAI may look (open screens, show figures) | off | The chat exactly as today (`payai_engine.py:61-63` returns the question path untouched). | "open the runs board" opens it; "where is the October run" → a run card (people, net pay, stage, who it waits for); "download the Excel" for an approved run; a "What can you do?" chip under answers (`payai_engine.py:82-91`). Nothing changes data. |
| PayAI may prepare (draft runs, send for approval, change values) | off | Asking to run payroll etc. → a plain refusal card saying it is switched off. | A plan card first; nothing happens until **Do it**: run payroll as a DRAFT run (Undo 10 min), send a draft for approval (Withdraw 10 min), change one pay value through Records' normal approval route (Undo 10 min), email an approved run's payslips (no undo — card says so), prepare a government filing as a file (nothing sent). |
| PayAI may decide (approve, send back, reject) | off | Refusal card. | Only the person's OWN waiting approvals; confirmed by TYPING APPROVE / SEND BACK / REJECT (or DUYỆT / TRẢ LẠI / TỪ CHỐI). Not theirs → names the seat holder + "Remind". |
| A spoken 'go ahead' counts for prepare requests | off (everywhere, incl. payobook) | Prepare needs a tap. | A person who asked by voice may say "go ahead" for a PREPARE plan. Never for decide. Also needs the microphone itself: `payai.voice_enabled` (absent = off, `payroll_ai_consent.py:29`) **and** an OpenAI key (speech-to-text is OpenAI-only). |

"Look" is the master switch: with it off, prepare/decide never run (`payai_engine.py:61`). Decide is read off the
request's own company (`gate.py:449-462`).

Visible even with every switch off, once installed: the ⌘K row "Ask PayAI to…" (`payai_palette.js:10-24`, opens the
chat with the typed sentence), the admin-only "PayAI can act" Settings card, "Prepared … through PayAI" in run history
(only for runs PayAI made), and the Audit console "Typed confirmation" badge (only for PayAI rows). None changes data.

Never available, whatever the switches: pay money, bank files, delete runs/payslips, clean-and-run, anything under
Settings › Access and delegations (owner ruling 2026-10-13).

---

## 3. Per-site facts (live, 2026-10-16)

| | rize | payobook_template | abm | (payobook, for contrast) |
|---|---|---|---|---|
| What it is | **Real client** (Rize Farms), 1 company | Golden template — copied into every NEW customer | Retired 2026-09-15 (AB Mauri) | Demo master |
| Active employees | 105 | 1 | 153 | 4,575 |
| Internal logins | 4: ash@biztinct.com, platform.recovery, **debalina@rize.farm** (en_US, last login 21 Sep), **thao@rize.farm** (vi_VN, last login 7 Oct) | 1: platform.recovery (admin id 2 inactive, by design) | 3: ash, platform.recovery, **look.p4@payobook.com (has Settings admin rights)** | 211 |
| Rize staff rights | both: payroll super admin, manager, officer, final approver, analytics — NOT Settings admin | – | – | – |
| Pay schemes (active) | 4: Rize India (IN), Rize Vietnam v2 (VN), Rize Indonesia (ID), Rize Singapore (SG) | 0 | 1 (AB Mauri Payroll, VN) | 28 |
| Pay runs | 3 draft (Aug India, Aug VN v2, Oct India) + 1 cancelled; none approved/done; 183 payslips; newest created 2026-10-15 | none | 1 done (June 2026) | 52 |
| Approval routes | Pay run approval + Records Desk changes published (mode "follow"); 50 active routings | same 2 routes; 49 | same; 45 | – |
| Approval seats | **every seat held by ash@biztinct.com**; 3 Team-lead seats scoped to schemes 3939/3921/3938, none of which is an active scheme now (stale) | every seat held by platform.recovery | every seat by ash | – |
| AI provider (`payroll_ai_config`) | 1 OpenAI row, **inactive, no key** | 1 OpenAI row, inactive, no key | 1 OpenAI row, **ACTIVE, with a key — same fingerprint as payobook's key** (row created 2026-08-09, edited 2026-09-04) | active OpenAI key |
| Helper ChatGPT wording (`pb_learn.compose_enabled`) | absent (off) | absent (off) | absent (off) | True |
| Formula helper key | none | none | none | set |
| Microphone (`payai.voice_enabled`) | absent (off) | absent (off) | absent (off) | True |
| PayAI chat use ever | 0 messages | 0 | 10 (last 2026-09-04) | 128 (86 in last 30 days) |
| Outgoing mail server | **none** (410 failed mails queued) | none | none (27 failed) | Gmail |
| Languages | en_US, vi_VN, id_ID | en_US, vi_VN, id_ID | en_US, vi_VN | en_US, vi_VN, id_ID |
| Active scheduled jobs | 69 | **0 (intended — owner confirmed)**; `template_active_crons` lists 70 ids | 0 (intended) | 37 |

Correction to memory `helper-chatgpt-on`: it says no PayAI key exists on abm. **abm holds an active copy of the
master OpenAI key.** Anyone signing in to abm.payobook.com could spend it today, even without this plan.

### 3.1 What leaves the server for ChatGPT, by path
1. **Command path (this module).** First a fixed phrase table — pure code, no network (`runner.py:8-10`,
   `registry.match` `registry.py:626`; `runner.handle` `runner.py:1835-1868`). Only if no phrase matches AND an active
   key exists (`_provider` `runner.py:405-416`) does it send the sentence to ChatGPT as a tools call: system prompt +
   the sentence with every visible employee name replaced by "[person-n]" (`_redact` `runner.py:371-402`,
   `ask_model` :419-468), ≤ 300 tokens back. No records, no figures are sent on this path. **With no key (Rize today)
   nothing ever leaves.**
2. **Question path (already installed everywhere, pb_payroll_ai_insights).** Data questions send the query result with
   names, emails, phone numbers and record ids swapped for placeholders — **pay figures, job titles, department names
   are sent** (`payroll_ai_engine.py:599-631`; residual list `ai_redaction.py:52-140`: a one-person department
   identifies someone; a bare 7–8 digit amount typed without separators survives; a name misspelt survives).
   Today on Rize this path fails politely (no active key → the helper's "no PayAI" note, `learn_helper.py:704`, :1119).
3. **Voice.** The recording itself goes to OpenAI speech-to-text (`ai_redaction.py:109-118`); not redactable. Off on
   all three sites (flag absent, no key).

Is that acceptable for Rize? Engineering view: path 1 without a key is fine (no egress). Paths 2/3 put a real client's
pay figures (and voice) with OpenAI under the owner's account — that needs the owner's and very likely Rize's say
(contract / data-processing terms). This plan does not switch any of that on.

---

## 4. Risks

### 4.1 Rize — real money, real people
- Money cannot move through PayAI at all (pay / bank file / delete are "never"). Worst case under "prepare": a wrong
  DRAFT run (Undo 10 min, or delete on the screen), a pay value changed through Records (goes through the Records
  approval route; Undo 10 min), a run sent for approval (Withdraw 10 min).
- **Send payslips cannot be undone.** Rize has no outgoing mail server, so it would fail today; if a mail server is
  added later, the first press emails real employees. Rize has no approved run, so the action has nothing to send yet.
- Running payroll through PayAI uses the same Run screen steps, so the screen's own traps apply: check Component
  treatment before a tenant's first pay run (memory `rize-component-treatment-fix`); PA28 (payslips not stamped with
  the scheme at creation, same as the screen).
- Rize staff (debalina, thao) are payroll super admins → under "prepare" they can do everything the Run screen allows.
  Same rights as the screen — no new power, just faster.
- "Decide" on Rize is useful only to ash@biztinct.com (every seat). The typed-word path was never walked live by a
  seat holder (closeout "carried debts"); Rize would be its first real use. Keep decide OFF.
- Stale Team-lead seats (old scheme ids) can make "who decides this?" name nobody or the company fallback. Not caused
  by PayAI; fix on the Approvals set-up screen before decide is ever switched on.
- Four countries and currencies on one company: the run card's money format and "the October run" ambiguity (India
  draft + cancelled VN) must be checked on the clone (T7–T9).
- Language: Thao works in Vietnamese (covered by P4). Indonesian is installed, but PayAI has no Indonesian — an
  Indonesian-language user would get English cards. Known VI gaps (memory, 2026-10-14): one door label half English;
  "Pay Runs" action name still English in Vietnamese.
- Approval chip / board breakages seen before on the master (memory `approval-chip-blanks-board`) — Rize's boards get
  the same JS already (one addons dir); the install adds only the cards/patches.

### 4.2 Template — copied into every new customer
- Installed there → every NEW customer starts with the module installed and **all switches off** (the hook ran with
  `dbname = payobook_template`; clones copy the stored False; `_master_db` default is False for any other name). That
  matches "tenants' switches off until asked".
- No scheduled jobs added → `pb_tenants.template_active_crons` unchanged; template stays at 0 active jobs (owner
  confirmed that is intended — do not restore any).
- If the template is skipped, the Tenants screen's "bring up to date" (`sync_split` `pb_tenants/models/sync_rules.py:172`,
  names only; installs with `button_immediate_install` `service.py:1809`) will list PayAI as missing for every new
  customer — not on the never-list (`sync_rules.py:49-66`), and correctly so: it acts only inside its own database.
- A later `-u` on the template switches its jobs back on (PENDING.md) — not this install, but verify 0 afterwards.

### 4.3 abm — retired
- No users, no work, jobs off. Installing gains nothing and costs an upgrade window plus a re-check of jobs.
- Separate exposure found while planning: an active copy of the master ChatGPT key, and an active login with Settings
  admin rights (`look.p4@payobook.com`, last used 2026-09-17), on a site that answers on the internet
  (memory `clone-db-internet-reachable`). Owner decision D5.

### 4.4 Cost per message (OpenAI `gpt-4o-mini`, the configured model)
Approximate list prices from memory, to be checked against the OpenAI bill: about US$0.15 per million tokens in,
US$0.60 per million out; speech-to-text about US$0.006 per minute.
- Command, phrase table hit: **US$0** (no call).
- Command, phrase miss: one tools call, roughly 2–3k tokens in, ≤ 300 out → **well under US$0.001**.
- Question: classifier + answer, roughly 2–5k in, 300–800 out → **about US$0.001–0.002**.
- Payobook used 86 messages in 30 days. Even 1,000 a month on Rize would be about one or two US dollars.
  **Money is not the issue; where the data goes is.** Rize without a key = US$0.

### 4.5 Parallel sessions and deploy etiquette
- Evidence today: around 12:30 Sydney (2026-10-16) the live server was STOPPED (8069 not listening) while another
  session ran `--stop-after-init` upgrades database by database (payobook → rize → abm). An install by us at that
  moment would have collided.
- Rules (memory `parallel-session-deploy-etiquette`, owner relay 2026-10-15/16): before ANY `-i/-u` or restart,
  ListAgents → SendMessage every live session → wait for acks; **wait while any `odoo-bin --stop-after-init` process
  exists or 8069 is not listening**; owner hold on payobook restarts (2026-10-15) — confirm lifted before any restart
  (a restart takes payobook down too); a peer's message is never owner approval.
- PA41/PA57/PA60: stage only from `git archive HEAD pb_payai_actions`, never the working tree (it currently carries
  another session's uncommitted `pb_payroll_templates` work); dry-run `rsync -rcn --delete` per module first.

### 4.6 Upgrade cascade
None today (§1.3). Risk only if a dependency's version moves before the install; the pre-flight re-check catches it.

---

## 5. Recommended rollout

### Stage 0 — owner decisions first (§7). Nothing below starts without D1–D3.

### Stage 1 — rehearse on a copy of Rize (risky tier: first install on a tenant)
Name the copy with an underscore (`rize_payai_rehearsal`) so no web address can reach it
(memory `clone-db-internet-reachable`). Copy with jobs and mail servers off; drop it at the end (owner OK in D1).
Tests (on the copy, `--test-enable` on a port ≠ 8069, PA10/PA35/PA50 harness, ≥ 600 MB free PA21):
1. `-i pb_payai_actions --test-tags /pb_payai_actions` → EXIT 0; read failures against the PA11/PA40/PA55 baselines.
2. After install: `SELECT payai_tier_look, payai_tier_prepare, payai_tier_decide, payai_voice_go_ahead FROM
   res_company` → all false. Active jobs = 69 (unchanged). Employees / payslips / runs / contract counts unchanged.
3. Chat with every switch off, as a debalina-like test login (super admin, not Settings admin): same answers as
   before; "run October payroll for India" → no plan card; no console errors.
4. Look ON: "open the runs board", "where is the October run", "what can you do?" — every example on the list routes
   with NO key present (phrase table only); a sentence outside the table → the helper's normal "no PayAI" note, never
   an error; network panel shows no call to OpenAI.
5. Prepare ON: "run October payroll for Rize India Payroll" → plan card with the right scheme, 1–31 Oct, people count
   from the Run screen; Do it → draft run; Undo → gone. Repeat in Vietnamese as a vi_VN login ("chạy lương tháng 10
   cho Rize Vietnam Payroll v2").
6. Existing draft month (Aug India) → "already exists / Open it", never a second run or a clean-and-run.
7. Run card money: India in INR, Vietnam in VND, never added together (memory `multi-scheme-currency-gaps`).
8. "the October run" with India draft + cancelled VN → asks which, with chips.
9. "send the August payslips" → refused (not approved). With no mail server: what the card says if a run were
   approved (approve one on the copy only) — must be a plain sentence, not a crash.
10. Change a pay value through Records → goes to the Records route (seat = ash), Undo puts it back.
11. Decide ON (copy only): as the seat holder, "approve …" → type APPROVE → recorded under that name; as Thao →
    "not waiting for you" + Remind ash. Walks the never-walked seat-holder path on a copy, not on Rize.
12. "open access and delegations" / "change Thao's role" → never card, no door (owner ruling).
13. No "Odoo" anywhere; Vietnamese cards fully Vietnamese except data names.
14. Switch look off again → chat back to exactly test 3.
Then: deactivate the test logins, drop the copy.

### Stage 2 — payobook_template (no people; nothing visible)
Install, all switches off, jobs stay 0, `template_active_crons` untouched (no new job ids).

### Stage 3 — rize, switches off
Install. Nothing changes for Rize staff until the owner flips a switch (only Settings admins can — on Rize that is
ash@biztinct.com and the platform recovery login, not the Rize staff).

### Stage 4 — owner turns on "look" for Rize (Settings › PayAI can act). One-week watch: `payai_task` rows by
action/state, any refusals that read badly.
### Stage 5 — "prepare" for Rize when the owner says (after Component treatment is checked and someone at Rize knows
the plan card + Undo). Spoken go-ahead stays off (microphone is off there anyway).
### Stage 6 — "decide": only after Rize staff hold their own approval seats and the stale Team-lead seats are fixed.
### abm — not installed (D4).

### Deploy steps (stages 2 and 3; per repo CLAUDE.md + tiered rule "risky")
Pre-flight (each time):
1. ListAgents → SendMessage every live session: "about to install pb_payai_actions on <db>, server stop ~3 min";
   wait for acks. Confirm with the owner that the payobook restart hold is lifted (stop/start takes every site down).
2. Wait until no `odoo-bin … --stop-after-init` process (`ps -eo user,args | grep -v "bash -c" | grep "[o]doo-bin"`),
   8069 listening, ≥ 600 MB available.
3. Re-run the §1.2 check (`python3 tools/deploy_status.py rize payobook_template`): every dependency at repo version,
   nothing in `to install/upgrade`. If anything moved, stop and re-plan the cascade.
4. Files: the module is already on disk. Still: `sudo rm -rf /tmp/deployP && mkdir -p /tmp/deployP`;
   `git archive HEAD pb_payai_actions | tar -x -C <local stage>`; rsync stage → `/tmp/deployP/`; dry-run
   `sudo rsync -rcn --delete /tmp/deployP/pb_payai_actions/ /odoo/odoo-server/addons/pb_payai_actions/` → expect no
   changes. Anything listed → stop and find out whose (PA60). Never `--delete` into `/odoo/odoo-server/addons/` itself.
5. Backup: `sudo bash -c "sudo -u postgres pg_dump -Fc <db> > /odoo/backups/payai-tenant-<db>-<stamp>.dump"`.
   Record: active job count, employee/payslip/run counts.
Install:
6. `sudo service odoo-server stop`; detached unit:
   `sudo -u odoo python3 /odoo/odoo-server/odoo-bin -c /etc/odoo-server.conf -d <db> -i pb_payai_actions
   --stop-after-init --no-http` → sentinel with EXIT (pattern of `~/pb_upgrade.sh`, which does `-u`; use an `-i`
   copy, never `sed` the `-u` line — it also hits `sudo -u odoo`).
7. Per DB: `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'`; bump `web.assets.version`;
   `INSERT INTO orm_signaling_assets DEFAULT VALUES`. `sudo service odoo-server start`; poll 8069.
8. Tell the other sessions it is finished.
Verify:
9. `latest_version` = 19.0.4.2.0 on the DB; switches all false per company; active jobs = before (rize 69, template 0;
   if the template shows any active job, switch it off — owner-confirmed desired state); counts unchanged.
10. Hash `pb_payai_actions` both sides (skip `__pycache__`, `*.pyc`, `.DS_Store`) — identical.
11. Log grep for the install window: no ERROR/Traceback for that DB.
12. rize: `curl -H "Host: rize.payobook.com" …/web/login` = 200; browser check in the owner's own signed-in session
    (Claude may not type a password on a live site): chat opens, an ordinary question behaves as before, ⌘K shows
    "Ask PayAI to…", Settings shows "PayAI can act" with all four off, console clean.
13. Add a PENDING.md row only if a DB is held back; update memory `payai-does-it-program` + this file's status.

---

## 6. Things deliberately NOT in this plan
- No ChatGPT key, helper wording, or microphone for Rize/template/abm (separate owner decision D3).
- No code change. (Optional later: let payroll managers, not only Settings admins, flip the switches — P1 open question.)
- No change to the approval seats on Rize (owner/consultant work on the Approvals screen).
- No restoring of template or abm scheduled jobs.

---

## 7. Owner decisions
- **D1** Rehearse on a temporary copy of Rize first, then delete the copy? (Recommended: yes.)
- **D2** Which sites get it: template + Rize (recommended), Rize only, or all three including abm.
- **D3** ChatGPT for Rize: keep it off (recommended — commands still work from fixed phrasings, nothing leaves, US$0),
  or switch it on (understands more phrasings and answers data questions, but Rize's pay figures go to OpenAI under
  your account — likely needs Rize's agreement first).
- **D4** abm: leave it out (recommended).
- **D5** abm housekeeping: switch off its ChatGPT key (a copy of the main one) and the spare admin-level test login
  (recommended), or leave them.
- **D6** Which switches on Rize and when: look first, prepare after a week, decide only once Rize staff hold their own
  approval seats (recommended).
- **D7** When: a quiet time agreed with you, because the install stops every site for about 3 minutes.

## 8. Size
No code. About half a day of engineering time: copy + tests + walk 2–3 h; template install 20–30 min; Rize install +
checks 30–45 min; owner browser check 10 min. Each switch flip later: 1 minute in Settings, then a one-week watch.

## STATUS 2026-10-16 13:12 Sydney — DONE (owner decisions via cards)
Owner chose: template + Rize; install directly (no rehearsal copy); ChatGPT ON for Rize (owner/admin must paste the
key into Rize's PayAI config — Claude may not enter API keys; until then the phrase table only); abm housekeeping YES;
Rize switches: "may look" only; install as soon as the server was free.
Waited for another assistant's payobook/rize upgrade (server down ~12:30–13:08; Rize jobs were temporarily 0 during it,
back to 69 after). Unit payai-tenant-ship: backups /tmp/pre_payai_tenant_{rize,payobook_template,abm}_*.dump;
`-i pb_payai_actions` on payobook_template + rize EXIT=0, 0 log errors; pb_payai_actions 19.0.4.2.0 installed on both;
switches rize look=on prepare/decide/voice=off, template all off; jobs rize 69→69, template 0→0; abm payroll_ai_config
is_active→false (0 active), user look.p4@payobook.com (id 265) inactive; asset purge + version bump ×4; sites 200.
Server-side check on Rize as ash (rolled back): run card for "where is the October India run" ✓; prepare → "PayAI can
look, but is not allowed to do this here yet" ✓; access → never card ✓; "what can you do" ✓. "open the pay runs board"
needs the browser's screen list (shell has none) — check in the browser. Browser check on rize.payobook.com still to do
in the owner's signed-in session.
