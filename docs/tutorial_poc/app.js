/* ==========================================================================
   Payobook Learn — prototype engine
   Vanilla JS, no build step. State persists in localStorage.
   ========================================================================== */
"use strict";

/* ------------------------------------------------------------------ state */
const DEFAULT_STATE = {
  lang: "en", role: "officer", motion: "auto", mode: null,
  progress: {},            // stationId -> {done, step}
  conf: { run: 20, setup: 10, approve: 0, formula: 0 },
  sim: {},                 // missionId -> {done}
  last: null,              // {hash, label:{en,vi}}
  visited: false,
};
let S;
try { S = Object.assign({}, DEFAULT_STATE, JSON.parse(localStorage.getItem("pbLearnPoc") || "{}")); }
catch (e) { S = Object.assign({}, DEFAULT_STATE); }
function save() { localStorage.setItem("pbLearnPoc", JSON.stringify(S)); }

/* ---------------------------------------------------------------- helpers */
const $ = (sel, root) => (root || document).querySelector(sel);
const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
const APP = $("#app"), OVER = $("#overlay-root"), TOASTS = $("#toast-root");

function T(key) {
  const v = I18N[S.lang][key];
  return v === undefined ? (I18N.en[key] !== undefined ? I18N.en[key] : key) : v;
}
function tx(o) { if (o == null) return ""; if (typeof o === "string") return o; return o[S.lang] || o.en || ""; }
function ic(name, cls) { return `<svg class="ic ${cls || ""}" aria-hidden="true"><use href="#i-${name}"/></svg>`; }
function fmt(n) {
  if (S.lang === "vi") return n.toLocaleString("vi-VN") + " ₫";
  return "₫" + n.toLocaleString("en-US");
}
function reduced() {
  return S.motion === "reduced" || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
function toast(msg, kind, icon) {
  const d = document.createElement("div");
  d.className = "toast " + (kind || "");
  d.innerHTML = ic(icon || "info") + `<span>${msg}</span>`;
  TOASTS.appendChild(d);
  setTimeout(() => { d.style.opacity = "0"; d.style.transition = "opacity .3s"; setTimeout(() => d.remove(), 350); }, 3400);
}
function setLast(label) { S.last = { hash: location.hash, label }; save(); }

/* ------------------------------------------------------------------ modal */
let modalEl = null;
function openModal(html, opts) {
  closeModal();
  modalEl = document.createElement("div");
  modalEl.className = "modal-veil";
  modalEl.innerHTML = `<div class="modal" role="dialog" aria-modal="true">${html}</div>`;
  if (!(opts && opts.noDismiss)) {
    modalEl.addEventListener("click", (e) => { if (e.target === modalEl) closeModal(); });
  }
  document.body.appendChild(modalEl);
  const f = $(".modal .btn", modalEl) || $(".modal button", modalEl);
  if (f) f.focus();
  return modalEl;
}
function closeModal() { if (modalEl) { modalEl.remove(); modalEl = null; } }

/* -------------------------------------------------------- spotlight engine */
const Spot = {
  hole: null, card: null, pointer: null, traceSvg: null, traceDot: null,
  ensure() {
    if (!this.hole) {
      this.hole = document.createElement("div"); this.hole.className = "spot-hole pulse"; OVER.appendChild(this.hole);
      this.card = document.createElement("div"); this.card.className = "coach-card"; OVER.appendChild(this.card);
      this.pointer = document.createElement("div"); this.pointer.className = "coach-pointer";
      this.pointer.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor"><path d="m3 3 7.07 16.97 2.51-7.39 7.39-2.51z"/></svg>`;
      OVER.appendChild(this.pointer);
    }
  },
  show(targetSel, cardHTML, opts) {
    this.ensure();
    const t = targetSel ? $(`[data-anchor="${targetSel}"]`) : null;
    const vw = innerWidth, vh = innerHeight;
    let r;
    if (t) { t.scrollIntoView({ block: "center", behavior: reduced() ? "auto" : "smooth" }); r = t.getBoundingClientRect(); }
    if (t && r) {
      const pad = 8;
      Object.assign(this.hole.style, {
        display: "block",
        top: (r.top - pad) + "px", left: (r.left - pad) + "px",
        width: (r.width + pad * 2) + "px", height: (r.height + pad * 2) + "px",
      });
      this.pointer.style.display = "block";
      this.pointer.style.top = Math.min(vh - 44, r.top + r.height / 2 - 15) + "px";
      this.pointer.style.left = Math.max(8, r.left - 40) + "px";
    } else {
      // no target: dim everything, center the card
      Object.assign(this.hole.style, { display: "block", top: "50%", left: "50%", width: "0px", height: "0px" });
      this.pointer.style.display = "none";
    }
    this.card.innerHTML = cardHTML;
    this.card.style.display = "block";
    // place card
    requestAnimationFrame(() => {
      const cw = this.card.offsetWidth, ch = this.card.offsetHeight;
      let top, left;
      if (t && r) {
        if (r.right + cw + 28 < vw) { left = r.right + 18; top = r.top; }
        else if (r.left - cw - 28 > 0) { left = r.left - cw - 18; top = r.top; }
        else if (r.bottom + ch + 20 < vh) { left = Math.min(Math.max(12, r.left), vw - cw - 12); top = r.bottom + 16; }
        else { left = Math.min(Math.max(12, r.left), vw - cw - 12); top = Math.max(12, r.top - ch - 16); }
        top = Math.min(Math.max(12, top), vh - ch - 12);
      } else { left = (vw - cw) / 2; top = Math.max(20, (vh - ch) / 2.4); }
      this.card.style.top = top + "px"; this.card.style.left = left + "px";
      if (opts && opts.onPlaced) opts.onPlaced();
    });
  },
  trace(fromSel, toSel) {
    this.clearTrace();
    const a = $(`[data-anchor="${fromSel}"]`), b = $(`[data-anchor="${toSel}"]`);
    if (!a || !b) return;
    const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
    const x1 = ra.left + ra.width / 2, y1 = ra.top + ra.height / 2;
    const x2 = rb.left + rb.width / 2, y2 = rb.top + rb.height / 2;
    const mx = (x1 + x2) / 2;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "trace-svg");
    svg.innerHTML = `<path d="M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}"/>`;
    OVER.appendChild(svg); this.traceSvg = svg;
    if (!reduced()) {
      const path = svg.querySelector("path"); const len = path.getTotalLength();
      const dot = document.createElement("div"); dot.className = "trace-dot"; OVER.appendChild(dot); this.traceDot = dot;
      const t0 = performance.now(), dur = 1500;
      const anim = (now) => {
        if (!this.traceDot) return;
        const p = Math.min(1, ((now - t0) % (dur + 600)) / dur);
        const pt = path.getPointAtLength(p * len);
        dot.style.left = (pt.x - 6) + "px"; dot.style.top = (pt.y - 6) + "px";
        this._traceRaf = requestAnimationFrame(anim);
      };
      this._traceRaf = requestAnimationFrame(anim);
    }
  },
  clearTrace() {
    if (this._traceRaf) cancelAnimationFrame(this._traceRaf);
    if (this.traceSvg) { this.traceSvg.remove(); this.traceSvg = null; }
    if (this.traceDot) { this.traceDot.remove(); this.traceDot = null; }
  },
  hide() {
    this.clearTrace();
    if (this.hole) { this.hole.style.display = "none"; this.card.style.display = "none"; this.pointer.style.display = "none"; }
  },
};
function flashRing(sel) {
  const t = $(`[data-anchor="${sel}"]`);
  if (!t) return false;
  t.scrollIntoView({ block: "center", behavior: reduced() ? "auto" : "smooth" });
  setTimeout(() => {
    const r = t.getBoundingClientRect();
    const d = document.createElement("div"); d.className = "flash-ring";
    Object.assign(d.style, { top: (r.top - 5) + "px", left: (r.left - 5) + "px", width: (r.width + 10) + "px", height: (r.height + 10) + "px" });
    OVER.appendChild(d); setTimeout(() => d.remove(), 2300);
  }, reduced() ? 0 : 250);
  return true;
}

/* ============================================================== app shell */
const ROLE_HIDE = {
  officer: ["structures", "statutory"],
  hr: [],
  gm: ["runpayroll", "import", "formula", "structures", "statutory", "integrations", "fullfinal", "proration", "retro"],
  viewer: ["runpayroll", "import", "formula", "structures", "statutory", "integrations", "approvals", "fullfinal", "retro"],
};
function screenTitle(id) {
  for (const sec of MENU) for (const it of sec.items) if (it.id === id) return tx(it.label);
  return "Payobook";
}
function shellHTML(screen, ctx) {
  ctx = ctx || {};
  const hidden = ctx.allNav ? [] : (ROLE_HIDE[S.role] || []);
  const nav = MENU.map((sec) => `
    <div class="sb-sec">
      <div class="sb-sec-label">${tx(sec.label)}</div>
      ${sec.items.filter((it) => !hidden.includes(it.id)).map((it) => `
        <button class="sb-item ${screen === it.id ? "on" : ""} ${ctx.glowNav === it.id ? "sim-glow" : ""}"
          data-nav="${it.id}" data-anchor="nav-${it.id}">${ic(it.icon)}<span>${tx(it.label)}</span></button>`).join("")}
    </div>`).join("");
  return `
  <div class="shell">
    <aside class="sb ${ctx.sbOpen ? "open" : ""}" aria-label="Sidebar">
      <div class="sb-logo"><span class="dot">${ic("zap")}</span> Payobook</div>
      ${nav}
      <div class="sb-foot">Hoa Sen Retail Co. · ${T("prototype")}</div>
    </aside>
    ${ctx.sbOpen ? `<div class="sb-veil" data-act="sb-close"></div>` : ""}
    <main class="stage">
      <header class="topbar">
        <button class="btn subtle sm hamb" data-act="sb-open" aria-label="Menu">${ic("layers")}</button>
        <h2>${screenTitle(screen)}</h2>
        <span class="co">Hoa Sen Retail Co. — ${tx(B_("Vietnam", "Việt Nam"))}</span>
        <div class="right">
          <span class="role-chip">${ic("users")} ${T("roles")[S.role]}</span>
        </div>
      </header>
      <section class="screen"><div class="screen-inner">${SCREENS[screen] ? SCREENS[screen](ctx) : ""}</div></section>
    </main>
  </div>`;
}
function B_(en, vi) { return { en, vi }; }

