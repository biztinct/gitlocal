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
import { B, CASE, EMP, FNB, INPUT_ANCHORS, LATER, MENU, POLICY, PRACTICE, ROUTE, RUN, STATUS_LABELS,
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
            </div>
            ${compareHTML()}`;
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
        const effective = tx(B("Effective from", "Có hiệu lực từ")) + SP + POLICY.effective;

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

    /* ==================================================================
       LEARN REFRESH step 3 — PAYROLL SETUP.
       Nine views over six stations. Anchors that exist in the product carry
       the product's own names (bp-*, mp-*, ct-*, am-*, rd-*, gp-*, ex-money);
       what exists only here is rep-* and registered as practice.
       ================================================================== */

    /* ---------------- Settings › Guided setup › New configuration · Start */
    blueprint() {
        const b = PRACTICE.blueprint;
        const tiles = (list) => list.map((t) => `
            <span class="lrn-ztile ${t.on ? "on" : ""}">${t.on ? ic("check") : ""}<b>${esc(tx(t.name))}</b></span>`).join("");
        const starters = b.starters.map((s) => {
            const badge = s.badge ? `<span class="lrn-chip ok">${esc(tx(B("Certified", "Được chứng nhận")))}</span>` : "";
            return `<span class="lrn-ztile ${s.on ? "on" : ""}">${s.on ? ic("check") : ic("layers")}<b>${
                esc(tx(s.name))}</b>${badge}</span>`;
        }).join("");
        return `
            ${bpTop(b)}
            <div class="lrn-zbp">
                ${bpRail(0)}
                <div class="lrn-zbpmain">
                    <div class="lrn-zeyebrow">${esc(tx(B("01 / Choose your starting point", "01 / Chọn điểm bắt đầu")))}</div>
                    <div class="lrn-panel" data-coach="bp-identity">
                        <h3>${ic("user-check")}${esc(tx(B("Identity", "Định danh")))}</h3>
                        <div class="lrn-kv2"><span>${esc(tx(B("Company", "Công ty")))}</span><b>Hoa Sen Retail Co.</b></div>
                        <div class="lrn-kv2"><span>${esc(tx(B("Configuration name", "Tên cấu hình")))}</span><b>${esc(b.name)}</b></div>
                        <div class="lrn-kv2" data-coach="bp-country"><span>${esc(tx(B("Country", "Quốc gia")))}</span>
                            <b>${esc(tx(b.country))}${SP}<span class="lrn-chip b">${ic("banknote")}${esc(tx(b.money))}</span></b></div>
                        <div class="lrn-kv2"><span>${esc(tx(B("Pay cycle", "Chu kỳ thanh toán")))}</span><b>${esc(tx(b.cycle))}</b></div>
                        <div class="lrn-kv2"><span>${esc(tx(B("Effective from", "Có hiệu lực từ")))}</span><b>${esc(b.effective)}</b></div>
                    </div>
                    <div class="lrn-panel" data-coach="bp-starters">
                        <h3>${ic("layers")}${esc(tx(B("How would you like to start?", "Bạn muốn bắt đầu như thế nào?")))}</h3>
                        <div class="lrn-ztiles">${starters}</div>
                    </div>
                    <div class="lrn-grid g2 top">
                        <div class="lrn-panel" data-coach="bp-audience">
                            <h3>${ic("users")}${esc(tx(B("Who are you paying?", "Bạn đang trả lương cho ai?")))}</h3>
                            <div class="lrn-ztiles">${tiles(b.audiences)}</div>
                        </div>
                        <div class="lrn-panel" data-coach="bp-reallife">
                            <h3>${ic("calendar")}${esc(tx(B("Real life belongs in the design", "Đời thực phải có trong thiết kế")))}</h3>
                            <div class="lrn-ztiles">${tiles(b.reallife)}</div>
                        </div>
                    </div>
                    ${bpFoot(1, B("Continue to pay rules", "Tiếp tục sang Quy tắc lương"), 0)}
                </div>
                ${bpPay(b, false)}
            </div>`;
    },

    /* ------------------------- New configuration · Pay rules (sub-screen) */
    blueprint_rules() {
        const b = PRACTICE.blueprint;
        const rows = b.rules.map((r) => `
            <div class="lrn-zrule ${r.added ? "added" : ""}" ${r.added ? ATTR_BP_ADDED : ""}>
                <span class="lrn-chip ${r.added ? "ok" : ""}">${esc(r.code)}</span>
                <span class="lrn-zsay">${esc(tx(r.say))}</span>
                <code>${esc(r.f)}</code>
            </div>`).join("");
        const tabs = [B("Components", "Thành phần"), B("Tax & protection", "Thuế & bảo hiểm"),
                      B("Calendar & payment", "Lịch & chi trả")].map((t, i) =>
            `<button aria-selected="${i === 0}">${esc(tx(t))}</button>`).join("");
        return `
            ${bpTop(b)}
            <div class="lrn-zbp">
                ${bpRail(1)}
                <div class="lrn-zbpmain">
                    <div class="lrn-zeyebrow">${esc(tx(B("02 / What goes into pay", "02 / Những gì tạo nên tiền lương")))}</div>
                    <div class="lrn-tabs">${tabs}</div>
                    <div class="lrn-panel" data-coach="rep-bp-rules">
                        <h3>${ic("list-checks")}${esc(tx(B("Every component. One clear rule.", "Mỗi thành phần. Một quy tắc rõ ràng.")))}</h3>
                        ${rows}
                    </div>
                    ${bpFoot(2, B("Continue to Tax & protection", "Tiếp tục sang Thuế & bảo hiểm"), b.rules.length)}
                </div>
                ${bpPay(b, true)}
            </div>`;
    },

    /* ---------------------- Settings › Integrations › Mapping · Journey */
    mapping() {
        const m = PRACTICE.mapping;
        const h = m.header;
        const headline = N(h.inputs) + SP + tx(B("needs a source", "cần một nguồn")) + DOT
            + N(h.fed) + SP + tx(B("fed", "đã có nguồn")) + DOT
            + N(h.unfed) + SP + tx(B("not fed yet", "chưa có nguồn"));
        const sys = m.systems.map((s) => `
            <div class="lrn-zcard">
                <b>${esc(s.name)}</b><span class="lrn-sub2">${esc(tx(s.sub))}</span>
                ${s.rows.map((r, i) => `<span class="lrn-zfield" ${s.id === "sys" && i === 0 ? ATTR_JNY_FILE : ""}>${
                    esc(typeof r === "string" ? r : tx(r))}</span>`).join("")}
            </div>`).join("");
        const feeds = m.feeds.map((f) => `
            <div class="lrn-zcard"><b>${esc(tx(f.name))}</b>
                ${f.rows.map((r, i) => `<span class="lrn-zfield" ${i === 0 ? ATTR_JNY_FEED : ""}>${esc(r)}</span>`).join("")}
            </div>`).join("");
        const xf = m.transforms.map((x) => `
            <div class="lrn-zcard" data-coach="rep-jny-xform"><b>${ic("sigma")}${esc(tx(x.name))}</b>
                <span class="lrn-sub2">${esc(tx(x.sub))}</span></div>`).join("");
        const scheme = m.scheme.map((r) => `
            <span class="lrn-zfield ${r.fed ? "" : "unfed"}" ${r.code === "LCB" ? ATTR_JNY_SCHEME : ""}>${
                esc(r.code)}${DOT}${esc(tx(r.label))}${r.fed ? "" : DOT + esc(tx(B("not fed", "chưa có nguồn")))}</span>`).join("");
        const src = m.source.map((g) => `<span class="lrn-zfield">${esc(tx(g))}</span>`).join("");
        const lane = (icon, label, body) => `
            <div class="lrn-zlane"><div class="lrn-zlaneh">${ic(icon)}<span>${esc(tx(label))}</span></div>${body}</div>`;
        return `
            ${mapTop(m, headline)}
            <div class="lrn-panel lrn-zjny">
                <div class="lrn-zjbar" data-coach="mp-jbar"><b>${esc(m.to)}</b><span class="lrn-sub2">${esc(headline)}</span>
                    <span class="lrn-zq">${ic("search")}${esc(tx(B("Filter the journey…", "Lọc hành trình…")))}</span></div>
                <div class="lrn-zlanes" data-coach="mp-lanes">
                    ${lane("database", B("Files & systems", "Tệp & hệ thống"), sys)}
                    ${lane("database", B("Feeds", "Nguồn cấp dữ liệu"), feeds)}
                    ${lane("sigma", B("Transformations", "Chuyển đổi"), xf)}
                    ${lane("calculator", B("Scheme", "Chương trình lương"), `<div class="lrn-zcard"><b>${esc(RUN.config)}</b>${scheme}</div>`)}
                    ${lane("users", B("Payobook Source", "Nguồn Payobook"), `<div class="lrn-zcard" data-coach="rep-jny-source"><b>${
                        esc(tx(B("Payobook Source", "Nguồn Payobook")))}</b>${src}<span class="lrn-zact">${ic("arrow-right")}${
                        esc(tx(B("Open Records Desk", "Mở Records Desk")))}</span></div>`)}
                </div>
            </div>
            <div class="lrn-panel lrn-zslip" data-coach="rep-jny-slip">
                <h3>${ic("receipt")}${esc(CASE.emp.mai.name)}${DOT}${esc(tx(RUN.period))}</h3>
                <div class="lrn-cr"><span>${esc(tx(CASE.slip[0].k))}</span><b>${esc(M(CASE.slip[0].v))}</b></div>
                <p class="lrn-note">${esc(tx(B(
                    "Her payslip line — the far end of the wire. Drawn here so the whole road fits on one screen.",
                    "Dòng trên phiếu lương của cô ấy — điểm cuối của sợi dây. Vẽ ở đây để cả chặng đường nằm trên một màn hình.")))}</p>
            </div>`;
    },

    /* ------------------------- Mapping · Spreadsheet columns → Scheme */
    mapping_sheet() {
        const m = PRACTICE.mapping;
        const cols = m.sheetColumns.map((c) => `
            <div class="lrn-row ${c.clash ? "hit" : ""}">
                <span class="lrn-avatar">${ic("table")}</span>
                <span><span class="lrn-nm">${esc(tx(c.col))}</span><br>
                    <span class="lrn-sub2">${esc(tx(B("e.g.", "ví dụ")))}${SP}${esc(c.eg)}</span></span>
                <span class="lrn-rr">${ic("arrow-right")}<span class="lrn-chip b">${esc(c.to)}</span></span>
            </div>`).join("");
        const runv = m.runValues.map((r) => `<div class="lrn-kv2"><span>${esc(tx(r.k))}</span><b>${esc(r.v)}</b></div>`).join("");
        const lane = tx(B("From this pay run", "Từ đợt lương này")) + DOT + tx(RUN.period);
        return `
            ${mapTop(m, "")}
            <div class="lrn-panel lrn-zdrop" data-coach="mp-ramp">
                <h3>${ic("table")}${esc(tx(B("Drop this period's spreadsheet here to see its columns",
                                            "Thả bảng tính của kỳ này vào đây để xem các cột")))}</h3>
                <p class="lrn-note">${esc(tx(B(
                    "It reads the headings and one example row. It imports no numbers.",
                    "Nó chỉ đọc tiêu đề và một dòng ví dụ. Nó không nhập con số nào.")))}</p>
                <div class="lrn-strip"><button class="lrn-btn sm">${ic("download")}${
                    esc(tx(B("Download a template built from this scheme", "Tải mẫu dựng từ chương trình lương này")))}</button></div>
            </div>
            <div class="lrn-grid g2 top">
                <div class="lrn-panel">
                    <h3>${ic("git-merge")}${esc(tx(B("Columns wired to the scheme", "Các cột đã nối vào chương trình lương")))}</h3>
                    ${cols}
                </div>
                <div class="lrn-panel" data-coach="rep-mp-runlane">
                    <h3>${ic("calendar")}${esc(lane)}</h3>
                    ${runv}
                    <p class="lrn-note">${esc(tx(B(
                        "Values the pay run itself knows. Wire one to a component and nobody has to type it into the file.",
                        "Những giá trị chính đợt lương đã biết. Nối một giá trị vào thành phần là không ai phải gõ nó vào tệp.")))}</p>
                </div>
            </div>
            <div class="lrn-panel lrn-zdialog" data-coach="rep-mp-conflict">
                <h3>${ic("alert-triangle")}${esc(tx(B("“PC” will read more than one source", "“PC” sẽ đọc nhiều hơn một nguồn")))}</h3>
                <p class="lrn-note">${esc(tx(B(
                    "The HR system already feeds Allowances. Keep both and the system is read first; the spreadsheet only fills the box when the system sent nothing.",
                    "Hệ thống nhân sự đã cấp Phụ cấp. Giữ cả hai thì hệ thống được đọc trước; bảng tính chỉ điền vào ô khi hệ thống không gửi gì.")))}</p>
                <div class="lrn-strip">
                    <button class="lrn-btn sm pri">${esc(tx(B("Add source", "Thêm nguồn")))}</button>
                    <button class="lrn-btn sm">${esc(tx(B("Use the spreadsheet instead", "Thay vào đó hãy sử dụng bảng tính")))}</button>
                    <button class="lrn-btn sm ghost">${esc(tx(B("Cancel", "Huỷ")))}</button>
                </div>
            </div>`;
    },

    /* -------------------------------- Mapping · Component treatment */
    treatment() {
        const t = PRACTICE.treatment;
        const c = t.counts;
        const rows = t.rows.map((r) => `
            <tr class="${r.clash ? "clash" : ""}${SP}${r.review ? "review" : ""}">
                <td><b>${esc(tx(r.name))}</b><br><span class="lrn-faint">${esc(r.code)}</span></td>
                <td><span class="lrn-chip">${esc(tx(r.from))}</span></td>
                <td>${esc(tx(r.group))}</td>
                <td>${r.role ? esc(tx(t.roles[r.role])) : `<span class="lrn-chip warn">${esc(tx(B("needs your answer", "cần câu trả lời của bạn")))}</span>`}</td>
                <td class="c">${r.sub ? ic("check") : ""}</td>
                <td>${esc(tx(t.types[r.type]))}</td>
            </tr>`).join("");
        return `
            ${mapTop(PRACTICE.mapping, "")}
            <div class="lrn-panel">
                <div class="lrn-zhead" data-coach="tr-head">
                    <h3>${ic("settings")}${esc(tx(B("How each component is treated", "Cách xử lý từng thành phần")))}</h3>
                    <span class="lrn-push"></span>
                    <button class="lrn-btn sm">${ic("rotate-ccw")}${esc(tx(B("Re-classify from the formulas", "Phân loại lại từ các công thức")))}</button>
                    <button class="lrn-btn sm pri" disabled="disabled">${esc(tx(B("Save", "Lưu")))}</button>
                </div>
                <div class="lrn-strip" data-coach="tr-filters">
                    <span class="lrn-chip b">${esc(tx(B("All", "Tất cả")))}${SP}${N(c.all)}</span>
                    <span class="lrn-chip warn">${esc(tx(B("Needs your answer", "Cần câu trả lời của bạn")))}${SP}${N(c.review)}</span>
                    <span class="lrn-chip warn">${esc(tx(B("Type says otherwise", "Loại giá trị nói khác")))}${SP}${N(c.clash)}</span>
                </div>
                <p class="lrn-callout warn" data-coach="rep-ct-warn">${ic("alert-triangle")}<span>${esc(tx(B(
                    "1 component is counted in hours, days or percent, yet is set to add to or come off net pay. Hours reach net pay by multiplying an amount, so it should be Information only.",
                    "1 thành phần được tính bằng giờ, ngày hoặc phần trăm, nhưng lại được đặt để cộng vào hoặc trừ khỏi thực nhận. Giờ đi vào thực nhận bằng cách nhân với một số tiền, nên nó phải là Chỉ để tham khảo.")))}</span></p>
                <div class="lrn-ztablewrap">
                <table class="lrn-ztable" data-coach="tr-table">
                    <thead><tr>
                        <th>${esc(tx(B("Component", "Thành phần")))}</th><th>${esc(tx(B("Comes from", "Đến từ")))}</th>
                        <th>${esc(tx(B("Group", "Nhóm")))}</th><th>${esc(tx(B("Pay role", "Vai trò trong lương")))}</th>
                        <th class="c">${esc(tx(B("Subtotal", "Tổng phụ")))}</th><th>${esc(tx(B("Value type", "Loại giá trị")))}</th>
                    </tr></thead>
                    <tbody>${rows}</tbody>
                </table>
                </div>
            </div>`;
    },

    /* ------------------------------------------ Settings › Approvals */
    matrix() {
        const x = PRACTICE.matrix;
        const route = (labels) => labels.length
            ? labels.map((l) => esc(tx(l))).join(ARROW)
            : esc(tx(B("No approval needed", "Không cần phê duyệt")));
        const body = x.areas.map((a) => `
            <tr class="lrn-zarea"><td colspan="4">${esc(tx(a.name))}${SP}<span class="lrn-tabn">${N(a.rows.length)}</span></td></tr>
            ${a.rows.map((r) => `
            <tr ${r.pay ? ATTR_AM_PAYROW : ""}>
                <td><b>${esc(tx(r.name))}</b>${r.fast ? `<span class="lrn-chip b">${ic("zap")}${esc(tx(B("no approval needed", "không cần phê duyệt")))}</span>` : ""}
                    <br><span class="lrn-sub2">${route(r.route)}</span></td>
                <td>${esc(tx(r.applies))}</td>
                <td><span class="lrn-chip ${x.statuses[r.status].t}">${esc(tx(x.statuses[r.status].l))}</span></td>
                <td>${esc(r.v)}</td>
            </tr>`).join("")}`).join("");
        const tabs = [B("Matrix", "Ma trận"), B("People & backups", "Con người & người thay thế"), B("History", "Lịch sử")]
            .map((t, i) => `<button aria-selected="${i === 0}">${esc(tx(t))}</button>`).join("");
        return `
            <div class="lrn-zhero" data-coach="am-hero">
                <div><div class="lrn-zeyebrow">${ic("stamp")}${esc(tx(B("Settings", "Cài đặt")))}</div>
                    <h3>${esc(tx(B("Approval Matrix", "Ma trận phê duyệt")))}</h3>
                    <span class="lrn-sub2">${esc(tx(B("Every check, in one place. Decide who signs off what, for each part of the business, in plain words.",
                        "Mọi bước kiểm tra, ở một nơi. Quyết định ai phê duyệt việc gì, cho từng phần của doanh nghiệp, bằng lời lẽ dễ hiểu.")))}</span></div>
                <div class="lrn-strip">
                    <button class="lrn-btn sm ghost">${ic("upload")}${esc(tx(B("Bring in from a spreadsheet", "Nạp từ bảng tính")))}</button>
                    <button class="lrn-btn sm pri" ${navAttr("matrix_builder")}>${ic("plus")}${esc(tx(B("Create a workflow", "Tạo một luồng phê duyệt")))}</button>
                </div>
            </div>
            <div class="lrn-tabs" data-coach="am-tabs">${tabs}</div>
            <div class="lrn-strip" data-coach="am-filters">
                <span class="lrn-chip b">${esc(tx(B("All areas", "Mọi mảng")))}</span>
                <span class="lrn-chip">${esc(tx(B("Payroll", "Tiền lương")))}</span>
                <span class="lrn-chip">${esc(tx(B("People", "Nhân sự")))}</span>
                <span class="lrn-chip">${esc(tx(B("Any status", "Mọi trạng thái")))}</span>
            </div>
            <div class="lrn-panel">
                <div class="lrn-zhead" data-coach="am-bulk">
                    <b>${esc(tx(B("5 processes", "5 quy trình")))}</b><span class="lrn-push"></span>
                    <button class="lrn-btn sm">${ic("zap")}${esc(tx(B("No approval needed for all", "Không cần phê duyệt cho tất cả")))}</button>
                </div>
                <div class="lrn-ztablewrap">
                <table class="lrn-ztable" data-coach="am-table">
                    <thead><tr><th>${esc(tx(B("Process and the route it follows", "Quy trình và lộ trình nó đi theo")))}</th>
                        <th>${esc(tx(B("Applies to", "Áp dụng cho")))}</th><th>${esc(tx(B("Status", "Trạng thái")))}</th>
                        <th>${esc(tx(B("Version", "Phiên bản")))}</th></tr></thead>
                    <tbody>${body}</tbody>
                </table>
                </div>
                <p class="lrn-note" data-coach="am-foot">${esc(tx(B(
                    "A row is In use only when its route is published and the feature behind it is wired up. Any process may be set to No approval needed; the row says so out loud and every use is still recorded.",
                    "Một dòng chỉ Đang dùng khi lộ trình của nó đã được ban hành và tính năng đứng sau đã được nối. Quy trình nào cũng có thể đặt Không cần phê duyệt; dòng đó nói rõ điều này và mọi lần dùng vẫn được ghi lại.")))}</p>
            </div>`;
    },

    /* ------------------------------------ Approval Matrix · the builder */
    matrix_builder() {
        const bd = PRACTICE.matrix.builder;
        const prog = [B("Purpose", "Mục đích"), B("People", "Nhân sự"), B("Safeguards", "Bảo vệ"),
                      B("Review", "Xem lại"), B("Publish", "Ban hành")].map((p, i) => `
            <div class="lrn-wstep ${i < 4 ? "done" : "cur"}"><span class="lrn-wdot">${i < 4 ? ic("check") : i + 1}</span><span>${esc(tx(p))}</span></div>`).join("");
        const steps = bd.steps.map((s, i) => `
            <div class="lrn-zstep">
                <span class="lrn-zstepn">${i + 1}</span>
                <span><b>${esc(tx(s.title))}</b><br><span class="lrn-sub2">${esc(tx(s.kind))}${DOT}${esc(s.who)}</span>${
                    s.band ? `<br><span class="lrn-chip warn">${esc(tx(s.band))}</span>` : ""}</span>
            </div>`).join("");
        const kinds = bd.kinds.map((k) => `<span class="lrn-chip">${esc(tx(k))}</span>`).join("");
        const guards = bd.safeguards.map((g) => `<div class="lrn-kv2"><span>${esc(tx(g))}</span><b>${ic("check")}</b></div>`).join("");
        return `
            <div class="lrn-strip"><button class="lrn-link" ${navAttr("matrix")}>${ic("chevron-left")}${
                esc(tx(B("Approval Matrix", "Ma trận phê duyệt")))}</button><b>${esc(tx(B("Pay run", "Đợt lương")))}</b></div>
            <div class="lrn-rail" data-coach="rep-am-bsteps">${prog}</div>
            <div class="lrn-grid g2 top">
                <div class="lrn-panel" data-coach="rep-am-route">
                    <h3>${ic("git-branch")}${esc(tx(B("The route", "Lộ trình")))}</h3>
                    ${steps}
                    <h4>${esc(tx(B("Add a step", "Thêm một bước")))}</h4>
                    <div class="lrn-strip">${kinds}</div>
                </div>
                <div class="lrn-panel" data-coach="rep-am-guards">
                    <h3>${ic("shield-check")}${esc(tx(B("Safeguards", "Bảo vệ")))}</h3>
                    ${guards}
                    <button class="lrn-btn sm ghost">${ic("users")}${esc(tx(B("Try an example", "Thử một ví dụ")))}</button>
                </div>
            </div>
            <div class="lrn-panel" data-coach="rep-am-publish">
                <h3>${ic("stamp")}${esc(tx(B("Publish", "Ban hành")))}</h3>
                <div class="lrn-kv2"><span>${esc(tx(B("New requests follow it from", "Yêu cầu mới đi theo nó từ")))}</span><b>${esc(bd.from)}</b></div>
                <p class="lrn-note">${esc(tx(B(
                    "Requests already on their way finish on the route they started on. Publishing never moves them.",
                    "Những yêu cầu đang trên đường sẽ đi hết lộ trình mà chúng đã bắt đầu. Ban hành không bao giờ chuyển chúng sang lộ trình mới.")))}</p>
                <button class="lrn-btn pri">${ic("stamp")}${esc(tx(B("Publish this route", "Ban hành lộ trình này")))}</button>
            </div>`;
    },

    /* ----------------------------------------------- People › Records */
    records() {
        const r = PRACTICE.records;
        const head = r.picked.map((p) => `<th>${esc(tx(p))}</th>`).join("");
        const rows = r.rows.map((row) => `
            <tr><td><b>${esc(row.emp.name)}</b><br><span class="lrn-faint">${esc(row.emp.code)}</span></td>
                ${row.vals.map((v, i) => {
                    const edited = (row.edit || []).includes(i);
                    const shown = typeof v === "number" ? M(v) : v;
                    return `<td class="${edited ? "edited" : ""}">${esc(shown)}</td>`;
                }).join("")}</tr>`).join("");
        const changes = r.rows.filter((row) => row.edit).map((row) => {
            const i = row.edit[0];
            const was = typeof row.was[0] === "number" ? M(row.was[0]) : row.was[0];
            const now = typeof row.vals[i] === "number" ? M(row.vals[i]) : row.vals[i];
            return `<div class="lrn-kv2"><span>${esc(row.emp.name)}${DOT}${esc(tx(r.picked[i]))}</span><b>${esc(was)}${ARROW}${esc(now)}</b></div>`;
        }).join("");
        const reviewLabel = tx(B("Review", "Xem lại")) + SP + N(r.changes) + SP + tx(B("changes", "thay đổi"));
        const fieldsLabel = RUN.scheme + DOT + N(r.fields) + SP + tx(B("fields", "trường"));
        return `
            <div class="lrn-zhead" data-coach="rd-head">
                <span class="lrn-sub2">${esc(tx(B("Update the employee, contract and bank details your pay scheme reads — one person or hundreds at once.",
                    "Cập nhật thông tin nhân viên, hợp đồng và ngân hàng mà chương trình lương của bạn đọc — một người hay hàng trăm người cùng lúc.")))}</span>
                <span class="lrn-push"></span>
                <span class="lrn-chip b" data-coach="rd-scheme">${ic("layers")}${esc(fieldsLabel)}</span>
                <span class="lrn-strip lrn-zinline" data-coach="rd-file">
                    <button class="lrn-btn sm ghost">${ic("download")}${esc(tx(B("Export with data", "Xuất kèm dữ liệu")))}</button>
                    <button class="lrn-btn sm ghost">${ic("upload")}${esc(tx(B("Import a file", "Nhập một tệp")))}</button>
                </span>
                <button class="lrn-btn sm ghost" data-coach="rd-history">${ic("clock")}${esc(tx(B("History", "Lịch sử")))}</button>
                <button class="lrn-btn sm pri" data-coach="rd-review">${ic("check-circle")}${esc(reviewLabel)}</button>
            </div>
            <div class="lrn-zdesk">
                <div class="lrn-panel" data-coach="rd-who">
                    <h3>${ic("users")}${esc(tx(B("Who", "Ai")))}</h3>
                    <span class="lrn-chip b">${esc(tx(B("Department", "Phòng ban")))}: ${esc(tx(RUN.division))}</span>
                    <p class="lrn-note">${esc(N(RUN.employees) + SP + tx(B("people match", "người khớp")))}</p>
                </div>
                <div class="lrn-panel">
                    <div class="lrn-strip" data-coach="rd-fields">
                        <b>${ic("layers")}${esc(tx(B("Fields", "Trường")))}</b>
                        ${r.picked.map((p) => `<span class="lrn-chip ok">${esc(tx(p))}</span>`).join("")}
                    </div>
                    <div class="lrn-ztablewrap">
                    <table class="lrn-ztable" data-coach="rep-rd-grid">
                        <thead><tr><th>${esc(tx(B("Employee", "Nhân viên")))}</th>${head}</tr></thead>
                        <tbody>${rows}</tbody>
                    </table>
                    </div>
                </div>
            </div>
            <div class="lrn-panel lrn-zdrawer" data-coach="rep-rd-reviewpanel">
                <h3>${ic("check-circle")}${esc(tx(B("Review your changes — drawn open", "Xem lại các thay đổi — đang mở sẵn")))}</h3>
                ${changes}
                <p class="lrn-note">${esc(tx(B("Applying sends them along the route", "Áp dụng sẽ gửi chúng theo lộ trình")))}${SP}“${
                    esc(tx(r.route))}”${DOT}${esc(tx(B("Sent for approval —", "Đã gửi phê duyệt —")))}${SP}${esc(r.approver)}</p>
                <div class="lrn-strip">
                    <button class="lrn-btn sm pri">${esc(tx(B("Apply", "Áp dụng")))}${SP}${N(r.changes)}${SP}${esc(tx(B("changes", "thay đổi")))}</button>
                    <button class="lrn-btn sm ghost">${ic("undo")}${esc(tx(B("Undo", "Hoàn tác")))}</button>
                </div>
            </div>`;
    },

    /* ------------------------------------------------ Settings › Group
       The `schemes` station's own screen: a pay scheme pays in its
       country's money, and the group is where two monies meet. */
    schemes() {
        const g = PRACTICE.group;
        const months = [B("Jan", "Th1"), B("Feb", "Th2"), B("Mar", "Th3"), B("Apr", "Th4"), B("May", "Th5"),
                        B("Jun", "Th6"), B("Jul", "Th7"), B("Aug", "Th8"), B("Sep", "Th9"), B("Oct", "Th10"),
                        B("Nov", "Th11"), B("Dec", "Th12")];
        const cells = g.strip.map((s, i) => `<span class="lrn-zcell ${s}">${esc(tx(months[i]))}</span>`).join("");
        const cos = g.companies.map((c) => `
            <div class="lrn-zco">
                <span class="lrn-chip">${esc(c.flag)}${DOT}${esc(c.cur)}</span>
                <b>${esc(c.name)}</b>
                <span class="lrn-sub2">${esc(N(c.people) + SP + tx(B("people", "người")) + DOT + N(c.schemes) + SP + tx(B("pay schemes", "chương trình lương")))}</span>
            </div>`).join("");
        const policies = g.policies.map((p, i) => `<span class="lrn-chip ${i === 0 ? "b" : ""}">${esc(tx(p))}</span>`).join("");
        return `
            <div class="lrn-zhead" data-coach="gp-head">
                <div><h3>${esc(tx(B("Your group", "Tập đoàn của bạn")))}</h3>
                    <span class="lrn-sub2">${esc(tx(B("The companies, currency and divisions every report and plan will use.",
                        "Các công ty, đồng tiền và khối mà mọi báo cáo và kế hoạch sẽ dùng.")))}</span></div>
                <span class="lrn-push"></span>
                <button class="lrn-btn sm ghost">${ic("clock")}${esc(tx(B("History", "Lịch sử")))}</button>
                <button class="lrn-btn sm pri">${esc(tx(B("Edit the group", "Sửa tập đoàn")))}</button>
            </div>
            <div class="lrn-panel" data-coach="gp-tree">
                <h3>${ic("landmark")}${esc(g.name)}${SP}<span class="lrn-chip b">${ic("banknote")}${esc(g.currency)}</span></h3>
                <div class="lrn-zcos">${cos}</div>
                <p class="lrn-note" data-coach="rep-gp-foot">${esc(tx(B(
                    "Nothing is stored in the group currency. Every figure keeps the money it was paid in and is converted when you look at it.",
                    "Không có gì được lưu bằng đồng tiền của tập đoàn. Mọi con số giữ nguyên đồng tiền đã trả và chỉ được quy đổi khi bạn xem.")))}</p>
            </div>
            <div class="lrn-panel" data-coach="gp-rates">
                <h3>${ic("banknote")}${esc(tx(B("Exchange rates", "Tỷ giá")))}</h3>
                <div class="lrn-kv2"><span>${esc(tx(B("How rates are picked", "Cách chọn tỷ giá")))}</span><b>${esc(tx(g.policy))}</b></div>
                <div class="lrn-strip">${policies}</div>
                <div class="lrn-zstrip"><b>SGD${SP}${ic("arrow-left-right")}${SP}VND</b>${cells}</div>
                <p class="lrn-note">${esc(tx(B(
                    "Green: a rate from that month. Amber: an older rate is used. Grey: no rate, so the figures stay in their own money. A change to a rate goes through approval.",
                    "Xanh: có tỷ giá của tháng đó. Vàng: dùng một tỷ giá cũ hơn. Xám: không có tỷ giá, nên số liệu giữ nguyên đồng tiền của nó. Thay đổi tỷ giá phải qua phê duyệt.")))}</p>
            </div>`;
    },

    /* ==========================================================================
       LEARN REFRESH step 4 — THE WIDER APP. Compact drawings of the real
       boards, fixture-driven (PRACTICE.*), carrying the product's own anchor
       names where the drawn element IS the product's element, and `rep-`
       names for what only a lesson needs. Workforce, Access and Compliance
       here; People › Pay, Plan and the Lifecycle boards below.
       ======================================================================= */

    /* ---------------------------------------------- Workforce › Today */
    wftoday() {
        const t = PRACTICE.wftoday;
        const tiles = t.tiles.map(([k, v]) => kpiTile("users", "", N(v), k)).join("");
        const needs = t.needs.map(([k, v]) => `<div class="lrn-kv2"><span>${esc(tx(k))}</span><b>${esc(N(v))}</b></div>`).join("");
        const clean = N(t.clean) + SP + tx(B("clean overtime — hours match the grid, under every limit, on an open day.",
            "tăng ca sạch — giờ khớp lưới, trong mọi giới hạn, vào ngày còn mở."));
        return `
            <div class="lrn-ywf">
                <div class="lrn-ywfmain">
                    <div class="lrn-zhead" data-coach="wf-today">
                        <h3>${ic("sun")}${esc(N(t.tiles[0][1]))}${SP}${esc(tx(B("on the board", "trên bảng")))}</h3>
                        <span class="lrn-push"></span>
                        <span class="lrn-seg"><button aria-pressed="true">${esc(tx(B("Board", "Bảng")))}</button><button aria-pressed="false">${
                            esc(tx(B("Map", "Bản đồ")))}</button></span>
                    </div>
                    <div class="lrn-grid g5">${tiles}</div>
                    <p class="lrn-note">${esc(tx(B("Who is in, who is late and who is out — today, for the teams you look after.",
                        "Ai có mặt, ai đi trễ, ai vắng — hôm nay, cho các nhóm bạn phụ trách.")))}</p>
                </div>
                <aside class="lrn-panel lrn-ydock" data-coach="wf-needs">
                    <h3>${ic("inbox")}${esc(tx(B("Needs you", "Cần bạn")))}</h3>
                    <span class="lrn-seg"><button aria-pressed="true">${esc(tx(B("My team", "Đội của tôi")))}</button><button aria-pressed="false">${
                        esc(tx(B("Organisation", "Tổ chức")))}</button></span>
                    ${needs}
                    <div class="lrn-yclean" data-coach="wf-clean">
                        <p class="lrn-note">${esc(clean)}</p>
                        <button class="lrn-btn sm pri">${ic("check-circle")}${esc(tx(B("Approve all", "Phê duyệt tất cả")))}${SP}${esc(N(t.clean))}${SP}${
                            esc(tx(B("clean", "sạch")))}</button>
                    </div>
                </aside>
            </div>`;
    },

    /* --------------------------------- Workforce › Time, Time Off, Overtime
       Three tabs drawn as three panels: the lesson walks all of them. */
    wftime() {
        const t = PRACTICE.wftime;
        const tabs = t.tabs.map((x, i) => `<button class="lrn-lens ${i === 0 ? "on" : ""}">${esc(tx(x))}${
            i === 2 ? `${SP}<span class="lrn-chip warn">${esc(N(t.exceptions))}</span>` : ""}</button>`).join("");
        const leave = t.leave.map((r) => `<div class="lrn-row"><span class="lrn-avatar">${esc(initial(r.name))}</span>
            <span><span class="lrn-nm">${esc(r.name)}</span><br><span class="lrn-sub2">${esc(tx(r.what))}</span></span>
            <span class="lrn-rr"><button class="lrn-btn sm pri">${esc(tx(B("Approve", "Duyệt")))}</button></span></div>`).join("");
        const ot = t.ot.map((r) => `<div class="lrn-row"><span class="lrn-avatar">${esc(initial(r.name))}</span>
            <span><span class="lrn-nm">${esc(r.name)}</span><br><span class="lrn-sub2">${esc(tx(r.what))}</span></span>
            <span class="lrn-rr">${r.near ? `<span class="lrn-chip warn">${esc(tx(B("Near the limit", "Gần giới hạn")))}</span>` : ""}</span></div>`).join("");
        const otn = t.otNumbers.map(([k, v]) => `<span><b>${esc(N(v))}</b>${SP}${esc(tx(k))}</span>`).join("");
        const caps = t.caps.map(([k, v]) => `<div class="lrn-kv2"><span>${esc(tx(k))}</span><b>${esc(v)}</b></div>`).join("");
        return `
            <div class="lrn-panel">
                <h3>${ic("clock")}${esc(tx(B("Time", "Chấm công")))}</h3>
                <div class="lrn-zmodes" data-coach="wf-time">${tabs}</div>
                <p class="lrn-note" data-coach="rep-wf-exc">${esc(tx(B(
                    "Exceptions are the days that did not add up: a missing check-out, a late start with no reason. Each one becomes a flag on Close.",
                    "Ngoại lệ là những ngày không khớp: thiếu giờ ra, đi trễ không lý do. Mỗi ngoại lệ thành một cờ cảnh báo ở tab Chốt kỳ.")))}</p>
            </div>
            <div class="lrn-grid g2 top">
                <div class="lrn-panel" data-coach="wf-leave-queue">
                    <div class="lrn-zhead" data-coach="wf-timeoff">
                        <h3>${ic("calendar")}${esc(tx(B("Time Off", "Nghỉ phép")))}</h3><span class="lrn-push"></span>
                        <button class="lrn-btn sm ghost">${ic("user-plus")}${esc(tx(B("Apply on behalf", "Đăng ký thay")))}</button>
                    </div>
                    <span class="lrn-sub2">${esc(tx(B("Approval queue", "Hàng chờ phê duyệt")))}</span>
                    <div class="lrn-rows">${leave}</div>
                </div>
                <div class="lrn-panel" data-coach="wf-overtime">
                    <h3>${ic("zap")}${esc(tx(B("Overtime", "Tăng ca")))}</h3>
                    <div class="lrn-ynums">${otn}</div>
                    <div data-coach="wf-ot-queue">
                        <span class="lrn-sub2">${esc(tx(B("Approval queue", "Hàng chờ duyệt")))}</span>
                        <div class="lrn-rows">${ot}</div>
                    </div>
                    <div class="lrn-yrules" data-coach="wf-ot-rules">${caps}</div>
                </div>
            </div>`;
    },

    /* ---------------------------------------------- Workforce › Close
       The replica a learner can press: flags, the payroll handoff, and the
       lock that stays grey until every flag has an answer. */
    wfclose() {
        const c = PRACTICE.wfclose;
        const flags = c.flags.map((f, i) => `
            <div class="lrn-row" ${i === 0 ? ATTR_WF_FLAG : ""}>
                <span class="lrn-chip warn">${esc(tx(f.kind))}</span>
                <span><span class="lrn-nm">${esc(f.name)}</span><br><span class="lrn-sub2">${esc(tx(f.day))}</span></span>
                <span class="lrn-rr">
                    <button class="lrn-btn sm ghost" ${i === 0 ? ATTR_WF_FIX : ""}>${esc(tx(B("Fix", "Điều chỉnh")))}</button>
                    <button class="lrn-btn sm" ${i === 0 ? ATTR_WF_ASIS : ""}>${esc(tx(B("Approve as-is", "Phê duyệt nguyên trạng")))}</button>
                </span>
            </div>`).join("");
        const hand = c.handoff.map(([k, v]) => `<div class="lrn-kv2"><span>${esc(tx(k))}</span><b>${esc(v)}</b></div>`).join("");
        return `
            <div class="lrn-zhead" data-coach="wf-close">
                <h3>${ic("lock")}${esc(tx(c.week))}</h3>
                <span class="lrn-chip warn">${esc(N(c.flags.length))}${SP}${esc(tx(B("flagged", "bị gắn cờ")))}</span>
            </div>
            <div class="lrn-ywf">
                <div class="lrn-panel lrn-ywfmain" data-coach="wf-close-flags">
                    <div class="lrn-zhead"><b>${esc(tx(B("Flags this week", "Cờ cảnh báo tuần này")))}</b><span class="lrn-push"></span>
                        <button class="lrn-btn sm ghost">${esc(tx(B("Review all", "Xem lại tất cả")))}${SP}${esc(N(c.flags.length))}</button></div>
                    <div class="lrn-rows">${flags}</div>
                </div>
                <aside class="lrn-panel lrn-ydock" data-coach="wf-close-handoff">
                    <h3>${ic("send")}${esc(tx(B("Payroll handoff", "Chuyển giao tiền lương")))}</h3>
                    ${hand}
                    <button class="lrn-btn pri" disabled="disabled" data-coach="wf-close-lock">${ic("lock")}${
                        esc(tx(B("Lock week & send to payroll", "Khóa tuần và gửi vào bảng lương")))}</button>
                    <p class="lrn-note">${esc(tx(B("Clear or review every flag first.", "Hãy xử lý hoặc xem lại mọi cờ cảnh báo trước.")))}</p>
                    <div class="lrn-ylocked" data-coach="rep-wf-locked">${ic("check-circle")}<span><b>${esc(tx(B("Week locked", "Tuần bị khóa")))}</b>${SP}${
                        esc(tx(B("— what it looks like afterwards. Reopen… asks for a reason.", "— trông như thế này sau khi khoá. Mở lại… sẽ hỏi lý do.")))}</span></div>
                </aside>
            </div>`;
    },

    /* ------------------------------------ Settings › Access & delegation */
    access() {
        /* biz_access has no Vietnamese yet: the real screen is English for
           every reader, so the drawing is too (owner item, ledger LR33). */
        const a = PRACTICE.access;
        const tabs = ["Roles", "People", "Screens", "Hand-overs"]
            .map((x, i) => `<button class="lrn-lens ${i === 0 ? "on" : ""}">${esc(x)}</button>`).join("");
        const roles = a.roles.map((r) => `
            <div class="lrn-yrole">
                <b>${ic("key")}${esc(tx(r.name))}</b>
                <span class="lrn-sub2">${esc(tx(r.line))}</span>
                <span class="lrn-chip">${ic("users")}Held by${SP}${esc(N(r.held))}${SP}people</span>
            </div>`).join("");
        return `
            <div class="lrn-zhead" data-coach="ac-head">
                <h3>${ic("key")}Access</h3>
                <span class="lrn-push"></span>
                <button class="lrn-btn sm ghost" data-coach="ac-seeas">${ic("eye")}See it as</button>
                <button class="lrn-btn sm ghost">Who holds what</button>
                <button class="lrn-btn sm" data-coach="ac-handover">${ic("repeat")}Hand my access over</button>
                <button class="lrn-btn sm pri" data-coach="ac-newrole">${ic("plus")}New role</button>
            </div>
            <div class="lrn-zmodes" data-coach="ac-tabs">${tabs}</div>
            <div class="lrn-yroles" data-coach="ac-rolecard">${roles}</div>
            <div class="lrn-panel lrn-zdialog" data-coach="rep-ac-handover">
                <h3>${ic("repeat")}Hand my access over${SP}·${SP}${esc(tx(B("drawn open", "đang mở sẵn")))}</h3>
                <div class="lrn-kv2"><span>Who</span><b>${esc(a.handover.to)}</b></div>
                <div class="lrn-kv2"><span>What</span><b>All my roles</b></div>
                <div class="lrn-kv2"><span>Until</span><b>${esc(a.handover.until)}</b></div>
                <p class="lrn-note">Taken back automatically the morning after the end date.</p>
                <button class="lrn-btn sm pri">Hand it over</button>
            </div>`;
    },

    /* ------------------------------------- Compliance › Generate a filing
       The flow a Filings tile opens: Choose the filing → Scope → Generate. */
    filing_flow() {
        const g = PRACTICE.govreports;
        const steps = [B("Choose the filing", "Chọn hồ sơ"), B("Scope", "Phạm vi"), B("Generate", "Tạo")]
            .map((x, i) => `<div class="lrn-zrailrow ${i === 0 ? "done" : i === 1 ? "cur" : ""}">
                <span class="lrn-wdot">${i === 0 ? ic("check") : i + 1}</span><span><b>${esc(tx(x))}</b></span></div>`).join("");
        const first = g.groups[0].reports[0];
        return `
            <div class="lrn-zbp lrn-y2col">
                <nav class="lrn-zbprail" data-coach="cp-gen-steps">
                    <span class="lrn-zeyebrow">${esc(tx(B("Generate a filing", "Tạo hồ sơ")))}</span>${steps}</nav>
                <div class="lrn-panel" data-coach="cp-generate">
                    <div class="lrn-kv2"><span>${esc(tx(B("Filing", "Hồ sơ")))}</span><b>${esc(first.en)}${SP}·${SP}${esc(first.vi)}</b></div>
                    <div class="lrn-kv2"><span>${esc(tx(B("Company", "Công ty")))}</span><b>Hoa Sen Retail Co.</b></div>
                    <div class="lrn-kv2"><span>${esc(tx(B("Month", "Tháng")))}</span><b>${esc(tx(g.period))}</b></div>
                    <div class="lrn-strip">
                        <button class="lrn-btn sm ghost">${esc(tx(B("Back", "Quay lại")))}</button>
                        <button class="lrn-btn sm pri" data-coach="cp-gen-go">${esc(tx(B("Generate", "Tạo")))}</button>
                    </div>
                    <p class="lrn-note">${esc(tx(B("Generating makes the files for you to download. Nothing is sent anywhere.",
                        "Tạo hồ sơ chỉ sinh ra các tệp để bạn tải xuống. Không có gì được gửi đi đâu cả.")))}</p>
                </div>
            </div>`;
    },

    /* ------------------------------ Compliance › Bank, Young workers, Audit */
    compliancemore() {
        const c = PRACTICE.compliance;
        const bank = c.bank.map(([k, v], i) => `${i ? `<span class="lrn-rline"></span>` : ""}<span class="lrn-ystage"><b>${esc(N(v))}</b>${esc(tx(k))}</span>`).join("");
        const young = c.young.map(([k, v]) => kpiTile("shield-check", "", N(v), k)).join("");
        const audit = c.audit.map(([k, v]) => kpiTile("eye", "", N(v), k)).join("");
        return `
            <div class="lrn-panel" data-coach="cp-bank">
                <h3>${ic("landmark")}${esc(tx(B("Bank", "Ngân hàng")))}</h3>
                <div class="lrn-ystages" data-coach="cp-bank-steps">${bank}</div>
                <div class="lrn-panel lrn-zdrop" data-coach="cp-bank-new">
                    <h3>${ic("upload")}${esc(tx(B("New bank-change request", "Yêu cầu thay đổi ngân hàng mới")))}</h3>
                    <p class="lrn-note">${esc(tx(B("Drop a bank confirmation letter, statement or passbook.",
                        "Thả thư xác nhận của ngân hàng, sao kê hoặc sổ tiết kiệm vào đây.")))}</p>
                </div>
            </div>
            <div class="lrn-grid g2 top">
                <div class="lrn-panel" data-coach="cp-young"><h3>${ic("shield-check")}${esc(tx(B("Young workers", "Lao động chưa thành niên")))}</h3>
                    <div class="lrn-grid g4">${young}</div></div>
                <div class="lrn-panel" data-coach="cp-audit"><h3>${ic("eye")}${esc(tx(B("Audit", "Nhật ký kiểm toán")))}</h3>
                    <div class="lrn-grid g4">${audit}</div></div>
            </div>`;
    },

    /* ------------------------------- Home › Wall and the rest of People */
    peoplemore() {
        const m = PRACTICE.more;
        const tiles = m.tiles.map(([k, v]) => `<div class="lrn-ztile"><b>${esc(tx(k))}</b><span class="lrn-sub2">${esc(tx(v))}</span></div>`).join("");
        return `
            <div class="lrn-panel" data-coach="rep-pm-wall">
                <h3>${ic("heart")}${esc(tx(B("What people said about each other", "Mọi người nói gì về nhau")))}</h3>
                <div class="lrn-yrole">
                    <b>${esc(m.praise.from)}${SP}${ic("arrow-right")}${SP}${esc(m.praise.to)}</b>
                    <span class="lrn-sub2">${esc(tx(m.praise.text))}</span>
                    <span class="lrn-chip ok">${esc(tx(m.praise.value))}</span>
                </div>
                <button class="lrn-btn sm pri">${ic("heart")}${esc(tx(B("Say thank you", "Nói lời cảm ơn")))}</button>
            </div>
            <div class="lrn-ztiles" data-coach="rep-pm-tiles">${tiles}</div>`;
    },

    /* ------------------------------------------ People › Pay › Bands
       One family, three bands, everybody placed. The picture is a range per
       band with a dot per person; a dot outside its range says so. */
    paybands() {
        const b = PRACTICE.paybands;
        const lo = Math.min(...b.bands.map((x) => x.min)) * 0.92;
        const hi = Math.max(...b.bands.map((x) => x.max)) * 1.04;
        const at = (v) => Math.round((v - lo) / (hi - lo) * 1000) / 10;
        const rows = b.bands.map((band) => {
            const below = band.people.filter((x) => x.pay < band.min).length;
            const dots = band.people.map((x) => `<i class="lrn-ydot ${x.pay < band.min ? "out" : ""}" style="left:${at(x.pay)}%"
                title="${esc(x.name + DOT + M(x.pay))}"></i>`).join("");
            return `<div class="lrn-yband">
                <span class="lrn-nm">${esc(tx(band.level))}</span>
                <span class="lrn-ytrack"><i class="lrn-yrange" style="left:${at(band.min)}%;width:${at(band.max) - at(band.min)}%"></i>
                    <i class="lrn-ymid" style="left:${at(band.mid)}%"></i>${dots}</span>
                <span>${below ? `<span class="lrn-chip warn">${esc(N(below))}${SP}${esc(tx(B("below", "dưới")))}</span>` : ""}</span>
            </div>`;
        }).join("");
        const health = b.health.map((h) => `<div class="lrn-kv2"><span>${esc(tx(h.k))}</span><b class="${h.tone === "warn" ? "lrn-yw" : ""}">${
            esc(typeof h.v === "number" ? N(h.v) : h.v)}</b></div>`).join("");
        return `
            ${payTabs(0)}
            <div class="lrn-zhead" data-coach="pp-bands-tools">
                <span class="lrn-chip b">${ic("layers")}${esc(tx(b.family))}</span><span class="lrn-push"></span>
                <button class="lrn-btn sm ghost">${ic("rotate-ccw")}${esc(tx(B("Work it out again", "Tính lại")))}</button>
                <button class="lrn-btn sm ghost">${ic("download")}${esc(tx(B("Export", "Xuất ra")))}</button>
                <button class="lrn-btn sm ghost">${ic("upload")}${esc(tx(B("Import", "Nhập vào")))}</button>
                <button class="lrn-btn sm pri">${ic("user-plus")}${esc(tx(B("Place a new hire", "Xếp lương người mới")))}</button>
            </div>
            <div class="lrn-grid g2 top">
                <div class="lrn-panel" data-coach="pp-band-picture">
                    <h3>${ic("bar-chart")}${esc(tx(B("The band picture", "Bức tranh khoảng lương")))}</h3>
                    <div class="lrn-ybands">${rows}</div>
                    <p class="lrn-note">${esc(tx(B("The shaded range is the band; the tick is its middle; each dot is a person.",
                        "Phần tô màu là khoảng lương; vạch là điểm giữa; mỗi chấm là một người.")))}</p>
                </div>
                <div class="lrn-panel" data-coach="pp-health">
                    <h3>${ic("lightbulb")}${esc(tx(B("Worth knowing", "Đáng biết")))}</h3>
                    ${health}
                    <p class="lrn-note">${esc(tx(B("Nothing here changes anybody's pay.", "Không có gì ở đây thay đổi lương của ai.")))}</p>
                </div>
            </div>
            <div class="lrn-panel" data-coach="pp-fairness">
                <h3>${ic("scale")}${esc(tx(B("Fairness", "Công bằng")))}</h3>
                <div class="lrn-kv2"><span>${esc(tx(B("Pay gap by gender", "Chênh lệch lương theo giới")))}${DOT}${esc(tx(B("Across everybody", "Trên toàn bộ nhân sự")))}</span><b>${esc(b.fairness.gap)}</b></div>
                <p class="lrn-note">${esc(tx(B("Worked out when you open it, never stored. Print the statement to keep one.",
                    "Được tính khi bạn mở, không bao giờ được lưu. In bản tường trình nếu muốn giữ lại.")))}</p>
            </div>`;
    },

    /* ------------------------------------------ People › Pay › Review
       The worksheet a learner can press. THE HERO: the budget meter carries
       its before and after (data-from / data-to) so the lesson can fill it
       as the rises go in (visuals.js runMeter). */
    payreview() {
        const r = PRACTICE.payreview;
        const pct = Math.round(r.used / r.budget * 100);
        const stages = r.stages.map((x, i) => `<span class="lrn-ystage ${i === r.at ? "on" : ""}">${esc(tx(x))}</span>`).join(`<span class="lrn-rline"></span>`);
        const band = { line: B("in line with the others", "ngang với những người khác"), out: B("stands out", "nổi bật") };
        const rows = r.rows.map((x) => {
            const rise = r.rise(x);
            const mid = x.emp.base >= 13000000 ? 15000000 : x.emp.base >= 10500000 ? 12500000 : 10000000;
            return `<tr>
                <td><b>${esc(x.emp.name)}</b>${x.below ? `<br><span class="lrn-chip warn">${esc(tx(B("Paid below the band", "Được trả dưới khoảng lương")))}</span>` : ""}</td>
                <td>${esc(N(x.score))}</td>
                <td>${esc(N(Math.round(x.emp.base / mid * 100)))}%</td>
                <td>${esc(M(x.emp.base))}</td>
                <td>${esc(N(x.pct))}%</td>
                <td><b>${esc(M(rise))}</b></td>
                <td>${esc(M(x.emp.base + rise))}</td>
                <td><span class="lrn-chip ${x.mark === "out" ? "warn" : "ok"}">${esc(tx(band[x.mark]))}</span></td>
            </tr>`;
        }).join("");
        const cols = [B("Person", "Người"), B("Score", "Điểm đánh giá"), B("In the band", "Trong khoảng lương"), B("Paid now", "Đang được trả"),
                      B("Rise", "Mức tăng"), B("Rise", "Mức tăng"), B("New pay", "Lương mới"), B("Calibration", "Cân chỉnh")];
        cols[4] = B("Guidance", "Hướng dẫn");
        return `
            ${payTabs(2)}
            <div class="lrn-zhead" data-coach="pp-reviews">
                <h3>${ic("trending-up")}${esc(tx(r.name))}</h3><span class="lrn-push"></span>
                <button class="lrn-btn sm ghost">${esc(tx(B("Set up guidance", "Thiết lập hướng dẫn")))}</button>
                <button class="lrn-btn sm">${ic("plus")}${esc(tx(B("New review", "Đợt xét lương mới")))}</button>
            </div>
            <div class="lrn-ystages" data-coach="pp-stepper">${stages}</div>
            <div class="lrn-grid g3" data-coach="pp-meters">
                <div class="lrn-kpi" data-coach="rep-pr-budget">
                    <div class="lrn-kt">${ic("banknote")}<span>${esc(tx(B("Budget", "Ngân sách")))}</span></div>
                    <div class="lrn-kv"><span data-meternum="1" data-from="0" data-to="${r.used}" data-cap="${r.budget}">${esc(M(r.used))}</span></div>
                    <div class="lrn-ymeter"><i data-meterfill="1" style="width:${pct}%"></i></div>
                    <div class="lrn-ksub">${esc(tx(B("of", "trên")))}${SP}${esc(M(r.budget))}${DOT}${esc(N(r.budgetPct))}%${SP}${esc(tx(B("of the wage bill", "quỹ lương")))}</div>
                </div>
                ${kpiTile("scale", "", "0", B("Fairness", "Công bằng"))}
                ${kpiTile("star", "", N(r.rows.length) + " / " + N(r.rows.length), B("Scores", "Điểm đánh giá"))}
            </div>
            <div class="lrn-ywf">
                <div class="lrn-panel lrn-ywfmain" data-coach="pp-worksheet">
                    <div class="lrn-strip">${[B("Everybody", "Tất cả mọi người"), B("My team", "Nhóm của tôi"), B("Not scored", "Chưa chấm điểm"),
                        B("Stops approval", "Chặn duyệt"), B("Paid below the band", "Được trả dưới khoảng lương"), B("No rise", "Không tăng")]
                        .map((f, i) => `<span class="lrn-chip ${i === 0 ? "b" : ""}">${esc(tx(f))}</span>`).join("")}</div>
                    <div class="lrn-ztablewrap"><table class="lrn-ztable">
                        <thead><tr>${cols.map((c) => `<th>${esc(tx(c))}</th>`).join("")}</tr></thead>
                        <tbody>${rows}</tbody>
                    </table></div>
                </div>
                <aside class="lrn-panel lrn-ydock">
                    <div class="lrn-ytools" data-coach="pp-bulk">
                        <button class="lrn-btn sm pri" ${ATTR_PR_GUIDE}>${esc(tx(B("Use the guidance", "Dùng hướng dẫn")))}</button>
                        <button class="lrn-btn sm ghost">${esc(tx(B("Add 1%", "Thêm 1%")))}</button>
                        <button class="lrn-btn sm ghost">${esc(tx(B("Take off 1%", "Bớt 1%")))}</button>
                        <button class="lrn-btn sm ghost">${esc(tx(B("Share out what is left", "Chia phần còn lại")))}</button>
                        <button class="lrn-btn sm" ${ATTR_PR_CAL}>${ic("scale")}${esc(tx(B("Calibration", "Cân chỉnh")))}</button>
                    </div>
                    <div class="lrn-yclean" data-coach="pp-calibration">
                        <b>${esc(tx(B("Worth a second look", "Đáng xem lại")))}</b>
                        <p class="lrn-note">${esc(EMP.trang.name)}${DOT}${esc(tx(B("top score, smallest rise — stands out", "điểm cao nhất, mức tăng nhỏ nhất — nổi bật")))}</p>
                    </div>
                    <div class="lrn-yclean" data-coach="pp-stops">
                        <b>${esc(tx(B("What stops approval", "Điều gì chặn duyệt")))}</b>
                        <p class="lrn-note">${esc(tx(B("Nothing. Within the budget, everybody scored, no limit broken.",
                            "Không có gì. Trong ngân sách, mọi người đã được chấm điểm, không vượt giới hạn nào.")))}</p>
                    </div>
                    <div class="lrn-strip" data-coach="pp-review-actions">
                        <button class="lrn-btn sm pri" ${ATTR_PR_SEND}>${ic("send")}${esc(tx(B("Send for approval", "Gửi duyệt")))}</button>
                    </div>
                </aside>
            </div>`;
    },

    /* ------------------------------------------------- People › Plan */
    decisionroom() {
        const d = PRACTICE.decisionroom;
        const presets = d.presets.map((x) => `<button class="lrn-btn sm ghost">${esc(tx(x))}</button>`).join("");
        const levers = d.levers.map(([k, v]) => `<div class="lrn-kv2"><span>${esc(tx(k))}</span><b>${esc(v)}</b></div>`).join("");
        const tabs = d.results.map((x, i) => `<button class="lrn-lens ${i === 1 ? "on" : ""}">${esc(tx(x))}</button>`).join("");
        const diff = Math.abs(d.exact - d.estimate) / d.estimate * 100;
        const exact = tx(B("Exact cost", "Chi phí chính xác")) + SP + M(d.exact) + DOT + tx(B("the estimate was", "ước tính là"))
            + SP + M(d.estimate) + SP + "(±" + P(Math.round(diff * 10) / 10) + ")";
        return `
            <div class="lrn-zhead" data-coach="dr-head">
                <div><span class="lrn-zeyebrow">${esc(tx(B("Decision Room", "Phòng quyết định")))}</span>
                    <h3>${esc(tx(B("See the year before you commit to it.", "Nhìn thấy cả năm trước khi bạn cam kết.")))}</h3></div>
                <span class="lrn-push"></span>
                <button class="lrn-btn sm ghost">${ic("undo")}${esc(tx(B("Undo", "Hoàn tác")))}</button>
                <button class="lrn-btn sm ghost">${esc(tx(B("Reset", "Đặt lại")))}</button>
                <button class="lrn-btn sm pri">${esc(tx(B("Save plan", "Lưu kế hoạch")))}</button>
            </div>
            <div class="lrn-ywf">
                <div class="lrn-panel lrn-ywfmain" data-coach="dr-levers">
                    <span class="lrn-zeyebrow">${esc(tx(B("What if we…", "Nếu chúng ta…")))}</span>
                    <div class="lrn-strip" data-coach="dr-presets">${presets}</div>
                    ${levers}
                    <p class="lrn-note">${esc(tx(B("Explore freely. Nothing here changes payroll.", "Cứ thoải mái khám phá. Không có gì ở đây thay đổi bảng lương.")))}</p>
                </div>
                <aside class="lrn-panel lrn-ydock" data-coach="dr-goals">
                    <h3>${ic("target")}${esc(tx(B("Your definition of a good year", "Định nghĩa của bạn về một năm tốt")))}</h3>
                    <p class="lrn-note">${esc(tx(B("Six goals. The room keeps score.", "Sáu mục tiêu. Căn phòng tự chấm điểm.")))}</p>
                </aside>
            </div>
            <div class="lrn-zmodes" data-coach="dr-results">${tabs}</div>
            <div class="lrn-panel" data-coach="dr-compare">
                <h3>${ic("git-merge")}${esc(tx(B("Compare possibilities, with confidence.", "So sánh các khả năng, một cách tự tin.")))}</h3>
                <div class="lrn-kv2"><span>${esc(tx(B("Grow thoughtfully", "Tăng trưởng thận trọng")))}</span><b>${esc(M(d.estimate))}</b></div>
                <div class="lrn-strip">
                    <button class="lrn-btn sm" data-coach="dr-exact">${ic("calculator")}${esc(tx(B("Exact cost", "Chi phí chính xác")))}</button>
                    <button class="lrn-btn sm pri" data-coach="dr-propose">${ic("send")}${esc(tx(B("Propose", "Đề xuất")))}</button>
                    <button class="lrn-btn sm ghost" data-coach="dr-brief">${ic("download")}${esc(tx(B("Export the decision brief", "Xuất bản tóm tắt quyết định")))}</button>
                </div>
                <p class="lrn-note" data-coach="rep-dr-exact">${esc(exact)}</p>
            </div>`;
    },

    /* --------------------------------------------- Lifecycle › Hiring
       The board a learner can press: Raise a hiring request opens the
       wizard (hiring_request); every role card says its step and what next. */
    hiring() {
        const h = PRACTICE.hiring;
        const roles = h.roles.map((r, i) => `
            <div class="lrn-yrole">
                <b>${ic("briefcase")}${esc(tx(r.title))}</b>
                <span class="lrn-sub2">${esc(tx(B("Step", "Bước")))}${SP}${esc(N(r.step))}${SP}${esc(tx(B("of 4", "của 4")))}${
                    r.cands ? DOT + esc(N(r.cands)) + SP + esc(tx(B("candidates", "ứng viên"))) : ""}</span>
                <span class="lrn-ynext" ${i === 0 ? ATTR_HI_NEXT : ""}><b>${esc(tx(B("Next:", "Tiếp theo:")))}</b>${SP}${esc(tx(r.next))}</span>
            </div>`).join("");
        const stages = h.stages.map((x, i) => `<span class="lrn-chip ${i === 4 ? "b" : ""}">${esc(tx(x))}</span>`).join("");
        return `
            <div class="lrn-zhead">
                <span class="lrn-push"></span>
                <button class="lrn-btn sm ghost" data-coach="hi-tools">${ic("settings")}${esc(tx(B("Hiring tools", "Công cụ tuyển dụng")))}</button>
                <button class="lrn-btn sm pri" data-coach="hi-raise" ${navAttr("hiring_request")}>${ic("plus")}${esc(tx(B("Raise a hiring request", "Đề xuất tuyển dụng")))}</button>
            </div>
            ${quietNums(h.numbers, ATTR_HI_NUMS)}
            <div class="lrn-steps" data-coach="hi-steps">${stepButtons(h.steps.map(([l, c], i) => ({ label: l, count: c, on: i === 2 })), B("", ""))}</div>
            <div class="lrn-zmodes" data-coach="hi-tabs"><button class="lrn-lens on">${esc(tx(B("Roles", "Vai trò")))}</button><button class="lrn-lens">${
                esc(tx(B("Interviews", "Phỏng vấn")))}</button></div>
            <div class="lrn-yroles" data-coach="hi-row">${roles}</div>
            <div class="lrn-panel" data-coach="rep-hi-cands">
                <h3>${ic("users")}${esc(tx(h.roles[0].title))}${DOT}${esc(tx(B("candidates", "ứng viên")))}</h3>
                <div class="lrn-strip">${stages}</div>
                <div class="lrn-row"><span class="lrn-avatar">${esc(initial(LATER.name))}</span>
                    <span><span class="lrn-nm">${esc(LATER.name)}</span><br><span class="lrn-sub2">${esc(tx(h.stages[4]))}</span></span>
                    <span class="lrn-rr"><button class="lrn-btn sm" data-coach="hi-stage">${esc(tx(B("Move stage", "Chuyển giai đoạn")))}</button></span></div>
            </div>`;
    },

    /* The request wizard, drawn open over the board. */
    hiring_request() {
        const w = PRACTICE.hiring.wizard;
        // The wizard's step names are written in code and never translated
        // on the real screen, so the drawing shows them in English too.
        const tabs = w.tabs.map((x, i) => `<button class="lrn-lens ${i === 3 ? "on" : ""}">${esc(x.en)}</button>`).join("");
        const route = w.route.map((x, i) => `${i ? `<span class="lrn-rline"></span>` : ""}<span class="lrn-ystage">${esc(tx(x))}</span>`).join("");
        return `
            <div class="lrn-panel lrn-zdialog" data-coach="hi-wizard">
                <span class="lrn-zeyebrow">${esc(tx(B("Build your team", "Xây dựng đội ngũ")))}</span>
                <h3>${esc(tx(w.title))}</h3>
                <div class="lrn-zmodes">${tabs}</div>
                <div class="lrn-kv2"><span>${esc(tx(B("Role", "Vị trí")))}</span><b>${esc(tx(PRACTICE.hiring.roles[0].title))}</b></div>
                <div class="lrn-kv2"><span>${esc(tx(B("Monthly salary", "Lương tháng")))}</span><b>${esc(M(w.salary))}</b></div>
                <div class="lrn-kv2"><span>${esc(tx(B("Within budget", "Trong ngân sách")))}</span><b>${esc(tx(B("Yes", "Có")))}</b></div>
                <span class="lrn-sub2">${esc(tx(B("Who signs it off", "Ai phê duyệt")))}</span>
                <div class="lrn-ystages" data-coach="rep-hi-route">${route}</div>
                <div class="lrn-strip">
                    <button class="lrn-btn sm ghost" ${navAttr("hiring")}>${esc(tx(B("Back", "Quay lại")))}</button>
                    <button class="lrn-btn sm pri" data-coach="rep-hi-send">${ic("send")}${esc(tx(B("Send for approval", "Gửi phê duyệt")))}</button>
                </div>
            </div>`;
    },

    /* ------------------------------------------ Lifecycle › New joiners */
    joiners() {
        const j = PRACTICE.joiners;
        const cards = j.rows.map((r) => `
            <div class="lrn-yrole">
                <b>${esc(r.name)}</b><span class="lrn-sub2">${esc(tx(r.sub))}</span>
                <span class="lrn-chip ${r.warn ? "warn" : "ok"}">${esc(tx(r.chip))}</span>
            </div>`).join("");
        const li = (xs, done) => xs.map((x) => `<div class="lrn-kv2"><span>${done ? ic("check") : ic("clock")}${esc(tx(x))}</span></div>`).join("");
        return `
            <div class="lrn-zhead"><span class="lrn-push"></span>
                <button class="lrn-btn sm" data-coach="nj-run">${ic("play")}${esc(tx(B("Run today's steps", "Chạy các bước hôm nay")))}</button></div>
            ${quietNums(j.numbers, ATTR_NJ_NUMS)}
            <div class="lrn-steps" data-coach="nj-steps">${stepButtons(j.steps.map(([l, c], i) => ({ label: l, count: c, on: i === 0 })), B("", ""))}</div>
            <div class="lrn-ywf">
                <div class="lrn-yroles lrn-ywfmain" data-coach="nj-list">${cards}</div>
                <aside class="lrn-panel lrn-ydock" data-coach="nj-drawer">
                    <h3>${esc(LATER.name)}</h3>
                    <div class="lrn-strip" data-coach="nj-buddy"><span class="lrn-chip">${esc(tx(B("HR contact", "Liên hệ nhân sự")))}</span><span class="lrn-chip ok">${
                        esc(tx(B("Buddy", "Người đồng hành")))}:${SP}${esc(EMP.mai.name)}</span></div>
                    <b>${esc(tx(B("Still to do", "Còn phải làm")))}</b>${li(j.todo, false)}
                    <b>${esc(tx(B("Done", "Hoàn tất")))}</b>${li(j.done, true)}
                    <b>${esc(tx(B("Conversations", "Trao đổi")))}</b>
                </aside>
            </div>`;
    },

    /* --------------------------------------------- Lifecycle › Probation */
    probation() {
        const p = PRACTICE.probation;
        const cards = p.rows.map((r) => `<div class="lrn-yrole"><b>${esc(r.name)}</b><span class="lrn-sub2">${esc(tx(r.sub))}</span></div>`).join("");
        const verdicts = p.verdicts.map((v, i) => `<button class="lrn-btn sm ${i === 0 ? "pri" : "ghost"}">${esc(tx(v))}</button>`).join("");
        return `
            ${quietNums(p.numbers, ATTR_PR_NUMS)}
            <div class="lrn-steps" data-coach="pr-steps">${stepButtons(p.steps.map(([l, c], i) => ({ label: l, count: c, on: i === 3 })), B("", ""))}</div>
            <div class="lrn-ywf">
                <div class="lrn-yroles lrn-ywfmain" data-coach="pr-list">${cards}</div>
                <aside class="lrn-panel lrn-ydock">
                    <h3>${esc(LATER.name)}</h3>
                    <div class="lrn-kv2" data-coach="pr-peers"><span>${esc(tx(B("Colleagues asked", "Đồng nghiệp được hỏi")))}</span><b>${esc(tx(B("3 of 4 answered", "3/4 đã trả lời")))}</b></div>
                    <span class="lrn-sub2">${esc(tx(B("Decide", "Quyết định")))}</span>
                    <div class="lrn-strip" data-coach="pr-verdict">${verdicts}</div>
                </aside>
            </div>`;
    },

    /* ------------------------------------------ Lifecycle › Growth plans */
    growth() {
        const g = PRACTICE.growth;
        const cards = g.rows.map((r) => `<div class="lrn-yrole"><b>${esc(r.name)}</b><span class="lrn-sub2">${esc(tx(r.sub))}</span></div>`).join("");
        const states = [[B("On track", "Đúng hướng"), "ok"], [B("On track", "Đúng hướng"), "ok"], [B("At risk", "Có rủi ro"), "warn"]]
            .map(([l, t]) => `<span class="lrn-chip ${t}">${esc(tx(l))}</span>`).join("");
        return `
            ${quietNums(g.numbers, ATTR_GW_NUMS)}
            <div class="lrn-steps" data-coach="gw-steps">${stepButtons(g.steps.map(([l, c], i) => ({ label: l, count: c, on: i === 2 })), B("", ""))}</div>
            <div class="lrn-yroles" data-coach="gw-list">${cards}</div>
            <div class="lrn-panel" data-coach="gw-objectives">
                <h3>${ic("sprout")}${esc(tx(B("What has to change", "Điều cần thay đổi")))}</h3>
                <div class="lrn-strip">${states}</div>
            </div>`;
    },

    /* ----------------------------------------- Lifecycle › Contracts */
    contractends() {
        const c = PRACTICE.contractends;
        const cards = c.rows.map((r) => `<div class="lrn-yrole"><b>${esc(r.name)}</b><span class="lrn-sub2">${esc(tx(r.sub))}</span></div>`).join("");
        const choices = c.choices.map((v, i) => `<button class="lrn-btn sm ${i === 0 ? "pri" : "ghost"}">${esc(tx(v))}</button>`).join("");
        return `
            ${quietNums(c.numbers, ATTR_CL_NUMS)}
            <div class="lrn-steps" data-coach="cl-steps">${stepButtons(c.steps.map(([l, n], i) => ({ label: l, count: n, on: i === 1 })), B("", ""))}</div>
            <div class="lrn-ywf">
                <div class="lrn-yroles lrn-ywfmain" data-coach="cl-list">${cards}</div>
                <aside class="lrn-panel lrn-ydock">
                    <h3>${esc(EMP.duc.name)}</h3>
                    <button class="lrn-btn sm" data-coach="cl-raise">${esc(tx(B("Raise the decision", "Nêu quyết định")))}</button>
                    <div class="lrn-strip" data-coach="cl-decide">${choices}</div>
                </aside>
            </div>`;
    },

    /* --------------------------------------------- Lifecycle › Exits
       The board a learner can press: four desks sign off, and the final
       settlement waits for all four — here, for Finance. */
    exits() {
        const e = PRACTICE.exits;
        const lights = e.desks.map((d) => `<span class="lrn-chip ${d.done ? "ok" : "warn"}">${d.done ? ic("check") : ic("clock")}${esc(tx(d.k))}</span>`).join("");
        const desks = e.desks.map((d) => `<div class="lrn-kv2"><span>${esc(tx(d.k))}</span><b class="${d.done ? "" : "lrn-yw"}">${esc(tx(d.what))}</b></div>`).join("");
        return `
            <div class="lrn-zhead"><span class="lrn-push"></span>
                <button class="lrn-btn sm">${ic("play")}${esc(tx(B("Run today's steps", "Chạy các bước hôm nay")))}</button></div>
            ${quietNums(e.numbers, ATTR_EX_NUMS)}
            <div class="lrn-steps" data-coach="ex2-steps">${stepButtons(e.steps.map(([l, c], i) => ({ label: l, count: c, on: i === 1 })), B("", ""))}</div>
            <div class="lrn-ywf">
                <div class="lrn-yroles lrn-ywfmain" data-coach="ex2-list">
                    <div class="lrn-yrole" ${ATTR_EX_CARD}>
                        <b>${ic("log-out")}${esc(e.leaver.name)}</b>
                        <span class="lrn-sub2">${esc(tx(e.leaver.role))}${DOT}${esc(tx(B("last day", "ngày làm cuối")))}${SP}${esc(e.leaver.last)}</span>
                        <span class="lrn-sub2">${esc(tx(B("Signed off by", "Được ký tắt bởi")))}</span>
                        <div class="lrn-strip" data-coach="ex2-clearance">${lights}</div>
                    </div>
                </div>
                <aside class="lrn-panel lrn-ydock" data-coach="rep-ex-desks">
                    <h3>${esc(e.leaver.name)}</h3>
                    ${desks}
                    <div class="lrn-yclean" data-coach="ex2-settle">
                        <p class="lrn-note">${esc(tx(B("The final settlement waits for all four.", "Quyết toán cuối cùng chờ đủ cả bốn bên.")))}</p>
                        <button class="lrn-btn sm pri" disabled="disabled">${esc(tx(B("Close settlement", "Chốt quyết toán")))}</button>
                        <button class="lrn-btn sm ghost" ${ATTR_EX_OPEN}>${esc(tx(B("Open the settlement", "Mở quyết toán")))}</button>
                    </div>
                    <div class="lrn-kv2" data-coach="ex2-handover"><span>${esc(tx(B("Handover", "Bàn giao công việc")))}</span><b>${esc(tx(B("2 of 3 done", "2/3 đã xong")))}</b></div>
                </aside>
            </div>`;
    },
};

/* ------------------------------------------ setup-replica helpers (step 3)
   Attributes held as constants for the same reason ATTR_IMPMATCH is: a
   quoted attribute inside an interpolation trips the minifier. */
const ATTR_BP_ADDED = 'data-coach="rep-bp-added"';
const ATTR_JNY_FILE = 'data-coach="rep-jny-file"';
const ATTR_JNY_FEED = 'data-coach="rep-jny-feed"';
const ATTR_JNY_SCHEME = 'data-coach="rep-jny-scheme"';
const ATTR_AM_PAYROW = 'data-coach="rep-am-payrow"';
/* LEARN REFRESH step 4 — attributes drawn inside an interpolation, held as
   constants for the same minifier reason as the step 3 ones above. */
const ATTR_PR_GUIDE = 'data-coach="rep-pr-guide"';
const ATTR_PR_CAL = 'data-coach="rep-pr-cal"';
const ATTR_PR_SEND = 'data-coach="rep-pr-send"';
const ATTR_HI_NEXT = 'data-coach="hi-next"';
const ATTR_HI_NUMS = 'data-coach="hi-numbers"';
const ATTR_NJ_NUMS = 'data-coach="nj-numbers"';
const ATTR_PR_NUMS = 'data-coach="pr-numbers"';
const ATTR_GW_NUMS = 'data-coach="gw-numbers"';
const ATTR_CL_NUMS = 'data-coach="cl-numbers"';
const ATTR_EX_NUMS = 'data-coach="ex2-numbers"';
const ATTR_EX_CARD = 'data-coach="rep-ex-card"';
const ATTR_EX_OPEN = 'data-coach="rep-ex-open"';

/* The quiet numbers row every Lifecycle board opens with: small, grey, one
   line — a count and its words, never a tile. `attr` is the board's own
   anchor (a constant above, so the registry scan sees it). */
function quietNums(list, attr) {
    return `<div class="lrn-ynums" ${attr}>${list.map(([k, v]) => `<span><b>${esc(N(v))}</b>${SP}${esc(tx(k))}</span>`).join("")}</div>`;
}

/* People › Pay's own tabs: Bands, Fairness, Review, Changes. */
function payTabs(on) {
    const tabs = [B("Bands", "Khoảng lương"), B("Fairness", "Công bằng"), B("Review", "Xét lương"), B("Changes", "Thay đổi")];
    const screens = ["paybands", "paybands", "payreview", "payreview"];
    return `<div class="lrn-zmodes" data-coach="pp-tabs">${tabs.map((t, i) => `<button class="lrn-lens ${i === on ? "on" : ""}" ${
        navAttr(screens[i])}>${esc(tx(t))}</button>`).join("")}</div>`;
}
const ATTR_WF_FLAG = 'data-coach="rep-wf-flag"';
const ATTR_WF_FIX = 'data-coach="rep-wf-fix"';
const ATTR_WF_ASIS = 'data-coach="rep-wf-asis"';


function bpTop(b) {
    return `<div class="lrn-zhead">
        <b>${esc(b.name)}</b><code class="lrn-faint">${esc(b.code)}</code>
        <span class="lrn-push"></span>
        <span class="lrn-chip ok" data-coach="bp-status">${esc(tx(b.saved))}</span>
        <button class="lrn-btn sm ghost">${esc(tx(B("Skip to the grid", "Chuyển đến lưới")))}</button>
        <button class="lrn-btn sm">${esc(tx(B("Save & close", "Lưu và đóng")))}</button>
    </div>`;
}

function bpRail(at) {
    const steps = [
        [B("Start", "Bắt đầu"), B("Name, starter, who you pay", "Tên, điểm bắt đầu, trả lương cho ai")],
        [B("Pay rules", "Quy tắc lương"), B("Components, tax, calendar", "Thành phần, thuế, lịch")],
        [B("Connect", "Kết nối"), B("Sources, payslip, approvals", "Nguồn dữ liệu, phiếu lương, phê duyệt")],
        [B("Outputs", "Đầu ra"), B("Every formula, one table", "Mọi công thức, một bảng")],
        [B("Test", "Kiểm thử"), B("Try the days that aren't ordinary", "Thử những ngày không bình thường")],
        [B("Finish", "Hoàn thành"), B("Review and open", "Xem lại và mở")],
    ].map(([l, h], i) => `
        <div class="lrn-zrailrow ${i < at ? "done" : i === at ? "cur" : ""}">
            <span class="lrn-wdot">${i < at ? ic("check") : i + 1}</span>
            <span><b>${esc(tx(l))}</b><br><span class="lrn-sub2">${esc(tx(h))}</span></span>
        </div>`).join("");
    return `<nav class="lrn-zbprail" data-coach="bp-rail">
        <span class="lrn-zeyebrow">${esc(tx(B("New configuration", "Cấu hình mới")))}</span>${steps}</nav>`;
}

function bpFoot(step, label, comps) {
    const line = tx(B("Step", "Bước")) + SP + N(step) + SP + tx(B("of 6", "trên 6")) + DOT
        + N(comps) + SP + tx(B("components", "thành phần"));
    return `<div class="lrn-zhead lrn-zfoot" data-coach="bp-foot">
        <span class="lrn-sub2">${esc(line)}</span><span class="lrn-push"></span>
        <button class="lrn-btn sm pri">${esc(tx(label))}${ic("arrow-right")}</button>
    </div>`;
}

/* "See it in someone's pay". `ticked` draws the after-state and carries the
   before/after pair for the lesson's tick moment (engine/visuals.js). */
function bpPay(b, ticked) {
    const p = b.pay;
    const shown = ticked ? p.after : p.before;
    const delta = ticked
        ? `<span class="lrn-chip ok">+${esc(M(p.delta))}</span>` : "";
    const lines = p.lines.map((l) => `<div class="lrn-cr"><span>${esc(tx(l.k))}</span><b>${esc(M(l.v))}</b></div>`).join("");
    return `<aside class="lrn-panel lrn-zpay" data-coach="bp-pay">
        <div class="lrn-zeyebrow">${esc(tx(B("See it in someone's pay", "Xem ngay trên lương của một người")))}</div>
        <b>${esc(p.who)}</b><span class="lrn-sub2">${esc(tx(p.sub))}</span>
        <span class="lrn-sub2">${esc(tx(B("Estimated take-home pay", "Thực nhận ước tính")))}</span>
        <div class="lrn-zpaynum"><b data-coach="rep-bp-paynum" data-from="${p.before}" data-to="${p.after}">${esc(M(shown))}</b>${delta}</div>
        <div class="lrn-calc">${lines}</div>
        <p class="lrn-note">${esc(tx(B("Calculated by the real payroll engine from this configuration. Sample data only.",
            "Tính bằng chính bộ máy tính lương từ cấu hình này. Chỉ là dữ liệu mẫu.")))}</p>
    </aside>`;
}

/* Insights › Explorer › Compare schemes, with the money switch
   (explorer.xml `pbex-money`): each scheme in its own money, and the one
   converted figure the group currency adds — never a sum of two monies. */
function compareHTML() {
    const g = PRACTICE.group;
    const rows = g.compare.map((r) => {
        const own = r.cur === "VND" ? M(r.own) : N(r.own) + SP + r.cur;
        const conv = r.group ? `<span class="lrn-sub2">≈${SP}${esc(M(r.group))}${SP}${
            esc(tx(B("in the group currency", "theo đồng tiền tập đoàn")))}</span>` : "";
        return `<div class="lrn-cr"><span>${esc(r.name)}</span><b>${esc(own)}</b>${conv}</div>`;
    }).join("");
    return `
            <div class="lrn-panel" data-coach="rep-ex-compare">
                <h3>${ic("git-merge")}${esc(tx(B("Compare schemes", "So sánh các chương trình lương")))}</h3>
                <div class="lrn-seg" data-coach="ex-money">
                    <button aria-pressed="false">${esc(tx(B("Group currency", "Đồng tiền của tập đoàn")))}</button>
                    <button aria-pressed="true">${esc(tx(B("Each in its own money", "Mỗi bên theo đồng tiền của mình")))}</button>
                </div>
                <p class="lrn-note">${esc(tx(B("Two currencies, kept apart: these are different monies. Switch to Group currency to add them up.",
                    "Hai đồng tiền, để riêng: đây là những đồng tiền khác nhau. Chuyển sang Đồng tiền của tập đoàn để cộng chúng lại.")))}</p>
                <div class="lrn-calc">${rows}</div>
            </div>`;
}

function mapTop(m, headline) {
    const tabs = [
        B("System fields → Scheme", "Trường hệ thống → Chương trình lương"), B("Transformations", "Chuyển đổi"),
        B("Spreadsheet columns → Scheme", "Cột bảng tính → Chương trình lương"), B("Employee & contract ⇆", "Nhân viên & hợp đồng ⇆"),
        B("Who is paid by what", "Ai được trả lương theo phương án nào"), B("Mid ↔ End cycle", "Giữa ↔ Cuối chu kỳ"),
        B("Component treatment", "Xử lý thành phần"), B("Journey", "Hành trình"),
    ];
    const screenOf = { 2: "mapping_sheet", 6: "treatment", 7: "mapping" };
    const on = { mapping: 7, mapping_sheet: 2, treatment: 6 }[CURRENT_SCREEN];
    const pills = tabs.map((t, i) => {
        const attr = screenOf[i] ? navAttr(screenOf[i]) : quietAttr(tx(B("Mapping", "Ánh xạ")) + " › " + tx(t));
        return `<button class="lrn-lens ${i === on ? "on" : ""}${SP}${screenOf[i] ? "" : "quiet"}" ${attr}>${esc(tx(t))}</button>`;
    }).join("");
    const count = headline ? N(m.header.fed) + SP + tx(B("fed", "đã có nguồn")) : N(m.sheetColumns.length) + SP + tx(B("mapped", "đã nối"));
    return `
        <div class="lrn-zstory" data-coach="mp-story">
            <span class="lrn-zend"><span class="lrn-zeyebrow">${esc(tx(B("From", "Từ")))}</span><b>${ic("database")}${esc(tx(m.from))}</b></span>
            <span class="lrn-zwire"><span>${esc(count)}</span></span>
            <span class="lrn-zend to"><span class="lrn-zeyebrow">${esc(tx(B("To", "Đến")))}</span><b>${ic("calculator")}${esc(m.to)}</b></span>
        </div>
        <div class="lrn-zmodes" data-coach="mp-modes">${pills}</div>`;
}

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
