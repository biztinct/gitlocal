/** @odoo-module **/
/**
 * FormStudioOverlay — the Form builder itself, laid over a host screen.
 *
 * The look and the interaction are the POC (docs/design/formstudio/
 * FORM_STUDIO_POC.html): a dark studio bar, a palette on the left ("New
 * field" / "Add existing"), the record's sections in the middle with drop
 * zones, a properties panel on the right, and a publish sheet that says in
 * plain words what will change.
 *
 * NOTHING changes for anybody until Publish. Until then the work is a DRAFT
 * kept on the server per administrator (`save_draft`, debounced), so leaving
 * and coming back — or a second device — keeps it. New fields are created by
 * `publish` itself, in the same transaction as the layout.
 *
 * Every refusal comes from the server in screen words; the client only adds
 * the typed confirmation in front of a delete (the server re-checks it).
 */
import { Component, useState, onWillStart, onWillUnmount, useExternalListener } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { fsIc, KIND_ICON } from "./fs_icons";
import { FACADE, toneClass, CHANGE_ICON, isEmptyDisplay } from "./fs_words";

const DRAFT_MS = 800;
const LANG_NAMES = { vi_VN: "Tiếng Việt", id_ID: "Bahasa Indonesia" };

function clone(x) { return JSON.parse(JSON.stringify(x)); }

