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
import { Component, useState, useRef, onMounted, onWillStart, onWillUnmount, useExternalListener } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { rpcBus } from "@web/core/network/rpc";
import { fsIc, KIND_ICON } from "./fs_icons";
import { FACADE, toneClass, CHANGE_ICON, isEmptyDisplay, fold, foldMatch, KIND_GROUP, isSlashKey, sameLabels } from "./fs_words";

const DRAFT_MS = 800;
const LANG_NAMES = { en_US: "English", vi_VN: "Tiếng Việt", id_ID: "Bahasa Indonesia" };
/** R23 — a standard field's screen rule travels in these keys. */
const STD_KEYS = ["std_hidden", "std_country_ids", "std_labels"];
/** FS-10 — the one-column layout (phone, tablet): the same breakpoint as
 * the stylesheet's `@media (max-width: 1100px)`. There the field's settings
 * are a sheet at the bottom and the studio bar stays at the top. */
function isOneColumn() {
    return Boolean(window.matchMedia && window.matchMedia("(max-width: 1100px)").matches);
}

function clone(x) { return JSON.parse(JSON.stringify(x)); }

export class FormStudioOverlay extends Component {
    static template = "pb_form_studio.Overlay";
    static props = {
        hostKey: { type: String },
        recordId: { type: [Number, Boolean], optional: true },
        focusField: { type: String, optional: true },
        // FS-11: "full" when opened from a full page (its tabs are the
        // fixed sections); the side panels leave it out.
        surface: { type: String, optional: true },
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
            // R24 — the filters of the left column (client-side only)
            exTerm: "", exType: "all", stdTerm: "", stdChip: "all", stdCountry: 0,
            // R23 — "Hidden in some countries" picked, no country chosen yet
            someOpen: null,
            // FS-11 (R29) — fixed sections list their fields; the canvas search
            findTerm: "", findAt: 0, collapsed: {},
        });
        this.canvas = useRef("canvas");
        this.exSearch = useRef("exSearch");
        this.stdSearch = useRef("stdSearch");
        this.propPanel = useRef("propPanel");
        this.studioBar = useRef("studioBar");
        this._seq = 1;
        this._timer = null;
        onWillStart(() => this.load());
        onWillUnmount(() => this._timer && clearTimeout(this._timer));
        // FS-10 — on a phone the studio bar stays at the top; the sticky
        // filter of the left column sits just under it, whatever its height.
        onMounted(() => {
            const bar = this.studioBar.el;
            if (!bar || !window.ResizeObserver) { return; }
            this._barObs = new ResizeObserver(() => {
                const root = bar.parentElement;
                if (root) { root.style.setProperty("--pbfb-bar-h", bar.offsetHeight + "px"); }
            });
            this._barObs.observe(bar);
        });
        onWillUnmount(() => this._barObs && this._barObs.disconnect());
        useExternalListener(window, "keydown", (ev) => {
            if (ev.key === "Escape" && this.state.sheet) { this.state.sheet = null; return; }
            // R24 — "/" jumps to the search of the list on the left.
            if (isSlashKey(ev) && !this.state.sheet) {
                const ref = this.state.pal === "std" ? this.stdSearch
                    : (this.state.pal === "existing" ? this.exSearch : null);
                if (ref && ref.el) { ev.preventDefault(); ref.el.focus(); ref.el.select(); }
            }
        });
    }

    ic(n, s = 16) { return fsIc(n, s); }

    // ================================================================ load
    async load() {
        this.state.loading = true;
        try {
            // FS-11: opened from a full page, the canvas shows that page's tabs.
            const context = this.props.surface ? { pbfs_surface: this.props.surface } : {};
            const data = await this.orm.call(FACADE, "get_studio", [this.props.hostKey], { context });
            this.state.data = data;
            // Fixed sections: open on a desktop, folded on a phone (R29).
            const fold = isOneColumn();
            this.state.collapsed = Object.fromEntries((data.sections || [])
                .filter((s) => s.kind !== "open").map((s) => [s.id, fold]));
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
    /** Fields that can be placed on this screen but are not, A to Z. A
     *  standard field listed only for its screen rule (R23) is not
     *  placeable and never shows here. */
    get hiddenFields() {
        const placed = this.placedNames;
        return Object.values(this.state.fields)
            .filter((f) => !placed.has(f.name) && !f.deleted && f.placeable !== false)
            .sort((a, b) => String(a.label).localeCompare(String(b.label), undefined, { sensitivity: "base" }));
    }

    // --------------------------------------------- R24: "Add existing" filter
    get typeChips() {
        return [
            { key: "all", label: _t("All") }, { key: "text", label: _t("Text") },
            { key: "number", label: _t("Number") }, { key: "date", label: _t("Date") },
            { key: "choice", label: _t("Choice") }, { key: "bool", label: _t("Yes / No") },
            { key: "link", label: _t("Link") },
        ];
    }
    typeChipClass(c) { return { on: this.state.exType === c.key }; }
    setExType(key) { this.state.exType = key; }
    get exFields() {
        const type = this.state.exType;
        return this.hiddenFields.filter((f) => (type === "all" || KIND_GROUP[f.kind] === type)
            && foldMatch(this.state.exTerm, f.label));
    }
    get exFiltered() { return Boolean(fold(this.state.exTerm)) || this.state.exType !== "all"; }
    get exCountText() {
        const n = this.exFields.length;
        const total = this.hiddenFields.length;
        if (this.exFiltered) { return _t("%(n)s of %(total)s", { n, total }); }
        return total === 1 ? _t("1 field") : _t("%s fields", total);
    }
    onExTerm(ev) { this.state.exTerm = ev.target.value; }
    clearEx() {
        this.state.exTerm = "";
        this.state.exType = "all";
        if (this.exSearch.el) { this.exSearch.el.focus(); }
    }
    /** Esc in a search box clears it and stays in the Form builder. */
    onFindKey(which, ev) {
        if (ev.key !== "Escape") { return; }
        ev.preventDefault();
        ev.stopPropagation();
        if (which === "ex") { this.state.exTerm = ""; } else { this.state.stdTerm = ""; }
    }

    // --------------------------------------------- R23: "Standard fields" tab
    get userLang() { return this.data.lang || "en_US"; }
    get portalHost() { return Boolean((this.data.host || {}).portal); }
    get stdAll() {
        // A field with no screen rule of its own (only its My Payobook ticks)
        // goes last, under "Other fields".
        const order = (f) => (f.stdbox ? f.stdbox.order || 0 : 1e6);
        const seq = (f) => (f.stdbox ? f.stdbox.seq || 0 : 0);
        return Object.values(this.state.fields || {})
            .filter((f) => !f.custom && !f.deleted && (f.stdbox || f.portal))
            .sort((a, b) => order(a) - order(b) || seq(a) - seq(b)
                || String(this.stdLabel(a)).localeCompare(String(this.stdLabel(b))));
    }
    /** The label a person sees on screen: own label, else the built-in one. */
    stdLabel(f) {
        const s = f.stdbox;
        if (!s) { return f.label; }
        return (s.labels || {})[this.userLang] || s.builtin || f.label;
    }
    get hasStd() { return this.stdAll.length > 0; }
    get stdChips() {
        const out = [{ key: "all", label: _t("All") }, { key: "hidden", label: _t("Hidden") },
                     { key: "renamed", label: _t("Renamed") }];
        if (this.portalHost) { out.push({ key: "portal", label: _t("On My Payobook") }); }
        return out;
    }
    stdChipClass(c) { return { on: this.state.stdChip === c.key }; }
    setStdChip(key) { this.state.stdChip = key; }
    stdIsHidden(f) { const s = f.stdbox; return Boolean(s && (s.hidden || (s.countries || []).length)); }
    stdIsRenamed(f) { return Boolean(f.stdbox && Object.keys(f.stdbox.labels || {}).length); }
    /** Does the field show for people of this Country of Work? */
    stdApplies(f, countryId) {
        const s = f.stdbox;
        if (!s || !countryId) { return true; }
        if (s.hidden && !s.lock) { return false; }
        if (!s.lock && (s.countries || []).some((c) => c.id === countryId)) { return false; }
        if (s.rule && s.rule.country_id && s.rule.country_id !== countryId) { return false; }
        return true;
    }
    get stdFields() {
        const chip = this.state.stdChip;
        const cid = Number(this.state.stdCountry) || 0;
        return this.stdAll.filter((f) => {
            if (chip === "hidden" && !this.stdIsHidden(f)) { return false; }
            if (chip === "renamed" && !this.stdIsRenamed(f)) { return false; }
            if (chip === "portal" && !(f.portal && f.portal.show)) { return false; }
            if (cid && !this.stdApplies(f, cid)) { return false; }
            return foldMatch(this.state.stdTerm, this.stdLabel(f), (f.stdbox || {}).builtin, f.label);
        });
    }
    get stdGroups() {
        const out = [];
        for (const f of this.stdFields) {
            const tab = (f.stdbox && f.stdbox.tab) || _t("Other fields");
            let g = out[out.length - 1];
            if (!g || g.tab !== tab) { g = { tab, items: [] }; out.push(g); }
            g.items.push(f);
        }
        return out;
    }
    get stdFiltered() {
        return Boolean(fold(this.state.stdTerm)) || this.state.stdChip !== "all" || Boolean(Number(this.state.stdCountry));
    }
    get stdCountText() {
        const n = this.stdFields.length;
        const total = this.stdAll.length;
        if (this.stdFiltered) { return _t("%(n)s of %(total)s", { n, total }); }
        return total === 1 ? _t("1 field") : _t("%s fields", total);
    }
    get countryOptions() {
        return [...(this.data.countries || [])].sort((a, b) => a.name.localeCompare(b.name));
    }
    onStdTerm(ev) { this.state.stdTerm = ev.target.value; }
    onStdCountry(ev) { this.state.stdCountry = Number(ev.target.value) || 0; }
    clearStd() {
        this.state.stdTerm = "";
        this.state.stdChip = "all";
        this.state.stdCountry = 0;
        if (this.stdSearch.el) { this.stdSearch.el.focus(); }
    }
    isSelectedCountry(c) { return Number(this.state.stdCountry) === c.id; }
    /** FS-13: labels two different fields of the list share (folded). */
    get stdSameLabels() { return sameLabels(this.stdAll, (f) => this.stdLabel(f)); }
    stdState(f, same) {
        const s = f.stdbox || {};
        const parts = [];
        // two fields with one label: the field code tells them apart
        if (same && same.has(fold(this.stdLabel(f)))) { parts.push(_t("Field code: %s", f.name)); }
        if (s.ignored) { parts.push(_t("Locked now, shown again")); }
        else if (s.hidden) { parts.push(_t("Hidden for everyone")); }
        else if ((s.countries || []).length) { parts.push(_t("Hidden in %s", s.countries.map((c) => c.name).join(", "))); }
        if (this.stdIsRenamed(f)) {
            parts.push(this.stdLabel(f) !== s.builtin ? _t("Built-in label: %s", s.builtin) : _t("Own label"));
        }
        if (s.rule) { parts.push(_t("Only where Country of Work is %s", s.rule.country)); }
        const p = f.portal || {};
        if (p.show) {
            parts.push(!p.edit ? _t("On My Payobook")
                : (p.mode === "instant" ? _t("My Payobook, saves at once") : _t("My Payobook, HR approves")));
        }
        return parts.join(" · ");
    }
    stdItemClass(f) {
        const s = f.stdbox || {};
        return { hid: this.stdIsHidden(f) && !s.ignored, sel: this.state.sel === f.name,
                 on: Boolean(f.portal && f.portal.show), renamed: this.stdIsRenamed(f) };
    }
    stdIcon(f) {
        const s = f.stdbox || {};
        if (this.stdIsHidden(f) && !s.ignored) { return this.ic("eyeOff", 15); }
        if (s.lock) { return this.ic("lock", 15); }
        if (f.portal && f.portal.show) { return this.ic("smartphone", 15); }
        if (this.stdIsRenamed(f)) { return this.ic("pencil", 15); }
        return this.ic("eye", 15);
    }
    // properties panel of a standard field
    isStd(f) { return Boolean(f && !f.custom && f.stdbox); }
    get allLangs() { return this.data.langs || ["en_US"]; }
    stdMode(f) {
        const s = f.stdbox || {};
        if (s.hidden) { return "all"; }
        if ((s.countries || []).length || this.state.someOpen === f.name) { return "some"; }
        return "shown";
    }
    stdModeClass(f, mode) { return { on: this.stdMode(f) === mode }; }
    setStdMode(f, mode) {
        const s = f.stdbox;
        if (!s || (mode !== "shown" && s.lock)) { return; }
        if (mode === "shown") {
            this.state.someOpen = null;
            if (s.hidden || (s.countries || []).length) {
                this.editStd(f, { std_hidden: false, std_country_ids: [] }, _t("shown"));
            }
        } else if (mode === "all") {
            this.state.someOpen = null;
            if (!s.hidden) { this.editStd(f, { std_hidden: true, std_country_ids: [] }, _t("hidden for everyone")); }
        } else {
            this.state.someOpen = f.name;
            if (s.hidden) { this.editStd(f, { std_hidden: false, std_country_ids: [] }, _t("hidden in some countries")); }
        }
    }
    stdCountryMatches(f) {
        const t = fold(this.state.countryTerm);
        if (!t) { return []; }
        const chosen = new Set(((f.stdbox || {}).countries || []).map((c) => c.id));
        const rank = (c) => (fold(c.name).startsWith(t) || fold(c.code) === t ? 0 : 1);
        return (this.data.countries || []).filter((c) => !chosen.has(c.id)
            && (fold(c.name).includes(t) || fold(c.code) === t))
            .sort((a, b) => rank(a) - rank(b)).slice(0, 6);
    }
    /** "Not used in <country>": the product already hides it there (rule 6). */
    stdNotUsed(f, c) {
        const r = (f.stdbox || {}).rule;
        return Boolean(r && r.country_id && r.country_id !== c.id);
    }
    stdMatchLabel(f, c) { return this.stdNotUsed(f, c) ? _t("%s (not used there)", c.name) : c.name; }
    addStdCountry(f, c) {
        if ((f.stdbox || {}).lock) { return; }
        const ids = [...((f.stdbox || {}).countries || []).map((x) => x.id), c.id];
        this.state.countryTerm = "";
        this.editStd(f, { std_hidden: false, std_country_ids: ids }, _t("hidden in some countries"));
    }
    removeStdCountry(f, c) {
        const ids = ((f.stdbox || {}).countries || []).map((x) => x.id).filter((id) => id !== c.id);
        this.editStd(f, { std_hidden: false, std_country_ids: ids }, _t("hidden in some countries"));
    }
    ruleText(f) {
        const r = (f.stdbox || {}).rule;
        return r ? _t("Shown only where Country of Work is %s: not used in other countries. That rule comes with the product and cannot be changed here.", r.country) : "";
    }
    stdLabelValue(f, lang) { return ((f.stdbox || {}).labels || {})[lang] || ""; }
    stdBuiltin(f, lang) { return ((f.stdbox || {}).builtins || {})[lang] || (f.stdbox || {}).builtin || ""; }
    onStdLabel(f, lang, ev) {
        const s = f.stdbox;
        if (!s || s.label_lock) { return; }
        const v = ev.target.value.trim();
        const labels = { ...(s.labels || {}) };
        if (v && v !== this.stdBuiltin(f, lang)) { labels[lang] = v; } else { delete labels[lang]; ev.target.value = ""; }
        if (JSON.stringify(labels) === JSON.stringify(s.labels || {})) { return; }
        this.editStd(f, { std_labels: labels }, _t("label"));
    }
    resetStdLabel(f) { this.editStd(f, { std_labels: {} }, _t("built-in label put back")); }
    /** One change line per field and per kind of change, however many clicks. */
    editStd(f, vals, what) {
        this.state.updates[f.name] = { ...(this.state.updates[f.name] || {}), ...vals };
        const was = this.stdLabel(f);
        this.mergeIntoDesc(f, vals);
        const key = String(what);
        this.state.changes = this.state.changes.filter((c) => !(c.ref === f.name && c.std === key));
        this.state.changes.push({ kind: "changed", what: _t("%(label)s: %(what)s", { label: was, what }), ref: f.name, std: key });
        this.scheduleDraft();
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
                 over: this.state.overField === f.name, pending: f.pending,
                 found: this.isFound(f.label) };
    }
    cardClass(sec) {
        return { open: sec.kind === "open", lockedzone: sec.kind === "locked", over: this.state.over === sec.id };
    }
    // ------------------------------------------- FS-11 (R29): fixed sections
    /** The fields a fixed section really shows, by sub-heading. */
    fixedGroups(sec) {
        const items = ((this.data.fixed || {})[sec.id]) || [];
        const out = [];
        for (const it of items) {
            let g = out[out.length - 1];
            if (!g || g.group !== it.group) { g = { group: it.group, items: [] }; out.push(g); }
            g.items.push(it);
        }
        return out;
    }
    /** FS-13: in one fixed section, the labels two different fields share. */
    fixedSameLabels(sec) {
        const items = (((this.data.fixed || {})[sec.id]) || []).filter((it) => this.fixedField(it));
        return sameLabels(items.map((it) => ({ name: it.ref, it })), (x) => this.fixedLabel(x.it));
    }
    fixedCode(it, same) {
        const f = this.fixedField(it);
        return f && same && same.has(fold(this.fixedLabel(it))) ? _t("Field code: %s", f.name) : "";
    }
    fixedCount(sec) { return (((this.data.fixed || {})[sec.id]) || []).length; }
    fixedCountText(sec) {
        const n = this.fixedCount(sec);
        return n === 1 ? _t("1 field") : _t("%s fields", n);
    }
    fixedField(it) { return it.ref ? this.state.fields[it.ref] : null; }
    fixedLabel(it) {
        const f = this.fixedField(it);
        // A renamed box shows its own label, as every screen does (R23).
        return f && this.stdIsRenamed(f) ? this.stdLabel(f) : it.label;
    }
    fixedIcon(it) {
        const f = this.fixedField(it);
        return fsIc(f ? (KIND_ICON[f.kind] || "type") : "sigma", 14);
    }
    countryName(code) {
        const c = (this.data.countries || []).find((x) => x.code === code);
        return c ? c.name : code;
    }
    /** Small state chips: hidden, renamed, country, My Payobook, locked. */
    fixedChips(it) {
        const out = [];
        const f = this.fixedField(it);
        const s = (f && f.stdbox) || {};
        if (it.country) { out.push({ k: "cty", text: _t("Only %s", this.countryName(it.country)), icon: "globe" }); }
        else if (s.rule && s.rule.country) { out.push({ k: "cty", text: _t("Only %s", s.rule.country), icon: "globe" }); }
        if (!f) {
            out.push({ k: "auto", text: _t("Worked out by the screen"), icon: "sigma" });
            return out;
        }
        if (s.hidden && !s.ignored) { out.push({ k: "hid", text: _t("Hidden"), icon: "eyeOff" }); }
        else if ((s.countries || []).length && !s.ignored) {
            out.push({ k: "hid", text: _t("Hidden for %s", s.countries.map((c) => c.name).join(", ")), icon: "eyeOff" });
        }
        if (this.stdIsRenamed(f)) { out.push({ k: "ren", text: _t("Renamed"), icon: "pencil" }); }
        if (f.portal && f.portal.show) { out.push({ k: "portal", text: _t("On My Payobook"), icon: "smartphone" }); }
        // the reason in full on hover and in the settings column
        if (s.lock) { out.push({ k: "lock", text: _t("Locked"), title: _t("Locked: %s", s.lock), icon: "lock" }); }
        return out;
    }
    fixedChipClass(c) { return "pbfb-fx-chip " + c.k; }
    fixedItemClass(it) {
        const f = this.fixedField(it);
        const s = (f && f.stdbox) || {};
        return { auto: !f, sel: Boolean(f) && this.state.sel === f.name,
                 hid: Boolean(f) && (s.hidden || (s.countries || []).length) && !s.ignored,
                 found: this.isFound(this.fixedLabel(it), it.label) };
    }
    onFixedClick(it) {
        const f = this.fixedField(it);
        if (f) { this.select(f); }
    }
    isCollapsed(sec) { return Boolean(this.state.collapsed[sec.id]); }
    toggleFixed(sec) { this.state.collapsed[sec.id] = !this.state.collapsed[sec.id]; }
    get zoneText() { return _t("Fixed layout — fields can be hidden or renamed"); }

    // ------------------------------------- FS-11: "Find a field on this screen"
    isFound(...labels) {
        const t = fold(this.state.findTerm);
        return Boolean(t) && labels.some((l) => fold(l).includes(t));
    }
    get findHits() {
        if (!fold(this.state.findTerm)) { return []; }
        const out = [];
        for (const sec of this.state.sections) {
            if (sec.kind === "open") {
                for (const f of this.tilesOf(sec)) { if (this.isFound(f.label)) { out.push({ sec: sec.id, key: "t:" + f.name }); } }
            } else {
                for (const it of ((this.data.fixed || {})[sec.id]) || []) {
                    if (this.isFound(this.fixedLabel(it), it.label)) { out.push({ sec: sec.id, key: "x:" + sec.id + ":" + it.key }); }
                }
            }
        }
        return out;
    }
    get findText() {
        const n = this.findHits.length;
        if (!fold(this.state.findTerm)) { return ""; }
        if (!n) { return _t("No field matches"); }
        return n === 1 ? _t("1 match") : _t("%(at)s of %(n)s", { at: (this.state.findAt % n) + 1, n });
    }
    onFindTerm(ev) {
        this.state.findTerm = ev.target.value;
        this.state.findAt = 0;
        this.revealFind();
    }
    onFindKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.state.findAt = this.state.findAt + (ev.shiftKey ? -1 : 1) + this.findHits.length;
            this.revealFind();
        } else if (ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();
            this.clearFind();
        }
    }
    clearFind() { this.state.findTerm = ""; this.state.findAt = 0; }
    /** Unfold the section of the current match and bring it into view. */
    revealFind() {
        const hits = this.findHits;
        if (!hits.length) { return; }
        const hit = hits[this.state.findAt % hits.length];
        if (this.state.collapsed[hit.sec]) { this.state.collapsed[hit.sec] = false; }
        setTimeout(() => {
            const root = this.canvas.el;
            const el = root && root.querySelector(`[data-fs-key="${CSS.escape(hit.key)}"]`);
            if (!el) { return; }
            for (const x of root.querySelectorAll(".pbfb-current")) { x.classList.remove("pbfb-current"); }
            el.classList.add("pbfb-current");
            el.scrollIntoView({ block: "center", behavior: "smooth" });
        }, 0);
    }
    tileKey(f) { return "t:" + f.name; }
    fixedKey(sec, it) { return "x:" + sec.id + ":" + it.key; }

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
            filled: 0, used_by: [], portal: this.pendingPortal(spec),
        };
    }
    countryById(id) {
        const c = (this.data.countries || []).find((x) => x.id === id);
        return c ? { id: c.id, name: c.name, code: c.code } : null;
    }
    /** R14 rules for a field that does not exist yet (the server decides for
     *  existing ones, and re-checks everything on Publish). */
    pendingPortal(spec) {
        if (!(this.data.host || {}).portal) { return null; }
        const editable = ["text", "longtext", "integer", "number", "date", "select", "bool", "m2o"].includes(spec.type);
        return {
            show: Boolean(spec.portal_show), edit: Boolean(spec.portal_edit), mode: spec.portal_mode || "approve",
            can_show: true, show_reason: "", can_edit: editable,
            edit_reason: editable ? "" : _t("Money and files can be shown, not changed by the employee."),
        };
    }
    mergeIntoDesc(desc, vals) {
        if (desc.stdbox && STD_KEYS.some((k) => k in vals)) {
            const s = { ...desc.stdbox };
            if ("std_hidden" in vals) { s.hidden = Boolean(vals.std_hidden); }
            if ("std_country_ids" in vals) {
                s.countries = (vals.std_country_ids || []).map((id) => this.countryById(id)).filter(Boolean);
            }
            if (s.hidden) { s.countries = []; }
            if (!s.hidden && !(s.countries || []).length) { s.ignored = false; }
            if ("std_labels" in vals) { s.labels = { ...(vals.std_labels || {}) }; }
            desc.stdbox = s;
            // own label, else the label this list always used for the field
            desc.label = (s.labels || {})[this.userLang]
                || (desc.placeable !== false && desc.field_label) || s.builtin || desc.label;
        }
        if (desc.portal && ["portal_show", "portal_edit", "portal_mode"].some((k) => k in vals)) {
            const p = { ...desc.portal };
            if ("portal_show" in vals) { p.show = vals.portal_show; }
            if ("portal_edit" in vals) { p.edit = vals.portal_edit; }
            if ("portal_mode" in vals) { p.mode = vals.portal_mode; }
            if (p.edit) { p.show = true; }
            if (!p.show) { p.edit = false; }
            desc.portal = p;
        }
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
    /** FS-10 — on a phone or tablet the field's settings are a sheet at the
     * bottom of the screen (stylesheet, `.pbfb-right.has-sel`): it opens in
     * view by itself; start it at its top for every newly picked field. */
    revealProps() {
        if (!isOneColumn()) { return; }
        setTimeout(() => {
            const el = this.propPanel.el;
            if (el) { el.scrollTop = 0; }
        }, 0);
    }
    addExisting(f) {
        this.dropInto(this.customSectionId, "existing:" + f.name, null);
        this.revealProps();
    }
    select(f) {
        const changed = this.state.sel !== f.name;
        this.state.sel = f.name;
        this.state.del = null;
        if (changed) { this.revealProps(); }
    }
    /** FS-10 — "Done" on the settings sheet (phone): back to the screen. */
    deselect() { this.state.sel = null; this.state.del = null; }
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
    // ------------------------------------------------- My Payobook (R14)
    portalOn(f) { return Boolean(f && f.portal); }
    portalShowHelp(f) {
        const p = f.portal;
        return p.can_show ? _t("Shown on the employee's own My Payobook page, even when only HR can see it here.") : p.show_reason;
    }
    portalEditHelp(f) {
        const p = f.portal;
        return p.can_edit ? _t("The employee can change it on My Payobook.") : p.edit_reason;
    }
    togglePortal(f, which) {
        const p = f.portal;
        if (which === "show") {
            if (!p.can_show) { return; }
            const on = !p.show;
            this.editPortal(f, on ? { portal_show: true } : { portal_show: false, portal_edit: false });
        } else {
            if (!p.can_edit) { return; }
            const on = !p.edit;
            this.editPortal(f, on ? { portal_show: true, portal_edit: true } : { portal_edit: false });
        }
    }
    /** Several ticks, one change line. */
    editPortal(f, vals) {
        if (f.pending) {
            const tmp = f.name.split(":")[1];
            Object.assign(this.state.creates[tmp], vals);
            Object.assign(this.state.fields[f.name], this.pendingDesc(tmp, this.state.creates[tmp]), { name: f.name });
            this.scheduleDraft();
            return;
        }
        this.state.updates[f.name] = { ...(this.state.updates[f.name] || {}), ...vals };
        this.mergeIntoDesc(f, vals);
        const what = _t("%(label)s: %(what)s", { label: f.label, what: _t("My Payobook") });
        // one line per field however many ticks were touched
        if (this.state.changes.some((c) => c.kind === "changed" && c.ref === f.name && c.what === what)) {
            this.scheduleDraft();
        } else {
            this.note("changed", what, f.name);
        }
    }
    setPortalMode(f, mode) {
        if (mode === "instant" && f.portal.mode_lock) { return; }      // R26: HR always approves
        if (f.portal.mode !== mode) { this.editPortal(f, { portal_mode: mode }); }
    }
    modeClass(f, mode) { return { on: f.portal.mode === mode }; }
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
            { label: _t("My Payobook"), on: Boolean(f.portal && f.portal.show) },
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
        const base = _t("Everyone, in every company, sees the new layout the next time the screen loads.");
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
            // R23: this browser reads the screen designs again (other people's
            // follow through the bus, form_studio_service.js).
            rpcBus.trigger("CLEAR-CACHES", "get_views");
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
