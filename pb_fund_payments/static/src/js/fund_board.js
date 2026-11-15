/** @odoo-module **/
/**
 * `pb_fund_payments_board` — the "Fund & tax payments" lens of the Payroll hub
 * (and its own page from the palette).
 *
 * THE HERO IS ONE PRESS: "Work out what we owe for October 2026" fills the
 * month from the finished payslips — one row per fund, owed, split employee /
 * employer, due date — and every later press says exactly what moved.
 *
 * FOUR PLACES A PAYMENT CAN BE: to pay, waiting for approval, approved (not
 * paid), paid. A payment is at exactly one, so the steps add up.
 *
 * R1 — no `t-as` variable is named lt/gt/lte/gte/and/or/not/in (UPDATES G60).
 * R2 — icons are the filter kit's CACHED markup (`pbfIcon`): a NEW markup()
 *      per render re-inserts the SVG on every patch (OWL markup flicker).
 * R3 — every sentence a person reads is a `_t()` literal, a template text, or
 *      comes from the server already translated.
 * R4 — the screen's own calls carry the kit's ctx (`kit.kw`), or the month
 *      drops out of the domain (filter-kit F31).
 */
import { Component, useState, onWillStart, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { useFilterKit, pbfIcon } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

const PAGE = 60;
const GLANCE_FILTERS = {
    to_pay: { where: ["to_pay"] },
    waiting: { where: ["waiting"] },
    approved: { where: ["approved"] },
    paid: { where: ["paid"] },
    changed: { changed: ["changed"] },
};

function blankPayee(currencyId) {
    return {
        id: 0, name: "", currency_id: currencyId || 0, due_day: 15,
        bank_details: "", reference_text: "", items: [],
    };
}

export class PbFundPaymentsBoard extends Component {
    static template = "pb_fund_payments.PbFundPaymentsBoard";
    static components = { PbFilterLayout };
    static props = ["*"];

    get stepsLabel() { return _t("Where every payment is"); }
    get searchLabel() { return _t("Find a fund, an office or a payment reference…"); }

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.state = useState({
            loaded: false, allowed: true, why: "", canWrite: false,
            month: "", monthLabel: "", prev: "", next: "", isFuture: false,
            payees: 0, slips: 0, kpis: {}, totals: [], total: 0,
            rows: [], listTotal: 0, listLoaded: false, listError: false,
            loadingMore: false, stepCounts: {},
            working: false, lastResult: "",
            // the drawer
            pay: null, payBusy: false, act: null,
            // who we pay
            setupOpen: false, setup: null, editing: null, options: [], optionTerm: "",
            saving: false,
            // suggest
            suggestOpen: false, proposals: [], suggestBusy: false,
        });
        this.kit = useFilterKit({
            model: "pb.fund.payments",
            noun: _t("payments"),
            defer: true,
            onChange: () => this.loadPage(),
        });
        this._optSeq = 0;
        useExternalListener(window, "keydown", (ev) => this.onKey(ev));
        onWillStart(async () => {
            await this.load();
            if (this.state.allowed) {
                this.kit.ctx = { month: this.state.month };
                await this.kit.load();
            } else {
                this.state.listLoaded = true;
            }
        });
    }

    icon(name, size = 16) { return pbfIcon(name, size); }

    // ------------------------------------------------------------ loading
    async load(month = null) {
        try {
            const d = await this.orm.call("pb.fund.payments", "get_board", [month || this.state.month || false]);
            Object.assign(this.state, {
                allowed: d.allowed !== false,
                why: d.why || "",
                canWrite: !!d.can_write,
                month: d.month || "",
                monthLabel: d.month_label || "",
                prev: d.prev || "", next: d.next || "",
                isFuture: !!d.is_future,
                payees: d.payees || 0,
                slips: d.slips || 0,
                kpis: d.kpis || {},
                totals: d.totals || [],
                total: d.total || 0,
            });
        } catch (e) {
            console.warn("pb_fund_payments: the board could not be read", e);
            this.state.allowed = false;
            this.state.why = _t("The payments could not be read just now.");
        } finally {
            this.state.loaded = true;
        }
    }

    async loadPage({ more = false } = {}) {
        if (this.kit.refusal) {
            this.state.listLoaded = true;
            return;
        }
        const q = this.kit.query;
        const offset = more ? this.state.rows.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call("pb.fund.payments", "get_page", [], this.kit.kw({
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
            }));
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.rows = more ? [...this.state.rows, ...d.rows] : d.rows;
            this.state.listTotal = d.total;
            if (d.steps) { this.state.stepCounts = d.steps; }
            this.state.listLoaded = true;
            this.state.listError = false;
        } catch (e) {
            if (!this.kit.isCurrent(q.seq)) { return; }
            console.error("pb_fund_payments: the payments could not load", e);
            if (!more) {
                this.state.listError = true;
                this.state.listLoaded = true;
            }
            this.notif.add(_t("The payments could not load. Check your connection, then press Try again."),
                           { type: "warning" });
        } finally {
            this.state.loadingMore = false;
        }
    }
    loadMore() { if (!this.state.loadingMore) { this.loadPage({ more: true }); } }
    retry() {
        this.state.listError = false;
        this.state.listLoaded = false;
        this.kit.refresh();
    }
    get hasMore() { return this.state.rows.length < this.state.listTotal; }
    get nextPage() { return Math.min(PAGE, this.state.listTotal - this.state.rows.length); }
    fmtInt(n) { return Number(n || 0).toLocaleString(); }
    async refresh() { await Promise.all([this.load(), this.kit.refresh()]); }

    // ---------------------------------------------------------- the month
    async goMonth(month, filters = null) {
        if (!month || month === this.state.month) {
            if (filters) { this.kit.setFilters(filters); }
            return;
        }
        this.state.listLoaded = false;
        this.state.pay = null;
        await this.load(month);
        await this.kit.reconfigure({ ctx: { month: this.state.month },
                                     initial: filters ? { filters } : null });
    }
    onMonthInput(ev) {
        const v = ev.target.value;
        if (v && v.length === 7) { this.goMonth(v + "-01"); }
    }
    get monthValue() { return (this.state.month || "").slice(0, 7); }

    // --------------------------------------------------------- the hero press
    async workOut() {
        if (this.state.working) { return; }
        if (!this.state.payees) { this.openSetup(); return; }
        this.state.working = true;
        try {
            const res = await this.orm.call("pb.fund.payments", "work_out", [this.state.month]);
            this.state.lastResult = res.msg || "";
            this.notif.add(res.msg || _t("Worked out."), {
                type: (res.created || res.updated || res.unchanged || res.changed) ? "success" : "info",
            });
            // New rows can make new filter sections worth showing (a panel
            // laid out over an empty month has none): lay it out again.
            await this.load();
            await this.kit.reconfigure({ ctx: { month: this.state.month } });
        } catch (e) {
            this.notif.add(this._msg(e, _t("The month could not be worked out.")), { type: "danger" });
        } finally {
            this.state.working = false;
        }
    }

    async exportXlsx() {
        try {
            const res = await this.orm.call("pb.fund.payments", "export_xlsx", [this.state.month]);
            if (!res || !res.ok) {
                this.notif.add((res && res.msg) || _t("The Excel file could not be made."), { type: "warning" });
                return;
            }
            const bin = atob(res.file_b64);
            const bytes = new Uint8Array(bin.length);
            for (let i = 0; i < bin.length; i++) { bytes[i] = bin.charCodeAt(i); }
            const url = URL.createObjectURL(new Blob([bytes], { type: res.mimetype }));
            const a = document.createElement("a");
            a.href = url;
            a.download = res.filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
        } catch (e) {
            this.notif.add(this._msg(e, _t("The Excel file could not be made.")), { type: "danger" });
        }
    }

    // --------------------------------------------------------- the quiet board
    get stepDefs() {
        return [
            { key: "to_pay", title: _t("To pay") },
            { key: "waiting", title: _t("Waiting for approval") },
            { key: "approved", title: _t("Approved, not paid") },
            { key: "paid", title: _t("Paid") },
        ];
    }
    _paymentsLabel(n) { return n === 1 ? _t("1 payment") : _t("%s payments", this.fmtInt(n)); }
    get steps() {
        const counts = this.state.stepCounts || {};
        return this.stepDefs.map((st, i) => {
            const count = counts[st.key] || 0;
            let flag = "";
            if (st.key === "waiting" && count) {
                flag = count === 1 ? _t("1 waiting for a sign-off") : _t("%s waiting for a sign-off", count);
            }
            return {
                ...st, n: String(i + 1).padStart(2, "0"), count,
                countLabel: this._paymentsLabel(count), sub: "", flag, flagTone: "",
                on: this.kit.loaded && this.kit.isOn("where", st.key),
            };
        });
    }
    pickStep(key) {
        const kit = this.kit;
        if (kit.isOn("where", key) && !kit.isExactly({ where: [key] })) {
            kit.toggle("where", key);
            return;
        }
        kit.toggleFilters({ where: [key] });
    }
    get glance() {
        const k = this.state.kpis || {};
        const tone = (v, t) => (v ? t : "");
        const pick = (id) => () => this.kit.toggleFilters(GLANCE_FILTERS[id]);
        const out = [
            { key: "to_pay", n: k.to_pay || 0, label: _t("to pay"), tone: tone(k.to_pay, "blue"), run: pick("to_pay") },
            { key: "waiting", n: k.waiting || 0, label: _t("waiting for approval"), tone: tone(k.waiting, "amber"), run: pick("waiting") },
            { key: "approved", n: k.approved || 0, label: _t("approved, not paid"), tone: tone(k.approved, "amber"), run: pick("approved") },
            { key: "paid", n: k.paid || 0, label: _t("paid"), tone: tone(k.paid, "green"), run: pick("paid") },
        ];
        if (k.changed) {
            out.push({ key: "changed", n: k.changed, label: _t("changed since approval"), tone: "amber", run: pick("changed") });
        }
        return out;
    }
    get glanceOn() {
        if (!this.kit.loaded) { return ""; }
        for (const [key, f] of Object.entries(GLANCE_FILTERS)) {
            if (this.kit.isExactly(f)) { return key; }
        }
        return "";
    }
    get lateSentence() {
        const n = (this.state.kpis || {}).late || 0;
        if (!n) { return ""; }
        return n === 1 ? _t("1 payment is past its due date")
                       : _t("%s payments are past their due date", n);
    }
    showLate() {
        const k = this.state.kpis || {};
        this.goMonth(k.late_month || this.state.month, { late: ["late"] });
    }

    // ------------------------------------------------------------ the drawer
    async openPay(row) {
        this.state.act = null;
        this.state.payBusy = true;
        if (!this.state.pay || this.state.pay.id !== row.id) {
            this.state.pay = { ...row, loading: true };
        }
        try {
            this.state.pay = await this.orm.call("pb.fund.payments", "get_payment", [row.id]);
        } catch (e) {
            this.notif.add(this._msg(e, _t("This payment could not be opened.")), { type: "danger" });
            this.state.pay = null;
        } finally {
            this.state.payBusy = false;
        }
    }
    closePay() { this.state.pay = null; this.state.act = null; }

    startAct(verb) {
        const p = this.state.pay;
        const today = new Date();
        const iso = new Date(today.getTime() - today.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
        this.state.act = {
            verb, reason: "", paid_on: iso,
            paid_amount: p ? String(p.owed_raw || "") : "",
            reference: "", note: "", attachment: null, uploading: false,
        };
    }
    cancelAct() { this.state.act = null; }
    onAct(field, ev) { this.state.act[field] = ev.target.value; }

    get actDiffers() {
        const act = this.state.act;
        const p = this.state.pay;
        if (!act || !p || act.verb !== "pay") { return false; }
        const amount = parseFloat(String(act.paid_amount).replace(/[^0-9.\-]/g, ""));
        if (isNaN(amount)) { return false; }
        const step = Math.pow(10, -(p.decimals || 0)) / 2;
        return Math.abs(amount - (p.owed_raw || 0)) >= step;
    }

    async onReceipt(ev) {
        const file = ev.target.files && ev.target.files[0];
        const act = this.state.act;
        const p = this.state.pay;
        if (!file || !act || !p) { return; }
        if (file.size > 15 * 1024 * 1024) {
            this.notif.add(_t("That file is larger than 15 MB."), { type: "warning" });
            return;
        }
        act.uploading = true;
        try {
            const b64 = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(String(reader.result).split(",").pop());
                reader.onerror = () => reject(reader.error);
                reader.readAsDataURL(file);
            });
            const res = await this.orm.call("pb.fund.payments", "attach_receipt",
                                            [p.id, file.name, b64, file.type || false]);
            act.attachment = res;
        } catch (e) {
            this.notif.add(this._msg(e, _t("The receipt could not be attached.")), { type: "danger" });
        } finally {
            act.uploading = false;
        }
    }

    async doAct() {
        const act = this.state.act;
        if (!act) { return; }
        if (act.verb === "reopen" && !act.reason.trim()) {
            this.notif.add(_t("Say why, in a few words."), { type: "warning" });
            return;
        }
        if (act.verb === "pay") {
            if (!act.attachment) {
                this.notif.add(_t("Attach the receipt or the bank confirmation first."), { type: "warning" });
                return;
            }
            if (this.actDiffers && !act.note.trim()) {
                this.notif.add(_t("The amount paid is not what is owed. Say why, in a few words."), { type: "warning" });
                return;
            }
        }
        await this.move(act.verb, {
            reason: act.reason, paid_on: act.paid_on,
            paid_amount: act.verb === "pay" ? parseFloat(String(act.paid_amount).replace(/[^0-9.\-]/g, "")) : null,
            reference: act.reference, note: act.note,
            attachment_id: act.attachment ? act.attachment.id : false,
        });
    }

    async move(verb, vals = {}) {
        const p = this.state.pay;
        if (!p) { return; }
        this.state.payBusy = true;
        try {
            const res = await this.orm.call("pb.fund.payments", "move", [p.id, verb, vals]);
            this.state.act = null;
            this.notif.add(res.msg || _t("Done."), { type: "success" });
            await this.openPay({ id: p.id });
            await this.refresh();
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be done.")), { type: "danger" });
        } finally {
            this.state.payBusy = false;
        }
    }

    async openLines() {
        const p = this.state.pay;
        if (!p) { return; }
        try {
            const action = await this.orm.call("pb.fund.payments", "open_lines", [p.id]);
            await this.action.doAction(action);
        } catch (e) {
            this.notif.add(this._msg(e, _t("The payslip lines could not be opened.")), { type: "danger" });
        }
    }
    async openRequest() {
        const p = this.state.pay;
        if (!p) { return; }
        try {
            const action = await this.orm.call("pb.fund.payments", "open_request", [p.id]);
            await this.action.doAction(action);
        } catch (e) {
            this.notif.add(this._msg(e, _t("Approvals could not be opened.")), { type: "danger" });
        }
    }

    // ------------------------------------------------------------ who we pay
    async openSetup() {
        this.state.setupOpen = true;
        this.state.editing = null;
        await this.loadSetup();
    }
    closeSetup() {
        this.state.setupOpen = false;
        this.state.editing = null;
        this.load();
    }
    async loadSetup() {
        try {
            this.state.setup = await this.orm.call("pb.fund.payments", "get_payees", []);
        } catch (e) {
            this.notif.add(this._msg(e, _t("The funds could not be read.")), { type: "danger" });
            this.state.setup = { payees: [], can_write: false, currencies: [] };
        }
    }
    editPayee(payee) {
        const setup = this.state.setup || {};
        this.state.editing = payee
            ? JSON.parse(JSON.stringify(payee))
            : blankPayee(setup.company_currency_id);
        this.state.optionTerm = "";
        this.state.options = [];
        this.findOptions("");
    }
    cancelEdit() { this.state.editing = null; }
    onEdit(field, ev) { this.state.editing[field] = ev.target.value; }
    async findOptions(term) {
        const seq = ++this._optSeq;
        this.state.optionTerm = term;
        try {
            const res = await this.orm.call("pb.fund.payments", "item_options",
                                            [term || "", (this.state.editing && this.state.editing.id) || 0]);
            if (seq === this._optSeq) { this.state.options = res; }
        } catch {
            if (seq === this._optSeq) { this.state.options = []; }
        }
    }
    onOptionSearch(ev) { this.findOptions(ev.target.value); }
    hasItem(opt) {
        const ed = this.state.editing;
        return !!(ed && ed.items.some((it) => it.rule_id === opt.rule_id));
    }
    addItem(opt) {
        const ed = this.state.editing;
        if (!ed || this.hasItem(opt)) { return; }
        ed.items.push({ ...opt });
    }
    removeItem(item) {
        const ed = this.state.editing;
        ed.items = ed.items.filter((it) => it.rule_id !== item.rule_id);
    }
    setShare(item, share) { item.share = share; }
    async savePayee() {
        const ed = this.state.editing;
        if (!ed) { return; }
        if (!ed.name.trim()) { this.notif.add(_t("Give the fund or office a name."), { type: "warning" }); return; }
        this.state.saving = true;
        try {
            await this.orm.call("pb.fund.payments", "save_payee", [{
                id: ed.id || 0, name: ed.name, currency_id: parseInt(ed.currency_id || 0, 10) || 0,
                due_day: parseInt(ed.due_day || 15, 10) || 15,
                bank_details: ed.bank_details, reference_text: ed.reference_text,
                items: ed.items.map((it) => ({ rule_id: it.rule_id, share: it.share })),
            }]);
            this.notif.add(_t("Saved. Work the month out again to see it in the figures."), { type: "success" });
            this.state.editing = null;
            await this.loadSetup();
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be saved.")), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }
    async archivePayee(payee) {
        try {
            await this.orm.call("pb.fund.payments", "archive_payee", [payee.id]);
            this.notif.add(_t("Removed. Payments already worked out for it are kept."), { type: "success" });
            this.state.editing = null;
            await this.loadSetup();
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be removed.")), { type: "danger" });
        }
    }

    // ------------------------------------------------------------ suggest
    async openSuggest() {
        this.state.suggestBusy = true;
        this.state.suggestOpen = true;
        try {
            const res = await this.orm.call("pb.fund.payments", "suggest", []);
            this.state.proposals = res.map((p) => ({
                ...p, into: "", items: p.items.map((it) => ({ ...it, on: true })),
            }));
        } catch (e) {
            this.notif.add(this._msg(e, _t("Nothing could be suggested just now.")), { type: "danger" });
            this.state.proposals = [];
        } finally {
            this.state.suggestBusy = false;
        }
    }
    closeSuggest() { this.state.suggestOpen = false; }
    onProposal(p, field, ev) { p[field] = ev.target.value; }
    toggleItem(it) { it.on = !it.on; }
    intoOptions(p) {
        return this.state.proposals.filter((o) => o.key !== p.key && !o.into && o.company_id === p.company_id);
    }
    get suggestCount() {
        return this.state.proposals.filter((p) => !p.into && this._proposalItems(p).length).length;
    }
    _proposalItems(p) {
        const own = p.items.filter((it) => it.on);
        const joined = this.state.proposals.filter((o) => o.into === p.key)
            .flatMap((o) => o.items.filter((it) => it.on));
        return [...own, ...joined];
    }
    async acceptSuggestions() {
        this.state.suggestBusy = true;
        try {
            const res = await this.orm.call("pb.fund.payments", "create_from_suggestions", [
                this.state.proposals.map((p) => ({
                    key: p.key, name: p.name, company_id: p.company_id, into: p.into,
                    items: p.items.map((it) => ({ rule_id: it.rule_id, share: it.share, on: it.on })),
                })),
            ]);
            this.notif.add(res.made === 1 ? _t("1 fund added.") : _t("%s funds added.", res.made), { type: "success" });
            this.state.suggestOpen = false;
            if (!this.state.setupOpen) { this.state.setupOpen = true; }
            await this.loadSetup();
            await this.load();
        } catch (e) {
            this.notif.add(this._msg(e, _t("The funds could not be added.")), { type: "danger" });
        } finally {
            this.state.suggestBusy = false;
        }
    }

    // ------------------------------------------------------------ plumbing
    onKey(ev) {
        if (ev.key !== "Escape") { return; }
        if (this.state.act) { this.state.act = null; return; }
        if (this.state.suggestOpen) { this.state.suggestOpen = false; return; }
        if (this.state.editing) { this.state.editing = null; return; }
        if (this.state.setupOpen) { this.closeSetup(); return; }
        if (this.state.pay) { this.closePay(); }
    }
    roleLabel(role) {
        return { deduction: _t("Taken off pay"), employer_cost: _t("Employer cost") }[role] || "";
    }
    _msg(e, fallback) {
        if (e && e.message && e.message.data && e.message.data.message) { return e.message.data.message; }
        if (e && e.data && e.data.message) { return e.data.message; }
        return fallback;
    }
}

registry.category("actions").add("pb_fund_payments_board", PbFundPaymentsBoard);
