# pb_payhub — the Pay Run hub

IA redesign Cycle 2. Eight cockpits, one workspace, one server read.

## The period tracker heuristic

`pb.pay.hub.get_period_state()` answers one question — *where is this calendar
month's payroll?* — as a stage between 1 and 5. It computes from states that
already exist; it stores nothing and it invents nothing.

### What it looks at

**Scope.** `hr.payslip.run` records that **overlap** the current calendar month
(`date_start <= last AND date_end >= first`) in `env.companies`, **excluding
`cancel`**.

* *Overlapping*, not contained: a run is keyed by the period it pays for, and a
  mid-cycle advance or a 25th-to-24th cycle legitimately straddles a boundary.
* *Cancelled runs are not a stage.* A rejected run is a thing that did not
  happen. Its testimony (`pb_reject_note` / `pb_reject_uid` / `pb_reject_date`)
  lives on the Runs lens, which is where a rejection belongs.

### The mapping

| `hr.payslip.run.state` | means | run stage |
|---|---|---|
| *(no run at all)* | nothing covers this month | **1** |
| `draft` | created, computing / being edited | **2** |
| `level0` | with the Payroll Officer tier | **3** |
| `level1` | with the HR tier | **3** |
| `level2` | with the Finance / GM tier | **3** |
| `done` | approved | **4** |
| `done` **and** a `pb.payslip.delivery.batch` on it in state `done` | delivered | **5** |
| `cancel` | *excluded from the scope entirely* | — |

`level0` is not in stock `om_hr_payroll`: `pb_payruns` adds the Payroll Officer
tier through `selection_add`
(`pb_payruns/models/hr_payslip_run.py`). The delivery model is
`pb_pay_delivery/models/payslip_delivery.py`.

**Stage 5 is deliberately not a run state.** `done` on a run means APPROVED and
nothing more — a run can sit approved and unpaid indefinitely. Calling that
"delivered" would be a lie in the one direction that costs money.

### The period's stage is the MINIMUM of its runs' stages

A Vietnamese month on this product is six division runs. "The period is
delivered" therefore has to mean *all six went out*: under a maximum, one
delivered division would light the chip while five thousand people were still
unpaid.

The minimum is also what makes the chip's click meaningful — it lands on the
lens where the work that is still outstanding lives, which is the only reason to
make a status chip a door at all.

| stage | label | the chip opens |
|---|---|---|
| 1 | Not started | `run` (the wizard) |
| 2 | Drafting | `runs` (submit it) |
| 3 | In approval | `payslips` (review) |
| 4 | Approved | `deliver` |
| 5 | Delivered | `runs` |

A month whose only runs were rejected reads as stage 1 — nothing stands for that
month, which is exactly what stage 1 says.

### Read-only by construction

`pb.pay.hub` contains no `create`, no `write` and no `unlink`, and
`tests/test_payhub.py::test_the_hub_model_can_not_write` asserts that by reading
the source. The tracker is read on every hub mount; a surface that is read that
often should not be able to write at all (W25/W41).

`stage_documentation()` returns the two maps above as data, and the tests assert
the table in this file against it, so the prose and the behaviour cannot drift
into describing different things.

## The lenses

| lens | icon | component | what `embedded` suppresses |
|---|---|---|---|
| run | zap | `PayrunWizard` | the `.pw-head` title row (and its Cancel, which would leave the hub) |
| runs | calendar | `PbPayruns` | the `.pbr-head` title block; the Run-payroll CTA stays and switches lens |
| payslips | receipt | `PayslipReview` | the `<h1>` + period line; the run selector beside it stays |
| results | table | `PbPayrunResults` | `.pbr-title`; the run picker and the XLSX export stay |
| import | download | `PbImport` | `.pbm-head`; every tile and launcher is untouched (one-door work is C3) |
| deliver | send | `PbPayDelivery` | the picker `<h1>` and the hero eyebrow; the hero `<h1>` is the RUN, i.e. data |
| adjust | percent | `LedgerCockpit` (tabs: Retro \| Proration) | the title row and the "Open full list" escape |
| settle | file | `LedgerCockpit` (Full & Final) | the title row and the "Open full list" escape |

Lens memory is `pbhub.pay.lens.v1` (the shell's `config.key` is `"pay"`).
