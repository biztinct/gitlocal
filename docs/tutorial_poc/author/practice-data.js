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
  /* These two default to what the PRODUCT calls those gates
     (pb_payruns/static/src/js/pipeline_field.js:8-12). A slot whose default
     disagrees with the screen it names is worse than no slot: the tenant who
     never sets it reads one word in the lesson and a different one on the
     board. contract.json::payrun-pipeline-labels pins the five. */
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
  flagged: 1,
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
  /* Overview */
  kpis: { headcount: 48, monthlyNet: 612480000, waiting: 1, configs: 2 },
  recentRuns: [
    { period: B("July 2026", "Tháng 7/2026"), employees: 48, net: 612480000, state: "level0" },
    { period: B("June 2026", "Tháng 6/2026"), employees: 47, net: 596110000, state: "done" },
    { period: B("May 2026", "Tháng 5/2026"), employees: 47, net: 590870000, state: "done" },
  ],

  /* Run Payroll — the wizard's own result table. Hùng carries the anomaly. */
  computed: [
    { emp: EMP.mai, ot: EMP.mai.otJul, net: EMP.mai.netJul },
    { emp: EMP.hung, ot: EMP.hung.otJul, net: EMP.hung.netJul, flag: true,
      why: B("Overtime is 382% of June", "Tăng ca bằng 382% tháng 6") },
    { emp: EMP.trang, ot: EMP.trang.otJul, net: EMP.trang.netJul },
  ],

  /* Pay Runs — the board. `col` is a REAL state key from
     pb_payruns/models/hr_payslip_run.py, never a display label. */
  board: [
    /* The July Retail run is at level0 — computed, submitted, and sitting with
       the Officer. It is at level0 on the Dashboard, on this board and in every
       lesson that mentions it: one run cannot be in two states, and a learner
       who sees it in two learns that the board is decorative. */
    { name: RUN.name, employees: 48, net: 612480000, col: "level0" },
    /* F&B is still in DRAFT, and that is the same fact m1's division decision
       turns on: its July attendance has not been committed, so nobody has
       submitted it. */
    { name: B("F&B — July 2026", "F&B — Tháng 7/2026"), employees: 21, net: 214300000, col: "draft" },
    { name: B("Retail — June 2026", "Bán lẻ — Tháng 6/2026"), employees: 47, net: 596110000, col: "done" },
    { name: B("Retail — May 2026", "Bán lẻ — Tháng 5/2026"), employees: 47, net: 590870000, col: "done" },
  ],
  /* Every count here is DERIVED from `board` above. Typing them by hand is how
     a KPI band and the columns under it end up disagreeing — which is the exact
     misreading the "In pipeline" column entry warns about. */
  get boardKpis() {
    const b = this.board;
    const pipeline = b.filter((r) => r.col !== "draft" && r.col !== "done");
    const done = b.filter((r) => r.col === "done");
    return {
      total: b.length,
      inPipeline: pipeline.length,
      myPending: pipeline.length,
      done: done.length,
      net: done.reduce((t, r) => t + r.net, 0),
    };
  },

  /* Payslips */
  /* The run is at level0, so its payslips are still DRAFT. level0 is a gate on
     the RUN and a payslip's own chain does not have it (STATUS_LABELS.payslip),
     so a slip cannot have moved further than the batch it belongs to. */
  slips: [
    { emp: EMP.mai, net: EMP.mai.netJul, state: "draft", sel: true },
    { emp: EMP.hung, net: EMP.hung.netJul, state: "draft", flag: true },
    { emp: EMP.trang, net: EMP.trang.netJul, state: "draft" },
    { emp: EMP.duc, net: EMP.duc.netJul, state: "draft" },
  ],
  slipTotals: { count: 48, net: 612480000, gross: 691200000, done: 0, flagged: 1 },

  /* Import + its wizard */
  importKpis: { batches: 6, done: 4, inProgress: 1, errors: 1, connectors: 2 },
  importPipe: [
    { key: "map", label: B("Map", "Ánh xạ"), count: 1 },
    { key: "validate", label: B("Validate", "Kiểm tra"), count: 1 },
    { key: "commit", label: B("Commit", "Ghi nhận"), count: 4 },
  ],
  importBatches: [
    { name: B("July attendance & OT", "Chấm công & tăng ca tháng 7"), rows: 48, state: "validate" },
    { name: B("June attendance & OT", "Chấm công & tăng ca tháng 6"), rows: 47, state: "done" },
  ],
  /* 46 of 48 rows read without ambiguity = 95.8%. The score is DERIVED, because
     a hand-typed percentage that does not match the counts under it is the one
     thing this screen must never do — the whole lesson is that the count
     matters more than the percentage. */
  wizard: {
    rows: 48, matched: 46, newEmployees: 0, errors: 2,
    get score() { return Math.round(this.matched / this.rows * 1000) / 10; },
    errorRows: [
      { name: "Bùi Anh Tuấn", code: "NV0052",
        why: B("No employee matches this code", "Không có nhân viên nào khớp mã này") },
      { name: "Đỗ Thị Lan", code: "NV0021",
        why: B("Duplicate row in the file", "Dòng bị lặp trong tệp") },
    ],
    outcome: { employees: 0, payslips: 48 },
  },

  /* The three ledgers share one shape, because the product shares one
     template. Keyed by screen so one renderer serves all three. */
  ledgers: {
    fullfinal: {
      title: B("Full & Final", "Quyết toán thôi việc"),
      subtitle: B("Departing employees and what they are still owed.",
                  "Nhân viên thôi việc và những khoản còn phải trả."),
      /* Both leavers are in THIS period — Lan on the 8th, Huy on the 15th — so
         "Leavers this period: 2" is a count of the two rows below it and not a
         number that has to be taken on trust. Settled is Lan's amount, because
         Lan is the one that has been settled; Huy's is still pending. */
      kpis: [
        { label: B("Leavers this period", "Thôi việc kỳ này"), v: "2" },
        { label: B("Pending settlement", "Chờ quyết toán"), v: 8420000, money: true },
        { label: B("Settled", "Đã chốt"), v: 14730000, money: true },
      ],
      facets: [B("All", "Tất cả"), B("Pending", "Đang chờ"), B("Settled", "Đã chốt")],
      rows: [
        { title: "Võ Quang Huy", code: "NV0044",
          sub: B("Last day 15/07/2026", "Ngày cuối 15/07/2026"), v: 8420000,
          badge: B("Pending", "Đang chờ") },
        { title: "Đỗ Thị Lan", code: "NV0021",
          sub: B("Last day 08/07/2026", "Ngày cuối 08/07/2026"), v: 14730000,
          badge: B("Settled", "Đã chốt") },
      ],
    },
    proration: {
      title: B("Proration Audit", "Soát xét ngày công (pro-rata)"),
      subtitle: B("Why a part-month amount is the amount it is.",
                  "Vì sao một khoản lương tính theo ngày công lại ra con số đó."),
      kpis: [
        { label: B("Prorated payslips", "Phiếu tính theo ngày công"), v: "2" },
        { label: B("Standard working days", "Ngày công chuẩn"), v: "22" },
        { label: B("From the division config", "Theo cấu hình bộ phận"), v: RUN.config },
      ],
      facets: [B("All", "Tất cả"), B("Joiners", "Vào mới"), B("Leavers", "Thôi việc")],
      /* The factor is shown to FOUR decimal places and the money is the base
         times that factor, rounded to the đồng — 10,000,000 × 9/22 is
         4,090,909.09, and printing 4,090,000 beside "0.41" invited a learner to
         multiply it out and find the tutorial wrong. Huy's 11/22 is exactly
         0.5000, which is why one row looks tidy and the other does not: that is
         what real proration looks like. */
      rows: [
        { title: "Võ Quang Huy", code: "NV0044",
          sub: B("11 / 22 days · factor 0.5000", "11 / 22 ngày · hệ số 0,5000"),
          v: Math.round(10500000 * 11 / 22),
          badge: B("Leaver", "Thôi việc") },
        { title: "Bùi Anh Tuấn", code: "NV0052",
          sub: B("9 / 22 days · factor 0.4091", "9 / 22 ngày · hệ số 0,4091"),
          v: Math.round(10000000 * 9 / 22),
          badge: B("Joiner", "Vào mới") },
      ],
    },
    retro: {
      title: B("Retro Adjustments", "Điều chỉnh hồi tố"),
      subtitle: B("Corrections for a closed month, paid in this one.",
                  "Hiệu chỉnh cho kỳ đã đóng, chi trong kỳ này."),
      kpis: [
        { label: B("Retro lines", "Dòng hồi tố"), v: "2" },
        { label: B("Total adjustment", "Tổng điều chỉnh"), v: 2400000 + 380000, money: true },
        { label: B("Oldest source period", "Kỳ gốc xa nhất"), v: "04/2026" },
      ],
      facets: [B("All", "Tất cả"), B("Pay increase", "Tăng lương"), B("Missed allowance", "Sót phụ cấp")],
      rows: [
        { title: EMP.trang.name, code: EMP.trang.code,
          sub: B("Backdated raise · source 04–06/2026", "Tăng lương lùi ngày · kỳ gốc 04–06/2026"),
          v: 2400000, badge: B("Pay increase", "Tăng lương") },
        { title: EMP.duc.name, code: EMP.duc.code,
          sub: B("Missed night-shift allowance · source 06/2026", "Sót phụ cấp ca đêm · kỳ gốc 06/2026"),
          v: 380000, badge: B("Missed allowance", "Sót phụ cấp") },
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
  structures: {
    categories: 8,
    countries: 1,
    rows: [
      { name: "VN Standard 2023", code: "VN_STD_2023", rules: 14, employees: 7,
        updated: "12/2023", badge: B("Historical", "Lịch sử") },
      { name: "VN Probation 2023", code: "VN_PROB_2023", rules: 9, employees: 5,
        updated: "12/2023", badge: B("Historical", "Lịch sử") },
      { name: "VN Expatriate 2022", code: "VN_EXPAT_2022", rules: 8, employees: 0,
        updated: "03/2022", badge: B("Archived", "Đã lưu trữ") },
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
      type: B("HR system", "Hệ thống nhân sự"),
      last: B("Synced 06:00 today", "Đồng bộ 06:00 hôm nay"),
      mappings: 42, staged: 0, synced: 4820 },
    { name: "Bank SFTP", icon: "send", status: "ok",
      type: B("Payment file", "Tệp chi lương"),
      last: B("Synced yesterday", "Đồng bộ hôm qua"),
      mappings: 9, staged: 0, synced: 312 },
    { name: B("Time clock — Hà Nội", "Máy chấm công — Hà Nội"), icon: "clock", status: "err",
      type: B("Attendance", "Chấm công"),
      last: B("Last synced 9 days ago", "Đồng bộ lần cuối 9 ngày trước"),
      mappings: 6, staged: 214, synced: 0 },
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
    };
  },

  /* --------------------------------------------------- Overview (Phase C1)
     NOT A SECOND SET OF NUMBERS. Everything below reads `board`, `recentRuns`,
     `statutory`, `ledgers` and the four employees above, because the Overview,
     People and Insights screens are the SAME payroll seen from further back. A
     Dashboard that disagreed with the Pay Runs board underneath it would teach
     a learner that the top of the product is decorative, which is the one thing
     a command centre cannot be.

     THE APPROVAL LANES ARE DERIVED FROM `board`, and that is the whole design.
     The July Retail run is at level0 on the Dashboard, on the Pay Runs board
     and here; the two lanes to its right are EMPTY, and drawing them empty is
     honest — the product renders "No runs here." for exactly this state, and a
     quiet Tuesday is most of what a payroll month looks like. */
  get approvals() {
    const lane = (col) => this.board.filter((r) => r.col === col);
    const lanes = [
      { key: "level0", runs: lane("level0") },
      { key: "level1", runs: lane("level1") },
      { key: "level2", runs: lane("level2") },
    ];
    return {
      lanes,
      /* Decided, not waiting: the two runs that have already passed every gate.
         Both are `done` on the board above, and their nets are the board's. */
      recent: this.board.filter((r) => r.col === "done"),
      /* `net at stake` is money that has NOT been paid and can still be
         stopped. Summed from the lanes, so it cannot disagree with them. */
      get kpis() {
        const at = (k) => (lanes.find((l) => l.key === k) || { runs: [] }).runs;
        return {
          officer: at("level0").length,
          hr: at("level1").length,
          finance: at("level2").length,
          net: lanes.reduce(
            (t, l) => t + l.runs.reduce((s, r) => s + r.net, 0), 0),
        };
      },
    };
  },

  /* ------------------------------------------------------ People (Phase C1)
     A wage here is the REGISTERED CONTRACT BASE, which is also the insurance
     base — one number, one meaning, wherever it is printed. The company-wide
     wage bill is `statutory.insuranceBase`: the sum of the registered bases is
     exactly what both that band and this one are describing. */
  people: {
    draftContracts: 1,
    expiring: 1,
    newHires: 1,
    /* Đức has no bank account on file. Everything else about him is ready and
       his pay still will not land, which is why payroll-readiness is its own
       column rather than a footnote on the wage. */
    notReady: 1,
    get kpis() {
      const head = RUN.employees;
      return {
        headcount: head,
        running: head - this.draftContracts,
        expiring: this.expiring,
        newHires: this.newHires,
        wageBill: PRACTICE.statutory.insuranceBase,
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
  },

  /* Contracts. A person is not a contract: the same four people, read as the
     agreements payroll is actually paid from. */
  contracts: {
    get kpis() {
      const p = PRACTICE.people;
      const head = RUN.employees;
      return {
        running: head - p.draftContracts,
        expiring: p.expiring,
        draft: p.draftContracts,
        expired: 0,
        wageBill: PRACTICE.statutory.insuranceBase,
        avgWage: Math.round(PRACTICE.statutory.insuranceBase / head),
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
        badge: B("Draft", "Nháp") },
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
    return {
      months,
      headline: RUN.totalNet,
      /* The month-on-month move, computed rather than restated. It is the same
         2.7% m2's anomaly card discusses, and it comes out of the same two
         numbers. */
      get deltaPct() {
        const a = months[months.length - 2].net;
        const b = months[months.length - 1].net;
        return Math.round((b - a) / a * 1000) / 10;
      },
      departments: [
        { label: RUN.division, v: RUN.totalNet, heads: RUN.employees },
        { label: B("F&B", "F&B"), v: 214300000, heads: 21 },
      ],
      statutory: [
        { label: B("Employee leg", "Phần người lao động"), v: s.employeeLeg },
        { label: B("Employer leg", "Phần doanh nghiệp"), v: s.employerLeg },
      ],
      pulse: [
        { label: B("Attendance exceptions", "Ngoại lệ chấm công"), v: w.exceptionTotal },
        { label: B("Payslips flagged", "Phiếu bị gắn cờ"), v: RUN.flagged },
        { label: B("Joiners this month", "Vào mới tháng này"), v: w.kpis.joiners },
        { label: B("Leavers this month", "Thôi việc tháng này"), v: w.kpis.leavers },
      ],
    };
  },

  /* Explorer. ONE question, asked properly: net pay by division for July, with
     the filters that scope it shown as removable tags — because a figure read
     without its filters is a figure read out of scope. */
  get explorer() {
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
    /* Bùi Anh Tuấn, the joiner on the proration ledger. Leavers are counted
       from the Full & Final rows rather than declared twice. */
    const joiners = 1;
    const leavers = this.ledgers.fullfinal.rows.length;
    const exceptions = [
      { label: B("Missing clock-out", "Thiếu chấm công ra"), v: 4 },
      { label: B("Unapproved overtime", "Tăng ca chưa duyệt"), v: 3 },
    ];
    return {
      months,
      exceptions,
      exceptionTotal: exceptions.reduce((t, e) => t + e.v, 0),
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
    groups: [
      {
        label: B("Social Insurance (BHXH)", "Bảo hiểm xã hội (BHXH)"), icon: "shield-check",
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
};

/* =============================================================================
   3. THE MENU — mirrors pb_sidebar/data/pb_sidebar_data.xml.
   -----------------------------------------------------------------------------
   `scope: true` marks the section Phase A teaches. Everything else is drawn so
   the replica looks like the product, and greyed while out of scope: a learner
   who is shown a menu that is not the menu learns the wrong menu.
   ========================================================================== */
const MENU = [
  {
    key: "overview", label: B("Overview", "Tổng quan"), scope: true, items: [
      { id: "dashboard", icon: "grid", label: B("Dashboard", "Bảng điều khiển") },
      { id: "approvals", icon: "clipboard-check", label: B("Approvals", "Phê duyệt") },
    ],
  },
  {
    key: "payrun", label: B("Pay Run", "Chạy lương"), scope: true, items: [
      { id: "runpayroll", icon: "zap", label: B("Run Payroll", "Chạy bảng lương") },
      { id: "payruns", icon: "calendar", label: B("Pay Runs", "Đợt tính lương") },
      { id: "payslips", icon: "receipt", label: B("Payslips", "Phiếu lương") },
      { id: "import", icon: "database", label: B("Import Data", "Nhập dữ liệu") },
      { id: "fullfinal", icon: "file-text", label: B("Full & Final", "Quyết toán thôi việc") },
      { id: "proration", icon: "calculator", label: B("Proration Audit", "Soát xét ngày công (pro-rata)") },
      { id: "retro", icon: "trending-up", label: B("Retro Adjustments", "Điều chỉnh hồi tố") },
    ],
  },
  {
    key: "setup", label: B("Setup", "Thiết lập"), scope: true, items: [
      { id: "formula", icon: "calculator", label: B("Formula Engine", "Công thức lương") },
      { id: "structures", icon: "layers", label: B("Salary Structures", "Cấu trúc lương") },
      { id: "statutory", icon: "shield-check", label: B("Statutory (Insurance & Tax)", "Bảo hiểm & Thuế") },
      { id: "integrations", icon: "database", label: B("Integrations", "Tích hợp") },
    ],
  },
  /* Phase C1. The order below is the order pb_sidebar draws these sections
     (People 30, Insights 40, Compliance 45) — Workforce and Planning sit
     between them in the product and are deliberately NOT taught yet, so they
     are not drawn here either: a replica menu that shows a section with no
     station behind it is a promise the map does not keep. */
  {
    key: "people", label: B("People", "Nhân sự"), scope: true, items: [
      { id: "employees", icon: "users", label: B("Employees", "Nhân viên") },
      { id: "contracts", icon: "file-text", label: B("Contracts", "Hợp đồng") },
    ],
  },
  {
    key: "insights", label: B("Insights", "Phân tích"), scope: true, items: [
      { id: "insights", icon: "trending-up", label: B("Insights", "Phân tích") },
      { id: "explorer", icon: "compass", label: B("Explorer", "Explorer") },
      { id: "workforcean", icon: "bar-chart", label: B("Workforce Analytics", "Phân tích nhân sự") },
    ],
  },
  {
    key: "compliance", label: B("Compliance", "Tuân thủ"), scope: true, items: [
      { id: "govreports", icon: "file-text", label: B("Government Reports", "Báo cáo cơ quan nhà nước") },
    ],
  },
];

/* The import wizard is a FLOW, not a destination — it has no sidebar leaf, so
   it cannot appear in MENU. Named here so the shell can still title it. */
const SUB_SCREENS = {
  importwizard: {
    owner: "import",
    label: B("Import — guided flow", "Nhập dữ liệu — luồng có hướng dẫn"),
  },
};

/* Real selection keys, with what the product actually calls them. The keys are
   from pb_payruns/models/hr_payslip_run.py and check_contract.py pins them —
   a lesson that teaches a renamed state is a lesson that teaches a lie. */
const STATUS_LABELS = {
  /* THE PAY RUN's chain — five stages, including level0. */
  payrun: {
    draft: { l: B("Draft", "Nháp"), t: "" },
    level0: { l: B("Payroll Officer pending", "Chờ Chuyên viên tính lương"), t: "b" },
    level1: { l: B("HR review", "HR soát xét"), t: "warn" },
    level2: { l: B("Finance approval", "Tài chính phê duyệt"), t: "warn" },
    done: { l: B("Done", "Hoàn tất"), t: "ok" },
    /* Where a rejection actually lands. The product's own label for this
       selection value is "Rejected", not "Cancelled" — which is why the board
       reads as a rejection while the record reads as a cancellation, and why
       the content has to say both. */
    cancel: { l: B("Rejected", "Đã từ chối"), t: "danger" },
  },
  /* A PAYSLIP's chain is FOUR stages, not five: it has no level0. Drawing the
     run's five on a payslip stepper would teach a gate that does not exist
     there, and a learner would go looking for an Officer tier on a slip. The
     two are separate on purpose, and check_contract.py pins both. */
  payslip: {
    draft: { l: B("Draft", "Nháp"), t: "" },
    level1: { l: B("HR Manager pending", "Chờ Trưởng phòng Nhân sự"), t: "warn" },
    level2: { l: B("GM pending", "Chờ Tổng Giám đốc"), t: "warn" },
    done: { l: B("Done", "Hoàn tất"), t: "ok" },
    /* A rejected RUN cancels every slip in it, so a payslip has this state
       too — reached by the batch, never by itself. */
    cancel: { l: B("Rejected", "Đã từ chối"), t: "danger" },
  },
  importbatch: {
    map: { l: B("Mapping", "Đang ánh xạ"), t: "" },
    validate: { l: B("Validating", "Đang kiểm tra"), t: "warn" },
    done: { l: B("Committed", "Đã ghi nhận"), t: "ok" },
  },
};

/* The pay run's real lifecycle, for the `pipeline` visual. Same keys as
   STATUS_LABELS.payrun, in the order the product moves through them. */
const CHAINS = {
  payrun: {
    nodes: ["draft", "level0", "level1", "level2", "done"],
    /* THE BRANCH IS A DEAD END, not a loop back to the start, and the caption
       said the opposite for the whole of Phases A and B. `action_payslip_run_
       cancel` cascades `action_payslip_cancel` over every slip and writes the
       RUN to 'cancel' — whose own selection label is "Rejected"
       (om_hr_payroll/models/hr_payslip.py:975). Getting a workable draft back
       is `draft_payslip_run`, a different method gated to the Finance/GM tier
       (pb_payruns/models/hr_payslip_run.py:283-298). Pinned by
       contract.json::rejection-cancels-the-run. */
    branch: B("Rejected — the whole run is cancelled, with a written reason",
              "Đã từ chối — cả đợt lương bị huỷ, kèm lý do bằng văn bản"),
  },
};
