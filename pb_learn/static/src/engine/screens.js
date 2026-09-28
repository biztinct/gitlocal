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
import { B, CASE, FNB, INPUT_ANCHORS, MENU, POLICY, PRACTICE, ROUTE, RUN, STATUS_LABELS,
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
/* People › Employees has a Contracts button that opens every contract
   (commit c9e5f2ee4); in the sandbox it opens the Contracts replica. */
const ATTR_CONTRACTS = 'data-nav="contracts"';

/* A formula configuration's stages (pb_hr_payroll_formula formula_config.py
   :529-535), in the order the Studio's main button moves it. */
const STAGE = {
    draft: B("Draft", "Nháp"),
    testing: B("Testing", "Đang thử nghiệm"),
    validated: B("Validated", "Đã xác thực"),
    active: B("Active", "Đang hoạt động"),
};

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


/* --------------------------------------------------------------- row renderers
   These read PRACTICE and CASE, never their own literals — which is what makes
   the fixture the single place to edit when the product changes. */
function kpiTile(icon, tone, value, label) {
    return `<div class="lrn-kpi ${tone}">
        <div class="lrn-kt">${ic(icon)}<span>${esc(tx(label))}</span></div>
        <div class="lrn-kv">${esc(value)}</div>
    </div>`;
}

/* A KPI tile with the product's second line under the figure (Home › Pulse
   prints "48 active contracts", "personnel cost in July 2026" …). */
function kpiTile2(icon, tone, value, label, sub) {
    return `<div class="lrn-kpi ${tone}">
        <div class="lrn-kt">${ic(icon)}<span>${esc(tx(label))}</span></div>
        <div class="lrn-kv">${esc(value)}</div>
        <div class="lrn-ksub">${esc(sub)}</div>
    </div>`;
}

/* The numbered step buttons the Runs, Payslips and Import lenses share
   (pb_import_kit's "numbered steps"): 01 Draft · 02 Waiting for approval …,
   each with its count and an optional amber flag. */
function stepButtons(steps, noun) {
    return steps.map((s, i) => {
        const num = String(i + 1).padStart(2, "0");
        const count = N(s.count) + SP + tx(noun);
        return `<button class="lrn-stepbtn ${s.on ? "on" : ""}" aria-pressed="${!!s.on}">
            <span class="lrn-stepnum">${num}</span>
            <span class="lrn-steplab">${esc(tx(s.label))}</span>
            <span class="lrn-stepcount">${esc(count)}</span>
            ${s.flag ? `<span class="lrn-stepflag">${ic("alert-triangle")}${esc(tx(s.flag))}</span>` : ""}
        </button>`;
    }).join("");
}

/* One pay run on the Runs board, drawn as payruns.xml draws it
   (pb_payruns/static/src/xml/payruns.xml:86-151): name, stats, division, the
   route line while it waits, the sent-back note when it came back, and ONLY the
   actions its state offers. */
function runCard(row) {
    const stats = [
        [B("Employees", "Nhân viên"), N(row.employees)],
        [B("Gross", "Tổng thu nhập"), M(row.gross)],
        [B("Net", "Thực nhận"), M(row.net)],
    ].map(([k, v]) => `<span><i>${esc(tx(k))}</i><b>${esc(v)}</b></span>`).join("");
    const step = row.col === "approval_pending" ? ROUTE.steps[row.step] : null;
    const route = step
        ? `<div class="lrn-kroute" data-coach="pk-route">${ic("git-branch")}<span><b>${
            esc(tx(step.title))}</b>${SP}·${SP}${esc(tx(B("With", "Đang ở")))}${SP}${esc(step.who)}</span></div>`
        : "";
    const back = row.sentBack
        ? `<div class="lrn-kback">${ic("undo")}<span><b>${esc(tx(B("Sent back by", "Trả lại bởi")))}${
            SP}${esc(row.sentBack.by)}</b>${SP}— ${esc(tx(row.sentBack.note))}</span></div>`
        : "";
    let acts = "";
    if (row.col === "done") {
        acts = [B("Pay & Deliver", "Chi trả & gửi phiếu"), B("Report", "Báo cáo"), B("Excel", "Excel"),
                B("Journals", "Bút toán"), B("Payments", "Thanh toán")]
            .map((a) => `<button class="lrn-btn sm ghost">${esc(tx(a))}</button>`).join("");
    } else if (row.col === "draft") {
        acts = `<button class="lrn-btn sm pri">${ic("send")}${esc(T("submitReview"))}</button>
                <button class="lrn-btn sm ghost danger">${esc(T("reject"))}</button>`;
    } else if (step && step.you) {
        acts = `<button class="lrn-btn sm pri">${ic("inbox")}${esc(tx(B("Open the approval", "Mở phê duyệt")))}</button>
                <button class="lrn-btn sm ghost danger">${esc(T("reject"))}</button>`;
    }
    return `<div class="lrn-kcard" data-coach="pk-card">
        <b>${esc(tx(row.name))}</b>
        <div class="lrn-kstats">${stats}</div>
        <span class="lrn-chip">${esc(tx(row.division))}</span>
        ${route}${back}
        <div class="lrn-kacts" data-coach="pk-card-actions">${acts}</div>
    </div>`;
}

/* The route dots on a request card, exactly as the inbox draws them: done ·
   current · next, joined by a line (pb_approval_config inbox.xml:175-181). */
const RLINE = '<span class="lrn-rline"></span>';
function routeDots(steps, at) {
    return steps.map((s, i) => {
        const cls = i < at ? "done" : i === at ? "current" : "next";
        const title = tx(s.title || s);
        const joint = i ? RLINE : "";
        const tick = i < at ? ic("check") : "";
        return `${joint}<span class="lrn-rdot ${cls}" title="${esc(title)}">${tick}<span>${esc(title)}</span></span>`;
    }).join("");
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
    /* ------------------------------------------------------ Home › Pulse
       LEARN REFRESH step 2. Drawn as pb_dashboard.xml draws it INSIDE the Home
       hub (embedded: no company line): the greeting and the live run, "Figures
       for {month}" over the month strip, the four tiles with their own second
       lines, and the three cards. The anchors are the product's own
       (dash-hero, dash-runpayroll, dash-period, dash-kpis, dash-formula). The
       first-payroll checklist is not drawn: the product shows it only while a
       company has NO pay run, and this one has five. */
    dashboard() {
        const p = PRACTICE.pulse;
        const k = p.kpis;
        const l = p.latest;
        const heroSub = tx(l.name) + DOT + N(l.done) + SLASH + N(l.slips) + SP
            + tx(B("payslips done", "phiếu lương đã xong")) + DOT + N(k.pending) + SP
            + tx(B("awaiting approval", "đang chờ phê duyệt"));
        const busiest = Math.max(...p.months.map((m) => m.people));
        const months = p.months.map((m) => {
            const h = Math.round(m.people / busiest * 100);
            const people = N(m.people) + SP + tx(B("people", "người"));
            return `<button class="lrn-mchip ${m.latest ? "on" : ""}" aria-pressed="${!!m.latest}">
                <span class="lrn-mbar"><i style="height:${h}%"></i></span>
                <b>${esc(tx(m.m))}</b><span>${esc(m.y)}</span>
                <span class="lrn-mcount">${esc(people)}</span>
            </button>`;
        }).join("");
        const f = PRACTICE.configs;
        const figure = (label, value) => `<div class="lrn-kv2"><span>${esc(tx(label))}</span><b>${esc(value)}</b></div>`;
        return `
            <div class="lrn-herocta" data-coach="dash-hero">
                ${ic("zap")}
                <span><b>${esc(tx(B("Good afternoon", "Chào buổi chiều")))},${SP}${esc(p.user)}</b><br>
                    <span class="lrn-sub2">${esc(heroSub)}</span></span>
                <button class="lrn-btn pri" data-coach="dash-runpayroll">${ic("zap")}${
                    esc(tx(B("Run Payroll", "Chạy bảng lương")))}</button>
                <button class="lrn-btn ghost">${ic("bar-chart")}${esc(tx(B("Analytics", "Phân tích")))}</button>
            </div>
            <div class="lrn-period" data-coach="dash-period">
                <div class="lrn-periodline">${ic("calendar")}<b>${esc(tx(B("Figures for", "Số liệu của")))}${
                    SP}${esc(tx(p.month))}</b>
                    <span class="lrn-chip">${esc(tx(B("the latest payroll month", "tháng lương gần nhất")))}</span></div>
                <div class="lrn-months">${months}</div>
                <p class="lrn-note">${esc(tx(B(
                    "Press a month to read the figures above for it.",
                    "Bấm vào một tháng để đọc các số liệu phía trên cho tháng đó.")))}</p>
            </div>
            <div class="lrn-grid g4" data-coach="dash-kpis">
                ${kpiTile2("users", "", N(k.headcount), B("Headcount", "Số lượng nhân sự"),
                    N(k.contracts) + SP + tx(B("active contracts", "hợp đồng đang hiệu lực")))}
                ${kpiTile2("trending-up", "pos", M(k.payroll), B("Monthly payroll", "Chi phí lương tháng"),
                    tx(B("personnel cost in", "chi phí nhân sự")) + SP + tx(p.month))}
                ${kpiTile2("clipboard-check", "warn", N(k.pending), B("Pending approval", "Đang chờ phê duyệt"),
                    tx(B("awaiting sign-off", "đang chờ phê duyệt")))}
                ${kpiTile2("calculator", "", N(k.configs), B("Active configs", "Cấu hình đang chạy"),
                    N(k.rules) + SP + tx(B("rules", "quy tắc")))}
            </div>
            <div class="lrn-grid g3 top">
                <div class="lrn-panel">
                    <h3>${ic("calendar")}${esc(tx(B("Latest pay run", "Đợt lương mới nhất")))}</h3>
                    <p class="lrn-note">${esc(tx(l.name))}</p>
                    ${figure(B("Payslips", "Phiếu lương"), N(l.slips))}
                    ${figure(B("Approved", "Đã duyệt"), N(l.done))}
                    ${figure(B("Pending", "Đang chờ"), N(l.pending))}
                    <button class="lrn-link">${esc(tx(B("Open pay runs →", "Mở các đợt lương →")))}</button>
                </div>
                <div class="lrn-panel">
                    <h3>${ic("layers")}${esc(tx(B("Company overview", "Tổng quan công ty")))}</h3>
                    <p class="lrn-note">${esc(tx(B("All departments · monthly", "Mọi bộ phận · theo tháng")))}</p>
                    ${figure(B("Payroll", "Chi phí lương"), M(k.payroll))}
                    ${figure(B("Avg salary", "Lương bình quân"), M(Math.round(k.payroll / k.headcount)))}
                    <button class="lrn-link">${esc(tx(B("Open analytics →", "Mở phân tích →")))}</button>
                </div>
                <div class="lrn-panel" data-coach="dash-formula">
                    <h3>${ic("calculator")}${esc(tx(B("Formula engine", "Bộ máy công thức")))}</h3>
                    <p class="lrn-note">${esc(tx(B("Excel-driven configs", "Cấu hình theo kiểu Excel")))}</p>
                    ${figure(B("Rules", "Quy tắc"), N(k.rules))}
                    ${figure(B("Configs", "Cấu hình"), N(f.length))}
                    <button class="lrn-link">${esc(tx(B("Open formula engine →", "Mở bộ máy công thức →")))}</button>
                </div>
            </div>`;
    },

    /* ------------------------------------------------------ Home › Approvals
       THE ONE INBOX (pb_approval_config inbox.xml), as it looks inside Home.
       The ai-* anchors are the ones step 2 added to the product template, so
       a lesson here and the helper on the live screen point at the same
       controls. The drawer is drawn OPEN on the July run: in the product it
       opens when you press a card. */
    approvals() {
        const inbox = PRACTICE.inbox;
        const req = inbox.requests;
        const mine = req[0];
        const other = req[1];
        const tabs = [
            [B("My turn", "Đến lượt tôi"), inbox.tabs.mine],
            [B("All I can see", "Tất cả tôi xem được"), inbox.tabs.all],
            [B("Sent back", "Đã trả lại"), inbox.tabs.back],
            [B("Finished", "Đã xong"), inbox.tabs.done],
        ].map(([label, n], i) => `<button aria-selected="${i === 0}">${esc(tx(label))}<span class="lrn-tabn">${N(n)}</span></button>`).join("");
        const card = (r, anchored) => {
            const steps = r.mine ? ROUTE.steps : r.route;
            const who = r.mine ? ROUTE.steps[r.at].who : r.waiting;
            const badge = r.mine
                ? `<span class="lrn-chip a">${esc(tx(B("Your turn", "Đến lượt bạn")))}</span>` : "";
            const sub = tx(r.process) + DOT + r.scope + DOT + tx(B("sent in by", "gửi bởi")) + SP + r.sentBy
                + "," + SP + tx(r.when);
            const amount = r.amount ? `<div class="lrn-reqamt">${esc(M(r.amount))}</div>
                <div class="lrn-sub2">${esc(N(r.count) + SP + tx(B("payslips", "phiếu lương")))}</div>` : "";
            const cardAnchor = anchored ? 'data-coach="ai-card"' : "";
            const routeAnchor = anchored ? 'data-coach="ai-route"' : "";
            return `<div class="lrn-req ${r.mine ? "mine" : ""}" ${cardAnchor}>
                <div class="lrn-reqmain">
                    <div class="lrn-reqt"><b>${esc(tx(r.title))}</b>${badge}</div>
                    <div class="lrn-sub2">${esc(sub)}</div>
                    <div class="lrn-reqfacts"><span class="lrn-chip">${esc(ROUTE.name)}${SP}· v1</span>
                        <span class="lrn-sub2">${esc(tx(B("Waiting for", "Đang chờ")))}${SP}${esc(who)}</span></div>
                    <div class="lrn-rt" ${routeAnchor}>${routeDots(steps, r.at)}</div>
                </div>
                <div class="lrn-reqright">${amount}
                    <div class="lrn-sub2">${esc(tx(r.kind))}</div>
                    <div class="lrn-reqdue">${esc(tx(r.due))}</div>
                </div>
            </div>`;
        };
        const facts = inbox.facts.map((x) => `<div class="lrn-cr"><span>${esc(tx(x.k))}</span>
                <b>${esc(x.money ? M(x.v) : tx(x.v))}</b></div>`).join("");
        const timeline = ROUTE.steps.map((s, i) => {
            const state = i < mine.at ? B("approved", "đã phê duyệt")
                : i === mine.at ? B("waiting — your turn", "đang chờ — đến lượt bạn") : B("next", "tiếp theo");
            return `<div class="lrn-atl ${i < mine.at ? "done" : i === mine.at ? "cur" : ""}">
                <span class="lrn-atldot"></span><b>${esc(tx(s.title))}</b>
                <span class="lrn-sub2">${esc(s.who)}${SP}·${SP}${esc(tx(state))}</span></div>`;
        }).join("");
        const moneyLine = N(inbox.tabs.mine) + SP + tx(B("waiting for you", "đang chờ bạn")) + DOT + M(mine.amount);
        return `
            <div class="lrn-strip" data-coach="ai-head">
                <button class="lrn-btn">${ic("send")}${esc(tx(B("Ask for a sign-off", "Xin một chữ ký duyệt")))}</button>
                <button class="lrn-btn ghost">${ic("git-branch")}${esc(tx(B("Workflows", "Luồng phê duyệt")))}</button>
                <button class="lrn-btn ghost">${ic("rotate-ccw")}${esc(tx(B("Refresh", "Làm mới")))}</button>
            </div>
            <div class="lrn-seg" data-coach="ai-scope">
                <button aria-pressed="true">${esc(tx(B("Mine", "Của tôi")))}</button>
                <button aria-pressed="false">${esc(tx(B("My team", "Nhóm của tôi")))}</button>
                <button aria-pressed="false">${esc(tx(B("Everyone", "Tất cả mọi người")))}</button>
            </div>
            <div class="lrn-tabs" data-coach="ai-tabs">${tabs}</div>
            <p class="lrn-note lrn-moneyline"><b>${esc(moneyLine)}</b>${SP}${esc(tx(B(
                "Amounts are never added across currencies.",
                "Số tiền không bao giờ được cộng chung giữa các loại tiền.")))}</p>
            <div class="lrn-grid g2 top">
                <div>
                    ${card(mine, true)}
                    <p class="lrn-note">${esc(tx(B(
                        "Also on All I can see — somebody else's turn:",
                        "Cũng có trong Tất cả tôi xem được — đến lượt người khác:")))}</p>
                    ${card(other, false)}
                </div>
                <div class="lrn-panel lrn-adrawer" data-coach="ai-drawer">
                    <h3>${ic("clipboard-check")}${esc(tx(mine.title))}</h3>
                    <p class="lrn-note">${esc(tx(mine.process) + DOT + ROUTE.name)}</p>
                    <h4>${esc(tx(B("The facts, as they were when it was sent in",
                                  "Các dữ kiện, đúng như lúc được gửi")))}</h4>
                    <div class="lrn-calc" data-coach="ai-facts">${facts}</div>
                    <h4>${esc(tx(B("The route", "Lộ trình")))}</h4>
                    <div class="lrn-atlwrap">${timeline}</div>
                    <div class="lrn-decide" data-coach="ai-decide">
                        <button class="lrn-btn ghost danger" data-coach="ai-turndown">${ic("x")}${esc(tx(B("Turn it down", "Từ chối")))}</button>
                        <button class="lrn-btn ghost" data-coach="ai-sendback">${ic("undo")}${esc(tx(B("Send it back", "Trả lại")))}</button>
                        <button class="lrn-btn pri" data-coach="ai-approve">${ic("check")}${esc(tx(B("Approve", "Phê duyệt")))}</button>
                    </div>
                    <div class="lrn-decide2">
                        <button class="lrn-btn sm ghost" data-coach="ai-move">${ic("users")}${esc(tx(B("Move it to somebody else", "Chuyển cho người khác")))}</button>
                        <button class="lrn-btn sm ghost" data-coach="ai-withdraw">${ic("rotate-ccw")}${esc(tx(B("Withdraw it", "Thu hồi")))}</button>
                    </div>
                    <p class="lrn-note">${esc(tx(B(
                        "Move it to somebody else shows only for whoever looks after this workflow, and Withdraw it only for the person who sent it in. They are drawn here so you know they exist.",
                        "Nút Chuyển cho người khác chỉ hiện với người phụ trách luồng phê duyệt này, còn nút Thu hồi chỉ hiện với người đã gửi. Chúng được vẽ ở đây để bạn biết chúng tồn tại.")))}</p>
                    <p class="lrn-note">${esc(tx(B(
                        "Approving records your name, the time, and exactly the facts above as they were when this was sent in.",
                        "Phê duyệt sẽ ghi lại tên bạn, thời điểm, và đúng các dữ kiện ở trên như lúc yêu cầu được gửi.")))}</p>
                </div>
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
                <button class="lrn-btn" ${ATTR_CONTRACTS}>${ic("file-text")}${
                    esc(tx(B("Contracts", "Hợp đồng")))}</button>
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

    /* ------------------------------------------------------- Pay Run › Run
       LEARN REFRESH step 2. The scheme-first run (pb_payrun_wizard). The
       product shows ONE step at a time; the replica lays all four out in rail
       order so a lesson can walk them without pretending to compute — every
       section carries the product's own anchor, and the rail says which step
       each one belongs to. Retail's scheme reads a spreadsheet, so the rail
       has four steps; a scheme that does not has three. */
    runpayroll() {
        const pd = PRACTICE.payData;
        const steps = [
            B("Select period", "Chọn kỳ lương"), B("Pay data", "Dữ liệu lương"),
            B("Compute", "Tính lương"), B("Review exceptions", "Soát ngoại lệ"),
        ].map((s, i) => `
            <div class="lrn-wstep ${i === 3 ? "cur" : "done"}">
                <span class="lrn-wdot">${i < 3 ? ic("check") : i + 1}</span><span>${esc(tx(s))}</span>
            </div>`).join("");
        const groups = PRACTICE.schemeGroups.map((g) => {
            const cards = PRACTICE.configs.filter((c) => c.kind === g.kind).map((c) => {
                const meta = N(c.covered) + SP + tx(B("people covered", "người được áp dụng")) + DOT
                    + tx(B("last run", "đợt gần nhất")) + SP + tx(c.last);
                return `<button class="lrn-scard ${c.name === RUN.scheme ? "on" : ""}"
                    aria-pressed="${c.name === RUN.scheme}"><b>${esc(c.name)}</b>
                    <span class="lrn-sub2">${esc(meta)}</span></button>`;
            }).join("");
            return cards ? `<div class="lrn-sgroup"><span class="lrn-sglab">${esc(tx(g.label))}</span>
                <div class="lrn-scards">${cards}</div></div>` : "";
        }).join("");
        const fed = pd.fed.map((c) => `<span class="lrn-chip ok">${ic("check")}${esc(tx(c))}</span>`).join("");
        const coverage = N(pd.fed.length) + SP + tx(B("of", "trên")) + SP + N(pd.fed.length) + SP
            + tx(B("spreadsheet components are fed by this file", "thành phần bảng tính được lấy từ tệp này"))
            + SP + "(" + N(pd.columns) + SP + tx(B("columns read", "cột đã đọc")) + ")";
        const computed = tx(B("Computed", "Đã tính")) + SP + N(RUN.employees) + SP + tx(B("of", "trên")) + SP
            + N(RUN.employees) + SP + tx(B("payslips", "phiếu lương"));
        const netLine = tx(RUN.name) + DOT + tx(B("net total", "tổng thực nhận")) + SP + M(RUN.totalNet);
        const missingHead = N(pd.missing.length) + SP + tx(B(
            "person in the file is not in Payobook yet — they were listed, not paid",
            "người trong tệp chưa có trong Payobook — họ được liệt kê, không được trả lương"));
        const missing = pd.missing.map((n) => `<span class="lrn-chip">${esc(n)}</span>`).join("");
        return `
            <div class="lrn-rail" data-coach="pw-rail">${steps}</div>
            <div class="lrn-panel" data-coach="pw-scheme">
                <h3>${ic("layers")}${esc(tx(B("Pay run for", "Đợt lương cho")))}</h3>
                ${groups}
            </div>
            <div class="lrn-grid g2 top" data-coach="pw-scope">
                <div class="lrn-panel">
                    <h3>${ic("calendar")}${esc(tx(B("Period", "Kỳ lương")))}</h3>
                    <label class="lrn-flabel">${esc(tx(B("Batch name", "Tên đợt")))}</label>
                    <input class="lrn-in" value="${esc(tx(RUN.name))}" readonly="readonly"/>
                    <div class="lrn-kv2"><span>${esc(tx(B("From", "Từ")))}</span><b>${esc(RUN.from)}</b></div>
                    <div class="lrn-kv2"><span>${esc(tx(B("To", "Đến")))}</span><b>${esc(RUN.to)}</b></div>
                </div>
                <div class="lrn-panel" data-coach="pw-summary">
                    <h3>${ic("target")}${esc(tx(B("Scope", "Phạm vi")))}</h3>
                    <div class="lrn-kv2"><span>${esc(tx(B("Company", "Công ty")))}</span><b>Hoa Sen Retail Co.</b></div>
                    <div class="lrn-kv2"><span>${esc(tx(B("Currency", "Tiền tệ")))}</span><b>VND${SP}·${SP}₫</b></div>
                    <div class="lrn-kv2"><span>${esc(tx(B("Payroll scheme", "Chương trình lương")))}</span><b>${esc(RUN.scheme)}</b></div>
                    <p class="lrn-note">${esc(tx(B(
                        "A draft run will be created and computed — fully reversible. Only the people this scheme pays are affected.",
                        "Một đợt nháp sẽ được tạo và tính — hoàn toàn có thể hoàn tác. Chỉ những người thuộc chương trình lương này bị ảnh hưởng.")))}</p>
                    <button class="lrn-btn pri" data-coach="pw-compute">${ic("play")}${
                        esc(tx(B("Add pay data", "Thêm dữ liệu lương")))}</button>
                </div>
            </div>
            <div class="lrn-grid g2 top">
                <div class="lrn-panel" data-coach="pw-paydata">
                    <h3>${ic("upload")}${esc(tx(B("This month's pay data", "Dữ liệu lương tháng này")))}</h3>
                    <p class="lrn-note">${esc(RUN.scheme)}${SP}${esc(tx(B(
                        "reads 3 pay components from a spreadsheet. Load the file for this period.",
                        "đọc 3 thành phần lương từ một bảng tính. Hãy tải tệp của kỳ này.")))}</p>
                    <div class="lrn-file">${ic("file-text")}<b>${esc(pd.file)}</b></div>
                    <div data-coach="pw-paymode">
                        <h4>${esc(tx(B("What should these values do?", "Các giá trị này dùng để làm gì?")))}</h4>
                        <button class="lrn-choice on" aria-pressed="true"><b>${esc(tx(B("Update Payobook", "Cập nhật Payobook")))}</b>
                            <span class="lrn-sub2">${esc(tx(B(
                                "Values are saved to employee and contract records and used from now on.",
                                "Các giá trị được lưu vào hồ sơ nhân viên và hợp đồng, và được dùng từ nay về sau.")))}</span></button>
                        <button class="lrn-choice" aria-pressed="false"><b>${esc(tx(B("This run only", "Chỉ đợt này")))}</b>
                            <span class="lrn-sub2">${esc(tx(B(
                                "Used just this once. Nothing in Payobook changes — good for a one-off bonus or a correction.",
                                "Chỉ dùng một lần này. Không có gì trong Payobook thay đổi — hợp với một khoản thưởng một lần hoặc một lần sửa.")))}</span></button>
                    </div>
                    <div class="lrn-strip">
                        <button class="lrn-btn ghost" data-coach="pw-skipsheet">${esc(tx(B("Run without a spreadsheet", "Chạy không cần bảng tính")))}</button>
                        <button class="lrn-btn pri">${esc(tx(B("Continue with this file", "Tiếp tục với tệp này")))}</button>
                    </div>
                </div>
                <div class="lrn-panel" data-coach="pw-coverage">
                    <h3>${ic("check-circle")}${esc(tx(B("Coverage", "Mức bao phủ")))}</h3>
                    <p class="lrn-note">${esc(coverage)}</p>
                    <div class="lrn-strip">${fed}</div>
                </div>
            </div>
            <div class="lrn-panel" data-coach="pw-result">
                <h3>${ic("check-circle")}${esc(computed)}</h3>
                <p class="lrn-note">${esc(netLine)}</p>
                <div class="lrn-statpills" data-coach="pw-pills">
                    <span class="lrn-statpill"><b>${N(RUN.employees)}</b>${esc(tx(B("Payslips", "Phiếu lương")))}</span>
                    <span class="lrn-statpill"><b>${N(RUN.employees)}</b>${esc(tx(B("Computed", "Đã tính")))}</span>
                    <span class="lrn-statpill warn"><b>${N(RUN.needReview)}</b>${esc(T("needReview"))}</span>
                </div>
            </div>
            <div class="lrn-grid g2 top">
                <div class="lrn-panel lrn-warnpanel" data-coach="pw-missing">
                    <h3>${ic("user-plus")}${esc(missingHead)}</h3>
                    <p class="lrn-note">${esc(tx(B(
                        "Nobody is created from a pay data file. Add them first and their pay will come through on the next run.",
                        "Không ai được tạo ra từ tệp dữ liệu lương. Hãy thêm họ trước, lương của họ sẽ có ở đợt kế tiếp.")))}</p>
                    <div class="lrn-strip">${missing}</div>
                    <div class="lrn-strip">
                        <button class="lrn-btn sm">${ic("user-plus")}${esc(tx(B("Add these people", "Thêm những người này")))}</button>
                        <button class="lrn-btn sm ghost">${ic("copy")}${esc(tx(B("Copy names", "Sao chép tên")))}</button>
                    </div>
                </div>
                <div class="lrn-panel" data-coach="pw-exceptions">
                    <h3>${ic("alert-triangle")}${esc(tx(B("These items need a look before approval:",
                                                         "Các mục này cần xem trước khi phê duyệt:")))}</h3>
                    <div class="lrn-row">
                        <span class="lrn-avatar">${esc(initial(PRACTICE.exception.name))}</span>
                        <span><span class="lrn-nm">${esc(PRACTICE.exception.name)}</span><br>
                            <span class="lrn-sub2">${esc(tx(PRACTICE.exception.why))}</span></span>
                    </div>
                </div>
            </div>
            <div class="lrn-strip">
                <button class="lrn-btn pri">${esc(tx(B("Open Payroll →", "Mở bảng lương →")))}</button>
            </div>`;
    },

    /* ------------------------------------------------------ Pay Run › Runs
       The board as the Pay Run hub draws it (PbPayruns, payruns.xml): the
       numbers row, the division chips, the numbered steps, three columns, and
       the collapsed Rejected list. */
    payruns() {
        const k = PRACTICE.boardKpis;
        const b = PRACTICE.board;
        const cols = ["draft", "approval_pending", "done"];
        const count = (c) => b.filter((r) => r.col === c).length;
        const backs = b.filter((r) => r.col === "draft" && r.sentBack).length;
        const steps = stepButtons([
            { label: STATUS_LABELS.payrun.draft.l, count: count("draft"),
              flag: backs ? B(N(backs) + " sent back to be fixed", N(backs) + " bị trả lại để sửa") : null },
            { label: STATUS_LABELS.payrun.approval_pending.l, count: count("approval_pending"),
              flag: k.myPending ? B(N(k.myPending) + " waiting on you", N(k.myPending) + " đang chờ bạn") : null },
            { label: STATUS_LABELS.payrun.done.l, count: count("done") },
        ], B("pay runs", "đợt lương"));
        const board = cols.map((col) => `
            <div class="lrn-kcol">
                <div class="lrn-kcolh">${statusChip("payrun", col)}</div>
                ${b.filter((r) => r.col === col).map(runCard).join("")}
            </div>`).join("");
        const shown = b.filter((r) => r.col !== "cancel").length;
        const showing = tx(B("Showing all", "Đang hiện tất cả")) + SP + N(shown) + SP
            + tx(B("pay runs · press a step or a number to narrow it", "đợt lương · bấm một bước hoặc một con số để thu hẹp"));
        const rejected = b.filter((r) => r.col === "cancel").map((r) => `
            <div class="lrn-row">
                <span class="lrn-avatar">${ic("x")}</span>
                <span><span class="lrn-nm">${esc(tx(r.name))}</span><br>
                    <span class="lrn-sub2">${esc(tx(r.reason))}</span></span>
                <span class="lrn-rr">${statusChip("payrun", "cancel")}</span>
            </div>`).join("");
        const netLabel = tx(B("Net paid (done), in", "Đã chi (hoàn tất), bằng")) + SP + "VND";
        return `
            <div class="lrn-strip">
                <button class="lrn-btn pri" data-coach="pk-run">${ic("zap")}${esc(T("runPayroll"))}</button>
            </div>
            <div class="lrn-grid g5" data-coach="pk-kpis">
                ${kpiTile("layers", "", N(k.total), B("Pay runs", "Đợt lương"))}
                ${kpiTile("clock", "", N(k.inPipeline), B("In pipeline", "Đang xử lý"))}
                ${kpiTile("alert-triangle", "warn", N(k.myPending), B("Awaiting your approval", "Chờ bạn phê duyệt"))}
                ${kpiTile("check-circle", "pos", N(k.done), B("Completed", "Hoàn tất"))}
                ${kpiTile("receipt", "pos", M(k.net), B(netLabel, netLabel))}
            </div>
            <div class="lrn-tabs" data-coach="pk-divchips">
                ${[B("All divisions", "Tất cả bộ phận"), RUN.division, B("F&B", "F&B")].map((d, i) =>
                    `<button aria-selected="${i === 0}">${esc(tx(d))}</button>`).join("")}
            </div>
            <div class="lrn-steps" data-coach="pk-steps">${steps}</div>
            <p class="lrn-note">${esc(showing)}</p>
            <div class="lrn-kanban" data-coach="pk-tabs">${board}</div>
            <div class="lrn-panel" data-coach="pk-rejected">
                <h3>${ic("x")}${esc(tx(B("Rejected pay runs", "Đợt lương bị từ chối")))}<span class="lrn-tabn">${
                    N(b.filter((r) => r.col === "cancel").length)}</span></h3>
                <div class="lrn-rows">${rejected}</div>
            </div>
            <div class="lrn-panel" data-coach="rep-pipeline">
                <h3>${ic("git-branch")}${esc(tx(B("How a run travels", "Một đợt lương đi thế nào")))}</h3>
                ${pipeHTML("payrun", 1)}
                <p class="lrn-note">${esc(tx(B(
                    "Open a run and its own page says the same in one sentence: “Pay run approval — now with Đặng Thu Hà for HR lead review”.",
                    "Mở một đợt lương và trang của nó nói điều đó trong một câu: “Pay run approval — đang ở Đặng Thu Hà, bước Trưởng nhân sự soát xét”.")))}</p>
            </div>`;
    },

    /* --------------------------------------------------- Pay Run › Payslips
       PayslipReview (pb_payslip_review): the run picker, four numbers, the
       numbered steps, the list, and one payslip open beside it. */
    payslips() {
        const t = PRACTICE.slipTotals;
        const slips = PRACTICE.slips;
        const steps = stepButtons([
            { label: STATUS_LABELS.payslip.draft.l, count: 0 },
            { label: STATUS_LABELS.payslip.verify.l, count: t.count },
            { label: STATUS_LABELS.payslip.done.l, count: 0 },
        ], B("payslips", "phiếu lương"));
        const list = slips.map((s) => `
            <div class="lrn-row ${s.sel ? "on" : ""}">
                <span class="lrn-avatar">${esc(initial(s.emp.name))}</span>
                <span><span class="lrn-nm">${esc(s.emp.name)}</span><br>
                    <span class="lrn-sub2">${esc(s.emp.code)}</span></span>
                <span class="lrn-rr">${statusChip("payslip", s.state)}
                    <b class="lrn-money">${esc(M(s.net))}</b></span>
            </div>`).join("");
        // A payslip's own stepper — Draft, Waiting for approval, Done — read
        // from the SELECTED slip, so it cannot disagree with the row that is
        // highlighted. There is no button on it: a payslip moves with its run.
        const chain = ["draft", "verify", "done"];
        const cur = Math.max(0, chain.indexOf((slips.find((x) => x.sel) || slips[0]).state));
        const flow = chain.map((c, i) => `
            <div class="lrn-st ${i < cur ? "done" : ""}${SP}${i === cur ? "cur" : ""}"
                >${esc(tx(STATUS_LABELS.payslip[c].l))}</div>`).join("");
        const showing = tx(B("Showing all", "Đang hiện tất cả")) + SP + N(t.count) + SP
            + tx(B("payslips · press a step or a number to narrow it", "phiếu lương · bấm một bước hoặc một con số để thu hẹp"));
        return `
            <div class="lrn-strip">
                <select class="lrn-in" data-coach="ps-runsel">
                    <option>${esc(tx(RUN.name))}</option>
                    <option>${esc(tx(FNB.name))}</option>
                    <option>${esc(tx(B("Retail — June 2026", "Bán lẻ — Tháng 6/2026")))}</option>
                </select>
            </div>
            <div class="lrn-grid g4" data-coach="ps-kpis">
                ${kpiTile("receipt", "", N(t.count), B("Payslips", "Phiếu lương"))}
                ${kpiTile("alert-triangle", "", N(t.flagged), B("Need review", "Cần xem xét"))}
                ${kpiTile("calculator", "", M(t.gross), B("Gross total", "Tổng thu nhập"))}
                ${kpiTile("trending-up", "pos", M(t.net), B("Net total", "Tổng thực nhận"))}
            </div>
            <div class="lrn-steps" data-coach="ps-chips">${steps}</div>
            <p class="lrn-note">${esc(showing)}</p>
            <div class="lrn-grid g2 top">
                <div class="lrn-panel">
                    <h3>${ic("users")}${esc(tx(B("Payslips in this run", "Phiếu lương trong đợt này")))}</h3>
                    <div class="lrn-rows" data-coach="ps-list">${list}</div>
                </div>
                <div class="lrn-panel" data-coach="ps-detail">
                    <h3>${ic("receipt")}${esc(CASE.emp.mai.name)}${SP}·${SP}${esc(CASE.emp.mai.code)}</h3>
                    <div class="lrn-kv2"><span>${esc(tx(B("Net pay", "Lương thực nhận")))}</span>
                        <b class="lrn-money">${esc(M(CASE.emp.mai.netJul))}</b></div>
                    <div class="lrn-status" data-coach="ps-status">${flow}</div>
                    <h4>${esc(tx(B("Salary breakdown", "Chi tiết lương")))}</h4>
                    <div data-coach="ps-breakdown">${calcHTML()}</div>
                </div>
            </div>`;
    },

    /* ----------------------------------------------------- Pay Run › Import
       The Import lens (pb_import import.xml): the numbers row, "Load this
       period's pay data", the setup tiles, the six-step pipeline and the
       recent batches. There is no confidence score here — the old replica
       drew one the product does not have. */
    import() {
        const k = PRACTICE.importKpis;
        const pipe = stepButtons(PRACTICE.importPipe.map((p) => ({ label: p.label, count: p.count })),
                                 B("batches", "đợt"));
        const batches = PRACTICE.importBatches.map((b) => `
            <div class="lrn-row">
                <span><span class="lrn-nm">${esc(tx(b.name))}</span><br>
                    <span class="lrn-sub2">${N(b.rows)}${SP}${esc(tx(B("rows", "dòng")))}</span></span>
                <span class="lrn-rr">${statusChip("importbatch", b.state)}</span>
            </div>`).join("");
        const tiles = [
            ["plug", B("Load From Connected System", "Tải từ hệ thống đã kết nối")],
            ["grid", B("Set up columns from Excel", "Thiết lập cột từ Excel")],
            ["user-plus", B("Import Employees", "Nhập nhân viên")],
            ["layers", B("Set up a scheme from a file", "Thiết lập chương trình lương từ tệp")],
        ].map(([icon, label]) => `<button class="lrn-btn sm">${ic(icon)}${esc(tx(label))}</button>`).join("");
        return `
            <div class="lrn-grid g4" data-coach="im-kpis">
                ${kpiTile("database", "", N(k.batches), B("Import batches", "Đợt nhập liệu"))}
                ${kpiTile("check-circle", "pos", N(k.done), B("Completed", "Hoàn tất"))}
                ${kpiTile("clock", "", N(k.inProgress), B("In progress", "Đang xử lý"))}
                ${kpiTile("alert-triangle", "warn", N(k.errors), B("With errors", "Có lỗi"))}
            </div>
            <div class="lrn-herocta" data-coach="im-cta">
                ${ic("upload")}
                <span><b>${esc(tx(B("Load this period's pay data", "Tải dữ liệu lương của kỳ này")))}</b><br>
                    <span class="lrn-sub2">${esc(tx(B(
                        "A guided flow — upload your file, review matches, fix any issues, then commit. The tiles below set a scheme up; this one runs a period.",
                        "Luồng có hướng dẫn — tải tệp lên, soát các dòng khớp, sửa lỗi, rồi ghi vào hệ thống. Các ô bên dưới dùng để thiết lập chương trình lương; ô này dùng cho một kỳ.")))}</span></span>
                <button class="lrn-btn pri">${esc(T("startImport"))}</button>
            </div>
            <div class="lrn-strip" data-coach="im-launches">${tiles}</div>
            <div class="lrn-panel">
                <h3>${ic("git-branch")}${esc(tx(B("Where every import batch is", "Mỗi đợt nhập đang ở đâu")))}</h3>
                <div class="lrn-steps" data-coach="im-pipe">${pipe}</div>
            </div>
            <div class="lrn-panel">
                <h3>${ic("clock")}${esc(tx(B("Recent batches", "Đợt nhập gần đây")))}</h3>
                <div class="lrn-rows" data-coach="im-batches">${batches}</div>
            </div>`;
    },

    /* ---------------------------------------------- Import wizard (flow)
       pb_import_wizard's four steps — Source & file · Review & match ·
       Validate · Commit — drawn stacked, standing on Validate. */
    importwizard() {
        const w = PRACTICE.wizard;
        const steps = [
            B("Source & file", "Nguồn & tệp"), B("Review & match", "Soát & khớp"),
            B("Validate", "Kiểm tra"), B("Commit", "Ghi vào hệ thống"),
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
            <div class="lrn-grid g2 top">
                <div class="lrn-panel" data-coach="iw-source">
                    <h3>${ic("database")}${esc(tx(B("Source", "Nguồn")))}</h3>
                    <div class="lrn-seg">
                        <button aria-pressed="true">${esc(tx(B("File upload", "Tải tệp lên")))}</button>
                        <button aria-pressed="false">${esc(tx(B("Connector", "Đầu nối")))}</button>
                    </div>
                    <label class="lrn-flabel">${esc(tx(B("Formula configuration", "Cấu hình công thức")))}</label>
                    <select class="lrn-in"><option>${esc(RUN.config)}</option></select>
                </div>
                <div class="lrn-panel">
                    <h3>${ic("calendar")}${esc(tx(B("Period & file", "Kỳ & tệp")))}</h3>
                    <div class="lrn-kv2"><span>${esc(tx(B("From", "Từ")))}</span><b>${esc(RUN.from)}</b></div>
                    <div class="lrn-kv2"><span>${esc(tx(B("To", "Đến")))}</span><b>${esc(RUN.to)}</b></div>
                    <div class="lrn-kv2"><span>${esc(tx(B("Standard working days", "Ngày công chuẩn")))}</span><b>22</b></div>
                    <p class="lrn-note">${esc(tx(B(
                        "Working days a full month is paid against. Drop it for a month with public holidays.",
                        "Số ngày công mà một tháng đủ được tính lương theo. Giảm xuống cho tháng có ngày nghỉ lễ.")))}</p>
                </div>
            </div>
            <div class="lrn-statpills" data-coach="iw-review">
                <span class="lrn-statpill"><b>${N(w.rows)}</b>${esc(tx(B("Rows loaded", "Dòng đã nạp")))}</span>
                <span class="lrn-statpill"><b>${N(w.matched)}</b>${esc(tx(B("Matched", "Đã khớp")))}</span>
                <span class="lrn-statpill"><b>${N(w.newEmployees)}</b>${esc(tx(B("New employees", "Nhân viên mới")))}</span>
                <span class="lrn-statpill warn"><b>${N(w.errors)}</b>${esc(tx(B("Need attention", "Cần xử lý")))}</span>
            </div>
            <div class="lrn-panel">
                <h3>${ic("alert-triangle")}${esc(tx(B(
                    "Resolve these before committing", "Xử lý các mục này trước khi ghi vào hệ thống")))}</h3>
                <div class="lrn-rows" data-coach="iw-fixrows">${errs}</div>
            </div>
            <div class="lrn-strip">
                <button class="lrn-btn pri" data-coach="iw-commit">${ic("check")}${esc(T("commitImport"))}</button>
                <span class="lrn-note">${esc(tx(B(
                    "Nothing is written until you press this. When your company's approval route covers pay data, the same button reads “Send for approval”.",
                    "Chưa gì được ghi cho tới khi bạn bấm nút này. Khi lộ trình phê duyệt của công ty bạn áp cho dữ liệu lương, chính nút này sẽ hiện “Gửi đi duyệt”.")))}</span>
            </div>
            <div class="lrn-statpills" data-coach="iw-outcome">
                <span class="lrn-statpill"><b>${N(w.outcome.employees)}</b>${esc(tx(B("Employees created", "Nhân viên đã tạo")))}</span>
                <span class="lrn-statpill"><b>${N(w.outcome.payslips)}</b>${esc(tx(B("Payslips created", "Phiếu lương đã tạo")))}</span>
            </div>`;
    },

    /* ------------------------------------------ Settings › Formula Engine
       Formula Studio as it is today (pb_formula_studio studio.xml): the
       configuration switcher, its stage and the button that moves it on, the
       six views (Cards · Grid · Test · Compare · Health · Settings) and Tools.
       Simulate is no longer a header button — it lives in Tools → Analyze,
       drawn here as the practice panel it opens. The anchors fs-config,
       fs-views, fs-command, fs-components, fs-formula, fs-namesletters,
       fs-deps and fs-preview are the Studio's own. */
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
        const views = [B("Cards", "Thẻ"), B("Grid", "Lưới"), B("Test", "Kiểm thử"), B("Compare", "So sánh"),
                       B("Health", "Sức khoẻ"), B("Settings", "Cài đặt")].map((v, i) =>
            `<button aria-pressed="${i === 0}">${esc(tx(v))}</button>`).join("");
        const analyze = [B("Execution replay", "Phát lại lần tính"), B("What-if", "Giả định"),
                         B("Dependency map", "Bản đồ phụ thuộc"), B("Simulate", "Mô phỏng"),
                         B("Offer calculator", "Tính thử mức lương đề nghị")].map((a, i) =>
            `<span class="lrn-chip ${i === 3 ? "b" : ""}">${esc(tx(a))}</span>`).join("");
        const stages = ["draft", "testing", "validated", "active"].map((s, i) =>
            `<span class="lrn-chip ${i === 3 ? "ok" : ""}">${esc(tx(STAGE[s]))}</span>`).join(ARROW);

        return `
            <div class="lrn-strip">
                <button class="lrn-btn" data-coach="fs-config">${ic("grid")}${esc(cfgName)}</button>
                <span class="lrn-chip ok" data-coach="rep-fs-stage">${ic("check-circle")}${esc(tx(STAGE.active))}</span>
                <div class="lrn-seg" data-coach="fs-views">${views}</div>
                <button class="lrn-btn ghost" data-coach="fs-command">${ic("search")}${
                    esc(tx(B("Tools", "Công cụ")))}</button>
            </div>
            <div class="lrn-grid g2 top">
                <div class="lrn-panel">
                    <h3>${ic("git-branch")}${esc(tx(B("How a configuration goes live", "Một cấu hình đi vào hoạt động thế nào")))}</h3>
                    <div class="lrn-strip">${stages}</div>
                    <p class="lrn-note">${esc(tx(B(
                        "The button beside the name moves it on: Start testing, then Validate, then Activate. The stage badge opens Put it back to draft, and Retire this configuration — or Propose retiring it, when retiring needs a sign-off.",
                        "Nút bên cạnh tên đưa nó đi tiếp: Bắt đầu thử nghiệm, rồi Xác thực, rồi Kích hoạt. Huy hiệu giai đoạn mở ra Đưa về bản nháp, và Ngừng sử dụng cấu hình này — hoặc Đề xuất ngừng sử dụng, khi việc ngừng cần được phê duyệt.")))}</p>
                </div>
                <div class="lrn-panel" data-coach="rep-fs-tools">
                    <h3>${ic("search")}${esc(tx(B("Tools → Analyze", "Công cụ → Phân tích")))}</h3>
                    <div class="lrn-strip">${analyze}</div>
                    <p class="lrn-note">${esc(tx(B(
                        "Tools opens every tool in one place (Ctrl or Cmd + K). Simulate runs this configuration against last period's real payslips before it goes live.",
                        "Công cụ mở mọi công cụ ở cùng một chỗ (Ctrl hoặc Cmd + K). Mô phỏng chạy cấu hình này trên phiếu lương thật của kỳ trước, trước khi nó được đưa vào dùng.")))}</p>
                </div>
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

    /* ------------------------------------------------------------ Settings
       A page of categories, not a row of tabs (pb_settings settings_hub.js).
       The four this practice company has replicas for open them; the rest
       are drawn quiet and say why. */
    hub_settings() {
        const hub = MENU.find((h) => h.key === "settings");
        const cards = hub.lenses.map((l) => {
            const card = l.card ? tx(l.card) : tx(l.label);
            const attr = l.screen ? navAttr(l.screen) : quietAttr(tx(hub.label) + " › " + tx(l.label));
            return `<button class="lrn-setcard ${l.screen ? "" : "quiet"}" ${attr}>
                <b>${esc(tx(l.label))}</b><span class="lrn-sub2">${esc(card)}</span></button>`;
        }).join("");
        return `
            <div class="lrn-setgrid" data-coach="rep-settings">${cards}</div>
            <p class="lrn-note">${esc(tx(B(
                "A category with one card opens that card straight away — Formula Engine opens Formula Studio.",
                "Mục nào chỉ có một thẻ thì mở thẳng thẻ đó — Bộ máy công thức mở Xưởng công thức.")))}</p>`;
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
   LEARN REFRESH step 2. The rail and the tabs of TODAY's product. `visible` is
   the set of station keys the LEARNER can reach — it comes from the server,
   which asks the real hubs — so a greyed tab here is the reader's own access,
   not a guess about it.

   EVERY CONTROL ON THE RAIL AND THE TAB STRIP DOES SOMETHING OR SAYS WHY NOT.
   A tab this practice company has a screen for carries `data-nav` (the
   sandbox switches to it; a lesson says the lesson moves the screen for you);
   a tab it does not carries `data-quiet` and a tooltip, and pressing it says
   where it lives in the real app. */
function navAttr(screen) {
    return `data-nav="${esc(screen)}"`;
}

function quietAttr(place) {
    return `data-quiet="${esc(place)}" title="${esc(T("replicaQuietTip"))}"`;
}

/** The hub (rail item) and tab a replica screen lives under. A sub-screen
 *  borrows its owner's place, and Settings screens live under the Settings
 *  page with the category they came from. */
function placeOf(screen) {
    const sub = SUB_SCREENS[screen];
    const id = sub ? sub.owner : screen;
    for (const hub of MENU) {
        if (hub.screen === id) {
            return { hub, lens: null };
        }
        for (const lens of hub.lenses) {
            if (lens.screen === id || (lens.also || []).includes(id)
                || (lens.sub || []).some((s) => s.screen === id)) {
                return { hub, lens };
            }
        }
    }
    return { hub: MENU[0], lens: null };
}

/** The first screen a hub opens on, or "" when the practice company has none. */
function hubEntry(hub) {
    if (hub.screen) {
        return hub.screen;
    }
    const lens = hub.lenses.find((l) => l.screen);
    return lens ? lens.screen : "";
}

export function screenTitle(id) {
    const sub = SUB_SCREENS[id];
    if (sub) {
        return tx(sub.label);
    }
    const { hub, lens } = placeOf(id);
    return lens ? tx(hub.label) + " › " + tx(lens.label) : tx(hub.label);
}

export function shellHTML(screen, opts) {
    const o = opts || {};
    const visible = o.visible || new Set();
    CURRENT_SCREEN = screen;

    const here = placeOf(screen);
    let lastSection = null;
    const rail = MENU.map((hub) => {
        const entry = hubEntry(hub);
        const on = hub === here.hub;
        const section = hub.section && hub.section !== lastSection
            ? `<div class="lrn-sec">${esc(tx(hub.section))}</div>` : "";
        if (hub.section) {
            lastSection = hub.section;
        }
        const attr = entry ? navAttr(entry) : quietAttr(tx(hub.label));
        return `${section}<button class="lrn-item ${on ? "on" : ""}${SP}${entry ? "" : "quiet"}" ${attr}>${
            ic(hub.icon)}<span>${esc(tx(hub.label))}</span></button>`;
    }).join("");

    // The tab strip of the page being shown — or, on a Settings screen, the
    // breadcrumb back to the category page, because Settings has no tabs.
    let strip = "";
    if (here.hub.page && here.lens) {
        strip = `<div class="lrn-crumb">
            <button class="lrn-link" ${navAttr(here.hub.screen)}>${ic("chevron-left")}${esc(tx(here.hub.label))}</button>
            <span>›</span><b>${esc(tx(here.lens.label))}</b></div>`;
    } else if (!here.hub.page) {
        const tabs = here.hub.lenses.map((l) => {
            const cur = l === here.lens;
            const seen = !l.screen || !!o.free || !!o.guided || visible.has(l.screen);
            const attr = l.screen ? navAttr(l.screen) : quietAttr(tx(here.hub.label) + " › " + tx(l.label));
            const off = seen ? "" : "off";
            return `<button class="lrn-lens ${cur ? "on" : ""}${SP}${l.screen ? "" : "quiet"}${SP}${off}"
                role="tab" aria-selected="${cur}" ${attr}>${esc(tx(l.label))}</button>`;
        }).join("");
        const subs = here.lens && here.lens.sub
            ? `<div class="lrn-subtabs">${here.lens.sub.map((s) => `<button class="lrn-lens ${
                s.screen === screen ? "on" : ""}" ${navAttr(s.screen)}>${esc(tx(s.label))}</button>`).join("")}</div>`
            : "";
        strip = `<div class="lrn-lensbar" role="tablist" data-coach="rep-tabs">${tabs}</div>${subs}`;
    }
    const note = o.note
        ? `<div class="lrn-shellnote" role="status">${ic("info")}<span>${esc(o.note)}</span></div>` : "";

    const body = SCREENS[screen] ? SCREENS[screen]() : "";
    const blocked = !o.guided && here.lens && !visible.has(screen);
    // ONE practice banner. The sandbox (`free`) already carries its own
    // watermark, which says the same thing about the whole surface; a second
    // banner stacked under it said it twice (owner's screenshot, step 2).
    const banner = o.free ? ""
        : `<div class="lrn-pbanner" data-coach="rep-banner">${ic("shield-check")}<span>${esc(T("practiceBanner"))}</span></div>`;

    return `
    <div class="lrn-shell">
        <aside class="lrn-sb" data-coach="rep-nav" aria-label="${esc(tx(B("Payobook navigation", "Điều hướng Payobook")))}">
            <!-- ERRORS E4-4. The replica's own brand mark. It is a DRAWING of
                 the product the learner is about to use, so it has to carry
                 whatever that product is called for them — routed through tx()
                 (and so through _t and the debranding seams) rather than
                 written down. -->
            <div class="lrn-brand"><span class="lrn-mark">${ic("zap")}</span><span>${esc(tx("Payobook"))}</span></div>
            <div class="lrn-catch"><b>Hoa Sen Retail Co.</b>${esc(tx(B("Vietnam", "Việt Nam")))}</div>
            ${rail}
            <div class="lrn-foot">${esc(tx(B("Practice data · not your company", "Dữ liệu thực hành · không phải công ty của bạn")))}</div>
        </aside>
        <div class="lrn-main">
            ${banner}
            <div class="lrn-mhead">
                <h2>${esc(tx(here.hub.label))}</h2>
                <span class="lrn-sub">${esc(tx(B("Practice company — demo data", "Công ty thực hành — dữ liệu mô phỏng")))}</span>
            </div>
            ${strip}${note}
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
   replica, the same anchors, the same screens a lesson stands on. Only the
   menu is different (`free`), because a sandbox whose menu is greyed out is a
   sandbox with one screen in it. `note` is what the shell says after a press
   on a tab the practice company does not have. */
export function practiceShellHTML(screen, visible, note) {
    const mark = `<div class="lrn-watermark" data-coach="rep-watermark">${
        ic("shield-check")}<span>${esc(T("practiceWatermark"))}</span></div>`;
    return mark + shellHTML(screen, { guided: true, free: true, visible: visible, note: note });
}
