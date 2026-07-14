/** @odoo-module **/
// F10 — Unified Mapping Canvas.
// A payroll-AGNOSTIC two-column wiring board. It knows nothing about payroll:
// it renders `leftItems`/`rightItems`, draws `wires` between them as SVG
// bezier paths, and calls back on user intent. Every mapping surface (cycle,
// API field, import column, employee→scheme) is just a different adapter that
// supplies these props and implements the callbacks against its own model.
import { Component, useState, useRef, onMounted, onWillUnmount, onPatched, useExternalListener } from "@odoo/owl";

export class MappingCanvas extends Component {
    static template = "pb_formula_studio.MappingCanvas";
    static props = {
        leftItems: Array,          // [{id, label, sublabel, meta}]
        rightItems: Array,
        wires: Array,              // [{id, leftId, rightId, state, confidence, reason, kind, ref}]
        leftTitle: { type: String, optional: true },
        rightTitle: { type: String, optional: true },
        canEdit: { type: Boolean, optional: true },
        busy: { type: Boolean, optional: true },
        onAccept: { type: Function, optional: true },   // (wire)
        onReject: { type: Function, optional: true },   // (wire)
        onDelete: { type: Function, optional: true },   // (wire)
        onDraw: { type: Function, optional: true },     // (leftId, rightId)
        onSuggest: { type: Function, optional: true },  // ()
        onTransformPreview: { type: Function, optional: true },  // (ref, draft) → Promise
        onTransformSave: { type: Function, optional: true },     // (ref, vals) → Promise
    };

    setup() {
        this.ui = useState({
            armedLeft: null,      // a left item id awaiting a right click (draw mode)
            armedRight: null,
            hoverWire: null,
            focusSide: "left",
            focusId: null,
            geom: [],             // [{...wire, path, mx, my}]
            // W62 — transform popover (API wires only)
            tfOpen: null,         // open wire id, or null
            tfPy: false,          // the open wire is a read-only python transform
            tfDraft: {},          // {transformation_type, transformation_value, transformation_decimals}
            tfPreview: {},        // {sample, result, error, loading}
            tfSaving: false,
        });
        this.rootRef = useRef("root");
        this._raf = null;
        this._tfRef = null;       // mapping ref of the open transform popover
        this._tfToken = 0;        // C8 supersede token for the debounced preview
        this._tfTimer = null;
        this._recompute = this._recompute.bind(this);
        onMounted(() => {
            this._recompute();
            this._ro = new ResizeObserver(() => this._schedule());
            if (this.rootRef.el) this._ro.observe(this.rootRef.el);
        });
        onWillUnmount(() => { if (this._ro) this._ro.disconnect(); if (this._raf) cancelAnimationFrame(this._raf); if (this._tfTimer) clearTimeout(this._tfTimer); });
        onPatched(() => this._schedule());
        // recompute wire geometry when either column scrolls
        useExternalListener(window, "resize", () => this._schedule());
    }

    // ---- geometry -----------------------------------------------------
    _schedule() {
        if (this._raf) return;
        this._raf = requestAnimationFrame(() => { this._raf = null; this._recompute(); });
    }
    onColScroll() { this._schedule(); }
    _recompute() {
        const root = this.rootRef.el;
        if (!root) return;
        const rb = root.getBoundingClientRect();
        const geom = [];
        for (const w of this.props.wires) {
            const le = root.querySelector(`.mc-item[data-side="left"][data-id="${w.leftId}"]`);
            const re = root.querySelector(`.mc-item[data-side="right"][data-id="${w.rightId}"]`);
            if (!le || !re) continue;
            const lr = le.getBoundingClientRect(), rr = re.getBoundingClientRect();
            const x1 = lr.right - rb.left, y1 = lr.top + lr.height / 2 - rb.top;
            const x2 = rr.left - rb.left, y2 = rr.top + rr.height / 2 - rb.top;
            const dx = Math.max(48, Math.abs(x2 - x1) * 0.42);
            geom.push({
                ...w,
                path: `M ${x1},${y1} C ${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`,
                mx: (x1 + x2) / 2, my: (y1 + y2) / 2,
            });
        }
        // clip badges/paths that fall outside the visible scroll band would need
        // per-column clipping; columns are short here so full-board paint is fine.
        this.ui.geom = geom;
    }
    get svgSize() {
        const el = this.rootRef.el;
        return el ? { w: el.clientWidth, h: el.clientHeight } : { w: 0, h: 0 };
    }

