/* GENERATED FILE. Do not edit.
            Source: docs/tutorial_poc/author/ · Regenerate: python3 docs/tutorial_poc/author/tools/gen_learn_data.py
            Hand edits are erased on the next run and fail the CI check.

            PHASE A1 PLACEHOLDER. Written by hand once, to the shape the
            generator will emit, so the module is complete before the authoring
            pipeline exists. Run A2 replaces it wholesale. */
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

   RULE FOR EDITORS: teaching content lives in `author/data.js`. Anything that
   is a fact about the product lives HERE, once, and is referenced from there.
   If you find yourself typing a number into a lesson step, it belongs in this
   file.

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
   1. THE WORKED EXAMPLE — one employee, one run, one month.
   ========================================================================== */
const EMP = {
  mai: {
    name: "Nguyễn Thị Mai", code: "NV0012",
    dept: B("Retail — Hà Nội", "Bán lẻ — Hà Nội"),
    base: 12000000, allowance: 780000, otJul: 1500000, otJun: 600000,
    bhxh: 960000, bhyt: 180000, bhtn: 120000,
    grossJul: 14280000, taxableJul: 2020000, pitJul: 101000, netJul: 12919000,
    grossJun: 13380000, pitJun: 56000, netJun: 12064000,
  },
  hung: {
    name: "Trần Văn Hùng", code: "NV0031",
    dept: B("Retail — Hà Nội", "Bán lẻ — Hà Nội"),
    base: 10500000, allowance: 650000, otJul: 4200000, otJun: 1100000,
    grossJul: 15350000, netJul: 13648000,
  },
  trang: { name: "Lê Thu Trang", code: "NV0007", base: 15200000, netJul: 15530000 },
  duc: { name: "Phạm Minh Đức", code: "NV0019", base: 9800000, netJul: 10241000 },
};

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
      why: B("Overtime is 282% of June", "Tăng ca bằng 282% tháng 6") },
    { emp: EMP.trang, ot: 310000, net: EMP.trang.netJul },
  ],

  /* Pay Runs — the board. `col` is a REAL state key from
     pb_payruns/models/hr_payslip_run.py, never a display label. */
  board: [
    { name: RUN.name, employees: 48, net: 612480000, col: "draft" },
    { name: B("F&B — July 2026", "F&B — Tháng 7/2026"), employees: 21, net: 214300000, col: "level1" },
    { name: B("Retail — June 2026", "Bán lẻ — Tháng 6/2026"), employees: 47, net: 596110000, col: "done" },
    { name: B("Retail — May 2026", "Bán lẻ — Tháng 5/2026"), employees: 47, net: 590870000, col: "done" },
  ],
  boardKpis: { total: 4, inPipeline: 2, myPending: 1, done: 2, net: 1186980000 },

  /* Payslips */
  slips: [
    { emp: EMP.mai, net: EMP.mai.netJul, state: "level1", sel: true },
    { emp: EMP.hung, net: EMP.hung.netJul, state: "level1", flag: true },
    { emp: EMP.trang, net: EMP.trang.netJul, state: "level1" },
    { emp: EMP.duc, net: EMP.duc.netJul, state: "done" },
  ],
  slipTotals: { count: 48, net: 612480000, gross: 691200000, done: 12, flagged: 1 },

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
  wizard: {
    score: 98.5, matched: 48, newEmployees: 0, errors: 2,
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
      kpis: [
        { label: B("Leavers this period", "Thôi việc kỳ này"), v: "2" },
        { label: B("Pending settlement", "Chờ quyết toán"), v: "1" },
        { label: B("Settled", "Đã chốt"), v: "8,420,000 ₫", money: true },
      ],
      facets: [B("All", "Tất cả"), B("Pending", "Đang chờ"), B("Settled", "Đã chốt")],
      rows: [
        { title: "Võ Quang Huy", code: "NV0044",
          sub: B("Last day 15/07/2026", "Ngày cuối 15/07/2026"), v: 8420000,
          badge: B("Pending", "Đang chờ") },
        { title: "Đỗ Thị Lan", code: "NV0021",
          sub: B("Last day 30/06/2026", "Ngày cuối 30/06/2026"), v: 14730000,
          badge: B("Settled", "Đã chốt") },
      ],
    },
    proration: {
      title: B("Proration Audit", "Soát xét ngày công"),
      subtitle: B("Why a part-month amount is the amount it is.",
                  "Vì sao một khoản lương tính theo ngày công lại ra con số đó."),
      kpis: [
        { label: B("Prorated payslips", "Phiếu tính theo ngày công"), v: "2" },
        { label: B("Standard working days", "Ngày công chuẩn"), v: "22" },
        { label: B("From the division config", "Theo cấu hình bộ phận"), v: RUN.config },
      ],
      facets: [B("All", "Tất cả"), B("Joiners", "Vào mới"), B("Leavers", "Thôi việc")],
      rows: [
        { title: "Võ Quang Huy", code: "NV0044",
          sub: B("11 / 22 days · factor 0.50", "11 / 22 ngày · hệ số 0,50"), v: 5250000,
          badge: B("Leaver", "Thôi việc") },
        { title: "Bùi Anh Tuấn", code: "NV0052",
          sub: B("9 / 22 days · factor 0.41", "9 / 22 ngày · hệ số 0,41"), v: 4090000,
          badge: B("Joiner", "Vào mới") },
      ],
    },
    retro: {
      title: B("Retro Adjustments", "Điều chỉnh hồi tố"),
      subtitle: B("Corrections for a closed month, paid in this one.",
                  "Hiệu chỉnh cho kỳ đã đóng, chi trong kỳ này."),
      kpis: [
        { label: B("Retro lines", "Dòng hồi tố"), v: "2" },
        { label: B("Total adjustment", "Tổng điều chỉnh"), v: "2,780,000 ₫", money: true },
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
      { id: "proration", icon: "calculator", label: B("Proration Audit", "Soát xét ngày công") },
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
  payrun: {
    draft: { l: B("Draft", "Nháp"), t: "" },
    level0: { l: B("Payroll Officer pending", "Chờ CV tính lương"), t: "b" },
    level1: { l: B("HR review", "HR soát xét"), t: "warn" },
    level2: { l: B("GM approval", "TGĐ phê duyệt"), t: "warn" },
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
