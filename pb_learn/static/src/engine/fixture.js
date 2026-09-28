/* GENERATED FILE. Do not edit.
            Source: docs/tutorial_poc/author/ · Regenerate: python3 docs/tutorial_poc/author/tools/gen_learn_data.py
            Hand edits are erased on the next run and fail the CI check. */
/** @odoo-module **/

/* =============================================================================
   Payobook Learn — PRACTICE DATASET
   -----------------------------------------------------------------------------
   THE ONLY FILE THAT MIRRORS THE PRODUCT.

   There is no demo tenant behind the practice screens and none is needed: the
   practice company is this JavaScript fixture. Nothing here can reach a real
   employee, contract, payslip or pay run, because there is no server on the
   other end of it. A mission step that says "compute the run" is therefore
   structurally incapable of computing one.

   THE COST OF THAT CHOICE, AND HOW IT IS PAID
   -------------------------------------------
   A fixture drifts. When a selection value is renamed, a contribution rate
   changes or a menu leaf moves, this file silently starts teaching a product
   that no longer exists — and a confidently wrong tutorial is worse than none.

   So every value below that mirrors something real is declared in
   `contract.json`, and `tools/check_contract.py` verifies each declaration
   against the actual addons. Run it in CI. When it fails, THIS file (and the
   content that quotes it) is what needs updating.

       python3 docs/tutorial_poc/author/tools/check_contract.py

   RULE FOR EDITORS: teaching content lives in `data.js`, beside this file.
   Anything that is a fact about the product lives HERE, once, and is referenced
   from there. If you find yourself typing a number into a lesson step, it
   belongs in this file.

   THIS FILE IS THE AUTHORING SOURCE. `tools/gen_learn_data.py` copies it into
   pb_learn/static/src/engine/fixture.js with a banner and an export line — so
   the shipped fixture and this file are the same bytes plus that wrapper, and
   hand-editing the shipped copy is a build failure rather than a fork.

   THE WORKED EXAMPLE IS ONE EXAMPLE. Nguyễn Thị Mai, July 2026, and the Retail
   — Hà Nội run around her. Every lesson calc, every Coach calc block and every
   mission fact reuses these numbers; none of them invents its own.
   ========================================================================== */

const B = (en, vi) => ({ en, vi });
/* LEARN REFRESH step 5. A label the PRODUCT shows in English in both
   languages (no translation exists for it on that screen). The replica says
   the same words the reader will meet, in either language. */
const EN = (s) => ({ en: s, vi: s });

/* Bump the minor when you add records; bump the major when a shape changes,
   because `check_contract.py` pins to it. */
const PRACTICE_META = {
  schemaVersion: "1.2.0",
  contract: "contract.json",
  derivedFrom: "gitlocal branch 19.1",
  isolation: B(
    "No server, no tenant, no credentials. Every action in the practice company resolves inside this file.",
    "Không máy chủ, không đơn vị riêng, không thông tin xác thực. Mọi thao tác trong công ty thực hành đều xử lý bên trong tệp này."),
};

/* =============================================================================
   0. TENANT SLOTS — the named facts a company may fill in for itself.
   -----------------------------------------------------------------------------
   ONE IMPORTANT DISTINCTION, because it is easy to conflate these two:

     · This PRACTICE FIXTURE is module-shipped and identical in every tenant.
       It is fake data, and it lives in JavaScript precisely so that it can
       never touch a real record.

     · A TENANT SLOT is a REAL fact about one company — its actual pay day, the
       name it gives its approval tiers, its actual import cut-off. Those differ
       per tenant, so they CANNOT live in a module-shipped file: the module
       ships the same bytes to everyone. In production each is one small
       database row per company (learn.tenant.override).

   The values below are the SHIPPED DEFAULTS, and the list is also the
   DECLARATION: a key with no row here does not exist, and the override
   constraint refuses one that does not fill a declared slot.

   Deliberately short. Slots are facts — a pay day, a tier name, a cut-off.
   The moment one grows into a sentence the next step is a tenant editing a
   lesson, and then no check can guard any of them (test_tenant_override
   asserts a 60-character ceiling).

   NOT EXPORTED to the engine on purpose: in the product these arrive resolved
   per company in the bundle. Exporting the fixture's copy would hand the
   engine a second source that is always wrong for eleven tenants out of
   twelve.
   ========================================================================== */
const TENANT_DEFAULTS = {
  companyDisplayName: B("your company", "công ty bạn"),
  payDay: B("the 5th of the month", "ngày 5 hằng tháng"),
  /* LEARN REFRESH step 2: NO CONTENT USES THESE TWO ANY MORE. They named the
     fixed approval tiers of the retired pay-run ladder; a pay run now follows
     whatever route the company drew in the Approval Matrix, so a lesson names
     the practice company's own route (ROUTE below) and says that a real
     company's route is its own. The slots stay DECLARED because a tenant may
     already hold an override row for them, and deleting a declared slot would
     orphan that row. token-lint lists them as unused, which is the truth. */
  hrTierName: B("HR review", "HR soát xét"),
  gmTierName: B("Finance approval", "Tài chính phê duyệt"),
  importCutoff: B("the 28th", "ngày 28"),
  bankFileFormat: B("the bank's standard salary file", "tệp chi lương chuẩn của ngân hàng"),
  standardWorkingDays: B("22", "22"),
  payrollSupportContact: B("your payroll administrator", "quản trị viên tính lương của bạn"),
};

/* =============================================================================
   0b. THE STATUTORY RECORDS — and the TWO PLACES a rate lives.
   -----------------------------------------------------------------------------
   THE MOST IMPORTANT FACT IN THIS FILE, because the content got it wrong once
   and confidently:

     A `vietnam.insurance.policy` record does NOT price a payslip.

   It is the company's DECLARED statutory rates. Everything that reads it reads
   it to DISPLAY or to REPORT: the Statutory cockpit
   (pb_statutory/models/pb_statutory.py:54-76), the contribution analytics
   (pb_hr_payroll_vietnam/models/hr_formula_config_analytics_vietnam.py:49-76),
   the employee cost estimate (hr_employee_vietnam.py:235-259) and the
   insurance analytics wizard. Grep the rate fields and that is the whole list.

   The rates that actually PRICE a payslip are PARAMETER CONSTANTS on each
   division's formula configuration. In the demo world BHYT is
   `EEHI = 0.015` (pb_demo/models/demo_catalog.py:62) and the component that
   charges it is `HIEMP = -ROUND(MIN(BASIC,CAPLO)*EEHI)` (:107). Change the
   policy record and not one đồng moves; change EEHI and every future payslip
   in that division does.

   THAT SEPARATION IS DESIGN, NOT AN OVERSIGHT: pay never changes because a
   reference table changed. It changes when somebody edits a configuration, and
   that edit is traceable, previewable and simulatable. The job the Statutory
   screen really does is DECLARE and RECONCILE — and the reconciliation is the
   lesson: when the declared rate and the configured rate disagree, payroll is
   running on a rate the company is not declaring.

   So this fixture holds the rates ONCE, in VN_RATES, and hands the same
   numbers to both places — because that is what a correctly run company looks
   like, and because the trace in L6 is a check that they still agree rather
   than a claim that one causes the other.

     vietnam.insurance.policy   name · code · effective_date · end_date ·
                                active · si/hi/ui employee+employer rates ·
                                si_max_salary_ceiling
     vietnam.tax.table          tax_year · personal_deduction ·
                                dependent_deduction · slab_ids

   THERE IS NO VERSION CHAIN ON EITHER MODEL, and the content must never teach
   one. A rate change is a NEW RECORD with its own `code` (unique per company —
   `code_company_uniq`) and its own `effective_date`. The cockpit picks the
   policy to display as the LATEST effective_date among active=True — it does
   NOT consult end_date, and it does not compare the date to today, so a
   future-dated policy is displayed the moment it is saved. `contract.json`
   pins that query.
   ========================================================================== */

/* The statutory reality, declared once. Both the policy record below and the
   configuration's parameter constants read from it. */
const VN_RATES = {
  SI: { employee: 8, employer: 17.5, ceiling: 20000000 },
  HI: { employee: 1.5, employer: 3, ceiling: 20000000 },
  UI: { employee: 1, employer: 1, ceiling: 20000000 },
};

const POLICY = {
  name: B("Insurance policy 2026", "Chính sách bảo hiểm 2026"),
  code: "VN-INS-2026",
  effective: "01/01/2026",
  end: "",
  active: true,
  /* `key` is the product's own scheme key (pb_statutory CONTRIB_MAP: SI / HI /
     UI), not a display label — the cockpit rows are keyed by it. */
  rows: [
    { key: "SI", label: B("BHXH — social insurance", "BHXH — bảo hiểm xã hội"), ...VN_RATES.SI },
    { key: "HI", label: B("BHYT — health insurance", "BHYT — bảo hiểm y tế"), ...VN_RATES.HI },
    { key: "UI", label: B("BHTN — unemployment insurance", "BHTN — bảo hiểm thất nghiệp"), ...VN_RATES.UI },
  ],
  /* Totals are DERIVED, exactly as `total_employee_rate` is a computed field on
     the real record. A hand-typed total beside the rows it sums is the first
     number a learner checks and the first one to go stale. */
  get totalEmployee() { return this.rows.reduce((t, r) => t + r.employee, 0); },
  get totalEmployer() { return this.rows.reduce((t, r) => t + r.employer, 0); },
};

const TAX = {
  name: B("PIT table 2026", "Biểu thuế TNCN 2026"),
  code: "VN-PIT-2026",
  year: 2026,
  personalDeduction: 11000000,
  dependentDeduction: 4400000,
  /* Vietnam's seven progressive bands. `to: 0` is the open-ended top one, which
     is how vietnam.tax.slab stores it (income_to left at zero). */
  slabs: [
    { from: 0, to: 5000000, rate: 5 },
    { from: 5000000, to: 10000000, rate: 10 },
    { from: 10000000, to: 18000000, rate: 15 },
    { from: 18000000, to: 32000000, rate: 20 },
    { from: 32000000, to: 52000000, rate: 25 },
    { from: 52000000, to: 80000000, rate: 30 },
    { from: 80000000, to: 0, rate: 35 },
  ],
};

/* =============================================================================
   1. THE WORKED EXAMPLE — one employee, one run, one month.
   ========================================================================== */
/* -----------------------------------------------------------------------------
   THE RULE, WRITTEN ONCE.

   Every displayed net in this fixture comes out of `payslip()`. It used to be
   that each employee carried hand-typed figures, and the moment one of them was
   edited the fixture stopped reconciling — a tutorial that teaches "the working
   is visible" while its own arithmetic does not add up is teaching the opposite
   of its lesson.

   The rule set, deliberately the simplest one that is still true of the worked
   example:
     · insurance = the three EMPLOYEE rates the CONFIGURATION carries as
       parameter constants (CONFIG_PARAMS below), each charged on the
       REGISTERED BASE and rounded to the đồng, then added up. Charged on the
       base, never on gross — that single fact is L3's spine.

       It reads CONFIG_PARAMS and not POLICY on purpose, and the distinction is
       the one the product actually makes: a payslip is priced by its division's
       configuration. The two hold the same numbers here because VN_RATES feeds
       both — which is what makes L6's trace a RECONCILIATION a learner can
       perform, rather than a causation the product does not implement.
     · taxable   = gross − insurance − the TAX table's personal deduction
                          − its dependant deduction per dependant
     · PIT       = the first band's rate on the taxable amount, floored at zero.
       Everyone in this fixture lands in the first band, which is realistic for
       a retail division and keeps the arithmetic checkable by a reader.

   MAI IS THE TEST VECTOR. Her canonical numbers were agreed before this
   function existed and it reproduces every one of them exactly — 14,280,000
   gross, 1,260,000 insurance, 2,020,000 taxable, 101,000 PIT, 12,919,000 net
   for July; 12,064,000 net for June. If a change here moves any of those, the
   change is wrong.

   `rates` is the ONE parameter that is not an employee input: it takes an
   alternative set of policy rows, which is how RATE_CHANGE below computes what
   a BHYT rise would do without a second copy of the arithmetic anywhere.
   -------------------------------------------------------------------------- */
const RELIEF_SELF = TAX.personalDeduction;
const RELIEF_DEPENDANT = TAX.dependentDeduction;
const PIT_FIRST_BRACKET = TAX.slabs[0].rate / 100;

/* What the division's configuration charges — the parameter constants a real
   config carries (EESI / EEHI / EEUI in the demo world). Same numbers as the
   declared policy, from one declaration, because a correctly run company keeps
   them in step. `rates` overrides them for the what-if in RATE_CHANGE. */
const CONFIG_PARAMS = {
  EESI: VN_RATES.SI.employee,
  EEHI: VN_RATES.HI.employee,
  EEUI: VN_RATES.UI.employee,
};

const PARAM_OF = { SI: "EESI", HI: "EEHI", UI: "EEUI" };

function employeeRate(key, rows) {
  if (rows) {
    return rows.find((r) => r.key === key).employee / 100;
  }
  return CONFIG_PARAMS[PARAM_OF[key]] / 100;
}

function payslip({ base, allowance = 0, ot = 0, dependants = 0, rates }) {
  const gross = base + allowance + ot;
  const bhxh = Math.round(base * employeeRate("SI", rates));
  const bhyt = Math.round(base * employeeRate("HI", rates));
  const bhtn = Math.round(base * employeeRate("UI", rates));
  const insurance = bhxh + bhyt + bhtn;
  const taxable = Math.max(0, gross - insurance
                              - RELIEF_SELF - dependants * RELIEF_DEPENDANT);
  const pit = Math.round(taxable * PIT_FIRST_BRACKET);
  return { base, allowance, ot, gross, bhxh, bhyt, bhtn, insurance, taxable, pit,
           net: gross - insurance - pit };
}

/* Each employee declares only their INPUTS. Everything printed anywhere is
   derived, so no two screens can disagree about the same person. */
const EMP_INPUT = {
  mai:   { name: "Nguyễn Thị Mai", code: "NV0012", dept: B("Retail — Hà Nội", "Bán lẻ — Hà Nội"),
           base: 12000000, allowance: 780000, otJul: 1500000, otJun: 600000, dependants: 0 },
  hung:  { name: "Trần Văn Hùng", code: "NV0031", dept: B("Retail — Hà Nội", "Bán lẻ — Hà Nội"),
           base: 10500000, allowance: 650000, otJul: 4200000, otJun: 1100000, dependants: 0 },
  trang: { name: "Lê Thu Trang", code: "NV0007", dept: B("Retail — Hà Nội", "Bán lẻ — Hà Nội"),
           base: 15200000, allowance: 500000, otJul: 310000, otJun: 0, dependants: 0 },
  /* Đức is below the relief threshold and pays no PIT at all. Kept in the
     fixture on purpose: a learner who has only ever seen taxed payslips reads a
     zero as a bug. */
  duc:   { name: "Phạm Minh Đức", code: "NV0019", dept: B("Retail — Hà Nội", "Bán lẻ — Hà Nội"),
           base: 9800000, allowance: 400000, otJul: 0, otJun: 0, dependants: 0 },
};

const EMP = Object.fromEntries(Object.entries(EMP_INPUT).map(([k, e]) => {
  const jul = payslip({ base: e.base, allowance: e.allowance, ot: e.otJul,
                        dependants: e.dependants });
  const jun = payslip({ base: e.base, allowance: e.allowance, ot: e.otJun,
                        dependants: e.dependants });
  return [k, {
    name: e.name, code: e.code, dept: e.dept,
    base: e.base, allowance: e.allowance, dependants: e.dependants,
    otJul: e.otJul, otJun: e.otJun,
    bhxh: jul.bhxh, bhyt: jul.bhyt, bhtn: jul.bhtn, insurance: jul.insurance,
    grossJul: jul.gross, taxableJul: jul.taxable, pitJul: jul.pit, netJul: jul.net,
    grossJun: jun.gross, taxableJun: jun.taxable, pitJun: jun.pit, netJun: jun.net,
  }];
}));

