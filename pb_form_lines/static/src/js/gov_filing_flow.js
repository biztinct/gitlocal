/** @odoo-module **/
/**
 * Prepare a filing — period → check → send for approval → download
 * (WDGAP S2-A). Opened from Compliance › Filings or from Form lines with
 * `pb_form_id` in the context.
 *
 * The flow writes nothing until "Prepare and send for approval" is pressed;
 * the check step only reads. A download asks the server first, so a refusal
 * is a sentence, not a broken download.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { download } from "@web/core/network/download";
import { pbfIcon } from "@pb_filter_kit/js/filter_kit";
import { HubBackChip, hubBack, openHub } from "@pb_hub/js/hub_nav";

const MODEL = "pb.gov.form.board";

export class PbGovFiling extends Component {
    static template = "pb_form_lines.PbGovFiling";
    static components = { HubBackChip };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.icon = pbfIcon;
        this.back = hubBack(this.props);
        const ctx = (this.props.action && this.props.action.context) || {};
        this.formId = ctx.pb_form_id || 0;
        this.state = useState({
            loaded: false, step: "period", form: null, period: "", periodKind: "month",
            year: new Date().getFullYear(), quarter: 1, schemeIds: [], currencyId: 0,
            check: null, filing: null, busy: false,
        });
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        try {
            const form = await this.orm.call(MODEL, "flow_start", [this.formId]);
            this.formId = form.id;
            this.state.form = form;
            this.state.period = form.default_period;
            this.state.periodKind = form.period_kind === "quarter" ? "quarter"
                : (form.period_kind === "tax_year" ? "year" : "month");
            const q = /^(\d{4})-Q([1-4])$/.exec(form.default_period || "");
            if (q) { this.state.year = parseInt(q[1], 10); this.state.quarter = parseInt(q[2], 10); }
            if (/^\d{4}$/.test(form.default_period || "")) { this.state.year = parseInt(form.default_period, 10); }
            this.state.schemeIds = form.schemes.map((s) => s.id);
        } catch (e) {
            this.notif.add(this._msg(e, _t("This form could not be opened.")), { type: "danger" });
        } finally {
            this.state.loaded = true;
        }
    }

    get form() { return this.state.form; }

    get acceptedLine() {
        const f = this.form;
        return f ? _t("Accepted by the authority — marked by %(who)s on %(when)s.", { who: f.accepted_by, when: f.accepted_on }) : "";
    }
    preparedLine(f) {
        return _t("Prepared by %(who)s on %(when)s · %(n)s people", { who: f.prepared_by, when: f.prepared_on, n: f.people });
    }
    downloadedLine(f) {
        return _t("Last downloaded by %(who)s on %(when)s.", { who: f.downloaded_by, when: f.downloaded_on });
    }
    historyLine(h) {
        return _t("%(n)s people · %(who)s · %(when)s", { n: h.people, who: h.prepared_by, when: h.prepared_on });
    }
    lookLine(n) {
        return n === 1 ? _t("1 person needs a look") : _t("%s people need a look", n);
    }
    waitingLine(f) {
        return f.waiting_for ? _t("Waiting for %s.", f.waiting_for) : _t("Waiting for its approver.");
    }

    get steps() {
        const order = ["period", "check", "approval"];
        const labels = { period: _t("Period"), check: _t("Check"), approval: _t("Approval and download") };
        const at = order.indexOf(this.state.step);
        return order.map((key, i) => ({ key, label: labels[key], n: i + 1, done: i < at, on: i === at }));
    }

    get periodKey() {
        if (this.state.periodKind === "year") { return String(this.state.year); }
        if (this.state.periodKind === "quarter") { return `${this.state.year}-Q${this.state.quarter}`; }
        return this.state.period && /^\d{4}-\d{2}$/.test(this.state.period) ? this.state.period : "";
    }

    get canQuarter() { return this.form && (this.form.period_kind === "quarter" || this.form.quarter_allowed); }
    get canMonth() { return this.form && this.form.period_kind === "month"; }
    get years() {
        // WDGAP S2-B: the server names the years in the authority's tax year
        // ("2026–27" for India); the old list stays as the fallback
        const opts = this.form && this.form.year_options;
        if (opts && opts.length) { return opts.map((o) => ({ key: parseInt(o.key, 10), label: o.label })); }
        const y = new Date().getFullYear();
        return [y - 2, y - 1, y, y + 1].map((k) => ({ key: k, label: String(k) }));
    }
    get quarterLabels() {
        const labels = this.form && this.form.quarter_labels;
        if (labels && labels.length === 4) { return labels; }
        return [_t("January – March"), _t("April – June"), _t("July – September"), _t("October – December")];
    }
    get isYear() { return this.form && this.form.period_kind === "tax_year"; }

    // ------------------------------------------------ certificates (S2-B)
    releasedLine(f) {
        return _t("Released to employees by %(who)s on %(when)s.", { who: f.released_by, when: f.released_on });
    }
    certCountLine(f) {
        return f.certificates === 1 ? _t("1 personal certificate") : _t("%s personal certificates", f.certificates);
    }
    async setReleased(value) {
        const f = this.state.filing;
        if (!f || this.state.busy) { return; }
        this.state.busy = true;
        try {
            this.state.filing = await this.orm.call(MODEL, "set_released", [f.id, value]);
            this.notif.add(value ? _t("Released. Each person now sees their own certificate on My Payobook.")
                : _t("Taken back. Employees no longer see these certificates."), { type: "success" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be done.")), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    setKind(kind) {
        this.state.periodKind = kind;
        if (kind === "month" && !/^\d{4}-\d{2}$/.test(this.state.period || "")) {
            this.state.period = `${this.state.year}-${String((this.state.quarter - 1) * 3 + 1).padStart(2, "0")}`;
        }
    }
    onMonth(ev) { this.state.period = ev.target.value || this.state.period; }
    onYear(ev) { this.state.year = parseInt(ev.target.value, 10) || this.state.year; }
    onQuarter(ev) { this.state.quarter = parseInt(ev.target.value, 10) || 1; }
    hasScheme(id) { return this.state.schemeIds.includes(id); }
    toggleScheme(id) {
        const list = this.state.schemeIds;
        this.state.schemeIds = list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
    }
    onCurrency(ev) { this.state.currencyId = parseInt(ev.target.value, 10) || 0; }

    async runCheck() {
        if (this.state.busy) { return; }
        if (!this.periodKey) { this.notif.add(_t("Pick the period first."), { type: "warning" }); return; }
        if (!this.state.schemeIds.length) { this.notif.add(_t("Pick at least one pay scheme."), { type: "warning" }); return; }
        this.state.busy = true;
        try {
            this.state.check = await this.orm.call(MODEL, "flow_check", [this.formId, this.periodKey,
                this.state.schemeIds, this.state.currencyId || false]);
            this.state.step = "check";
        } catch (e) {
            this.notif.add(this._msg(e, _t("The figures could not be read.")), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    warnTone(w) { return { block: "is-red", warn: "is-amber", info: "is-grey" }[w.level] || "is-grey"; }
    lineValue(line) {
        const v = line.value || 0;
        if (line.kind === "count") { return String(v); }
        return Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
    }

    async prepare() {
        if (this.state.busy || !this.state.check || this.state.check.blocked) { return; }
        this.state.busy = true;
        try {
            this.state.filing = await this.orm.call(MODEL, "flow_prepare", [this.formId, this.periodKey,
                this.state.schemeIds, this.state.check.currency_id || false]);
            this.state.step = "approval";
            const f = this.state.filing;
            this.notif.add(f.downloadable ? _t("Prepared and approved. The files can be downloaded.") : _t("Prepared and sent for approval."), { type: "success" });
            await this._refreshHistory();
        } catch (e) {
            this.notif.add(this._msg(e, _t("The filing could not be prepared.")), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async resend() {
        const f = this.state.filing;
        if (!f || this.state.busy) { return; }
        this.state.busy = true;
        try {
            this.state.filing = await this.orm.call(MODEL, "flow_submit", [f.id]);
            await this._refreshHistory();
        } catch (e) {
            this.notif.add(this._msg(e, _t("It could not be sent in.")), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async openFiling(row) {
        try {
            this.state.filing = await this.orm.call(MODEL, "get_filing", [row.id]);
            this.state.step = "approval";
        } catch (e) {
            this.notif.add(this._msg(e, _t("That filing could not be opened.")), { type: "danger" });
        }
    }

    async refreshFiling() {
        if (this.state.filing) { await this.openFiling(this.state.filing); }
    }

    async _refreshHistory() {
        try {
            const form = await this.orm.call(MODEL, "flow_start", [this.formId]);
            this.state.form.history = form.history;
        } catch {
            // the history is a convenience; the filing itself is on screen
        }
    }

    async downloadFile(file) {
        const f = this.state.filing;
        if (!f || this.state.busy) { return; }
        this.state.busy = true;
        try {
            await this.orm.call(MODEL, "download_check", [f.id, file.id]);
            await download({ url: "/pb_form_lines/filing/download", data: { filing_id: f.id, file_id: file.id } });
        } catch (e) {
            this.notif.add(this._msg(e, _t("That file could not be downloaded.")), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    startAgain() { this.state.step = "period"; this.state.check = null; this.state.filing = null; }
    backToPeriod() { this.state.step = "period"; }

    openLines() {
        openHub(this.action, {
            tag: "pb_form_lines", context: { pb_form_id: this.formId },
            back: { label: _t("Prepare a filing"), tag: "pb_gov_filing", context: { pb_form_id: this.formId } },
        });
    }

    stateTone(state) {
        return { approved: "is-green", pending: "is-blue", returned: "is-amber", rejected: "is-red" }[state] || "is-grey";
    }

    _msg(e, fallback) {
        if (e && e.message && e.message.data && e.message.data.message) { return e.message.data.message; }
        if (e && e.data && e.data.message) { return e.data.message; }
        return fallback;
    }
}

registry.category("actions").add("pb_gov_filing", PbGovFiling);