export class FormStudioOverlay extends Component {
    static template = "pb_form_studio.Overlay";
    static props = {
        hostKey: { type: String },
        recordId: { type: [Number, Boolean], optional: true },
        focusField: { type: String, optional: true },
        onClose: { type: Function },
        onPublished: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true, error: "", data: null,
            sections: [], fields: {}, creates: {}, updates: {}, deletes: {}, changes: [],
            baseVersion: 0, sel: this.props.focusField || null, pal: "new", sheet: null,
            stale: null, draftNote: "", preview: {}, del: null, saving: false,
            over: null, overField: null, countryTerm: "", langsOpen: false, publishing: false,
        });
        this._seq = 1;
        this._timer = null;
        onWillStart(() => this.load());
        onWillUnmount(() => this._timer && clearTimeout(this._timer));
        useExternalListener(window, "keydown", (ev) => {
            if (ev.key === "Escape" && this.state.sheet) { this.state.sheet = null; }
        });
    }

    ic(n, s = 16) { return fsIc(n, s); }

    // ================================================================ load
    async load() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(FACADE, "get_studio", [this.props.hostKey]);
            this.state.data = data;
            this.state.fields = clone(data.fields);
            this.state.sections = clone(data.sections).map((s) => ({ ...s, fields: [...(s.fields || [])] }));
            this.state.baseVersion = data.version;
            this.state.creates = {};
            this.state.updates = {};
            this.state.deletes = {};
            this.state.changes = [];
            if (data.draft && data.draft.payload && (data.draft.payload.changes || []).length) {
                this.applyDraft(data.draft);
            }
            if (this.props.recordId) {
                try {
                    const r = await this.orm.call(FACADE, "render", [this.props.hostKey, this.props.recordId]);
                    const preview = {};
                    for (const s of r.sections) {
                        for (const f of s.fields || []) { preview[f.name] = f.display; }
                    }
                    this.state.preview = preview;
                } catch {
                    this.state.preview = {};
                }
            }
        } catch (e) {
            this.state.error = (e && e.data && e.data.message) || _t("The Form builder could not open.");
        } finally {
            this.state.loading = false;
        }
    }

    applyDraft(draft) {
        const p = draft.payload;
        const byId = Object.fromEntries((p.sections || []).map((s) => [s.id, s.fields || []]));
        for (const s of this.state.sections) {
            if (s.kind === "open" && byId[s.id]) { s.fields = [...byId[s.id]]; }
        }
        this.state.creates = clone(p.creates_map || {});
        for (const [tmp, spec] of Object.entries(this.state.creates)) {
            this.state.fields["new:" + tmp] = this.pendingDesc(tmp, spec);
            this._seq = Math.max(this._seq, Number(tmp) + 1);
        }
        this.state.updates = clone(p.updates || {});
        for (const [name, vals] of Object.entries(this.state.updates)) {
            if (this.state.fields[name]) { this.mergeIntoDesc(this.state.fields[name], vals); }
        }
        this.state.deletes = clone(p.deletes_map || {});
        for (const name of Object.keys(this.state.deletes)) {
            if (this.state.fields[name]) { this.state.fields[name].deleted = true; }
        }
        this.state.changes = clone(p.changes || []);
        this.state.baseVersion = draft.base_version;
        if (draft.stale) {
            this.state.stale = { message: _t("Another administrator published this screen after you started your changes.") };
        } else {
            this.state.draftNote = _t("Your unpublished changes from last time are back.");
        }
    }

    // ============================================================ getters
    get data() { return this.state.data || {}; }
    get hostTitle() { return (this.data.host || {}).title || ""; }
    get types() { return this.data.types || []; }
    get changeCount() { return this.state.changes.length; }
    get changeText() {
        const n = this.changeCount;
        if (!n) { return _t("No changes yet"); }
        return n === 1 ? _t("1 change not yet published") : _t("%s changes not yet published", n);
    }
    get placedNames() {
        return new Set(this.state.sections.flatMap((s) => s.fields || []));
    }
    get hiddenFields() {
        const placed = this.placedNames;
        return Object.values(this.state.fields).filter((f) => !placed.has(f.name) && !f.deleted);
    }
    get openSections() { return this.state.sections.filter((s) => s.kind === "open"); }
    get customSectionId() {
        const want = (this.data.host || {}).custom_section;
        const open = this.openSections;
        return (open.find((s) => s.id === want) || open[open.length - 1] || {}).id;
    }
    get selField() { return this.state.sel ? this.state.fields[this.state.sel] : null; }
    get recordsText() {
        const n = this.data.records || 0;
        return n === 1 ? _t("1 record") : _t("%s records", n.toLocaleString());
    }
    get langs() { return (this.data.langs || []).filter((l) => l !== "en_US"); }
    langName(code) { return LANG_NAMES[code] || code; }
    get busyText() { return this.data.busy || ""; }

    sectionTitle(id) { return (this.state.sections.find((s) => s.id === id) || {}).title || ""; }
    sectionOf(name) { return (this.state.sections.find((s) => (s.fields || []).includes(name)) || {}).id || ""; }
    toneCls(sec) { return "pbfb-tone-" + toneClass(sec.tone); }
    kindIcon(f) { return fsIc(KIND_ICON[f.kind] || "type", 14); }
    typeIcon(t) { return fsIc(t.icon, 16); }
    tilesOf(sec) { return (sec.fields || []).map((n) => this.state.fields[n]).filter((f) => f && !f.deleted); }
    tileClass(f) {
        return { custom: f.custom, locked: f.locked, sel: this.state.sel === f.name,
                 over: this.state.overField === f.name, pending: f.pending };
    }
    cardClass(sec) {
        return { open: sec.kind === "open", lockedzone: sec.kind === "locked", over: this.state.over === sec.id };
    }
    previewOf(f) {
        const v = this.state.preview[f.name];
        return isEmptyDisplay(v) ? "—" : v;
    }
    previewClass(f) { return { money: f.kind === "money", empty: isEmptyDisplay(this.state.preview[f.name]) }; }
    markIcon(f) {
        if (f.locked) { return fsIc("lock", 13); }
        if (f.vis === "hr" || f.vis === "admin") { return fsIc("eyeOff", 13); }
        if ((f.countries || []).length) { return fsIc("globe", 13); }
        return "";
    }
    markTitle(f) {
        if (f.locked) { return f.reason || _t("Locked"); }
        if (f.vis === "hr") { return _t("HR staff and administrators only"); }
        if (f.vis === "admin") { return _t("Administrators only"); }
        if ((f.countries || []).length) { return _t("Only some countries of work"); }
        return "";
    }
    changeIcon(c) { return fsIc(CHANGE_ICON[c.kind] || "settings2", 15); }
    /** An "added" line follows the new field's CURRENT name, type and
     *  section — it is renamed after it is dropped, nearly always. */
    changeWhat(c) {
        const f = c.ref && this.state.fields[c.ref];
        if (c.kind === "added" && f) {
            return _t("%(label)s (%(type)s) in %(section)s", {
                label: f.label, type: f.type_label, section: this.sectionTitle(this.sectionOf(f.name)) || "-" });
        }
        return c.what;
    }
    changeKind(c) {
        return { added: _t("Added"), moved: _t("Moved"), hidden: _t("Hidden"), shown: _t("Shown"),
                 deleted: _t("Deleted"), changed: _t("Changed") }[c.kind] || c.kind;
    }

    // ========================================================== changes
    note(kind, what, ref = null) {
        this.state.changes.push({ kind, what, ref });
        this.scheduleDraft();
    }
    scheduleDraft() {
        clearTimeout(this._timer);
        this._timer = setTimeout(() => this.saveDraft(), DRAFT_MS);
    }
    draftPayload() {
        return {
            sections: this.openSections.map((s) => ({ id: s.id, fields: [...s.fields] })),
            creates_map: this.state.creates, updates: this.state.updates,
            deletes_map: this.state.deletes, changes: this.state.changes,
            base_version: this.state.baseVersion,
        };
    }
    async saveDraft() {
        try {
            await this.orm.call(FACADE, "save_draft", [this.props.hostKey, this.draftPayload()]);
        } catch {
            // A draft that could not be kept is not worth an error over the
            // work itself; Publish still carries everything.
        }
    }

    pendingDesc(tmp, spec) {
        const type = this.types.find((t) => t.key === spec.type) || {};
        return {
            name: "new:" + tmp, label: spec.label, help: spec.help || "", kind: spec.type,
            type_label: type.label || "", custom: true, std: false, pending: true, locked: false,
            vis: spec.vis || "hr", required: Boolean(spec.is_required), list_ok: Boolean(spec.list_ok),
            formula_ok: Boolean(spec.formula_ok),
            formula_possible: ["integer", "number", "money", "bool", "date", "select"].includes(spec.type),
            countries: (spec.country_ids || []).map((id) => this.countryById(id)).filter(Boolean),
            options: (spec.options || []).map((l, i) => ({ value: "", label: l, key: i })),
            comodel: spec.comodel || false, labels: spec.labels || {}, helps: spec.helps || {},
            filled: 0, used_by: [],
        };
    }
    countryById(id) {
        const c = (this.data.countries || []).find((x) => x.id === id);
        return c ? { id: c.id, name: c.name } : null;
    }
    mergeIntoDesc(desc, vals) {
        if ("label" in vals) { desc.label = vals.label; }
        if ("help" in vals) { desc.help = vals.help; }
        if (vals.labels) { desc.labels = { ...(desc.labels || {}), ...vals.labels }; }
        if (vals.helps) { desc.helps = { ...(desc.helps || {}), ...vals.helps }; }
        for (const [k, d] of [["vis", "vis"], ["is_required", "required"], ["list_ok", "list_ok"], ["formula_ok", "formula_ok"]]) {
            if (k in vals) { desc[d] = vals[k]; }
        }
        if (vals.country_ids) { desc.countries = vals.country_ids.map((id) => this.countryById(id)).filter(Boolean); }
        if (vals.options) { desc.options = vals.options.map((o, i) => ({ value: o.value || "", label: o.label, key: i })); }
    }

    defaultLabel(kind) {
        const t = this.types.find((x) => x.key === kind);
        return _t("New %s", (t ? t.label : _t("field")).toLowerCase());
    }

    createPending(kind) {
        if (!this.data.money_ok && kind === "money") {
            this.notification.add(_t("This record type has no money of its own. Use Decimal instead."), { type: "warning" });
            return null;
        }
        const tmp = String(this._seq++);
        const spec = { tmp, type: kind, label: this.defaultLabel(kind), vis: "hr" };
        if (kind === "select") { spec.options = [_t("Option A"), _t("Option B")]; }
        if (kind === "m2o") { spec.comodel = (this.data.comodels || [])[0]?.model || false; }
        this.state.creates[tmp] = spec;
        const desc = this.pendingDesc(tmp, spec);
        this.state.fields[desc.name] = desc;
        return desc.name;
    }

    place(name, secId, beforeName) {
        const sec = this.state.sections.find((s) => s.id === secId);
        if (!sec || sec.kind !== "open") { return false; }
        for (const s of this.state.sections) {
            if (s.fields) { s.fields = s.fields.filter((n) => n !== name); }
        }
        const idx = beforeName ? sec.fields.indexOf(beforeName) : -1;
        if (idx >= 0) { sec.fields.splice(idx, 0, name); } else { sec.fields.push(name); }
        return true;
    }

    dropInto(secId, data, beforeName) {
        if (!data) { return; }
        const [op, arg] = [data.slice(0, data.indexOf(":")), data.slice(data.indexOf(":") + 1)];
        const sec = this.state.sections.find((s) => s.id === secId);
        if (!sec || sec.kind !== "open") { return; }
        if (op === "new") {
            const name = this.createPending(arg);
            if (!name) { return; }
            this.place(name, secId, beforeName);
            const f = this.state.fields[name];
            this.note("added", _t("%(label)s (%(type)s) in %(section)s", { label: f.label, type: f.type_label, section: sec.title }), name);
            this.state.sel = name;
        } else if (op === "existing") {
            if (!this.state.fields[arg]) { return; }
            this.place(arg, secId, beforeName);
            this.note("shown", _t("%(label)s in %(section)s", { label: this.state.fields[arg].label, section: sec.title }));
            this.state.sel = arg;
        } else if (op === "move") {
            const f = this.state.fields[arg];
            if (!f || arg === beforeName) { return; }
            if (f.locked && this.sectionOf(arg) !== secId) {
                this.notification.add(_t("A locked field stays in its own section. You can still change its order there."), { type: "info" });
                return;
            }
            this.place(arg, secId, beforeName);
            if (f.pending) {
                this.scheduleDraft();          // its "added" line already says where
            } else {
                this.note("moved", _t("%(label)s to %(section)s", { label: f.label, section: sec.title }));
            }
            this.state.sel = arg;
        }
    }

    // ---------------------------------------------------------- dragging
    onDragStart(ev, data) { ev.dataTransfer.setData("text/plain", data); ev.dataTransfer.effectAllowed = "move"; }
    onTileDragStart(ev, f) { this.onDragStart(ev, "move:" + f.name); }
    onCardOver(ev, sec) { if (sec.kind === "open") { ev.preventDefault(); this.state.over = sec.id; } }
    onCardLeave(ev, sec) {
        if (!ev.currentTarget.contains(ev.relatedTarget)) {
            if (this.state.over === sec.id) { this.state.over = null; }
        }
    }
    onCardDrop(ev, sec) {
        ev.preventDefault();
        this.state.over = null;
        this.state.overField = null;
        this.dropInto(sec.id, ev.dataTransfer.getData("text/plain"), null);
    }
    onTileOver(ev, f) { ev.preventDefault(); this.state.overField = f.name; }
    onTileLeave(f) { if (this.state.overField === f.name) { this.state.overField = null; } }
    onTileDrop(ev, sec, f) {
        ev.preventDefault();
        ev.stopPropagation();
        this.state.over = null;
        this.state.overField = null;
        this.dropInto(sec.id, ev.dataTransfer.getData("text/plain"), f.name);
    }
    /** Tap / keyboard alternative to dragging (phones, screen readers). */
    addType(kind) {
        this.dropInto(this.customSectionId, "new:" + kind, null);
        this.revealProps();
    }
    /** On a phone the panels stack: bring the new field's settings into view. */
    revealProps() {
        if (window.innerWidth > 1100) { return; }
        setTimeout(() => {
            const el = document.querySelector(".pbfb-overlay .pbfb-right");
            if (el && el.scrollIntoView) { el.scrollIntoView({ behavior: "smooth", block: "start" }); }
        }, 60);
    }
    addExisting(f) { this.dropInto(this.customSectionId, "existing:" + f.name, null); }
    select(f) { this.state.sel = f.name; this.state.del = null; }
    onTileKey(ev, f) {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); this.select(f); }
    }

    // ------------------------------------------------------- properties
    setPal(p) { this.state.pal = p; }
    palClass(p) { return { on: this.state.pal === p }; }
    isPending(f) { return Boolean(f && f.pending); }

    edit(f, key, value, label) {
        if (f.pending) {
            const tmp = f.name.split(":")[1];
            const spec = this.state.creates[tmp];
            if (key === "labels") { spec.labels = { ...(spec.labels || {}), ...value }; }
            else if (key === "helps") { spec.helps = { ...(spec.helps || {}), ...value }; }
            else { spec[key] = value; }
            Object.assign(this.state.fields[f.name], this.pendingDesc(tmp, spec), { name: f.name });
            this.scheduleDraft();
            return;
        }
        const vals = this.state.updates[f.name] || {};
        if (key === "labels" || key === "helps") { vals[key] = { ...(vals[key] || {}), ...value }; }
        else { vals[key] = value; }
        this.state.updates[f.name] = vals;
        this.mergeIntoDesc(f, { [key]: value });
        this.note("changed", _t("%(label)s: %(what)s", { label: f.label, what: label }));
    }
    onLabel(f, ev) {
        const v = ev.target.value.trim();
        if (!v || v === f.label) { ev.target.value = f.label; return; }
        this.edit(f, "label", v, _t("name"));
    }
    onLangLabel(f, lang, ev) { this.edit(f, "labels", { [lang]: ev.target.value.trim() }, _t("name in %s", this.langName(lang))); }
    onHelp(f, ev) { this.edit(f, "help", ev.target.value, _t("help text")); }
    onVis(f, ev) { this.edit(f, "vis", ev.target.value, _t("who can see it")); }
    onType(f, ev) {
        if (!f.pending) { return; }
        const kind = ev.target.value;
        if (kind === "money" && !this.data.money_ok) { return; }
        const tmp = f.name.split(":")[1];
        const spec = this.state.creates[tmp];
        spec.type = kind;
        if (kind === "select" && !spec.options) { spec.options = [_t("Option A"), _t("Option B")]; }
        if (kind === "m2o" && !spec.comodel) { spec.comodel = (this.data.comodels || [])[0]?.model || false; }
        Object.assign(this.state.fields[f.name], this.pendingDesc(tmp, spec), { name: f.name });
        this.scheduleDraft();
    }
    onComodel(f, ev) { if (f.pending) { this.edit(f, "comodel", ev.target.value, ""); } }
    toggle(f, key, descKey, label) {
        if (key === "formula_ok" && !f.formula_possible) { return; }
        this.edit(f, key, !f[descKey], label);
    }
    switchAttr(on) { return on ? "true" : "false"; }
    get requiredWord() { return _t("required"); }
    get listWord() { return _t("show in lists"); }
    get formulaWord() { return _t("use in pay formulas"); }
    get visOptions() {
        return [
            { value: "all", label: _t("Everyone, including the employee") },
            { value: "hr", label: _t("HR staff and administrators") },
            { value: "admin", label: _t("Administrators only") },
        ];
    }
    // options (choice list)
    optionsOf(f) { return f.options || []; }
    optionsPayload(f, list) {
        return list.map((o) => (f.pending ? o.label : { value: o.value, label: o.label }));
    }
    setOptions(f, list) {
        if (f.pending) { this.edit(f, "options", list.map((o) => o.label), ""); return; }
        this.edit(f, "options", list.map((o) => ({ value: o.value, label: o.label })), _t("choices"));
    }
    onOption(f, i, ev) {
        const list = this.optionsOf(f).map((o) => ({ ...o }));
        list[i].label = ev.target.value.trim() || list[i].label;
        this.setOptions(f, list);
    }
    addOption(f) {
        const list = this.optionsOf(f).map((o) => ({ ...o }));
        list.push({ value: "", label: _t("Option %s", list.length + 1) });
        this.setOptions(f, list);
    }
    removeOption(f, i) {
        const list = this.optionsOf(f).map((o) => ({ ...o }));
        if (list.length <= 1) { return; }
        list.splice(i, 1);
        this.setOptions(f, list);
    }
    // countries (R10)
    allCountries(f) { return !(f.countries || []).length; }
    get countryOk() { return Boolean(this.data.country_ok); }
    setAllCountries(f) { if (!this.allCountries(f)) { this.edit(f, "country_ids", [], _t("countries")); } }
    onCountryTerm(ev) { this.state.countryTerm = ev.target.value; }
    countryMatches(f) {
        const t = (this.state.countryTerm || "").toLowerCase().trim();
        if (!t) { return []; }
        const chosen = new Set((f.countries || []).map((c) => c.id));
        const rank = (c) => (c.name.toLowerCase().startsWith(t) || (c.code || "").toLowerCase() === t ? 0 : 1);
        return (this.data.countries || []).filter((c) => !chosen.has(c.id)
            && (c.name.toLowerCase().includes(t) || (c.code || "").toLowerCase() === t))
            .sort((a, b) => rank(a) - rank(b)).slice(0, 6);
    }
    addCountry(f, c) {
        const ids = [...(f.countries || []).map((x) => x.id), c.id];
        this.state.countryTerm = "";
        this.edit(f, "country_ids", ids, _t("countries"));
    }
    removeCountry(f, c) {
        const ids = (f.countries || []).map((x) => x.id).filter((id) => id !== c.id);
        this.edit(f, "country_ids", ids, _t("countries"));
    }
    toggleLangs() { this.state.langsOpen = !this.state.langsOpen; }
    langValue(f, lang) { return (f.labels || {})[lang] || ""; }
    // where it appears / used by
    whereChips(f) {
        return [
            { label: _t("This screen"), on: this.placedNames.has(f.name) },
            { label: _t("Lists"), on: Boolean(f.list_ok) },
            { label: _t("Pay formulas"), on: Boolean(f.formula_ok) },
            { label: _t("Self-service"), on: f.vis === "all" },
        ];
    }
    chipClass(c) { return { on: c.on }; }
    chipIcon(c) { return fsIc(c.on ? "check" : "minus", 12); }
    usedBy(f) { return f.used_by || []; }
    filledText(f) {
        return _t("Filled on %(n)s of %(total)s records.", { n: (f.filled || 0).toLocaleString(), total: (this.data.records || 0).toLocaleString() });
    }
    sectionChoices() { return this.openSections; }
    onMoveTo(f, ev) {
        const target = ev.target.value;
        if (target === "__hide") { this.hide(f); return; }
        this.dropInto(target, (this.placedNames.has(f.name) ? "move:" : "existing:") + f.name, null);
    }
    isSelectedSection(f, sec) { return this.sectionOf(f.name) === sec.id; }
    hide(f) {
        if (f.locked) { return; }
        for (const s of this.state.sections) { if (s.fields) { s.fields = s.fields.filter((n) => n !== f.name); } }
        this.note("hidden", f.label);
        this.state.sel = null;
        this.notification.add(_t("%s is hidden. Find it again under \"Add existing\".", f.label), { type: "info" });
    }

    // ------------------------------------------------------------ delete
    askDelete(f) { this.state.del = { name: f.name, typed: "" }; }
    cancelDelete() { this.state.del = null; }
    onDelTyped(ev) { if (this.state.del) { this.state.del.typed = ev.target.value; } }
    get delReady() {
        const f = this.selField;
        return Boolean(f && this.state.del && this.state.del.typed.trim().toLowerCase() === f.label.trim().toLowerCase());
    }
    deleteWarn(f) {
        return _t("This deletes the field and every value in it (%s filled in). A copy of the values is kept in the Form builder history.", (f.filled || 0).toLocaleString());
    }
    typeToConfirm(f) { return _t("Type %s to confirm.", f.label); }
    doDelete(f) {
        if (!this.delReady) { return; }
        if (f.pending) {
            delete this.state.creates[f.name.split(":")[1]];
            this.state.changes = this.state.changes.filter((c) => c.ref !== f.name);
        } else {
            this.state.deletes[f.name] = this.state.del.typed;
            this.note("deleted", f.label);
        }
        for (const s of this.state.sections) { if (s.fields) { s.fields = s.fields.filter((n) => n !== f.name); } }
        f.deleted = true;
        if (f.pending) { delete this.state.fields[f.name]; }
        this.state.sel = null;
        this.state.del = null;
        this.scheduleDraft();
    }

    // ----------------------------------------------------------- publish
    openPublish() { if (this.changeCount) { this.state.sheet = "publish"; } }
    closeSheet() { this.state.sheet = null; }
    get publishSub() {
        const added = Object.keys(this.state.creates).length;
        const base = _t("Everyone in this company sees the new layout the next time the screen loads.");
        return added ? base + " " + _t("New fields are added to every record of this kind (%s), empty until filled.", this.recordsText) : base;
    }
    publishPayload(overwrite) {
        const sections = this.openSections.map((s) => ({ id: s.id, fields: [...s.fields] }));
        const creates = Object.values(this.state.creates).map((spec) => ({ ...spec }));
        return {
            sections, creates, updates: this.state.updates,
            deletes: Object.entries(this.state.deletes).map(([name, confirm]) => ({ name, confirm })),
            base_version: this.state.baseVersion, overwrite: Boolean(overwrite),
            changes: this.state.changes.map((c) => this.changeKind(c) + ": " + this.changeWhat(c)),
        };
    }
    async publish(overwrite = false) {
        if (this.state.publishing) { return; }
        this.state.publishing = true;
        try {
            const res = await this.orm.call(FACADE, "publish", [this.props.hostKey, this.publishPayload(overwrite)]);
            if (res && res.stale) {
                this.state.stale = res;
                this.state.sheet = "stale";
                return;
            }
            const n = this.changeCount;
            clearTimeout(this._timer);
            this.notification.add(n === 1 ? _t("Published. 1 change is now live for everyone.")
                : _t("Published. %s changes are now live for everyone.", n), { type: "success" });
            this.state.sheet = null;
            if (this.props.onPublished) { await this.props.onPublished(res); }
            this.props.onClose();
        } catch (e) {
            this.state.sheet = null;
            this.notification.add((e && e.data && e.data.message) || _t("Publishing did not work. Nothing was changed."), { type: "danger", sticky: true });
        } finally {
            this.state.publishing = false;
        }
    }
    async startAgain() {
        clearTimeout(this._timer);
        await this.orm.call(FACADE, "discard_draft", [this.props.hostKey]);
        this.state.sheet = null;
        this.state.stale = null;
        this.state.draftNote = "";
        this.state.sel = null;
        await this.load();
    }
    async discard() {
        await this.startAgain();
        this.notification.add(_t("Changes discarded. Nothing was published."), { type: "info" });
    }
    requestClose() {
        if (this.changeCount) { this.state.sheet = "leave"; return; }
        this.props.onClose();
    }
    async leaveKeepDraft() {
        clearTimeout(this._timer);
        await this.saveDraft();
        this.state.sheet = null;
        this.props.onClose();
    }
    dismissNote() { this.state.draftNote = ""; }
}