const RUN = {
  name: B("Retail — July 2026", "Bán lẻ — Tháng 7/2026"),
  division: B("Retail — Hà Nội", "Bán lẻ — Hà Nội"),
  period: B("July 2026", "Tháng 7/2026"),
  employees: 48, totalNet: 612480000, totalGross: 691200000,
  config: "HOASEN_RETAIL_END", configVersion: "v12",
  /* LEARN REFRESH step 2. The run is picked by its PAY SCHEME now — the
     "Pay run for" cards in Pay Run › Run — and a scheme's name is a record's
     own name, the same in every language (a record's name is data). */
  scheme: "Hoa Sen Retail — End-Month Payroll",
  from: "01/07/2026", to: "31/07/2026",
  /* WHAT "NEED REVIEW" COUNTS, and it is less than the old content claimed.
     The Run lens adds three things (pb_payrun_wizard payrun_wizard.js:338-342):
     payslips that came out at zero or below, people it could not make a
     payslip for (no running contract, a compute error), and people in the pay
     data file who are not in Payobook yet. It does NOT flag a big change on
     last month — Hùng's overtime is a thing a person has to notice. */
  flagged: 0,
  exceptions: 1,
  notInPayobook: 1,
  get needReview() { return this.flagged + this.exceptions + this.notInPayobook; },
};

/* The one person the July run could NOT make a payslip for — and correctly:
   Nam signed in July to start on 1 August, so the Run lens lists him with the
   product's own words (pb_payrun_wizard.py `_no_contract_reason`) and pays
   him nothing. He IS an employee (Pulse's headcount counts him) and he is not
   PAID in July (the month strip does not). That gap is a lesson, not a bug. */
const LATER = {
  name: "Hoàng Văn Nam", code: "NV0061", base: 9000000,
  why: B("Not employed yet in this period — contract starts 2026-08-01.",
         "Chưa làm việc trong kỳ này — hợp đồng bắt đầu ngày 2026-08-01."),
};

/* The other division in the practice company. F&B's July run exists and was
   SENT BACK — which is the state m2 works on, and the reason a second July run
   for it cannot simply be started (the Run lens would say "Payroll already
   exists"). */
const FNB = {
  name: B("F&B — July 2026", "F&B — Tháng 7/2026"),
  scheme: "Hoa Sen F&B — End-Month Payroll",
  employees: 21, totalNet: 214300000, totalGross: 241050000,
  insuranceBase: 190000000,
};

/* THE APPROVAL ROUTE. Nobody's pay run follows fixed tiers any more: it
   follows the route the company drew in the Approval Matrix. This is the
   practice company's, and it is the SAME shape Payobook seeds for every new
   company ("Pay run approval": Payroll check → HR lead review → Finance
   approval, pb_payruns/models/approval_seed.py:53-55) — so a learner who
   reads this reads the default they will meet. The names are the practice
   company's people. `you` marks the seat the approval lessons sit in. */
const ROUTE = {
  name: "Pay run approval",
  steps: [
    { key: "s1", title: B("Payroll check", "Kiểm tra bảng lương"), who: "Vũ Thị Lan Anh" },
    { key: "s2", title: B("HR lead review", "Trưởng nhân sự soát xét"), who: "Đặng Thu Hà", you: true },
    { key: "s3", title: B("Finance approval", "Tài chính phê duyệt"), who: "Trịnh Quốc Bảo" },
  ],
  preparer: "Phan Minh Tú",
};

/* The two visuals in visuals.js read CASE and nothing else, so a lesson step
   and a Coach answer can never disagree about the arithmetic. */
const CASE = {
  emp: EMP,
  run: RUN,

  /* Mai's July payslip, term by term. `neg` rows are deductions; the renderer
     prints the sign, so the stored value stays positive and comparable. */
  slip: [
    { k: B("Base salary (LCB)", "Lương cơ bản (LCB)"), v: EMP.mai.base },
    { k: B("Allowances (PCCC, ATVSV)", "Phụ cấp (PCCC, ATVSV)"), v: EMP.mai.allowance },
    { k: B("Overtime", "Tăng ca"), v: EMP.mai.otJul },
    { k: B("Gross", "Tổng thu nhập"), v: EMP.mai.grossJul, sub: true },
    { k: B("BHXH (8%)", "BHXH (8%)"), v: EMP.mai.bhxh, neg: true },
    { k: B("BHYT (1.5%)", "BHYT (1,5%)"), v: EMP.mai.bhyt, neg: true },
    { k: B("BHTN (1%)", "BHTN (1%)"), v: EMP.mai.bhtn, neg: true },
    { k: B("PIT (progressive)", "Thuế TNCN (luỹ tiến)"), v: EMP.mai.pitJul, neg: true },
  ],
  slipTotal: { k: B("Net pay", "Thực nhận"), v: EMP.mai.netJul },

  /* June → July, for "why is this different from last month". The insurance
     line is deliberately flat: it is charged on the REGISTERED contract base,
     which overtime does not move. That single fact answers most of the
     variance questions a payroll desk actually receives. */
  variance: {
    from: B("June 2026", "Tháng 6/2026"),
    to: B("July 2026", "Tháng 7/2026"),
    rows: [
      { k: B("Overtime", "Tăng ca"), v: EMP.mai.otJul - EMP.mai.otJun },
      { k: B("Insurance (registered base — unchanged)", "Bảo hiểm (mức đóng đã đăng ký — không đổi)"), v: 0 },
      { k: B("PIT", "Thuế TNCN"), v: -(EMP.mai.pitJul - EMP.mai.pitJun) },
    ],
    total: { k: B("Net pay", "Thực nhận"), v: EMP.mai.netJul - EMP.mai.netJun },
  },
};

/* -----------------------------------------------------------------------------
   THE RATE CHANGE — the (fictional) decree L6 explains and m4 practises.

   BHYT's employee share goes from 1.5% to 2.0%. The new rates arrive as a NEW
   POLICY RECORD with its own code and its own effective date, because that is
   what the product supports; nothing here versions anything in place.

   Every figure below is `payslip()` run twice. It was hand-typed once, in the
   v1 prototype, and the round trip through the tax line is exactly where a
   hand-typed impact goes wrong: the extra 60,000 ₫ of BHYT also REDUCES taxable
   income, so PIT falls by 3,000 and the net drop is 57,000 rather than 60,000.
   -------------------------------------------------------------------------- */
const POLICY_NEXT = {
  name: B("Insurance policy 2026 · August", "Chính sách bảo hiểm 2026 · tháng 8"),
  code: "VN-INS-2026-08",
  effective: "01/08/2026",
  end: "",
  active: true,
  rows: POLICY.rows.map((r) => (r.key === "HI" ? { ...r, employee: 2 } : { ...r })),
};

const RATE_CHANGE = {
  scheme: "HI",
  from: POLICY.rows.find((r) => r.key === "HI").employee,
  to: POLICY_NEXT.rows.find((r) => r.key === "HI").employee,
  before: payslip({ base: EMP_INPUT.mai.base, allowance: EMP_INPUT.mai.allowance,
                    ot: EMP_INPUT.mai.otJul, dependants: EMP_INPUT.mai.dependants }),
  after: payslip({ base: EMP_INPUT.mai.base, allowance: EMP_INPUT.mai.allowance,
                   ot: EMP_INPUT.mai.otJul, dependants: EMP_INPUT.mai.dependants,
                   rates: POLICY_NEXT.rows }),
  get netDelta() { return this.after.net - this.before.net; },
};

/* =============================================================================
   2. THE REPLICA'S OWN ROWS — what each practice screen draws.
   ========================================================================== */