/* ------------------------------------------------------------- screens -- */
const SCREENS = {
  dashboard() {
    return `
    <div class="kpis">
      ${kpi("users", "indigo", "48", T("hero").headcount)}
      ${kpi("trending-up", "green", fmt(612480000), T("hero").monthlyNet)}
      ${kpi("clipboard-check", "amber", "1", T("hero").waiting)}
      ${kpi("calculator", "cyan", "2", T("hero").configs)}
    </div>
    <div class="panel card">
      <h3>${ic("calendar", "lg")} ${tx(B_("Recent pay runs", "Các đợt lương gần đây"))}</h3>
      <table class="tbl">
        <tr><th>${T("period")}</th><th>${T("division")}</th><th class="r">${T("employees")}</th><th class="r">${T("net")}</th><th></th></tr>
        <tr><td>${tx(B_("July 2026", "Tháng 7/2026"))}</td><td>${tx(RUN.division)}</td><td class="r">48</td><td class="r money">${fmt(612480000)}</td><td><span class="chip amber">${T("pipeline")[2]}</span></td></tr>
        <tr><td>${tx(B_("June 2026", "Tháng 6/2026"))}</td><td>${tx(RUN.division)}</td><td class="r">47</td><td class="r money">${fmt(596110000)}</td><td><span class="chip green">${T("pipeline")[4]}</span></td></tr>
        <tr><td>${tx(B_("May 2026", "Tháng 5/2026"))}</td><td>${tx(RUN.division)}</td><td class="r">47</td><td class="r money">${fmt(590870000)}</td><td><span class="chip green">${T("pipeline")[4]}</span></td></tr>
      </table>
    </div>`;
  },

  runpayroll(ctx) {
    const computed = ctx.computed;
    return `
    <div class="wiz-steps">
      <span class="wiz-step ${computed ? "done" : "on"}"><span class="n">1</span> ${tx(B_("Scope", "Phạm vi"))}</span>
      <span class="wiz-step ${computed ? "on" : ""}"><span class="n">2</span> ${T("compute")}</span>
      <span class="wiz-step"><span class="n">3</span> ${tx(B_("Review & submit", "Soát xét & trình"))}</span>
    </div>
    <div class="panel card" style="max-width:640px">
      <h3>${ic("zap", "lg")} ${tx(B_("Run payroll", "Chạy bảng lương"))}</h3>
      <div class="field" data-anchor="pw-division">
        <label>${T("division")}</label>
        <select data-act="pw-division" ${ctx.glow === "pw-division" ? 'class="sim-glow"' : ""}>
          <option value="" ${!ctx.division ? "selected" : ""}>${tx(B_("— choose —", "— chọn —"))}</option>
          <option value="retail" ${ctx.division === "retail" ? "selected" : ""}>${tx(B_("Retail — Hà Nội", "Bán lẻ — Hà Nội"))}</option>
          <option value="it">${tx(B_("IT Services", "Dịch vụ CNTT"))}</option>
          <option value="fnb">F&amp;B</option>
        </select>
      </div>
      <div class="field" data-anchor="pw-period">
        <label>${T("period")} · ${T("cycle")}</label>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <select style="flex:1"><option>${tx(B_("July 2026", "Tháng 7/2026"))}</option><option>${tx(B_("August 2026", "Tháng 8/2026"))}</option></select>
          <select style="flex:1"><option>${T("cycleEnd")}</option><option>${T("cycleMid")}</option></select>
        </div>
      </div>
      <div class="cfg-preview" data-anchor="pw-config">
        ${ic("calculator")} <span class="chip">${RUN.config} · ${RUN.configVersion}</span>
        <b class="num">${ctx.division ? 48 : "—"}</b> <span class="muted">${T("eligible")}</span>
      </div>
      <div style="margin-top:16px;display:flex;gap:8px;align-items:center">
        <button class="btn primary ${ctx.glow === "pw-compute" ? "sim-glow" : ""}" data-anchor="pw-compute" data-act="pw-compute" ${computed ? "disabled" : ""}>${ic("play")} ${T("compute")}</button>
        <span class="muted small">${tx(B_("Creates drafts only — nothing is paid or sent.", "Chỉ tạo bản nháp — chưa chi trả hay gửi gì."))}</span>
      </div>
    </div>
    ${ctx.computing ? `
    <div class="panel card" style="max-width:640px">
      <p style="display:flex;gap:9px;align-items:center">${ic("refresh")} ${T("computing")}</p>
      <div class="pbar" style="margin-top:10px"><i style="width:100%;transition:width 1.1s linear"></i></div>
    </div>` : ""}
    ${computed ? `
    <div class="panel card" style="max-width:640px" data-anchor="pw-result">
      <h3>${ic("check-circle", "lg")} ${tx(RUN.name)}</h3>
      <div class="kpis" style="margin-bottom:10px">
        ${kpi("users", "indigo", "48", tx(B_("payslips drafted", "phiếu lương nháp")))}
        ${kpi("trending-up", "green", fmt(612480000), tx(B_("total net", "tổng thực nhận")))}
      </div>
      <div class="chip amber" style="margin-bottom:10px">${ic("alert-triangle")} ${T("anomalies")(1)}</div>
      <table class="tbl">
        <tr><th>${T("employees")}</th><th class="r">${tx(B_("Overtime", "Tăng ca"))}</th><th class="r">${T("net")}</th><th></th></tr>
        <tr><td>${EMP.mai.name}</td><td class="r num">${fmt(EMP.mai.otJul)}</td><td class="r money">${fmt(EMP.mai.netJul)}</td><td></td></tr>
        <tr class="hl ${ctx.glow === "anomaly" ? "sim-glow" : ""}" data-anchor="pw-anomaly" data-act="pw-anomaly" style="cursor:pointer">
          <td>${EMP.hung.name}</td><td class="r num"><b>${fmt(EMP.hung.otJul)}</b></td><td class="r money">${fmt(EMP.hung.netJul)}</td>
          <td><span class="chip amber">${ic("alert-triangle")} ${T("anomaly")}</span></td></tr>
        <tr><td>${EMP.trang.name}</td><td class="r num">${fmt(310000)}</td><td class="r money">${fmt(EMP.trang.netJul)}</td><td></td></tr>
      </table>
      <div style="margin-top:14px;display:flex;gap:8px">
        <button class="btn primary ${ctx.glow === "submit" ? "sim-glow" : ""}" data-act="pw-submit" data-anchor="pw-submit" ${ctx.decided ? "" : "disabled"}>${ic("send")} ${T("submitApproval")}</button>
        <button class="btn outline sm" data-act="pw-recompute">${ic("rotate-ccw")} ${tx(B_("Recompute", "Tính lại"))}</button>
      </div>
    </div>` : ""}`;
  },

  payruns(ctx) {
    const cols = T("pipeline");
    const dots = ["#64748b", "#5A4BB0", "#6E72B0", "#B7791F", "#0F8A63"];
    const julyCol = ctx.submitted ? 1 : 0;
    return `
    <div class="kanban">
      ${cols.map((c, i) => `
      <div class="kcol" ${i === 0 ? 'data-anchor="k-draft"' : ""}>
        <div class="kcol-h"><span class="dot" style="background:${dots[i]}"></span> ${c}</div>
        ${i === julyCol ? kanbanCard(tx(RUN.name), 48, 612480000, i) : ""}
        ${i === 4 ? kanbanCard(tx(B_("Retail — June 2026", "Bán lẻ — Tháng 6/2026")), 47, 596110000, i) + kanbanCard(tx(B_("Retail — May 2026", "Bán lẻ — Tháng 5/2026")), 47, 590870000, i) : ""}
        ${i === 2 ? kanbanCard(tx(B_("F&B — July 2026", "F&B — Tháng 7/2026")), 21, 214300000, i) : ""}
      </div>`).join("")}
    </div>
    <div class="panel card">
      <h3>${ic("git-branch", "lg")} ${tx(B_("How a run travels", "Một đợt lương đi thế nào"))}</h3>
      <p class="muted small">${tx(B_("Draft → Payroll Officer → HR review → GM approval → Done. Each gate belongs to one role; a rejection returns the run to Draft with a written reason.", "Nháp → CV tính lương → HR soát xét → TGĐ phê duyệt → Hoàn tất. Mỗi cổng thuộc một vai trò; từ chối sẽ trả đợt về Nháp kèm lý do bằng văn bản."))}</p>
    </div>`;
  },

  payslips(ctx) {
    const morph = ctx.morph;
    const bhyt = morph ? 240000 : 180000, pit = morph ? 98000 : 101000, net = morph ? 12862000 : 12919000;
    const ins = morph ? 1320000 : 1260000;
    return `
    <div class="slip-grid">
      <div class="card slip-list">
        ${[EMP.mai, EMP.hung, EMP.trang, EMP.duc].map((e, i) => `
          <div class="slip-row ${i === 0 ? "on" : ""}"><span>${e.name}</span><span class="money">${fmt(e.netJul)}</span></div>`).join("")}
      </div>
      <div class="panel card">
        <h3>${ic("receipt", "lg")} ${EMP.mai.name} · ${EMP.mai.code} — ${tx(B_("July 2026", "Tháng 7/2026"))}
          ${morph ? `<span class="chip cyan">${tx(B_("preview: BHYT 2%", "xem trước: BHYT 2%"))}</span>` : ""}</h3>
        <table class="tbl">
          <tr><td>${tx(B_("Base salary (LCB)", "Lương cơ bản (LCB)"))}</td><td class="r num">${fmt(EMP.mai.base)}</td></tr>
          <tr><td>${tx(B_("Allowances (PCCC, ATVSV)", "Phụ cấp (PCCC, ATVSV)"))}</td><td class="r num">${fmt(EMP.mai.allowance)}</td></tr>
          <tr><td>${tx(B_("Overtime", "Tăng ca"))}</td><td class="r num">${fmt(EMP.mai.otJul)}</td></tr>
          <tr class="total"><td>${T("gross")}</td><td class="r num">${fmt(EMP.mai.grossJul)}</td></tr>
          <tr data-anchor="sl-bhxh"><td>BHXH (8%)</td><td class="r num line-neg">−${fmt(EMP.mai.bhxh)}</td></tr>
          <tr data-anchor="sl-bhyt" ${morph ? 'class="count-flip"' : ""}><td>BHYT (${morph ? "2%" : "1.5%"})</td><td class="r num line-neg">−${fmt(bhyt)}</td></tr>
          <tr><td>BHTN (1%)</td><td class="r num line-neg">−${fmt(EMP.mai.bhtn)}</td></tr>
          <tr ${morph ? 'class="count-flip"' : ""}><td>${tx(B_("PIT (progressive)", "Thuế TNCN (luỹ tiến)"))}</td><td class="r num line-neg">−${fmt(pit)}</td></tr>
          <tr class="total" data-anchor="sl-net" ${morph ? 'class="total count-flip"' : ""}><td>${T("net")}</td><td class="r money" style="font-size:15px">${fmt(net)}</td></tr>
        </table>
        <p class="muted small" style="margin-top:8px">${tx(B_("Insurance total", "Tổng bảo hiểm"))}: ${fmt(ins)} · ${tx(B_("Taxable income", "Thu nhập chịu thuế"))}: ${fmt(morph ? 1960000 : 2020000)}</p>
      </div>
    </div>`;
  },

  import() {
    return `
    <div class="panel card" style="max-width:680px">
      <h3>${ic("download", "lg")} ${tx(B_("Guided import — July attendance & OT", "Nhập có hướng dẫn — chấm công & tăng ca tháng 7"))}</h3>
      <div class="wiz-steps">
        <span class="wiz-step done"><span class="n">1</span> ${tx(B_("Upload", "Tải lên"))}</span>
        <span class="wiz-step done"><span class="n">2</span> ${tx(B_("Preview", "Xem trước"))}</span>
        <span class="wiz-step on"><span class="n">3</span> ${tx(B_("Score", "Chấm điểm"))}</span>
        <span class="wiz-step"><span class="n">4</span> ${tx(B_("Commit", "Ghi nhận"))}</span>
      </div>
      <div class="kpis">
        ${kpi("check-circle", "green", "98.5%", tx(B_("confidence score", "điểm tin cậy")))}
        ${kpi("users", "indigo", "48", tx(B_("rows matched", "dòng khớp")))}
        ${kpi("alert-triangle", "amber", "2", tx(B_("warnings to review", "cảnh báo cần xem")))}
      </div>
      <p class="muted small" style="margin-top:10px">${tx(B_("Nothing commits until the score is reviewed — fix warnings here, not in payslips.", "Chưa gì được ghi nhận cho tới khi điểm được soát — sửa cảnh báo tại đây, đừng sửa trên phiếu lương."))}</p>
    </div>`;
  },

  fullfinal() {
    return `
    <div class="panel card">
      <h3>${ic("file", "lg")} ${tx(B_("Departing employees — settlements", "Nhân viên thôi việc — quyết toán"))}</h3>
      <table class="tbl">
        <tr><th>${T("employees")}</th><th>${tx(B_("Last day", "Ngày cuối"))}</th><th class="r">${tx(B_("Settlement", "Quyết toán"))}</th><th></th></tr>
        <tr><td>Võ Quang Huy · NV0044</td><td>15/07/2026</td><td class="r money">${fmt(8420000)}</td><td><span class="chip amber">${tx(B_("Pending", "Đang chờ"))}</span></td></tr>
        <tr><td>Đỗ Thị Lan · NV0021</td><td>30/06/2026</td><td class="r money">${fmt(14730000)}</td><td><span class="chip green">${tx(B_("Settled", "Đã chốt"))}</span></td></tr>
      </table>
      <p class="muted small" style="margin-top:8px">${tx(B_("Settlement = final salary + unused leave − deductions. Remember to exclude the leaver from the normal monthly run.", "Quyết toán = lương cuối + phép chưa dùng − khấu trừ. Nhớ loại nhân viên này khỏi đợt lương tháng bình thường."))}</p>
    </div>`;
  },

  proration() {
    return `
    <div class="panel card">
      <h3>${ic("calculator", "lg")} ${tx(B_("Proration audit — July 2026", "Soát xét ngày công — Tháng 7/2026"))}</h3>
      <table class="tbl">
        <tr><th>${T("employees")}</th><th class="r">${tx(B_("Worked / standard days", "Ngày công / chuẩn"))}</th><th class="r">${tx(B_("Factor", "Hệ số"))}</th><th class="r">${tx(B_("Prorated base", "Lương theo tỷ lệ"))}</th></tr>
        <tr><td>Võ Quang Huy (${tx(B_("left 15/07", "nghỉ 15/07"))})</td><td class="r num">11 / 22</td><td class="r num">0.50</td><td class="r num">${fmt(5250000)}</td></tr>
        <tr><td>Bùi Anh Tuấn (${tx(B_("joined 20/07", "vào 20/07"))})</td><td class="r num">9 / 22</td><td class="r num">0.41</td><td class="r num">${fmt(4090000)}</td></tr>
      </table>
      <p class="muted small" style="margin-top:8px">${tx(B_("Factors use standard working days from the division's config — not calendar days.", "Hệ số dùng ngày công chuẩn theo cấu hình của bộ phận — không phải ngày dương lịch."))}</p>
    </div>`;
  },

  retro() {
    return `
    <div class="panel card">
      <h3>${ic("percent", "lg")} ${tx(B_("Retro adjustments — applied in July", "Điều chỉnh hồi tố — áp vào tháng 7"))}</h3>
      <table class="tbl">
        <tr><th>${T("employees")}</th><th>${tx(B_("Reason", "Lý do"))}</th><th>${tx(B_("Source periods", "Kỳ gốc"))}</th><th class="r">${tx(B_("Amount", "Số tiền"))}</th></tr>
        <tr><td>${EMP.trang.name}</td><td>${tx(B_("Backdated raise (Apr)", "Tăng lương lùi ngày (T4)"))}</td><td>04–06/2026</td><td class="r money">+${fmt(2400000)}</td></tr>
        <tr><td>${EMP.duc.name}</td><td>${tx(B_("Missed night-shift allowance", "Sót phụ cấp ca đêm"))}</td><td>06/2026</td><td class="r money">+${fmt(380000)}</td></tr>
      </table>
      <p class="muted small" style="margin-top:8px">${tx(B_("Closed months stay closed — the difference is paid now, with the source period on record.", "Kỳ đã đóng luôn đóng — phần chênh chi ngay kỳ này, kèm kỳ gốc được ghi nhận."))}</p>
    </div>`;
  },

  formula() {
    const comps = [
      ["A", "LCB", tx(B_("Base salary", "Lương cơ bản")), "input"],
      ["B", "PC", tx(B_("Allowances", "Phụ cấp")), "earning"],
      ["C", "TANGCA", tx(B_("Overtime", "Tăng ca")), "earning"],
      ["D", "GROSS", tx(B_("Gross income", "Tổng thu nhập")), "total"],
      ["E", "BHXH", tx(B_("Social insurance", "BH xã hội")), "deduction"],
      ["F", "TNCT", tx(B_("Taxable income", "TN chịu thuế")), "total"],
      ["G", "TNCN", tx(B_("Personal income tax", "Thuế TNCN")), "deduction"],
      ["H", "THUCNHAN", tx(B_("Net pay", "Thực nhận")), "total"],
    ];
    return `
    <div class="fs-grid">
      <div class="card" style="padding:10px" data-anchor="fs-components">
        <div class="sb-sec-label" style="color:var(--pb-muted);padding:4px 8px 8px">${RUN.config} · v12</div>
        ${comps.map((c, i) => `<div class="fs-comp tag-${c[3]} ${i === 6 ? "on" : ""}"><span class="letter">${c[0]}</span><div><b style="font-size:12.5px">${c[1]}</b><div class="muted" style="font-size:11px">${c[2]}</div></div></div>`).join("")}
      </div>
      <div class="panel card" data-anchor="fs-formula">
        <h3>${ic("calculator", "lg")} TNCN — ${tx(B_("the formula, in plain language", "công thức, bằng ngôn ngữ dễ hiểu"))}</h3>
        <div style="line-height:2.1">
          <span class="f-chip deduction">TNCN</span> <span class="f-chip op">=</span> <span class="f-chip op">5% ×</span>
          <span class="f-chip total">TNCT</span><br/>
          <span class="f-chip total">TNCT</span> <span class="f-chip op">=</span> <span class="f-chip total">GROSS</span>
          <span class="f-chip op">−</span> <span class="f-chip deduction">BHXH+BHYT+BHTN</span>
          <span class="f-chip op">−</span> <span class="f-chip input">11,000,000</span>
        </div>
        <p class="muted small" style="margin-top:10px">${tx(B_("Depends on: GROSS, insurance · Used by: THUCNHAN. Click any chip in the real app to jump to that component.", "Phụ thuộc: GROSS, bảo hiểm · Được dùng bởi: THUCNHAN. Trong ứng dụng thật, bấm vào chip để nhảy tới thành phần đó."))}</p>
      </div>
      <div class="panel card fs-preview-col" data-anchor="fs-preview">
        <h3>${ic("eye", "lg")} ${tx(B_("Live preview", "Xem trước trực tiếp"))}</h3>
        <p class="small muted">${EMP.mai.name}</p>
        <table class="tbl">
          <tr><td>GROSS</td><td class="r num">${fmt(EMP.mai.grossJul)}</td></tr>
          <tr><td>TNCT</td><td class="r num">${fmt(2020000)}</td></tr>
          <tr><td>TNCN</td><td class="r num line-neg">−${fmt(101000)}</td></tr>
          <tr class="total"><td>THUCNHAN</td><td class="r money">${fmt(EMP.mai.netJul)}</td></tr>
        </table>
      </div>
    </div>`;
  },

  structures() {
    return `
    <div class="panel card" style="max-width:680px">
      <h3>${ic("layers", "lg")} ${tx(B_("Salary structures (legacy)", "Cấu trúc lương (thế hệ cũ)"))}</h3>
      <table class="tbl">
        <tr><th>${tx(B_("Structure", "Cấu trúc"))}</th><th class="r">${tx(B_("Rules", "Quy tắc"))}</th><th></th></tr>
        <tr><td>VN Standard 2023</td><td class="r num">14</td><td><span class="chip slate">${tx(B_("historical", "lịch sử"))}</span></td></tr>
        <tr><td>VN Probation 2023</td><td class="r num">9</td><td><span class="chip slate">${tx(B_("historical", "lịch sử"))}</span></td></tr>
      </table>
      <p class="muted small" style="margin-top:10px">${tx(B_("Old payslips still reference these rule sets. New pay logic belongs in the Formula Engine.", "Phiếu lương cũ vẫn tham chiếu các bộ quy tắc này. Logic lương mới hãy xây trong Công thức lương."))}</p>
    </div>`;
  },

  statutory(ctx) {
    const v2 = ctx.stVersion2;
    const rate = ctx.stRate || 1.5;
    return `
    <div class="panel card" style="max-width:720px" data-anchor="st-policy">
      <h3>${ic("shield", "lg")} ${tx(B_("Insurance policy — VN-2026", "Chính sách bảo hiểm — VN-2026"))}
        <span class="chip green">${tx(B_("active", "đang hiệu lực"))}</span>
        ${v2 ? `<span class="chip amber">${tx(B_("+ draft v2 (practice)", "+ nháp v2 (thực hành)"))}</span>` : ""}</h3>
      <table class="tbl">
        <tr><th></th><th class="r">${tx(B_("Employee", "Người lao động"))}</th><th class="r">${tx(B_("Employer", "Doanh nghiệp"))}</th></tr>
        <tr><td>BHXH</td><td class="r num">8%</td><td class="r num">17.5%</td></tr>
        <tr data-anchor="st-bhyt" ${ctx.glow === "st-bhyt" ? 'class="sim-glow"' : ""}><td>BHYT</td>
          <td class="r num">${v2 ? `<span class="chip clickable" data-act="st-rate">${rate}% ▾</span>` : "1.5%"}</td><td class="r num">3%</td></tr>
        <tr><td>BHTN</td><td class="r num">1%</td><td class="r num">1%</td></tr>
      </table>
      <div class="cfg-preview" style="margin-top:12px" data-anchor="st-cap">
        ${ic("scale")} <span>${tx(B_("Insurance base = registered contract base · cap 20× reference wage", "Mức đóng BH = lương cơ bản đã đăng ký · trần 20 lần lương tham chiếu"))}</span>
      </div>
      <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap" data-anchor="st-effective">
        <span class="chip slate">${ic("clock")} ${tx(B_("Effective from 01/01/2026", "Hiệu lực từ 01/01/2026"))}</span>
        ${v2 ? `<span class="chip amber">${ic("clock")} v2: ${ctx.stEffective || tx(B_("effective date not set", "chưa đặt ngày hiệu lực"))}</span>` : ""}
        <span class="spacer" style="flex:1"></span>
        <button class="btn outline sm ${ctx.glow === "st-new" ? "sim-glow" : ""}" data-act="st-new">${ic("git-branch")} ${tx(B_("New version (practice)", "Phiên bản mới (thực hành)"))}</button>
        ${v2 && ctx.stEffective ? `<button class="btn primary sm ${ctx.glow === "st-preview" ? "sim-glow" : ""}" data-act="st-preview">${ic("eye")} ${tx(B_("Preview impact", "Xem trước tác động"))}</button>` : ""}
      </div>
    </div>
    <div class="panel card" style="max-width:720px" data-anchor="st-pit">
      <h3>${ic("percent", "lg")} ${tx(B_("PIT table (progressive)", "Biểu thuế TNCN (luỹ tiến)"))}</h3>
      <table class="tbl">
        <tr><th>${tx(B_("Monthly taxable income", "TN chịu thuế/tháng"))}</th><th class="r">${tx(B_("Rate", "Thuế suất"))}</th></tr>
        <tr><td>≤ ${fmt(5000000)}</td><td class="r num">5%</td></tr>
        <tr><td>${fmt(5000000)} – ${fmt(10000000)}</td><td class="r num">10%</td></tr>
        <tr><td>${fmt(10000000)} – ${fmt(18000000)}</td><td class="r num">15%</td></tr>
        <tr><td colspan="2" class="muted small">… ${tx(B_("up to 35% · personal deduction ₫11m + ₫4.4m per dependant", "tới 35% · giảm trừ bản thân 11tr + 4,4tr/người phụ thuộc"))}</td></tr>
      </table>
    </div>`;
  },

  integrations() {
    return `
    <div class="kpis" style="max-width:720px">
      ${kpi("database", "indigo", "Zoho People", tx(B_("connected · daily sync 06:00", "đã kết nối · đồng bộ 06:00 hằng ngày")))}
      ${kpi("building", "cyan", "Bank SFTP", tx(B_("payment files · configured", "file chi lương · đã cấu hình")))}
    </div>
    <div class="panel card" style="max-width:720px">
      <h3>${ic("git-branch", "lg")} ${tx(B_("Field mappings", "Ánh xạ trường dữ liệu"))}</h3>
      <p class="muted small">${tx(B_("42 fields mapped from Zoho People → Payobook (employee, contract, attendance). A broken sync raises a warning on the Dashboard — check it before payroll week.", "42 trường được ánh xạ từ Zoho People → Payobook (nhân viên, hợp đồng, chấm công). Đồng bộ lỗi sẽ hiện cảnh báo trên Bảng điều khiển — hãy kiểm tra trước tuần tính lương."))}</p>
    </div>`;
  },

  approvals() {
    return `
    <div class="panel card" style="max-width:680px">
      <h3>${ic("clipboard-check", "lg")} ${tx(B_("Waiting for you", "Đang chờ bạn"))}</h3>
      ${S.role === "hr" || S.role === "gm" || S.role === "officer" ? `
      <div class="kcard card" style="box-shadow:none;border:1px solid var(--pb-border)">
        <b>${tx(RUN.name)}</b>
        <div class="meta"><span>48 ${T("employees").toLowerCase()}</span><span class="money">${fmt(612480000)}</span><span class="chip amber">${T("pipeline")[2]}</span></div>
        <div style="display:flex;gap:8px;margin-top:8px">
          <button class="btn primary sm" data-act="appr-ok">${ic("check")} ${tx(B_("Approve", "Phê duyệt"))}</button>
          <button class="btn danger-ghost sm" data-act="appr-no">${ic("x")} ${tx(B_("Reject with reason", "Từ chối kèm lý do"))}</button>
        </div>
      </div>` : `<p class="muted">${tx(B_("Your role has no approval gate.", "Vai trò của bạn không có cổng phê duyệt."))}</p>`}
    </div>`;
  },
};
function kpi(icon, tone, val, label) {
  return `<div class="kpi card"><span class="k-ic ${tone}">${ic(icon, "lg")}</span><div><b>${val}</b><span>${label}</span></div></div>`;
}
function kanbanCard(name, emp, net, col) {
  return `<div class="kcard card"><b>${name}</b><div class="meta"><span>${emp} ${T("employees").toLowerCase()}</span><span class="money">${fmt(net)}</span></div>
  ${col === 4 ? `<div style="display:flex;gap:6px;margin-top:4px"><span class="chip green">${ic("check")} ${T("pipeline")[4]}</span></div>` : ""}</div>`;
}