    // ---- wire lookups -------------------------------------------------
    wiresForLeft(id) { return this.props.wires.filter(w => w.leftId === id); }
    wiresForRight(id) { return this.props.wires.filter(w => w.rightId === id); }
    isLeftWired(id) { return this.props.wires.some(w => w.leftId === id); }
    isRightWired(id) { return this.props.wires.some(w => w.rightId === id); }
    leftHasAccepted(id) { return this.props.wires.some(w => w.leftId === id && w.state === "accepted"); }
    rightHasAccepted(id) { return this.props.wires.some(w => w.rightId === id && w.state === "accepted"); }

    // ---- draw interaction (click-arm-left → click-right) --------------
    clickLeft(id) {
        if (!this.props.canEdit) { this.ui.focusSide = "left"; this.ui.focusId = id; return; }
        this.ui.focusSide = "left"; this.ui.focusId = id;
        this.ui.armedLeft = (this.ui.armedLeft === id) ? null : id;
        this.ui.armedRight = null;
    }
    clickRight(id) {
        this.ui.focusSide = "right"; this.ui.focusId = id;
        if (this.ui.armedLeft != null && this.props.canEdit && this.props.onDraw) {
            this.props.onDraw(this.ui.armedLeft, id);
            this.ui.armedLeft = null;
        }
    }
    isArmed(side, id) { return side === "left" ? this.ui.armedLeft === id : this.ui.armedRight === id; }

    // ---- wire badge actions -------------------------------------------
    accept(w) { if (this.props.onAccept) this.props.onAccept(w); }
    reject(w) { if (this.props.onReject) this.props.onReject(w); }
    del(w) { if (this.props.onDelete) this.props.onDelete(w); }
    confidencePct(w) { return Math.round((w.confidence || 0) * 100); }

