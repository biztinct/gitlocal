# Rize Vietnam October salary and deduction repair

The October draft used zero VND contracted salary for all 70 employees. Its
deduction formulas ran, but zero salary removed basic pay and most insurance
and income tax. No additional deduction mapping was needed.

## Cause and correction

The August client file had nonzero `LUONGHOPVND` values, but that input had no
persistent contract-field mapping. All 70 current contract wages were zero.
The template's automatic wage candidate picked the earlier, unused USD salary
column; VND salary was consequently treated as a monthly adjustment. An absent
numeric monthly input became zero in the generated engine file.

There was also a stale-source defect: a prior monthly upload could override a
saved recurring record, including with zero. Recomputing a saved monthly batch
reused that old file instead of joining current recurring records again.

`pb_payroll_templates` **19.0.1.0.2** fixes these paths:

- Prefer a salary candidate labelled with the payroll currency. Ambiguous
  candidates are not assigned to the native wage field by column order.
- Always read readonly recurring context freshly from records, even when an
  earlier monthly snapshot contains another value.
- Refuse missing recurring salary rather than silently turning absence into zero.
  A deliberately saved numeric zero remains a valid value.
- A persisted monthly batch refreshes recurring records when recomputed and
  records their actual record-source provenance. Ordinary uploads retain their
  existing behavior; monthly adjustment zero continues to mean update.

Functional commits: **2811a7482**, **f871dec0d**.
Audited repair/recompute tools: **4d6533f2d**, **ec92ad86f**.

## Owner-confirmed Rize data repair

The owner explicitly confirmed August's salaries as October's baseline.
Mapped VND salary to `hr.contract.wage` through Studio, then applied only those
70 salary changes through Records Desk's existing preview/approval/audit flow.
Reference **RD00092**, request 78, applied with no approval pending.
Baseline total: **VND 1,814,978,020**. No August time, bonus or other variable
amount was copied into October.

Recomputed the existing draft **685**, keeping all 70 original payslip IDs.

| October run | Before (VND) | After (VND) |
|---|---:|---:|
| Gross | 161,968,987 | 1,753,152,926 |
| Deductions | 642,865 | 251,935,396 |
| Net | 161,326,122 | 1,501,217,530 |

Insurance deductions: SI 96,931,380; HI 18,174,635; UI 12,745,779.
PIT: 124,083,547. Existing client formulas and rates were retained.
All **350 independent checks** passed (70 × prorated salary, SI, HI, UI, PIT).
The run reconciles gross minus deductions to net and remains **Draft**.
October monthly inputs and August stored payroll results have unchanged hashes.

Chrome on Rize showed the corrected totals, 70 employees, Draft status and no
browser errors. A fresh generated monthly engine file also reads all 70 current
database salaries, totaling VND 1,814,978,020, despite the old file's zeros.

## Deployment scope and verification

The shared-server combined rollout had already begun before the owner requested
Rize-only deployment during the payobook demo; the owner then allowed the
already-started rollout. Completed that in-flight upgrade on **payobook, rize,
p0clone, payobook_template and abm**. All actual salary and payroll data repairs
were restricted to **rize**. No further demo deployment was initiated.
The web service was brought back online during remaining background checks;
payobook.com login returned HTTP 200. No further service restart was required.

Final results: **25 module checks passed per database, 125 total**. The first
ABM test attempt hit a concurrent delete in its pay-position refresh; rerunning
with scheduled jobs disabled passed all 25 checks. Both logs are retained.
ABM and the golden template retain zero active scheduled jobs.

The owner concurrently created India October run **686** with 16 payslips during
the pre-stop backup window. The invariant check stopped on that legitimate
count change; it was audited and preserved before finishing the rollout.
All other counts and aggregate wages matched each database's deployment baseline.

The deployed combined snapshot had **4,732 files**, verified against its hashes.
Installed module versions match across all five databases. Three later concurrent
portal UI source edits were preserved locally and not pushed as another demo
deployment, in accordance with the owner's latest restriction.

Backups on SSH `Payobook19v2`:

- `/odoo/backups/rize-vietnam-salary-20261015/`: pre-repair Rize dump, exact
  repair/recompute scripts and receipts.
- `/odoo/backups/payroll-templates-rollout-20261015-202604/`: five pre-upgrade
  dumps, prior changed addons, combined manifest, module test logs and rollout
  receipt, including the audited concurrent India run and successful ABM retry.

No test screenshots/PNGs or workbook downloads were generated or retained.
