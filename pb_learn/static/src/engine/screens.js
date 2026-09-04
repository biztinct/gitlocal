/** @odoo-module **/
/* =============================================================================
   The practice shell — a replica of the Pay Run screens, drawn from the fixture.

   It is a REPLICA, not the product: there is no server behind it, so it is
   structurally incapable of computing a run, approving a payslip or committing
   an import. The banner is the last line of defence rather than the only one.

   Every control the content points at carries data-coach="…" — the SAME anchor
   keys the real templates carry, so a lesson step, a mission target and a Coach
   answer address a control by one name whichever surface it is on. That is the
   whole reason the replica is worth building: the vocabulary a learner acquires
   here is the vocabulary the Coach uses on the live screen tomorrow.

   Anchors that exist only here — the arithmetic breakdown, the lifecycle
   stepper, the replica's own navigation — are named `rep-*` and registered as
   kind "practice", so the gap is visible: the Coach must never claim to point
   at one of these on a live screen.

   Screen prose is inline B("en","vi") on purpose. These strings must mirror
   what the PRODUCT says in Vietnamese; putting them in the module's .po would
   hand a translator wording they do not own, and the two would diverge at the
   first product rename.
   ========================================================================== */
import { B, CASE, INPUT_ANCHORS, MENU, POLICY, PRACTICE, RUN, STATUS_LABELS,
         SUB_SCREENS, TAX } from "./fixture";
import { esc, ic, initial, tx, T, N, M, P, SP} from "./runtime";
import { calcHTML, pipeHTML } from "./visuals";

/* Which screen the shell is showing. The Coach grounds on this. */
export let CURRENT_SCREEN = null;

/* Separators live here rather than inside a template interpolation. A quoted
   string CONCATENATED inside `${…}` makes rjsmin lose track of the enclosing
   literal and strip whitespace from the rest of it — the same hazard the
   `approved` line in payslips() is written out of line to avoid. */
const DOT = " · ";
const DASH = " – ";
const ARROW = " → ";
const SLASH = " / ";

/* A formula component's kind decides its chip colour and its label. The Studio
   colours them the same way, which is what makes a formula readable at a
   glance: red is money leaving, green is money arriving, amber is a subtotal. */
const CHIP_TONE = { input: "b", earning: "ok", deduction: "danger", total: "a",
                   param: "", op: "" };
const KIND_LABEL = {
    input: B("Input", "Đầu vào"),
    earning: B("Earning", "Thu nhập"),
    deduction: B("Deduction", "Khấu trừ"),
    total: B("Total", "Tổng"),
    // The parameter constants. Drawn last and drawn plainly, because they are
    // not lines on a payslip — they are the NUMBERS the lines are priced from,
    // and they are the answer to "where does a rate actually live".
    param: B("Parameter", "Tham số"),
};

/* An attribute, held as a constant rather than written inline. A quoted string
   inside a `${…}` makes rjsmin lose track of the enclosing template literal and
   strip whitespace from the rest of it — the hazard runtime.js documents and
   test_assets::test_01c enforces — so a conditional attribute is built here and
   interpolated as a bare identifier. */
const ATTR_IMPMATCH = 'data-coach="rep-impmatch"';

/* ------------------------------------------------------------------- helpers */
/** A real <input>, drawn ONLY at an anchor the fixture declares.
 *
 *  The guard is not politeness: `INPUT_ANCHORS` is the table the generator
 *  validates input steps against and the table `input_match.js` reads the
 *  comparison rule from, so a field drawn outside it would be a field the
 *  engine has no rule for and the author cannot point a step at. Drawing
 *  nothing is the honest failure — a step that cannot find its field degrades
 *  to a centred card, which says something, where a field with no entry would
 *  silently never match.
 */
function inputRow(anchor, label, placeholder) {
    if (!INPUT_ANCHORS[anchor]) {
        return "";
    }
    // A <label> WRAPPING THE FIELD, not a <div>. One of the two call sites is
    // inside a `<span>` — the import wizard's error row — and a div there is
    // invalid nesting that the parser fixes by closing the span early, which
    // moves the field out of the row it belongs to. Label and span are both
    // phrasing content, so this form is valid in either place, and wrapping
    // the input gives the field its accessible name without a second
    // attribute that can drift from the visible text.
    return `<label class="lrn-inputrow">
        <span class="lrn-flabel">${esc(tx(label))}</span>
        <input class="lrn-in" type="text" autocomplete="off" value=""
               data-coach="${esc(anchor)}" placeholder="${esc(tx(placeholder))}"/>
    </label>`;
}

export function statusChip(kind, key) {
    const s = (STATUS_LABELS[kind] || {})[key];
    return s
        ? `<span class="lrn-chip ${s.t}">${esc(tx(s.l))}</span>`
        : `<span class="lrn-chip">${esc(key)}</span>`;
}

export function screenTitle(id) {
    for (const sec of MENU) {
        for (const it of sec.items) {
            if (it.id === id) {
                return tx(it.label);
            }
        }
    }
    const sub = SUB_SCREENS[id];
    return sub ? tx(sub.label) : "";
}

/** Which sidebar section owns this screen — the section that is IN SCOPE while
 *  it is on display, and every other one greyed. A sub-screen (the import
 *  wizard) borrows its owner leaf's section, so the wizard does not read as
 *  having escaped the menu. */
function ownerSection(screen) {
    const sub = SUB_SCREENS[screen];
    const id = sub ? sub.owner : screen;
    return MENU.find((sec) => sec.items.some((it) => it.id === id)) || MENU[0];
}

/** The leaf that is highlighted while `screen` is showing. */
function ownerLeaf(screen) {
    const sub = SUB_SCREENS[screen];
    return sub ? sub.owner : screen;
}

/* --------------------------------------------------------------- row renderers
   These read PRACTICE and CASE, never their own literals — which is what makes
   the fixture the single place to edit when the product changes. */
function kpiTile(icon, tone, value, label) {
    return `<div class="lrn-kpi ${tone}">
        <div class="lrn-kt">${ic(icon)}<span>${esc(tx(label))}</span></div>
        <div class="lrn-kv">${esc(value)}</div>
    </div>`;
}

function runCard(row) {
    return `<div class="lrn-kcard" data-coach="pk-card">
        <b>${esc(tx(row.name))}</b>
        <div class="lrn-kmeta">
            <span>${N(row.employees)}${SP}${esc(T("employees"))}</span>
            <span class="lrn-money">${esc(M(row.net))}</span>
        </div>
        <div class="lrn-kacts" data-coach="pk-card-actions">
            ${row.col === "done"
                ? `<button class="lrn-btn sm ghost">${esc(T("bankFile"))}</button>
                   <button class="lrn-btn sm ghost">${esc(T("journals"))}</button>`
                : `<button class="lrn-btn sm pri">${esc(T("submitReview"))}</button>
                   <button class="lrn-btn sm ghost danger">${esc(T("reject"))}</button>`}
        </div>
    </div>`;
}

function ledgerHTML(key) {
    const d = PRACTICE.ledgers[key];
    if (!d) {
        return "";
    }
    // A money value arrives as a NUMBER and is formatted here, in the one place
    // that formats money — so it follows the reader's language like every other
    // figure on the screen. Pre-formatted strings in the fixture printed
    // "8,420,000 ₫" to a Vietnamese reader who groups thousands with a dot.
    const kpis = d.kpis.map((k) => `
        <div class="lrn-kpi">
            <div class="lrn-kt">${ic("calculator")}<span>${esc(tx(k.label))}</span></div>
            <div class="lrn-kv ${k.money ? "lrn-money" : ""}">${
                esc(typeof k.v === "number" ? M(k.v) : k.v)}</div>
        </div>`).join("");
    const facets = d.facets.map((f, i) =>
        `<button class="lrn-chip ${i === 0 ? "b" : ""}">${esc(tx(f))}</button>`).join("");
    const rows = d.rows.map((r) => `
        <div class="lrn-row">
            <span class="lrn-avatar">${esc(initial(r.title))}</span>
            <span><span class="lrn-nm">${esc(r.title)}
                    <span class="lrn-faint">${esc(r.code)}</span></span><br>
                <span class="lrn-sub2">${esc(tx(r.sub))}</span></span>
            <span class="lrn-rr"><span class="lrn-chip">${esc(tx(r.badge))}</span>
                <b class="lrn-money">${esc(M(r.v))}</b></span>
        </div>`).join("");

    return `
        <div class="lrn-grid g3" data-coach="lg-kpis">${kpis}</div>
        <div class="lrn-tabs" data-coach="lg-facets">${facets}</div>
        <div class="lrn-panel">
            <h3>${ic("list-checks")}${esc(tx(d.subtitle))}</h3>
            <div class="lrn-rows" data-coach="lg-rows">${rows}</div>
            <div class="lrn-foot2">
                <button class="lrn-link" data-coach="lg-openfull">${esc(T("openFullList"))}</button>
            </div>
        </div>`;
}

/* -------------------------------------------- the practice employee form
   DRAWN INLINE, UNDER THE ROSTER, AND SAID SO ON THE CARD.

   The product opens a form VIEW here — press New and the roster is replaced.
   The replica cannot: a screen is one zero-argument function with no state
   behind it, so a form that appears and disappears would be a second screen
   with no sidebar leaf, no action tag and nothing for the Coach to resolve it
   by. Drawing it inline is the honest version of the same lesson, and the
   panel's own heading says which of the two you are looking at — the same
   ruling as `rep-pipeline`, where the product draws columns and the replica
   draws a stepper because the lesson is about the journey between them.

   Nothing here saves anything. The Save button is a picture of a button; what
   the learner is rehearsing is the ORDER — name, division, save — and the fact
   that a person on the roster is still not a person who can be paid. */
