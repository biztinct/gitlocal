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
import { B, CASE, MENU, PRACTICE, RUN, STATUS_LABELS, SUB_SCREENS } from "./fixture";
import { esc, ic, initial, tx, T, N, M, P, SP} from "./runtime";
import { calcHTML, pipeHTML } from "./visuals";

/* Which screen the shell is showing. The Coach grounds on this. */
export let CURRENT_SCREEN = null;

/* ------------------------------------------------------------------- helpers */
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
    const kpis = d.kpis.map((k) => `
        <div class="lrn-kpi">
            <div class="lrn-kt">${ic("calculator")}<span>${esc(tx(k.label))}</span></div>
            <div class="lrn-kv ${k.money ? "lrn-money" : ""}">${esc(k.v)}</div>
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

/* -------------------------------------------------------------------- screens */
export const SCREENS = {
    /* Context only. Not a Phase A station — drawn so the replica's menu leads
       somewhere and the learner recognises where they landed. */
    dashboard() {
        const k = PRACTICE.kpis;
        const rows = PRACTICE.recentRuns.map((r) => `
            <div class="lrn-row">
                <span><span class="lrn-nm">${esc(tx(r.period))}</span><br>
                    <span class="lrn-sub2">${esc(tx(RUN.division))}${SP}· ${N(r.employees)}${SP}${esc(T("employees"))}</span></span>
                <span class="lrn-rr">${statusChip("payrun", r.state)}
                    <b class="lrn-money">${esc(M(r.net))}</b></span>
            </div>`).join("");
        return `
            <div class="lrn-grid g4" data-coach="rep-dash-kpis">
                ${kpiTile("users", "", N(k.headcount), B("Headcount", "Nhân sự"))}
                ${kpiTile("trending-up", "pos", M(k.monthlyNet), B("Net this month", "Thực nhận tháng này"))}
                ${kpiTile("clipboard-check", "warn", N(k.waiting), B("Waiting for you", "Đang chờ bạn"))}
                ${kpiTile("calculator", "", N(k.configs), B("Formula configurations", "Cấu hình công thức"))}
            </div>
            <div class="lrn-panel" data-coach="rep-dash-runs">
                <h3>${ic("calendar")}${esc(tx(B("Recent pay runs", "Các đợt lương gần đây")))}</h3>
                <div class="lrn-rows">${rows}</div>
            </div>`;
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

        const flow = ["draft", "level0", "level1", "level2", "done"].map((c, i) => `
            <div class="lrn-st ${i < 2 ? "done" : ""}${SP}${i === 2 ? "cur" : ""}"
                >${esc(tx(STATUS_LABELS.payrun[c].l))}</div>`).join("");

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
        const errs = w.errorRows.map((r) => `
            <div class="lrn-err">
                <span><span class="lrn-nm">${esc(r.name)}</span>
                    <span class="lrn-faint">${esc(r.code)}</span><br>
                    <span class="lrn-sub2">${esc(tx(r.why))}</span></span>
                <span class="lrn-rr">
                    <button class="lrn-btn sm">${esc(T("match"))}</button>
                    <button class="lrn-btn sm ghost">${esc(T("retry"))}</button>
                    <button class="lrn-btn sm ghost">${esc(T("skip"))}</button>
                </span>
            </div>`).join("");

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
            const inScope = sec === owner;
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
