/** @odoo-module **/
/**
 * PbPageBuilder — the My Payobook page builder (FS-12, owner ruling R30).
 *
 * The Form builder's look and words (studio bar, a list on the left, the
 * page in the middle, the picked thing's settings on the right, a publish
 * sheet that says in plain words what changes) for ONE page: the employee's
 * "My Profile". A guided builder, not a free-form editor: sections (title
 * per language, one or two columns), fields from the list (half or full
 * width), a header (heading, sub-line, banner picture, tint). The person
 * card is always first; "My requests" and the My details door can swap.
 *
 * WHY IN THE APP AND NOT ON THE PAGE (the FS-12 spike): the Form builder's
 * overlay lives in the app's bundle (its tokens, buttons and icons come with
 * the import kit there); carrying it into the website page would mean a
 * second copy of those styles fighting the website theme, and every
 * employee's page would have to be ready to load it. Here the page is shown
 * EXACTLY as an employee gets it — in a frame, from the server, as a chosen
 * employee — which the page itself never could (it is always the viewer's
 * own). "Edit this page" on My Profile opens this screen.
 *
 * Nothing changes for anybody until Publish; the work in between is the
 * administrator's draft on the server (the engine's drafts).
 */
import { Component, useState, useRef, onWillStart, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { fsIc, KIND_ICON } from "@pb_form_studio/js/fs_icons";
import { fold, foldMatch } from "@pb_form_studio/js/fs_words";

const FACADE = "pb.form.studio";
const DRAFT_MS = 800;
const LANG_NAMES = { en_US: "English", vi_VN: "Tiếng Việt", id_ID: "Bahasa Indonesia" };
const SIDE_LABEL = () => ({ requests: _t("My requests"), door: _t("Family, ID papers, photo and bank account") });

function clone(x) { return JSON.parse(JSON.stringify(x === undefined ? null : x)); }

export class PbPageBuilder extends Component {
    static template = "pb_form_studio_portal.PageBuilder";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true, error: "", data: null,
            specs: { default: null }, scope: "default", updates: {}, changes: [],
            baseVersion: 0, sel: null, left: "fields", view: "build", sheet: null,
            term: "", chip: "all", country: 0, over: null, overField: null,
            publishing: false, uploading: false, draftNote: "", stale: null,
            emps: [], empTerm: "", previewEmp: 0, previewSize: "desktop", previewKey: 0,
        });
        this.fileInput = useRef("fileInput");
        this._timer = null;
        this._seq = 1;
        onWillStart(() => this.load());
        onWillUnmount(() => this._timer && clearTimeout(this._timer));
    }

    ic(n, s = 16) { return fsIc(n, s); }

    // ================================================================ load
    async load() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(FACADE, "page_studio", []);
            this.state.data = data;
            this.state.baseVersion = data.version;
            this.state.updates = {};
            this.state.changes = [];
            this.state.scope = "default";
            const pub = data.published;
            const specs = { default: clone(pub ? pub.default : data.standard) };
            for (const [cid, spec] of Object.entries((pub && pub.companies) || {})) {
                specs[cid] = clone(spec);
            }
            this.state.specs = specs;
            if (pub) { this.syncTicks(); }
            const draft = data.draft;
            if (draft && draft.payload && (draft.payload.changes || []).length) {
                const p = draft.payload;
                this.state.specs = { default: clone(p.spec), ...clone(p.companies || {}) };
                for (const k of Object.keys(this.state.specs)) {
                    if (!this.state.specs[k]) { delete this.state.specs[k]; }
                }
                this.state.updates = clone(p.updates || {});
                this.state.changes = clone(p.changes || []);
                this.state.baseVersion = draft.base_version;
                if (draft.stale) {
                    this.state.stale = { message: _t("Another administrator published this page after you started your changes.") };
                } else {
                    this.state.draftNote = _t("Your unpublished changes from last time are back.");
                }
            }
            // a field that cannot be shown any more (deleted, or closed by a
            // rule since) leaves the canvas; Publish would refuse it
            for (const spec of this.allSpecs()) {
                for (const sec of spec.sections) { sec.fields = sec.fields.filter((x) => this.field(x.name)); }
            }
            this._seq = 1 + Math.max(0, ...this.allSpecs().flatMap((s) => s.sections.map((x) => Number(String(x.id).replace(/\D/g, "")) || 0)));
            const emps = await this.orm.call(FACADE, "page_employees", [""]);
            this.state.emps = emps;
            this.state.previewEmp = (emps[0] || {}).id || 0;
        } catch (e) {
            this.state.error = (e && e.data && e.data.message) || _t("The page builder could not open.");
        } finally {
            this.state.loading = false;
        }
    }

    /** One truth with the employee Form builder: a field ticked "Show on My
     *  Payobook" there is on the page (end of the first section until moved);
     *  a field not ticked any more is not. */
    syncTicks() {
        const ticked = new Set(this.data.ticked || []);
        const placed = new Set(this.allSpecs().flatMap((s) => s.sections.flatMap((x) => x.fields.map((f) => f.name))));
        for (const spec of this.allSpecs()) {
            for (const sec of spec.sections) { sec.fields = sec.fields.filter((f) => ticked.has(f.name)); }
        }
        const first = this.state.specs.default.sections[0];
        for (const name of ticked) {
            if (!placed.has(name) && first && this.data.fields[name]) { first.fields.push({ name, width: "half" }); }
        }
    }

    // ============================================================ getters
    get data() { return this.state.data || {}; }
    get userLang() { return this.data.lang || "en_US"; }
    get langs() { return this.data.langs || ["en_US"]; }
    langName(code) { return LANG_NAMES[code] || code; }
    allSpecs() { return Object.values(this.state.specs).filter(Boolean); }
    get spec() { return this.state.specs[this.state.scope] || this.state.specs.default; }
    get ownPage() { return this.state.scope === "default" || Boolean(this.state.specs[this.state.scope]); }
    get companies() { return this.data.companies || []; }
    get changeCount() { return this.state.changes.length; }
    get changeText() {
        const n = this.changeCount;
        if (!n) { return _t("No changes yet"); }
        return n === 1 ? _t("1 change not yet published") : _t("%s changes not yet published", n);
    }
    text(texts) {
        if (!texts || typeof texts !== "object") { return texts || ""; }
        return texts[this.userLang] || texts.en_US || Object.values(texts).find(Boolean) || "";
    }
    get headingText() { return this.text(this.spec.header.title) || _t("My Profile"); }
    get subText() { return this.text(this.spec.header.sub) || _t("Your details on file. Bank changes go through a separate secure flow."); }
    get bannerUrl() {
        const id = this.spec.header.banner;
        return id ? ((this.data.banners || {})[String(id)] || `/my/profile/banner/${id}`) : "";
    }
    heroClass() { return `pbpb-hero pbpb-tint-${this.spec.header.tint || "plain"}` + (this.isSel("header") ? " sel" : ""); }
    get tints() { return this.data.tints || []; }
    tintClass(t) { return `pbpb-swatch pbpb-tint-${t}` + (this.spec.header.tint === t ? " on" : ""); }
    tintLabel(t) {
        return { plain: _t("White"), brand: _t("Purple"), teal: _t("Teal"), sky: _t("Blue"), green: _t("Green"),
                 amber: _t("Amber"), rose: _t("Rose"), slate: _t("Grey") }[t] || t;
    }
    get eyebrow() { return _t("My %s", this.data.brand || "Payobook"); }
    setLeft(tab) { this.state.left = tab; }
    get sideBlocks() { return this.spec.side || ["requests", "door"]; }
    sideLabel(b) { return SIDE_LABEL()[b] || b; }

    // fields
    field(name) { return (this.data.fields || {})[name] || null; }
    label(f) {
        const u = this.state.updates[f.name] || {};
        const own = f.custom ? (u.labels || {})[this.userLang] : (u.std_labels || f.std_labels || {})[this.userLang];
        return own || f.label;
    }
    kindIcon(f) { return fsIc(KIND_ICON[f.kind] || "type", 14); }
    placedIn(spec) { return new Set(spec.sections.flatMap((s) => s.fields.map((x) => x.name))); }
    get placed() { return this.placedIn(this.spec); }
    portal(f) {
        const p = { ...(f.portal || {}) };
        const u = this.state.updates[f.name] || {};
        if ("portal_edit" in u) { p.edit = u.portal_edit; }
        if ("portal_mode" in u) { p.mode = u.portal_mode; }
        return p;
    }
    canChange(f) {
        if (f.request) { return true; }        // today's change request (HR approves)
        const p = this.portal(f);
        return Boolean(p.can_edit && p.edit);
    }
    get fieldList() {
        const chip = this.state.chip;
        const cid = Number(this.state.country) || 0;
        const placed = this.placed;
        return Object.values(this.data.fields || {}).filter((f) => {
            if (chip === "own" && !f.custom) { return false; }
            if (chip === "std" && f.custom) { return false; }
            if (chip === "on" && !placed.has(f.name)) { return false; }
            if (chip === "off" && placed.has(f.name)) { return false; }
            if (chip === "change" && !(placed.has(f.name) && this.canChange(f))) { return false; }
            if (cid && (f.countries || []).length && !(f.countries || []).some((c) => c.id === cid)) { return false; }
            return foldMatch(this.state.term, this.label(f), f.field_label);
        });
    }
    get chips() {
        return [
            { key: "all", label: _t("All") }, { key: "own", label: _t("Own") }, { key: "std", label: _t("Standard") },
            { key: "on", label: _t("On the page") }, { key: "off", label: _t("Not on the page") },
            { key: "change", label: _t("Employee can change") },
        ];
    }
    chipClass(c) { return { on: this.state.chip === c.key }; }
    setChip(k) { this.state.chip = k; }
    onTerm(ev) { this.state.term = ev.target.value; }
    onCountry(ev) { this.state.country = Number(ev.target.value) || 0; }
    clearFilter() { this.state.term = ""; this.state.chip = "all"; this.state.country = 0; }
    get filtered() { return Boolean(fold(this.state.term)) || this.state.chip !== "all" || Boolean(this.state.country); }
    get countText() {
        const n = this.fieldList.length;
        const total = Object.keys(this.data.fields || {}).length;
        return this.filtered ? _t("%(n)s of %(total)s", { n, total }) : _t("%s fields", total);
    }
    get countryOptions() { return [...(this.data.countries || [])].sort((a, b) => a.name.localeCompare(b.name)); }
    isCountry(c) { return Number(this.state.country) === c.id; }
    rowClass(f) { return { on: this.placed.has(f.name), custom: f.custom, sel: this.isSelField(f.name) }; }
    rowSub(f) {
        const parts = [f.custom ? _t("Own field") : _t("Standard field"), f.type_label];
        if ((f.countries || []).length) { parts.push(_t("Only %s", f.countries.map((c) => c.name).join(", "))); }
        if (this.placed.has(f.name)) {
            parts.push(this.canChange(f) ? _t("On the page, employee can change") : _t("On the page"));
        }
        return parts.join(" · ");
    }

    // canvas
    get sections() { return this.spec.sections; }
    sectionTitle(sec) { return this.text(sec.title) || _t("Untitled section"); }
    secClass(sec) { return { sel: this.isSel("section", sec.id), over: this.state.over === sec.id }; }
    gridClass(sec) { return "pbpb-grid " + (sec.cols === 1 ? "one" : "two"); }
    tiles(sec) { return sec.fields.map((x) => ({ ...x, f: this.field(x.name) })).filter((x) => x.f); }
    tileClass(sec, t) {
        return { full: sec.cols === 1 || t.width === "full", sel: this.isSelField(t.name),
                 over: this.state.overField === t.name, change: this.canChange(t.f) };
    }
    get formRows() {
        return this.sections.flatMap((s) => s.fields).map((x) => this.field(x.name)).filter((f) => f && this.canChange(f));
    }
    // selection
    isSel(type, id) { const s = this.state.sel; return Boolean(s && s.type === type && (id === undefined || s.id === id)); }
    isSelField(name) { return this.isSel("field", name); }
    selectHeader() { this.state.sel = { type: "header" }; }
    selectSection(sec) { this.state.sel = { type: "section", id: sec.id }; }
    selectField(name) { this.state.sel = { type: "field", id: name }; }
    deselect() { this.state.sel = null; }
    get selSection() { return this.isSel("section") ? this.sections.find((s) => s.id === this.state.sel.id) : null; }
    get selField() { return this.isSel("field") ? this.field(this.state.sel.id) : null; }
    get selItem() {
        if (!this.isSel("field")) { return null; }
        for (const sec of this.sections) {
            const it = sec.fields.find((x) => x.name === this.state.sel.id);
            if (it) { return { sec, it }; }
        }
        return null;
    }

    // ========================================================== changes
    note(what) {
        this.state.changes.push(String(what));
        this.scheduleDraft();
    }
    noteOnce(key, what) {
        const k = "[" + key + "] ";
        this.state.changes = this.state.changes.filter((c) => !c.startsWith(k));
        this.state.changes.push(k + what);
        this.scheduleDraft();
    }
    changeLine(c) { return String(c).replace(/^\[[^\]]*\] /, ""); }
    scheduleDraft() {
        clearTimeout(this._timer);
        this._timer = setTimeout(() => this.saveDraft(), DRAFT_MS);
    }
    draftPayload() {
        const companies = {};
        for (const [k, v] of Object.entries(this.state.specs)) { if (k !== "default") { companies[k] = v; } }
        return { spec: this.state.specs.default, companies, updates: this.state.updates,
                 changes: this.state.changes, base_version: this.state.baseVersion };
    }
    async saveDraft() {
        clearTimeout(this._timer);
        try {
            await this.orm.call(FACADE, "save_draft", ["my_profile_page", this.draftPayload()]);
        } catch {
            // Publish still carries everything.
        }
    }

    // ------------------------------------------------------------ fields
    addField(f, secId, before) {
        const spec = this.spec;
        const target = spec.sections.find((s) => s.id === secId)
            || (this.selSection) || (this.selItem && this.selItem.sec) || spec.sections[0];
        if (!target) { return; }
        let item = { name: f.name, width: "half" };
        for (const s of spec.sections) {
            const i = s.fields.findIndex((x) => x.name === f.name);
            if (i >= 0) { item = s.fields[i]; s.fields.splice(i, 1); }
        }
        const at = before ? target.fields.findIndex((x) => x.name === before) : -1;
        if (at >= 0) { target.fields.splice(at, 0, item); } else { target.fields.push(item); }
        this.note(_t("%(f)s in %(s)s", { f: this.label(f), s: this.sectionTitle(target) }));
        this.selectField(f.name);
    }
    removeField(name) {
        const f = this.field(name);
        for (const s of this.spec.sections) { s.fields = s.fields.filter((x) => x.name !== name); }
        if (f) { this.note(_t("%s taken off the page", this.label(f))); }
        if (this.isSelField(name)) { this.state.sel = null; }
    }
    setWidth(name, width) {
        const hit = this.selItem;
        if (!hit || hit.it.width === width) { return; }
        hit.it.width = width;
        this.noteOnce("w:" + name, _t("%(f)s: %(w)s", { f: this.label(this.field(name)), w: width === "full" ? _t("full width") : _t("half width") }));
    }
    widthClass(w) { const hit = this.selItem; return { on: Boolean(hit) && hit.it.width === w }; }
    moveFieldTo(ev) {
        const f = this.selField;
        if (f) { this.addField(f, ev.target.value, null); }
    }
    isItemSection(sec) { const hit = this.selItem; return Boolean(hit) && hit.sec.id === sec.id; }
    // settings of a field (the engine's own ticks and labels)
    upd(f, vals, what) {
        this.state.updates[f.name] = { ...(this.state.updates[f.name] || {}), ...vals };
        this.noteOnce("u:" + f.name + ":" + Object.keys(vals).join(","), _t("%(f)s: %(what)s", { f: f.label, what }));
    }
    labelValue(f, lang) {
        const u = this.state.updates[f.name] || {};
        if (f.custom) { return (u.labels || f.labels || {})[lang] || ""; }
        return (u.std_labels || f.std_labels || {})[lang] || "";
    }
    onLabel(f, lang, ev) {
        const v = ev.target.value.trim();
        if (f.custom) {
            if (lang === "en_US" && !v) { ev.target.value = this.labelValue(f, lang); return; }
            const labels = { ...((this.state.updates[f.name] || {}).labels || {}), [lang]: v };
            this.upd(f, { labels }, _t("label"));
        } else {
            const labels = { ...((this.state.updates[f.name] || {}).std_labels || f.std_labels || {}) };
            if (v) { labels[lang] = v; } else { delete labels[lang]; }
            this.upd(f, { std_labels: labels }, _t("label"));
        }
    }
    toggleChange(f) {
        const p = this.portal(f);
        if (!p.can_edit) { return; }
        this.upd(f, { portal_edit: !p.edit }, !p.edit ? _t("employee can change it") : _t("look only"));
    }
    setMode(f, mode) {
        const p = this.portal(f);
        if (mode === "instant" && p.mode_lock) { return; }
        if (p.mode !== mode) { this.upd(f, { portal_mode: mode }, mode === "instant" ? _t("saves at once") : _t("HR approves")); }
    }
    modeClass(f, mode) { return { on: (this.portal(f).mode || "approve") === mode }; }
    switchAttr(on) { return on ? "true" : "false"; }
    countryText(f) { return (f.countries || []).map((c) => c.name).join(", "); }

    // ---------------------------------------------------------- sections
    addSection() {
        if (this.spec.sections.length >= (this.data.caps || {}).sections) { return; }
        let id;
        do { id = "s" + this._seq++; } while (this.spec.sections.some((s) => s.id === id));
        const title = {};
        title[this.userLang] = _t("New section");
        if (this.userLang !== "en_US") { title.en_US = "New section"; }
        const sec = { id, title, cols: 2, fields: [] };
        this.spec.sections.push(sec);
        this.note(_t("New section"));
        this.selectSection(sec);
    }
    onSecTitle(sec, lang, ev) {
        sec.title = { ...(sec.title || {}), [lang]: ev.target.value.trim() };
        this.noteOnce("t:" + sec.id, _t("Section name: %s", this.sectionTitle(sec)));
    }
    secTitleValue(sec, lang) { return (sec.title || {})[lang] || ""; }
    setCols(sec, cols) {
        if (sec.cols === cols) { return; }
        sec.cols = cols;
        this.noteOnce("c:" + sec.id, _t("%(s)s: %(n)s", { s: this.sectionTitle(sec), n: cols === 1 ? _t("one column") : _t("two columns") }));
    }
    colsClass(sec, n) { return { on: (sec.cols || 2) === n }; }
    moveSection(sec, dir) {
        const list = this.spec.sections;
        const i = list.indexOf(sec);
        const j = i + dir;
        if (i < 0 || j < 0 || j >= list.length) { return; }
        list.splice(i, 1);
        list.splice(j, 0, sec);
        this.note(_t("%s moved", this.sectionTitle(sec)));
    }
    canRemoveSection(sec) { return !sec.fields.length && this.spec.sections.length > 1; }
    removeSection(sec) {
        if (!this.canRemoveSection(sec)) { return; }
        this.spec.sections = this.spec.sections.filter((s) => s !== sec);
        this.note(_t("%s removed", this.sectionTitle(sec)));
        this.state.sel = null;
    }
    moveSide(b, dir) {
        const list = [...this.sideBlocks];
        const i = list.indexOf(b);
        const j = i + dir;
        if (i < 0 || j < 0 || j >= list.length) { return; }
        [list[i], list[j]] = [list[j], list[i]];
        this.spec.side = list;
        this.note(_t("%s moved", this.sideLabel(b)));
    }

    // ------------------------------------------------------------ header
    headerValue(key, lang) { return ((this.spec.header || {})[key] || {})[lang] || ""; }
    onHeader(key, lang, ev) {
        this.spec.header[key] = { ...(this.spec.header[key] || {}), [lang]: ev.target.value.trim() };
        this.noteOnce("h:" + key, { title: _t("Heading"), sub: _t("Line under the heading"), banner_alt: _t("Picture description") }[key]);
    }
    setTint(t) {
        if (this.spec.header.tint === t) { return; }
        this.spec.header.tint = t;
        this.noteOnce("h:tint", _t("Header colour: %s", this.tintLabel(t)));
    }
    pickBanner() { if (this.fileInput.el) { this.fileInput.el.click(); } }
    async onBanner(ev) {
        const file = ev.target.files && ev.target.files[0];
        ev.target.value = "";
        if (!file) { return; }
        const caps = this.data.caps || {};
        if (file.size > (caps.banner_mb || 2) * 1024 * 1024) {
            this.notification.add(_t("The picture is too big: at most 2 MB."), { type: "danger" });
            return;
        }
        this.state.uploading = true;
        try {
            const data = await new Promise((resolve, reject) => {
                const r = new FileReader();
                r.onload = () => resolve(String(r.result));
                r.onerror = reject;
                r.readAsDataURL(file);
            });
            const res = await this.orm.call(FACADE, "page_upload_banner", [file.name, data]);
            this.data.banners = { ...(this.data.banners || {}), [String(res.id)]: res.url };
            this.spec.header.banner = res.id;
            this.noteOnce("h:banner", _t("Banner picture"));
        } catch (e) {
            this.notification.add((e && e.data && e.data.message) || _t("That file could not be read."), { type: "danger" });
        } finally {
            this.state.uploading = false;
        }
    }
    removeBanner() {
        this.spec.header.banner = false;
        this.noteOnce("h:banner", _t("Banner picture removed"));
    }

    // --------------------------------------------------------- companies
    setScope(ev) { this.state.scope = ev.target.value; this.state.sel = null; }
    isScope(c) { return this.state.scope === String(c.id); }
    get scopeName() {
        const c = this.companies.find((x) => String(x.id) === this.state.scope);
        return c ? c.name : _t("All companies");
    }
    ownPageForCompany() {
        if (this.state.scope === "default") { return; }
        this.state.specs[this.state.scope] = clone(this.state.specs.default);
        this.note(_t("%s gets its own page", this.scopeName));
    }
    dropCompanyPage() {
        if (this.state.scope === "default") { return; }
        delete this.state.specs[this.state.scope];
        this.note(_t("%s uses the page for all companies again", this.scopeName));
    }

    // ---------------------------------------------------------- dragging
    onDragStart(ev, name) { ev.dataTransfer.setData("text/plain", name); ev.dataTransfer.effectAllowed = "move"; }
    onSecOver(ev, sec) { ev.preventDefault(); this.state.over = sec.id; }
    onSecLeave(ev, sec) { if (!ev.currentTarget.contains(ev.relatedTarget) && this.state.over === sec.id) { this.state.over = null; } }
    onSecDrop(ev, sec) {
        ev.preventDefault();
        this.state.over = null;
        this.state.overField = null;
        const f = this.field(ev.dataTransfer.getData("text/plain"));
        if (f) { this.addField(f, sec.id, null); }
    }
    onTileOver(ev, t) { ev.preventDefault(); this.state.overField = t.name; }
    onTileLeave(t) { if (this.state.overField === t.name) { this.state.overField = null; } }
    onTileDrop(ev, sec, t) {
        ev.preventDefault();
        ev.stopPropagation();
        this.state.over = null;
        this.state.overField = null;
        const f = this.field(ev.dataTransfer.getData("text/plain"));
        if (f && f.name !== t.name) { this.addField(f, sec.id, t.name); }
    }
    onTileKey(ev, t) { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); this.selectField(t.name); } }
    moveTile(sec, t, dir) {
        const i = sec.fields.findIndex((x) => x.name === t.name);
        const j = i + dir;
        if (i < 0 || j < 0 || j >= sec.fields.length) { return; }
        const [it] = sec.fields.splice(i, 1);
        sec.fields.splice(j, 0, it);
        this.noteOnce("o:" + sec.id, _t("Order in %s", this.sectionTitle(sec)));
    }

    // ----------------------------------------------------------- preview
    setView(v) {
        if (v === "preview") { this.saveDraft().then(() => { this.state.previewKey++; this.state.view = v; }); return; }
        this.state.view = v;
    }
    viewClass(v) { return { on: this.state.view === v }; }
    get previewUrl() {
        const q = new URLSearchParams({ employee_id: String(this.state.previewEmp || 0),
                                        source: this.changeCount ? "draft" : "live", t: String(this.state.previewKey) });
        if (this.state.scope !== "default") { q.set("company_id", this.state.scope); }
        return "/my/profile/preview?" + q.toString();
    }
    onPreviewEmp(ev) { this.state.previewEmp = Number(ev.target.value) || 0; this.state.previewKey++; }
    isPreviewEmp(e) { return this.state.previewEmp === e.id; }
    async onEmpTerm(ev) {
        this.state.empTerm = ev.target.value;
        this.state.emps = await this.orm.call(FACADE, "page_employees", [this.state.empTerm]);
    }
    setSize(s) { this.state.previewSize = s; }
    sizeClass(s) { return { on: this.state.previewSize === s }; }
    frameClass() { return "pbpb-frame " + this.state.previewSize; }
    empLabel(e) { return [e.name, e.company, e.country].filter(Boolean).join(" · "); }

    // ----------------------------------------------------------- history
    get history() { return this.data.history || []; }
    async restore(h) {
        try {
            const page = await this.orm.call(FACADE, "page_version", [h.id]);
            this.state.specs = { default: clone(page.spec), ...clone(page.companies || {}) };
            this.state.scope = "default";
            // a field deleted since then cannot come back; the rest does
            for (const spec of this.allSpecs()) {
                for (const sec of spec.sections) { sec.fields = sec.fields.filter((x) => this.field(x.name)); }
            }
            this.note(_t("Restored the page published %s", h.when));
            this.state.sheet = null;
            this.notification.add(_t("That version is loaded. Publish to make it live again."), { type: "info" });
        } catch (e) {
            this.notification.add((e && e.data && e.data.message) || _t("This version cannot be restored."), { type: "danger" });
        }
    }
    undo() {
        const restorable = this.history.filter((h) => h.restorable);
        if (restorable.length >= 2) { this.restore(restorable[1]); }
    }
    get canUndo() { return this.history.filter((h) => h.restorable).length >= 2; }
    openSheet(s) { this.state.sheet = s; }
    closeSheet() { this.state.sheet = null; }
    async resetPage() {
        try {
            await this.orm.call(FACADE, "page_reset", []);
            this.notification.add(_t("My Profile is the standard page again."), { type: "success" });
            this.state.sheet = null;
            await this.load();
        } catch (e) {
            this.notification.add((e && e.data && e.data.message) || _t("That did not work. Nothing was changed."), { type: "danger" });
        }
    }

    // ----------------------------------------------------------- publish
    async publish(overwrite = false) {
        if (this.state.publishing) { return; }
        this.state.publishing = true;
        try {
            const p = this.draftPayload();
            const res = await this.orm.call(FACADE, "page_publish", [{ ...p, overwrite: Boolean(overwrite),
                changes: this.state.changes.map((c) => this.changeLine(c)) }]);
            if (res && res.stale) {
                this.state.stale = res;
                this.state.sheet = "stale";
                return;
            }
            clearTimeout(this._timer);
            const n = this.changeCount;
            this.notification.add(n === 1 ? _t("Published. 1 change is now live for every employee.")
                : _t("Published. %s changes are now live for every employee.", n), { type: "success" });
            this.state.sheet = null;
            this.state.changes = [];
            this.state.draftNote = "";
            await this.load();
        } catch (e) {
            this.state.sheet = null;
            this.notification.add((e && e.data && e.data.message) || _t("Publishing did not work. Nothing was changed."), { type: "danger", sticky: true });
        } finally {
            this.state.publishing = false;
        }
    }
    async discard() {
        clearTimeout(this._timer);
        await this.orm.call(FACADE, "discard_draft", ["my_profile_page"]);
        this.state.draftNote = "";
        this.state.stale = null;
        this.state.sel = null;
        await this.load();
        this.notification.add(_t("Changes discarded. Nothing was published."), { type: "info" });
    }
    dismissNote() { this.state.draftNote = ""; }
    async close() {
        if (this.changeCount) { await this.saveDraft(); }
        if (this.props.action && this.props.action.context && this.props.action.context.pb_back) {
            return this.action.doAction(this.props.action.context.pb_back);
        }
        return this.action.doAction({ type: "ir.actions.client", tag: "pb_settings_hub" });
    }
    openMyProfile() { window.open("/my/profile", "_blank", "noopener"); }
}

registry.category("actions").add("pb_page_builder", PbPageBuilder);
