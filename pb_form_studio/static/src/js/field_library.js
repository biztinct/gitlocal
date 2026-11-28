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
import { Component, useState, useRef, onWillStart, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { rpcBus } from "@web/core/network/rpc";
import { fsIc, KIND_ICON } from "./fs_icons";
import { FACADE, fold, foldMatch, isSlashKey } from "./fs_words";
import { CountryPicker, SHOW_ALL, SHOW_NONE, showOnly, showSame, showUnion, showCovers, showApplies, showChipText, showLongText } from "./country_picker";

const LANG_NAMES = { en_US: "English", vi_VN: "Tiếng Việt", id_ID: "Bahasa Indonesia" };

export class FieldLibrary extends Component {
    static template = "pb_form_studio.FieldLibrary";
    static components = { CountryPicker };
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true, error: "", rows: [], std: [], screens: [], langs: [], countries: [],
            inUse: [], noneCount: 0,
            busy: "", filter: "all", term: "", edit: null, del: null, saving: false,
            // R24 — kind chip and Country of Work picker (client-side only)
            kind: "all", country: 0, lang: "en_US",
            // R23 — the Edit sheet of a standard field (R31: "Shown for")
            stdEdit: null,
        });
        this.search = useRef("libSearch");
        useExternalListener(window, "keydown", (ev) => {
            if (isSlashKey(ev) && !this.state.edit && !this.state.del && !this.state.stdEdit && this.search.el) {
                ev.preventDefault();
                this.search.el.focus();
                this.search.el.select();
            }
        });
        onWillStart(() => this.load());
    }

    ic(n, s = 16) { return fsIc(n, s); }

    async load() {
        this.state.loading = true;
        try {
            const res = await this.orm.call(FACADE, "library", []);
            Object.assign(this.state, { rows: res.fields, std: res.std || [], screens: res.screens,
                                        langs: res.langs, countries: res.countries, busy: res.busy,
                                        inUse: res.countries_in_use || [], noneCount: res.countries_none || 0,
                                        lang: res.lang || "en_US", error: "" });
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
        for (const r of this.allRows) { if (!out.includes(r.record_type)) { out.push(r.record_type); } }
        return out;
    }
    /** Own fields first, then every standard field (R23), one list. */
    get allRows() { return [...this.state.rows, ...this.state.std]; }
    isStdRow(r) { return Boolean(r.stdbox && !r.custom); }
    rowHidden(r) {
        if (this.isStdRow(r)) {
            // R31: the administrator shows it for fewer people than the product does
            const sb = r.stdbox;
            return Boolean(sb.changed && sb.show && sb.base && !showCovers(sb.show, sb.base));
        }
        return !r.where.length;
    }
    /** R31 — taken off the screens by the product, not shown again. */
    rowOff(r) { return this.isStdRow(r) && Boolean(r.stdbox.removed) && (r.stdbox.show || {}).mode === "none"; }
    rowOnPortal(r) { return Boolean(r.portal && r.portal.show); }
    /** R24 — does the field show for people of this Country of Work? */
    rowApplies(r, cid) {
        if (!cid) { return true; }
        if (this.isStdRow(r)) { return showApplies(r.stdbox.show, cid); }
        return !(r.countries || []).length || r.countries.some((c) => c.id === cid);
    }
    get rows() {
        const kind = this.state.kind;
        const cid = Number(this.state.country) || 0;
        return this.allRows.filter((r) => {
            if (this.state.filter !== "all" && r.record_type !== this.state.filter) { return false; }
            if (kind === "own" && this.isStdRow(r)) { return false; }
            if (kind === "std" && !this.isStdRow(r)) { return false; }
            if (kind === "hidden" && !this.rowHidden(r)) { return false; }
            if (kind === "off" && !(this.isStdRow(r) && r.stdbox.removed)) { return false; }
            if (kind === "portal" && !this.rowOnPortal(r)) { return false; }
            if (!this.rowApplies(r, cid)) { return false; }
            return foldMatch(this.state.term, r.label, r.help, (r.stdbox || {}).builtin);
        });
    }
    get kindChips() {
        return [
            { key: "all", label: _t("All") }, { key: "own", label: _t("Own fields") },
            { key: "std", label: _t("Standard fields") }, { key: "hidden", label: _t("Hidden") },
            { key: "portal", label: _t("On My Payobook") },
            { key: "off", label: _t("Taken off the screens") },
        ];
    }
    kindClass(c) { return { on: this.state.kind === c.key }; }
    setKind(key) { this.state.kind = key; }
    get countryOptions() { return [...this.state.countries].sort((a, b) => a.name.localeCompare(b.name)); }
    onCountry(ev) { this.state.country = Number(ev.target.value) || 0; }
    isCountry(c) { return Number(this.state.country) === c.id; }
    get filtered() {
        return Boolean(fold(this.state.term)) || this.state.kind !== "all" || this.state.filter !== "all"
            || Boolean(Number(this.state.country));
    }
    get countText() {
        const n = this.rows.length;
        const total = this.allRows.length;
        if (this.filtered) { return _t("%(n)s of %(total)s", { n, total }); }
        return total === 1 ? _t("1 field") : _t("%s fields", total);
    }
    clearFilters() {
        Object.assign(this.state, { term: "", kind: "all", filter: "all", country: 0 });
        if (this.search.el) { this.search.el.focus(); }
    }
    onSearchKey(ev) {
        if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); this.state.term = ""; }
    }
    get kpis() {
        const rows = this.state.rows;
        const std = this.state.std;
        return [
            { key: "n", icon: "sparkles", tone: "", value: rows.length, label: _t("Custom fields") },
            { key: "f", icon: "calculator", tone: "g", value: rows.filter((r) => r.formula_ok).length, label: _t("Feed pay formulas") },
            { key: "l", icon: "columns", tone: "b", value: rows.filter((r) => r.list_ok).length, label: _t("Shown in lists") },
            { key: "h", icon: "eyeOff", tone: "a", value: rows.filter((r) => !r.where.length).length, label: _t("Not on any screen") },
            { key: "sh", icon: "eyeOff", tone: "a", value: std.filter((r) => this.rowHidden(r)).length, label: _t("Standard fields hidden") },
            { key: "sr", icon: "pencil", tone: "", value: std.filter((r) => Object.keys(r.stdbox.labels || {}).length).length, label: _t("Standard fields renamed") },
        ];
    }
    // standard rows (R23)
    stdHiddenText(r) {
        const sb = r.stdbox;
        if (this.rowOff(r)) { return sb.comeback ? _t("Taken off the screens, stays off") : _t("Taken off the screens"); }
        return showChipText(sb.show);
    }
    stdShowSub(r) {
        const sb = r.stdbox;
        if (!sb.changed) { return ""; }
        return sb.removed ? _t("Shown again") : _t("Changed from: %s", showChipText(sb.base));
    }
    stdRenamedText(r) {
        const s = r.stdbox;
        return Object.keys(s.labels || {}).length ? _t("Built-in label: %s", s.builtin) : "";
    }
    get hasOwn() { return this.state.rows.length > 0; }
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
            { label: _t("My Payobook"), on: Boolean(r.portal && r.portal.show) },
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
            portal: r.portal ? { ...r.portal } : null,
        };
    }
    // My Payobook (R14)
    portalText(r) {
        const p = r.portal;
        if (!p) { return "—"; }
        if (!p.show) { return _t("Not shown"); }
        if (!p.edit) { return _t("Shown"); }
        return p.mode === "instant" ? _t("Can change · saves at once") : _t("Can change · HR approves");
    }
    toggleEditPortal(which) {
        const p = this.state.edit.portal;
        if (which === "show") {
            if (!p.can_show) { return; }
            p.show = !p.show;
            if (!p.show) { p.edit = false; }
        } else {
            if (!p.can_edit) { return; }
            p.edit = !p.edit;
            if (p.edit) { p.show = true; }
        }
    }
    setEditMode(mode) { if (mode === "instant" && this.state.edit.portal.mode_lock) { return; } this.state.edit.portal.mode = mode; }
    editModeClass(mode) { return { on: this.state.edit.portal.mode === mode }; }
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
    get editChosenIds() { return this.state.edit.countries.map((c) => c.id); }
    addCountry(c) {
        if (!c || c === "none" || this.editChosenIds.includes(c.id)) { return; }
        this.state.edit.countries.push({ id: c.id, name: c.name });
    }
    removeCountry(c) { this.state.edit.countries = this.state.edit.countries.filter((x) => x.id !== c.id); }
    allCountries() { this.state.edit.countries = []; }
    async saveEdit() {
        const e = this.state.edit;
        const vals = {
            label: e.label, help: e.help, vis: e.vis, is_required: e.required, list_ok: e.list_ok,
            formula_ok: e.formula_ok, labels: e.labels, country_ids: e.countries.map((c) => c.id),
        };
        if (e.row.kind === "select") { vals.options = e.options.map((o) => ({ value: o.value, label: o.label })); }
        if (e.portal) {
            Object.assign(vals, { portal_show: e.portal.show, portal_edit: e.portal.edit, portal_mode: e.portal.mode });
        }
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

    // -------------------------------------------- standard field (R23 sheet)
    startStdEdit(r, again = false) {
        const sb = r.stdbox;
        this.state.edit = null;
        this.state.del = null;
        let show = { ...(sb.show || SHOW_ALL), countries: [...((sb.show || SHOW_ALL).countries || [])] };
        if (again && sb.propose && !sb.comeback) {
            show = sb.propose.mode === "only" ? showOnly(sb.propose.countries, sb.propose.unset) : SHOW_ALL;
        }
        this.state.stdEdit = {
            row: r, labels: { ...(sb.labels || {}) }, show, picking: false,
            portal: r.portal ? { ...r.portal } : null,
        };
    }
    closeStdEdit() { this.state.stdEdit = null; }
    get allLangs() { return this.state.langs || ["en_US"]; }
    stdBuiltin(lang) {
        const sb = this.state.stdEdit.row.stdbox;
        return (sb.builtins || {})[lang] || sb.builtin || "";
    }
    onStdLabel(lang, ev) {
        const v = ev.target.value.trim();
        const e = this.state.stdEdit;
        if (v && v !== this.stdBuiltin(lang)) { e.labels[lang] = v; } else { delete e.labels[lang]; }
    }
    resetStdLabels() { this.state.stdEdit.labels = {}; }
    get stdHasLabels() { return Object.keys(this.state.stdEdit.labels || {}).length > 0; }
    // ------------------------------------------- R31 (FS-15): "Shown for"
    get eBase() { return this.state.stdEdit.row.stdbox.base || SHOW_ALL; }
    get eMode() {
        const e = this.state.stdEdit;
        return e.picking && e.show.mode !== "only" ? "only" : e.show.mode;
    }
    stdModeClass(mode) { return { on: this.eMode === mode }; }
    stdModeBlock(mode) {
        const sb = this.state.stdEdit.row.stdbox;
        if (sb.comeback && mode !== "none") { return sb.comeback; }
        if (!sb.lock) { return ""; }
        if (mode === "none" || (mode === "only" && this.eBase.mode === "all")) { return _t("Cannot be hidden. %s", sb.lock); }
        return "";
    }
    setStdMode(mode) {
        const e = this.state.stdEdit;
        if (this.stdModeBlock(mode) || this.eMode === mode) { return; }
        e.picking = false;
        if (mode === "all") { e.show = SHOW_ALL; }
        else if (mode === "none") { e.show = SHOW_NONE; }
        else {
            const from = e.show.mode === "only" ? e.show : this.eBase;
            if (from.mode === "only") { e.show = showOnly(from.countries, from.unset); }
            else { e.picking = true; }
        }
    }
    get eChosenIds() { return this.state.stdEdit.show.mode === "only" ? this.state.stdEdit.show.countries.map((c) => c.id) : []; }
    get eUnset() { return this.state.stdEdit.show.mode === "only" && Boolean(this.state.stdEdit.show.unset); }
    eChipFixed(c) { return Boolean(this.state.stdEdit.row.stdbox.lock) && this.eBase.countries.some((x) => x.id === c.id); }
    get eUnsetFixed() { return Boolean(this.state.stdEdit.row.stdbox.lock) && this.eBase.mode === "only" && Boolean(this.eBase.unset); }
    addStdCountry(c) {
        const e = this.state.stdEdit;
        const cur = e.show.mode === "only" ? e.show : { countries: [], unset: false };
        e.picking = false;
        e.show = c === "none" ? showOnly(cur.countries, true) : showOnly([...cur.countries, { id: c.id, name: c.name, code: c.code }], cur.unset);
    }
    removeStdCountry(c) {
        if (this.eChipFixed(c)) { return; }
        const e = this.state.stdEdit;
        e.show = showOnly(e.show.countries.filter((x) => x.id !== c.id), e.show.unset);
    }
    removeStdUnset() {
        if (this.eUnsetFixed) { return; }
        const e = this.state.stdEdit;
        e.show = showOnly(e.show.countries, false);
    }
    resetStdShow() { const e = this.state.stdEdit; e.picking = false; e.show = { ...this.eBase }; }
    get eChanged() { return !showSame(this.state.stdEdit.show, this.eBase); }
    get eBaseText() {
        const sb = this.state.stdEdit.row.stdbox;
        return sb.removed ? _t("Taken off the screens") : showLongText(this.eBase);
    }
    get eShowText() { return showLongText(this.state.stdEdit.show); }
    get eLockNote() {
        const sb = this.state.stdEdit.row.stdbox;
        return sb.label_lock ? sb.lock : _t("%s You can still rename it.", sb.lock);
    }
    get ePlaceText() {
        const sb = this.state.stdEdit.row.stdbox;
        if (!sb.removed) { return ""; }
        const tab = sb.tab || _t("Other fields");
        return sb.panel ? _t("When shown again: Full details, %s tab, and the side panel.", tab)
            : _t("When shown again: Full details, %s tab, in its old place. Not on the side panel.", tab);
    }
    eShowAgain() {
        const sb = this.state.stdEdit.row.stdbox;
        if (sb.comeback || !sb.propose) { return; }
        const p = sb.propose;
        this.state.stdEdit.picking = false;
        this.state.stdEdit.show = p.mode === "only" ? showOnly(p.countries, p.unset) : SHOW_ALL;
    }
    get eOff() { const sb = this.state.stdEdit.row.stdbox; return Boolean(sb.removed) && this.state.stdEdit.show.mode === "none"; }
    toggleStdPortal(which) {
        const p = this.state.stdEdit.portal;
        if (which === "show") {
            if (!p.can_show) { return; }
            p.show = !p.show;
            if (!p.show) { p.edit = false; }
        } else {
            if (!p.can_edit) { return; }
            p.edit = !p.edit;
            if (p.edit) { p.show = true; }
        }
    }
    setStdPortalMode(mode) { if (mode === "instant" && this.state.stdEdit.portal.mode_lock) { return; } this.state.stdEdit.portal.mode = mode; }
    stdPortalModeClass(mode) { return { on: this.state.stdEdit.portal.mode === mode }; }
    async saveStdEdit() {
        const e = this.state.stdEdit;
        if (e.picking && e.show.mode !== "only") {
            this.notification.add(_t("Pick at least one Country of Work, or choose All countries."), { type: "warning" });
            return;
        }
        const vals = { std_labels: e.labels };
        // R31 — "Shown for": the built-in setting, or the administrator's
        if (!this.eChanged) { vals.std_show = "builtin"; }
        else if (e.show.mode === "only") {
            Object.assign(vals, { std_show: "only", std_show_country_ids: e.show.countries.map((c) => c.id),
                                  std_show_unset: Boolean(e.show.unset) });
        } else { vals.std_show = e.show.mode; }
        if (e.row.stdbox.label_lock) { delete vals.std_labels; }
        if (e.portal) {
            Object.assign(vals, { portal_show: e.portal.show, portal_edit: e.portal.edit, portal_mode: e.portal.mode });
        }
        this.state.saving = true;
        try {
            await this.orm.call(FACADE, "update_standard", [e.row.model, e.row.name, vals]);
            rpcBus.trigger("CLEAR-CACHES", "get_views");
            this.notification.add(_t("Saved. Everyone sees the change the next time their screen loads."), { type: "success" });
            this.state.stdEdit = null;
            await this.load();
        } catch (err) {
            this.notification.add((err && err.data && err.data.message) || _t("That could not be saved."), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }
    /** One click back to the product's own way (the history keeps the line). */
    async undoStd(r) {
        this.state.saving = true;
        try {
            const vals = { std_labels: {}, std_show: "builtin" };
            if (r.stdbox.label_lock) { delete vals.std_labels; }
            await this.orm.call(FACADE, "update_standard", [r.model, r.name, vals]);
            rpcBus.trigger("CLEAR-CACHES", "get_views");
            this.notification.add(_t("%s is back to how the product shows it.", r.stdbox.builtin), { type: "success" });
            await this.load();
        } catch (err) {
            this.notification.add((err && err.data && err.data.message) || _t("That could not be saved."), { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }
    stdChanged(r) { return Boolean(r.stdbox.changed) || Object.keys(r.stdbox.labels || {}).length > 0; }

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
