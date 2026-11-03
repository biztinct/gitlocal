/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
import { useFilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

const STATE_CLS = { open: "ok", close: "warn", draft: "info", cancel: "muted" };
// The contract's journey. A contract sits at exactly one step (the server's
// `_step_domains`); cancelled contracts are at no step and "All contracts"
// still lists them.
const STEPS = [
    { key: "draft", title: _t("Draft"), sub: _t("Being prepared") },
    { key: "running", title: _t("Running"), sub: _t("In force") },
    { key: "ending", title: _t("Ending soon"), sub: _t("Ends within 30 days") },
    { key: "ended", title: _t("Ended"), sub: _t("Past its end date") },
];
const PAGE = 60;
// What each figure on the numbers line means as a filter: the same filters as
// the built-in views, so pressing a figure lights the matching tab.
const GLANCE_FILTERS = {
    open: { status: ["open"] },
    expiring: { step: ["ending"] },
    draft: { status: ["draft"] },
    close: { status: ["close"] },
};

export class PbContracts extends Component {
    static template = "pb_contracts.PbContracts";
    static components = { HubBackChip, PbFilterLayout };
    static props = ["*"];

    // A literal inside a template expression is never extracted for
    // translation, so the panel's placeholder comes through _t here.
    get searchLabel() { return _t("Search person, reference, structure, job…"); }

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.dialog = useService("dialog");
        // The return door (hub_nav.js). The People hub no longer mounts this
        // board as a lens — the Employees lens opens it as its own page — so
        // the way back is read ONCE, from props, like every plain cockpit.
        this.back = hubBack(this.props);
        this.state = useState({
            loaded: false, currency: "", kpis: {}, total: 0,
            contracts: [], listTotal: 0, listLoaded: false, listError: false,
            loadingMore: false, stepCounts: {},
            drawerContractId: null, drawerTab: "", canCheck: false,
            checking: 0,
        });
        // FILLIN P2 C1 — the pay run's door ("Open the Contracts list") lands
        // on the To check view: `params.view = "fillin"`.
        const params = (this.props.action && (this.props.action.params || this.props.action.context)) || {};
        // The shared filter panel (pb_filter_kit, FILTER W1): it owns the
        // filters, the counts and the views; this screen loads one page of
        // contracts for kit.query, with the step strip's counts beside it.
        this.kit = useFilterKit({
            model: "pb.contracts",
            noun: _t("contracts"),
            onChange: () => this.loadPage(),
            initial: params.view === "fillin"
                ? { filters: { fillin: ["unchecked"] }, viewKey: "fillin" } : null,
        });
        onWillStart(async () => { await this.load(); });
        // deep link: ?contract=<id>, or an action param, opens the drawer when
        // it is registered — otherwise it is simply ignored and the roster
        // renders as it always did.
        const p = params;
        let cid = p.contract || p.contract_id || p.active_id;
        if (!cid) {
            try { cid = new URLSearchParams(window.location.search).get("contract"); } catch (e) { cid = null; }
        }
        if (cid && this.drawerCmp) { this.state.drawerContractId = Number(cid); }
    }

    // Soft component registry (the People precedent): the drawer registers
    // itself here, so this file carries no hard import of it and the cockpit
    // still works with the full-page contract screen if it is ever absent.
    get drawerCmp() {
        const r = registry.category("pb_contracts_drawer");
        return r.contains("contract_360") ? r.get("contract_360") : null;
    }
    // Props come off stable state and a bound closure, exactly as
    // `people.js:57` builds them; the mount point's `t-key` is the contract id,
    // so switching records remounts and the panel slides in again.
    get drawerProps() {
        const props = {
            contractId: this.state.drawerContractId, onClose: () => this.closeDrawer(),
            // the answers were confirmed inside the panel: the card and the
            // "To check" count follow at once (kit 1.3.0 recounts the tabs)
            onChanged: () => this.kit.refresh(),
        };
        if (this.state.drawerTab) { props.tab = this.state.drawerTab; }
        return props;
    }
    closeDrawer() { this.state.drawerContractId = null; this.state.drawerTab = ""; }

    /** The numbers line, counted over every contract whatever is filtered. */
    async load() {
        const d = await this.orm.call("pb.contracts", "get_board", []);
        Object.assign(this.state, {
            currency: d.currency, kpis: d.kpis, total: d.total, loaded: true,
        });
    }

    /** One page of contracts for the panel's current filters. */
    async loadPage({ more = false } = {}) {
        const q = this.kit.query;
        const offset = more ? this.state.contracts.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call("pb.contracts", "get_contracts_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.contracts = more ? [...this.state.contracts, ...d.rows] : d.rows;
            this.state.listTotal = d.total;
            if (d.steps) { this.state.stepCounts = d.steps; }
            this.state.canCheck = Boolean(d.can_check);
            this.state.listLoaded = true;
            this.state.listError = false;
        } catch (e) {
            if (!this.kit.isCurrent(q.seq)) { return; }
            console.error("pb_contracts: the contract list could not load", e);
            if (!more) {
                this.state.listError = true;
                this.state.listLoaded = true;
            }
            this.notif.add(_t("The contract list could not load. Check your connection, then press Try again."),
                           { type: "warning" });
        } finally {
            this.state.loadingMore = false;
        }
    }
    loadMore() {
        if (!this.state.loadingMore) { this.loadPage({ more: true }); }
    }
    retry() {
        this.state.listError = false;
        this.state.listLoaded = false;
        this.kit.refresh();
    }
    get hasMore() { return this.state.contracts.length < this.state.listTotal; }
    get nextPage() { return Math.min(PAGE, this.state.listTotal - this.state.contracts.length); }
    fmtInt(n) { return Number(n || 0).toLocaleString("en-US"); }

    ic(n, s = 16) { return ic(n, s); }
    stateCls(s) { return STATE_CLS[s] || "muted"; }
    /** One figure per currency ("₫1.2B · Rp612M"), or its average; a single currency reads as before. */
    moneyTotals(totals, fallback, average) {
        if (!totals || !totals.length) return this.money(fallback || 0);
        return totals.map((t) => this.money(average ? (t.count ? t.amount / t.count : 0) : t.amount, t.symbol)).join(" · ");
    }
    money(n, cur) {
        if (n === null || n === undefined) return "—";
        cur = cur || this.state.currency || "₫";
        const a = Math.abs(n);
        if (a >= 1e9) return cur + (n / 1e9).toFixed(1) + "B";
        if (a >= 1e6) return cur + (n / 1e6).toFixed(1) + "M";
        if (a >= 1e3) return cur + (n / 1e3).toFixed(0) + "K";
        return cur + Math.round(n);
    }

    // ---- the numbers (quiet line) ----
    // The figures that filter set the panel: pressing one ticks exactly its
    // filters (and lights the matching view tab); pressing it again shows
    // every contract.
    get glance() {
        const k = this.state.kpis || {};
        const tone = (v, t) => (v ? t : "");
        const pick = (id) => () => this.kit.toggleFilters(GLANCE_FILTERS[id]);
        return [
            { key: "open", n: k.running || 0, label: _t("Running"), tone: "", run: pick("open") },
            { key: "expiring", n: k.expiring || 0, label: _t("Expiring within 30 days"), tone: tone(k.expiring, "amber"), run: pick("expiring") },
            { key: "draft", n: k.draft || 0, label: _t("Draft"), tone: "", run: pick("draft") },
            { key: "close", n: k.expired || 0, label: _t("Expired"), tone: "", run: pick("close") },
            { key: "wage", n: this.moneyTotals(k.wage_totals, k.total_wage, false), label: _t("Monthly wage"), tone: "", run: null },
            { key: "avg", n: this.moneyTotals(k.wage_totals, k.avg_wage, true), label: _t("Average wage"), tone: "", run: null },
        ];
    }
    /** Which figure is lit: the one whose filters are exactly what is on. */
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(GLANCE_FILTERS)) {
            if (this.kit.isExactly(f)) { return key; }
        }
        return "";
    }

    // ---- the steps ----
    // Counted by the server for the panel's state (each step against every
    // OTHER filter, the panel's own rule), so the strip and the panel's
    // "Where it is" section always agree.
    get steps() {
        const counts = this.state.stepCounts || {};
        return STEPS.map((st, i) => {
            const count = counts[st.key] || 0;
            return {
                ...st, n: String(i + 1).padStart(2, "0"), count,
                countLabel: count === 1 ? _t("1 contract") : _t("%s contracts", this.fmtInt(count)),
                flag: "", on: this.kit.loaded && this.kit.isOn("step", st.key),
            };
        });
    }
    /** A step pressed: list that step. Pressed again: back to the start view
     * when it was the only filter, otherwise only that step comes off. */
    pickStep(key) {
        const kit = this.kit;
        if (kit.isOn("step", key) && !kit.isExactly({ step: [key] })) {
            kit.toggle("step", key);
            return;
        }
        kit.toggleFilters({ step: [key] });
    }

    // ============================================ FILLIN P2 — To check
    /** The answers are spelled out on the card only on the review list. */
    get fillinView() { return this.kit.loaded && this.kit.isOn("fillin", "unchecked"); }
    fillinCount(c) { return (c.fillin && c.fillin.n) || 0; }
    fillinChip(c) {
        const n = this.fillinCount(c);
        return n === 1 ? _t("1 answer to check") : _t("%s answers to check", this.fmtInt(n));
    }
    fillinAnswers(c) { return (c.fillin && c.fillin.answers) || []; }
    get fillinTotal() {
        const v = (this.kit.views || []).find((x) => x.key === "fillin");
        return this.state.listTotal || (v && v.n) || 0;
    }
    get allLookRightLabel() {
        const n = this.state.listTotal;
        return n === 1 ? _t("It looks right") : _t("All %s look right", this.fmtInt(n));
    }
    /** "Looks right" on one card. */
    async looksRight(c) {
        if (this.state.checking) { return; }
        this.state.checking = c.id;
        try {
            const r = await this.orm.call("pb.contracts", "fillin_check_contract", [c.id]);
            this.notif.add(r.msg || "", { type: r.ok ? "success" : "warning" });
        } catch (e) {
            this.notif.add(_t("The answers could not be confirmed just now. Try again in a moment."), { type: "danger" });
        } finally {
            this.state.checking = 0;
        }
        await this.kit.refresh();
        this.load();
    }
    /** "Change": the panel opens on its Components tab. */
    changeAnswers(c) { this.openContract(c.id, "components"); }
    /** "All N look right": a confirm that states the count and names people. */
    async allLookRight() {
        const q = this.kit.query;
        let p;
        try {
            p = await this.orm.call("pb.contracts", "fillin_preview_all", [], {
                filters: q.filters, search: q.search,
            });
        } catch (e) {
            this.notif.add(_t("The list of answers could not be read just now. Try again in a moment."), { type: "danger" });
            return;
        }
        if (!p.n) { this.notif.add(_t("Nothing was left to check."), { type: "info" }); return; }
        const names = p.people.join(", ") + (p.more ? " " + _t("…and %s more", this.fmtInt(p.more)) : "");
        const body = p.n === 1
            ? _t("Confirm the answers Payobook filled in on 1 contract (%s)? Nothing is changed; each answer is marked as checked by you.", names)
            : _t("Confirm the answers Payobook filled in on %(n)s contracts (%(names)s)? Nothing is changed; each answer is marked as checked by you.", { n: this.fmtInt(p.n), names });
        this.dialog.add(ConfirmationDialog, {
            title: _t("Confirm the filled-in answers"),
            body,
            confirmLabel: p.n === 1 ? _t("Confirm 1 contract") : _t("Confirm %s contracts", this.fmtInt(p.n)),
            cancelLabel: _t("Cancel"),
            confirm: async () => {
                try {
                    const r = await this.orm.call("pb.contracts", "fillin_check_all", [], {
                        filters: q.filters, search: q.search,
                    });
                    this.notif.add(r.msg || "", { type: r.ok ? "success" : "warning" });
                } catch (e) {
                    this.notif.add(_t("The answers could not be confirmed just now. Try again in a moment."), { type: "danger" });
                }
                await this.kit.refresh();
                this.load();
            },
            cancel: () => {},
        });
    }

    openContract(id, tab = "") {
        if (!id) return;
        this.state.drawerTab = tab || "";
        if (this.drawerCmp) { this.state.drawerContractId = Number(id); return; }
        this.action.doAction({ type: "ir.actions.client", tag: "pb_contract_detail", name: _t("Contract"), params: { contract_id: id } });
    }
    newContract() {
        this.action.doAction({ type: "ir.actions.client", tag: "pb_contract_wizard", name: _t("New contract") });
    }
    openAll() { this.action.doAction("pb_hr_payroll_base.action_hr_contract_payroll", { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_contracts", PbContracts);
