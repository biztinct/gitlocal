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
    };

    setup() {
        this.ui = useState({
            armedLeft: null,      // a left item id awaiting a right click (draw mode)
            armedRight: null,
            hoverWire: null,
            focusSide: "left",
            focusId: null,
            geom: [],             // [{...wire, path, mx, my}]
        });
        this.rootRef = useRef("root");
        this._raf = null;
        this._recompute = this._recompute.bind(this);
        onMounted(() => {
            this._recompute();
            this._ro = new ResizeObserver(() => this._schedule());
            if (this.rootRef.el) this._ro.observe(this.rootRef.el);
        });
        onWillUnmount(() => { if (this._ro) this._ro.disconnect(); if (this._raf) cancelAnimationFrame(this._raf); });
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
