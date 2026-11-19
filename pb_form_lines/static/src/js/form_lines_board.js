/** @odoo-module **/
/**
 * Form lines — HR says once which pay item goes on each line of each
 * government form (WDGAP S2-A). Opened from Compliance › Filings.
 *
 * Quiet board: grey until something needs doing; amber only for a line that
 * the form needs and that has no pay item yet, and for the adviser sentence
 * (owner ruling G3). Every write is a click; nothing is written on mount.
 */
import { Component, useState, onWillStart, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { pbfIcon } from "@pb_filter_kit/js/filter_kit";
import { HubBackChip, hubBack, openHub } from "@pb_hub/js/hub_nav";

const MODEL = "pb.gov.form.board";

export class PbFormLines extends Component {
    static template = "pb_form_lines.PbFormLines";
    static components = { HubBackChip };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.icon = pbfIcon;
        this.back = hubBack(this.props);
        const ctx = (this.props.action && this.props.action.context) || {};
        this.state = useState({
            loaded: false, data: { forms: [], countries: [] }, country: ctx.pb_country || "",
            formId: ctx.pb_form_id || 0, form: null, busy: false,
            editing: null, options: [], optionTerm: "",
            settings: { employer_tax_id: "", place_of_business: "" },
            suggestOpen: false, proposals: [], suggestBusy: false, sourceOpen: false,
        });
        this._optSeq = 0;
        useExternalListener(window, "keydown", (ev) => this.onKey(ev));
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        try {
            this.state.data = await this.orm.call(MODEL, "get_forms", [this.state.country || false]);
            const forms = this.state.data.forms || [];
            if (!forms.find((f) => f.id === this.state.formId)) {
                this.state.formId = forms.length ? forms[0].id : 0;
            }
            if (this.state.formId) { await this.openForm(this.state.formId); }
            else { this.state.form = null; }
        } catch (e) {
            this.notif.add(this._msg(e, _t("The forms could not be read.")), { type: "danger" });
        } finally {
            this.state.loaded = true;
        }
    }

    async pickCountry(code) {
        this.state.country = this.state.country === code ? "" : code;
        this.state.formId = 0;
        await this.load();
    }

    async openForm(formId) {
        this.state.formId = formId;
        this.state.editing = null;
        try {
            const form = await this.orm.call(MODEL, "get_form", [formId]);
            this._setForm(form);
        } catch (e) {
            this.notif.add(this._msg(e, _t("The form could not be read.")), { type: "danger" });
        }
    }

    _setForm(form) {
        this.state.form = form;
        this.state.settings = { ...form.settings };
        const card = (this.state.data.forms || []).find((f) => f.id === form.id);
        if (card) { Object.assign(card, {
            lines_mapped: form.lines_mapped, required_missing: form.required_missing,
            accepted: form.accepted, items: form.items,
        }); }
    }

    get form() { return this.state.form; }

    get acceptedLine() {
        const f = this.form;
        return f ? _t("Accepted by the authority — marked by %(who)s on %(when)s.", { who: f.accepted_by, when: f.accepted_on }) : "";
    }

    setLine(f) {
        return _t("%(done)s of %(all)s lines set", { done: f.lines_mapped, all: f.lines_mappable });
    }

    get mappedCount() {
        const f = this.form;
        return f ? `${f.lines_mapped} / ${f.lines_mappable}` : "";
    }

    lineTone(line) {
        if (!line.mappable) { return "is-derived"; }
        if (line.items.length) { return "is-set"; }
        return line.required ? "is-needed" : "is-empty";
    }

    sourceLabel(source) {
        return source === "computed_value" ? _t("Worked-out value") : _t("Payslip line");
    }

    // ------------------------------------------------------------ editing
    editLine(line) {
        this.state.editing = {
            lineId: line.id, code: line.code, label: line.label, kind: line.kind,
            items: line.items.map((it) => ({ ...it })),
        };
        this.findOptions("");
    }
    cancelEdit() { this.state.editing = null; }
    async findOptions(term) {
        const seq = ++this._optSeq;
        this.state.optionTerm = term;
        try {
            const res = await this.orm.call(MODEL, "item_options", [this.state.formId, term || ""]);
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
        ed.items.push({ ...opt, sign: "add", share_pct: 100 });
    }
    removeItem(item) {
        const ed = this.state.editing;
        ed.items = ed.items.filter((it) => it.rule_id !== item.rule_id);
    }
    setSource(item, source) { item.source = source; }
    setSign(item, sign) { item.sign = sign; }
    onShare(item, ev) { item.share_pct = parseFloat(ev.target.value || "100") || 100; }

    async saveLine() {
        const ed = this.state.editing;
        if (!ed || this.state.busy) { return; }
        this.state.busy = true;
        try {
            const form = await this.orm.call(MODEL, "save_line", [this.state.formId, ed.lineId,
                ed.items.map((it) => ({ rule_id: it.rule_id, source: it.source, sign: it.sign, share_pct: it.share_pct }))]);
            this._setForm(form);
            this.state.editing = null;
            this.notif.add(_t("Saved."), { type: "success" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be saved.")), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------------------------------ settings
    onSetting(key, ev) { this.state.settings[key] = ev.target.value; }
    async saveSettings() {
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            const form = await this.orm.call(MODEL, "save_settings", [this.state.formId, this.state.settings]);
            this._setForm(form);
            this.notif.add(_t("Saved."), { type: "success" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be saved.")), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async toggleAccepted() {
        const f = this.form;
        if (!f || this.state.busy) { return; }
        this.state.busy = true;
        try {
            const card = await this.orm.call(MODEL, "set_accepted", [f.id, !f.accepted]);
            Object.assign(f, { accepted: card.accepted, accepted_by: card.accepted_by, accepted_on: card.accepted_on });
            const listed = (this.state.data.forms || []).find((x) => x.id === f.id);
            if (listed) { listed.accepted = card.accepted; }
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be changed.")), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    toggleSource() { this.state.sourceOpen = !this.state.sourceOpen; }

    // ------------------------------------------------------------ suggest
    async openSuggest() {
        this.state.suggestOpen = true;
        this.state.suggestBusy = true;
        try {
            const res = await this.orm.call(MODEL, "suggest", [this.state.formId]);
            this.state.proposals = res.map((p) => ({ ...p, on: true }));
        } catch (e) {
            this.notif.add(this._msg(e, _t("Nothing could be suggested just now.")), { type: "danger" });
            this.state.proposals = [];
        } finally {
            this.state.suggestBusy = false;
        }
    }
    closeSuggest() { this.state.suggestOpen = false; }
    toggleProposal(p) { p.on = !p.on; }
    get suggestCount() { return this.state.proposals.filter((p) => p.on).length; }
    async acceptSuggestions() {
        this.state.suggestBusy = true;
        try {
            const res = await this.orm.call(MODEL, "accept_suggestions", [this.state.formId,
                this.state.proposals.map((p) => ({ line_id: p.line_id, rule_id: p.rule_id, source: p.source, on: p.on }))]);
            this._setForm(res.form);
            this.state.suggestOpen = false;
            this.notif.add(res.made === 1 ? _t("1 pay item put on its line.") : _t("%s pay items put on their lines.", res.made), { type: "success" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be saved.")), { type: "danger" });
        } finally {
            this.state.suggestBusy = false;
        }
    }

    // ------------------------------------------------------------ doors
    prepare() {
        const f = this.form;
        if (!f) { return; }
        openHub(this.action, {
            tag: "pb_gov_filing", context: { pb_form_id: f.id },
            back: { label: _t("Form lines"), tag: "pb_form_lines", context: { pb_form_id: f.id } },
        });
    }

    onKey(ev) {
        if (ev.key !== "Escape") { return; }
        if (this.state.suggestOpen) { this.state.suggestOpen = false; return; }
        if (this.state.editing) { this.state.editing = null; }
    }

    _msg(e, fallback) {
        if (e && e.message && e.message.data && e.message.data.message) { return e.message.data.message; }
        if (e && e.data && e.data.message) { return e.data.message; }
        return fallback;
    }
}

registry.category("actions").add("pb_form_lines", PbFormLines);