function newEmployeeHTML() {
    return `
        <div class="lrn-panel">
            <h3>${ic("user-plus")}${esc(tx(B(
                "New employee — practice form. Save writes nothing.",
                "Nhân viên mới — biểu mẫu thực hành. Nút Lưu không ghi gì.")))}</h3>
            <p class="lrn-note">${esc(tx(B(
                "In Payobook this opens as its own form. Here it sits under the roster, so you can read both at once.",
                "Trong Payobook, phần này mở ra thành một biểu mẫu riêng. Ở đây nó nằm ngay dưới danh sách để bạn đọc được cả hai cùng lúc.")))}</p>
            ${inputRow("rep-newemp-name",
                       B("Full name", "Họ và tên"),
                       B("Type the person's full name", "Nhập họ và tên của người đó"))}
            <label class="lrn-flabel">${esc(tx(B("Division", "Bộ phận")))}</label>
            <select class="lrn-in" data-coach="rep-newemp-div">
                <option>${esc(tx(RUN.division))}</option>
                <option>F&amp;B</option>
                <option>${esc(tx(B("IT Services", "Dịch vụ CNTT")))}</option>
            </select>
            <div class="lrn-strip">
                <button class="lrn-btn pri" data-coach="rep-newemp-save">${ic("check")}${
                    esc(tx(B("Save", "Lưu")))}</button>
            </div>
            <!-- WHAT PAYOBOOK DOES, said as what Payobook does. The first
                 version of this sentence promised that a saved person "joins
                 the roster above", which is not true of this panel: nothing is
                 saved and the roster never grows. A replica may show less than
                 the product; it may not promise more. -->
            <p class="lrn-note">${esc(tx(B(
                "In Payobook a saved person joins the roster above, and is still not payroll-ready: that needs a running contract and bank details.",
                "Trong Payobook, người đã lưu sẽ xuất hiện trong danh sách ở trên, và vẫn chưa sẵn sàng tính lương: còn cần hợp đồng đang hiệu lực và thông tin ngân hàng.")))}</p>
        </div>`;
}

