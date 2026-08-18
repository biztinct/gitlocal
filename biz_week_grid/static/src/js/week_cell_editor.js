/** @odoo-module **/
/**
 * WeekCellEditor — the one focused editing state of the WeekGrid.
 *
 * A popover that owns the WHOLE of one cell: the primary measure, a stepper per
 * extra measure that applies on that day, the consumer's live budget bar and
 * its advisory warnings. It is the only place besides the legend where a RATE
 * is written down, and the only way to reach an extra measure by keyboard.
 *
 * WHY THE OVERLAY (W43). The grid's body is an `overflow: auto` scroller, and
 * per CSS Overflow such a box clips HORIZONTALLY too (W34) — an absolutely
 * positioned panel would be sliced off at the scroller's edge and read as a
 * rendering bug. The overlay container is a sibling of the whole action host,
 * so this wins by LOCATION and week_grid.scss does not have to enter a z-index
 * argument with a lens modal at 1050 (W37).
 *
 * CONSEQUENCE OF THAT CHOICE (W14/W43.1). Mounted there, the panel is OUTSIDE
 * both the `.pbim` root and the `.bwg` root, so NEITHER `--pbim-*` nor
 * `--bwg-*` resolves: the `var()` FALLBACK is what actually paints. Every
 * fallback in the `.bwgx` block is therefore the real token value, and the
 * block re-declares the `--bwg-*` defaults on itself so a future addition
 * cannot silently render an unstyled panel.
 *
 * IT NEVER WRITES ANYTHING. `onCommit` stages through the grid's existing
 * dirty-cell mechanism and is fired from the Save CLICK — mount hooks read,
 * event handlers write (W21/W21.1). There is no autosave and no RPC in here.
 */
import { Component, useState, useRef, useEffect, onMounted, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class WeekCellEditor extends Component {
    static template = "biz_week_grid.WeekCellEditor";
    static props = {
        rect: Object,                 // anchor geometry, measured by the grid
        title: String,
        subtitle: { type: String, optional: true },
        primary: Object,              // {key,name,value,editable,lockReason,min,max,step}
        chips: Array,                 // applicable extra measures for THIS day
        recompute: { type: Function, optional: true },
        onCommit: Function,
        onClose: Function,
        close: { type: Function, optional: true },   // overlay-supplied
        "*": true,
    };

    setup() {
        this.rootRef = useRef("root");
        this.primaryRef = useRef("primary");
        const values = { [this.props.primary.key]: this.props.primary.value };
        for (const c of this.props.chips) { values[c.key] = c.value; }
        this.state = useState({
            values,
            pos: { top: 0, left: 0 },
            placed: false,
        });
        this._onDocDown = (ev) => {
            if (this.rootRef.el && !this.rootRef.el.contains(ev.target)) {
                this.props.onClose();
            }
        };
        this._onReflow = () => this._place();
        onMounted(() => {
            // measured AFTER mount: the panel's own size decides whether it
            // flips above the cell or to its left, and a fixed panel off a
            // measured origin is the only shape that escapes the scroller.
            this._place();
            document.addEventListener("mousedown", this._onDocDown, true);
            window.addEventListener("resize", this._onReflow);
        });
        onWillUnmount(() => {
            document.removeEventListener("mousedown", this._onDocDown, true);
            window.removeEventListener("resize", this._onReflow);
        });
        useEffect(
            (el) => { if (el) { el.focus(); el.select(); } },
            () => [this.primaryRef.el],
        );
    }

    _place() {
        const el = this.rootRef.el;
        if (!el) { return; }
        const r = this.props.rect;
        const w = el.offsetWidth || 300;
        const h = el.offsetHeight || 260;
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const gap = 6;
        let left = r.left;
        let top = r.bottom + gap;
        if (top + h > vh - 8) {
            const above = r.top - h - gap;
            top = above >= 8 ? above : Math.max(8, vh - h - 8);
        }
        if (left + w > vw - 8) { left = Math.max(8, vw - w - 8); }
        this.state.pos = { top: Math.round(top), left: Math.round(left) };
        this.state.placed = true;
    }

    // ------------------------------------------------------------- values
    get info() {
        if (!this.props.recompute) { return {}; }
        return this.props.recompute({ ...this.state.values }) || {};
    }
    get ceiling() { return this.info.ceiling || null; }
    get warnings() { return this.info.warnings || []; }

    num(v) {
        const n = Number(String(v).replace(",", "."));
        return Number.isNaN(n) ? 0 : n;
    }
    clamp(def, v) {
        let n = this.num(v);
        if (def.min !== undefined && def.min !== null && n < def.min) { n = def.min; }
        if (def.max !== undefined && def.max !== null && n > def.max) { n = def.max; }
        return Math.round(n * 100) / 100;
    }
    setValue(def, raw) {
        this.state.values[def.key] = this.clamp(def, raw);
    }
    onInput(def, ev) {
        // keep the raw string usable while typing ("0.", "1,5"); clamp on blur
        const n = Number(String(ev.target.value).replace(",", "."));
        this.state.values[def.key] = Number.isNaN(n) ? 0 : n;
    }
    onBlur(def, ev) { this.setValue(def, ev.target.value); }
    step(def, dir) {
        const s = def.step || 0.5;
        this.setValue(def, this.num(this.state.values[def.key]) + dir * s);
    }
    barPct(used, cap) {
        if (!cap) { return 0; }
        return Math.min(100, Math.round((used / cap) * 100));
    }
    barTone(used, cap) {
        const p = cap ? used / cap : 0;
        if (p >= 1) { return "danger"; }
        if (p >= 0.9) { return "warn"; }
        return "ok";
    }
    fmt(v) { return String(Math.round(Number(v || 0) * 100) / 100); }

    // ---- the strings the template used to hold inside a t-att expression ----
    // Odoo's extractor reads text nodes and translatable attributes, never a
    // literal inside `t-esc="x or 'Locked'"`. Those read fine in English and
    // never appear in a .po, so they stay English in a translated UI with
    // nothing to report them. Every one now comes through here.
    get closeTitle() { return _t("Close (Esc)"); }
    get lockedLabel() { return _t("Locked"); }
    /** The consumer names its own budget; this is the fallback when it does
     *  not (the panel still has to label the bar). */
    get budgetLabel() { return _t("Budget"); }

    // ------------------------------------------------------------ commands
    commit() {
        const out = {};
        const defs = [this.props.primary, ...this.props.chips];
        for (const d of defs) {
            if (!d.editable) { continue; }
            out[d.key] = this.clamp(d, this.state.values[d.key]);
        }
        this.props.onCommit(out);
    }
    onKeydown(ev) {
        if (ev.key === "Escape") {
            ev.preventDefault(); ev.stopPropagation();
            this.props.onClose();
        } else if (ev.key === "Enter") {
            ev.preventDefault(); ev.stopPropagation();
            this.commit();
        }
    }
    get anyEditable() {
        return this.props.primary.editable
            || this.props.chips.some((c) => c.editable);
    }
}