const PRACTICE = {
  /* ------------------------------------------------------ Home › Pulse
     LEARN REFRESH step 2. Every figure is the SAME query the product runs
     (pb_dashboard/models/pb_dashboard.py), applied to this fixture:
       Headcount        every employee in the company, not month-scoped (:247)
                        — Retail's 48 and F&B's 21 — subtitle "N active
                        contracts" (running contracts, :248)
       Monthly payroll  gross on the chosen month's END-OF-MONTH payslips, in
                        any state (:184-215) — both July runs
       Pending approval payslips in "Waiting" (the fallback at :278-280) —
                        the Retail run's 48, frozen while it is with its route
       Active configs   formula configurations in Active, subtitle the sum of
                        their rules (:338-343) */
  get pulse() {
    const b = this.board;
    const waiting = b.filter((r) => r.col === "approval_pending");
    const configs = this.configs;
    return {
      user: "Minh Tú",
      month: RUN.period,
      /* The month strip: one chip per payroll month, bar = people paid. */
      months: [
        { m: B("May", "Th5"), y: "2026", people: 47 },
        { m: B("Jun", "Th6"), y: "2026", people: 47 },
        { m: B("Jul", "Th7"), y: "2026", people: RUN.employees + FNB.employees, latest: true },
      ],
      kpis: {
        headcount: RUN.employees + FNB.employees + 1,
        contracts: RUN.employees + FNB.employees + 1,
        payroll: RUN.totalGross + FNB.totalGross,
        pending: waiting.reduce((t, r) => t + r.employees, 0),
        configs: configs.length,
        rules: configs.reduce((t, c) => t + c.rules, 0),
      },
      /* "Latest pay run" is the NEWEST RUN BY ID (pb_dashboard.py:257-275):
         Retail July, whose 48 payslips are all waiting. */
      latest: { name: RUN.name, slips: RUN.employees, done: 0,
                pending: waiting.reduce((t, r) => t + r.employees, 0) },
    };
  },
  /* The practice company's three pay schemes — the "Pay run for" cards, and
     the Active configs tile. Grouped by kind of run, in the order the Run lens
     draws the groups (pb_formula_studio: End of month, Regular payroll,
     Mid-month advance, Final settlement). */
  configs: [
    { name: RUN.scheme, code: "HOASEN_RETAIL_END", kind: "end_cycle", covered: 48,
      last: B("Retail — June 2026", "Bán lẻ — Tháng 6/2026"), rules: 13 },
    { name: FNB.scheme, code: "HOASEN_FNB_END", kind: "end_cycle", covered: 21,
      last: B("F&B — July 2026", "F&B — Tháng 7/2026"), rules: 12 },
    { name: "Hoa Sen Retail — Mid-Month Advance", code: "HOASEN_RETAIL_MID", kind: "mid_cycle",
      covered: 48, last: B("Retail — mid-July 2026", "Bán lẻ — giữa tháng 7/2026"), rules: 9 },
  ],
  schemeGroups: [
    { kind: "end_cycle", label: B("End of month", "Cuối tháng") },
    { kind: "regular", label: B("Regular payroll", "Kỳ lương thường") },
    { kind: "mid_cycle", label: B("Mid-month advance", "Tạm ứng giữa tháng") },
    { kind: "full_final", label: B("Final settlement", "Quyết toán thôi việc") },
  ],
  recentRuns: [
    { period: B("July 2026", "Tháng 7/2026"), employees: 48, net: 612480000, state: "approval_pending" },
    { period: B("June 2026", "Tháng 6/2026"), employees: 47, net: 596110000, state: "done" },
    { period: B("May 2026", "Tháng 5/2026"), employees: 47, net: 590870000, state: "done" },
  ],

  /* The Run lens's exceptions list: the one person it could not pay. */
  exception: LATER,

  /* -------------------------------------------------------- Pay Run › Run
     The pay data step. Retail's scheme reads three components from a
     spreadsheet, so the rail has four steps; the file has one row for a
     person who is not in Payobook yet — listed, never paid. */
  payData: {
    file: "retail_july_2026.xlsx",
    columns: 6,
    fed: [B("Overtime", "Tăng ca"), B("Allowances", "Phụ cấp"), B("Days worked", "Ngày công")],
    missing: ["Lý Thị Hồng"],
  },

  /* ------------------------------------------------------- Pay Run › Runs
     `col` is a REAL state key (pb_payruns/models/hr_payslip_run.py:51-56):
     draft · approval_pending · done, and cancel for the Rejected list. */
  board: [
    /* The July Retail run is WAITING FOR APPROVAL, at its second step. It is
       that on Pulse, on this board, in the inbox and in every lesson: one run
       cannot be in two states, and a learner who sees it in two learns that
       the screens are decorative. */
    { name: RUN.name, employees: 48, gross: 691200000, net: 612480000,
      col: "approval_pending", cur: true, division: RUN.division,
      step: 1 },
    /* F&B's July run was SENT BACK by the HR lead and is a draft again, with
       the note on it. m2 works on exactly this card. */
    { name: FNB.name, employees: FNB.employees, gross: FNB.totalGross, net: FNB.totalNet,
      col: "draft", cur: true, division: B("F&B", "F&B"),
      sentBack: { by: "Đặng Thu Hà",
                  note: B("NV0203 — overtime reads 46 hours for the week; the timesheet says 4.6. Please correct and send it in again.",
                          "NV0203 — tăng ca ghi 46 giờ trong tuần; bảng chấm công ghi 4,6. Vui lòng sửa rồi gửi lại.") } },
    { name: B("Retail — June 2026", "Bán lẻ — Tháng 6/2026"), employees: 47, gross: 672500000,
      net: 596110000, col: "done", division: RUN.division },
    { name: B("Retail — May 2026", "Bán lẻ — Tháng 5/2026"), employees: 47, gross: 666300000,
      net: 590870000, col: "done", division: RUN.division },
    /* A run that should never have existed, rejected from the board. It sits
       in the collapsed "Rejected pay runs" list, not in a column: a rejected
       run is an outcome, not a stage. */
    { name: B("Retail — July 2026 (made twice)", "Bán lẻ — Tháng 7/2026 (tạo trùng)"),
      employees: 48, gross: 691200000, net: 612480000, col: "cancel", division: RUN.division,
      reason: B("Made by mistake — a second copy of the July run.",
                "Tạo nhầm — bản thứ hai của đợt tháng 7.") },
  ],
  /* Every count here is DERIVED from `board` above, the way the board's own
     numbers row counts them (pb_payruns/models/pb_payruns.py:172-179). */
  get boardKpis() {
    const b = this.board;
    const pipeline = b.filter((r) => r.col === "draft" || r.col === "approval_pending");
    const done = b.filter((r) => r.col === "done");
    return {
      total: b.length,
      inPipeline: pipeline.length,
      myPending: b.filter((r) => r.col === "approval_pending"
                         && ROUTE.steps[r.step] && ROUTE.steps[r.step].you).length,
      done: done.length,
      net: done.reduce((t, r) => t + r.net, 0),
    };
  },

  /* -------------------------------------------------- Pay Run › Payslips
     The run is WAITING, so its payslips are "Waiting for approval" — the
     product freezes them there while the route decides
     (hr_payslip_run.py:920-932). "Need review" on this screen is narrower
     than the Run lens's: a payslip whose take-home pay is zero or below
     (pb_payslip_review.py:127). Nobody here is — so it reads 0, and that is
     not the same as "nothing to check". */
  slips: [
    { emp: EMP.mai, net: EMP.mai.netJul, state: "verify", sel: true },
    { emp: EMP.hung, net: EMP.hung.netJul, state: "verify" },
    { emp: EMP.trang, net: EMP.trang.netJul, state: "verify" },
    { emp: EMP.duc, net: EMP.duc.netJul, state: "verify" },
  ],
  slipTotals: { count: 48, net: 612480000, gross: 691200000, flagged: 0 },

  /* ------------------------------------------------------ Home › Approvals
     THE ONE INBOX. A pay run is one kind of request among many — leave,
     overtime, hiring — and the practice inbox shows that: one request is the
     July run (your turn, at HR lead review), one is somebody else's. */
  get inbox() {
    const run = this.board[0];
    const totals = { net: run.net, gross: run.gross };
    return {
      /* The facts the product FREEZES on a pay-run request when it is sent in
         (pb_payruns/models/hr_payslip_run.py:743-796), in its order. */
      facts: [
        { k: B("Amount", "Số tiền"), v: totals.net, money: true },
        { k: B("Total net pay", "Tổng thực nhận"), v: totals.net, money: true },
        { k: B("Total gross pay", "Tổng lương gộp"), v: totals.gross, money: true },
        { k: B("Payslips", "Phiếu lương"), v: String(run.employees) },
        { k: B("Employees", "Nhân viên"), v: String(run.employees) },
        /* Against the previous DONE run on the same scheme — June. */
        { k: B("Change against the last run", "Thay đổi so với kỳ trước"),
          v: (() => { const pct = Math.round((run.net - 596110000) / 596110000 * 1000) / 10;
                      return B("+" + pct + "%", "+" + String(pct).replace(".", ",") + "%"); })() },
        { k: B("Contains overtime", "Có làm thêm giờ"), v: B("Yes", "Có") },
      ],
      requests: [
        { title: RUN.name, mine: true, process: B("Pay run", "Đợt lương"),
          scope: RUN.scheme + " · " + "Retail — Hà Nội",
          sentBy: ROUTE.preparer, when: B("yesterday", "hôm qua"),
          at: 1, amount: run.net, count: run.employees,
          kind: B("End of month", "Cuối tháng"), due: B("Due tomorrow", "Hạn ngày mai") },
        { title: B("Overtime — Trần Văn Hùng, week 29", "Tăng ca — Trần Văn Hùng, tuần 29"),
          mine: false, process: B("Overtime", "Tăng ca"),
          scope: "Retail — Hà Nội", sentBy: "Trần Văn Hùng", when: B("3 days ago", "3 ngày trước"),
          route: [B("Line manager", "Quản lý trực tiếp"), B("HR lead review", "Trưởng nhân sự soát xét")],
          at: 0, waiting: "Nguyễn Hữu Phước", amount: 0, count: 0,
          kind: B("Overtime", "Tăng ca"), due: B("Due today", "Hạn hôm nay") },
      ],
      tabs: { mine: 1, all: 2, back: 1, done: 4 },
    };
  },

  /* ------------------------------------------------------ Pay Run › Import
     The numbers row, the pipeline and the recent batches, as the Import lens
     draws them (pb_import/static/src/xml/import.xml). THERE IS NO CONFIDENCE
     SCORE on this screen or in its wizard; the old content taught one. */
  importKpis: { batches: 6, done: 4, inProgress: 1, errors: 1 },
  importPipe: [
    { key: "draft", label: B("Draft", "Nháp"), count: 0 },
    { key: "loaded", label: B("Loaded", "Đã tải"), count: 0 },
    { key: "matched", label: B("Matched", "Đã khớp"), count: 1 },
    { key: "validated", label: B("Validated", "Đã kiểm tra"), count: 0 },
    { key: "processing", label: B("Processing", "Đang ghi"), count: 0 },
    { key: "done", label: B("Done", "Hoàn tất"), count: 4 },
  ],
  importBatches: [
    { name: B("July attendance & OT", "Chấm công & tăng ca tháng 7"), rows: 48, state: "matched" },
    { name: B("June attendance & OT", "Chấm công & tăng ca tháng 6"), rows: 47, state: "done" },
  ],
  /* The guided flow's four steps, and the counts its review step prints:
     Rows loaded · Matched · New employees · Need attention. One of the two
     problem rows can be repaired by typing (the cell that could not be read);
     the other is a duplicate, which no amount of typing fixes. */
  wizard: {
    rows: 48, matched: 46, newEmployees: 0, errors: 2,
    errorRows: [
      { name: "Bùi Anh Tuấn", code: "NV0052", fix: true,
        why: B("Overtime cell is not a number", "Ô tăng ca không phải là số") },
      { name: "Đỗ Thị Lan", code: "NV0021",
        why: B("Duplicate row in the file", "Dòng bị lặp trong tệp") },
    ],
    outcome: { employees: 0, payslips: 48 },
  },

  /* LEARN REFRESH step 5 — the three ledgers as pb_payrun_ledgers draws them
     today (ledger.xml, ledger_cockpits.py): Pay Run › Adjust carries two tabs
     (Retro, Proration) over ONE template; Pay Run › Settle carries one
     (Full & Final, whose single tab the product never draws). Counts are one
     quiet line, the money totals stand beside it, and a row opens a drawer in
     place. THE DESCRIPTOR WORDS ARE ENGLISH IN BOTH LANGUAGES because the
     product's are: KPI labels, facets, metrics and drawer labels are plain
     Python strings with no translation (owner item, ledger LR44). Every money
     figure is derived from the rows. */
  ledgers: {
    fullfinal: {
      subtitle: EN("Every settlement, its components and net payable at a glance."),
      /* Hạnh is the leaver on Lifecycle › Exits (same person, same last day),
         held up there by Finance's desk — so her settlement is still Being
         prepared. Lan's was made by hand and is Approved, the only state that
         offers Download. */
      rows: [
        { title: "Bùi Thị Hạnh", code: "NV0044", sub: EN("Retail — Hà Nội · Cashier"), step: 0,
          badge: EN("Auto"), earnings: 8500000 + 980769, deductions: 680000 + 127500 + 85000 },
        { title: "Đỗ Thị Lan", code: "NV0021", sub: EN("Retail — Hà Nội · Store supervisor"), step: 2,
          badge: EN("Manual"), earnings: 16100000, deductions: 1370000, download: true },
      ],
      get counts() {
        return [[EN("Settlements"), this.rows.length],
                [EN("Manual"), this.rows.filter((r) => r.badge.en === "Manual").length]];
      },
      get money() {
        const e = this.rows.reduce((t, r) => t + r.earnings, 0);
        const d = this.rows.reduce((t, r) => t + r.deductions, 0);
        return [{ label: EN("Net payable"), v: e - d, icon: "wallet" },
                { label: EN("Earnings"), v: e, icon: "trending-up" },
                { label: EN("Deductions"), v: d, icon: "trending-down" }];
      },
      /* The three steps a settlement travels (fnf_approval.py: draft/returned →
         pending → approved), with no Vietnamese in the product either. */
      get steps() {
        const at = (i) => this.rows.filter((r) => r.step === i).length;
        return [{ label: EN("Being prepared"), count: at(0) },
                { label: EN("Waiting for approval"), count: at(1) },
                { label: EN("Approved"), count: at(2) }];
      },
      facets: [
        { label: EN("Source"), chips: [EN("Auto"), EN("Manual")] },
        { label: EN("Department"), chips: [EN("Retail — Hà Nội"), EN("F&B — Hà Nội")] },
      ],
      metrics: [EN("Net payable")],
      drawer: {
        title: "Bùi Thị Hạnh", sub: EN("Settlement · 31/07/2026"),
        sections: [
          { label: EN("Settlement"), fields: [[EN("Settlement date"), "31/07/2026"],
                                              [EN("State"), EN("Being prepared")],
                                              [EN("Source"), EN("Auto")]] },
          { label: EN("Breakdown"), fields: [[EN("Basic salary"), 8500000],
                                             [EN("Unused leave"), 980769],
                                             [EN("Social insurance"), -680000],
                                             [EN("Health insurance"), -127500],
                                             [EN("Unemployment insurance"), -85000]] },
          { label: EN("Trace"), fields: [[EN("Import batch"), EN("July 2026 pay data")]] },
        ],
      },
    },
    /* Pay Run › Adjust › Proration. Two kinds of row, both real: a contract
       whose pay changed mid-month (the pay data import splits the month at the
       change) and a person who was here for part of it (pb_workseg writes old =
       new = the monthly amount, and the days do the work). The DAYS are only in
       the drawer, never on the row, and there is no "factor" on this screen. */
    proration: {
      tab: "proration",
      subtitle: EN("Every prorated component, old → new → prorated, per employee."),
      rows: [
        { title: "Vũ Thị Hoa", code: "NV0026", sub: EN("Basic salary"), badge: EN("Posted"), kind: "change",
          old: 9500000, new: 11000000, v: Math.round(9500000 * 15 / 31 + 11000000 * 16 / 31) },
        { title: "Bùi Anh Tuấn", code: "NV0052", sub: EN("Basic salary"), badge: EN("Posted"), kind: "joiner",
          old: 10000000, new: 10000000, v: Math.round(10000000 * 10 / 31) },
      ],
      get counts() {
        return [[EN("Proration lines"), this.rows.length], [EN("Employees"), this.rows.length],
                [EN("Batches"), 1]];
      },
      get money() {
        return [{ label: EN("Total prorated"), v: this.rows.reduce((t, r) => t + r.v, 0), icon: "calculator" }];
      },
      facets: [
        { label: EN("Status"), chips: [EN("Draft"), EN("Posted")] },
        { label: EN("Component"), chips: [EN("Basic salary"), EN("Night-shift allowance")] },
        { label: EN("Batch"), chips: [EN("July 2026 pay data"), EN("June 2026 pay data")] },
      ],
      metrics: [EN("Old"), EN("New"), EN("Prorated")],
      drawer: {
        title: "Vũ Thị Hoa", sub: EN("Basic salary · promoted on 16/07/2026"),
        sections: [
          { label: EN("Period"), fields: [[EN("Effective date"), "16/07/2026"], [EN("Period"), EN("July 2026")],
                                          [EN("Basis"), EN("Calendar Days")], [EN("Period days"), "31"],
                                          [EN("Old days"), "15"], [EN("New days"), "16"]] },
          { label: EN("Money"), fields: [[EN("Old amount"), 9500000], [EN("New amount"), 11000000],
                                         [EN("Prorated"), Math.round(9500000 * 15 / 31 + 11000000 * 16 / 31)]] },
          { label: EN("Trace"), fields: [[EN("Import batch"), EN("July 2026 pay data")]] },
        ],
      },
    },
    /* Pay Run › Adjust › Retro. Back pay the pay data import worked out by
       itself: a pay change dated BEFORE this period, compared with payslips
       already paid for it; the difference for the days it covers is added to
       this month. Khoa's raise was backdated to 1 June; Đức's night-shift
       allowance started on 16 June (15 of June's 30 days). */
    retro: {
      tab: "retro",
      subtitle: EN("Retroactive deltas, old → new → delta, per employee."),
      rows: [
        { title: "Vũ Minh Khoa", code: "NV0038", sub: EN("Basic salary"), badge: EN("Posted"),
          old: 11000000, new: 11800000, v: 800000 },
        { title: EMP.duc.name, code: EMP.duc.code, sub: EN("Night-shift allowance"), badge: EN("Posted"),
          old: 0, new: 300000, v: Math.round(300000 * 15 / 30) },
      ],
      get counts() {
        return [[EN("Retro lines"), this.rows.length], [EN("Employees"), this.rows.length], [EN("Batches"), 1]];
      },
      get money() {
        return [{ label: EN("Total delta"), v: this.rows.reduce((t, r) => t + r.v, 0), icon: "trending-up" }];
      },
      facets: [
        { label: EN("Status"), chips: [EN("Posted"), EN("Cancelled")] },
        { label: EN("Component"), chips: [EN("Basic salary"), EN("Night-shift allowance")] },
        { label: EN("Applied batch"), chips: [EN("July 2026 pay data")] },
      ],
      metrics: [EN("Old"), EN("New"), EN("Delta")],
      drawer: {
        title: "Vũ Minh Khoa", sub: EN("Basic salary · BASIC"),
        sections: [
          { label: EN("Period"), fields: [[EN("Retro period"), "01/06/2026 – 30/06/2026"],
                                          [EN("Change effective"), "01/06/2026"]] },
          { label: EN("Money"), fields: [[EN("Old amount"), 11000000], [EN("New amount"), 11800000],
                                         [EN("Delta"), 800000]] },
          { label: EN("Trace"), fields: [[EN("Applied in batch"), EN("July 2026 pay data")],
                                         [EN("Applied in payslip"), EN("Vũ Minh Khoa — July 2026")],
                                         [EN("Original payslip"), EN("Vũ Minh Khoa — June 2026")]] },
        ],
      },
    },
  },

  /* LEARN REFRESH step 5 — AFTER THE RUN: the four Pay Run tabs a run is
     finished through. Results is the whole run as one grid; Deliver sends the
     money file and the payslips, each through its own approval; Calendar says
     when changes close and when people are paid; Awards puts one-off money
     into a draft run. Words are the product's, Vietnamese where the product
     has it (the rest stays English, as on the screen — ledger LR44). */
  afterrun: {
    /* Results reads the same four people the Payslips replica shows, from the
       same derived EMP figures, with June beside July. */
    get results() {
      const cols = [["BASIC", EN("Basic salary"), "base"], ["ALW", EN("Allowances"), "allowance"],
                    ["OT", EN("Overtime"), "otJul"], ["GROSS", EN("Gross"), "grossJul"],
                    ["BHXH", EN("Social insurance"), "bhxh"], ["PIT", EN("Income tax"), "pitJul"],
                    ["NET", EN("Net pay"), "netJul"]];
      return {
        cols,
        rows: [EMP.mai, EMP.hung, EMP.trang, EMP.duc].map((e) => ({
          name: e.name, code: e.code, vals: cols.map((c) => e[c[2]]),
          delta: e.netJul - e.netJun,
        })),
      };
    },
    deliver: {
      ready: RUN.employees, leftOut: 0,
      bank: "Vietcombank", account: "0011 0045 6789",
    },
    paycal: {
      days: 6, month: B("August 2026", "Tháng 8/2026"), closes: "25/08/2026", paid: "01/09/2026",
      counts: [[B("months planned", "tháng đã lên kế hoạch"), 12], [B("still ahead", "còn phía trước"), 5],
               [B("closed", "đã đóng"), 7], [B("reminders sent", "lời nhắc đã gửi"), 21]],
      months: [
        { m: B("Jul", "Th7"), closes: "25/07", paid: "01/08", closed: true },
        { m: B("Aug", "Th8"), closes: "25/08", paid: "01/09", next: true },
        { m: B("Sep", "Th9"), closes: "25/09", paid: "01/10" },
        { m: B("Oct", "Th10"), closes: "26/10", paid: "01/11" },
      ],
    },
    awards: {
      counts: [[B("waiting for a decision", "đang chờ quyết định"), 1],
               [B("agreed, not in a run", "đã đồng ý, chưa vào kỳ lương"), 1],
               [B("in a pay run", "trong một kỳ lương"), 1], [B("paid this month", "đã trả tháng này"), 2],
               [B("not approved", "không được duyệt"), 0]],
      steps: [[B("Being prepared", "Đang chuẩn bị"), 0], [B("Waiting for approval", "Đang chờ phê duyệt"), 1],
              [B("Agreed, not in a run", "Đã đồng ý, chưa vào kỳ lương"), 1],
              [B("In a pay run", "Trong một kỳ lương"), 1], [B("Paid", "Đã trả"), 2]],
      rows: [
        { who: EMP.mai.name, kind: EN("Spot award"), amount: 500000, paidIn: EN("July 2026"),
          approval: EN("Approved"), where: EN("In the next pay run"), run: RUN.name },
        { who: EMP.trang.name, kind: EN("Incentive"), amount: 1500000, paidIn: EN("July 2026"),
          approval: EN("Approved"), where: EN("Approved"), run: EN("—") },
        { who: EMP.hung.name, kind: EN("Bonus"), amount: 2000000, paidIn: EN("August 2026"),
          approval: EN("Waiting for approval"), where: EN("—"), run: EN("—") },
      ],
    },
  },

  /* ---------------------------------------------------------------- Setup
     The four Setup screens. Same discipline as the Pay Run rows above: every
     count is derived from the list beneath it, and every rate is read from
     POLICY / TAX rather than restated. */

  /* Statutory. `policies` is the ROSTER, and it is deliberately two rows: the
     2025 policy END-DATED and archived, the 2026 one active. That shape IS the
     lesson — the product has no version chain, so a rate change is a second
     record, and the roster is where a learner sees that for themselves. */
  policies: [
    {
      name: POLICY.name, code: POLICY.code, effective: POLICY.effective,
      end: POLICY.end, active: POLICY.active,
      employee: POLICY.totalEmployee, employer: POLICY.totalEmployer,
    },
    {
      name: B("Insurance policy 2025", "Chính sách bảo hiểm 2025"),
      code: "VN-INS-2025", effective: "01/01/2025", end: "31/12/2025",
      active: false, employee: 10.5, employer: 21.5,
    },
  ],
  /* The registered insurance base across the 48-person run. Both legs are the
     POLICY's own totals applied to it, so the KPI band cannot disagree with the
     rates table above it — and the employer leg being twice the employee one is
     the fact the "who pays what" step turns on. */
  statutory: {
    insuranceBase: 570000000,
    taxTables: 2,
    dependents: 6,
    get employeeLeg() { return Math.round(this.insuranceBase * POLICY.totalEmployee / 100); },
    get employerLeg() { return Math.round(this.insuranceBase * POLICY.totalEmployer / 100); },
    get contributions() { return this.employeeLeg + this.employerLeg; },
  },

  /* Formula Engine. The components are the division's rulebook, letter by
     letter — the letters are what the Studio's Names/Letters toggle switches
     to, and they are why a formula can be read aloud. */
  config: {
    code: RUN.config,
    version: RUN.configVersion,
    division: RUN.division,
    components: [
      { l: "A", code: "LCB", kind: "input", label: B("Base salary", "Lương cơ bản") },
      { l: "B", code: "PC", kind: "earning", label: B("Allowances", "Phụ cấp") },
      { l: "C", code: "TANGCA", kind: "earning", label: B("Overtime", "Tăng ca") },
      { l: "D", code: "GROSS", kind: "total", label: B("Gross income", "Tổng thu nhập") },
      { l: "E", code: "BHXH", kind: "deduction", label: B("Social insurance", "Bảo hiểm xã hội") },
      { l: "F", code: "BHYT", kind: "deduction", label: B("Health insurance", "Bảo hiểm y tế") },
      { l: "G", code: "BHTN", kind: "deduction", label: B("Unemployment insurance", "Bảo hiểm thất nghiệp") },
      { l: "H", code: "TNCT", kind: "total", label: B("Taxable income", "Thu nhập chịu thuế") },
      { l: "I", code: "TNCN", kind: "deduction", label: B("Personal income tax", "Thuế TNCN") },
      { l: "J", code: "THUCNHAN", kind: "total", label: B("Net pay", "Thực nhận") },
      /* THE PARAMETER CONSTANTS. These are the numbers that actually price the
         insurance lines — `BHYT = −ROUND(MIN(LCB, CAPLO) × EEHI)` — and they
         live HERE, on the configuration, not on the statutory policy. L6 sends
         the learner to this list to see where a rate really moves a payslip. */
      { l: "K", code: "EESI", kind: "param", label: B("BHXH rate (employee)", "Tỷ lệ BHXH (NLĐ)"),
        value: CONFIG_PARAMS.EESI },
      { l: "L", code: "EEHI", kind: "param", label: B("BHYT rate (employee)", "Tỷ lệ BHYT (NLĐ)"),
        value: CONFIG_PARAMS.EEHI },
      { l: "M", code: "EEUI", kind: "param", label: B("BHTN rate (employee)", "Tỷ lệ BHTN (NLĐ)"),
        value: CONFIG_PARAMS.EEUI },
    ],
    /* The component the editor card is open on. */
    selected: "TNCN",
    /* Two lines of chips, exactly as the Studio prints them. `k` is the chip's
       kind and decides its colour; `op` is an operator and never a component. */
    formula: [
      [{ k: "deduction", t: "TNCN" }, { k: "op", t: "=" }, { k: "op", t: "5% ×" },
       { k: "total", t: "TNCT" }],
      [{ k: "total", t: "TNCT" }, { k: "op", t: "=" }, { k: "total", t: "GROSS" },
       { k: "op", t: "−" }, { k: "deduction", t: "BHXH + BHYT + BHTN" },
       /* Read from the tax table, never typed: the relief figure on a chip and
          the relief figure in the arithmetic are the same number or the screen
          is arguing with itself. */
       { k: "op", t: "−" }, { k: "input", t: TAX.personalDeduction.toLocaleString("en-US") }],
    ],
    dependsOn: ["GROSS", "BHXH", "BHYT", "BHTN"],
    usedBy: ["THUCNHAN"],
    /* The live preview, on the worked example. Derived, like everything else. */
    get preview() {
      return [
        { code: "GROSS", v: EMP.mai.grossJul },
        { code: "TNCT", v: EMP.mai.taxableJul },
        { code: "TNCN", v: EMP.mai.pitJul, neg: true },
        { code: "THUCNHAN", v: EMP.mai.netJul, tot: true },
      ];
    },
  },

  /* Salary Structures — legacy on purpose. New pay logic belongs in a formula
     configuration; these exist because old payslips still reference them. */
  /* LEARN REFRESH step 5 — Settings › Salary Structures as structures.xml
     draws it today. The status words come from a plain Python dict and stay
     English on screen (ledger LR44). This company pays through PAY SCHEMES:
     its contracts name no structure (Mai's drawer shows "—"), so the two old
     structures cover nobody and are kept only because old payslips point at
     them; the probation one is still used by five contracts. */
  structures: {
    categories: 8,
    countries: 1,
    rows: [
      { name: "VN Standard 2023", code: "VN_STD_2023", rules: 14, employees: 0, base: true,
        country: "VN", schedule: EN("Monthly"), updated: "12/2023", badge: EN("Deprecated") },
      { name: "VN Probation 2023", code: "VN_PROB_2023", rules: 9, employees: 5,
        country: "VN", schedule: EN("Monthly"), updated: "12/2023", badge: EN("Active") },
      { name: "VN Expatriate 2022", code: "VN_EXPAT_2022", rules: 8, employees: 0,
        country: "VN", schedule: EN("Monthly"), updated: "03/2022", badge: EN("Archived") },
    ],
    get kpis() {
      const r = this.rows;
      return {
        structures: r.length,
        rules: r.reduce((t, s) => t + s.rules, 0),
        categories: this.categories,
        employees: r.reduce((t, s) => t + s.employees, 0),
        countries: this.countries,
      };
    },
  },

  /* Integrations. One connector is BROKEN, and it looks exactly like a working
     one until the month it matters — which is the whole of the syncbroken
     answer and the integrations station's one mistake. */
  connectors: [
    { name: "Zoho People", icon: "database", status: "ok",
      type: B("Zoho People", "Zoho People"),
      last: B("Synced <1h ago", "Đã đồng bộ <1 giờ trước"),
      mappings: 42, feeds: 3, staged: 0, synced: 4820 },
    { name: B("Monthly pay data file", "Tệp dữ liệu lương hằng tháng"), icon: "file-text", status: "ok",
      type: B("Excel File", "Excel File"),
      last: B("Synced 2 days ago", "Đã đồng bộ 2 ngày trước"),
      mappings: 9, feeds: 1, staged: 0, synced: 312 },
    { name: B("Time clock — Hà Nội", "Máy chấm công — Hà Nội"), icon: "clock", status: "err",
      type: B("Demo / Stub", "Demo / Stub"),
      last: B("Synced 9 days ago", "Đã đồng bộ 9 ngày trước"),
      mappings: 6, feeds: 1, staged: 214, synced: 0 },
  ],
  /* The Zoho connector's own screen (pb_import_advanced connector_cockpit):
     the action bar and the "Automatic fetch" panel. None of its words have
     Vietnamese in the product. */
  connectorScreen: {
    name: "Zoho People",
    actions: [EN("Test connection"), EN("Pull data"), EN("Fetch fields")],
    more: [EN("Configure connection"), EN("Load pay data…"), EN("Open Mapping")],
    schedule: { every: EN("Monthly"), day: 26, at: "06:00", next: "26/08/2026 06:00",
                last: EN("Fetched 312 records · 26/07/2026 06:00") },
  },
  /* Arrivals from the connected system (pb_zoho_bridge inbox): changes the
     connected system sent, each with its outcome. Record changes that need a
     decision wait in the approvals inbox as "Arrivals · N people". */
  arrivals: [
    { when: "27/07 06:02", who: "Vũ Thị Hoa", what: EN("Job changed"), outcome: EN("review") },
    { when: "27/07 06:02", who: "Bùi Anh Tuấn", what: EN("New joiner"), outcome: EN("applied") },
    { when: "27/07 06:01", who: "Đỗ Thị Lan", what: EN("Left the company"), outcome: EN("applied") },
  ],
  get integrationKpis() {
    const c = this.connectors;
    return {
      connectors: c.length,
      connected: c.filter((x) => x.status === "ok").length,
      errors: c.filter((x) => x.status === "err").length,
      synced: c.reduce((t, x) => t + x.synced, 0),
      mappings: c.reduce((t, x) => t + x.mappings, 0),
      staged: c.reduce((t, x) => t + x.staged, 0),
      feeds: c.reduce((t, x) => t + x.feeds, 0),
      stale: c.filter((x) => x.status === "err").length,
    };
  },

  /* ------------------------------------------------------ People (Phase C1)
     A wage here is the REGISTERED CONTRACT BASE, which is also the insurance
     base — one number, one meaning, wherever it is printed.

     LEARN REFRESH step 2: the band counts the WHOLE COMPANY — Retail's 48 and
     F&B's 21 — because that is what the product's headcount counts (Home ›
     Pulse reads every employee, pb_dashboard.py:247), and a People band that
     said 48 beside a Pulse that said 69 would be two screens disagreeing about
     one company. The roster below is still a four-person sample. Đức's
     probation contract is RUNNING: a draft contract would have kept him out of
     the July run, and he is in it. */
  people: {
    draftContracts: 0,
    expiring: 1,
    newHires: 1,
    /* Đức has no bank account on file. Everything else about him is ready and
       his pay still will not land, which is why payroll-readiness is its own
       column rather than a footnote on the wage. */
    notReady: 1,
    get kpis() {
      /* +1 is Nam (LATER): hired, contract running from August, not paid in
         July. The band counts people the company EMPLOYS. */
      const head = RUN.employees + FNB.employees + 1;
      return {
        headcount: head,
        running: head - this.draftContracts,
        expiring: this.expiring,
        newHires: this.newHires,
        wageBill: PRACTICE.statutory.insuranceBase + FNB.insuranceBase + LATER.base,
        readyPct: Math.round((head - this.notReady) / head * 100),
      };
    },
    /* Four of forty-eight, exactly as the Payslips replica shows four slips of
       a forty-eight-slip run. The KPI band counts the company; the roster is a
       sample small enough to read. */
    rows: [
      { emp: EMP.mai, job: B("Store supervisor", "Giám sát cửa hàng"), ready: true },
      { emp: EMP.hung, job: B("Sales associate", "Nhân viên bán hàng"), ready: true,
        expiresIn: 18 },
      { emp: EMP.trang, job: B("Area manager", "Quản lý khu vực"), ready: true },
      { emp: EMP.duc, job: B("Stock keeper", "Nhân viên kho"), ready: false,
        blocker: B("No bank account on file", "Chưa có tài khoản ngân hàng") },
    ],
    /* LEARN REFRESH step 5 — the per-row "Contract" drawer (pb_contracts
       contract_360), opened on Mai. The drawer's words have no Vietnamese in
       the product (ledger LR44) except the source chips, so the replica shows
       them as the screen does. Mai's contract names NO salary structure — so
       the pay scheme pays her, which is the Salary Structures lesson's point
       seen from the other side. */
    drawer: {
      name: EMP.mai.name, ref: "HĐ-2023-0312", ends: EN("Open-ended"), state: EN("Running"),
      terms: [
        [EN("The money"), [[EN("Monthly wage"), EMP.mai.base], [EN("Salary structure"), EN("—")],
                           [EN("Paid"), EN("Monthly")]]],
        [EN("Dates"), [[EN("Contract starts"), "01/03/2023"], [EN("Contract ends"), EN("—")]]],
      ],
      scheme: RUN.scheme,
      comps: [
        { code: "BASIC", name: EN("Basic salary"), v: EMP.mai.base,
          src: B("Held on this contract", "Lưu trên hợp đồng này"), tone: "b" },
        { code: "ALW", name: EN("Lunch allowance"), v: EMP.mai.allowance,
          src: B("Held on this contract", "Lưu trên hợp đồng này"), tone: "b" },
        { code: "OT", name: EN("Overtime"), v: 0,
          src: B("From a pay data file", "Từ tệp dữ liệu lương"), tone: "ok" },
      ],
      history: [
        { what: EN("Monthly wage"), from: 11000000, to: EMP.mai.base, when: "01/01/2026",
          src: EN("Changed on the contract") },
      ],
    },
  },

  /* Contracts. A person is not a contract: the same four people, read as the
     agreements payroll is actually paid from. */
  contracts: {
    get kpis() {
      const p = PRACTICE.people;
      const head = RUN.employees + FNB.employees + 1;
      const bill = p.kpis.wageBill;
      return {
        running: head - p.draftContracts,
        expiring: p.expiring,
        draft: p.draftContracts,
        expired: 0,
        wageBill: bill,
        avgWage: Math.round(bill / head),
      };
    },
    rows: [
      { emp: EMP.mai, kind: B("Indefinite term", "Không xác định thời hạn"),
        period: B("From 01/03/2023", "Từ 01/03/2023"),
        badge: B("Running", "Đang hiệu lực") },
      { emp: EMP.hung, kind: B("12-month term", "Có thời hạn 12 tháng"),
        period: B("01/08/2025 → 31/07/2026", "01/08/2025 → 31/07/2026"),
        badge: B("Expiring", "Sắp hết hạn"), expiresIn: 18 },
      { emp: EMP.trang, kind: B("Indefinite term", "Không xác định thời hạn"),
        period: B("From 15/06/2021", "Từ 15/06/2021"),
        badge: B("Running", "Đang hiệu lực") },
      { emp: EMP.duc, kind: B("Probation", "Thử việc"),
        period: B("From 01/07/2026", "Từ 01/07/2026"),
        badge: B("Running", "Đang hiệu lực") },
    ],
  },

  /* ---------------------------------------------------- Insights (Phase C1)
     Three months of net read off `recentRuns` in the order they were paid, a
     statutory split read off `statutory`, and a pulse whose every figure is a
     count something else in this fixture already holds. */
  get insights() {
    const months = [...this.recentRuns].reverse();
    const s = this.statutory;
    const w = this.workforce;
    /* THE HERO AND THE LEADERBOARD DO NOT HAVE THE SAME SCOPE, and the replica
       has to show that rather than smooth it over. pb_insights' hero is the
       LATEST RUN — `_runs()` carries no state filter — so it is ONE division's
       month, and the product prints the run's name and its state chip beside
       the figure for exactly this reason. The department leaderboard is every
       division in the period. A Retail-only total labelled "Net" above a table
       that sums Retail AND F&B is how a learner concludes the board does not
       add up, so the hero states what it is the net OF. */
    const current = this.board.filter((r) => r.cur);
    return {
      months,
      headline: RUN.totalNet,
      headlineScope: RUN.name,
      headlineState: (this.board.find((r) => r.name === RUN.name) || {}).col,
      /* "avg cost / employee" = (gross + employer contributions) ÷ people paid,
         pb_insights.py; here over the July Retail run. */
      costPerEmployee: Math.round((RUN.totalGross + s.employerLeg) / RUN.employees),
      /* The month-on-month move, computed rather than restated. It is the same
         2.7% m2's anomaly card discusses, and it comes out of the same two
         numbers. */
      get deltaPct() {
        const a = months[months.length - 2].net;
        const b = months[months.length - 1].net;
        return Math.round((b - a) / a * 1000) / 10;
      },
      /* Both divisions of the current period, read off `board`. No re-typed
         F&B literal anywhere: change a board row and the leaderboard, its
         headcounts and the Explorer's total all move with it. */
      departments: current.map((r) => ({ label: r.name, v: r.net, heads: r.employees })),
      statutory: [
        { label: B("Employee leg", "Phần người lao động"), v: s.employeeLeg },
        { label: B("Employer leg", "Phần doanh nghiệp"), v: s.employerLeg },
      ],
      pulse: [
        { label: B("Attendance exceptions", "Ngoại lệ chấm công"), v: w.exceptionTotal },
        { label: B("Payslips at zero or below", "Phiếu thực nhận bằng 0 hoặc âm"), v: RUN.flagged },
        { label: B("Joiners this month", "Vào mới tháng này"), v: w.kpis.joiners },
        { label: B("Leavers this month", "Thôi việc tháng này"), v: w.kpis.leavers },
      ],
    };
  },

  /* Explorer. ONE question, asked properly: net pay by division for July, with
     the filters that scope it shown as removable tags — because a figure read
     without its filters is a figure read out of scope. */
  get explorer() {
    /* The same two board rows the leaderboard uses. The Explorer legitimately
       spans divisions where the hero does not — that difference of scope is
       the whole of the whichtool answer, so the fixture has to make it
       visible rather than accidental. */
    const rows = this.insights.departments;
    return {
      measure: B("Net pay", "Thực nhận"),
      dimension: B("Division", "Bộ phận"),
      filters: [
        { k: B("Period", "Kỳ lương"), v: B("July 2026", "Tháng 7/2026") },
        { k: B("Run state", "Trạng thái đợt"), v: B("Any", "Tất cả") },
      ],
      rows,
      get total() { return rows.reduce((t, r) => t + r.v, 0); },
    };
  },

  /* Workforce Analytics. Employees PAID, not employed — the count comes off the
     runs, which is why it can differ from the headcount on People. */
  get workforce() {
    const months = [...this.recentRuns].reverse();
    /* DERIVED where a derivation exists, DECLARED where it does not — and said
       out loud either way, because a number whose provenance is invisible is
       the one a learner cannot check.
         joiners  : the one Joiner row on the proration ledger (Bùi Anh Tuấn).
         leavers  : the Full & Final rows, counted rather than declared twice.
         the rest : DECLARED INPUTS. There is no attendance model behind this
                    fixture — no clock-ins, no leave requests — so these are
                    the practice company's given facts, in the same way an
                    employee's base salary is. They are consumed by the pulse
                    on Insights, which reads this block instead of holding a
                    second copy. */
    const joiners = this.ledgers.proration.rows.filter(
      (r) => r.kind === "joiner").length;
    const leavers = this.ledgers.fullfinal.rows.length;
    const exceptions = [
      { label: B("Missing clock-out", "Thiếu chấm công ra"), v: 4 },
      { label: B("Unapproved overtime", "Tăng ca chưa duyệt"), v: 3 },
    ];
    return {
      months,
      exceptions,
      exceptionTotal: exceptions.reduce((t, e) => t + e.v, 0),
      /* Declared input, like the two exception counts above it. */
      leaveDays: 9,
      kpis: {
        paid: RUN.employees,
        joiners,
        leavers,
        /* Cost per head, from the run's own net. It is the only figure on this
           screen that survives a headcount change without being re-read. */
        perHead: Math.round(RUN.totalNet / RUN.employees),
      },
      /* Overtime by person, from the same July inputs the payslips are computed
         from. Hùng is at the top of it, which is the flag seen from a
         different screen. */
      overtime: [
        { emp: EMP.hung, v: EMP.hung.otJul },
        { emp: EMP.mai, v: EMP.mai.otJul },
        { emp: EMP.trang, v: EMP.trang.otJul },
      ],
    };
  },

  /* LEARN REFRESH step 5 — Insights › Payroll Report and Insights › Budget.
     The report's totals are the July run's own (RUN); the budget's "People"
     spend is the three months of net the other screens already show. The
     report's words have no Vietnamese in the product. */
  get reports() {
    const spent = this.recentRuns.reduce((t, r) => t + r.net, 0);
    return {
      report: { employees: RUN.employees, gross: RUN.totalGross, net: RUN.totalNet,
                deductions: RUN.totalGross - RUN.totalNet, changes: 6 },
      budget: {
        year: 2026,
        functions: [
          { name: B("People", "Con người"), budget: 3100000000, spent, reading: B("On pace", "Đúng nhịp"), tone: "ok" },
          { name: B("HR operations", "Vận hành nhân sự"), budget: 360000000, spent: 250000000, reading: B("Running warm", "Đang nóng lên"), tone: "warn" },
          { name: B("Admin", "Hành chính"), budget: 240000000, spent: 88000000, reading: B("Behind the year", "Chậm hơn năm"), tone: "" },
        ],
        months: [B("May", "Th5"), B("Jun", "Th6"), B("Jul", "Th7"), B("Aug", "Th8")],
      },
    };
  },

  /* ------------------------------------------------- Compliance (Phase C1)
     The VN filing catalogue, mirrored from pb_govt_reports/models/
     pb_govt_reports.py::_CATALOG. These are PRODUCT FACTS — each tile opens a
     real wizard — so contract.json pins them, and the fixture never invents a
     filing that does not exist.

     Vietnam is the only country with tiles in this catalogue today, and the
     replica shows exactly that: a country chip row, and an honest "coming soon"
     for the country that has none. */
  govreports: {
    country: B("Vietnam", "Việt Nam"),
    period: B("July 2026", "Tháng 7/2026"),
    countries: [B("Vietnam", "Việt Nam"), B("Singapore", "Singapore")],
    /* WHICH CHIP IS ACTIVE, and therefore which of the two states the screen is
       in. The product is a t-if/t-else on `available`: tiles OR the empty card,
       never both. 0 = Vietnam, whose module is installed here. */
    selected: 0,
    groups: [
      {
        /* The catalogue's own icon for this group is `checkCircle`
           (pb_govt_reports.py::_CATALOG); the replica's sprite spells the same
           icon `check-circle`. Same glyph, two naming conventions — mirrored
           rather than re-chosen. */
        label: B("Social Insurance (BHXH)", "Bảo hiểm xã hội (BHXH)"), icon: "check-circle",
        reports: [
          { en: "Sickness & Maternity", vi: "BHXH630 · Ốm đau / Thai sản" },
          { en: "Participant Schedule", vi: "BHXHDSTK01-DV_595 · Mẫu 595" },
          { en: "Dossier Cover Sheet", vi: "Bảng kê hồ sơ D01-TS" },
        ],
      },
      {
        label: B("Labour Changes", "Biến động lao động"), icon: "users",
        reports: [
          { en: "Headcount Increase", vi: "Báo tăng lao động" },
          { en: "Headcount Decrease", vi: "Báo giảm lao động" },
        ],
      },
    ],
    get kpis() {
      return {
        filings: this.groups.reduce((t, g) => t + g.reports.length, 0),
        groups: this.groups.length,
      };
    },
  },

  /* ==========================================================================
     LEARN REFRESH step 3 — PAYROLL SETUP. Six replicas: the guided setup
     (Start + Pay rules + the live pay panel), Mapping's Journey and its
     spreadsheet tab, Component treatment, the Approval Matrix and its builder,
     the Records Desk, and the Group page. Same discipline as everything above:
     every money figure is DERIVED (payslip(), POLICY, TAX), never typed.
     ======================================================================= */

  /* ------------------------------------ Settings › Guided setup › New config
     pb_blueprint. The practice company is setting up its Retail scheme. The
     pay panel is "See it in someone's pay" on the sample employee (Mai) —
     `before` is the scheme without the allowances component, `after` is with
     it: the number a learner watches tick when a component is added. */
  blueprint: {
    name: RUN.scheme,
    code: "HOASEN_RETAIL_END",
    saved: B("Draft · saved 2 min ago", "Bản nháp · đã lưu 2 phút trước"),
    country: B("Vietnam", "Việt Nam"),
    money: B("Pays in ₫ VND", "Trả bằng ₫ VND"),
    cycle: B("End-month payroll", "Kỳ lương cuối tháng"),
    effective: "01/08/2026",
    starters: [
      { name: B("Vietnam · Complete", "Việt Nam · Đầy đủ"), badge: "certified", on: true },
      { name: B("Vietnam · Essentials", "Việt Nam · Cơ bản"), badge: "certified" },
      { name: B("Import Excel workbook", "Nhập sổ tính Excel") },
      { name: B("Blank canvas", "Trang trắng") },
    ],
    audiences: [
      { name: B("Local employees", "Nhân viên trong nước"), on: true },
      { name: B("International employees", "Nhân viên nước ngoài") },
      { name: B("Short-term workers", "Lao động ngắn hạn") },
      { name: B("Guaranteed take-home", "Lương thực nhận cố định") },
    ],
    reallife: [
      { name: B("Joiners & leavers", "Vào làm & nghỉ việc"), on: true },
      { name: B("Annual & event-based pay", "Khoản trả hằng năm & theo sự kiện"), on: true },
      { name: B("Salary changes within a month", "Thay đổi lương giữa tháng") },
      { name: B("Corrections & arrears", "Điều chỉnh & truy lĩnh") },
    ],
    /* The Pay rules step: each component a sentence, with its formula. The
       last one is the component being ADDED in the lesson. */
    rules: [
      { code: "LCB", say: B("Base salary comes from the person's contract.",
                            "Lương cơ bản lấy từ hợp đồng của người đó."), f: "LCB" },
      { code: "TANGCA", say: B("Overtime is the hours worked over the standard, paid at the overtime rate.",
                               "Tăng ca là số giờ làm vượt giờ chuẩn, trả theo đơn giá tăng ca."), f: "LCB ÷ 22 ÷ 8 × 1.5 × OTH" },
      { code: "BHXH", say: B("Social insurance takes 8% of the base, up to the ceiling.",
                             "BHXH trừ 8% trên lương cơ bản, tối đa tới mức trần."), f: "−MIN(LCB, CAP) × EESI" },
      { code: "TNCN", say: B("Income tax is worked out on what is left after insurance and relief.",
                             "Thuế TNCN tính trên phần còn lại sau bảo hiểm và giảm trừ."), f: "5% × TNCT" },
      { code: "PC", say: B("Allowances are paid every month, as written on the contract.",
                           "Phụ cấp được trả hằng tháng, theo hợp đồng."), f: "PC", added: true },
    ],
    get pay() {
      const mai = EMP_INPUT.mai;
      const before = payslip({ base: mai.base, allowance: 0 });
      const after = payslip({ base: mai.base, allowance: mai.allowance });
      const employer = Math.round(mai.base * POLICY.totalEmployer / 100);
      return {
        who: mai.name,
        sub: B("Retail — Hà Nội · sample employee", "Bán lẻ — Hà Nội · nhân viên mẫu"),
        before: before.net, after: after.net, delta: after.net - before.net,
        lines: [
          { k: B("Cash earnings", "Thu nhập bằng tiền"), v: after.gross },
          { k: B("Employee deductions", "Các khoản trừ của nhân viên"), v: after.insurance },
          { k: B("Income tax", "Thuế thu nhập cá nhân"), v: after.pit },
          { k: B("Employer cost", "Chi phí của người sử dụng lao động"), v: employer },
        ],
      };
    },
  },

  /* -------------------------------------------- Settings › Integrations › Mapping
     The Journey board for the Retail scheme, and the ONE value the lesson
     follows along it: Mai's base salary, sent by the HR system as text,
     turned into an amount by a transformation, fed to LCB, printed on her
     payslip. `fed`/`unfed`/`inputs` are counted from the lists below. */
  mapping: {
    from: B("Hoa Sen HR · Employees & pay", "Hoa Sen HR · Nhân viên & lương"),
    to: RUN.scheme,
    systems: [
      { id: "sys", name: "Hoa Sen HR", sub: B("Connected system", "Hệ thống đã kết nối"),
        rows: ["basic_salary", "allowance_monthly", "bank_account"] },
      { id: "sheet", name: "retail_july_2026.xlsx", sub: B("Spreadsheet", "Bảng tính"),
        rows: [B("Overtime hours", "Giờ tăng ca"), B("Days worked", "Ngày công")] },
    ],
    feeds: [{ name: B("Employees & pay", "Nhân viên & lương"), rows: ["basic_salary", "allowance_monthly"] }],
    transforms: [{ name: B("Text to amount", "Chữ thành số tiền"),
                   sub: B("\"12.000.000\" → 12000000", "\"12.000.000\" → 12000000") }],
    scheme: [
      { code: "LCB", label: B("Base salary", "Lương cơ bản"), fed: true },
      { code: "PC", label: B("Allowances", "Phụ cấp"), fed: true },
      { code: "OTH", label: B("Overtime hours", "Giờ tăng ca"), fed: true },
      { code: "NGAYCONG", label: B("Days worked", "Ngày công"), fed: true },
      { code: "KPIBONUS", label: B("KPI bonus", "Thưởng KPI"), fed: false },
    ],
    source: [B("Employee", "Nhân viên"), B("Contract", "Hợp đồng"), B("Bank", "Ngân hàng"),
             B("Contract pay components", "Thành phần lương theo hợp đồng"), B("Pay run", "Đợt lương")],
    get header() {
      const fed = this.scheme.filter((r) => r.fed).length;
      return { inputs: this.scheme.length - fed, fed, unfed: this.scheme.length - fed };
    },
    /* The run-provided values the Spreadsheet tab lists as "From this pay
       run · <Month>" (pb_formula_studio.py:9578), with July's values. */
    runValues: [
      { k: B("Pay month", "Tháng lương"), v: "7" },
      { k: B("Pay year", "Năm lương"), v: "2026" },
      { k: B("Days in the period", "Số ngày trong kỳ"), v: "31" },
      { k: B("Standard working days", "Ngày công chuẩn"), v: "22" },
    ],
    sheetColumns: [
      { col: B("Overtime hours", "Giờ tăng ca"), eg: "12", to: "OTH" },
      { col: B("Days worked", "Ngày công"), eg: "22", to: "NGAYCONG" },
      { col: B("Allowances", "Phụ cấp"), eg: "780000", to: "PC", clash: true },
    ],
  },

  /* ---------------------------------------- Mapping › Component treatment
     The Retail scheme's components as the treatment board lists them. Two
     rows carry the board's own warnings: OTH is counted in hours yet set to
     add to net pay ("Type says otherwise"), and KPI bonus has no pay role yet
     ("Needs your answer"). GROSS is a subtotal — its parts are already added. */
  treatment: {
    rows: [
      { code: "LCB", name: B("Base salary", "Lương cơ bản"), from: B("Contract component", "Thành phần hợp đồng"),
        group: B("Earnings", "Thu nhập"), role: "add", sub: false, type: "amount" },
      { code: "PC", name: B("Allowances", "Phụ cấp"), from: B("Connected system", "Hệ thống đã kết nối"),
        group: B("Earnings", "Thu nhập"), role: "add", sub: false, type: "amount" },
      { code: "OTH", name: B("Overtime hours", "Giờ tăng ca"), from: B("Spreadsheet", "Bảng tính"),
        group: B("Time", "Thời gian"), role: "add", sub: false, type: "qty", clash: true },
      { code: "KPIBONUS", name: B("KPI bonus", "Thưởng KPI"), from: B("Spreadsheet", "Bảng tính"),
        group: B("Earnings", "Thu nhập"), role: "", sub: false, type: "amount", review: true },
      { code: "GROSS", name: B("Gross income", "Tổng thu nhập"), from: B("Calculated", "Được tính"),
        group: B("Totals", "Tổng"), role: "add", sub: true, type: "amount" },
      { code: "BHXH", name: B("Social insurance", "Bảo hiểm xã hội"), from: B("Calculated", "Được tính"),
        group: B("Deductions", "Khấu trừ"), role: "off", sub: false, type: "amount" },
      { code: "TNCN", name: B("Personal income tax", "Thuế TNCN"), from: B("Calculated", "Được tính"),
        group: B("Deductions", "Khấu trừ"), role: "off", sub: false, type: "amount" },
      { code: "ERSI", name: B("Employer social insurance", "BHXH phần doanh nghiệp"), from: B("Calculated", "Được tính"),
        group: B("Employer", "Doanh nghiệp"), role: "employer", sub: false, type: "amount" },
      { code: "THUCNHAN", name: B("Net pay", "Thực nhận"), from: B("Calculated", "Được tính"),
        group: B("Totals", "Tổng"), role: "net", sub: false, type: "amount" },
    ],
    roles: {
      add: B("Added to net pay", "Cộng vào thực nhận"),
      off: B("Taken off net pay", "Trừ khỏi thực nhận"),
      net: B("Net pay itself", "Chính là thực nhận"),
      employer: B("Employer cost", "Chi phí doanh nghiệp"),
      info: B("Information only", "Chỉ để tham khảo"),
      both: B("Both added and taken off", "Vừa cộng vừa trừ"),
    },
    types: {
      amount: B("Amount (currency)", "Số tiền"),
      qty: B("Quantity (hours, days)", "Số lượng (giờ, ngày)"),
      pct: B("Percentage / rate", "Phần trăm / tỷ lệ"),
      text: B("Text", "Văn bản"),
    },
    get counts() {
      return {
        all: this.rows.length,
        review: this.rows.filter((r) => r.review).length,
        clash: this.rows.filter((r) => r.clash).length,
      };
    },
  },

  /* ------------------------------------------------ Settings › Approvals
     The Approval Matrix, grouped by area as the product groups it. The pay
     run row IS the route every other lesson teaches (ROUTE above). Trips are
     set to "No approval needed" — still recorded. */
  matrix: {
    areas: [
      { name: B("Payroll", "Tiền lương"), rows: [
        { name: B("Pay run", "Đợt lương"), route: ROUTE.steps.map((s) => s.title),
          applies: B("Every pay scheme", "Mọi chương trình lương"), status: "live", v: "v3", pay: true },
        { name: B("Scheme change", "Thay đổi chương trình lương"), route: [B("Payroll check", "Kiểm tra bảng lương"), B("Finance approval", "Tài chính phê duyệt")],
          applies: B("Hoa Sen Retail Co.", "Hoa Sen Retail Co."), status: "needs", v: "v1" },
      ] },
      { name: B("People", "Nhân sự"), rows: [
        { name: B("Records Desk bulk changes", "Thay đổi hàng loạt ở Records Desk"), route: [B("HR lead review", "Trưởng nhân sự soát xét")],
          applies: B("Hoa Sen Retail Co.", "Hoa Sen Retail Co."), status: "live", v: "v1" },
        { name: B("Overtime", "Tăng ca"), route: [B("Line manager", "Quản lý trực tiếp"), B("HR lead review", "Trưởng nhân sự soát xét")],
          applies: B("Every team", "Mọi nhóm"), status: "live", v: "v2" },
        { name: B("Business trip", "Công tác"), route: [], fast: true,
          applies: B("Every team", "Mọi nhóm"), status: "live", v: "v2" },
      ] },
    ],
    statuses: {
      live: { l: B("In use", "Đang dùng"), t: "ok" },
      draft: { l: B("Draft", "Nháp"), t: "" },
      needs: { l: B("Needs people", "Cần bổ sung người"), t: "warn" },
      soon: { l: B("Not connected yet", "Chưa kết nối"), t: "b" },
    },
    /* The builder, open on the pay run route. `kind` is the step kind the
       builder's "Add a step" menu offers (builder.js:224-240). */
    builder: {
      steps: [
        { title: ROUTE.steps[0].title, kind: B("Review", "Xem lại"), who: ROUTE.steps[0].who },
        { title: ROUTE.steps[1].title, kind: B("Review", "Xem lại"), who: ROUTE.steps[1].who },
        { title: ROUTE.steps[2].title, kind: B("Final approval", "Phê duyệt cuối"), who: ROUTE.steps[2].who,
          band: B("Only when the run is over ₫500,000,000", "Chỉ khi đợt lương trên ₫500.000.000") },
      ],
      kinds: [B("Review", "Xem lại"), B("Final approval", "Phê duyệt cuối"), B("Joint approval", "Cùng phê duyệt"),
              B("Any one of a team", "Một người bất kỳ trong nhóm"), B("Only when…", "Chỉ khi…"),
              B("Tell somebody", "Báo cho ai đó"), B("No approval needed", "Không cần phê duyệt")],
      safeguards: [B("Who may not decide?", "Ai không được quyết định?"), B("What must be attached?", "Cần đính kèm gì?"),
                   B("When is it due?", "Khi nào đến hạn?"), B("And if it is late?", "Nếu trễ hạn thì sao?")],
      from: "01/08/2026",
    },
  },

  /* ----------------------------------------------------- People › Records
     The Records Desk on the Retail scheme, with three edits typed into the
     grid and waiting for Review. Only fields the scheme maps are offered. */
  records: {
    fields: 9,
    picked: [B("Base salary", "Lương cơ bản"), B("Allowances", "Phụ cấp"), B("Bank account", "Tài khoản ngân hàng")],
    rows: [
      { emp: EMP.mai, vals: [EMP.mai.base, EMP.mai.allowance, "0451000123456"] },
      { emp: EMP.hung, vals: [EMP.hung.base, EMP.hung.allowance, "0451000987654"], edit: [2], was: ["0451000111222"] },
      { emp: EMP.trang, vals: [15800000, EMP.trang.allowance, "0451000555777"], edit: [0], was: [EMP.trang.base] },
      { emp: EMP.duc, vals: [EMP.duc.base, 450000, "0451000333444"], edit: [1], was: [EMP.duc.allowance] },
    ],
    route: B("Records Desk bulk changes", "Thay đổi hàng loạt ở Records Desk"),
    approver: ROUTE.steps[1].who,
    get changes() { return this.rows.filter((r) => r.edit).length; },
  },

  /* ----------------------------------------------------- Settings › Group
     The practice group: two companies, two currencies. The Singapore
     company's pay run is in SGD and STAYS in SGD; the rate below is only
     used when somebody asks to see the group added up in VND. A practice
     rate, not a market one. */
  group: {
    name: "Hoa Sen Group",
    currency: "VND",
    policy: B("The last rate of the month", "Tỷ giá cuối cùng của tháng"),
    policies: [B("The last rate of the month", "Tỷ giá cuối cùng của tháng"),
               B("The rate on the day the pay run ends", "Tỷ giá vào ngày đợt lương kết thúc"),
               B("The average rate for the month", "Tỷ giá bình quân của tháng")],
    companies: [
      { name: "Hoa Sen Retail Co.", flag: "VN", cur: "VND", people: RUN.employees + FNB.employees + 1, schemes: 3 },
      { name: "Hoa Sen Singapore Pte. Ltd.", flag: "SG", cur: "SGD", people: 6, schemes: 1 },
    ],
    rate: 19650,
    /* Months with a rate: ok = a rate from that month, old = an older rate is
       used, none = no rate, so figures stay in their own money. */
    strip: ["ok", "ok", "ok", "ok", "ok", "ok", "old", "none", "none", "none", "none", "none"],
    sgScheme: { name: "Hoa Sen Singapore — Monthly Payroll", net: 31200, people: 6 },
    get compare() {
      return [
        { name: RUN.scheme, cur: "VND", own: RUN.totalNet },
        { name: FNB.scheme, cur: "VND", own: FNB.totalNet },
        { name: this.sgScheme.name, cur: "SGD", own: this.sgScheme.net,
          group: this.sgScheme.net * this.rate },
      ];
    },
  },

  /* ==========================================================================
     LEARN REFRESH step 4 — THE WIDER APP. People › Pay and Plan, the
     Lifecycle boards, Workforce, Access & delegation and the rest of
     Compliance. Four of these are full replicas a learner can press (Hiring,
     the pay review worksheet, Exits, Close the week); the rest are compact
     drawings of the real board so a lesson has something true to stand on.
     Every money figure is DERIVED from EMP / LATER, never typed.

     THE ONE PERSON THE LIFECYCLE LINE FOLLOWS is Hoàng Văn Nam (LATER): the
     store-assistant role he was hired into, his first weeks, his trial
     period — and, years later, his last day. The map lights his road.
     ======================================================================= */

  /* ------------------------------------------------ People › Pay › Bands
     One job family (Retail), three levels. The four practice employees and
     Nam stand in them. Hùng is paid below his band — the one a review should
     look at first. "In the band" is pay ÷ the band's middle. */
  paybands: {
    family: B("Retail", "Bán lẻ"),
    bands: [
      { level: B("Store assistant", "Nhân viên bán hàng"), min: 8500000, mid: 10000000, max: 11500000,
        people: [{ name: LATER.name, pay: LATER.base }, { name: EMP.duc.name, pay: EMP.duc.base }] },
      { level: B("Senior sales associate", "Chuyên viên bán hàng cao cấp"), min: 10800000, mid: 12500000, max: 14200000,
        people: [{ name: EMP.hung.name, pay: EMP.hung.base }, { name: EMP.mai.name, pay: EMP.mai.base }] },
      { level: B("Store supervisor", "Giám sát cửa hàng"), min: 13000000, mid: 15000000, max: 17000000,
        people: [{ name: EMP.trang.name, pay: EMP.trang.base }] },
    ],
    health: [
      { k: B("Paid below the band", "Được trả dưới khoảng lương"), v: 1, tone: "warn" },
      { k: B("Paid above the band", "Được trả trên khoảng lương"), v: 0, tone: "ok" },
      { k: B("Newer people paid more", "Người mới được trả cao hơn"), v: 0, tone: "ok" },
      { k: B("A manager paid less", "Quản lý được trả thấp hơn"), v: 0, tone: "ok" },
      { k: B("How wide each band has become", "Mỗi khoảng lương đã rộng ra bao nhiêu"), v: "35%", tone: "ok" },
    ],
    fairness: { gap: "3.1%", level: B("By level", "Theo cấp bậc") },
  },

  /* ------------------------------------------ People › Pay › Review
     The 2026 review for the four practice employees. Budget = 3.5% of their
     monthly base; each rise is its score's guidance (a person below the band
     gets more). The meter FILLS as the rises are added — the lesson's hero. */
  payreview: {
    name: B("Annual pay review 2026", "Xét lương năm 2026"),
    budgetPct: 3.5,
    stages: [B("Being written", "Đang soạn"), B("With HR", "Đang ở nhân sự"), B("With finance", "Đang ở tài chính"),
             B("With the CEO", "Đang ở tổng giám đốc"), B("Approved", "Đã duyệt"), B("Applied", "Đã áp dụng")],
    at: 0,
    rows: [
      { emp: EMP.mai, score: 4, pct: 4, mark: "line" },
      { emp: EMP.hung, score: 3, pct: 5, mark: "line", below: true },
      { emp: EMP.trang, score: 5, pct: 2, mark: "out" },
      { emp: EMP.duc, score: 3, pct: 3, mark: "line" },
    ],
    get wage() { return this.rows.reduce((t, r) => t + r.emp.base, 0); },
    get budget() { return Math.round(this.wage * this.budgetPct / 100); },
    rise(r) { return Math.round(r.emp.base * r.pct / 100); },
    get used() { return this.rows.reduce((t, r) => t + this.rise(r), 0); },
  },

  /* ----------------------------------------------- People › Plan
     The Decision Room on next year for the practice company. The estimate is
     the room's own arithmetic; Exact cost runs the real pay scheme and lands
     within half a percent. */
  decisionroom: {
    presets: [B("Grow thoughtfully", "Tăng trưởng thận trọng"), B("Invest in people", "Đầu tư vào con người"),
              B("Ease overtime", "Giảm làm thêm giờ")],
    levers: [
      [B("Add people", "Thêm người"), "+4 · " + "03/2027"],
      [B("Salary increase", "Tăng lương"), "3.5% · 01/2027"],
      [B("Overtime per person", "Tăng ca mỗi người"), "−2 h"],
      [B("Leavers", "Người nghỉ việc"), "8%"],
    ],
    results: [B("Work & shifts", "Công việc & ca làm"), B("Why profit changed", "Vì sao lợi nhuận thay đổi"),
              B("People & pay", "Con người & lương"), B("Room to hire", "Dư địa tuyển dụng")],
    estimate: 7420000000,
    exact: 7388500000,
  },

  /* ----------------------------------------------- Lifecycle › Hiring
     The role Nam was hired into, a year before the practice July. Four steps
     on every role; "Step 3 of 4" is where candidates are met. */
  hiring: {
    numbers: [
      [B("Open", "Mở"), 3], [B("Awaiting sign-off", "Chờ phê duyệt"), 1], [B("Waiting on you", "Đang chờ bạn"), 1],
      [B("Candidates", "Ứng viên"), 14], [B("Over budget", "Vượt ngân sách"), 0], [B("Interviews this week", "Phỏng vấn tuần này"), 4],
    ],
    steps: [
      [B("Request & approve", "Đề xuất & phê duyệt"), 1], [B("Prepare & publish", "Chuẩn bị & đăng tin"), 1],
      [B("Meet your candidates", "Gặp ứng viên"), 1], [B("Welcome aboard", "Chào mừng gia nhập"), 0],
    ],
    roles: [
      { title: B("Store assistant — Hà Nội", "Nhân viên bán hàng — Hà Nội"), step: 3, cands: 6,
        next: B("Two opinions are late — ask the panel for them.", "Hai ý kiến đánh giá đang trễ — hãy nhắc hội đồng phỏng vấn.") },
      { title: B("Cashier — Hải Phòng", "Thu ngân — Hải Phòng"), step: 1, cands: 0,
        next: B("Waiting for the HR lead to sign off.", "Đang chờ trưởng nhân sự phê duyệt.") },
      { title: B("Stock controller — Hà Nội", "Nhân viên kiểm kho — Hà Nội"), step: 2, cands: 0,
        next: B("Write the advert, then publish it.", "Viết tin tuyển dụng, rồi đăng tin.") },
    ],
    wizard: {
      title: B("Let's shape your next hire.", "Hãy cùng phác thảo vị trí tuyển dụng tiếp theo."),
      tabs: [B("The role", "Vị trí"), B("Responsibilities", "Trách nhiệm"), B("Interview plan", "Kế hoạch phỏng vấn"),
             B("Budget & review", "Ngân sách & xem lại")],
      route: [B("Manager", "Quản lý"), B("HR lead", "Trưởng nhân sự"), B("Finance — only if over budget", "Tài chính — chỉ khi vượt ngân sách")],
      salary: LATER.base,
    },
    stages: [B("Screening", "Sàng lọc"), B("Panel Review", "Hội đồng xem xét"), B("Recruiter Phone Call", "Gọi điện sơ vấn"),
             B("Assignment", "Bài tập"), B("Discussion 1", "Trao đổi 1"), B("Offer Stage", "Giai đoạn đề nghị"), B("Joined", "Đã nhận việc")],
  },

  /* ----------------------------------------------- Lifecycle › New joiners
     Nam, a week before 1 August, with Mai as his buddy. */
  joiners: {
    numbers: [[B("Joining this week", "Vào làm tuần này"), 2], [B("Already started", "Đã bắt đầu làm việc"), 3],
              [B("Still without a buddy", "Chưa có người đồng hành"), 1], [B("Steps overdue", "Bước quá hạn"), 0],
              [B("Said they are struggling", "Cho biết đang gặp khó khăn"), 0]],
    steps: [[B("Getting ready", "Đang chuẩn bị"), 2], [B("Settling in", "Đang hòa nhập"), 3], [B("Checklist done", "Đã xong danh mục"), 4]],
    rows: [
      { name: LATER.name, sub: B("Store assistant · starts 01/08/2026", "Nhân viên bán hàng · bắt đầu 01/08/2026"), step: 0,
        chip: B("Buddy: Nguyễn Thị Mai", "Người đồng hành: Nguyễn Thị Mai") },
      { name: "Đinh Thị Yến", sub: B("Cashier · starts 03/08/2026", "Thu ngân · bắt đầu 03/08/2026"), step: 0,
        chip: B("No buddy yet", "Chưa có người đồng hành"), warn: true },
    ],
    todo: [B("Laptop and store card ready", "Máy tính và thẻ cửa hàng đã sẵn sàng"), B("Bank account on file", "Đã có tài khoản ngân hàng"),
           B("First-week rota sent", "Đã gửi lịch ca tuần đầu")],
    done: [B("Contract signed", "Đã ký hợp đồng"), B("Buddy chosen", "Đã chọn người đồng hành")],
  },

  /* ----------------------------------------------- Lifecycle › Probation
     Nam's two-month trial, in its last week. */
  probation: {
    numbers: [[B("In a trial period", "Đang thử việc"), 4], [B("Reviews running", "Đánh giá đang chạy"), 2],
              [B("Waiting on a decision", "Đang chờ quyết định"), 1], [B("Answers overdue", "Câu trả lời quá hạn"), 1],
              [B("Ending within a week", "Kết thúc trong vòng một tuần"), 1]],
    steps: [[B("Choose peers", "Chọn đồng nghiệp"), 1], [B("Gather perspectives", "Thu thập ý kiến"), 1],
            [B("Manager conversation", "Trao đổi với quản lý"), 1], [B("HR & leadership review", "Nhân sự và lãnh đạo xem xét"), 1],
            [B("Share the outcome", "Thông báo kết quả"), 0]],
    rows: [
      { name: LATER.name, sub: B("Trial ends 30/09/2026 · Colleagues asked: 3 of 4 answered", "Thử việc kết thúc 30/09/2026 · Đồng nghiệp được hỏi: 3/4 đã trả lời"), step: 3 },
      { name: "Đinh Thị Yến", sub: B("Trial ends 02/10/2026", "Thử việc kết thúc 02/10/2026"), step: 1 },
    ],
    verdicts: [B("Confirm them", "Xác nhận chính thức"), B("Extend the trial", "Kéo dài thử việc"), B("Do not confirm", "Không xác nhận")],
  },

  /* ----------------------------------------------- Lifecycle › Growth plans */
  growth: {
    numbers: [[B("Open", "Đang mở"), 2], [B("Still a conversation", "Vẫn đang trao đổi"), 1], [B("Plans running", "Kế hoạch đang chạy"), 1],
              [B("Waiting on a decision", "Đang chờ quyết định"), 0], [B("Drifting or at risk", "Chệch hướng hoặc có rủi ro"), 1]],
    steps: [[B("Asked", "Đã yêu cầu"), 1], [B("Coaching", "Kèm cặp"), 0], [B("Plan running", "Kế hoạch đang chạy"), 1], [B("Decision", "Quyết định"), 0]],
    rows: [
      { name: "Võ Quang Huy", sub: B("Plan running · 2 of 3 objectives on track", "Kế hoạch đang chạy · 2/3 mục tiêu đúng hướng"), step: 2 },
    ],
  },

  /* ----------------------------------------------- Lifecycle › Contracts */
  contractends: {
    numbers: [[B("Ending within 60 days", "Kết thúc trong vòng 60 ngày"), 3], [B("Nobody has decided", "Chưa ai quyết định"), 1],
              [B("Waiting to be agreed", "Đang chờ đồng ý"), 1], [B("Being evaluated", "Đang được đánh giá"), 1],
              [B("Made permanent this year", "Chuyển chính thức trong năm nay"), 6]],
    steps: [[B("Running", "Đang hiệu lực"), 41], [B("Decision needed", "Cần quyết định"), 1], [B("Being agreed", "Đang chờ đồng ý"), 1], [B("Decided", "Đã quyết định"), 2]],
    rows: [
      { name: EMP.duc.name, sub: B("Fixed term ends 30/09/2026", "Hợp đồng xác định thời hạn kết thúc 30/09/2026"), step: 1 },
    ],
    choices: [B("Make it permanent", "Chuyển chính thức"), B("Extend it", "Gia hạn"), B("Let it end", "Để hết hạn")],
  },

  /* ----------------------------------------------- Lifecycle › Exits
     A leaver whose last day has passed. Three desks have signed; Finance
     has not, so the settlement is held — and says why. */
  exits: {
    numbers: [[B("Leaving this month", "Nghỉ việc trong tháng này"), 2], [B("Last day has passed", "Đã qua ngày làm việc cuối"), 1],
              [B("Settlements held up", "Quyết toán bị vướng"), 1], [B("Clearances still open", "Xác nhận bàn giao còn mở"), 1],
              [B("Items not back yet", "Tài sản chưa trả lại"), 1]],
    steps: [[B("Working their notice", "Đang trong thời gian báo trước"), 1], [B("Signing off", "Đang xác nhận bàn giao"), 1],
            [B("Ready to settle", "Sẵn sàng quyết toán"), 0], [B("Settled", "Đã quyết toán"), 3]],
    leaver: { name: "Bùi Thị Hạnh", code: "NV0044", last: "31/07/2026", role: B("Cashier — Hà Nội", "Thu ngân — Hà Nội") },
    desks: [
      { k: "IT", done: true, what: B("Laptop returned", "Đã trả máy tính") },
      { k: B("HR", "Nhân sự"), done: true, what: B("Exit conversation held", "Đã trao đổi trước khi nghỉ") },
      { k: B("Finance", "Tài chính"), done: false, what: B("Store float not counted back", "Chưa đếm lại quỹ tiền lẻ của quầy") },
      { k: B("Admin", "Quản trị viên"), done: true, what: B("Store card handed in", "Đã nộp thẻ cửa hàng") },
    ],
  },

  /* ----------------------------------------------- Workforce › Today */
  wftoday: {
    tiles: [[B("On shift", "Theo ca"), 38], [B("Late", "Trễ"), 3], [B("Not started", "Chưa bắt đầu"), 5],
            [B("Checked out", "Đăng xuất"), 2], [B("On leave", "Đang nghỉ phép"), 4]],
    needs: [
      [B("Leave requests", "Đơn nghỉ phép"), 2],
      [B("Overtime to approve", "Tăng ca cần duyệt"), 7],
      [B("Flags on this week", "Cờ cảnh báo tuần này"), 3],
    ],
    clean: 5,
  },

  /* ----------------------------------------------- Workforce › Time / Time Off / Overtime */
  wftime: {
    tabs: [B("Timeline", "Dòng thời gian"), B("Week Grid", "Lưới tuần"), B("Exceptions", "Ngoại lệ"), B("Import", "Nhập")],
    exceptions: 4,
    leave: [{ name: EMP.mai.name, what: B("Annual leave · 12–14/08 · 3 days", "Nghỉ phép năm · 12–14/08 · 3 ngày") }],
    ot: [
      { name: EMP.hung.name, what: B("Thu 30/07 · 3 h", "Th5 30/07 · 3 giờ"), near: true },
      { name: EMP.trang.name, what: B("Sat 01/08 · 2 h", "Th7 01/08 · 2 giờ") },
    ],
    otNumbers: [[B("pending approvals", "chờ duyệt"), 7], [B("near or over the ceiling", "gần hoặc vượt mức trần"), 1],
                [B("bonus hours this month", "giờ thưởng tháng này"), 12]],
    caps: [[B("Monthly", "Tháng"), "40 h"], [B("Annual", "Năm"), "200 h"]],
  },

  /* ----------------------------------------------- Workforce › Close
     The practice week 27 Jul – 2 Aug with three flags left. The lock stays
     grey until every flag is fixed or approved as it is. */
  wfclose: {
    week: B("Week of 27/07 – 02/08/2026", "Tuần 27/07 – 02/08/2026"),
    flags: [
      { name: EMP.hung.name, kind: B("Missing check-out", "Thiếu giờ ra"), day: B("Tue 28/07", "Th3 28/07") },
      { name: EMP.trang.name, kind: B("Overtime over the plan", "Tăng ca vượt kế hoạch"), day: B("Thu 30/07", "Th5 30/07") },
      { name: EMP.duc.name, kind: B("Late, no reason given", "Đi trễ, không có lý do"), day: B("Mon 27/07", "Th2 27/07") },
    ],
    handoff: [[B("Regular hours", "Giờ thông thường"), "1,824 h"], [B("Overtime", "Tăng ca"), "46 h"],
              [B("Bonus hours", "Giờ thưởng"), "12 h"]],
  },

  /* ----------------------------------------------- Settings › Access & delegation
     biz_access. Roles are what people are given; a hand-over lends yours for
     a while and comes back by itself. */
  access: {
    roles: [
      { name: B("Payroll officer", "Chuyên viên tính lương"), line: B("Runs the monthly pay run and fixes its data.", "Chạy đợt lương hằng tháng và sửa dữ liệu của nó."), held: 2 },
      { name: B("HR lead", "Trưởng nhân sự"), line: B("Reviews pay runs and people changes.", "Soát xét đợt lương và thay đổi nhân sự."), held: 1 },
      { name: B("Line manager", "Quản lý trực tiếp"), line: B("Sees their own team and approves its time.", "Xem nhóm của mình và duyệt giờ công của nhóm."), held: 6 },
    ],
    handover: { to: ROUTE.steps[0].who, until: "21/08/2026" },
  },

  /* ----------------------------------------------- Compliance › Bank / Young workers / Audit */
  compliance: {
    bank: [[B("Draft", "Nháp"), 1], [B("HR Review", "Nhân sự xét duyệt"), 1], [B("Finance Review", "Tài chính xét duyệt"), 0],
           [B("Approved", "Đã duyệt"), 12]],
    young: [[B("Protected", "Được bảo vệ"), 2], [B("Compliant this week", "Tuân thủ tuần này"), 2],
            [B("Violations in the last 30 days", "Vi phạm trong 30 ngày qua"), 0], [B("Missing birthdays", "Thiếu ngày sinh"), 1]],
    audit: [[B("Events today", "Sự kiện hôm nay"), 64], [B("Last 7 days", "7 ngày qua"), 412]],
  },

  /* ----------------------------------------------- Home › Wall and the rest of People */
  more: {
    praise: { from: EMP.trang.name, to: EMP.mai.name, value: B("Customers first", "Khách hàng là trên hết"),
              text: B("Stayed late to help a customer find the right size.", "Ở lại muộn để giúp khách tìm đúng cỡ.") },
    tiles: [
      [B("Where they work", "Nơi họ làm việc"), B("People who work for more than one company", "Người làm cho nhiều công ty")],
      [B("Assets", "Tài sản"), B("Laptops, phones and cards, and who holds them", "Máy tính, điện thoại, thẻ, và ai đang giữ")],
      [B("Goals", "Mục tiêu"), B("What each person plans this year", "Điều mỗi người dự định trong năm")],
      [B("Announce", "Thông báo"), B("Messages to your people, on one calendar", "Thông báo tới mọi người, trên một lịch")],
    ],
  },
};