/* =============================================================== controls */
function headControls() {
  return `
    <div class="seg" role="group" aria-label="${T("langLabel")}">
      <button data-act="lang-en" class="${S.lang === "en" ? "on" : ""}">EN</button>
      <button data-act="lang-vi" class="${S.lang === "vi" ? "on" : ""}">VI</button>
    </div>
    <div class="seg" role="group" aria-label="${T("roleLabel")}">
      ${["officer", "hr", "gm", "viewer"].map((r) => `<button data-act="role-${r}" class="${S.role === r ? "on" : ""}" title="${T("roles")[r]}">${{ officer: "OF", hr: "HR", gm: "GM", viewer: "VW" }[r]}</button>`).join("")}
    </div>
    <button class="btn subtle sm" data-act="motion" title="${T("motion")}" aria-pressed="${S.motion === "reduced"}">${ic(S.motion === "reduced" ? "pause" : "play")} ${T("motion")}</button>`;
}
function optHead(conceptLabel, backHash) {
  return `<header class="opt-head">
    <button class="btn subtle sm" data-go="${backHash || "#/hub"}">${ic("chevron-left")} ${T("backHub")}</button>
    <span class="crumb">${conceptLabel}</span>
    <span class="badge-poc">${T("prototype")}</span>
    <div class="right">${headControls()}</div>
  </header>`;
}