/* -------------------------------------------------------------------- screens */
export const SCREENS = {
    /* --------------------------------------------------------- Dashboard
       The anchors here are the REAL dashboard's — dash-hero, dash-runpayroll,
       dash-kpis, dash-formula. They have been in pb_dashboard.xml since before
       this module existed (the retired hero tour pointed at three of them); Phase
       C1 promoted them out of the registry's `foreign` block into `product`,
       because LW names them and an anchor a lesson points at has to be one a
       test can check. pb_learn adds NOTHING to that template.

       `rep-dash-runs` stays practice-only and honest: the product's card here
       is one "Latest pay run" summary, and the replica draws three months
       because a lesson about the monthly loop needs to show a loop. */
    dashboard() {
        const k = PRACTICE.kpis;
        const rows = PRACTICE.recentRuns.map((r) => `
            <div class="lrn-row">
                <span><span class="lrn-nm">${esc(tx(r.period))}</span><br>
                    <span class="lrn-sub2">${esc(tx(RUN.division))}${SP}· ${N(r.employees)}${SP}${esc(T("employees"))}</span></span>
                <span class="lrn-rr">${statusChip("payrun", r.state)}
                    <b class="lrn-money">${esc(M(r.net))}</b></span>
            </div>`).join("");
        const heroSub = tx(RUN.name) + DOT + N(RUN.employees) + SP
            + tx(B("payslips", "phiếu lương")) + DOT + N(PRACTICE.kpis.waiting) + SP
            + tx(B("awaiting approval", "chờ phê duyệt"));
        const f = PRACTICE.config;
        const formulaMeta = N(PRACTICE.kpis.configs) + SP + tx(B("configurations", "cấu hình"))
            + DOT + N(f.components.length) + SP + tx(B("components", "thành phần"));

        return `
            <div class="lrn-herocta" data-coach="dash-hero">
                ${ic("zap")}
                <span><b>${esc(tx(B("Good afternoon", "Chào buổi chiều")))}${SP}·
                        Hoa Sen Retail Co.</b><br>
                    <span class="lrn-sub2">${esc(heroSub)}</span></span>
                <button class="lrn-btn pri" data-coach="dash-runpayroll">${ic("zap")}${
                    esc(T("runPayroll"))}</button>
            </div>
            <div class="lrn-grid g4" data-coach="dash-kpis">
                ${kpiTile("users", "", N(k.headcount), B("Headcount", "Nhân sự"))}
                ${kpiTile("trending-up", "pos", M(k.monthlyNet), B("Monthly payroll", "Chi phí lương tháng"))}
                ${kpiTile("clipboard-check", "warn", N(k.waiting), B("Pending approval", "Chờ phê duyệt"))}
                ${kpiTile("calculator", "", N(k.configs), B("Active configs", "Cấu hình đang chạy"))}
            </div>
            <div class="lrn-grid g2 top">
                <div class="lrn-panel" data-coach="rep-dash-runs">
                    <h3>${ic("calendar")}${esc(tx(B("Recent pay runs", "Các đợt lương gần đây")))}</h3>
                    <div class="lrn-rows">${rows}</div>
                </div>
                <div class="lrn-panel" data-coach="dash-formula">
                    <h3>${ic("calculator")}${esc(tx(B("Formula engine", "Công thức lương")))}</h3>
                    <p class="lrn-note">${esc(formulaMeta)}</p>
                    <div class="lrn-kv2"><span>${esc(tx(B("This division", "Bộ phận này")))}</span>
                        <b>${esc(f.code)}</b></div>
                    <p class="lrn-note">${esc(tx(B(
                        "Pay is computed from readable configurations, not fixed salary structures. This card is the way in.",
                        "Lương được tính từ các cấu hình đọc được, không phải từ cấu trúc lương cố định. Thẻ này là lối vào đó.")))}</p>
                </div>
            </div>`;
    },

    /* --------------------------------------------------------- Approvals
       The LANES ARE THE FIXTURE'S BOARD, filtered by gate. Two of the three are
       empty today and are drawn empty on purpose: the product renders "No runs
       here." for exactly this state, and a lane with nothing in it is not a
       lane that is broken. */
    approvals() {
        const a = PRACTICE.approvals;
        const k = a.kpis;
        const lanes = a.lanes.map((lane) => {
            const cards = lane.runs.map((r) => {
                const meta = N(r.employees) + SP + tx(B("payslips", "phiếu lương"));
                return `
                <div class="lrn-kcard" data-coach="pk-card">
                    <b>${esc(tx(r.name))}</b>
                    <div class="lrn-kmeta">
                        <span>${esc(meta)}</span>
                        <span class="lrn-money">${esc(M(r.net))}</span>
                    </div>
                    <div class="lrn-kacts">
                        <button class="lrn-btn sm pri">${ic("check")}${
                            esc(tx(B("Approve", "Phê duyệt")))}</button>
                        <button class="lrn-btn sm ghost danger">${esc(T("reject"))}</button>
                    </div>
                </div>`;
            }).join("");
            const empty = `<p class="lrn-note">${esc(tx(B(
                "No runs here.", "Không có đợt nào ở đây.")))}</p>`;
            return `
            <div class="lrn-kcol">
                <div class="lrn-kcolh">${statusChip("payrun", lane.key)}</div>
                ${cards || empty}
            </div>`;
        }).join("");

        const recent = a.recent.map((r) => `
            <div class="lrn-row">
                <span class="lrn-avatar">${ic("check-circle")}</span>
                <span><span class="lrn-nm">${esc(tx(r.name))}</span><br>
                    <span class="lrn-sub2">${esc(tx(B("Approved", "Đã duyệt")))}</span></span>
                <span class="lrn-rr"><b class="lrn-money">${esc(M(r.net))}</b></span>
            </div>`).join("");

        return `
            <div class="lrn-herocta" data-coach="pa-hero">
                ${ic("clipboard-check")}
                <span><b>${esc(tx(B("Approval pipeline", "Quy trình phê duyệt")))}</b><br>
                    <span class="lrn-sub2">${esc(tx(B(
                        "Officer review → HR review → Finance approval",
                        "Chuyên viên soát → HR soát xét → Tài chính phê duyệt")))}</span></span>
                <span class="lrn-chip warn">${ic("inbox")}${N(k.officer)}${SP}${
                    esc(tx(B("awaiting you", "đang chờ bạn")))}</span>
            </div>
            <div class="lrn-grid g4" data-coach="pa-kpis">
                ${kpiTile("clock", "", N(k.officer), B("At Officer review", "Ở vòng Chuyên viên"))}
                ${kpiTile("users", "", N(k.hr), B("At HR review", "Ở vòng HR soát xét"))}
                ${kpiTile("shield-check", "", N(k.finance), B("At Finance approval", "Ở vòng Tài chính"))}
                ${kpiTile("receipt", "warn", M(k.net), B("Net at stake", "Số tiền đang treo"))}
            </div>
            <div class="lrn-kanban" data-coach="pa-lanes">${lanes}</div>
            <div class="lrn-panel" data-coach="pa-reject">
                <h3>${ic("x")}${esc(tx(B("Reject this run", "Từ chối đợt lương này")))}</h3>
                <label class="lrn-flabel">${esc(tx(B(
                    "Reason (required)", "Lý do (bắt buộc)")))}</label>
                <input class="lrn-in" readonly="readonly" value="${esc(tx(B(
                    "Payslip NV0031 — overtime is 382% of June. Verify against the timesheet and resubmit.",
                    "Phiếu NV0031 — tăng ca bằng 382% tháng 6. Đối chiếu bảng chấm công rồi trình lại.")))}"/>
                <p class="lrn-note">${esc(tx(B(
                    "All payslips in this run go back to draft together. The reason is recorded with your name and the time, and it is the only thing the officer has to work from.",
                    "Toàn bộ phiếu lương trong đợt cùng quay về Nháp. Lý do được lưu kèm tên bạn và thời điểm, và đó là thứ duy nhất chuyên viên có để làm việc.")))}</p>
            </div>
            <div class="lrn-panel" data-coach="pa-recent">
                <h3>${ic("list-checks")}${esc(tx(B("Recently decided", "Đã quyết gần đây")))}</h3>
                <div class="lrn-rows">${recent}</div>
                <p class="lrn-note">${esc(tx(B(
                    "Approvals and rejections land here together, and a rejection keeps its written reason. This list is the audit trail as a reading surface.",
                    "Cả phê duyệt lẫn từ chối đều rơi vào đây, và một lần từ chối vẫn giữ nguyên lý do bằng văn bản. Danh sách này là vết kiểm toán ở dạng đọc được.")))}</p>
            </div>`;
    },

    /* --------------------------------------------------------- Employees */
    employees() {
        const p = PRACTICE.people;
        const k = p.kpis;
        const ready = tx(B("Payroll-ready", "Sẵn sàng tính lương"));
        const notReady = tx(B("Not ready", "Chưa sẵn sàng"));
        const rows = p.rows.map((r) => {
            const meta = tx(r.job) + DOT + tx(r.emp.dept);
            const expiry = r.expiresIn
                ? `<span class="lrn-chip warn">${ic("alert-triangle")}${N(r.expiresIn)}${
                    SP}${esc(tx(B("days", "ngày")))}</span>`
                : "";
            return `
            <div class="lrn-row ${r.ready ? "" : "hit"}">
                <span class="lrn-avatar">${esc(initial(r.emp.name))}</span>
                <span><span class="lrn-nm">${esc(r.emp.name)}
                        <span class="lrn-faint">${esc(r.emp.code)}</span></span><br>
                    <span class="lrn-sub2">${esc(meta)}${
                        r.blocker ? DOT + esc(tx(r.blocker)) : ""}</span></span>
                <span class="lrn-rr">${expiry}
                    <span class="lrn-chip ${r.ready ? "ok" : "danger"}">${
                        esc(r.ready ? ready : notReady)}</span>
                    <b class="lrn-money">${esc(M(r.emp.base))}</b></span>
            </div>`;
        }).join("");

        return `
            <div class="lrn-strip" data-coach="pe-head">
                <button class="lrn-btn" data-coach="pe-bulk">${ic("list-checks")}${
                    esc(tx(B("Select", "Chọn nhiều")))}</button>
                <button class="lrn-btn pri" data-coach="rep-newemp-open">${ic("plus")}${
                    esc(tx(B("Add employee", "Thêm nhân viên")))}</button>
            </div>
            <div class="lrn-grid g6" data-coach="pe-kpis">
                ${kpiTile("users", "", N(k.headcount), B("Headcount", "Sĩ số"))}
                ${kpiTile("check-circle", "pos", N(k.running), B("Running contracts", "Hợp đồng đang hiệu lực"))}
                ${kpiTile("alert-triangle", "warn", N(k.expiring), B("Expiring in 30 days", "Hết hạn trong 30 ngày"))}
                ${kpiTile("user-plus", "", N(k.newHires), B("New this month", "Vào mới tháng này"))}
                ${kpiTile("receipt", "", M(k.wageBill), B("Monthly wage bill", "Quỹ lương tháng"))}
                ${kpiTile("check", "pos", P(k.readyPct), B("Payroll-ready", "Sẵn sàng tính lương"))}
                <!-- The tile is bank-details-over-headcount; the per-row tick
                     below also requires a running contract. Two different
                     tests, one word — see the payroll_ready column. -->
            </div>
            <div class="lrn-tabs" data-coach="pe-filters">
                ${[B("All", "Tất cả"), B("Running", "Đang hiệu lực"),
                   B("Expiring", "Sắp hết hạn"), B("Not payroll-ready", "Chưa sẵn sàng")].map(
                    (f, i) => `<button aria-selected="${i === 0}">${esc(tx(f))}</button>`).join("")}
            </div>
            <div class="lrn-panel">
                <h3>${ic("users")}${esc(tx(B("Employees", "Nhân viên")))}</h3>
                <div class="lrn-rows" data-coach="pe-roster">${rows}</div>
                <p class="lrn-note">${esc(tx(B(
                    "Headcount counts everybody this practice company employs — all 48 — while the four rows below are a sample you can read. The wage shown is the registered contract base, the figure insurance is charged on, not what the person will be paid this month.",
                    "Sĩ số đếm toàn bộ nhân sự của công ty thực hành này — đủ 48 người — còn bốn dòng bên dưới là một mẫu đủ nhỏ để đọc. Mức lương hiển thị là lương cơ bản đã đăng ký theo hợp đồng, tức mức dùng để tính bảo hiểm, không phải số người đó thực nhận trong tháng.")))}</p>
            </div>
            ${newEmployeeHTML()}`;
    },

    /* --------------------------------------------------------- Contracts */
    contracts() {
        const c = PRACTICE.contracts;
        const k = c.kpis;
        const rows = c.rows.map((r) => {
            const meta = tx(r.kind) + DOT + tx(r.period);
            const expiry = r.expiresIn
                ? `<span class="lrn-chip warn">${ic("alert-triangle")}${N(r.expiresIn)}${
                    SP}${esc(tx(B("days", "ngày")))}</span>`
                : "";
            return `
            <div class="lrn-row">
                <span class="lrn-avatar">${esc(initial(r.emp.name))}</span>
                <span><span class="lrn-nm">${esc(r.emp.name)}
                        <span class="lrn-faint">${esc(r.emp.code)}</span></span><br>
                    <span class="lrn-sub2">${esc(meta)}</span></span>
                <span class="lrn-rr">${expiry}
                    <span class="lrn-chip">${esc(tx(r.badge))}</span>
                    <b class="lrn-money">${esc(M(r.emp.base))}</b></span>
            </div>`;
        }).join("");

        return `
            <div class="lrn-strip" data-coach="ct-head">
                <button class="lrn-btn pri">${ic("plus")}${
                    esc(tx(B("New contract", "Hợp đồng mới")))}</button>
            </div>
            <div class="lrn-grid g6" data-coach="ct-kpis">
                ${kpiTile("check-circle", "pos", N(k.running), B("Running", "Đang hiệu lực"))}
                ${kpiTile("alert-triangle", "warn", N(k.expiring), B("Expiring in 30 days", "Hết hạn trong 30 ngày"))}
                ${kpiTile("file-text", "", N(k.draft), B("Draft", "Nháp"))}
                ${kpiTile("clock", "", N(k.expired), B("Expired", "Đã hết hạn"))}
                ${kpiTile("receipt", "", M(k.wageBill), B("Monthly wage bill", "Quỹ lương tháng"))}
                ${kpiTile("calculator", "", M(k.avgWage), B("Average wage", "Lương bình quân"))}
            </div>
            <div class="lrn-tabs" data-coach="ct-filters">
                ${[B("All", "Tất cả"), B("Running", "Đang hiệu lực"),
                   B("Expiring", "Sắp hết hạn"), B("Draft", "Nháp")].map(
                    (f, i) => `<button aria-selected="${i === 0}">${esc(tx(f))}</button>`).join("")}
            </div>
            <div class="lrn-panel">
                <h3>${ic("file-text")}${esc(tx(B("Contracts", "Hợp đồng")))}</h3>
                <div class="lrn-rows" data-coach="ct-roster">${rows}</div>
                <p class="lrn-note">${esc(tx(B(
                    "A draft contract is not paid. It is the same person as on Employees, read as the agreement payroll is computed from.",
                    "Hợp đồng ở trạng thái Nháp thì không được trả lương. Vẫn là con người ấy như bên Nhân viên, nhưng đọc dưới dạng thoả thuận mà hệ thống lương dựa vào để tính.")))}</p>
            </div>`;
    },

    /* ---------------------------------------------------------- Insights */
    insights() {
        const d = PRACTICE.insights;
        const months = d.months.map((m) => `
            <div class="lrn-cr"><span>${esc(tx(m.period))}</span>
                <b>${esc(M(m.net))}</b></div>`).join("");
        const depts = d.departments.map((x) => {
            const heads = N(x.heads) + SP + T("employees");
            return `
            <div class="lrn-row">
                <span><span class="lrn-nm">${esc(tx(x.label))}</span><br>
                    <span class="lrn-sub2">${esc(heads)}</span></span>
                <span class="lrn-rr"><b class="lrn-money">${esc(M(x.v))}</b></span>
            </div>`;
        }).join("");
        const stat = d.statutory.map((x) => `
            <div class="lrn-cr"><span>${esc(tx(x.label))}</span>
                <b>${esc(M(x.v))}</b></div>`).join("");
        const pulse = d.pulse.map((x) => `
            <span class="lrn-statpill"><b>${N(x.v)}</b>${esc(tx(x.label))}</span>`).join("");
        // THE HERO IS ONE RUN, and it says so. pb_insights takes the LATEST run
        // whatever state it is in and prints its name and state chip beside the
        // figure; the leaderboard below spans every division in the period. A
        // hero labelled just "Net" above a table that sums two divisions reads
        // as a board that does not add up.
        const heroSub = tx(B("Latest run", "Đợt gần nhất")) + DOT + tx(d.headlineScope)
            + DOT + P(d.deltaPct) + SP + tx(B("against last month", "so với tháng trước"));

        return `
            <div class="lrn-herocta" data-coach="in-hero">
                ${ic("trending-up")}
                <span><b>${esc(M(d.headline))}</b><br>
                    <span class="lrn-sub2">${esc(heroSub)}</span></span>
                ${statusChip("payrun", d.headlineState)}
                <span class="lrn-chip b">${esc(tx(B("Net payroll", "Lương thực chi")))}</span>
            </div>
            <div class="lrn-panel" data-coach="in-trend">
                <h3>${ic("bar-chart")}${esc(tx(B("Cost story", "Diễn biến chi phí")))}</h3>
                <div class="lrn-calc">${months}</div>
                <p class="lrn-note">${esc(tx(B(
                    "Three months, in the order they were paid. A trend answers a different question from a total, and the window you choose decides which.",
                    "Ba tháng, theo đúng thứ tự đã chi. Một xu hướng trả lời câu hỏi khác với một con số tổng, và khoảng thời gian bạn chọn quyết định đó là câu hỏi nào.")))}</p>
            </div>
            <div class="lrn-grid g2 top" data-coach="in-duo">
                <div class="lrn-panel">
                    <h3>${ic("layers")}${esc(tx(B("Department leaderboard", "Xếp hạng bộ phận")))}</h3>
                    <div class="lrn-rows">${depts}</div>
                    <p class="lrn-note">${esc(tx(B(
                        "Every division in the period — which is a wider scope than the headline above, and the reason the two do not add up to each other.",
                        "Mọi bộ phận trong kỳ — phạm vi rộng hơn con số nổi bật ở trên, và đó là lý do hai bên không cộng lại bằng nhau.")))}</p>
                </div>
                <div class="lrn-panel">
                    <h3>${ic("shield-check")}${esc(tx(B("Statutory split", "Cơ cấu đóng bắt buộc")))}</h3>
                    <div class="lrn-calc">${stat}</div>
                    <p class="lrn-note">${esc(tx(B(
                        "The employer leg never appears in anybody's net, which is why it is invisible in every conversation about pay unless somebody puts it on the table.",
                        "Phần doanh nghiệp không bao giờ xuất hiện trong thực nhận của ai, nên nó vô hình trong mọi cuộc trao đổi về lương trừ khi có người chủ động nêu ra.")))}</p>
                </div>
            </div>
            <div class="lrn-panel">
                <h3>${ic("heart")}${esc(tx(B("Workforce pulse", "Nhịp nhân sự")))}</h3>
                <div class="lrn-statpills" data-coach="in-pulse">${pulse}</div>
            </div>
            <div class="lrn-herocta" data-coach="in-explore">
                ${ic("sparkles")}
                <span><b>${esc(tx(B("Ask something else", "Hỏi điều khác")))}</b><br>
                    <span class="lrn-sub2">${esc(tx(B(
                        "Every figure above opens where it came from. When the question is one this board did not anticipate, the Explorer is the way in.",
                        "Mọi con số ở trên đều mở ra đúng nơi nó sinh ra. Khi câu hỏi vượt ra ngoài những gì bảng này lường trước, Explorer là lối đi tiếp.")))}</span></span>
                <button class="lrn-btn">${esc(tx(B("Open Explorer", "Mở Explorer")))}</button>
            </div>`;
    },

    /* ---------------------------------------------------------- Explorer */
    explorer() {
        const x = PRACTICE.explorer;
        const filters = x.filters.map((f) => `
            <span class="lrn-chip b">${esc(tx(f.k))}: ${esc(tx(f.v))}${ic("x")}</span>`).join("");
        const rows = x.rows.map((r) => `
            <div class="lrn-cr"><span>${esc(tx(r.label))}</span>
                <b>${esc(M(r.v))}</b></div>`).join("");
        const headline = tx(x.measure) + SP + tx(B("by", "theo")) + SP + tx(x.dimension);

        return `
            <div class="lrn-strip" data-coach="ex-head">
                <span class="lrn-chip">${ic("compass")}${esc(tx(B("Explorer", "Explorer")))}</span>
                <span class="lrn-sub2">${esc(tx(B(
                    "Pick a measure, break it down, filter it.",
                    "Chọn một chỉ tiêu, tách theo chiều nào đó, rồi lọc.")))}</span>
            </div>
            <div class="lrn-panel" data-coach="ex-rail">
                <h3>${ic("crosshair")}${esc(tx(B("The question", "Câu hỏi")))}</h3>
                <div class="lrn-strip">
                    <span class="lrn-chip b">${esc(tx(B("Measure", "Chỉ tiêu")))}: ${
                        esc(tx(x.measure))}</span>
                    <span class="lrn-chip b">${esc(tx(B("Break down by", "Tách theo")))}: ${
                        esc(tx(x.dimension))}</span>
                </div>
                <div class="lrn-strip" data-coach="ex-filters">
                    <span class="lrn-sub2">${esc(tx(B("Where", "Điều kiện")))}</span>${filters}
                </div>
            </div>
            <div class="lrn-panel">
                <div class="lrn-kv2" data-coach="ex-headline">
                    <span>${esc(headline)}</span><b class="lrn-money">${esc(M(x.total))}</b>
                </div>
                <div class="lrn-calc" data-coach="ex-table">${rows}</div>
                <p class="lrn-note">${esc(tx(B(
                    "The rows are the breakdown and the total is their sum, read from the payslips themselves. A figure taken from here without its filters is a figure read out of scope.",
                    "Các dòng là phần tách nhỏ và con số tổng là tổng của chúng, đọc thẳng từ chính các phiếu lương. Lấy một con số ở đây mà bỏ quên bộ lọc là đọc sai phạm vi.")))}</p>
            </div>`;
    },

    /* ------------------------------------------------ Workforce Analytics */
    workforcean() {
        const w = PRACTICE.workforce;
        const k = w.kpis;
        const chart = w.months.map((m) => `
            <div class="lrn-cr"><span>${esc(tx(m.period))}</span>
                <b>${N(m.employees)}</b></div>`).join("");
        const exceptions = w.exceptions.map((e) => `
            <div class="lrn-cr"><span>${esc(tx(e.label))}</span><b>${N(e.v)}</b></div>`).join("");
        const ot = w.overtime.map((o) => `
            <div class="lrn-row">
                <span class="lrn-avatar">${esc(initial(o.emp.name))}</span>
                <span><span class="lrn-nm">${esc(o.emp.name)}</span><br>
                    <span class="lrn-sub2">${esc(o.emp.code)}</span></span>
                <span class="lrn-rr"><b class="lrn-money">${esc(M(o.v))}</b></span>
            </div>`).join("");

        return `
            <div class="lrn-strip" data-coach="wa-head">
                <span class="lrn-chip">${ic("users")}${esc(tx(B(
                    "Workforce Insights", "Phân tích nhân sự")))}</span>
                <span class="lrn-sub2">${esc(tx(B(
                    "Attendance, overtime and cost per head — read off payroll, not off a separate system.",
                    "Chấm công, tăng ca và chi phí bình quân đầu người — đọc từ chính dữ liệu lương, không từ một hệ thống riêng.")))}</span>
            </div>
            <div class="lrn-tabs" data-coach="wa-filters">
                ${[B("All divisions", "Tất cả bộ phận"), RUN.division,
                   B("This month", "Tháng này")].map(
                    (f, i) => `<button aria-selected="${i === 0}">${esc(tx(f))}</button>`).join("")}
            </div>
            <div class="lrn-grid g4" data-coach="wa-kpis">
                ${kpiTile("users", "", N(k.paid), B("Employees paid", "Nhân viên được trả lương"))}
                ${kpiTile("user-plus", "pos", N(k.joiners), B("Joiners", "Vào mới"))}
                ${kpiTile("arrow-right", "warn", N(k.leavers), B("Leavers", "Thôi việc"))}
                ${kpiTile("calculator", "", M(k.perHead), B("Cost per head", "Chi phí bình quân"))}
            </div>
            <div class="lrn-panel" data-coach="wa-chart">
                <h3>${ic("bar-chart")}${esc(tx(B("Headcount paid", "Số người được trả lương")))}</h3>
                <div class="lrn-calc">${chart}</div>
                <p class="lrn-note">${esc(tx(B(
                    "Paid, not employed. A step in this line is a joiner wave, a leaver wave — or a run that did not include everybody.",
                    "Là được TRẢ LƯƠNG, không phải đang làm việc. Một bậc nhảy trên đường này là một nhóm người mới vào, một nhóm người nghỉ việc — hoặc một kỳ lương đã bỏ sót ai đó.")))}</p>
            </div>
            <div class="lrn-grid g2 top" data-coach="wa-duo">
                <div class="lrn-panel">
                    <h3>${ic("alert-triangle")}${esc(tx(B(
                        "Attendance exceptions", "Ngoại lệ chấm công")))}</h3>
                    <div class="lrn-calc">${exceptions}</div>
                </div>
                <div class="lrn-panel">
                    <h3>${ic("clock")}${esc(tx(B("Overtime this month", "Tăng ca tháng này")))}</h3>
                    <div class="lrn-rows">${ot}</div>
                </div>
            </div>`;
    },

    /* -------------------------------------------------- Government Reports */
    govreports() {
        const g = PRACTICE.govreports;
        const chips = g.countries.map((c, i) =>
            `<button aria-selected="${i === g.selected}">${esc(tx(c))}</button>`).join("");
        const groups = g.groups.map((grp) => {
            const tiles = grp.reports.map((r) => `
                <div class="lrn-row">
                    <span class="lrn-avatar">${ic("file-text")}</span>
                    <span><span class="lrn-nm">${esc(r.en)}</span><br>
                        <span class="lrn-sub2">${esc(r.vi)}</span></span>
                    <span class="lrn-rr"><button class="lrn-btn sm pri">${
                        esc(tx(B("Generate", "Kết xuất")))}</button></span>
                </div>`).join("");
            return `
            <div class="lrn-panel">
                <h3>${ic(grp.icon)}${esc(tx(grp.label))}</h3>
                <div class="lrn-rows">${tiles}</div>
            </div>`;
        }).join("");
        const head = tx(g.country) + DOT + tx(g.period);

        // ONE STATE OR THE OTHER, never both. The product is a t-if/t-else on
        // `available`: a country whose payroll module is installed shows its
        // tiles, and one whose module is not shows the empty card INSTEAD.
        // Drawing them together taught a screen that cannot exist — and taught
        // it on the one screen whose lesson is about reading an empty state
        // correctly. `available` follows the selected country chip.
        const available = g.selected === 0;
        const body = available
            ? `<div class="lrn-grid g2 top" data-coach="gr-grid">${groups}</div>`
            : `<div class="lrn-panel" data-coach="gr-empty">
                <h3>${ic("globe")}${esc(tx(B("Coming soon", "Sắp có")))}</h3>
                <p class="lrn-note">${esc(tx(B(
                    "Government reports for this country are coming soon.",
                    "Các báo cáo cơ quan nhà nước cho quốc gia này sắp có.")))}</p>
                <p class="lrn-note">${esc(tx(B(
                    "It means this country's own payroll module is not installed on this database — not that the filings do not exist. Five countries are in the catalogue, and a country's tiles appear as soon as the module holding its wizard is there.",
                    "Điều đó nghĩa là mô-đun tính lương của quốc gia này chưa được cài trên cơ sở dữ liệu — chứ không phải các biểu mẫu không tồn tại. Danh mục đã có năm quốc gia, và biểu mẫu của một quốc gia sẽ xuất hiện ngay khi mô-đun chứa trình lập báo cáo của nó có mặt.")))}</p>
            </div>`;

        return `
            <div class="lrn-strip" data-coach="gr-head">
                <span class="lrn-chip">${ic("file-text")}${esc(head)}</span>
                <span class="lrn-sub2">${esc(tx(B(
                    "Statutory filings for this company, for one month at a time.",
                    "Các báo cáo bắt buộc của công ty này, theo từng tháng một.")))}</span>
            </div>
            <div class="lrn-tabs" data-coach="gr-countries">${chips}</div>
            ${body}`;
    },

    /* ------------------------------------------------------- Run Payroll */
    runpayroll() {
        const rows = PRACTICE.computed.map((r) => `
            <div class="lrn-row ${r.flag ? "hit" : ""}">
                <span class="lrn-avatar">${esc(initial(r.emp.name))}</span>
                <span><span class="lrn-nm">${esc(r.emp.name)}
                        <span class="lrn-faint">${esc(r.emp.code)}</span></span><br>
                    <span class="lrn-sub2">${esc(tx(B("Overtime", "Tăng ca")))}: ${esc(M(r.ot))}</span></span>
                <span class="lrn-rr">${r.flag
                    ? `<span class="lrn-chip warn">${ic("alert-triangle")}${esc(tx(r.why))}</span>` : ""}
                    <b class="lrn-money">${esc(M(r.net))}</b></span>
            </div>`).join("");

        const steps = [
            B("Scope", "Phạm vi"), B("Compute", "Tính lương"),
            B("Review exceptions", "Soát ngoại lệ"), B("Open payroll", "Mở bảng lương"),
        ].map((s, i) => `
            <div class="lrn-wstep ${i === 1 ? "cur" : i < 1 ? "done" : ""}">
                <span class="lrn-wdot">${i + 1}</span><span>${esc(tx(s))}</span>
            </div>`).join("");

        return `
            <div class="lrn-rail" data-coach="pw-rail">${steps}</div>
            <div class="lrn-grid g2 top">
                <div class="lrn-panel" data-coach="pw-scope">
                    <h3>${ic("calendar")}${esc(tx(B("Period", "Kỳ lương")))}</h3>
                    <label class="lrn-flabel">${esc(tx(B("Configuration", "Cấu hình")))}</label>
                    <select class="lrn-in" data-coach="pw-division">
                        <option>${esc(tx(RUN.division))}</option>
                        <option>${esc(tx(B("IT Services", "Dịch vụ CNTT")))}</option>
                        <option>F&amp;B</option>
                    </select>
                    <label class="lrn-flabel">${esc(tx(B("Batch name", "Tên đợt")))}</label>
                    <input class="lrn-in" value="${esc(tx(RUN.name))}" readonly="readonly"/>
                </div>
                <div class="lrn-panel" data-coach="pw-summary">
                    <h3>${ic("target")}${esc(tx(B("Scope", "Phạm vi")))}</h3>
                    <div class="lrn-kv2"><span>${esc(tx(B("Company", "Công ty")))}</span><b>Hoa Sen Retail Co.</b></div>
                    <div class="lrn-kv2"><span>${esc(tx(B("Configuration", "Cấu hình")))}</span><b>${esc(RUN.config)}${SP}· ${esc(RUN.configVersion)}</b></div>
                    <div class="lrn-kv2"><span>${esc(tx(B("Eligible employees", "Nhân viên đủ điều kiện")))}</span><b>${N(RUN.employees)}</b></div>
                    <p class="lrn-note">${esc(tx(B(
                        "A draft run will be created and computed — fully reversible. Only the selected division is affected.",
                        "Một đợt nháp sẽ được tạo và tính — hoàn toàn có thể hoàn tác. Chỉ bộ phận đã chọn bị ảnh hưởng.")))}</p>
                    <button class="lrn-btn pri" data-coach="pw-compute">${ic("play")}${esc(T("compute"))}</button>
                </div>
            </div>
            <div class="lrn-panel" data-coach="pw-result">
                <h3>${ic("check-circle")}${esc(tx(RUN.name))}</h3>
                <div class="lrn-statpills" data-coach="pw-pills">
                    <span class="lrn-statpill"><b>${N(RUN.employees)}</b>${esc(tx(B("Payslips", "Phiếu lương")))}</span>
                    <span class="lrn-statpill"><b>${N(RUN.employees)}</b>${esc(tx(B("Computed", "Đã tính")))}</span>
                    <span class="lrn-statpill warn"><b>${N(RUN.flagged)}</b>${esc(T("needReview"))}</span>
                </div>
                <div class="lrn-rows" data-coach="pw-exceptions">${rows}</div>
            </div>`;
    },

    /* ---------------------------------------------------------- Pay Runs */
    payruns() {
        const k = PRACTICE.boardKpis;
        const cols = ["draft", "level0", "level1", "level2", "done"];
        const board = cols.map((col) => `
            <div class="lrn-kcol">
                <div class="lrn-kcolh">${statusChip("payrun", col)}</div>
                ${PRACTICE.board.filter((r) => r.col === col).map(runCard).join("")}
            </div>`).join("");

        return `
            <div class="lrn-grid g5" data-coach="pk-kpis">
                ${kpiTile("layers", "", N(k.total), B("Pay runs", "Đợt tính lương"))}
                ${kpiTile("clock", "", N(k.inPipeline), B("In pipeline", "Đang trong quy trình"))}
                ${kpiTile("alert-triangle", "warn", N(k.myPending), B("Awaiting your approval", "Chờ bạn phê duyệt"))}
                ${kpiTile("check-circle", "pos", N(k.done), B("Completed", "Hoàn tất"))}
                ${kpiTile("receipt", "pos", M(k.net), B("Net paid (done)", "Đã chi (hoàn tất)"))}
            </div>
            <div class="lrn-strip">
                <button class="lrn-btn pri" data-coach="pk-run">${ic("zap")}${esc(T("runPayroll"))}</button>
            </div>
            <div class="lrn-tabs" data-coach="pk-tabs">
                ${cols.map((c, i) =>
                    `<button aria-selected="${i === 0}">${esc(tx(STATUS_LABELS.payrun[c].l))}</button>`).join("")}
            </div>
            <div class="lrn-tabs" data-coach="pk-datechips">
                ${[B("This month", "Tháng này"), B("Last month", "Tháng trước"), B("This year", "Năm nay")].map((d, i) =>
                    `<button aria-selected="${i === 0}">${esc(tx(d))}</button>`).join("")}
            </div>
            <div class="lrn-tabs" data-coach="pk-divchips">
                ${[B("All divisions", "Tất cả bộ phận"), RUN.division, B("F&B", "F&B")].map((d, i) =>
                    `<button aria-selected="${i === 0}">${esc(tx(d))}</button>`).join("")}
            </div>
            <div class="lrn-kanban">${board}</div>
            <div class="lrn-panel" data-coach="rep-pipeline">
                <h3>${ic("git-branch")}${esc(tx(B("How a run travels", "Một đợt lương đi thế nào")))}</h3>
                ${pipeHTML("payrun", 0)}
            </div>`;
    },

    /* ---------------------------------------------------------- Payslips */
    payslips() {
        const t = PRACTICE.slipTotals;
        // Built OUTSIDE the template literal on purpose: a quoted string inside
        // an interpolation makes rjsmin lose track of the enclosing literal and
        // strip whitespace from the rest of it (see runtime.js).
        const approved = N(t.done) + " / " + N(t.count);
        const list = PRACTICE.slips.map((s) => `
            <div class="lrn-row ${s.sel ? "on" : ""}">
                <span class="lrn-avatar">${esc(initial(s.emp.name))}</span>
                <span><span class="lrn-nm">${esc(s.emp.name)}</span><br>
                    <span class="lrn-sub2">${esc(s.emp.code)}</span></span>
                <span class="lrn-rr">${s.flag
                    ? `<span class="lrn-chip warn">${esc(T("needReview"))}</span>` : ""}
                    <b class="lrn-money">${esc(M(s.net))}</b></span>
            </div>`).join("");

        // A payslip's own chain — FOUR stages. It has no level0; that gate
        // belongs to the run. Drawing the run's five here would teach a tier
        // that does not exist on a slip.
        //
        // The current stage is read from the SELECTED slip rather than fixed,
        // so the stepper cannot disagree with the row that is highlighted. The
        // July run is at level0, which means every slip in it is still draft.
        const chain = ["draft", "level1", "level2", "done"];
        const at = Math.max(0, chain.indexOf((PRACTICE.slips.find((x) => x.sel)
            || PRACTICE.slips[0]).state));
        const flow = chain.map((c, i) => `
            <div class="lrn-st ${i < at ? "done" : ""}${SP}${i === at ? "cur" : ""}"
                >${esc(tx(STATUS_LABELS.payslip[c].l))}</div>`).join("");

        return `
            <div class="lrn-strip">
                <select class="lrn-in" data-coach="ps-runsel">
                    <option>${esc(tx(RUN.name))}</option>
                    <option>${esc(tx(B("Retail — June 2026", "Bán lẻ — Tháng 6/2026")))}</option>
                </select>
            </div>
            <div class="lrn-grid g5" data-coach="ps-kpis">
                ${kpiTile("receipt", "", N(t.count), B("Payslips", "Phiếu lương"))}
                ${kpiTile("trending-up", "pos", M(t.net), B("Net total", "Tổng thực nhận"))}
                ${kpiTile("calculator", "", M(t.gross), B("Gross total", "Tổng thu nhập"))}
                ${kpiTile("check-circle", "", approved, B("Approved", "Đã duyệt"))}
                ${kpiTile("alert-triangle", "warn", N(t.flagged), B("Need review", "Cần soát xét"))}
            </div>
            <div class="lrn-tabs" data-coach="ps-chips">
                ${[B("All", "Tất cả"), B("Need review", "Cần soát xét"), B("HR pending", "Chờ HR"),
                   B("GM pending", "Chờ TGĐ"), B("Done", "Hoàn tất")].map((c, i) =>
                    `<button aria-selected="${i === 0}">${esc(tx(c))}</button>`).join("")}
            </div>
            <div class="lrn-grid g2 top">
                <div class="lrn-panel">
                    <h3>${ic("users")}${esc(tx(B("Payslips in this run", "Phiếu lương trong đợt này")))}</h3>
                    <div class="lrn-rows" data-coach="ps-list">${list}</div>
                </div>
                <div class="lrn-panel" data-coach="ps-detail">
                    <h3>${ic("receipt")}${esc(CASE.emp.mai.name)}${SP}· ${esc(CASE.emp.mai.code)}</h3>
                    <div class="lrn-status" data-coach="ps-status">${flow}</div>
                    <div data-coach="ps-breakdown">${calcHTML()}</div>
                </div>
            </div>`;
    },

    /* ------------------------------------------------------------ Import */
    import() {
        const k = PRACTICE.importKpis;
        const pipe = PRACTICE.importPipe.map((p, i) => `
            <button class="lrn-pipestep ${p.count ? "on" : ""}">
                <span class="lrn-pipen">${N(p.count)}</span>
                <span>${esc(tx(p.label))}</span>
            </button>${i < PRACTICE.importPipe.length - 1 ? '<span class="lrn-pa"></span>' : ""}`).join("");
        const batches = PRACTICE.importBatches.map((b) => `
            <div class="lrn-row">
                <span><span class="lrn-nm">${esc(tx(b.name))}</span><br>
                    <span class="lrn-sub2">${N(b.rows)}${SP}${esc(tx(B("rows", "dòng")))}</span></span>
                <span class="lrn-rr">${statusChip("importbatch", b.state)}</span>
            </div>`).join("");

        return `
            <div class="lrn-grid g5" data-coach="im-kpis">
                ${kpiTile("database", "", N(k.batches), B("Import batches", "Đợt nhập liệu"))}
                ${kpiTile("check-circle", "pos", N(k.done), B("Completed", "Hoàn tất"))}
                ${kpiTile("clock", "", N(k.inProgress), B("In progress", "Đang xử lý"))}
                ${kpiTile("alert-triangle", "warn", N(k.errors), B("With errors", "Có lỗi"))}
                ${kpiTile("plug", "", N(k.connectors), B("Connectors", "Đầu nối"))}
            </div>
            <div class="lrn-herocta" data-coach="im-cta">
                ${ic("send")}
                <span><b>${esc(tx(B("Start an import", "Bắt đầu nhập liệu")))}</b><br>
                    <span class="lrn-sub2">${esc(tx(B(
                        "A guided flow — upload your file, review matches, fix any issues, then commit.",
                        "Luồng có hướng dẫn — tải tệp lên, soát các dòng khớp, sửa lỗi, rồi ghi nhận.")))}</span></span>
                <button class="lrn-btn pri">${esc(T("startImport"))}</button>
            </div>
            <div class="lrn-strip" data-coach="im-launches">
                <button class="lrn-btn sm">${ic("file-text")}${esc(tx(B("Multi-sheet import", "Nhập nhiều bảng")))}</button>
                <button class="lrn-btn sm">${ic("plug")}${esc(tx(B("Connectors", "Đầu nối")))}</button>
            </div>
            <div class="lrn-panel">
                <h3>${ic("git-branch")}${esc(tx(B("Import pipeline", "Quy trình nhập liệu")))}</h3>
                <div class="lrn-pipe2" data-coach="im-pipe">${pipe}</div>
            </div>
            <div class="lrn-panel">
                <h3>${ic("clock")}${esc(tx(B("Recent batches", "Đợt nhập gần đây")))}</h3>
                <div class="lrn-rows" data-coach="im-batches">${batches}</div>
            </div>`;
    },

    /* ---------------------------------------------- Import wizard (flow) */
    importwizard() {
        const w = PRACTICE.wizard;
        const steps = [
            B("Source", "Nguồn"), B("Review & match", "Soát & khớp"),
            B("Validate & fix", "Kiểm tra & sửa"), B("Commit", "Ghi nhận"),
        ].map((s, i) => `
            <div class="lrn-wstep ${i === 2 ? "cur" : i < 2 ? "done" : ""}">
                <span class="lrn-wdot">${i + 1}</span><span>${esc(tx(s))}</span>
            </div>`).join("");
        // ONE ROW IS REPAIRABLE BY TYPING, and it is the row whose cell could
        // not be read. The other one is a duplicate, which no amount of typing
        // fixes — that asymmetry is the product's, and drawing a field on both
        // would teach that every flagged row has an answer you can type.
        const errs = w.errorRows.map((r) => {
            const fix = r.fix
                ? inputRow("rep-impfix",
                           B("Overtime amount", "Số tiền tăng ca"),
                           B("Type the amount from the file",
                             "Nhập số tiền theo tệp"))
                : "";
            const matchAttr = r.fix ? ATTR_IMPMATCH : "";
            return `
            <div class="lrn-err">
                <span><span class="lrn-nm">${esc(r.name)}</span>
                    <span class="lrn-faint">${esc(r.code)}</span><br>
                    <span class="lrn-sub2">${esc(tx(r.why))}</span>
                    ${fix}</span>
                <span class="lrn-rr">
                    <button class="lrn-btn sm" ${matchAttr}>${esc(T("match"))}</button>
                    <button class="lrn-btn sm ghost">${esc(T("retry"))}</button>
                    <button class="lrn-btn sm ghost">${esc(T("skip"))}</button>
                </span>
            </div>`;
        }).join("");

        return `
            <div class="lrn-rail" data-coach="iw-steps">${steps}</div>
            <div class="lrn-panel" data-coach="iw-source">
                <h3>${ic("database")}${esc(tx(B("Source", "Nguồn")))}</h3>
                <div class="lrn-seg">
                    <button aria-pressed="true">${esc(tx(B("File upload", "Tải tệp lên")))}</button>
                    <button aria-pressed="false">${esc(tx(B("Connector", "Đầu nối")))}</button>
                </div>
                <label class="lrn-flabel">${esc(tx(B("Formula configuration", "Cấu hình công thức")))}</label>
                <select class="lrn-in"><option>${esc(RUN.config)}</option></select>
            </div>
            <div class="lrn-statpills" data-coach="iw-review">
                <span class="lrn-statpill"><b>${P(w.score)}</b>${esc(T("confidenceScore"))}</span>
                <span class="lrn-statpill"><b>${N(w.rows)}</b>${esc(tx(B("Rows loaded", "Dòng đã nạp")))}</span>
                <span class="lrn-statpill"><b>${N(w.matched)}</b>${esc(tx(B("Matched", "Đã khớp")))}</span>
                <span class="lrn-statpill"><b>${N(w.newEmployees)}</b>${esc(tx(B("New employees", "Nhân viên mới")))}</span>
                <span class="lrn-statpill warn"><b>${N(w.errors)}</b>${esc(tx(B("Need attention", "Cần xử lý")))}</span>
            </div>
            <div class="lrn-panel">
                <h3>${ic("alert-triangle")}${esc(tx(B(
                    "Resolve these before committing", "Xử lý các mục này trước khi ghi nhận")))}</h3>
                <div class="lrn-rows" data-coach="iw-fixrows">${errs}</div>
            </div>
            <div class="lrn-statpills" data-coach="iw-outcome">
                <span class="lrn-statpill"><b>${N(w.outcome.employees)}</b>${esc(tx(B("Employees created", "Nhân viên đã tạo")))}</span>
                <span class="lrn-statpill"><b>${N(w.outcome.payslips)}</b>${esc(tx(B("Payslips created", "Phiếu lương đã tạo")))}</span>
            </div>
            <div class="lrn-strip">
                <button class="lrn-btn pri" data-coach="iw-commit">${ic("check")}${esc(T("commitImport"))}</button>
                <span class="lrn-note">${esc(tx(B(
                    "Nothing is written until you press this. Fix the rows above, not the payslips afterwards.",
                    "Chưa gì được ghi cho tới khi bạn bấm nút này. Hãy sửa các dòng ở trên, đừng sửa phiếu lương về sau.")))}</span>
            </div>`;
    },

    /* --------------------------------------------------- Formula Engine
       The anchors here are the REAL Formula Studio's — fs-config, fs-components,
       fs-formula, fs-namesletters, fs-deps, fs-preview, fs-simulate. pb_learn
       adds NOTHING to studio.xml: those attributes have been in that template
       since before this module existed, and the registry now owns the seven the
       content names, so a rename over there breaks a build here. */
    formula() {
        const c = PRACTICE.config;
        const cfgName = c.code + DOT + c.version;
        const comps = c.components.map((k) => `
            <div class="lrn-row ${k.code === c.selected ? "on" : ""}">
                <span class="lrn-avatar">${esc(k.l)}</span>
                <span><span class="lrn-nm">${esc(k.code)}</span><br>
                    <span class="lrn-sub2">${esc(tx(k.label))}</span></span>
                <span class="lrn-rr">${k.value === undefined ? ""
                    : `<b class="lrn-money">${P(k.value)}</b>`}
                    <span class="lrn-chip ${CHIP_TONE[k.kind]}"
                        >${esc(tx(KIND_LABEL[k.kind]))}</span></span>
            </div>`).join("");

        const formula = c.formula.map((line) => `
            <div class="lrn-strip">${line.map((tok) =>
                `<span class="lrn-chip ${CHIP_TONE[tok.k]}">${esc(tok.t)}</span>`).join("")}</div>`
        ).join("");

        const preview = c.preview.map((r) => `
            <div class="lrn-cr ${r.tot ? "tot" : ""}"><span>${esc(r.code)}</span>
                <b>${r.neg ? "−" : ""}${esc(M(r.v))}</b></div>`).join("");
        const previewFor = CASE.emp.mai.name + DOT + tx(RUN.period);
        const dependsOn = c.dependsOn.join(DOT);
        const usedBy = c.usedBy.join(DOT);

        return `
            <div class="lrn-strip">
                <button class="lrn-btn" data-coach="fs-config">${ic("grid")}${esc(cfgName)}</button>
                <button class="lrn-btn ghost" data-coach="fs-simulate">${ic("bar-chart")}${
                    esc(tx(B("Simulate", "Mô phỏng")))}</button>
            </div>
            <div class="lrn-grid g3 top">
                <div class="lrn-panel" data-coach="fs-components">
                    <h3>${ic("layers")}${esc(tx(B("Components", "Thành phần")))}</h3>
                    <div class="lrn-rows">${comps}</div>
                </div>
                <div class="lrn-panel" data-coach="fs-formula">
                    <h3>${ic("calculator")}${esc(c.selected)}</h3>
                    <div class="lrn-seg" data-coach="fs-namesletters">
                        <button aria-pressed="true">${esc(tx(B("Names", "Tên")))}</button>
                        <button aria-pressed="false">${esc(tx(B("Letters", "Chữ cái")))}</button>
                    </div>
                    ${formula}
                    <div class="lrn-kv2" data-coach="fs-deps">
                        <span>${esc(tx(B("Depends on", "Phụ thuộc vào")))}</span>
                        <b>${esc(dependsOn)}</b>
                    </div>
                    <div class="lrn-kv2">
                        <span>${esc(tx(B("Used by", "Được dùng bởi")))}</span>
                        <b>${esc(usedBy)}</b>
                    </div>
                </div>
                <div class="lrn-panel" data-coach="fs-preview">
                    <h3>${ic("eye")}${esc(tx(B("Live preview", "Xem trước trực tiếp")))}</h3>
                    <p class="lrn-note">${esc(previewFor)}</p>
                    <div class="lrn-calc">${preview}</div>
                </div>
            </div>`;
    },

    /* -------------------------------------------------- Salary Structures */
    structures() {
        const k = PRACTICE.structures.kpis;
        const rows = PRACTICE.structures.rows.map((s) => {
            const meta = N(s.rules) + SP + tx(B("rules", "quy tắc")) + DOT
                + N(s.employees) + SP + T("employees");
            return `
            <div class="lrn-row">
                <span class="lrn-avatar">${ic("layers")}</span>
                <span><span class="lrn-nm">${esc(s.name)}
                        <span class="lrn-faint">${esc(s.code)}</span></span><br>
                    <span class="lrn-sub2">${esc(meta)}</span></span>
                <span class="lrn-rr"><span class="lrn-chip">${esc(tx(s.badge))}</span>
                    <span class="lrn-sub2">${esc(s.updated)}</span></span>
            </div>`;
        }).join("");

        return `
            <div class="lrn-grid g5" data-coach="sr-kpis">
                ${kpiTile("layers", "", N(k.structures), B("Structures", "Cấu trúc"))}
                ${kpiTile("list-checks", "", N(k.rules), B("Salary rules", "Quy tắc lương"))}
                ${kpiTile("grid", "", N(k.categories), B("Categories", "Nhóm quy tắc"))}
                ${kpiTile("users", "", N(k.employees), B("Employees covered", "Nhân viên áp dụng"))}
                ${kpiTile("globe", "", N(k.countries), B("Countries", "Quốc gia"))}
            </div>
            <div class="lrn-strip">
                <button class="lrn-btn pri" data-coach="sr-new">${ic("plus")}${
                    esc(tx(B("New structure", "Cấu trúc mới")))}</button>
            </div>
            <div class="lrn-tabs" data-coach="sr-filters">
                ${[B("All", "Tất cả"), B("Active", "Đang dùng"), B("Historical", "Lịch sử")].map(
                    (f, i) => `<button aria-selected="${i === 0}">${esc(tx(f))}</button>`).join("")}
            </div>
            <div class="lrn-panel">
                <h3>${ic("layers")}${esc(tx(B(
                    "Salary structures (legacy)", "Cấu trúc lương (thế hệ cũ)")))}</h3>
                <div class="lrn-rows" data-coach="sr-roster">${rows}</div>
                <div class="lrn-foot2">
                    <button class="lrn-link" data-coach="sr-openall">${esc(T("openFullList"))}</button>
                </div>
                <p class="lrn-note">${esc(tx(B(
                    "Old payslips still reference these rule sets. New pay logic belongs in a formula configuration.",
                    "Phiếu lương cũ vẫn tham chiếu các bộ quy tắc này. Logic lương mới thuộc về cấu hình công thức.")))}</p>
            </div>`;
    },

    /* ---------------------------------------------------------- Statutory
       `rep-slipline` on the right exists ONLY here, and that is deliberate: the
       product's statutory cockpit shows RATES and a payslip shows ĐỒNG, and no
       single product screen shows both at once. L6's trace needs both ends in
       one DOM — spotlight.js draws nothing when either anchor is absent — so the
       far end is drawn here and registered as practice-only, which is what stops
       the Coach ever claiming to point at it on a live screen. Its rows are
       CASE, the same ones the payslips replica draws. */
    statutory() {
        const s = PRACTICE.statutory;
        const rates = POLICY.rows.map((r) => {
            const cap = tx(B("Ceiling", "Trần đóng")) + SP + M(r.ceiling);
            return `
            <div class="lrn-row">
                <span><span class="lrn-nm">${esc(tx(r.label))}</span><br>
                    <span class="lrn-sub2">${esc(cap)}</span></span>
                <span class="lrn-rr"><span class="lrn-chip b">${P(r.employee)}</span>
                    <span class="lrn-chip">${P(r.employer)}</span></span>
            </div>`;
        }).join("");
        const totals = P(POLICY.totalEmployee) + SLASH + P(POLICY.totalEmployer);

        const slabs = TAX.slabs.map((b) => {
            const band = b.to
                ? M(b.from) + DASH + M(b.to)
                : tx(B("above", "trên")) + SP + M(b.from);
            return `<div class="lrn-cr"><span>${esc(band)}</span><b>${P(b.rate)}</b></div>`;
        }).join("");
        const relief = tx(B("Personal relief", "Giảm trừ bản thân")) + SP
            + M(TAX.personalDeduction) + DOT
            + tx(B("per dependant", "mỗi người phụ thuộc")) + SP + M(TAX.dependentDeduction);

        const roster = PRACTICE.policies.map((p) => {
            const dates = tx(B("Effective", "Hiệu lực")) + SP + p.effective
                + (p.end ? ARROW + p.end : "");
            const legs = P(p.employee) + SLASH + P(p.employer);
            return `
            <div class="lrn-row">
                <span class="lrn-avatar">${ic("shield-check")}</span>
                <span><span class="lrn-nm">${esc(tx(p.name))}
                        <span class="lrn-faint">${esc(p.code)}</span></span><br>
                    <span class="lrn-sub2">${esc(dates)}</span></span>
                <span class="lrn-rr"><span class="lrn-chip ${p.active ? "ok" : ""}"
                    >${esc(tx(p.active ? B("Active", "Đang hiệu lực")
                                       : B("Archived", "Đã lưu trữ")))}</span>
                    <span class="lrn-sub2">${esc(legs)}</span></span>
            </div>`;
        }).join("");

        /* The worked example's statutory lines only — the far end of the trace. */
        const slip = CASE.slip.filter((t) => t.neg).map((t) => `
            <div class="lrn-cr"><span>${esc(tx(t.k))}</span>
                <b>−${esc(M(t.v))}</b></div>`).join("");
        const slipFor = CASE.emp.mai.name + DOT + tx(RUN.period) + DOT
            + tx(B("registered base", "mức đóng đã đăng ký")) + SP + M(CASE.emp.mai.base);
        const effective = tx(B("Effective from", "Hiệu lực từ")) + SP + POLICY.effective;

        return `
            <div class="lrn-grid g6" data-coach="st-kpis">
                ${kpiTile("receipt", "", M(s.contributions), B("Contributions", "Tổng đóng bảo hiểm"))}
                ${kpiTile("users", "", M(s.employeeLeg), B("Employee leg", "Phần người lao động"))}
                ${kpiTile("bar-chart", "", M(s.employerLeg), B("Employer leg", "Phần doanh nghiệp"))}
                ${kpiTile("shield-check", "pos", N(PRACTICE.policies.length), B("Policies", "Chính sách"))}
                ${kpiTile("pie", "", N(s.taxTables), B("Tax tables", "Biểu thuế"))}
                ${kpiTile("user-plus", "", N(s.dependents), B("Dependents", "Người phụ thuộc"))}
            </div>
            <div class="lrn-strip">
                <button class="lrn-btn pri" data-coach="st-new">${ic("plus")}${
                    esc(tx(B("Insurance policy", "Chính sách bảo hiểm")))}</button>
            </div>
            <div class="lrn-grid g2 top">
                <div class="lrn-panel" data-coach="st-rates">
                    <h3>${ic("shield-check")}${esc(tx(B(
                        "Active insurance rates", "Tỷ lệ bảo hiểm đang hiệu lực")))}</h3>
                    <div class="lrn-strip" data-coach="st-effective">
                        <span class="lrn-chip">${ic("clock")}${esc(effective)}</span>
                        <span class="lrn-chip">${esc(POLICY.code)}</span>
                    </div>
                    <div class="lrn-kv2">
                        <span>${esc(tx(B("Scheme", "Loại bảo hiểm")))}</span>
                        <b>${esc(tx(B("Employee / Employer",
                                      "Người lao động / Doanh nghiệp")))}</b>
                    </div>
                    <div class="lrn-rows">${rates}</div>
                    <div class="lrn-kv2">
                        <span>${esc(tx(B("Total", "Tổng cộng")))}</span><b>${esc(totals)}</b>
                    </div>
                </div>
                <div class="lrn-panel" data-coach="rep-slipline">
                    <h3>${ic("receipt")}${esc(tx(B(
                        "What those rates deduct", "Các tỷ lệ đó khấu trừ bao nhiêu")))}</h3>
                    <p class="lrn-note">${esc(slipFor)}</p>
                    <div class="lrn-calc">${slip}</div>
                </div>
            </div>
            <div class="lrn-panel" data-coach="st-slabs">
                <h3>${ic("pie")}${esc(tx(B(
                    "Tax brackets (progressive)", "Biểu thuế TNCN (luỹ tiến)")))}</h3>
                <div class="lrn-calc">${slabs}</div>
                <p class="lrn-note">${esc(relief)}</p>
            </div>
            <div class="lrn-tabs" data-coach="st-filters">
                ${[B("Insurance policies", "Chính sách bảo hiểm"), B("Tax tables", "Biểu thuế"),
                   B("Active only", "Chỉ đang hiệu lực")].map(
                    (f, i) => `<button aria-selected="${i === 0}">${esc(tx(f))}</button>`).join("")}
            </div>
            <div class="lrn-panel">
                <h3>${ic("clock")}${esc(tx(B("Policy history", "Lịch sử chính sách")))}</h3>
                <div class="lrn-rows" data-coach="st-roster">${roster}</div>
                <p class="lrn-note">${esc(tx(B(
                    "A rate change is a new record with its own code and effective date, and the outgoing one is end-dated. The policy in force is the active one with the latest effective date.",
                    "Đổi tỷ lệ là tạo bản ghi mới với mã và ngày hiệu lực riêng, còn bản cũ được đặt ngày kết thúc. Chính sách đang hiệu lực là bản còn bật có ngày hiệu lực mới nhất.")))}</p>
            </div>`;
    },

    /* ------------------------------------------------------- Integrations */
    integrations() {
        const k = PRACTICE.integrationKpis;
        const rows = PRACTICE.connectors.map((c) => {
            const meta = tx(c.type) + DOT + tx(c.last);
            const counts = N(c.mappings) + SP + tx(B("mappings", "ánh xạ")) + DOT
                + N(c.staged) + SP + tx(B("staged", "đang chờ"));
            return `
            <div class="lrn-row ${c.status === "err" ? "hit" : ""}">
                <span class="lrn-avatar">${ic(c.icon)}</span>
                <span><span class="lrn-nm">${esc(tx(c.name))}</span><br>
                    <span class="lrn-sub2">${esc(meta)}</span></span>
                <span class="lrn-rr"><span class="lrn-sub2">${esc(counts)}</span>
                    <span class="lrn-chip ${c.status === "err" ? "danger" : "ok"}"
                        >${esc(tx(c.status === "err" ? B("Sync failed", "Đồng bộ lỗi")
                                                     : B("Connected", "Đã kết nối")))}</span></span>
            </div>`;
        }).join("");

        return `
            <div class="lrn-grid g6" data-coach="ig-kpis">
                ${kpiTile("plug", "", N(k.connectors), B("Connectors", "Đầu nối"))}
                ${kpiTile("check-circle", "pos", N(k.connected), B("Connected", "Đã kết nối"))}
                ${kpiTile("alert-triangle", "warn", N(k.errors), B("Errors", "Lỗi"))}
                ${kpiTile("rotate-ccw", "", N(k.synced), B("Synced records", "Bản ghi đã đồng bộ"))}
                ${kpiTile("git-branch", "", N(k.mappings), B("Field mappings", "Ánh xạ trường"))}
                ${kpiTile("inbox", "warn", N(k.staged), B("Staged records", "Bản ghi đang chờ"))}
            </div>
            <div class="lrn-strip">
                <button class="lrn-btn pri" data-coach="ig-connect">${ic("plug")}${
                    esc(tx(B("Connect a system", "Kết nối một hệ thống")))}</button>
            </div>
            <div class="lrn-tabs" data-coach="ig-filters">
                ${[B("All", "Tất cả"), B("Connected", "Đã kết nối"), B("Errors", "Lỗi")].map(
                    (f, i) => `<button aria-selected="${i === 0}">${esc(tx(f))}</button>`).join("")}
            </div>
            <div class="lrn-panel">
                <h3>${ic("plug")}${esc(tx(B("Connectors", "Đầu nối")))}</h3>
                <div class="lrn-rows" data-coach="ig-roster">${rows}</div>
                <p class="lrn-note">${esc(tx(B(
                    "Read the last sync time, not just the status. A connector that stopped nine days ago still says connected.",
                    "Hãy đọc thời điểm đồng bộ gần nhất, đừng chỉ đọc trạng thái. Một đầu nối ngừng chạy chín ngày trước vẫn hiện là đã kết nối.")))}</p>
            </div>`;
    },

    /* ------------------------------------------- the three shared ledgers
       ONE renderer, three screens — mirroring pb_payrun_ledgers, which really
       does serve all three from one template. Giving each its own renderer here
       would teach three screens that the product treats as one. */
    fullfinal() {
        return ledgerHTML("fullfinal");
    },

    proration() {
        return ledgerHTML("proration");
    },

    retro() {
        return ledgerHTML("retro");
    },
};