/* =============================================================================
   3. THE RAIL — mirrors the product's left rail and each hub's tabs.
   -----------------------------------------------------------------------------
   LEARN REFRESH step 2. The practice company used to draw the old six-section
   sidebar, which no longer exists: since the rail cutover the product has
   nine pages on its rail (pb_*_hub modules, in rail order) and every working
   screen is a TAB inside one of them. The replica draws the same rail and, on
   the page being shown, the same tabs in the same order with the same words —
   the Vietnamese included, as the product's own .po files now say it.

   `screen` names the replica screen a tab opens. A tab with NO screen is drawn
   present-but-quiet ("Not in the practice company"): it is really there in
   the product, and a replica that hid it would teach a different page; a
   replica that pretended to open it would be a dead click. `sub` is a tab's
   own inner tabs (Pay Run › Adjust has Retro and Proration).

   Settings is not a row of tabs but a page of categories (pb_settings
   settings_hub.js:132-241): its screens open FROM that page, so the replica
   draws it as the `hub_settings` screen and names the category a screen
   came from in the breadcrumb. */
const MENU = [
  {
    key: "home", icon: "home", label: B("Home", "Trang chủ"), section: null,
    lenses: [
      { key: "pulse", label: B("Pulse", "Tổng quan"), screen: "dashboard" },
      { key: "approvals", label: B("Approvals", "Phê duyệt"), screen: "approvals" },
      { key: "wall", label: B("Wall", "Bảng vinh danh"), screen: "peoplemore" },
      { key: "coming_up", label: B("Announce", "Thông báo") },
    ],
  },
  {
    key: "pay", icon: "zap", label: B("Pay Run", "Đợt lương"),
    section: B("Operate", "Vận hành"),
    lenses: [
      { key: "run", label: B("Run", "Chạy lương"), screen: "runpayroll" },
      { key: "runs", label: B("Runs", "Các đợt lương"), screen: "payruns" },
      { key: "payslips", label: B("Payslips", "Phiếu lương"), screen: "payslips" },
      { key: "results", label: B("Results", "Kết quả"), screen: "results" },
      { key: "import", label: B("Import", "Nhập"), screen: "import" },
      { key: "deliver", label: B("Deliver", "Chi trả"), screen: "deliver" },
      { key: "adjust", label: B("Adjust", "Điều chỉnh"), screen: "retro",
        sub: [{ key: "retro", label: B("Retro", "Hồi tố"), screen: "retro" },
              { key: "proration", label: B("Proration", "Phân bổ theo tỷ lệ"), screen: "proration" }] },
      /* Settle has ONE tab (Full & Final), and the product never draws a strip
         of one (ledger.xml: `tabs.length > 1`), so neither does the replica. */
      { key: "settle", label: B("Settle", "Quyết toán"), screen: "fullfinal" },
      { key: "paycal", label: B("Calendar", "Lịch lương"), screen: "paycal" },
      { key: "awards", label: B("Awards", "Thưởng"), screen: "awards" },
    ],
  },
  {
    key: "people", icon: "users", label: B("People", "Con người"), section: null,
    lenses: [
      { key: "employees", label: B("Employees", "Nhân viên"), screen: "employees",
        also: ["contracts"] },
      { key: "records", label: B("Records", "Hồ sơ"), screen: "records" },
      { key: "pay", label: B("Pay", "Lương"), screen: "paybands", also: ["payreview"] },
      { key: "where", label: B("Where they work", "Nơi họ làm việc") },
      { key: "assets", label: B("Assets", "Tài sản") },
      { key: "praise", label: B("Praise", "Khen ngợi") },
      { key: "goals", label: B("Goals", "Mục tiêu") },
      { key: "announcements", label: B("Announce", "Thông báo") },
      { key: "plan", label: B("Plan", "Kế hoạch"), screen: "decisionroom" },
    ],
  },
  {
    key: "lifecycle", icon: "git-branch", label: B("Lifecycle", "Vòng đời nhân sự"), section: null,
    lenses: [
      { key: "journeys", label: B("Journeys", "Hành trình") },
      { key: "hiring", label: B("Hiring", "Tuyển dụng"), screen: "hiring" },
      { key: "newjoiners", label: B("New joiners", "Nhân viên mới"), screen: "joiners" },
      { key: "exits", label: B("Exits", "Nghỉ việc"), screen: "exits" },
      { key: "probation", label: B("Probation", "Thử việc"), screen: "probation" },
      { key: "pip", label: B("Growth plans", "Kế hoạch phát triển"), screen: "growth" },
      { key: "contracts", label: B("Contracts", "Hợp đồng"), screen: "contractends" },
    ],
  },
  {
    key: "workforce", icon: "compass", label: B("Workforce", "Lực lượng lao động"), section: null,
    lenses: [
      { key: "today", label: B("Today", "Hôm nay"), screen: "wftoday" },
      { key: "schedule", label: B("Schedule", "Lịch ca") },
      { key: "time", label: B("Time", "Chấm công"), screen: "wftime" },
      { key: "timeoff", label: B("Time Off", "Nghỉ phép") },
      { key: "overtime", label: B("Overtime", "Tăng ca") },
      { key: "trips", label: B("Trips", "Công tác") },
      { key: "approvals", label: B("Approvals", "Phê duyệt") },
      { key: "close", label: B("Close", "Chốt kỳ"), screen: "wfclose" },
      { key: "holidays", label: B("Holidays", "Ngày lễ") },
      { key: "field", label: B("Field", "Hiện trường") },
    ],
  },
  {
    key: "insights", icon: "trending-up", label: B("Insights", "Phân tích"),
    section: B("Understand", "Hiểu"),
    lenses: [
      { key: "pulse", label: B("Pulse", "Tổng quan"), screen: "insights" },
      { key: "explorer", label: B("Explorer", "Khám phá dữ liệu"), screen: "explorer" },
      { key: "workforce", label: B("Workforce", "Lực lượng lao động"), screen: "workforcean" },
      { key: "payroll", label: B("Payroll Report", "Báo cáo lương"), screen: "reports" },
      { key: "budget", label: B("Budget", "Ngân sách"), screen: "reports" },
      { key: "hiring", label: B("Hiring", "Tuyển dụng") },
      { key: "training", label: B("Training", "Đào tạo") },
      { key: "goals", label: B("Goals", "Mục tiêu") },
    ],
  },
  {
    key: "compliance", icon: "shield-check", label: B("Compliance", "Tuân thủ"), section: null,
    lenses: [
      { key: "filings", label: B("Filings", "Tờ khai"), screen: "govreports" },
      { key: "bank", label: B("Bank", "Ngân hàng"), screen: "compliancemore" },
      { key: "young", label: B("Young workers", "Lao động chưa thành niên") },
      { key: "audit", label: B("Audit", "Nhật ký kiểm toán") },
    ],
  },
  {
    key: "learn", icon: "book-open", label: B("Learn", "Học cùng Payobook"),
    section: B("Grow", "Phát triển"),
    lenses: [
      { key: "lessons", label: B("Lessons", "Bài học") },
      { key: "training", label: B("Training", "Đào tạo") },
      { key: "team", label: B("Team", "Nhóm") },
      { key: "settings", label: B("Settings", "Cài đặt") },
    ],
  },
  {
    key: "settings", icon: "settings", label: B("Settings", "Cài đặt"), section: null, page: true,
    screen: "hub_settings",
    /* The category page, in the product's order. `screen` opens a replica;
       the rest are drawn quiet. */
    lenses: [
      { key: "formula", label: B("Formula Engine", "Bộ máy công thức"), screen: "formula",
        card: B("Formula Studio", "Xưởng công thức") },
      { key: "structures", label: B("Salary Structures", "Cấu trúc lương"), screen: "structures" },
      { key: "statutory", label: B("Statutory", "Bảo hiểm & Thuế"), screen: "statutory",
        card: B("Insurance & Tax", "Bảo hiểm & Thuế") },
      /* Integrations has two cards: its connectors and Mapping (whose tabs
         include Component treatment). Both replicas live under it. */
      { key: "integrations", label: B("Integrations", "Tích hợp"), screen: "integrations",
        also: ["mapping", "treatment"] },
      { key: "payroll", label: B("Payroll defaults", "Mặc định tính lương") },
      { key: "org", label: B("Companies & Tenants", "Công ty & Đơn vị thuê bao") },
      { key: "nav", label: B("Navigation", "Điều hướng") },
      { key: "company", label: B("Your company", "Công ty của bạn") },
      { key: "vendors", label: B("Vendors", "Nhà cung cấp") },
      { key: "guided_setup", label: B("Guided setup", "Thiết lập có hướng dẫn"),
        card: B("New configuration", "Cấu hình mới"), screen: "blueprint" },
      { key: "group", label: B("Group", "Tập đoàn"), screen: "schemes" },
      { key: "access", label: B("Access & delegation", "Quyền truy cập & uỷ quyền"), screen: "access" },
      { key: "approvals", label: B("Approvals", "Phê duyệt"), screen: "matrix",
        card: B("Approval Matrix", "Ma trận phê duyệt") },
      { key: "hiring", label: B("Hiring", "Tuyển dụng") },
      { key: "about", label: B("About Payobook", "Về Payobook") },
      { key: "announcements", label: B("Announcements", "Thông báo") },
      { key: "demo_data", label: B("Demo data", "Dữ liệu mẫu") },
    ],
  },
];