/* ==================================================================== HUB */
const HubView = {
  render() {
    Spot.hide();
    const modes = [
      ["map", "grad-cap", B_("Give me the complete guided journey", "Cho tôi hành trình đầy đủ có dẫn dắt")],
      ["role", "users", B_("Teach me only what I need for my role", "Chỉ dạy phần tôi cần cho vai trò của mình")],
      ["task", "target", B_("Help me complete today's task", "Giúp tôi hoàn thành việc hôm nay")],
      ["explore", "compass", B_("Let me explore independently", "Để tôi tự khám phá")],
      ["test", "award", B_("Test what I already know", "Kiểm tra những gì tôi đã biết")],
    ];
    APP.innerHTML = `
    <div class="hub">
      <div class="hub-top">
        <div class="hub-logo"><span class="dot">${ic("zap", "lg")}</span> Payobook <span style="font-weight:600;color:var(--pb-primary)">Learn</span> <span class="badge-poc">${T("prototype")}</span></div>
        <div class="hub-controls">${headControls()}
          <a class="btn outline sm" href="analysis.html">${ic("book-open")} ${T("readAnalysis")}</a>
          <button class="btn subtle sm" data-act="reset">${ic("rotate-ccw")} ${T("reset")}</button>
        </div>
      </div>
      <div class="hub-hero">
        <h1>${T("hubTitle")}</h1>
        <p>${T("hubSub")}</p>
      </div>
      ${S.last && S.visited ? `
      <div class="hub-resume card">
        ${ic("play", "lg")} <div class="grow"><b>${T("resumeTitle")}</b><div class="muted small">${T("resumeBody")} ${tx(S.last.label)}</div></div>
        <button class="btn primary sm" data-go="${S.last.hash}">${T("resumeCta")} ${ic("arrow-right")}</button>
      </div>` : ""}
      <h3 style="font-size:14px;color:var(--pb-ink-2);margin-top:8px">${T("modeTitle")}</h3>
      <div class="mode-row">
        ${modes.map((m) => `<button class="mode-card ${S.mode === m[0] ? "on" : ""}" data-act="mode-${m[0]}">
          <span class="mc-ic">${ic(m[1], "lg")}</span><b>${tx(m[2])}</b></button>`).join("")}
      </div>
      <div class="concepts">
        ${this.concept(1, "map", "vis-journey", `<div class="line"></div><div class="stop done" style="left:15%"></div><div class="stop done" style="left:38%"></div><div class="stop" style="left:61%"></div><div class="stop" style="left:84%"></div><div class="runner"></div>`, "#/journey")}
        ${this.concept(2, "flask", "vis-sim", `<div class="pane p1"></div><div class="pane p2"></div><div class="flag"></div><span class="check">${ic("check-circle", "xl")}</span>`, "#/sim")}
        ${this.concept(3, "bot", "vis-ai", `<div class="bub b1"></div><div class="bub b2"></div><span class="ping">${ic("sparkles")}</span>`, "#/companion")}
      </div>
      <div class="hub-note">${ic("info")} <span>${tx(B_(
        "All three concepts run on the same simulated Payobook shell (real menu structure from pb_sidebar, real VN payroll maths). Progress and language survive refresh via localStorage. The full comparison, recommendation and roadmap live in <a href='analysis.html'>analysis.html</a>.",
        "Cả ba ý tưởng chạy trên cùng một giao diện Payobook mô phỏng (cấu trúc menu thật từ pb_sidebar, phép tính lương VN thật). Tiến độ và ngôn ngữ được giữ sau khi tải lại trang. Bản so sánh, khuyến nghị và lộ trình đầy đủ nằm trong <a href='analysis.html'>analysis.html</a>."))}</span></div>
    </div>`;
  },
  concept(n, icon, visCls, visHTML, href) {
    return `<div class="concept-card card">
      <div class="concept-vis ${visCls}">${visHTML}</div>
      <div class="concept-body">
        <h3>${ic(icon, "lg")} ${T("concept" + n)}</h3>
        <span class="tagline">${T("concept" + n + "Tag")}</span>
        <p>${T("concept" + n + "Desc")}</p>
        <div class="concept-foot"><button class="btn primary" data-go="${href}">${T("explore")} ${ic("arrow-right")}</button></div>
      </div>
    </div>`;
  },
  onAct(name) {
    if (name.startsWith("mode-")) {
      S.mode = name.slice(5); save(); this.render();
      const hints = {
        map: B_("The Journey concept fits this best — opening its map.", "Ý tưởng Hành trình hợp nhất — đang mở bản đồ."),
        role: B_("Role mode: menus and answers already adapt to the role picker above.", "Chế độ vai trò: menu và câu trả lời đã bám theo vai trò bạn chọn ở trên."),
        task: B_("Task mode: the ★ Run Payroll lesson is your fastest path.", "Chế độ công việc: bài ★ Chạy bảng lương là đường nhanh nhất."),
        explore: B_("Explore mode: the AI Companion keeps help one click away.", "Chế độ khám phá: Trợ lý AI luôn ở cạnh, cách một cú bấm."),
        test: B_("Test mode: jump into a lesson and go straight to its quick check.", "Chế độ kiểm tra: vào bài học và tới thẳng phần kiểm tra nhanh."),
      };
      toast(tx(hints[S.mode]), "", "lightbulb");
      if (S.mode === "map") setTimeout(() => { location.hash = "#/journey"; }, 900);
      if (S.mode === "explore") setTimeout(() => { location.hash = "#/companion"; }, 900);
      if (S.mode === "task" || S.mode === "test") setTimeout(() => { location.hash = "#/journey/lesson/L1"; }, 900);
    }
    if (name === "reset") { localStorage.removeItem("pbLearnPoc"); location.reload(); }
  },
};

/* ================================================== OPTION 1 — JOURNEY MAP */
const JourneyView = {
  q: "",
  stationState(st) {
    const p = S.progress[st.id];
    if (p && p.done) return "done";
    return "";
  },
  nextStation() {
    for (const line of ["payrun", "setup"]) for (const st of STATIONS[line]) {
      if (!(S.progress[st.id] && S.progress[st.id].done)) return st.id;
    }
    return null;
  },
  render() {
    Spot.hide();
    setLast(B_("Journey map", "Bản đồ hành trình"));
    const all = [...STATIONS.payrun, ...STATIONS.setup];
    const done = all.filter((s) => S.progress[s.id] && S.progress[s.id].done).length;
    const pct = Math.round((done / all.length) * 100);
    const next = this.nextStation();
    APP.innerHTML = `
    ${optHead(ic("map") + " " + T("concept1"))}
    <div class="jmap-wrap">
      <div class="jmap-hero">
        <div><h1>${T("journeyTitle")}</h1><p class="sub">${T("journeySub")}</p></div>
        <div class="jmap-overall card" style="padding:14px">
          <div style="display:flex;justify-content:space-between;font-size:12.5px;font-weight:700;margin-bottom:6px">
            <span>${T("overall")}</span><span class="num">${pct}%</span></div>
          <div class="pbar ${pct === 100 ? "green" : ""}"><i style="width:${pct}%"></i></div>
          ${done >= all.length ? `<div class="chip green" style="margin-top:8px">${ic("award")} ${T("completedBadge")}</div>` : ""}
        </div>
      </div>
      <div class="jmap-search">${ic("search")}<input type="search" placeholder="${T("searchLessons")}" value="${this.q}" data-act="jsearch" aria-label="${T("searchLessons")}"/></div>
      ${this.line("payrun", T("payrunLine"), "zap", next)}
      ${this.line("setup", T("setupLine"), "shield", next)}
    </div>`;
    const inp = $('[data-act="jsearch"]');
    inp.addEventListener("input", () => { this.q = inp.value; this.refreshLines(next); });
  },
  refreshLines(next) {
    $$(".jline").forEach((el) => el.remove());
    const wrap = $(".jmap-wrap");
    wrap.insertAdjacentHTML("beforeend", this.line("payrun", T("payrunLine"), "zap", next) + this.line("setup", T("setupLine"), "shield", next));
  },
  line(key, label, icon, next) {
    const sts = STATIONS[key].filter((st) => {
      if (!this.q) return true;
      const q = this.q.toLowerCase();
      return tx(st.title).toLowerCase().includes(q) || tx(st.desc).toLowerCase().includes(q);
    });
    const doneN = STATIONS[key].filter((s) => S.progress[s.id] && S.progress[s.id].done).length;
    const pct = Math.round((doneN / STATIONS[key].length) * 100);
    return `
    <div class="jline card">
      <div class="jline-h">${ic(icon, "lg")} <h2>${label}</h2>
        <div class="jl-progress"><div class="pbar"><i style="width:${pct}%"></i></div><span class="small num muted">${doneN}/${STATIONS[key].length}</span></div>
      </div>
      <div class="jline-sub">${key === "payrun"
        ? tx(B_("The monthly loop: import → compute → review → approve → pay → correct.", "Vòng lặp hằng tháng: nhập liệu → tính → soát xét → phê duyệt → chi trả → hiệu chỉnh."))
        : tx(B_("The rulebook behind every number: formulas, structures, statutory rates, connectors.", "Bộ quy tắc sau mỗi con số: công thức, cấu trúc, tỷ lệ bắt buộc, đầu nối dữ liệu."))}</div>
      <div class="jtrack">
        ${sts.map((st) => {
          const stt = this.stationState(st);
          const isNext = st.id === next;
          const dep = st.after ? [...STATIONS.payrun, ...STATIONS.setup].find((x) => x.id === st.after) : null;
          return `
          <div class="jstation ${stt} ${isNext ? "next" : ""}" data-act="station-${st.id}" role="button" tabindex="0">
            <span class="js-ic">${ic(stt === "done" ? "check" : st.icon, "lg")}</span>
            <div class="js-main">
              <div class="js-title">${tx(st.title)}
                ${st.star ? `<span class="chip">${ic("star")} ${T("fullLesson")}</span>` : ""}
                ${st.required ? `<span class="chip cyan">${T("required")}</span>` : `<span class="chip slate">${T("optional")}</span>`}
              </div>
              <div class="js-desc">${tx(st.desc)}</div>
              <div class="js-meta">
                <span class="chip slate">${ic("clock")} ${T("est")} ${st.mins} ${T("minutes")}</span>
                ${dep && !(S.progress[dep.id] && S.progress[dep.id].done) ? `<span class="jdep">${ic("alert-triangle")} ${T("dependsOn")}: ${tx(dep.title)}</span>` : ""}
                ${stt === "done" ? `<span class="chip green">${ic("check")} ${T("mastered")}</span>` : ""}
                ${S.progress[st.id] && !S.progress[st.id].done && S.progress[st.id].step ? `<span class="chip amber">${T("inProgress")}</span>` : ""}
              </div>
            </div>
            <span class="js-open">${ic("chevron-right", "lg")}</span>
          </div>`;
        }).join("")}
      </div>
    </div>`;
  },
  onAct(name) {
    if (name.startsWith("station-")) {
      const id = name.slice(8);
      const st = [...STATIONS.payrun, ...STATIONS.setup].find((x) => x.id === id);
      if (st.lesson) { location.hash = "#/journey/lesson/" + st.lesson; return; }
      this.outlineModal(st);
    }
  },
  outlineModal(st) {
    const o = st.outline;
    openModal(`
      <h3>${ic(st.icon, "lg")} ${tx(st.title)}</h3>
      <p class="muted small" style="margin-bottom:12px">${ic("info")} ${T("outlineNote")}</p>
      ${[["whatIs", "book-open", o.what], ["whyMatters", "lightbulb", o.why], ["whenUse", "clock", o.when], ["prereq", "list-checks", o.prereq], ["mistakes", "alert-triangle", o.mistakes]]
        .map((r) => `<div style="display:flex;gap:10px;margin-top:10px"><span style="color:var(--pb-primary)">${ic(r[1])}</span>
          <div><b style="font-size:12.5px">${T(r[0])}</b><div class="small" style="color:var(--pb-ink-2)">${tx(r[2])}</div></div></div>`).join("")}
      <div class="m-actions">
        <button class="btn outline" data-close>${T("close")}</button>
        <button class="btn primary" data-done-station="${st.id}">${ic("check")} ${T("gotIt")}</button>
      </div>`);
    $("[data-close]", modalEl).onclick = closeModal;
    $("[data-done-station]", modalEl).onclick = () => {
      S.progress[st.id] = { done: true }; save(); closeModal(); this.render();
      toast(tx(B_("Station complete", "Hoàn thành trạm")), "green", "check");
    };
  },
};