    // ---- W62 transforms on the wire (API adapter only) ----------------
    // Cycle wires never carry `.transform`, so none of this ever renders for
    // them (D-I1: cycle canvas is byte-identical — no transform affordances).
    _num(x) { const s = String(x ?? ""); return s.indexOf(".") >= 0 ? s.replace(/\.?0+$/, "") : s; }
    // D-I2 badge vocabulary
    transformGlyph(tf) {
        if (!tf) return "=";
        switch (tf.type) {
            case "multiply": return "×" + this._num(tf.value);
            case "divide": return "÷" + this._num(tf.value);
            case "add": return "+" + this._num(tf.value);
            case "subtract": return "−" + this._num(tf.value);   // U+2212 minus
            case "round": return "≈" + this._num(tf.decimals);   // ≈
            case "abs": return "|x|";
            case "default_if_empty": return "?" + this._num(tf.value);
            case "python": return "ƒ";                            // ƒ
            default: return "=";
        }
    }
    // tfDraft uses the record field names; transformGlyph wants {type,value,decimals}
    get tfDraftGlyph() {
        const d = this.ui.tfDraft;
        return this.transformGlyph({ type: d.transformation_type,
                                     value: d.transformation_value,
                                     decimals: d.transformation_decimals });
    }
    get tfNeedsValue() {
        return ["multiply", "divide", "add", "subtract", "default_if_empty"]
            .includes(this.ui.tfDraft.transformation_type);
    }
    get tfNeedsDecimals() { return this.ui.tfDraft.transformation_type === "round"; }
    get tfAnchor() {
        const g = this.ui.geom.find(x => x.id === this.ui.tfOpen);
        return g ? { x: g.mx, y: g.my } : { x: 0, y: 0 };
    }
    get tfTypeOptions() {
        return [
            { v: "direct", l: "Direct copy" },
            { v: "multiply", l: "Multiply by" },
            { v: "divide", l: "Divide by" },
            { v: "add", l: "Add" },
            { v: "subtract", l: "Subtract" },
            { v: "round", l: "Round to decimals" },
            { v: "abs", l: "Absolute value" },
            { v: "default_if_empty", l: "Default if empty" },
        ];
    }
    openTransform(g) {
        if (!g || !g.transform) return;
        this.ui.tfOpen = g.id;
        this._tfRef = g.ref;
        this.ui.tfPy = !!g.transform.python;
        this.ui.tfDraft = {
            transformation_type: g.transform.type || "direct",
            transformation_value: g.transform.value ?? 0,
            transformation_decimals: g.transform.decimals ?? 2,
        };
        this.ui.tfPreview = {
            sample: g.transform.sample, result: null,
            error: g.transform.error ? (g.transform.error_msg || "This Python transform last failed — it fell back to the default value.") : null,
            loading: false,
        };
        this.ui.tfSaving = false;
        if (this.props.canEdit && !this.ui.tfPy) this._tfPreview();
    }
    closeTransform() {
        this.ui.tfOpen = null;
        this._tfToken++;                       // supersede any in-flight preview
        if (this._tfTimer) { clearTimeout(this._tfTimer); this._tfTimer = null; }
    }
    // C8 — 260 ms debounce + monotonic supersede token (never stack previews)
    _tfPreview() {
        if (!this.props.onTransformPreview) return;
        if (this._tfTimer) clearTimeout(this._tfTimer);
        const token = ++this._tfToken;
        this.ui.tfPreview = { ...this.ui.tfPreview, loading: true };
        this._tfTimer = setTimeout(async () => {
            const draft = {
                transformation_type: this.ui.tfDraft.transformation_type,
                transformation_value: parseFloat(this.ui.tfDraft.transformation_value) || 0,
                transformation_decimals: parseInt(this.ui.tfDraft.transformation_decimals, 10) || 0,
            };
            let res;
            try { res = await this.props.onTransformPreview(this._tfRef, draft); }
            catch (e) { res = { ok: false, error: "Preview failed" }; }
            if (token !== this._tfToken) return;      // superseded — drop
            this.ui.tfPreview = (res && res.ok)
                ? { sample: res.sample, result: res.result, error: null, loading: false }
                : { sample: this.ui.tfPreview.sample, result: null,
                    error: (res && (res.error || res.msg)) || "Preview failed", loading: false };
        }, 260);
    }
    onDraftType(ev) { this.ui.tfDraft.transformation_type = ev.target.value; this._tfPreview(); }
    onDraftValue(ev) { this.ui.tfDraft.transformation_value = ev.target.value; this._tfPreview(); }
    onDraftDecimals(ev) { this.ui.tfDraft.transformation_decimals = ev.target.value; this._tfPreview(); }
    async saveTransform() {
        if (!this.props.canEdit || this.ui.tfPy || !this.props.onTransformSave) return;
        this.ui.tfSaving = true;
        const vals = {
            transformation_type: this.ui.tfDraft.transformation_type,
            transformation_value: parseFloat(this.ui.tfDraft.transformation_value) || 0,
            transformation_decimals: parseInt(this.ui.tfDraft.transformation_decimals, 10) || 0,
        };
        let res;
        try { res = await this.props.onTransformSave(this._tfRef, vals); }
        catch (e) { res = { ok: false, msg: "Save failed" }; }
        this.ui.tfSaving = false;
        if (res && res.ok === false) {
            this.ui.tfPreview = { ...this.ui.tfPreview, error: res.msg || "Save failed" };
            return;
        }
        this.closeTransform();     // parent reloads the board → badge re-renders
    }

    // ---- keyboard path (focus item → Enter arms → Enter on other side draws)
    onKeydown(ev) {
        const list = this.ui.focusSide === "left" ? this.props.leftItems : this.props.rightItems;
        if (!list.length) return;
        let idx = list.findIndex(i => i.id === this.ui.focusId);
        if (idx === -1) idx = 0;
        const set = (i) => { this.ui.focusId = list[Math.max(0, Math.min(list.length - 1, i))].id; };
        switch (ev.key) {
            case "ArrowDown": ev.preventDefault(); set(idx + 1); break;
            case "ArrowUp": ev.preventDefault(); set(idx - 1); break;
            case "ArrowRight": case "ArrowLeft":
                ev.preventDefault();
                this.ui.focusSide = this.ui.focusSide === "left" ? "right" : "left";
                { const l2 = this.ui.focusSide === "left" ? this.props.leftItems : this.props.rightItems;
                  this.ui.focusId = (l2[0] || {}).id ?? null; }
                break;
            case "Enter":
                ev.preventDefault();
                if (this.ui.focusSide === "left") this.clickLeft(this.ui.focusId);
                else this.clickRight(this.ui.focusId);
                break;
            case "Escape": this.ui.armedLeft = null; this.ui.armedRight = null; break;
            default: return;
        }
        ev.stopPropagation();
    }
}