/* =============================================================================
   3b. THE FIELDS A LEARNER MAY TYPE IN  (LEARNOS Phase 5)
   -----------------------------------------------------------------------------
   ONE TABLE, THREE READERS, AND THAT IS THE ENTIRE POINT OF IT.

     · `engine/screens.js` draws a real <input> at each of these anchors, and
       at no other anchor. The replica has no free-text fields anywhere else,
       so a step cannot ask a learner to type into a picture of a field.
     · `engine/input_match.js` reads `kind` to decide how loosely the typed
       value is compared — thousands marks are optional in a number, tone
       marks are optional in a name.
     · `tools/gen_learn_data.py` REFUSES an `act: "input"` step whose anchor is
       not a key here, and refuses a key here the replica does not draw. An
       input step pointed at a paragraph is a step nobody can ever complete,
       and it would fail silently: the learner types, nothing happens, and the
       walkthrough is stuck with no error anywhere.

   THE EXPECTED VALUE IS NOT HERE. It is the step's own `value`, in both
   languages, because it is content: what to type is part of the lesson, and a
   second copy of it beside the field is a second thing to keep in step.

   Keys are `rep-` names because these fields exist only in the practice
   company. The product's import wizard repairs a cell in its own way and the
   product's employee form is a form view; neither is what is drawn here, and
   the Coach must never claim to point at one of these on a live screen.
   ========================================================================== */