/* ------------------------------------------------- journey lesson player */
const LessonView = {
  lesson: null, idx: 0, playing: false, timer: null, morph: false, mode: "interactive",
  open(id) {
    this.lesson = LESSONS[id]; this.idx = (S.progress[this.lesson.station] && S.progress[this.lesson.station].step) || 0;
    if (this.idx >= this.lesson.steps.length) this.idx = 0;
    this.playing = false; this.morph = false;
    setLast(this.lesson.title);
    this.renderStep();
  },
  ctx() {
    const step = this.lesson.steps[this.idx];
    const c = { allNav: true };
    if (step.simulate === "computed" || this.lesson.id === "L1" && this.idx >= 5) { c.computed = true; c.decided = true; }
    if (this.lesson.id === "L1" && this.idx >= 1) c.division = "retail";
    if (step.morph) c.morph = this.morph;
    return c;
  },
  renderStep() {
    const L = this.lesson, step = L.steps[this.idx];
    APP.innerHTML = shellHTML(step.screen, this.ctx());
    this.renderPlayerBar();
    requestAnimationFrame(() => setTimeout(() => this.showCard(), 60));
  },
  showCard() {
    const L = this.lesson, step = L.steps[this.idx], n = L.steps.length;
    const memChip = step.trace ? `<div style="margin-top:10px"><span class="chip" data-anchor="${step.trace.from}">${ic("shield")} BHXH 8% · BHYT 1.5%</span> <span class="muted small">← ${tx(step.trace.label)}</span></div>` : "";
    const morphCtl = step.morph ? `
      <div class="seg" style="margin-top:10px">
        <button data-act="morph-0" class="${!this.morph ? "on" : ""}">${T("morphBefore")} · 1.5%</button>
        <button data-act="morph-1" class="${this.morph ? "on" : ""}">${T("morphAfter")} · 2%</button>
      </div>` : "";
    const html = `
      <div class="cc-kicker">${ic("sparkles")} ${T("coachKicker")} · ${tx(step.kicker)}</div>
      <h4>${tx(step.title)}</h4>
      <div class="cc-body" aria-live="polite">${tx(step.body)}</div>
      ${step.consequence ? `<div class="cc-consequence">${ic("alert-triangle")} <span>${tx(step.consequence)}</span></div>` : ""}
      ${step.tip ? `<div class="cc-tip">${ic("lightbulb")} <span>${tx(step.tip)}</span></div>` : ""}
      ${memChip}${morphCtl}
      <div class="cc-progress"><span class="small muted num">${T("stepOf")(this.idx + 1, n)}</span><div class="pbar"><i style="width:${((this.idx + 1) / n) * 100}%"></i></div></div>
      <div class="cc-controls">
        <button class="btn outline sm" data-act="l-prev" ${this.idx === 0 ? "disabled" : ""}>${ic("chevron-left")} ${T("prev")}</button>
        <button class="btn primary sm" data-act="l-next">${this.idx === n - 1 ? T("done") : T("next")} ${ic("chevron-right")}</button>
        <span class="spacer"></span>
        <button class="btn subtle sm" data-act="l-replay" title="${T("replay")}">${ic("rotate-ccw")}</button>
      </div>
      ${this.playing ? `<div class="autobar running"><i style="animation-duration:${this.stepMs()}ms"></i></div>` : ""}`;
    Spot.show(step.target, html);
    if (step.trace) setTimeout(() => Spot.trace(step.trace.from, step.target), reduced() ? 50 : 650);
    else Spot.clearTrace();
    if (step.morph && !this.morph && !reduced()) setTimeout(() => { if (L.steps[this.idx] === step && !this.morph) { this.morph = true; this.renderStep(); } }, 2200);
    if (this.playing) this.armTimer();
  },
  stepMs() {
    const step = this.lesson.steps[this.idx];
    const words = tx(step.body).replace(/<[^>]+>/g, "").split(/\s+/).length;
    return Math.max(4500, words * 300);
  },
  armTimer() {
    clearTimeout(this.timer);
    this.timer = setTimeout(() => { if (this.playing) this.next(); }, this.stepMs());
  },
  renderPlayerBar() {
    const n = this.lesson.steps.length;
    const bar = document.createElement("div");
    bar.className = "player-bar";
    bar.innerHTML = `
      <button data-act="l-exit" title="${T("exit")}" aria-label="${T("exit")}">${ic("x")}</button>
      <button data-act="l-prev" aria-label="${T("prev")}">${ic("chevron-left")}</button>
      <button data-act="l-toggle" aria-label="${this.playing ? T("pause") : T("play")}">${ic(this.playing ? "pause" : "play")}</button>
      <button data-act="l-next" aria-label="${T("next")}">${ic("chevron-right")}</button>
      <span class="pb-step num">${T("stepOf")(this.idx + 1, n)}</span>
      <button data-act="l-skip" title="${T("skip")}" aria-label="${T("skip")}">${ic("skip-forward")}</button>`;
    APP.appendChild(bar);
  },
  next() {
    clearTimeout(this.timer);
    if (this.idx < this.lesson.steps.length - 1) {
      this.idx++; this.morph = false;
      S.progress[this.lesson.station] = { step: this.idx }; save();
      this.renderStep();
    } else this.quiz();
  },
  prev() { clearTimeout(this.timer); if (this.idx > 0) { this.idx--; this.morph = false; this.renderStep(); } },
  quiz() {
    Spot.hide();
    const L = this.lesson, q = L.quiz;
    let answered = false;
    openModal(`
      <h3>${ic("help-circle", "lg")} ${T("quizTitle")}</h3>
      <p class="muted small">${T("quizWhy")}</p>
      <p style="margin-top:12px;font-weight:600">${tx(q.q)}</p>
      <div id="qopts">${q.opts.map((o, i) => `<button class="quiz-opt" data-q="${i}"><span class="qo-dot"></span><span>${tx(o.t)}</span></button>`).join("")}</div>
      <div id="qexpl"></div>
      <div class="m-actions" id="qact"></div>`, { noDismiss: true });
    $$("#qopts .quiz-opt", modalEl).forEach((btn) => {
      btn.onclick = () => {
        const i = +btn.dataset.q, o = q.opts[i];
        if (answered && !o.ok) return;
        btn.classList.add(o.ok ? "correct" : "wrong");
        $("#qexpl", modalEl).innerHTML = `<div class="quiz-expl ${o.ok ? "good" : "bad"}"><b>${o.ok ? T("correct") : T("notQuite")}</b> ${tx(o.expl)}</div>`;
        if (o.ok) {
          answered = true;
          $("#qact", modalEl).innerHTML = `<button class="btn primary" id="qdone">${ic("check")} ${T("done")}</button>`;
          $("#qdone", modalEl).onclick = () => this.complete();
        } else {
          $("#qact", modalEl).innerHTML = `<button class="btn outline" id="qreplay">${ic("rotate-ccw")} ${T("replay")}</button>`;
          $("#qreplay", modalEl).onclick = () => { closeModal(); this.idx = Math.max(0, this.lesson.steps.length - 2); this.renderStep(); };
        }
      };
    });
  },
  complete() {
    S.progress[this.lesson.station] = { done: true }; save();
    const both = ["runpayroll", "statutory"].every((s) => S.progress[s] && S.progress[s].done);
    const nxt = JourneyView.nextStation();
    const nextSt = nxt ? [...STATIONS.payrun, ...STATIONS.setup].find((x) => x.id === nxt) : null;
    openModal(`
      <div class="celebrate">
        <div class="halo">${ic(both ? "award" : "check-circle", "xl")}</div>
        <h3 style="justify-content:center">${T("lessonDone")}</h3>
        <p class="muted">${T("lessonDoneBody")}</p>
        ${both ? `<div class="chip green" style="margin-top:10px">${ic("award")} ${T("completedBadge")}</div>` : ""}
      </div>
      <div class="m-actions" style="justify-content:center">
        <button class="btn outline" id="cb-map">${T("backToMap")}</button>
        ${nextSt ? `<button class="btn primary" id="cb-next">${T("nextLesson")}: ${tx(nextSt.title)} ${ic("arrow-right")}</button>` : ""}
      </div>`, { noDismiss: true });
    $("#cb-map", modalEl).onclick = () => { closeModal(); location.hash = "#/journey"; };
    const nb = $("#cb-next", modalEl);
    if (nb) nb.onclick = () => {
      closeModal();
      location.hash = "#/journey";
      setTimeout(() => JourneyView.onAct("station-" + nextSt.id), 150);
    };
  },
  onAct(name) {
    if (name === "l-next") this.next();
    else if (name === "l-prev") this.prev();
    else if (name === "l-replay") this.renderStep();
    else if (name === "l-skip") { clearTimeout(this.timer); this.quiz(); }
    else if (name === "l-exit") { clearTimeout(this.timer); S.progress[this.lesson.station] = Object.assign({}, S.progress[this.lesson.station], { step: this.idx }); save(); Spot.hide(); location.hash = "#/journey"; }
    else if (name === "l-toggle") { this.playing = !this.playing; if (!this.playing) clearTimeout(this.timer); this.renderStep(); }
    else if (name === "morph-0") { this.morph = false; this.renderStep(); }
    else if (name === "morph-1") { this.morph = true; this.renderStep(); }
  },
  onKey(e) {
    if (e.key === "ArrowRight") this.next();
    else if (e.key === "ArrowLeft") this.prev();
    else if (e.key === "Escape") this.onAct("l-exit");
    else if (e.key === " " && !/input|textarea|select/i.test(e.target.tagName)) { e.preventDefault(); this.onAct("l-toggle"); }
  },
};