/* ---------------------------------------------------------------------- shell
   `visible` is the set of station keys the LEARNER's own sidebar shows — it
   comes from the server, which computes it by calling the real sidebar. So the
   replica's menu is not a guess about the group gate; it is the group gate. */
export function shellHTML(screen, opts) {
    const o = opts || {};
    const visible = o.visible || new Set();
    CURRENT_SCREEN = screen;

    const owner = ownerSection(screen);
    const leaf = ownerLeaf(screen);
    const secs = MENU.map((sec) => {
        const items = sec.items.map((it) => {
            // `free` is practice mode: every section is in scope, because the
            // whole point of the sandbox is that a learner opens whatever they
            // are curious about. A lesson keeps one section lit, so that a step
            // about the pay-run desk does not read as an invitation to wander.
            const inScope = !!o.free || sec === owner;
            const seen = !inScope || visible.has(it.id);
            // During a guided lesson the full menu stays legible: a learner who
            // cannot open a screen is exactly the person who needs to read what
            // it is before asking for access.
            const off = !inScope || (!seen && !o.guided);
            const on = it.id === leaf;
            return `<button class="lrn-item ${on ? "on" : ""}${SP}${off ? "off" : ""}" data-nav="${esc(it.id)}"
                ${off ? 'tabindex="-1" aria-disabled="true"' : ""}>${ic(it.icon)}
                <span>${esc(tx(it.label))}</span></button>`;
        }).join("");
        return `<div class="lrn-sec">${esc(tx(sec.label))}</div>${items}`;
    }).join("");

    const body = SCREENS[screen] ? SCREENS[screen]() : "";
    const gated = owner.items.find((i) => i.id === leaf);
    const blocked = gated && !visible.has(leaf) && !o.guided;

    return `
    <div class="lrn-shell">
        <aside class="lrn-sb" data-coach="rep-nav" aria-label="Payobook navigation">
            <div class="lrn-brand"><span class="lrn-mark">${ic("zap")}</span><span>Payobook</span></div>
            <div class="lrn-catch"><b>Hoa Sen Retail Co.</b>${esc(tx(B("Vietnam", "Việt Nam")))}</div>
            ${secs}
            <div class="lrn-foot">${esc(tx(B("Practice data · not your company", "Dữ liệu thực hành · không phải công ty của bạn")))}</div>
        </aside>
        <div class="lrn-main">
            <div class="lrn-pbanner" data-coach="rep-banner">${ic("shield-check")}<span>${esc(T("practiceBanner"))}</span></div>
            <div class="lrn-mhead">
                <h2>${esc(screenTitle(screen))}</h2>
                <span class="lrn-sub">${esc(tx(B("Practice company — demo data", "Công ty thực hành — dữ liệu mô phỏng")))}</span>
            </div>
            <div class="lrn-screen">${blocked ? blockedHTML() : body}</div>
        </div>
    </div>`;
}