const INPUT_ANCHORS = {
  /* The import wizard's one repairable cell. A MONEY figure, so the reader's
     own thousands mark has to be accepted: the same step is played by somebody
     typing 1,200,000 and by somebody typing 1.200.000. */
  "rep-impfix": { kind: "number" },
  /* The practice employee form's name field. A NAME, so tone marks are
     optional — the keyboard a learner has is not part of the lesson. */
  "rep-newemp-name": { kind: "text" },
};

/* The import wizard is a FLOW, not a destination — it has no sidebar leaf, so
   it cannot appear in MENU. Named here so the shell can still title it. */
const SUB_SCREENS = {
  importwizard: {
    owner: "import",
    label: B("Import — guided flow", "Nhập dữ liệu — luồng có hướng dẫn"),
  },
  /* LEARN REFRESH step 3 — the second view of three setup stations: the
     guided setup's Pay rules step, Mapping's spreadsheet tab, and the
     Approval Matrix's route builder. Each borrows its owner's place. */
  blueprint_rules: {
    owner: "blueprint",
    label: B("New configuration — Pay rules", "Cấu hình mới — Quy tắc lương"),
  },
  mapping_sheet: {
    owner: "mapping",
    label: B("Mapping — Spreadsheet columns → Scheme", "Ánh xạ — Cột bảng tính → Chương trình lương"),
  },
  matrix_builder: {
    owner: "matrix",
    label: B("Approval Matrix — route builder", "Ma trận phê duyệt — dựng lộ trình"),
  },
  /* LEARN REFRESH step 4 — the hiring request wizard over its board, and
     the Generate a filing flow a Filings tile opens. */
  hiring_request: {
    owner: "hiring",
    label: B("Hiring — Raise a hiring request", "Tuyển dụng — Đề xuất tuyển dụng"),
  },
  filing_flow: {
    owner: "govreports",
    label: B("Filings — Generate a filing", "Tờ khai — Tạo hồ sơ"),
  },
};