/* ================================================= OPTION 2 — SIMULATOR */
const SimView = {
  mission: null, stepIdx: 0, data: {},
  render() {
    Spot.hide();
    setLast(B_("Practice Studio", "Xưởng thực hành"));
    const confRows = [
      ["run", B_("Running payroll", "Chạy bảng lương")],
      ["approve", B_("Review & approvals", "Soát xét & phê duyệt")],
      ["setup", B_("Statutory setup", "Thiết lập bắt buộc")],
      ["formula", B_("Formula engine", "Công thức lương")],
    ];
    APP.innerHTML = `
    ${optHead(ic("flask") + " " + T("concept2"))}
    <div class="sandbox-banner">${ic("shield-check")} ${T("practiceOnly")} · Hoa Sen Retail Co. — 48 ${T("employees").toLowerCase()}, ${tx(B_("July 2026", "Tháng 7/2026"))}
      <span style="flex:1"></span><button class="btn subtle sm" data-act="sandbox-reset">${ic("rotate-ccw")} ${T("sandboxReset")}</button></div>
    <div class="sim-hub">
      <div class="hub-hero" style="margin-top:0"><h1 style="font-size:24px">${T("simTitle")}</h1><p>${T("simSub")}</p></div>
      <div class="sim-cols">
        <div>
          ${["payrun", "setup"].map((g) => `
          <div class="mission-group">
            <h2>${ic(g === "payrun" ? "zap" : "shield", "lg")} ${g === "payrun" ? T("missionsPayrun") : T("missionsSetup")}</h2>
            ${MISSIONS.filter((m) => m.group === g).map((m) => {
              const done = S.sim[m.id] && S.sim[m.id].done;
              return `<div class="mission card" data-act="mission-${m.id}" role="button" tabindex="0">
                <span class="m-ic">${ic(done ? "check" : m.icon, "lg")}</span>
                <div class="m-main"><b>${tx(m.title)}</b><div class="m-desc">${tx(m.desc)}</div>
                  <div class="m-meta">
                    <span class="chip slate">${ic("clock")} ${T("est")} ${m.mins} ${T("minutes")}</span>
                    <span class="chip">${T("confidenceUp")(m.conf.gain)}</span>
                    ${m.full ? "" : `<span class="chip amber">${ic("info")} ${tx(B_("outline", "dàn ý"))}</span>`}
                    ${done ? `<span class="chip green">${ic("check")} ${T("missionDone")}</span>` : ""}
                  </div></div>
                <span class="js-open">${ic("chevron-right", "lg")}</span>
              </div>`;
            }).join("")}
          </div>`).join("")}
        </div>
        <div class="conf-panel card">
          <h3 style="font-size:14px;display:flex;gap:8px;align-items:center">${ic("trending-up", "lg")} ${T("confidence")}</h3>
          <p class="muted small">${T("confidenceSub")}</p>
          ${confRows.map((r) => `<div class="conf-row"><div class="cr-h"><span>${tx(r[1])}</span><span class="num">${Math.min(100, S.conf[r[0]])}%</span></div>
            <div class="pbar ${S.conf[r[0]] >= 70 ? "green" : ""}"><i style="width:${Math.min(100, S.conf[r[0]])}%"></i></div></div>`).join("")}
        </div>
      </div>
    </div>`;
  },
  /* ---- mission runtime ---- */
  startMission(id) {
    const m = MISSIONS.find((x) => x.id === id);
    if (!m.full) { this.outlineMission(m); return; }
    this.mission = m; this.stepIdx = 0;
    this.data = { screen: m.id === "m1" ? "dashboard" : "dashboard" };
    setLast(m.title);
    this.renderMission();
  },
  outlineMission(m) {
    openModal(`
      <h3>${ic(m.icon, "lg")} ${tx(m.title)}</h3>
      <p class="muted small">${T("outlineMission")}</p>
      <div class="ab ab-steps" style="margin-top:12px">${m.outline.map((o) => `<div class="ab-step"><span>${tx(o)}</span></div>`).join("")}</div>
      <div class="m-actions"><button class="btn primary" data-close>${T("gotIt")}</button></div>`);
    $("[data-close]", modalEl).onclick = closeModal;
  },
  steps() { return !this.mission ? [] : (this.mission.id === "m1" ? M1_STEPS : M2_STEPS); },
  renderMission() {
    const m = this.mission, steps = this.steps(), cur = steps[this.stepIdx];
    const ctx = Object.assign({ allNav: true }, this.data);
    // glow wiring per step
    if (cur) {
      if (cur.id === "open") ctx.glowNav = cur.nav;
      if (m.id === "m1") {
        if (cur.id === "division") ctx.glow = "pw-division";
        if (cur.id === "compute") ctx.glow = "pw-compute";
        if (cur.id === "inspect") ctx.glow = "anomaly";
        if (cur.id === "submit") ctx.glow = "submit";
      } else {
        if (cur.id === "newversion") ctx.glow = "st-new";
        if (cur.id === "rate") ctx.glow = "st-bhyt";
        if (cur.id === "preview") ctx.glow = "st-preview";
      }
    }
    APP.innerHTML = `
    ${optHead(ic("flask") + " " + T("concept2"), "#/sim")}
    <div class="sandbox-banner">${ic("shield-check")} ${T("practiceOnly")}
      <span style="flex:1"></span><button class="btn subtle sm" data-act="mission-exit">${ic("x")} ${T("abandonMission")}</button></div>
    <div class="sim-stage">
      ${shellHTML(this.data.screen, ctx)}
      <aside class="mission-dock" aria-label="Mission">
        <div class="md-h"><span class="chip">${T("missionKicker")}</span><b style="display:block;margin-top:6px">${tx(m.title)}</b>
          <div class="pbar" style="margin-top:8px"><i style="width:${(this.stepIdx / steps.length) * 100}%"></i></div></div>
        <div class="md-steps">
          ${steps.map((s, i) => `
          <div class="mstep ${i < this.stepIdx ? "done" : ""} ${i === this.stepIdx ? "on" : ""}">
            <span class="ms-dot">${i < this.stepIdx ? ic("check") : i + 1}</span>
            <div class="ms-body"><b>${tx(s.t)}</b><span class="muted">${tx(s.d)}</span>
              <div class="ms-hint ${this.data.hint && i === this.stepIdx ? "show" : ""}">${ic("lightbulb")} ${tx(s.hint)}</div></div>
          </div>`).join("")}
        </div>
        <div class="md-f">
          <button class="btn outline sm" data-act="mission-hint">${ic("lightbulb")} ${T("showHint")}</button>
        </div>
      </aside>
    </div>`;
  },
  advance() {
    this.data.hint = false;
    this.stepIdx++;
    const steps = this.steps();
    if (this.stepIdx >= steps.length) { this.debrief(); return; }
    this.renderMission();
  },
  curStep() { return this.steps()[this.stepIdx]; },
  nav(id) {
    const cur = this.curStep();
    this.data.screen = id;
    if (cur && cur.id === "open" && id === cur.nav) { this.advance(); toast(tx(B_("Good — this is the place.", "Chuẩn — đúng chỗ rồi.")), "green", "check"); }
    else this.renderMission();
  },
  onAct(name, el) {
    const m = this.mission, cur = this.curStep();
    if (name === "mission-exit") { location.hash = "#/sim"; return; }
    if (name === "mission-hint") { this.data.hint = true; this.renderMission(); return; }
    if (name === "sandbox-reset") { S.sim = {}; S.conf = Object.assign({}, DEFAULT_STATE.conf); save(); this.render(); toast(tx(B_("Sandbox reset.", "Đã đặt lại môi trường.")), "", "rotate-ccw"); return; }
    if (name.startsWith("mission-")) { this.startMission(name.slice(8)); return; }
    if (!m) return;

    if (m.id === "m1") {
      if (name === "pw-compute") {
        if (!this.data.division) { toast(tx(B_("Choose a division first.", "Hãy chọn bộ phận trước.")), "amber", "alert-triangle"); return; }
        this.consequenceModal();
      }
      if (name === "pw-anomaly" && cur && cur.id === "inspect") { this.advance(); this.anomalyModal(); }
      if (name === "pw-submit" && cur && cur.id === "submit") this.pipelineModal();
      if (name === "pw-recompute") toast(tx(B_("Drafts recomputed — same result (inputs unchanged).", "Đã tính lại bản nháp — kết quả không đổi (đầu vào giữ nguyên).")), "", "rotate-ccw");
    }
    if (m.id === "m2") {
      if (name === "st-new" && cur && cur.id === "newversion") {
        this.data.stVersion2 = true; this.advance();
        toast(tx(B_("Draft v2 created — the live policy is untouched.", "Đã tạo nháp v2 — chính sách đang chạy không bị đụng tới.")), "green", "git-branch");
      }
      if (name === "st-rate" && cur && cur.id === "rate") this.rateModal();
      if (name === "st-preview" && cur && cur.id === "preview") this.previewModal();
    }
  },
  onChange(name, el) {
    if (!this.mission) return;
    const cur = this.curStep();
    if (this.mission.id === "m1" && name === "pw-division" && cur && cur.id === "division") {
      if (el.value === "retail") { this.data.division = "retail"; this.advance(); }
      else if (el.value) {
        toast(tx(B_("Not wrong — but July inputs are only committed for Retail. Pick Retail — Hà Nội.", "Không sai — nhưng dữ liệu tháng 7 mới ghi nhận cho Bán lẻ. Hãy chọn Bán lẻ — Hà Nội.")), "amber", "info");
        el.value = "";
      }
    }
  },
  consequenceModal() {
    openModal(`
      <h3>${ic("alert-triangle", "lg")} ${T("consequenceTitle")}</h3>
      <table class="tbl" style="margin-top:8px">
        <tr><td style="width:40%"><b>${T("consequenceAffects")}</b></td><td>${tx(B_("48 draft payslips · Retail — Hà Nội · July 2026 only", "48 phiếu lương nháp · Bán lẻ — Hà Nội · chỉ Tháng 7/2026"))}</td></tr>
        <tr><td><b>${T("consequenceReversible")}</b></td><td>${tx(B_("Yes — drafts can be deleted or recomputed freely", "Có — bản nháp xoá hoặc tính lại thoải mái"))}</td></tr>
        <tr><td><b>${T("consequenceCheck")}</b></td><td>${tx(B_("Import committed (98.5%) · config v12 · 48 eligible", "Nhập liệu đã ghi nhận (98,5%) · cấu hình v12 · 48 người đủ điều kiện"))}</td></tr>
      </table>
      <div class="ab-ok" style="margin-top:12px">${ic("shield-check")} ${tx(B_("Practice mode: this cannot reach production even if wrong.", "Chế độ thực hành: kể cả sai cũng không thể chạm dữ liệu thật."))}</div>
      <div class="m-actions"><button class="btn outline" data-close>${T("cancel")}</button>
        <button class="btn primary" id="cq-go">${ic("play")} ${T("proceed")}</button></div>`);
    $("[data-close]", modalEl).onclick = closeModal;
    $("#cq-go", modalEl).onclick = () => {
      closeModal();
      this.data.computing = true; this.renderMission();
      setTimeout(() => {
        this.data.computing = false; this.data.computed = true;
        this.advance();
        toast(tx(B_("48 drafts created — 1 flagged for review.", "Đã tạo 48 bản nháp — 1 phiếu bị gắn cờ.")), "green", "check");
      }, reduced() ? 150 : 1300);
    };
  },
  anomalyModal() {
    openModal(`
      <h3>${ic("alert-triangle", "lg")} ${EMP.hung.name} — ${tx(B_("overtime spike", "tăng ca đột biến"))}</h3>
      <div class="evsa">
        <div class="col"><h5>${tx(B_("Expected (Jun avg)", "Kỳ vọng (TB tháng 6)"))}</h5>
          <b class="num" style="font-size:18px">${fmt(EMP.hung.otJun)}</b><p class="muted small">${tx(B_("≈ 12 OT hours", "≈ 12 giờ tăng ca"))}</p></div>
        <div class="col"><h5>${tx(B_("Actual (July)", "Thực tế (tháng 7)"))}</h5>
          <b class="num" style="font-size:18px">${fmt(EMP.hung.otJul)}</b><p class="small delta">+282% ${tx(B_("vs June", "so tháng 6"))}</p></div>
      </div>
      <p class="small muted" style="margin-top:10px">${tx(B_("The import shows 46 OT hours. Warehouse stocktake ran in July — it might be genuine. What do you do?", "File nhập ghi 46 giờ tăng ca. Tháng 7 có kiểm kê kho — có thể là thật. Bạn xử lý thế nào?"))}</p>
      <div class="m-actions">
        <button class="btn outline" id="an-accept">${T("acceptAnyway")}</button>
        <button class="btn primary" id="an-flag">${ic("clipboard-check")} ${T("flagReview")}</button>
      </div>`);
    $("#an-flag", modalEl).onclick = () => { closeModal(); this.decide(true); };
    $("#an-accept", modalEl).onclick = () => { closeModal(); this.recovery(); };
  },
  recovery() {
    openModal(`
      <h3>${ic("lightbulb", "lg")} ${T("recoveryTitle")}</h3>
      <p style="font-size:13.5px">${tx(B_(
        "A 282% spike <b>might</b> be real — but payroll never assumes. Accepting it silently means nobody checks the timesheet, and if it's a data-entry error (4.6h → 46h is a classic), Hùng gets overpaid and July closes wrong. Flagging costs one Slack message; an overpayment costs a clawback conversation.",
        "Mức tăng 282% <b>có thể</b> là thật — nhưng nghề lương không bao giờ giả định. Chấp nhận trong im lặng nghĩa là không ai đối chiếu bảng chấm công, và nếu là lỗi nhập liệu (4,6h → 46h là lỗi kinh điển), Hùng bị trả thừa và kỳ tháng 7 chốt sai. Gắn cờ chỉ tốn một tin nhắn; trả thừa tốn cả một cuộc nói chuyện thu hồi."))}</p>
      <div class="m-actions">
        <button class="btn primary" id="rc-flag">${ic("clipboard-check")} ${T("flagReview")}</button>
      </div>`, { noDismiss: true });
    $("#rc-flag", modalEl).onclick = () => { closeModal(); this.decide(false); };
  },
  decide(firstTry) {
    this.data.decided = true;
    this.data.firstTry = firstTry;
    this.advance();
    toast(tx(B_("Flagged — HR will see your note in review.", "Đã gắn cờ — HR sẽ thấy ghi chú của bạn khi soát xét.")), "green", "clipboard-check");
  },
  pipelineModal() {
    const stages = T("pipeline");
    openModal(`
      <h3>${ic("send", "lg")} ${tx(B_("Submitted — watch it travel", "Đã trình — xem đợt lương di chuyển"))}</h3>
      <div style="display:flex;gap:6px;align-items:center;margin:18px 0;flex-wrap:wrap" id="pipe">
        ${stages.map((s, i) => `<span class="chip ${i === 0 ? "on" : "slate"}" data-pipe="${i}">${s}</span>${i < 4 ? ic("chevron-right") : ""}`).join("")}
      </div>
      <p class="muted small">${tx(B_("Each gate is one role: Officer checks inputs, HR reviews people, GM owns the total. A rejection at any gate returns the run to Draft with a written reason.", "Mỗi cổng là một vai trò: CV tính lương kiểm dữ liệu, HR soát con người, TGĐ chịu trách nhiệm tổng. Từ chối ở bất kỳ cổng nào sẽ trả đợt về Nháp kèm lý do."))}</p>
      <div class="m-actions"><button class="btn primary" id="pp-done">${T("continueBtn")}</button></div>`, { noDismiss: true });
    let i = 0;
    const iv = setInterval(() => {
      i++; if (i > 1 || !modalEl) { clearInterval(iv); return; }
      $$("#pipe .chip", modalEl).forEach((c, j) => { c.className = "chip " + (j <= i ? "on" : "slate"); });
    }, reduced() ? 10 : 900);
    $("#pp-done", modalEl).onclick = () => { clearInterval(iv); closeModal(); this.data.submitted = true; this.debrief(); };
  },
  rateModal() {
    openModal(`
      <h3>${ic("percent", "lg")} ${tx(B_("BHYT — employee share (draft v2)", "BHYT — phần người lao động (nháp v2)"))}</h3>
      <p class="muted small">${tx(B_("The fictional decree sets it to 2.0% . Pick the new rate:", "Nghị định giả lập quy định 2,0%. Chọn tỷ lệ mới:"))}</p>
      <div style="display:flex;gap:8px;margin-top:12px">
        ${["1.5", "2.0", "3.0"].map((r) => `<button class="btn outline" data-rate="${r}">${r}%</button>`).join("")}
      </div>
      <div class="m-actions"><button class="btn subtle" data-close>${T("cancel")}</button></div>`);
    $("[data-close]", modalEl).onclick = closeModal;
    $$("[data-rate]", modalEl).forEach((b) => b.onclick = () => {
      const v = b.dataset.rate;
      if (v === "2.0") { closeModal(); this.data.stRate = "2.0"; this.advance(); this.effectiveModal(); }
      else if (v === "1.5") toast(tx(B_("That's the current rate — the decree changes it.", "Đó là tỷ lệ hiện tại — nghị định thay đổi nó.")), "amber", "info");
      else toast(tx(B_("3% is the employer share — you're editing the employee share.", "3% là phần doanh nghiệp — bạn đang sửa phần người lao động.")), "amber", "alert-triangle");
    });
  },
  effectiveModal() {
    openModal(`
      <h3>${ic("clock", "lg")} ${tx(B_("When should v2 take effect?", "v2 nên có hiệu lực từ khi nào?"))}</h3>
      <p class="muted small">${tx(B_("The July run is still open (awaiting GM).", "Đợt tháng 7 vẫn đang mở (chờ TGĐ)."))}</p>
      <button class="quiz-opt" id="ef-now"><span class="qo-dot"></span><span>${tx(B_("Immediately (today, 6 Aug)", "Ngay lập tức (hôm nay, 6/8)"))}</span></button>
      <button class="quiz-opt" id="ef-aug"><span class="qo-dot"></span><span>${tx(B_("From 1 August 2026", "Từ 01/08/2026"))}</span></button>
      <div id="ef-x"></div>`, { noDismiss: true });
    $("#ef-now", modalEl).onclick = () => {
      $("#ef-now", modalEl).classList.add("wrong");
      $("#ef-x", modalEl).innerHTML = `<div class="quiz-expl bad"><b>${T("notQuite")}</b> ${tx(B_(
        "'Immediately' includes July — if the open run recomputes, July payslips get August rates. The safe pattern: dated versions that start on a period boundary.",
        "'Ngay lập tức' bao trùm cả tháng 7 — nếu đợt đang mở tính lại, phiếu tháng 7 sẽ nhận tỷ lệ của tháng 8. Cách an toàn: phiên bản có ngày hiệu lực bắt đầu đúng ranh giới kỳ."))}</div>`;
    };
    $("#ef-aug", modalEl).onclick = () => {
      closeModal();
      this.data.stEffective = "01/08/2026";
      this.advance();
      toast(tx(B_("Effective 01/08 — July stays untouched.", "Hiệu lực 01/08 — tháng 7 không bị ảnh hưởng.")), "green", "check");
    };
  },
  previewModal() {
    openModal(`
      <h3>${ic("eye", "lg")} ${tx(B_("Impact preview — Nguyễn Thị Mai", "Xem trước tác động — Nguyễn Thị Mai"))}</h3>
      <div class="ab-calc" style="margin-top:10px"><table>
        <tr><td></td><td class="r"><b>${T("morphBefore")} (1.5%)</b></td><td class="r"><b>${T("morphAfter")} (2.0%)</b></td><td class="r"><b>Δ</b></td></tr>
        <tr><td>BHYT</td><td class="r num">−180,000</td><td class="r num">−240,000</td><td class="r num">−60,000</td></tr>
        <tr><td>${tx(B_("Taxable income", "TN chịu thuế"))}</td><td class="r num">2,020,000</td><td class="r num">1,960,000</td><td class="r num">−60,000</td></tr>
        <tr><td>${tx(B_("PIT", "Thuế TNCN"))}</td><td class="r num">−101,000</td><td class="r num">−98,000</td><td class="r num">+3,000</td></tr>
        <tr><td>${T("net")}</td><td class="r num">12,919,000</td><td class="r num">12,862,000</td><td class="r num"><b>−57,000</b></td></tr>
      </table></div>
      <p class="muted small" style="margin-top:10px">${tx(B_("Note how PIT slightly falls — higher insurance means lower taxable income. The system computed the knock-on for you.", "Để ý thuế TNCN giảm nhẹ — bảo hiểm cao hơn khiến thu nhập chịu thuế thấp hơn. Hệ thống đã tính giúp bạn hiệu ứng dây chuyền."))}</p>
      <div class="m-actions">
        <button class="btn outline" id="pv-undo">${ic("undo")} ${T("undo")}</button>
        <button class="btn primary" id="pv-commit">${ic("check")} ${tx(B_("Commit v2 (practice)", "Ghi nhận v2 (thực hành)"))}</button>
      </div>`);
    $("#pv-undo", modalEl).onclick = () => {
      closeModal(); this.data = { screen: "statutory" }; this.stepIdx = 1; this.renderMission();
      toast(tx(B_("Draft v2 discarded — sandbox restored.", "Đã huỷ nháp v2 — môi trường khôi phục.")), "", "undo");
    };
    $("#pv-commit", modalEl).onclick = () => { closeModal(); this.debrief(); };
  },
  debrief() {
    const m = this.mission;
    const didList = m.id === "m1" ? [
      B_("Computed 48 July drafts for Retail after a consequence check", "Tính 48 bản nháp tháng 7 cho Bán lẻ sau khi soát hậu quả"),
      this.data.firstTry === false ? B_("Recovered from an 'accept blindly' instinct and flagged the OT spike", "Nhận ra và sửa phản xạ 'chấp nhận bừa', đã gắn cờ tăng ca đột biến") : B_("Flagged a 282% OT spike for timesheet verification", "Gắn cờ tăng ca đột biến 282% để đối chiếu chấm công"),
      B_("Submitted into the Officer → HR → GM pipeline", "Trình vào quy trình CV tính lương → HR → TGĐ"),
    ] : [
      B_("Versioned the policy instead of editing live rates", "Tạo phiên bản chính sách thay vì sửa đè tỷ lệ đang chạy"),
      B_("Chose a period-boundary effective date (01/08)", "Chọn ngày hiệu lực đúng ranh giới kỳ (01/08)"),
      B_("Previewed the payslip impact (net −57,000 ₫) before committing", "Xem trước tác động lên phiếu lương (thực nhận −57.000 ₫) rồi mới ghi nhận"),
    ];
    const check = m.id === "m1" ? [
      B_("Headcount vs expected", "Sĩ số so với kỳ vọng"), B_("All flags resolved", "Mọi cờ đã xử lý"),
      B_("Total net variance vs last month explained", "Giải thích được biến động tổng so tháng trước"),
    ] : [
      B_("No open runs inside the effective window", "Không còn đợt mở trong khoảng hiệu lực"),
      B_("One payslip previewed per affected division", "Xem trước một phiếu cho mỗi bộ phận bị ảnh hưởng"),
      B_("The change documented with its decree", "Thay đổi được lưu kèm văn bản pháp lý"),
    ];
    const gain = this.data.firstTry === false ? Math.round(m.conf.gain * 0.7) : m.conf.gain;
    S.sim[m.id] = { done: true };
    S.conf[m.conf.key] = Math.min(100, (S.conf[m.conf.key] || 0) + gain);
    save();
    openModal(`
      <div class="celebrate"><div class="halo">${ic("award", "xl")}</div>
        <h3 style="justify-content:center">${T("debriefTitle")}</h3></div>
      <b class="small">${T("whatYouDid")}</b>
      <div class="ab ab-steps" style="margin-top:6px">${didList.map((d) => `<div class="ab-step"><span>${tx(d)}</span></div>`).join("")}</div>
      <b class="small" style="display:block;margin-top:14px">${T("checklist")}</b>
      <div style="margin-top:6px">${check.map((c) => `<div style="display:flex;gap:8px;padding:4px 0" class="small">${ic("check-circle")} ${tx(c)}</div>`).join("")}</div>
      <div class="chip green" style="margin-top:14px">${ic("trending-up")} ${T("confidenceUp")(gain)}</div>
      <div class="m-actions"><button class="btn primary" id="db-done">${T("done")}</button></div>`, { noDismiss: true });
    $("#db-done", modalEl).onclick = () => { closeModal(); this.mission = null; location.hash = "#/sim"; this.render(); };
  },
};