function blockedHTML() {
    return `<div class="lrn-panel lrn-blocked">
        <h3>${ic("lock")}${esc(T("notVisible"))}</h3>
        <p class="lrn-note">${esc(T("notVisibleBody"))}</p>
        <p class="lrn-note">${esc(tx(B(
            "You can still read what this screen does, and what it would take to be given access.",
            "Bạn vẫn có thể đọc màn hình này làm gì, và cần gì để được cấp quyền truy cập.")))}</p>
    </div>`;
}

/* ------------------------------------------------------- the practice view
   LEARNOS Phase 5. The free-roam sandbox's builder, and it is the LAST thing
   in this file on purpose: `tests/test_practice.py` reads from its `export`
   line to the end of the file and asserts that the body contains no branch of
   any kind. That is what "unconditional" means here — not "we always pass the
   flag", but "there is no flag, and no expression that could evaluate to no
   watermark". A state that hides the mark cannot be written, because there is
   nothing in this function for a state to reach.

   Everything else about the view is deliberately the ordinary shell: the same
   replica, the same anchors, the same twenty screens a lesson stands on. Only
   the menu is different (`free`), because a sandbox whose menu is greyed out
   is a sandbox with one screen in it. */
export function practiceShellHTML(screen, visible) {
    const mark = `<div class="lrn-watermark" data-coach="rep-watermark">${
        ic("shield-check")}<span>${esc(T("practiceWatermark"))}</span></div>`;
    return mark + shellHTML(screen, { guided: true, free: true, visible: visible });
}
