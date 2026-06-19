/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onPatched } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const GROUPS = ["Inputs", "Earnings", "Deductions", "Totals"];
const CAT_COLOR = { info: "#0E7490", earn: "#4F46E5", ded: "#B45309", total: "#059669" };
const OPSYM = { "+": "+", "-": "−", "*": "×", "/": "÷", "^": "^" };

export class PbFormulaStudio extends Component {
    static template = "pb_formula_studio.PbFormulaStudio";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.state = useState({
            loaded: false,
            empty: false,
            view: "cards",
            config: {},
            configs: [],
            components: [],
            samples: [],
            preview: { sample_id: false, values: {} },
            selectedId: null,
            arrowsOn: true,
            flowOpen: false,
            flowStack: [],
            flowZoom: null,
            aiOpen: false,
            aiMsgs: [],
            aiProposal: null,
            aiLlm: false,
            aiModel: "",
            wizardOpen: false,
            wizardStep: 1,
            wizardForm: { name: "", country_code: "VN", cycle_type: "regular", template: "vn_standard" },
            wizardTemplates: [],
            wizardBusy: false,
            configPickerOpen: false,
        });
        onWillStart(async () => {
            await this.load();
            try {
                const s = await this.orm.call("pb.formula.studio", "ai_status", []);
                this.state.aiLlm = s.llm; this.state.aiModel = s.model;
            } catch (e) { /* non-fatal */ }
        });
        onMounted(() => { this._bindArrowEvents(); this.redrawArrows(); });
        onPatched(() => { this.redrawArrows(); requestAnimationFrame(() => { this.applyZoom(); this.applyInlineFit(); }); });
    }

    async load(configId) {
        const d = await this.orm.call("pb.formula.studio", "get_studio_data", [configId || false]);
        this.state.empty = d.empty;
        this.state.configs = d.configs || [];
        if (d.empty) { this.state.loaded = true; return; }
        this.state.config = d.config;
        this.state.components = d.components;
        this.state.samples = d.samples;
        this.state.preview = d.preview || { sample_id: false, values: {} };
        if (!this.state.selectedId || !d.components.some(c => c.id === this.state.selectedId)) {
            const firstFormula = d.components.find(c => c.type === "formula") || d.components[0];
            this.state.selectedId = firstFormula ? firstFormula.id : null;
        }
        this.state.loaded = true;
    }

    // ---- selectors ----
    get selected() { return this.state.components.find(c => c.id === this.state.selectedId) || null; }
    byCol(col) { return this.state.components.find(c => c.col === col); }
    groupItems(g) { return this.state.components.filter(c => c.group === g); }
    get visibleGroups() { return GROUPS.filter(g => this.groupItems(g).length); }
    get sampleName() {
        const s = this.state.samples.find(s => s.id === this.state.preview.sample_id);
        return s ? s.name : "—";
    }
    selectComponent(id) {
        this.state.selectedId = id;
        // reveal the outcome row in the live preview so the output arrow latches to it
        requestAnimationFrame(() => {
            const comp = this.state.components.find(x => x.id === id);
            if (comp) { const row = document.querySelector(`.pbfs-test .tp-row[data-col="${comp.col}"]`); if (row) row.scrollIntoView({ block: "nearest" }); }
            this.drawArrows();
        });
    }
    setView(v) { this.state.view = v; }

    // ---- formatting ----
    vnd(n) {
        if (n === null || n === undefined || isNaN(n)) return "—";
        const cur = this.state.config.currency || "₫";
        return cur + Math.round(n).toLocaleString("en-US");
    }
    previewVal(col) {
        const v = this.state.preview.values[col];
        return (v === undefined) ? "—" : this.vnd(v);
    }
    stageCls() { return { draft: "draft", testing: "testing", validated: "validated", active: "active", archived: "muted" }[this.state.config.state] || "muted"; }
    stageLabel() { return { draft: "Draft", testing: "Testing", validated: "Validated", active: "Active", archived: "Archived" }[this.state.config.state] || this.state.config.state; }
    nextLabel() { return { draft: "Start testing", testing: "Validate", validated: "Activate", active: "Active" }[this.state.config.state] || "Advance"; }
    isDeduction(c) { return c.group === "Deductions"; }
    ring(score) { const C = 2 * Math.PI * 19; return { dash: C, offset: C * (1 - (score || 0) / 100) }; }
    catKey(group) { return { Inputs: "info", Earnings: "earn", Deductions: "ded", Totals: "total" }[group] || "earn"; }
    colOf(c) { return c ? CAT_COLOR[this.catKey(c.group)] : "#4F46E5"; }

    // ---- dependency highlighting ----
    depColsOf(c) {
        if (!c || c.type !== "formula" || !c.excel_formula) return [];
        const out = [];
        (c.excel_formula.match(/[A-Za-z]+\d+/g) || []).forEach(x => {
            const col = x.replace(/\d+$/, "").toUpperCase();
            if (this.byCol(col) && !out.includes(col)) out.push(col);
        });
        return out;
    }
    isDep(col) { return this.depColsOf(this.selected).includes(col); }
    isOutcome(col) { return this.selected && this.selected.col === col; }
    depStyle(c) { return this.isDep(c.col) ? ("--depc:" + this.colOf(c)) : ""; }

    // ---- formula chips (IF / function aware) ----
    chips(formula) {
        if (!formula) return [{ kind: "src", text: "From contract / import" }];
        const re = /("[^"]*")|([A-Za-z_]+)(?=\()|([A-Za-z]+\d+)|(\d+\.?\d*)|([+\-*/^])|([()])|(,)|(<=|>=|<>|[<>=])/g;
        const out = []; let m; const f = formula.replace(/^=/, "");
        while ((m = re.exec(f))) {
            if (m[1]) out.push({ kind: "num", text: m[1] });
            else if (m[2]) out.push({ kind: "func", text: m[2].toUpperCase() });
            else if (m[3]) { const col = m[3].replace(/\d+$/, "").toUpperCase(); const r = this.byCol(col); out.push({ kind: "ref", col, text: r ? r.name : col }); }
            else if (m[4]) out.push({ kind: "num", text: (+m[4]).toLocaleString("en-US") });
            else if (m[5]) out.push({ kind: "op", text: OPSYM[m[5]] || m[5] });
            else if (m[6]) out.push({ kind: "paren", text: m[6] });
            else if (m[7]) out.push({ kind: "comma", text: "," });
            else if (m[8]) out.push({ kind: "op", text: m[8] });
        }
        return out;
    }

    // ---- tiny Excel-ish parser (client-side; no backend change) ----
    parseFormula(formula) {
        const toks = [];
        const re = /\s*("[^"]*"|[A-Za-z_]+(?=\()|[A-Za-z]+\d+|\d+\.?\d*|<=|>=|<>|[-+*/^&(),<>=])/g;
        let m; const f = (formula || "").replace(/^=/, "");
        while ((m = re.exec(f))) toks.push(m[1]);
        let p = 0;
        const peek = () => toks[p];
        const next = () => toks[p++];
        const parseExpr = () => parseCmp();
        const parseCmp = () => { let l = parseAdd(); while (["<", ">", "<=", ">=", "<>", "="].includes(peek())) { const op = next(); l = { t: "cmp", op, l, r: parseAdd() }; } return l; };
        const parseAdd = () => { let l = parseMul(); while (["+", "-"].includes(peek())) { const op = next(); l = { t: "op", op, l, r: parseMul() }; } return l; };
        const parseMul = () => { let l = parseUnary(); while (["*", "/"].includes(peek())) { const op = next(); l = { t: "op", op, l, r: parseUnary() }; } return l; };
        const parseUnary = () => { if (peek() === "-") { next(); return { t: "op", op: "-", l: { t: "num", v: 0 }, r: parseUnary() }; } return parsePrimary(); };
        const parsePrimary = () => {
            const tk = peek();
            // never consume a delimiter as a value (keeps IF arg lists intact)
            if (tk === undefined || tk === "," || tk === ")") return { t: "num", v: 0 };
            if (tk === "(") { next(); const e = parseExpr(); if (peek() === ")") next(); return e; }
            if (tk[0] === '"') { next(); return { t: "str", v: tk.slice(1, -1) }; }
            if (/^[A-Za-z]+\d+$/.test(tk)) { next(); return { t: "ref", col: tk.replace(/\d+$/, "").toUpperCase() }; }
            if (/^\d/.test(tk)) { next(); return { t: "num", v: parseFloat(tk) }; }
            if (/^[A-Za-z_]+$/.test(tk)) {
                const name = next().toUpperCase(); const args = [];
                if (peek() === "(") { next(); if (peek() !== ")") { args.push(parseExpr()); while (peek() === ",") { next(); args.push(parseExpr()); } } if (peek() === ")") next(); }
                return { t: "fn", name, args };
            }
            next(); return { t: "num", v: 0 };
        };
        try { return parseExpr(); } catch (e) { return null; }
    }
    evalNode(a) {
        try {
            if (!a) return 0;
            if (a.t === "num") return a.v;
            if (a.t === "str") return 0;
            if (a.t === "ref") return this.state.preview.values[a.col] || 0;
            if (a.t === "op") { const l = this.evalNode(a.l), r = this.evalNode(a.r); return a.op === "+" ? l + r : a.op === "-" ? l - r : a.op === "*" ? l * r : a.op === "/" ? (r ? l / r : 0) : a.op === "^" ? Math.pow(l, r) : 0; }
            if (a.t === "cmp") { const l = this.evalNode(a.l), r = this.evalNode(a.r), o = a.op; return (o === ">" ? l > r : o === "<" ? l < r : o === ">=" ? l >= r : o === "<=" ? l <= r : o === "<>" ? l !== r : l === r) ? 1 : 0; }
            if (a.t === "fn") {
                const g = a.args || [], n = a.name;
                if (n === "IF") return this.evalNode(g[0]) ? this.evalNode(g[1]) : this.evalNode(g[2] || { t: "num", v: 0 });
                if (n === "SUM") return g.reduce((s, x) => s + this.evalNode(x), 0);
                if (n === "MAX") return Math.max(...g.map(x => this.evalNode(x)));
                if (n === "MIN") return Math.min(...g.map(x => this.evalNode(x)));
                if (n === "ROUND") { const v = this.evalNode(g[0]), d = g[1] ? this.evalNode(g[1]) : 0, f = Math.pow(10, d); return Math.round(v * f) / f; }
                if (n === "IFERROR") { const v = this.evalNode(g[0]); return isFinite(v) ? v : this.evalNode(g[1] || { t: "num", v: 0 }); }
                return this.evalNode(g[0] || { t: "num", v: 0 });
            }
            return 0;
        } catch (e) { return 0; }
    }
    fmtNum(v) { return (Number.isInteger(v) ? v.toString() : String(v)); }

    // ---- flowchart model (result at bottom, leaves at top) ----
    dnode(a) {
        if (!a) return { kind: "num", label: "?", value: 0, children: [] };
        if (a.t === "num") return { kind: "num", label: this.fmtNum(a.v), value: a.v, children: [] };
        if (a.t === "str") return { kind: "num", label: '"' + a.v + '"', value: 0, children: [] };
        if (a.t === "ref") { const c = this.byCol(a.col) || {}; return { kind: "ref", col: a.col, label: c.name || a.col, sub: "Col " + a.col, value: this.state.preview.values[a.col], formula: c.type === "formula", children: [] }; }
        if (a.t === "op") return { kind: "op", label: OPSYM[a.op] || a.op, value: this.evalNode(a), children: [this.dnode(a.l), this.dnode(a.r)] };
        if (a.t === "cmp") return { kind: "op", label: a.op, value: this.evalNode(a), children: [this.dnode(a.l), this.dnode(a.r)] };
        if (a.t === "fn") {
            if (a.name === "IF") { const g = a.args; return { kind: "if", label: "IF", value: this.evalNode(a), children: [this.dnode(g[0]), this.dnode(g[1] || { t: "num", v: 0 }), this.dnode(g[2] || { t: "num", v: 0 })] }; }
            return { kind: "fn", label: a.name, value: this.evalNode(a), children: (a.args || []).map(x => this.dnode(x)) };
        }
        return { kind: "num", label: "?", value: 0, children: [] };
    }
    nodeColor(n) {
        if (n.kind === "ref") { const c = this.byCol(n.col); return CAT_COLOR[this.catKey(c ? c.group : "Earnings")]; }
        if (n.kind === "num") return "#64748B";
        if (n.kind === "if") return "#B45309";
        if (n.kind === "result") return "#312E81";
        return "#4F46E5";
    }
    fmtNode(n) { return n.kind === "num" ? n.label : this.vnd(n.value); }
    buildFlow(comp) {
        if (!comp || comp.type !== "formula") return null;
        const ast = this.parseFormula(comp.excel_formula);
        const root = { kind: "result", label: comp.name, col: comp.col, value: this.evalNode(ast), children: [this.dnode(ast)] };
        const slotW = 188, boxH = 52, diaH = 92, levelGap = 124, padX = 28, padY = 72;
        let leaf = 0, maxDepth = 0;
        const place = (n, depth) => {
            n.depth = depth; if (depth > maxDepth) maxDepth = depth;
            if (!n.children || !n.children.length) { n.x = leaf * slotW + slotW / 2 + padX; leaf++; }
            else { n.children.forEach(c => place(c, depth + 1)); n.x = n.children.reduce((s, c) => s + c.x, 0) / n.children.length; }
        };
        place(root, 0);
        const width = Math.max(leaf * slotW + padX * 2, 360);
        const height = (maxDepth + 1) * levelGap + padY * 2;
        const yOf = n => (maxDepth - n.depth) * levelGap + padY + (n.kind === "if" ? 20 : 26);
        const nodes = [], edges = [], labels = [];
        let idc = 0;
        const OPCLS = { "+": "op-add", "−": "op-sub", "×": "op-mul", "÷": "op-div", "%": "op-pct", "^": "op-pow",
            "=": "op-cmp", "<": "op-cmp", ">": "op-cmp", "<=": "op-cmp", ">=": "op-cmp", "<>": "op-cmp" };
        const collect = (n) => {
            n.y = yOf(n); n._id = "n" + (idc++);
            nodes.push({ id: n._id, x: n.x, y: n.y, kind: n.kind, label: n.label, value: this.fmtNode(n), sub: n.sub || "", color: this.nodeColor(n), ref: n.col, formula: !!n.formula, opCls: (n.kind === "op" ? (OPCLS[n.label] || "op-mul") : "") });
            (n.children || []).forEach(collect);
        };
        collect(root);
        const eWalk = (n) => {
            const ph = (n.kind === "if" ? diaH : boxH);
            (n.children || []).forEach((c, ci) => {
                const chh = (c.kind === "if" ? diaH : boxH);
                const ay = c.y + chh / 2, by = n.y - ph / 2, ax = c.x, bx = n.x;
                const d = `M ${ax} ${ay} C ${ax} ${(ay + by) / 2} ${bx} ${(ay + by) / 2} ${bx} ${by}`;
                edges.push({ d, color: this.nodeColor(c) });
                if (n.kind === "if") { const lab = ci === 0 ? "if" : (ci === 1 ? "Yes" : "No"); labels.push({ text: lab, cls: ci === 1 ? "yes" : (ci === 2 ? "no" : ""), x: (ax + bx) / 2, y: (ay + by) / 2 }); }
                eWalk(c);
            });
        };
        eWalk(root);
        return { nodes, edges, labels, width, height };
    }
    get inlineFlow() { return this.buildFlow(this.selected); }
    get modalComp() { const col = this.state.flowStack[this.state.flowStack.length - 1]; return this.byCol(col); }
    get modalFlow() { return this.modalComp ? this.buildFlow(this.modalComp) : null; }
    get modalCrumbs() { return this.state.flowStack.map(c => ({ col: c, name: (this.byCol(c) || {}).name || c })); }

    openExpand() { if (this.selected && this.selected.type === "formula") { this.state.flowStack = [this.selected.col]; this.state.flowZoom = null; this.state.flowOpen = true; } }
    flowDrill(col) {
        if (!this.byCol(col)) return;
        this.state.flowZoom = null;
        if (this.state.flowOpen) {
            if (this.state.flowStack[this.state.flowStack.length - 1] !== col) this.state.flowStack = [...this.state.flowStack, col];
        } else { this.state.flowStack = [col]; this.state.flowOpen = true; }
    }
    crumbTo(i) { this.state.flowZoom = null; this.state.flowStack = this.state.flowStack.slice(0, i + 1); }
    closeFlow() { this.state.flowOpen = false; }
    flowNodeClick(ev, n) { if (ev) ev.stopPropagation(); if (n && n.formula) this.flowDrill(n.ref); }

    // ---- expand-modal zoom (fit by default, +/- to blow up/down) ----
    _fitZoom() {
        const canvas = document.querySelector(".fc-modal .fc-canvas");
        const flow = this.modalFlow;
        if (!canvas || !flow) return 1;
        const pad = 28;
        return Math.min((canvas.clientWidth - pad) / flow.width, (canvas.clientHeight - pad) / flow.height, 1.5);
    }
    applyZoom() {
        if (!this.state.flowOpen) return;
        const canvas = document.querySelector(".fc-modal .fc-canvas");
        const wrap = canvas && canvas.querySelector(".fc-zoomwrap");
        const stage = wrap && wrap.querySelector(".fc-stage");
        const flow = this.modalFlow;
        if (!canvas || !wrap || !stage || !flow) return;
        const fit = this._fitZoom();
        const z = (this.state.flowZoom != null ? this.state.flowZoom : fit);
        this._curZoom = z;
        stage.style.transformOrigin = "top left";
        stage.style.transform = "scale(" + z + ")";
        wrap.style.width = (flow.width * z) + "px";
        wrap.style.height = (flow.height * z) + "px";
        wrap.style.margin = "0 auto";        // centre horizontally; scrolls when zoomed in
        const lbl = document.querySelector(".fc-zoom .zlabel");
        if (lbl) lbl.textContent = Math.round(z * 100) + "%";
    }
    zoomIn() { this.state.flowZoom = (this._curZoom || this._fitZoom()) * 1.2; this.applyZoom(); }
    zoomOut() { this.state.flowZoom = Math.max(0.15, (this._curZoom || this._fitZoom()) / 1.2); this.applyZoom(); }
    zoomFit() { this.state.flowZoom = null; this.applyZoom(); }
    // inline flow always fits its window (Expand to see complex ones bigger)
    applyInlineFit() {
        const container = document.querySelector(".pbfs-editor .fc-inline");
        const wrap = container && container.querySelector(".fc-zoomwrap");
        const stage = wrap && wrap.querySelector(".fc-stage");
        const flow = this.inlineFlow;
        if (!container || !wrap || !stage || !flow) return;
        const pad = 18;
        const z = Math.min((container.clientWidth - pad) / flow.width, (container.clientHeight - pad) / flow.height, 1);
        stage.style.transformOrigin = "top left";
        stage.style.transform = "scale(" + z + ")";
        wrap.style.width = (flow.width * z) + "px";
        wrap.style.height = (flow.height * z) + "px";
    }

    // ---- dependency arrows (imperative SVG over the two left panes) ----
    toggleArrows() { this.state.arrowsOn = !this.state.arrowsOn; this.redrawArrows(); }
    redrawArrows() { requestAnimationFrame(() => requestAnimationFrame(() => this.drawArrows())); }
    _bindArrowEvents() {
        const ol = document.querySelector(".pbfs-outline");
        if (ol) ol.addEventListener("scroll", () => this.redrawArrows());
        const ed = document.querySelector(".pbfs-editor");
        if (ed) ed.addEventListener("scroll", () => this.redrawArrows());
        const pv = document.querySelector(".pbfs-test");
        if (pv) pv.addEventListener("scroll", () => this.redrawArrows());
        window.addEventListener("resize", () => this.redrawArrows());
    }
    scrollToCol(col) {
        const row = document.querySelector(`.pbfs-outline .ol-item[data-col="${col}"]`);
        if (!row) return;
        row.scrollIntoView({ behavior: "smooth", block: "center" });
        row.classList.add("pulse"); setTimeout(() => row.classList.remove("pulse"), 950);
    }
    _arrow(layer, sx, sy, tipx, ty, color, onClick, dur, clampPt) {
        const NS = "http://www.w3.org/2000/svg";
        const rtl = tipx < sx;                       // pointing left?
        const basex = tipx + (rtl ? 14 : -14);
        const dx = basex - sx, c1 = sx + dx * 0.45, c2 = sx + dx * 0.55;
        const d = `M ${sx} ${sy} C ${c1} ${sy} ${c2} ${ty} ${basex} ${ty}`;
        const p = document.createElementNS(NS, "path");
        p.setAttribute("d", d); p.setAttribute("fill", "none"); p.setAttribute("stroke", color);
        p.setAttribute("stroke-width", "2.6"); p.setAttribute("stroke-linecap", "round");
        p.style.pointerEvents = "stroke";
        if (onClick) { p.style.cursor = "pointer"; p.addEventListener("click", onClick); }
        layer.appendChild(p);
        const dot = document.createElementNS(NS, "circle");
        dot.setAttribute("r", "3.6"); dot.setAttribute("fill", color); dot.style.pointerEvents = "none";
        const am = document.createElementNS(NS, "animateMotion");
        am.setAttribute("dur", dur + "s"); am.setAttribute("repeatCount", "indefinite"); am.setAttribute("path", d);
        dot.appendChild(am); layer.appendChild(dot);
        const head = document.createElementNS(NS, "polygon");
        head.setAttribute("points", `${tipx},${ty} ${basex},${ty - 7} ${basex},${ty + 7}`);
        head.setAttribute("fill", color);
        if (onClick) { head.style.cursor = "pointer"; head.style.pointerEvents = "auto"; head.addEventListener("click", onClick); }
        layer.appendChild(head);
        if (clampPt) { const t = document.createElementNS(NS, "circle"); t.setAttribute("cx", clampPt[0]); t.setAttribute("cy", clampPt[1]); t.setAttribute("r", "4"); t.setAttribute("fill", color); layer.appendChild(t); }
    }
    drawArrows() {
        const layer = document.getElementById("pbfsArrows");
        const work = document.querySelector(".pbfs-work");
        if (!layer || !work) return;
        const card = document.querySelector(".pbfs-editor .ed-card");
        const outline = document.querySelector(".pbfs-outline");
        const editor = document.querySelector(".pbfs-editor");
        const preview = document.querySelector(".pbfs-test");
        layer.innerHTML = "";
        const wr = work.getBoundingClientRect();
        layer.setAttribute("width", wr.width); layer.setAttribute("height", wr.height);
        layer.style.width = wr.width + "px"; layer.style.height = wr.height + "px";
        const c = this.selected;
        if (!this.state.arrowsOn || !card || !outline || !editor || !c || c.type !== "formula") return;
        const deps = this.depColsOf(c);
        const cardR = card.getBoundingClientRect(), olR = outline.getBoundingClientRect(), edR = editor.getBoundingClientRect();
        // anchor arrowheads near the editor's vertical centre so they stay visible while scrolling
        const centerY = edR.top + edR.height / 2 - wr.top;
        const edTop = edR.top - wr.top + 34, edBot = edR.bottom - wr.top - 34;
        const gap = 34, n = deps.length;
        // ---- input arrows: dependency rows -> left edge of the card ----
        deps.forEach((col, i) => {
            const row = outline.querySelector(`.ol-item[data-col="${col}"]`);
            if (!row) return;
            const rr = row.getBoundingClientRect();
            let sy = rr.top + rr.height / 2 - wr.top;
            const bandTop = olR.top - wr.top + 8, bandBot = olR.bottom - wr.top - 8;
            const clamped = sy < bandTop || sy > bandBot;
            sy = Math.max(bandTop, Math.min(bandBot, sy));
            const sx = olR.right - wr.left - 6;
            const tipx = cardR.left - wr.left + 6;
            let ty = centerY - (n - 1) * gap / 2 + i * gap;
            ty = Math.max(edTop, Math.min(edBot, ty));
            const color = this.colOf(this.byCol(col));
            this._arrow(layer, sx, sy, tipx, ty, color, () => this.scrollToCol(col), (7.5 + i * 0.7), clamped ? [sx, sy] : null);
        });
        // ---- output arrow: right edge of the card -> outcome row in the live preview ----
        if (preview) {
            const outRow = preview.querySelector(`.tp-row[data-col="${c.col}"]`);
            const pvR = preview.getBoundingClientRect();
            const sx = cardR.right - wr.left + 4;
            const sy = Math.max(edTop, Math.min(edBot, centerY));
            const tipx = pvR.left - wr.left + 4;
            let ty = sy, clampedOut = false;
            if (outRow) {
                const orr = outRow.getBoundingClientRect();
                ty = orr.top + orr.height / 2 - wr.top;
                const pT = pvR.top - wr.top + 8, pB = pvR.bottom - wr.top - 8;
                clampedOut = ty < pT || ty > pB;
                ty = Math.max(pT, Math.min(pB, ty));
            }
            this._arrow(layer, sx, sy, tipx, ty, this.colOf(c), () => this.scrollToPreviewCol(c.col), 8.5, clampedOut ? [tipx, ty] : null);
        }
    }
    scrollToPreviewCol(col) {
        const row = document.querySelector(`.pbfs-test .tp-row[data-col="${col}"]`);
        if (!row) return;
        row.scrollIntoView({ behavior: "smooth", block: "center" });
        row.classList.add("pulse"); setTimeout(() => row.classList.remove("pulse"), 950);
    }

    // ---- sample switching ----
    async cycleSample() {
        if (this.state.samples.length < 2) return;
        const idx = this.state.samples.findIndex(s => s.id === this.state.preview.sample_id);
        const next = this.state.samples[(idx + 1) % this.state.samples.length];
        this.state.preview = await this.orm.call("pb.formula.studio", "compute_preview", [this.state.config.id, next.id]);
    }

    // ---- lifecycle ----
    async advance() {
        const r = await this.orm.call("pb.formula.studio", "advance", [this.state.config.id]);
        if (!r.ok) { this.notif.add(r.message || "Action blocked", { type: "warning" }); }
        else { this.notif.add("Now " + (r.state || ""), { type: "success" }); }
        await this.load(this.state.config.id);
    }
    async runValidate() {
        const r = await this.orm.call("pb.formula.studio", "validate", [this.state.config.id]);
        this.notif.add(r.ok ? "Validation complete" : (r.message || "Validation failed"), { type: r.ok ? "success" : "warning" });
        await this.load(this.state.config.id);
    }
    async runTests() {
        const r = await this.orm.call("pb.formula.studio", "run_tests", [this.state.config.id]);
        if (r.ok) this.notif.add(`${r.passed}/${r.total} tests passed`, { type: r.failed ? "warning" : "success" });
        else this.notif.add(r.message || "Test run failed", { type: "danger" });
        await this.load(this.state.config.id);
    }

    // ---- config picker ----
    toggleConfigPicker() { this.state.configPickerOpen = !this.state.configPickerOpen; }
    async pickConfig(id) { this.state.configPickerOpen = false; this.state.selectedId = null; await this.load(id); }

    // ---- PayAI ----
    openAI() { this.state.aiOpen = true; }
    closeAI() { this.state.aiOpen = false; }
    async aiAsk(text) {
        if (!text || !text.trim()) return;
        this.state.aiMsgs.push({ who: "you", text });
        this.state.aiProposal = null;
        const r = await this.orm.call("pb.formula.studio", "ai_propose", [this.state.config.id, text]);
        this.state.aiMsgs.push({ who: "ai", text: r.reply || "" });
        if (r.ok && r.kind === "formula") this.state.aiProposal = r;
        const inp = document.querySelector(".pbfs-ai-input input");
        if (inp) inp.value = "";
    }
    aiAskInput(ev) { if (ev.key === "Enter") this.aiAsk(ev.target.value); }
    aiAskChip(text) { this.aiAsk(text); }
    async applyProposal() {
        const p = this.state.aiProposal;
        if (!p) return;
        if (p.target_id) {
            const r = await this.orm.call("pb.formula.studio", "apply_ai_formula", [p.target_id, p.formula]);
            if (r.ok) { this.notif.add("Formula applied to " + (p.target_name || ""), { type: "success" }); }
            else { this.notif.add(r.msg || "Could not apply", { type: "warning" }); }
        } else {
            this.notif.add("That would create a new component — open the editor to confirm name & code.", { type: "info" });
        }
        this.state.aiProposal = null;
        this.state.aiOpen = false;
        await this.load(this.state.config.id);
    }
    discardProposal() { this.state.aiProposal = null; }

    // ---- guided first-setup wizard ----
    async openWizard() {
        this.state.configPickerOpen = false;
        this.state.wizardStep = 1;
        this.state.wizardForm = { name: "", country_code: "VN", cycle_type: "regular", template: "vn_standard" };
        if (!this.state.wizardTemplates.length) {
            this.state.wizardTemplates = await this.orm.call("pb.formula.studio", "wizard_templates", []);
        }
        this.state.wizardOpen = true;
    }
    closeWizard() { this.state.wizardOpen = false; }
    wizardSet(field, ev) { this.state.wizardForm[field] = ev.target.value; }
    pickTemplate(key) { this.state.wizardForm.template = key; }
    get wizardTpl() { return this.state.wizardTemplates.find(t => t.key === this.state.wizardForm.template) || {}; }
    wizardBack() { if (this.state.wizardStep > 1) this.state.wizardStep--; }
    wizardNext() {
        if (this.state.wizardStep === 1 && !this.state.wizardForm.name.trim()) { this.notif.add("Give the configuration a name first.", { type: "warning" }); return; }
        if (this.state.wizardStep < 5) this.state.wizardStep++;
    }
    async wizardCreate() {
        if (this.state.wizardBusy) return;
        this.state.wizardBusy = true;
        try {
            const r = await this.orm.call("pb.formula.studio", "create_config", [this.state.wizardForm]);
            if (r.ok) {
                this.notif.add(`Created “${this.state.wizardForm.name}” with ${r.rule_count} components`, { type: "success" });
                this.state.wizardOpen = false; this.state.selectedId = null; await this.load(r.config_id);
            } else { this.notif.add("Could not create configuration", { type: "danger" }); }
        } finally { this.state.wizardBusy = false; }
    }
    importExcel() { this.action.doAction("pb_hr_payroll_formula.action_formula_config", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_formula_studio", PbFormulaStudio);