/* ================================================ OPTION 3 — COMPANION */
const CompView = {
  screen: "runpayroll", msgs: [], dockOpen: false,
  render() {
    Spot.hide();
    setLast(B_("AI Companion", "Trợ lý AI"));
    const ctx = SCREEN_CTX[this.screen] || SCREEN_CTX.dashboard;
    const hidden = ROLE_HIDE[S.role] || [];
    if (hidden.includes(this.screen)) this.screen = "dashboard";
    APP.innerHTML = `
    ${optHead(ic("bot") + " " + T("concept3"))}
    <div class="comp-stage">
      ${shellHTML(this.screen, { computed: this.screen === "runpayroll" ? this.computed : false, division: this.computed ? "retail" : "" })}
      <aside class="comp-dock ${this.dockOpen ? "open" : ""}" aria-label="${T("compTitle")}">
        <div class="cd-h"><span class="cd-ava">${ic("sparkles")}</span>
          <div><b>${T("compTitle")}</b><span>${T("compSub")}: ${screenTitle(this.screen)}</span></div></div>
        <div class="comp-guard">${ic("shield-check")} ${T("compGuard")}</div>
        <div class="comp-scroll" id="comp-scroll">
          <div class="ctx-card"><div class="cx-k">${T("youAreOn")}: ${screenTitle(this.screen)}</div>
            <p>${tx((SCREEN_CTX[this.screen] || {}).blurb)}</p></div>
          <div><div class="cx-k" style="font-size:10.5px;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:var(--pb-muted);margin-bottom:6px">${T("suggested")}</div>
            <div class="sugg">${(SCREEN_CTX[this.screen] || { chips: [] }).chips.map((id) => {
              const qa = QA.find((q) => q.id === id);
              return qa ? `<button data-act="qa-${qa.id}">${tx(qa.label)}</button>` : "";
            }).join("")}</div></div>
          ${this.msgs.map((m) => m.html).join("")}
        </div>
        <div class="comp-input">
          <input id="comp-q" type="text" placeholder="${T("askPlaceholder")}" aria-label="${T("askPlaceholder")}"/>
          <button class="send" data-act="comp-send" aria-label="${T("send")}">${ic("send")}</button>
        </div>
      </aside>
      <button class="comp-fab" data-act="comp-fab" aria-label="${T("compTitle")}">${ic("message-circle", "lg")}</button>
    </div>`;
    const inp = $("#comp-q");
    inp.addEventListener("keydown", (e) => { if (e.key === "Enter") this.ask(inp.value); });
    this.scrollDown();
  },
  scrollDown() { const sc = $("#comp-scroll"); if (sc) sc.scrollTop = sc.scrollHeight; },
  nav(id) { this.screen = id; this.render(); },
  ask(text) {
    text = (text || "").trim();
    if (!text) return;
    const qa = this.matchQA(text);
    this.pushUser(text);
    this.answer(qa);
  },
  matchQA(text) {
    const t = text.toLowerCase();
    let best = null, bestScore = 0;
    for (const qa of QA) {
      for (const m of qa.match || []) {
        if (t.includes(m) && m.length > bestScore) { best = qa; bestScore = m.length; }
      }
    }
    return best;
  },
  pushUser(text) {
    this.msgs.push({ html: `<div class="msg user"><span class="who">${T("roles")[S.role]}</span><span class="bub">${text.replace(/</g, "&lt;")}</span></div>` });
    this.render();
  },
  answer(qa, opts) {
    // typing indicator then answer
    const typing = `<div class="msg ai" id="typing"><span class="bub typing"><i></i><i></i><i></i></span></div>`;
    this.msgs.push({ html: typing, temp: true });
    this.render();
    setTimeout(() => {
      this.msgs = this.msgs.filter((m) => !m.temp);
      this.msgs.push({ html: this.answerHTML(qa, opts) });
      this.render();
    }, reduced() ? 60 : 750);
  },
  answerHTML(qa, opts) {
    if (!qa) return this.wrapAI(`<p>${T("fallback")}</p>`);
    let blocks;
    if (qa.permission) blocks = APPROVE_BY_ROLE[S.role].blocks;
    else if (qa.roleAware) blocks = qa.roleAware[S.role] ? qa.roleAware[S.role].blocks : qa.roleAware.viewer.blocks;
    else if (qa.perScreen) blocks = this.whatPageBlocks();
    else blocks = qa.blocks;
    if (opts && opts.simpler && qa.simpler) blocks = [{ p: qa.simpler }];
    let html = blocks.map((b) => this.blockHTML(b)).join("");
    if (qa.permission || qa.roleAware) html += `<div class="ab-src">${ic("users")} ${T("roleNote")}: <b>${T("roles")[S.role]}</b></div>`;
    // footer actions
    const foot = [];
    if (qa.showme || (blocks || []).some((b) => b.steps)) foot.push(`<button class="btn ghost sm" data-act="showme-${qa.id}">${ic("eye")} ${T("showMe")}</button>`);
    if (qa.simpler && !(opts && opts.simpler)) foot.push(`<button class="btn outline sm" data-act="simpler-${qa.id}">${ic("message-circle")} ${T("simpler")}</button>`);
    if (foot.length) html += `<div class="ab ab-links">${foot.join("")}</div>`;
    return this.wrapAI(html);
  },
  wrapAI(inner) { return `<div class="msg ai"><span class="who">PayAI</span><span class="bub">${inner}</span></div>`; },
  blockHTML(b) {
    if (b.p) return `<p>${this.gloss(tx(b.p))}</p>`;
    if (b.warn) return `<div class="ab ab-warn">${ic("alert-triangle")} <span>${tx(b.warn)}</span></div>`;
    if (b.ok) return `<div class="ab ab-ok">${ic("shield-check")} <span>${tx(b.ok)}</span></div>`;
    if (b.src) return `<div class="ab-src">${ic("book-open")} ${T("grounded")}: ${tx(b.src)} <button class="btn subtle sm" style="padding:2px 7px" title="${T("whySeeing")}">${ic("help-circle")}</button></div>`;
    if (b.steps) return `<div class="ab ab-steps">${b.steps.map((s) => `
      <div class="ab-step"><span>${tx(s.t)}</span>${s.target ? `<button class="btn subtle sm pt" data-act="point-${s.target}" title="${T("showMe")}">${ic("target")}</button>` : ""}</div>`).join("")}</div>`;
    if (b.calc) return `<div class="ab ab-calc"><table>${b.calc.title ? `<tr><td colspan="3"><b>${tx(b.calc.title)}</b></td></tr>` : ""}
      ${b.calc.rows.map((r) => `<tr><td>${tx(r[0])}</td><td class="r num">${r[1]}</td><td class="r num">${r[2] || ""}</td></tr>`).join("")}</table></div>`;
    if (b.links) return `<div class="ab ab-links">${b.links.map((l) => {
      const [kind, id] = l.split(":");
      if (kind === "lesson") return `<button class="btn ghost sm" data-act="go-lesson-${id}">${ic("map")} ${T("openLessonLink")}: ${tx(LESSONS[id].title)}</button>`;
      const m = MISSIONS.find((x) => x.id === id);
      return `<button class="btn ghost sm" data-act="go-mission-${id}">${ic("flask")} ${T("letMeTry")}: ${tx(m.title)}</button>`;
    }).join("")}</div>`;
    if (b.more) return `<div class="ab ab-more"><button data-more>${ic("chevron-down")} ${T("tellMore")}</button><div class="more-body">${tx(b.more.body)}</div></div>`;
    return "";
  },
  gloss(html) {
    // wrap known terms with hover definitions (first occurrence only)
    for (const k of Object.keys(GLOSSARY)) {
      const g = GLOSSARY[k], term = tx(g.term);
      const re = new RegExp(`\\b(${term})\\b`);
      if (re.test(html) && !html.includes("class=\"term\"")) {
        html = html.replace(re, `<span class="term" tabindex="0" data-def="${tx(g.def).replace(/"/g, "&quot;")}">$1</span>`);
      }
    }
    return html;
  },
  showMe(qa) {
    const blocks = qa.permission ? APPROVE_BY_ROLE[S.role].blocks : (qa.roleAware ? (qa.roleAware[S.role] || qa.roleAware.viewer).blocks : qa.blocks) || [];
    const targets = [];
    for (const b of blocks) if (b.steps) for (const s of b.steps) if (s.target) targets.push(s.target);
    if (!targets.length) return;
    let i = 0;
    const stepFlash = () => {
      if (i >= targets.length) return;
      const t = targets[i];
      if (t.startsWith("nav-")) flashRing(t);
      else if (!flashRing(t)) flashRing("nav-" + this.screen);
      i++;
      setTimeout(stepFlash, reduced() ? 350 : 1250);
    };
    stepFlash();
  },
  whatPageBlocks() {
    const st = [...STATIONS.payrun, ...STATIONS.setup].find((x) => x.id === this.screen);
    const blocks = [{ p: (SCREEN_CTX[this.screen] || {}).blurb }];
    if (st && st.outline) {
      blocks.push({ steps: [
        { t: B_(`<b>Why:</b> ${st.outline.why.en}`, `<b>Vì sao:</b> ${st.outline.why.vi}`) },
        { t: B_(`<b>When:</b> ${st.outline.when.en}`, `<b>Khi nào:</b> ${st.outline.when.vi}`) },
        { t: B_(`<b>Watch out:</b> ${st.outline.mistakes.en}`, `<b>Cẩn thận:</b> ${st.outline.mistakes.vi}`) },
      ] });
    }
    if (st && st.lesson) blocks.push({ links: ["lesson:" + st.lesson] });
    else if (st && st.star) blocks.push({ links: ["lesson:" + (st.id === "runpayroll" ? "L1" : "L2")] });
    blocks.push({ src: B_(`${screenTitle(this.screen)} · Payobook sidebar`, `${screenTitle(this.screen)} · thanh menu Payobook`) });
    return blocks;
  },
  onAct(name) {
    if (name === "comp-send") { this.ask($("#comp-q").value); return; }
    if (name === "comp-fab") { this.dockOpen = !this.dockOpen; this.render(); return; }
    if (name.startsWith("qa-")) {
      const qa = QA.find((q) => q.id === name.slice(3));
      this.pushUser(tx(qa.label)); this.answer(qa); return;
    }
    if (name.startsWith("simpler-")) {
      const qa = QA.find((q) => q.id === name.slice(8));
      this.pushUser(T("simpler")); this.answer(qa, { simpler: true }); return;
    }
    if (name.startsWith("showme-")) { const qa = QA.find((q) => q.id === name.slice(7)); this.showMe(qa); return; }
    if (name.startsWith("point-")) { const t = name.slice(6); if (!flashRing(t)) toast(tx(B_("That control lives on another screen — use Show me.", "Nút đó ở màn hình khác — hãy dùng Chỉ cho tôi.")), "", "info"); return; }
    if (name.startsWith("go-lesson-")) { location.hash = "#/journey/lesson/" + name.slice(10); return; }
    if (name.startsWith("go-mission-")) { location.hash = "#/sim"; setTimeout(() => SimView.startMission(name.slice(11)), 120); return; }
    if (name === "appr-ok") toast(tx(B_("(Prototype) Approved — the run moves to the next gate.", "(Bản thử) Đã phê duyệt — đợt chuyển sang cổng kế tiếp.")), "green", "check");
    if (name === "appr-no") toast(tx(B_("(Prototype) A reason dialog would open here.", "(Bản thử) Hộp thoại nhập lý do sẽ mở ở đây.")), "", "info");
    if (name === "pw-compute") { this.computed = true; this.render(); toast(tx(B_("(Prototype) Drafts created — ask me what to check next.", "(Bản thử) Đã tạo bản nháp — hãy hỏi tôi cần kiểm tra gì tiếp.")), "green", "check"); }
  },
};

