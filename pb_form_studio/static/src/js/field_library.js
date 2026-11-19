/** @odoo-module **/
/**
 * Settings › Form builder — the Field library (POC "Field library" tab).
 *
 * Every custom field in this company: what it is, which record type, where it
 * is placed, how filled it is, who can see it, in which countries it applies,
 * and what uses it. Edit opens a side sheet with the same settings as the
 * Studio's properties panel (`update_field`); Delete asks for the field's
 * name to be typed and lists what still uses it (`delete_field` re-checks).
 *
 * Administrator only: the card is registered for `base.group_system`, and
 * `library` / `update_field` / `delete_field` refuse anybody else.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { fsIc, KIND_ICON } from "./fs_icons";
import { FACADE } from "./fs_words";

const LANG_NAMES = { vi_VN: "Tiếng Việt", id_ID: "Bahasa Indonesia" };

export class FieldLibrary extends Component {
    static template = "pb_form_studio.FieldLibrary";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true, error: "", rows: [], screens: [], langs: [], countries: [],
            busy: "", filter: "all", term: "", edit: null, del: null, saving: false,
        });
        onWillStart(() => this.load());
    }

    ic(n, s = 16) { return fsIc(n, s); }

    async load() {
        this.state.loading = true;
        try {
            const res = await this.orm.call(FACADE, "library", []);
            Object.assign(this.state, { rows: res.fields, screens: res.screens, langs: res.langs,
                                        countries: res.countries, busy: res.busy, error: "" });
        } catch (e) {
            this.state.error = (e && e.data && e.data.message) || _t("The Field library could not open.");
        } finally {
            this.state.loading = false;
        }
    }

    get back() {
        const ctx = (this.props.action && this.props.action.context) || {};
        return ctx.pb_back || null;
    }
    goBack() {
        const b = this.back;
        if (b && (b.tag || b.xmlid)) {
            return this.action.doAction(b.xmlid || { type: "ir.actions.client", tag: b.tag, context: b.context || {} });
        }
        return this.action.doAction({ type: "ir.actions.client", tag: "pb_settings_hub" });
    }
    get backLabel() { return _t("Back to %s", (this.back && this.back.label) || _t("Settings")); }

    // ------------------------------------------------------------ figures
    get recordTypes() {
        const out = [];
        for (const r of this.state.rows) { if (!out.includes(r.record_type)) { out.push(r.record_type); } }
        return out;
    }
    get rows() {
        const t = (this.state.term || "").toLowerCase().trim();
        return this.state.rows.filter((r) => (this.state.filter === "all" || r.record_type === this.state.filter)
            && (!t || r.label.toLowerCase().includes(t) || (r.help || "").toLowerCase().includes(t)));
    }
    get kpis() {
        const rows = this.state.rows;
        return [
            { key: "n", icon: "sparkles", tone: "", value: rows.length, label: _t("Custom fields") },
            { key: "f", icon: "calculator", tone: "g", value: rows.filter((r) => r.formula_ok).length, label: _t("Feed pay formulas") },
            { key: "l", icon: "columns", tone: "b", value: rows.filter((r) => r.list_ok).length, label: _t("Shown in lists") },
            { key: "h", icon: "eyeOff", tone: "a", value: rows.filter((r) => !r.where.length).length, label: _t("Not on any screen") },
        ];
    }
    kpiClass(k) { return { quiet: !k.value, ["t-" + k.tone]: Boolean(k.tone) }; }
    filterClass(key) { return { on: this.state.filter === key }; }
    setFilter(key) { this.state.filter = key; }
    onTerm(ev) { this.state.term = ev.target.value; }
    kindIcon(r) { return fsIc(KIND_ICON[r.kind] || "type", 14); }
    fillPct(r) { return r.total ? Math.round((100 * (r.filled || 0)) / r.total) : 0; }
    fillStyle(r) { return "--p:" + this.fillPct(r) + "%"; }
    fillText(r) { return (r.filled || 0).toLocaleString() + " / " + (r.total || 0).toLocaleString(); }
    optionsText(r) { return (r.options || []).map((o) => o.label).join(" · "); }
    countriesText(r) { return (r.countries || []).length ? r.countries.map((c) => c.name).join(", ") : _t("All countries"); }
    usage(r) {
        return [
            { label: _t("Screen"), on: r.where.length > 0 },
            { label: _t("Lists"), on: r.list_ok },
            { label: _t("Formulas"), on: r.formula_ok },
            { label: _t("Self-service"), on: r.vis === "all" },
        ];
    }
    usageClass(u) { return { on: u.on }; }
    usedCount(r) { return (r.used_by || []).reduce((n, u) => n + (u.count || 0), 0); }
    get hasRows() { return this.state.rows.length > 0; }
    get emptyTitle() { return _t("No custom fields yet"); }

    // ------------------------------------------------------------- editing
    startEdit(r) {
        this.state.del = null;
        this.state.edit = {
            row: r, label: r.label, help: r.help || "", vis: r.vis, required: r.required,
            list_ok: r.list_ok, formula_ok: r.formula_ok,
            labels: { ...(r.labels || {}) }, helps: { ...(r.helps || {}) },
            countries: (r.countries || []).map((c) => ({ ...c })), options: (r.options || []).map((o) => ({ ...o })),
            countryTerm: "",
        };
    }
    closeEdit() { this.state.edit = null; }
    get langs() { return (this.state.langs || []).filter((l) => l !== "en_US"); }
    langName(l) { return LANG_NAMES[l] || l; }
    onEditInput(key, ev) { this.state.edit[key] = ev.target.value; }
    onEditLang(lang, ev) { this.state.edit.labels[lang] = ev.target.value; }
    onEditToggle(key) {
        if (key === "formula_ok" && !this.state.edit.row.formula_possible) { return; }
        this.state.edit[key] = !this.state.edit[key];
    }
    switchAttr(on) { return on ? "true" : "false"; }
    get visOptions() {
        return [
            { value: "all", label: _t("Everyone, including the employee") },
            { value: "hr", label: _t("HR staff and administrators") },
            { value: "admin", label: _t("Administrators only") },
        ];
    }
    onOption(i, ev) { this.state.edit.options[i].label = ev.target.value; }
    addOption() { this.state.edit.options.push({ value: "", label: _t("Option %s", this.state.edit.options.length + 1) }); }
    removeOption(i) { if (this.state.edit.options.length > 1) { this.state.edit.options.splice(i, 1); } }
    onCountryTerm(ev) { this.state.edit.countryTerm = ev.target.value; }
    get countryMatches() {
        const e = this.state.edit;
        const t = (e.countryTerm || "").toLowerCase().trim();
        if (!t) { return []; }
        const chosen = new Set(e.countries.map((c) => c.id));
        const rank = (c) => (c.name.toLowerCase().startsWith(t) ? 0 : 1);
        return this.state.countries.filter((c) => !chosen.has(c.id) && c.name.toLowerCase().includes(t))
            .sort((a, b) => rank(a) - rank(b)).slice(0, 6);
    }
    addCountry(c) { this.state.edit.countries.push({ id: c.id, name: c.name }); this.state.edit.countryTerm = ""; }
    removeCountry(c) { this.state.edit.countries = this.state.edit.countries.filter((x) => x.id !== c.id); }
    allCountries() { this.state.edit.countries = []; }
    async saveEdit() {
        const e = this.state.edit;
        const vals = {
            label: e.label, help: e.help, vis: e.vis, is_required: e.required, list_ok: e.list_ok,
            formula_ok: e.formula_ok, labels: e.labels, country_ids: e.countries.map((c) => c.id),
        };
        if (e.row.kind === "select") { vals.options = e.options.map((o) => ({ value: o.value, label: o.label })); }
        this.state.saving = true;
        try {
            await this.orm.call(FACADE, "update_field", [e.row.model, e.row.name, vals]);
            this.notification.add(_t("Saved. Everyone sees the change the next time their screen loads."), { type: "success" });
            this.state.edit = null;
            await this.load();
        } catch (err) {
            this.notification.add((err && err.data && err.data.message) || _t("That could not be saved."), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }

    // ------------------------------------------------------------- delete
    startDelete(r) { this.state.edit = null; this.state.del = { row: r, typed: "" }; }
    closeDelete() { this.state.del = null; }
    onDelTyped(ev) { this.state.del.typed = ev.target.value; }
    get delReady() {
        const d = this.state.del;
        return Boolean(d && d.typed.trim().toLowerCase() === d.row.label.trim().toLowerCase());
    }
    typeToConfirm(r) { return _t("Type %s to confirm.", r.label); }
    deleteWarn(r) {
        return _t("This deletes the field and every value in it (%s filled in). A copy of the values is kept in the Form builder history.", (r.filled || 0).toLocaleString());
    }
    async doDelete() {
        const d = this.state.del;
        if (!this.delReady) { return; }
        this.state.saving = true;
        try {
            await this.orm.call(FACADE, "delete_field", [d.row.model, d.row.name, d.typed]);
            this.notification.add(_t("%s is deleted.", d.row.label), { type: "success" });
            this.state.del = null;
            await this.load();
        } catch (err) {
            this.notification.add((err && err.data && err.data.message) || _t("That could not be deleted."), { type: "danger", sticky: true });
        } finally {
            this.state.saving = false;
        }
    }
}

registry.category("actions").add("pb_form_library", FieldLibrary);
