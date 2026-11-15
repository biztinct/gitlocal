/** @odoo-module **/
/**
 * WDGAP W2-C — "Work back from take-home".
 *
 * One card, two doors:
 *   - Formula Studio's real-pay preview (a person's payslip is on screen);
 *   - the contract drawer, beside the wage ("Use this amount" stages the
 *     figure in the OPEN form — the drawer's own Save bar writes it, with
 *     whatever approval a wage change already needs).
 *
 * The card is opened through the overlay service (`openTakeHome`) so it is
 * mounted at the root: the contract drawer slides with a CSS transform, and a
 * `position: fixed` card inside a transformed ancestor would be placed
 * relative to the drawer, not the screen (the CdPicker trap).
 *
 * pb_contracts does not depend on this module, so the drawer finds the door
 * through the soft registry `pb_take_home` and simply shows no link when this
 * module is absent.
 *
 * RPC: pb.formula.studio — `take_home_open`, `take_home_solve`. Both are pure
 * reads; nothing on this card can change a payslip, a contract or a run.
 *
 * W96: every expression the template evaluates lives in a method here.
 */
import { Component, useState, useRef, onWillStart, onMounted, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.formula.studio";

/** Money the way the server writes it in its sentences (one opinion). */
export function thMoney(value, currency) {
    const cur = currency || {};
    const d = Number.isInteger(cur.decimals) ? cur.decimals : 0;
    const n = Number(value);
    if (!isFinite(n)) { return "—"; }
    const text = Math.abs(n).toLocaleString("en-US", {
        minimumFractionDigits: d, maximumFractionDigits: d,
    });
    const sign = n < 0 ? "-" : "";
    const sym = cur.symbol || "";
    if (!sym) { return sign + text; }
    return cur.position === "before" ? sign + sym + text : sign + text + " " + sym;
}

/** "12,000,000" / "12000000" / "12 000 000" -> 12000000; anything else -> null. */
export function thParse(text) {
    const clean = String(text === undefined || text === null ? "" : text)
        .replace(/[,\s ]/g, "").trim();
    if (!clean) { return null; }
    if (!/^-?\d*\.?\d+$/.test(clean)) { return null; }
    const n = Number(clean);
    return isFinite(n) ? n : null;
}

export class TakeHomeCard extends Component {
    static template = "pb_formula_studio.TakeHomeCard";
    static props = {
        configId: { type: [Number, Boolean], optional: true },
        payslipId: { type: [Number, Boolean], optional: true },
        contractId: { type: [Number, Boolean], optional: true },
        // The contract drawer's door: copies the figure into the open form.
        onUse: { type: Function, optional: true },
        onClose: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.targetRef = useRef("target");
        this.state = useState({
            loading: true, ctx: null, error: "",
            configId: this.props.configId || false,
            target: "", item: "", busy: false, result: null,
            onlyChanged: false, shown: false, runKey: 0,
        });
        // Icons made once: a NEW markup() per render re-inserts the DOM.
        this.icons = {
            calc: ic("calculator", 20), x: ic("x", 18), arrow: ic("arrowRight", 14),
            check: ic("checkCircle", 18), alert: ic("triangleAlert", 18),
            info: ic("info", 15), target: ic("target", 16), sparkles: ic("sparkles", 15),
            down: ic("trendingDown", 15), user: ic("user", 14), layers: ic("layers", 14),
            copy: ic("arrowUpRight", 15), file: ic("fileText", 14),
        };
        onWillStart(() => this.load());
        onMounted(() => {
            this.state.shown = true;
            if (this.targetRef.el) { this.targetRef.el.focus(); }
        });
        // Capture phase: the card owns Escape while it is up, so a host that
        // also listens for it (the contract drawer) never closes underneath.
        useExternalListener(window, "keydown", (ev) => this.onKey(ev), { capture: true });
    }

    // ------------------------------------------------------------- reading
    subjectArgs(extra = {}) {
        return Object.assign({
            config_id: this.state.configId || false,
            payslip_id: this.props.payslipId || false,
            contract_id: this.props.contractId || false,
        }, extra);
    }

    async load() {
        this.state.loading = true;
        this.state.result = null;
        try {
            const ctx = await this.orm.call(MODEL, "take_home_open", [], this.subjectArgs());
            if (!ctx || !ctx.ok) {
                this.state.error = (ctx && ctx.msg) || _t("This cannot be worked out just now.");
                this.state.ctx = null;
            } else {
                this.state.error = "";
                this.state.ctx = ctx;
                this.state.configId = ctx.scheme.id;
                if (!ctx.items.some((i) => i.code === this.state.item)) {
                    this.state.item = ctx.item || "";
                }
            }
        } catch (e) {
            this.state.error = this._err(e);
        } finally {
            this.state.loading = false;
        }
    }
    _err(e) {
        return (e && e.message && e.message.data && e.message.data.message)
            || (e && e.data && e.data.message)
            || _t("This cannot be worked out just now. Try again in a moment.");
    }

    // ------------------------------------------------------------ accessors
    get ctx() { return this.state.ctx || {}; }
    get currency() { return this.ctx.currency || {}; }
    get items() { return this.ctx.items || []; }
    get schemes() { return this.ctx.schemes || []; }
    get hasSchemeChoice() { return this.schemes.length > 1; }
    get who() { return this.ctx.who || ""; }
    get schemeName() { return (this.ctx.scheme && this.ctx.scheme.name) || ""; }
    get sourceLabel() { return this.ctx.source_label || ""; }
    get currentItem() { return this.items.find((i) => i.code === this.state.item) || null; }
    get currentNet() { return this.money((this.ctx.current || {}).net || 0); }
    get currentItemValue() { return this.currentItem ? this.money(this.currentItem.current) : ""; }
    get currencySymbol() { return this.currency.symbol || ""; }
    get symbolBefore() { return this.currency.position === "before"; }
    get canSolve() {
        return Boolean(!this.state.busy && this.state.item && thParse(this.state.target) > 0
            && this.ctx.has_net);
    }
    get noNetLine() {
        return _t("This scheme has no take-home line, so there is nothing to work back from.");
    }
    get pickLine() { return _t("Pick the pay item to change."); }
    money(v) { return thMoney(v, this.currency); }
    itemSelected(item) { return item.code === this.state.item; }
    schemeSelected(s) { return s.id === this.state.configId; }

    // --------------------------------------------------------------- result
    get r() { return this.state.result || {}; }
    get hasResult() { return Boolean(this.state.result); }
    get resultOk() { return this.hasResult && this.r.ok !== false; }
    get resultTone() {
        const o = this.r.outcome;
        if (!this.resultOk) { return "refused"; }
        if (o === "exact") { return "exact"; }
        if (o === "closest" || o === "limit") { return "closest"; }
        return "refused";
    }
    get resultIcon() {
        return this.resultTone === "exact" ? this.icons.check
            : this.resultTone === "closest" ? this.icons.target : this.icons.alert;
    }
    get sentence() { return this.resultOk ? (this.r.sentence || "") : (this.r.msg || ""); }
    get hasFigure() {
        return this.resultOk && this.r.value !== undefined && this.r.value !== null
            && ["exact", "closest", "limit"].includes(this.r.outcome);
    }
    get figure() { return this.money(this.r.value); }
    get figureNet() { return this.money(this.r.net); }
    get itemName() { return (this.r.item && this.r.item.name) || ""; }
    get figureLabel() { return _t("%s must be", this.itemName); }
    get hasBelow() { return this.r.outcome === "closest" && Boolean(this.r.below); }
    get belowValue() { return this.hasBelow ? this.money(this.r.below.value) : ""; }
    get belowNet() { return this.hasBelow ? this.money(this.r.below.net) : ""; }
    get tries() {
        const s = ((this.r.ms || 0) / 1000).toLocaleString("en-US", { maximumFractionDigits: 1 });
        return _t("Worked out in %(n)s tries · %(s)s s", { n: this.r.evals || 0, s });
    }
    get totals() {
        if (!this.hasFigure) { return []; }
        const b = this.r.before || {};
        const a = this.r.after || {};
        const rows = [
            { key: "item", label: this.itemName, before: b.value, after: a.value },
            { key: "gross", label: _t("Gross pay"), before: b.gross, after: a.gross },
            { key: "deductions", label: _t("Deductions"), before: b.deductions, after: a.deductions },
            { key: "net", label: _t("Take-home"), before: b.net, after: a.net },
        ];
        if ((b.employer_cost || 0) || (a.employer_cost || 0)) {
            rows.push({ key: "employer", label: _t("Employer contributions"),
                        before: b.employer_cost, after: a.employer_cost });
        }
        return rows;
    }
    totalClass(t) { return { net: t.key === "net", moved: Math.abs((t.after || 0) - (t.before || 0)) > 1e-9 }; }
    delta(t) {
        const d = (t.after || 0) - (t.before || 0);
        if (Math.abs(d) < 1e-9) { return ""; }
        return (d > 0 ? "+" : "−") + thMoney(Math.abs(d), this.currency);
    }
    get lines() {
        const rows = this.r.lines || [];
        return this.state.onlyChanged ? rows.filter((l) => l.changed) : rows;
    }
    get changedCount() { return this.r.changed || 0; }
    get changedLabel() {
        const n = this.changedCount;
        return n === 1 ? _t("1 line changed") : _t("%s lines changed", n);
    }
    lineClass(line) { return { changed: line.changed, ["k-" + line.kind]: true, muted: !line.counts }; }
    kindLabel(line) {
        return line.kind === "earning" ? _t("Earning")
            : line.kind === "deduction" ? _t("Deduction")
                : line.kind === "net" ? _t("Take-home")
                    : line.kind === "employer" ? _t("Employer")
                        : _t("Information");
    }
    get canUse() { return Boolean(this.props.onUse && this.resultOk && this.r.can_use); }
    get showUseHint() {
        return Boolean(this.props.onUse && this.hasFigure && !this.r.can_use);
    }
    get useHint() {
        return _t("This scheme does not take %s from the contract wage, so the figure cannot be copied into it.", this.itemName);
    }
    get useLabel() { return _t("Use this amount"); }

    // --------------------------------------------------------------- acting
    onTarget(ev) { this.state.target = ev.target.value; }
    onTargetBlur() {
        const n = thParse(this.state.target);
        if (n !== null) {
            const d = Number.isInteger(this.currency.decimals) ? this.currency.decimals : 0;
            this.state.target = n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: d });
        }
    }
    onTargetKey(ev) {
        if (ev.key === "Enter") { ev.preventDefault(); this.solve(); }
    }
    onItem(ev) { this.state.item = ev.target.value; this.state.result = null; }
    async onScheme(ev) {
        this.state.configId = Number(ev.target.value) || false;
        await this.load();
    }
    toggleOnlyChanged() { this.state.onlyChanged = !this.state.onlyChanged; }

    async solve() {
        if (!this.canSolve) { return; }
        this.state.busy = true;
        try {
            const r = await this.orm.call(MODEL, "take_home_solve", [], this.subjectArgs({
                target: thParse(this.state.target), item_code: this.state.item,
            }));
            this.state.result = r || { ok: false, msg: _t("Nothing came back.") };
            this.state.runKey += 1;
        } catch (e) {
            this.state.result = { ok: false, msg: this._err(e) };
            this.state.runKey += 1;
        } finally {
            this.state.busy = false;
        }
    }

    use() {
        if (!this.canUse) { return; }
        this.props.onUse(this.r.value);
        this.close();
    }

    onKey(ev) {
        if (ev.key !== "Escape") { return; }
        ev.preventDefault();
        ev.stopPropagation();
        this.close();
    }
    close() {
        this.state.shown = false;
        setTimeout(() => this.props.onClose(), 160);
    }
}

/**
 * Open the card at the root of the page. `overlay` is the caller's overlay
 * service; `props` are the card's props minus `onClose`; `onClosed` runs once
 * the card has gone. Returns the remove function.
 */
export function openTakeHome(overlay, props, onClosed) {
    let remove = () => {};
    remove = overlay.add(TakeHomeCard, Object.assign({}, props, {
        onClose: () => {
            remove();
            if (onClosed) { onClosed(); }
        },
    }));
    return remove;
}

registry.category("pb_take_home").add("open", openTakeHome);