/* ================================================================ router */
let CUR = HubView;
function route() {
  closeModal(); Spot.hide();
  const h = location.hash || "#/hub";
  S.visited = true; save();
  if (h.startsWith("#/journey/lesson/")) { CUR = LessonView; LessonView.open(h.split("/").pop()); }
  else if (h.startsWith("#/journey")) { CUR = JourneyView; JourneyView.render(); }
  else if (h.startsWith("#/sim")) { CUR = SimView; SimView.mission = null; SimView.render(); }
  else if (h.startsWith("#/companion")) { CUR = CompView; CompView.render(); }
  else { CUR = HubView; HubView.render(); }
}
window.addEventListener("hashchange", route);

/* global delegated events */
document.addEventListener("click", (e) => {
  const go = e.target.closest("[data-go]");
  if (go) { location.hash = go.dataset.go; return; }
  const nav = e.target.closest("[data-nav]");
  if (nav) {
    const id = nav.dataset.nav;
    if (CUR === SimView && SimView.mission) SimView.nav(id);
    else if (CUR === CompView) CompView.nav(id);
    else if (CUR === LessonView) toast(tx(B_("Navigation is driven by the lesson here — use Next.", "Trong bài học, việc chuyển màn hình do bài dẫn dắt — hãy dùng Tiếp theo.")), "", "info");
    return;
  }
  const act = e.target.closest("[data-act]");
  if (act) {
    const name = act.dataset.act;
    // shared header actions
    if (name === "lang-en" || name === "lang-vi") { S.lang = name.slice(5); save(); rerender(); return; }
    if (name.startsWith("role-")) { S.role = name.slice(5); save(); rerender(); toast(T("roleNote") + ": " + T("roles")[S.role], "", "users"); return; }
    if (name === "motion") { S.motion = S.motion === "reduced" ? "auto" : "reduced"; document.documentElement.dataset.motion = S.motion; save(); rerender(); return; }
    if (name === "sb-open") { const sb = $(".sb"); if (sb) sb.classList.add("open"); return; }
    if (name === "sb-close") { const sb = $(".sb"); if (sb) sb.classList.remove("open"); return; }
    if (CUR.onAct) CUR.onAct(name, act);
    return;
  }
  const more = e.target.closest("[data-more]");
  if (more) { more.parentElement.classList.toggle("open"); return; }
});
document.addEventListener("change", (e) => {
  const el = e.target.closest("[data-act]");
  if (el && CUR.onChange) CUR.onChange(el.dataset.act, el);
});
document.addEventListener("keydown", (e) => {
  if (CUR === LessonView && LessonView.lesson && !modalEl) LessonView.onKey(e);
  else if (e.key === "Escape" && modalEl) closeModal();
});
window.addEventListener("resize", () => { if (CUR === LessonView && LessonView.lesson) LessonView.renderStep(); });

function rerender() {
  if (CUR === LessonView && LessonView.lesson) LessonView.renderStep();
  else if (CUR === SimView && SimView.mission) SimView.renderMission();
  else if (CUR.render) CUR.render();
}

/* boot */
document.documentElement.dataset.motion = S.motion;
document.documentElement.lang = S.lang;
route();