/* Real selection keys, with what the product actually calls them. The keys are
   from pb_payruns/models/hr_payslip_run.py (PB_STATES, :51-56) and
   check_contract.py pins them — a lesson that teaches a renamed state is a
   lesson that teaches a lie. */
const STATUS_LABELS = {
  /* THE PAY RUN. Three stages and one outcome. The fixed approval tiers are
     GONE: while a run is waiting, WHO it waits for is its route, not its
     state (ROUTE above). */
  payrun: {
    draft: { l: B("Draft", "Nháp"), t: "" },
    approval_pending: { l: B("Waiting for approval", "Chờ phê duyệt"), t: "warn" },
    done: { l: B("Done", "Hoàn tất"), t: "ok" },
    /* A rejected run is an outcome, not a column: the board lists it under
       "Rejected pay runs". Reached by the board's Reject, or by "Turn it down"
       in the inbox — both cancel every payslip in it. */
    cancel: { l: B("Rejected", "Đã từ chối"), t: "danger" },
  },
  /* A PAYSLIP follows its run and never moves on its own
     (pb_payslip_review STATUS_FLOW: Draft → Waiting for approval → Done). */
  payslip: {
    draft: { l: B("Draft", "Nháp"), t: "" },
    verify: { l: B("Waiting for approval", "Chờ phê duyệt"), t: "warn" },
    done: { l: B("Done", "Hoàn tất"), t: "ok" },
    cancel: { l: B("Rejected", "Đã từ chối"), t: "danger" },
  },
  /* The practice company's route, for the `pipeline` visual on the approval
     lessons: the request travels the steps in order. */
  route: {
    s1: { l: ROUTE.steps[0].title, t: "" },
    s2: { l: ROUTE.steps[1].title, t: "" },
    s3: { l: ROUTE.steps[2].title, t: "" },
    applied: { l: B("Done — the run is finished", "Hoàn tất — đợt lương đã xong"), t: "ok" },
  },
  /* A formula configuration's stages (pb_hr_payroll_formula
     formula_config.py:529-535). */
  formula: {
    draft: { l: B("Draft", "Nháp"), t: "" },
    testing: { l: B("Testing", "Đang thử nghiệm"), t: "b" },
    validated: { l: B("Validated", "Đã xác thực"), t: "warn" },
    active: { l: B("Active", "Đang hoạt động"), t: "ok" },
    archived: { l: B("Archived", "Đã lưu trữ"), t: "" },
  },
  importbatch: {
    matched: { l: B("Matched", "Đã khớp"), t: "warn" },
    done: { l: B("Done", "Hoàn tất"), t: "ok" },
  },
  /* LEARN REFRESH step 4 — the pay review's stepper (pb_pay pay_review.xml),
     a role's four hiring steps (pb_hiring) and a leaver's four (pb_offboarding),
     for the `pipeline` visual. Labels are the screens' own. */
  review: {
    draft: { l: B("Being written", "Đang soạn"), t: "" },
    hr: { l: B("With HR", "Đang ở nhân sự"), t: "warn" },
    finance: { l: B("With finance", "Đang ở tài chính"), t: "warn" },
    ceo: { l: B("With the CEO", "Đang ở tổng giám đốc"), t: "warn" },
    approved: { l: B("Approved", "Đã duyệt"), t: "b" },
    applied: { l: B("Applied", "Đã áp dụng"), t: "ok" },
  },
  hiring: {
    request: { l: B("Request & approve", "Đề xuất & phê duyệt"), t: "" },
    publish: { l: B("Prepare & publish", "Chuẩn bị & đăng tin"), t: "b" },
    meet: { l: B("Meet your candidates", "Gặp ứng viên"), t: "warn" },
    welcome: { l: B("Welcome aboard", "Chào mừng gia nhập"), t: "ok" },
  },
  exit: {
    notice: { l: B("Working their notice", "Đang trong thời gian báo trước"), t: "" },
    signing: { l: B("Signing off", "Đang xác nhận bàn giao"), t: "warn" },
    ready: { l: B("Ready to settle", "Sẵn sàng quyết toán"), t: "b" },
    settled: { l: B("Settled", "Đã quyết toán"), t: "ok" },
  },
};

