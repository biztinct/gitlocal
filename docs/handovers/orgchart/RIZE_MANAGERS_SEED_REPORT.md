# rize — managers seeded from the pay data file (2026-11-05)

Owner ruling 2026-11-05: set `hr.employee.parent_id` on rize from the pay data
file's "Reporting Manager" column; fill the clean matches now, send the rest to
Rize as a list. Database `rize` ONLY (no other DB, no abm). No module change,
no deploy, no restart.

## What was written

* **204 managers** set at 2026-11-05 01:21:57 UTC by
  `tools/seed_rize_managers_from_payfile.py` (run through `odoo-bin shell`
  as the admin, uid 2 — the 204 history entries on the employee records are
  signed by Ash Sohani).
* Written ONLY through `pb.orgchart._set_managers` (ledger rule 12 / G16):
  coach, time-off approver and expense approver kept their value. Checked
  afterwards by SQL against the undo table: 204/204 manager = new value,
  204/204 coach, time-off approver and expense approver = old value.
* Loops judged with `pb.orgchart._loop_in` on the whole change list: none.
* Nobody in the files already had a (different) manager; nobody archived was
  touched.

| | before | after |
|---|---|---|
| active employees with a manager | 5 of 241 | **209** of 241 |
| coach set | 5 | 5 |
| time-off approver set | 0 | 0 |
| expense approver set | 0 | 0 |
| Org chart "no manager yet" (people in the lane) | 234 | **26** (+ 66 open roles waiting in the same lane, hence "+73 more") |

Browser check (Chrome, signed-in session, rize.payobook.com › People › Org
chart): 241 people across 197 teams, 5 levels deep; Dhruv Sawhney (CEO) at the
top with 193 people under him; country trees (Nguyễn Huy Dũng 47, Hồ Hữu Dư 34,
…) visible. No console errors on a fresh load.

## Sources

Latest real batch per scheme (`hr.payroll.import.line.raw_data_json`):

| batch | scheme | rows | manager column |
|---|---|---|---|
| 2072 | Vietnam, October 2026 | 63 | `Consolidated|Reporting Manager` |
| 2284 | Indonesia, August 2026 | 122 | `Consolidated|Master Reporting Manager` |
| 2260 | India, October 2026 | 27 | `Consolidated|Reporting Manager` |
| 2285 | Singapore, August 2026 | 2 | `Consolidated|Master Reporting Manager` |

"Hiring Manager" is never read.

## Matching (as built)

Accent-insensitive (đ→d, NFKD, punctuation dropped) against every employee,
active or archived, in three tiers — first tier with any hit wins:
1. full name (178 rows);
2. same words in another order (4 rows: "Nithya R" = "R Nithya", "Siem
   Daantje Schreurs" = "Schreurs Siem Daantje");
3. short name (22 rows): every word of the file's text inside the person's
   name ("Monica" = "Monica Puranlal Bhojwani", "Arief Hidayat" = "Arief
   Andani Hidayat"). Outside Vietnam a short name must not contradict the
   file's own manager email. All 26 tier-2/3 rows (VN 6, ID 18, IN 2) agree
   with the file's manager email.

Written per scheme: Indonesia 118, Vietnam 59, India 25, Singapore 2.

Written only when the tier has exactly ONE active person and nobody archived.
Email settles a tie only outside Vietnam (no tie needed it this time). The
Vietnam email column is unreliable (`du.ho@rize.farm` beside five names) and is
shown as information only.

Deviation found on the dry run and handled: the read-only check's 204/6 split
was only reproducible once short names and archived people were taken into
account — "Shreya" fits Shreya Gaunekar (active) and Shreya Prasad (archived),
so it is NOT written (matches the owner's list of 6).

## Dry-run summary (01:21:32 UTC, the run that was then applied)

```
SUMMARY rows=214 with_manager=210 clean=204 problems=6 blank=4 already_set=0
        kept_other=0 loops=0 to_write=204 in_no_file=27
people with a manager now: 5 of 241 active; coach 5; time-off approver 0; expense approver 0
```

A second dry run after the write: `already_set=204 to_write=0` (idempotent).

## Problem rows (not written)

| scheme | employee | file says | why |
|---|---|---|---|
| VN | Bùi Hương Lan | Indra | Indra Aditya Pambudy / Indra Guntara |
| VN | Nguyễn Thị Phương Thảo | Nithya (mail indra@) | Nithya Mary Devadoss / R Nithya |
| VN | Phan Công Toàn | Nithya (mail hr-nithya@) | Nithya Mary Devadoss / R Nithya |
| VN | Schreurs Siem Daantje | Shreya | Shreya Gaunekar / Shreya Prasad (archived) |
| IN | Dhruv Sawhney | Board | not a person — CEO stays a root |
| IN | Rachit Arora | Dhruv Swhney | misspelt; dhruv@rize.farm = Dhruv Sawhney (3380) |

Blank manager cell (4, Indonesia): Agung Maulana, Archy Fenanditya Ananta
Putra, Jakaria, Naufal Afif Alfarisiy.

In no file (27 active): 18 real staff (4 Indonesia, 14 Vietnam) + 9 non-staff
records (admin login id 1, 7 `Demo`/`DEMO` practice records — 5 of them carry
the 5 pre-existing managers — and a shared "Indonesia Finance" record).

## Files on the server — `/odoo/archives/rize-managers-20261105/` (odoo:odoo 750)

* `seed_rize_managers_from_payfile.py` — the exact script that ran (pipe it
  in with `sudo cat`; the folder is odoo-only).
* `undo-20261105T012157Z.csv` — employee id, name, old manager, old coach,
  old time-off approver, old expense approver, new manager (204 rows).
* `hr_employee-before.dump` — `pg_dump -Fc -t hr_employee` taken just before.
* `proposal-dry-*.json`, `proposal-apply-20261105T012157Z.json` — full proposal.

## Undo

```
sudo cat /odoo/archives/rize-managers-20261105/seed_rize_managers_from_payfile.py \
  | sudo -u odoo PB_MGR_UNDO=/odoo/archives/rize-managers-20261105/undo-20261105T012157Z.csv \
    python3 /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf -d rize --no-http
```

Puts back manager, coach and both approvers for every row whose manager is
still the one this run wrote (rows changed by someone since are left alone and
listed). Add `PB_MGR_DRY=1` after `sudo -u odoo` to rehearse — rehearsed
01:22 UTC: 204 put back, 209 → 5, rolled back.

Gotcha (new): a setting written in FRONT of `sudo` (`X=1 sudo -u odoo …`) is
dropped by sudo's env reset — the script then silently does a dry run. Put it
after `sudo -u odoo`. The first printed undo command had this bug; fixed
before commit.

## Client list

`outputs/rize-managers-2026-11-05/Rize reporting managers - 5 Nov 2026.xlsx`
(not committed): *Need your decision* (6), *Not in any pay file* (18 staff +
a one-line note on the 9 non-staff records), *Managers set* (204), *Blank in
the file* (4).
