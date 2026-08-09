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

/* Bump the minor when you add records; bump the major when a shape changes,
   because `check_contract.py` pins to it. */
const PRACTICE_META = {
  schemaVersion: "1.1.0",
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
     · insurance = 10.5% of the REGISTERED BASE (BHXH 8 + BHYT 1.5 + BHTN 1).
       Charged on the base, never on gross — that single fact is L3's spine.
     · taxable   = gross − insurance − 11,000,000 personal relief
                          − 4,400,000 per dependant
     · PIT       = 5% of taxable, floored at zero. Everyone in this fixture
       lands in the first bracket, which is realistic for a retail division and
       keeps the arithmetic checkable by a reader.

   MAI IS THE TEST VECTOR. Her canonical numbers were agreed before this
   function existed and it reproduces every one of them exactly — 14,280,000
   gross, 1,260,000 insurance, 2,020,000 taxable, 101,000 PIT, 12,919,000 net
   for July; 12,064,000 net for June. If a change here moves any of those, the
   change is wrong.
   -------------------------------------------------------------------------- */
const RELIEF_SELF = 11000000;
const RELIEF_DEPENDANT = 4400000;
const INSURANCE_RATE = 0.105;   // 8% BHXH + 1.5% BHYT + 1% BHTN
const PIT_FIRST_BRACKET = 0.05;

function payslip({ base, allowance = 0, ot = 0, dependants = 0 }) {
  const gross = base + allowance + ot;
  const bhxh = Math.round(base * 0.08);
  const bhyt = Math.round(base * 0.015);
  const bhtn = Math.round(base * 0.01);
  const insurance = Math.round(base * INSURANCE_RATE);
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
    key: "overview", label: B("Overview", "Tổng quan"), items: [
      { id: "dashboard", icon: "grid", label: B("Dashboard", "Bảng điều khiển") },
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
    branch: B("Rejected — back to draft, with a written reason",
              "Bị từ chối — trả về Nháp, kèm lý do bằng văn bản"),
  },
};

export { B, PRACTICE_META, CASE, EMP, RUN, PRACTICE, MENU, SUB_SCREENS, STATUS_LABELS, CHAINS };