/* The lifecycles the `pipeline` visual draws. Same keys as STATUS_LABELS. */
const CHAINS = {
  payrun: {
    nodes: ["draft", "approval_pending", "done"],
    /* TWO WAYS OFF THE ROAD, and they are not the same. Sent back returns the
       run to Draft with the note on it (hr_payslip_run.py `_approval_return`);
       turned down in the inbox, or rejected from the board, cancels the run
       and every payslip in it (`_approval_reject` / `action_payslip_run_
       cancel`). Pinned by contract.json::payrun-state-chain and
       ::rejection-cancels-the-run. */
    branches: [
      B("Sent back — back to Draft, with a note saying what to change",
        "Trả lại — về Nháp, kèm ghi chú cần sửa gì"),
      B("Turned down or rejected — the whole run is cancelled, reason kept",
        "Bị từ chối — cả đợt lương bị huỷ, lý do được lưu lại"),
    ],
  },
  /* Start testing → Validate → Activate, the Studio's one main button
     (pb_formula_studio formula_studio.js:1604). */
  formula: {
    nodes: ["draft", "testing", "validated", "active"],
    branches: [
      B("Put it back to draft, or retire it — or propose retiring it when retiring needs a sign-off",
        "Đưa về bản nháp, hoặc ngừng sử dụng — hoặc đề xuất ngừng sử dụng khi việc đó cần được phê duyệt"),
    ],
  },
  route: {
    nodes: ["s1", "s2", "s3", "applied"],
    branches: [
      B("Any step can send it back, or turn it down", "Bước nào cũng có thể trả lại, hoặc từ chối"),
    ],
  },
  review: {
    nodes: ["draft", "hr", "finance", "ceo", "approved", "applied"],
    branches: [
      B("Send back — back to Being written, with the reason", "Trả lại — về Đang soạn, kèm lý do"),
      B("Take it back — within 24 hours of Apply", "Lấy lại — trong vòng 24 giờ sau khi Áp dụng"),
    ],
  },
  hiring: {
    nodes: ["request", "publish", "meet", "welcome"],
    branches: [
      B("Finance signs only when the role is over budget", "Tài chính chỉ duyệt khi vị trí vượt ngân sách"),
    ],
  },
  exit: {
    nodes: ["notice", "signing", "ready", "settled"],
    branches: [
      B("The settlement waits for IT, HR, Finance and Admin", "Quyết toán chờ đủ IT, Nhân sự, Tài chính và Quản trị viên"),
    ],
  },
};

export { B, EN, PRACTICE_META, CASE, EMP, RUN, FNB, ROUTE, LATER, PRACTICE, MENU, SUB_SCREENS, INPUT_ANCHORS, STATUS_LABELS, CHAINS, POLICY, TAX };
