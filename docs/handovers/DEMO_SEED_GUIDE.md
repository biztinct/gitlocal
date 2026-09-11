# Demo data and the Vietnam record mapping — operating guide

Two modules, built together on 2026-09-11, live on the `rize` tenant
(`rize.payobook.com`). They are independent of each other and of any one
customer; `rize_vn` is simply the first profile.

| Module | What it is |
|---|---|
| `pb_payroll_mapping_vn` | Typed employee/contract fields for the Vietnam pay scheme, the contract components, and the applier that wires a scheme onto them. |
| `pb_demo_seed` | A register-backed demo world: five people with one story each, loadable and removable. |

---

## 1. The mapping

### What it does

The Vietnam starter scheme (`config_template_vn_complete.xml`, 111 columns)
asks a person for ~45 values. After the profile is applied, the monthly pay-data
file carries **the employee code, six time columns and sixteen approved
amounts** — 24 columns. Everything else resolves from:

| Source | Columns | Rank |
|---|---|---|
| Employee record (`pb_vn_*` on `hr.employee`) | 8 person facts | 4 |
| Contract record (`pb_vn_*` + `wage`, `dependents`) | 14 contract facts | 4 |
| Contract components (`hr.contract.advantage`) | `UNIFORM`, `PRIVINSAMT`, `HLTHEEAMT`, `HLTHDEPAMT` | 5 |
| Bank account (`res.partner.bank`) | `BANKACC`, `BANKNAME`, `BANKBIC`, `BANKHOLDER` | 4 |
| The pay period itself | `PAYMONTH` | last |

`models/vn_profile.py` is the single declaration of all of it — the fields, the
mapping, the spreadsheet layout. `tools/pb_vn_pay_data.py` imports it rather
than restating it.

### Applying it to a scheme

```bash
sudo -u odoo PB_DEMO_ACTION=mapping PB_DEMO_CONFIG=RIZE_VIETNAM \
  python3 /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf \
  -d <tenant> --no-http < tools/pb_demo_seed_cli.py
```

Idempotent. A second run reports `Columns newly mapped: 0`. It never edits a
column the profile does not name, never changes a formula, and never replaces a
destination somebody set by hand.

There is also a button: `hr.formula.config.action_pb_apply_vn_mapping()`.

### ⚠ The column-letter trap — read before changing the spreadsheet

When a pay-data file arrives, the resolver tries each component's **name**, then
its **code**, then — if neither matched — its remembered **column letter**
against the file's own columns. The file's letters come from header *position*
(`_raw_data_from_row`), so a short file's column F is not the scheme's column F.

On the first live run of the short file, `PAYMONTH` (scheme column F) read the
sixth column and came back as **eight hours of weekend overtime**. The
thirteenth-month bonus is `IF(PAYMONTH=12, …)`; somebody with twelve weekend
hours would have been paid an extra month's salary, silently.

**Clearing the column letters does not fix it and makes things worse**: the
compiled formulas address some components *by letter* (`GROSS` reads
`values['AS']` for the uniform allowance), so a scheme with cleared letters
silently drops those components out of gross pay. This was tried and reverted;
the letters on `rize` were restored by hand.

The fix lives in the **file**: `vn_profile.RESERVED_POSITIONS` names the
positions that belong to components the file does not carry, and
`sheet_layout()` leaves them empty and hidden. `tools/pb_vn_demo_check.py`
asserts the invariant and fails loudly if a new column ever reintroduces a
clash. **Run that check after any change to the spreadsheet's columns.**

### Regenerating the spreadsheet

```bash
python3 tools/pb_vn_pay_data.py            # → RIZE/VIETNAM/Rize Vietnam - demo pay data.xlsx
```

No Odoo needed. Dates and the standard-working-days figure follow the month it
is run in.

### Verifying end to end

```bash
scp "RIZE/VIETNAM/Rize Vietnam - demo pay data.xlsx" <host>:/tmp/pb_vn_pay_data.xlsx
sudo -u odoo python3 /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf \
  -d <tenant> --no-http < tools/pb_vn_demo_check.py
```

Imports the file, computes five payslips, prints where every input came from,
then deletes the run it made. Last run on `rize`: 5 lines, 5 matched, 0 errors,
65 inputs with a real source per payslip.

---

## 2. The demo world

### The five people

| Code | Story |
|---|---|
| DEMO001 | Joiner, three days in. Checklist running, buddy confirmed, laptop request stopped at "spare found, not handed over". |
| DEMO002 | Trial period ends in 18 days. Four peers asked, two answered, manager 1:1 in the diary. |
| DEMO003 | Week five of a six-week performance plan. Three objectives, one at risk, four check-ins held. |
| DEMO004 | Fixed-term contract ending in 45 days. Extension asked for and refused, leaving checklist open, laptop still out. |
| DEMO005 | Country manager, foreign hire — exercises the expatriate branches of the pay scheme. Assets, an award, a full benefits package. |

Around them: 5 suppliers with agreements (one expiring in a month), manpower and
HR-operations budgets over three months, recognition (a decided quarter and an
open one), benefit plans and enrolments, a payroll calendar, leave, and the
training that gates a probation clearance.

### Load / remove

```bash
sudo -u odoo PB_DEMO_ACTION=load   python3 /odoo/odoo-server/odoo-bin shell … < tools/pb_demo_seed_cli.py
sudo -u odoo PB_DEMO_ACTION=status python3 … < tools/pb_demo_seed_cli.py
sudo -u odoo PB_DEMO_ACTION=remove python3 … < tools/pb_demo_seed_cli.py
```

In the product: **Settings → Demo data** (system administrators only), with a
Load and a Remove button and the full register on the page.

### How removal is safe

Every record is written into `pb.demo.record` **as it is created**, with its
creation order. Removal walks that register backwards and unlinks exactly those
rows. It does **not** match on "starts with Demo".

Three things the first live removal taught us, all now handled:

1. **`last=True`** on `ctx.track` — a record created as a side effect of the
   thing that depends on it (an employee's private contact) must be removed
   *after* it, so it gets a negative sequence.
2. **`_release_before_removal`** — an open asset handover and an approved
   time-off record both refuse to be deleted, correctly. They are handed back /
   returned to draft first, through the product's own actions.
3. **One world per company** — several records are unique by name (a supplier
   is), so a second load is refused up front rather than failing half-built.

### Adding a tenant

A second tenant is a second **profile** in `pb_demo_seed/seeds/__init__.py`, not
a second module. Builder order in `PROFILES` is the removal order reversed —
organisation first, stories last.

---

## 3. Tests

18 tests, all passing on `rize` (2026-09-11):

```bash
odoo-bin -d <tenant> -u pb_payroll_mapping_vn,pb_demo_seed --test-enable \
  --test-tags /pb_payroll_mapping_vn,/pb_demo_seed --stop-after-init
```

The one that matters is `test_01_the_round_trip_leaves_nothing_behind`: load,
then remove, then assert on the **database** that no demo employee, no demo
asset and no register row survives.

---

## 4. Known gaps

* The **Settings buttons have not been clicked through in a browser** — there is
  no known password for `ash@biztinct.com` on `rize`. The action, the view and
  the settings-hub card are installed and the gate logic is confirmed
  (`resolve_gates` rule 1: a system administrator sees everything); the click
  path itself is unverified.
* An attempt to compile `web.assets_backend` in a shell to prove the new JS
  imports cleanly was **OOM-killed** on this 1.9 GB box. Do not retry it there.
* `pb_demo_seed` is not yet installed on `payobook`, `abm` or `acme`.
