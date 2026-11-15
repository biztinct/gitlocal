/** @odoo-module **/
/**
 * WDGAP S8-A — "Build from a total": one card, opened from the contract
 * drawer (the `pb_build_total` soft registry, like W2-C's take-home card).
 *
 * Type the total package (a year or a month), say how much of it is basic
 * pay and which pay item takes the rest; the scheme's own formulas fill
 * everything else. Nothing is saved here: "Use these figures" puts the wage
 * and the pay lines into the open contract form, and the contract's Save
 * sends them through its normal approval.
 */
import { Component, onMounted, onWillStart, useExternalListener, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.pay.package";

function parseAmount(text) {
    const clean = String(text === undefined || text === null ? "" : text)
        .replace(/[\s,]/g, "").replace(/[^0-9.\-]/g, "");
    if (clean === "" || clean === "-" || clean === ".") { return null; }
    const value = Number(clean);
    return Number.isFinite(value) ? value : null;
}

export class BuildTotalCard extends Component {
    static template = "pb_pay_package.BuildTotalCard";
    static props = {
        contractId: { type: Number },
        onUse: { type: Function, optional: true },
        onClose: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.amountRef = useRef("amount");
        this.state = useState({
            shown: false, loading: true, error: "", ctx: null,
            total: "", period: "year", mode: "share", share: "50", basicAmount: "",
            basic: "", balance: "", schemeId: 0,
            busy: false, r: null, onlyChanged: true,
        });
        onWillStart(() => this.open());
        onMounted(() => {
            this.state.shown = true;
            setTimeout(() => { if (this.amountRef.el) { this.amountRef.el.focus(); } }, 60);
        });
        useExternalListener(window, "keydown", (ev) => this.onKey(ev), { capture: true });
    }

    ic(n, s = 16) { return ic(n, s); }

    async open() {
        this.state.loading = true;
        try {
            const ctx = await this.orm.call(MODEL, "package_open", [this.props.contractId, this.state.schemeId || false]);
            if (!ctx.ok) {
                this.state.error = ctx.msg;
            } else {
                this.state.ctx = ctx;
                this.state.error = "";
                this.state.basic = ctx.basic || "";
                this.state.balance = ctx.balance || "";
                this.state.share = String(ctx.basic_share || 50);
                this.state.schemeId = ctx.scheme.id;
            }
        } catch (e) {
            this.state.error = this._err(e);
        }
        this.state.loading = false;
    }
    _err(e) {
        return (e && e.data && e.data.message)
            || (e && e.message && e.message.data && e.message.data.message)
            || _t("This could not be worked out just now. Try again in a moment.");
    }

    get ctx() { return this.state.ctx || {}; }
    get items() { return this.ctx.items || []; }
    get cur() { return this.ctx.currency || {}; }
    money(v) {
        if (v === null || v === undefined) { return ""; }
        const c = this.cur;
        const d = Number.isInteger(c.decimals) ? c.decimals : 0;
        const text = Number(v).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
        if (!c.symbol) { return text; }
        return c.position === "before" ? c.symbol + text : text + " " + c.symbol;
    }
    get schemes() { return this.ctx.schemes || []; }
    get hasSchemeChoice() { return this.schemes.length > 1; }
    get now() { return this.ctx.now || {}; }
    get canSolve() {
        const t = parseAmount(this.state.total);
        return Boolean(t && t > 0 && this.state.basic && this.state.balance
            && this.state.basic !== this.state.balance && !this.state.busy);
    }
    get r() { return this.state.r; }
    get rows() { return (this.r && this.r.rows) || []; }
    get lines() {
        const all = (this.r && this.r.lines) || [];
        return this.state.onlyChanged ? all.filter((l) => l.changed) : all;
    }
    get answerOk() { return Boolean(this.r && (this.r.outcome === "exact" || this.r.outcome === "closest")); }
    get toneClass() { return this.answerOk ? "pbpk-ans is-ok" : "pbpk-ans is-off"; }
    get periodWord() { return this.state.period === "year" ? _t("a year") : _t("a month"); }

    onTotal(ev) { this.state.total = ev.target.value; this.state.r = null; }
    onTotalKey(ev) { if (ev.key === "Enter" && this.canSolve) { ev.preventDefault(); this.solve(); } }
    setPeriod(p) { this.state.period = p; this.state.r = null; }
    setMode(m) { this.state.mode = m; this.state.r = null; }
    onShare(ev) { this.state.share = ev.target.value; this.state.r = null; }
    onBasicAmount(ev) { this.state.basicAmount = ev.target.value; this.state.r = null; }
    onBasic(ev) { this.state.basic = ev.target.value; this.state.r = null; }
    onBalance(ev) { this.state.balance = ev.target.value; this.state.r = null; }
    async onScheme(ev) {
        this.state.schemeId = Number(ev.target.value) || 0;
        this.state.r = null;
        await this.open();
    }
    toggleOnly() { this.state.onlyChanged = !this.state.onlyChanged; }

    async solve() {
        if (!this.canSolve) { return; }
        this.state.busy = true;
        try {
            const basicValue = this.state.mode === "share"
                ? parseAmount(this.state.share) : parseAmount(this.state.basicAmount);
            this.state.r = await this.orm.call(MODEL, "package_solve", [this.props.contractId], {
                total: parseAmount(this.state.total), period: this.state.period,
                basic_mode: this.state.mode, basic_value: basicValue || 0,
                basic_code: this.state.basic, balance_code: this.state.balance,
                config_id: this.state.schemeId || false,
            });
        } catch (e) {
            this.state.r = { ok: false, msg: this._err(e) };
        }
        this.state.busy = false;
    }

    use() {
        if (!this.r || !this.r.can_use || !this.props.onUse) { return; }
        this.props.onUse(this.r.use);
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

export function openBuildTotal(overlay, props, onClosed) {
    let remove = () => {};
    remove = overlay.add(BuildTotalCard, Object.assign({}, props, {
        onClose: () => {
            remove();
            if (onClosed) { onClosed(); }
        },
    }));
    return remove;
}

registry.category("pb_build_total").add("open", openBuildTotal);
