/** @odoo-module **/
/**
 * Settings › Documents — the Document studio (DOCSTUDIO phase F).
 *
 * Two views in one client action (`pb_doc_studio`):
 *   gallery   every letter grouped by kind (F1)
 *   designer  fields | the page | Preview · Page (F2–F8)
 *
 * HERO (F4): the Preview tab draws the finished page for a REAL person as you
 * type (400 ms), in their language, with real values; empty values are amber
 * chips, hidden paragraphs can be ghosted in, values that change when you
 * switch person glow for a moment, and "Download a sample PDF" is the true
 * PDF. The preview is drawn by the server (the same frame as the PDF) and
 * shown in a sandboxed frame that runs no script.
 *
 * Every call goes to `pb.doc.studio`, which refuses anyone who may not change
 * letter wording.
 */
import { Component, onMounted, onPatched, onWillStart, onWillUnmount, useExternalListener, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
import { dsIc, FIELD_GROUP_ICON, KIND_ICON } from "./doc_icons";
import { FACADE, ago, errorText, fold, modKey, readBase64, store } from "./doc_words";
import { DocEditor, DocToolbar } from "./doc_editor";
import { RuleBuilder, ruleSentence } from "./rule_builder";

const A4_W = 794;
const A4_H = 1123;
const MARGIN_PX = { normal: [40, 28, 20, 20], narrow: [32, 22, 12, 12], wide: [46, 32, 30, 30] };
const MM = 3.7795;
const PV_STYLE = `
@font-face{font-family:'Roboto';src:url('/web/static/fonts/google/Roboto/Roboto-Regular.ttf') format('truetype');font-weight:400}
@font-face{font-family:'Roboto';src:url('/web/static/fonts/google/Roboto/Roboto-Bold.ttf') format('truetype');font-weight:700}
@font-face{font-family:'Roboto';src:url('/web/static/fonts/google/Roboto/Roboto-Italic.ttf') format('truetype');font-style:italic}
@font-face{font-family:'Open_Sans';src:url('/web/static/fonts/google/Open_Sans/Open_Sans-Regular.ttf') format('truetype');font-weight:400}
@font-face{font-family:'Open_Sans';src:url('/web/static/fonts/google/Open_Sans/Open_Sans-Bold.ttf') format('truetype');font-weight:700}
@font-face{font-family:'Montserrat';src:url('/web/static/fonts/google/Montserrat/Montserrat-Regular.ttf') format('truetype');font-weight:400}
@font-face{font-family:'Montserrat';src:url('/web/static/fonts/google/Montserrat/Montserrat-Bold.ttf') format('truetype');font-weight:700}
@font-face{font-family:'DejaVu Serif';src:url('/pb_hr_payroll_formula/static/fonts/dejavu/DejaVuSerif.ttf') format('truetype');font-weight:400}
@font-face{font-family:'DejaVu Serif';src:url('/pb_hr_payroll_formula/static/fonts/dejavu/DejaVuSerif-Bold.ttf') format('truetype');font-weight:700}
html,body{margin:0;padding:0;background:#fff}
body{width:${A4_W}px;overflow:hidden}
.pbds-screen{min-height:${A4_H}px;box-sizing:border-box}
`;

function clone(v) { return v === undefined ? undefined : JSON.parse(JSON.stringify(v)); }

export class DocStudio extends Component {
    static template = "pb_doc_studio.DocStudio";
    static components = { DocEditor, DocToolbar, RuleBuilder, HubBackChip };
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.back = hubBack(this.props);
        this.state = useState({
            view: "gallery", loading: true, error: "", board: null,
            term: "", kind: "all", menu: 0, dialog: null,
            // designer
            docLoading: false, doc: null, draft: null, lang: "en_US", editorKey: 1,
            dirty: false, saving: false, savedAt: "", rightTab: "preview",
            person: null, previewLang: "", pv: { html: "", hidden: 0, missing: [], values: {}, loading: false, error: "" },
            pvScale: 0.42, pvHeight: A4_H, ghosts: false, large: false,
            fieldTerm: "", collapsed: {}, picker: null, ruleEdit: null,
            peopleOpen: false, peopleTerm: "", people: [], peopleBusy: false,
            restore: null, pdfBusy: false, zoom: 1, pages: 1, signBusy: false,
        });
        this.ui = useState({ canUndo: false, canRedo: false, bold: false, italic: false, underline: false,
                             ul: false, ol: false, align: "left", block: "p", inTable: false, image: false,
                             inRule: false, focused: false });
        this.api = null;
        // A stable handle for the toolbar: the editor's own api arrives after
        // it mounts (and changes with each language tab), without a redraw.
        this.editorApi = new Proxy({}, {
            get: (_target, name) => {
                if (typeof name !== "string" || ["then", "constructor", "toJSON"].includes(name)) {
                    return undefined;
                }
                return (...args) => (this.api && typeof this.api[name] === "function"
                    ? this.api[name](...args) : undefined);
            },
        });
        this.searchRef = useRef("search");
        this.pvFrame = useRef("pvFrame");
        this.pvBox = useRef("pvBox");
        this.largeFrame = useRef("largeFrame");
        this.imgInput = useRef("imgInput");
        this.signInput = useRef("signInput");
        this.desk = useRef("desk");
        this.paper = useRef("paper");
        this.pickerInput = useRef("pickerInput");
        this.peopleInput = useRef("peopleInput");
        this.pvSeq = 0;
        this.prevValues = {};
        this._pvTimer = null;
        this._localTimer = null;
        this._peopleTimer = null;
        useExternalListener(window, "keydown", (ev) => this.onKey(ev));
        useExternalListener(window, "mousedown", (ev) => this.onOutside(ev));
        useExternalListener(window, "beforeunload", (ev) => {
            if (this.state.view === "designer" && this.state.dirty) {
                ev.preventDefault();
                ev.returnValue = "";
            }
        });
        onWillStart(async () => {
            await this.loadBoard();
            const ctx = (this.props.action && this.props.action.context) || {};
            if (ctx.pbds_open) { await this.openDoc(ctx.pbds_open); }
        });
        onMounted(() => {
            this.ro = new ResizeObserver(() => { this.measureDesk(); this.measurePreview(); });
            this.observe();
        });
        onPatched(() => { this.observe(); this.measurePages(); });
        onWillUnmount(() => {
            if (this.ro) { this.ro.disconnect(); }
            clearTimeout(this._pvTimer);
            clearTimeout(this._localTimer);
            clearTimeout(this._peopleTimer);
        });
    }

    ic(n, s = 16) { return dsIc(n, s); }
    get mod() { return modKey(); }
    noop() {}

    observe() {
        if (!this.ro) { return; }
        for (const ref of [this.desk, this.pvBox]) {
            if (ref.el && !ref.el._pbdsObserved) {
                ref.el._pbdsObserved = true;
                this.ro.observe(ref.el);
            }
        }
    }

    // ================================================================ gallery
    async loadBoard() {
        this.state.loading = true;
        try {
            this.state.board = await this.orm.call(FACADE, "board", []);
            this.state.error = "";
        } catch (e) {
            this.state.error = errorText(e, _t("The documents could not be loaded."));
        } finally {
            this.state.loading = false;
        }
    }

    get cards() {
        const b = this.state.board;
        if (!b) { return []; }
        const term = fold(this.state.term);
        return b.cards.filter((c) => {
            if (this.state.kind !== "all" && c.kind !== this.state.kind) { return false; }
            if (!term) { return true; }
            return [c.name, c.subject, c.type_label, c.company, ...(c.countries || []), c.snippet]
                .some((v) => fold(v).includes(term));
        });
    }
    get groups() {
        const b = this.state.board;
        if (!b) { return []; }
        const cards = this.cards;
        return b.kinds.map((k) => ({ ...k, icon: KIND_ICON[k.key] || "folder", cards: cards.filter((c) => c.kind === k.key) }))
            .filter((g) => g.cards.length);
    }
    get kindChips() {
        const b = this.state.board;
        if (!b) { return []; }
        const all = b.cards.length;
        return [{ key: "all", label: _t("All"), n: all },
            ...b.kinds.map((k) => ({ ...k, n: b.cards.filter((c) => c.kind === k.key).length }))];
    }
    setKind(key) { this.state.kind = key; }
    onTerm(ev) { this.state.term = ev.target.value; }
    clearFilters() { this.state.term = ""; this.state.kind = "all"; }
    get filtered() { return Boolean(this.state.term) || this.state.kind !== "all"; }
    get yoursCount() { return ((this.state.board && this.state.board.cards) || []).filter((c) => c.edited).length; }

    cardFor(c) {
        const out = [];
        if (c.company) { out.push(c.company); }
        out.push(...(c.countries || []));
        return out.length ? out.join(" · ") : _t("Everyone");
    }
    cardChanged(c) {
        if (!c.changed_on) { return ""; }
        return c.changed_by ? _t("Changed by %(who)s, %(when)s", { who: c.changed_by, when: ago(c.changed_on) })
            : _t("Changed %s", ago(c.changed_on));
    }
    missingText(n) { return n === 1 ? _t("1 field no longer exists") : _t("%s fields no longer exist", n); }
    toggleMenu(c, ev) {
        if (ev) { ev.stopPropagation(); }
        this.state.menu = this.state.menu === c.id ? 0 : c.id;
    }
    onOutside(ev) {
        if (this.state.menu && !(ev.target.closest && ev.target.closest(".pbds-menu, .pbds-kebab"))) {
            this.state.menu = 0;
        }
        if (this.state.peopleOpen && !(ev.target.closest && ev.target.closest(".pbds-person"))) {
            this.state.peopleOpen = false;
        }
        if (this.state.picker && !(ev.target.closest && ev.target.closest(".pbds-picker"))) {
            this.state.picker = null;
        }
    }

    // ---------------------------------------------------------------- actions
    async setActive(c, active) {
        this.state.menu = 0;
        try {
            await this.orm.call(FACADE, "set_active", [c.id, active]);
            this.notification.add(active ? _t("“%s” is switched on again.", c.name)
                : _t("“%s” is switched off. Letters will no longer use it.", c.name), { type: active ? "success" : "info" });
            await this.loadBoard();
            if (this.state.doc && this.state.doc.id === c.id) { this.state.doc.active = active; }
        } catch (e) {
            this.notification.add(errorText(e, _t("That did not work. Try again.")), { type: "danger" });
        }
    }

    askCopy(c) {
        this.state.menu = 0;
        this.state.dialog = { type: "copy", card: c, company: 0, countries: [], busy: false, term: "" };
    }
    copyToggle(id) {
        const d = this.state.dialog;
        const at = d.countries.indexOf(id);
        if (at >= 0) { d.countries.splice(at, 1); } else { d.countries.push(id); }
    }
    get copyCountries() {
        const d = this.state.dialog;
        const all = (this.state.board && this.state.board.countries) || [];
        const term = fold(d && d.term);
        return term ? all.filter((c) => fold(c.name).includes(term)) : all;
    }
    get copySentence() {
        const d = this.state.dialog;
        if (!d) { return ""; }
        const b = this.state.board;
        const company = d.company ? (b.companies.find((c) => c.id === Number(d.company)) || {}).name : "";
        const countries = b.countries.filter((c) => d.countries.includes(c.id)).map((c) => c.name).join(", ");
        if (company && countries) {
            return _t("Letters for people at %(company)s who work in %(countries)s will use this copy.", { company, countries });
        }
        if (company) { return _t("Letters for people at %s will use this copy.", company); }
        if (countries) { return _t("Letters for people who work in %s will use this copy.", countries); }
        return _t("Choose a company, one or more countries of work, or both.");
    }
    get copyReady() { const d = this.state.dialog; return Boolean(d && (Number(d.company) || d.countries.length)); }
    async doCopy() {
        const d = this.state.dialog;
        if (!this.copyReady || d.busy) { return; }
        d.busy = true;
        try {
            const res = await this.orm.call(FACADE, "copy_for", [d.card.id, Number(d.company) || false, d.countries]);
            this.state.dialog = null;
            this.notification.add(res.existing ? _t("There is already a copy for these people. It is open now.")
                : _t("Copy made. Change it as you like: only the people it is for get it."), { type: "success" });
            await this.loadBoard();
            await this.openDoc(res.id);
        } catch (e) {
            d.busy = false;
            this.notification.add(errorText(e, _t("The copy could not be made.")), { type: "danger" });
        }
    }

    askReset(c) {
        this.state.menu = 0;
        const lost = [_t("Your wording")];
        const versions = (c.langs || []).slice(1).map((l) => l.name);
        if (versions.length) { lost.push(_t("The wording in %s", versions.join(", "))); }
        if (c.rules) { lost.push(c.rules === 1 ? _t("1 “Show only when” rule") : _t("%s “Show only when” rules", c.rules)); }
        if (c.page) { lost.push(_t("The page design (letterhead, margins, font, signature)")); }
        this.state.dialog = { type: "reset", card: c, lost, busy: false };
    }
    async doReset() {
        const d = this.state.dialog;
        if (d.busy) { return; }
        d.busy = true;
        const id = d.card.id;
        const name = d.card.name;
        try {
            await this.orm.call(FACADE, "reset", [id]);
            this.state.dialog = null;
            this.store.drop(id);
            this.notification.add(_t("“%s” has its built-in wording again.", name), {
                type: "success",
                autocloseDelay: 10000,
                buttons: [{ name: _t("Undo"), primary: true, onClick: () => this.undoReset(id) }],
            });
            await this.loadBoard();
            if (this.state.view === "designer" && this.state.doc && this.state.doc.id === id) {
                await this.openDoc(id, true);
            }
        } catch (e) {
            d.busy = false;
            this.notification.add(errorText(e, _t("The built-in wording could not be put back.")), { type: "danger" });
        }
    }
    async undoReset(id) {
        try {
            await this.orm.call(FACADE, "undo_reset", [id]);
            this.notification.add(_t("Your wording is back."), { type: "success" });
            await this.loadBoard();
            if (this.state.view === "designer" && this.state.doc && this.state.doc.id === id) {
                await this.openDoc(id, true);
            }
        } catch (e) {
            this.notification.add(errorText(e, _t("There is nothing to undo.")), { type: "warning" });
        }
    }

    askNew() {
        this.state.dialog = { type: "new", name: "", kind: this.state.kind !== "all" ? this.state.kind : "other", busy: false };
    }
    async doNew() {
        const d = this.state.dialog;
        if (d.busy) { return; }
        d.busy = true;
        try {
            const res = await this.orm.call(FACADE, "create_blank", [d.kind, d.name]);
            this.state.dialog = null;
            await this.loadBoard();
            await this.openDoc(res.id);
        } catch (e) {
            d.busy = false;
            this.notification.add(errorText(e, _t("The document could not be made.")), { type: "danger" });
        }
    }
    closeDialog() { if (!(this.state.dialog && this.state.dialog.busy)) { this.state.dialog = null; } }
    onCopyCompany(ev) { this.state.dialog.company = Number(ev.target.value) || 0; }
    onCopyTerm(ev) { this.state.dialog.term = ev.target.value; }
    onNewName(ev) { this.state.dialog.name = ev.target.value; }
    onNewKey(ev) { if (ev.key === "Enter") { ev.preventDefault(); this.doNew(); } }
    setNewKind(key) { this.state.dialog.kind = key; }
    kindIcon(key) { return KIND_ICON[key] || "folder"; }
    onCardKey(c, ev) {
        if (ev.target !== ev.currentTarget) { return; }
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); this.openDoc(c.id); }
    }
    askCopyDoc() { this.askCopy({ id: this.state.doc.id, name: this.state.draft.name }); }
    askResetDoc() {
        const doc = this.state.doc;
        const versions = Object.keys(doc.versions || {});
        this.askReset({
            id: doc.id, name: this.state.draft.name,
            langs: [{}].concat(doc.langs.filter((l) => versions.includes(l.code))),
            rules: Object.keys(doc.rules || {}).length, page: doc.page_set,
        });
    }
    onFieldTerm(ev) { this.state.fieldTerm = ev.target.value; }
    openLarge() { this.state.large = true; }
    closeLarge() { this.state.large = false; }
    // Whole sentences, translated as one (a sentence cut by a value in the
    // template would be translated in pieces, ledger PRD-3).
    get restoreText() { return _t("You have changes from %s that were not saved. Restore them?", this.restoreWhen); }
    get noLangTitle() { return _t("No %s wording yet", this.curLangName); }
    get noLangText() {
        return this.curTranslated
            ? _t("This letter already comes with a %(lang)s translation. Start from it to change it, or from the %(main)s wording.", { lang: this.curLangName, main: this.mainLangName })
            : _t("People who read %(lang)s get the %(main)s wording until you write one.", { lang: this.curLangName, main: this.mainLangName });
    }
    get copyFromText() { return _t("Copy from %s", this.mainLangName); }
    get copyIntro() {
        const d = this.state.dialog;
        return _t("Some people get their own version of “%s”. Everyone else keeps the one they have now.", (d && d.card && d.card.name) || "");
    }
    get resetIntro() {
        const d = this.state.dialog;
        return _t("“%s” goes back to the wording it came with. You lose:", (d && d.card && d.card.name) || "");
    }
    get removeLangTitle() { return _t("Remove the %s wording?", (this.state.dialog || {}).name || ""); }
    get removeLangText() {
        return _t("People who read %(lang)s will get the %(main)s wording. Nothing changes until you save.",
                  { lang: (this.state.dialog || {}).name || "", main: this.mainLangName });
    }
    get yoursText() {
        const n = this.yoursCount;
        return n === 1 ? _t("1 with your wording") : _t("%s with your wording", n);
    }
    get docForText() {
        const doc = this.state.doc;
        return doc ? [doc.for_company, ...(doc.for_countries || [])].filter(Boolean).join(" · ") : "";
    }
    langLabel(l) {
        const p = this.state.person;
        return p && l.code === p.lang ? _t("%s (their language)", l.name) : l.name;
    }

    // ================================================================ designer
    get store() {
        return {
            key: (id) => `pbds.draft.${id}`,
            get: (id) => store.get(`pbds.draft.${id}`),
            set: (id, v) => store.set(`pbds.draft.${id}`, v),
            drop: (id) => store.drop(`pbds.draft.${id}`),
        };
    }

    async openDoc(id, quiet = false) {
        this.state.menu = 0;
        this.state.docLoading = true;
        this.state.view = "designer";
        try {
            const doc = await this.orm.call(FACADE, "open", [id]);
            this.applyDoc(doc);
            const kept = this.store.get(doc.id);
            if (!quiet && kept && kept.draft && JSON.stringify(kept.draft) !== JSON.stringify(this.payload())) {
                this.state.restore = kept;
            } else {
                this.state.restore = null;
            }
            this.schedulePreview(0);
        } catch (e) {
            this.state.view = "gallery";
            this.notification.add(errorText(e, _t("The document could not be opened.")), { type: "danger" });
        } finally {
            this.state.docLoading = false;
        }
    }

    applyDoc(doc) {
        this.state.doc = doc;
        this.state.draft = {
            name: doc.name, subject: doc.subject, body: doc.body,
            versions: clone(doc.versions) || {}, rules: clone(doc.rules) || {},
            page: { ...doc.page }, sign: null,
        };
        this.state.lang = doc.main_lang;
        this.state.person = this.state.person && this.state.doc ? this.state.person : doc.person;
        if (!this.state.person) { this.state.person = doc.person; }
        this.state.previewLang = this.state.person ? this.state.person.lang : doc.main_lang;
        this.state.dirty = false;
        this.state.editorKey += 1;
        this.state.pv = { html: "", hidden: 0, missing: [], values: {}, loading: true, error: "" };
        this.state.rightTab = "preview";
        this.state.savedAt = doc.changed_on || "";
    }

    async backToGallery(force = false) {
        if (this.state.dirty && !force) {
            this.state.dialog = { type: "leave", busy: false };
            return;
        }
        this.state.dialog = null;
        this.state.view = "gallery";
        this.state.doc = null;
        this.state.draft = null;
        this.api = null;
        await this.loadBoard();
    }
    async leaveDiscard() {
        if (this.state.doc) { this.store.drop(this.state.doc.id); }
        this.state.dirty = false;
        await this.backToGallery(true);
    }
    async leaveSave() {
        const ok = await this.save();
        if (ok) { await this.backToGallery(true); }
    }

    // ---------------------------------------------------------------- fields
    get fieldMap() {
        const out = {};
        for (const g of (this.state.doc && this.state.doc.catalogue) || []) {
            for (const f of g.fields) { out[f.key] = f; }
        }
        return out;
    }
    get fieldGroups() {
        const term = fold(this.state.fieldTerm);
        return ((this.state.doc && this.state.doc.catalogue) || []).map((g) => ({
            ...g, icon: FIELD_GROUP_ICON[g.key] || "braces",
            fields: g.fields.filter((f) => !f.missing && (!term || fold(f.label).includes(term)
                || fold(this.state.pv.values[f.key] || "").includes(term))),
        })).filter((g) => g.fields.length);
    }
    get missingFields() {
        const map = this.fieldMap;
        return ((this.state.doc && this.state.doc.missing) || []).filter((k) => map[k]);
    }
    isCollapsed(g) { return Boolean(this.state.collapsed[g.key]) && !this.state.fieldTerm; }
    toggleGroup(g) { this.state.collapsed[g.key] = !this.state.collapsed[g.key]; }
    fieldValue(f) {
        if (f.later) { return _t("When the letter is made"); }
        const v = this.state.pv.values[f.key];
        return v || "";
    }
    insertField(f) {
        if (!this.api || !this.hasEditor) { return; }
        this.api.insertField(f.key);
    }
    onFieldDrag(f, ev) {
        ev.dataTransfer.setData("text/pbds-field", f.key);
        ev.dataTransfer.setData("text/plain", f.label);
        ev.dataTransfer.effectAllowed = "copy";
    }
    removeMissing(key) {
        if (this.api) {
            const n = this.api.removeField(key);
            if (!n) {
                this.notification.add(_t("That field is not in this language’s wording. Check the other language tabs."), { type: "info" });
            }
        }
    }

    // ---------------------------------------------------------------- picker
    openPicker(at) {
        if (!this.hasEditor) { return; }
        at = at || { x: window.innerWidth / 2 - 150, y: 200 };
        const x = Math.min(Math.max(12, at.x), window.innerWidth - 320);
        const y = Math.min(at.y + 6, window.innerHeight - 340);
        this.state.picker = { x, y, term: "", index: 0 };
        setTimeout(() => { if (this.pickerInput.el) { this.pickerInput.el.focus(); } }, 0);
    }
    get pickerList() {
        const p = this.state.picker;
        if (!p) { return []; }
        const term = fold(p.term);
        const out = [];
        for (const g of (this.state.doc && this.state.doc.catalogue) || []) {
            for (const f of g.fields) {
                if (f.missing) { continue; }
                if (!term || fold(f.label).includes(term) || fold(g.label).includes(term)) {
                    out.push({ ...f, groupLabel: g.label });
                }
            }
        }
        return out.slice(0, 40);
    }
    onPickerInput(ev) { this.state.picker.term = ev.target.value; this.state.picker.index = 0; }
    onPickerKey(ev) {
        const p = this.state.picker;
        const list = this.pickerList;
        if (ev.key === "ArrowDown") { ev.preventDefault(); p.index = Math.min(list.length - 1, p.index + 1); }
        else if (ev.key === "ArrowUp") { ev.preventDefault(); p.index = Math.max(0, p.index - 1); }
        else if (ev.key === "Enter") { ev.preventDefault(); if (list[p.index]) { this.pick(list[p.index]); } }
        else if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); this.state.picker = null; if (this.api) { this.api.focus(); } }
    }
    pick(f) {
        this.state.picker = null;
        if (this.api) { this.api.insertField(f.key); }
    }

    // ---------------------------------------------------------------- editor
    get hasEditor() {
        const d = this.state.draft;
        if (!d) { return false; }
        return this.isMain || Boolean(d.versions[this.state.lang]);
    }
    get isMain() { return this.state.doc && this.state.lang === this.state.doc.main_lang; }
    get editorHtml() {
        const d = this.state.draft;
        if (this.isMain) { return d.body || ""; }
        return (d.versions[this.state.lang] || {}).body || "";
    }
    get subjectValue() {
        const d = this.state.draft;
        if (this.isMain) { return d.subject || ""; }
        return (d.versions[this.state.lang] || {}).subject || "";
    }
    onSubject(ev) {
        const d = this.state.draft;
        if (this.isMain) { d.subject = ev.target.value; } else if (d.versions[this.state.lang]) { d.versions[this.state.lang].subject = ev.target.value; }
        this.touched();
    }
    onName(ev) { this.state.draft.name = ev.target.value; this.touched(false); }
    onEditorReady(api) { this.api = api; }
    onEditorChange(html) {
        const d = this.state.draft;
        if (!d) { return; }
        if (this.isMain) { d.body = html; } else if (d.versions[this.state.lang]) { d.versions[this.state.lang].body = html; }
        this.touched();
    }
    touched(preview = true) {
        this.state.dirty = true;
        if (preview) { this.schedulePreview(); }
        clearTimeout(this._localTimer);
        this._localTimer = setTimeout(() => {
            if (this.state.doc && this.state.dirty) {
                this.store.set(this.state.doc.id, { at: Date.now(), draft: this.payload() });
            }
        }, 1200);
    }
    get sentences() {
        const out = {};
        const d = this.state.draft;
        const cond = this.state.doc && this.state.doc.conditions;
        for (const [id, rule] of Object.entries((d && d.rules) || {})) { out[id] = ruleSentence(rule, cond); }
        return out;
    }
    get editorPlaceholder() { return _t("Write the letter here. Press / to add a field."); }

    // ---------------------------------------------------------------- languages
    get langTabs() {
        const doc = this.state.doc;
        const d = this.state.draft;
        if (!doc || !d) { return []; }
        return doc.langs.map((l) => ({
            ...l,
            main: l.code === doc.main_lang,
            has: l.code === doc.main_lang || Boolean(d.versions[l.code]),
            translated: Boolean((doc.translated || {})[l.code]),
        }));
    }
    get mainLangName() {
        const doc = this.state.doc;
        const row = doc && doc.langs.find((l) => l.code === doc.main_lang);
        return row ? row.name : "English";
    }
    get curLangName() {
        const doc = this.state.doc;
        const row = doc && doc.langs.find((l) => l.code === this.state.lang);
        return row ? row.name : this.state.lang;
    }
    get curTranslated() { return Boolean(this.state.doc && (this.state.doc.translated || {})[this.state.lang]); }
    switchLang(code) {
        if (code === this.state.lang) { return; }
        this.state.lang = code;
        this.state.editorKey += 1;
        this.api = null;
        if (this.state.draft.versions[code] || code === this.state.doc.main_lang) {
            this.state.previewLang = code;
            this.schedulePreview(0);
        }
    }
    startVersion(from) {
        const d = this.state.draft;
        const code = this.state.lang;
        if (from === "translated") {
            const t = this.state.doc.translated[code];
            d.versions[code] = { subject: t.subject, body: t.body };
        } else if (from === "blank") {
            d.versions[code] = { subject: d.subject, body: "" };
        } else {
            d.versions[code] = { subject: d.subject, body: d.body };
        }
        this.state.editorKey += 1;
        this.state.previewLang = code;
        this.touched();
    }
    askRemoveVersion() {
        this.state.dialog = { type: "removeLang", lang: this.state.lang, name: this.curLangName };
    }
    doRemoveVersion() {
        const code = this.state.dialog.lang;
        this.state.draft.versions[code] = null;
        this.state.dialog = null;
        this.state.editorKey += 1;
        this.touched();
    }

    // ---------------------------------------------------------------- rules
    onRule(id, isNew) {
        if (!id) {
            this.notification.add(_t("Click in the paragraph you want to show only for some people, then press “Show only when…”."), { type: "info" });
            return;
        }
        const rule = (this.state.draft.rules || {})[id];
        this.state.ruleEdit = { id, isNew: isNew && !rule, rule: rule ? clone(rule) : null };
    }
    onRuleSave(rule) {
        const id = this.state.ruleEdit.id;
        this.state.draft.rules[id] = rule;
        this.state.ruleEdit = null;
        this.touched();
        if (this.api) { this.api.refreshPills(); }
    }
    onRuleRemove() {
        const id = this.state.ruleEdit.id;
        delete this.state.draft.rules[id];
        this.state.ruleEdit = null;
        if (this.api) { this.api.unwrapRule(id); }
        this.touched();
    }
    onRuleClose() {
        const edit = this.state.ruleEdit;
        this.state.ruleEdit = null;
        if (edit && edit.isNew && !this.state.draft.rules[edit.id] && this.api) {
            this.api.unwrapRule(edit.id);
        }
    }

    // ---------------------------------------------------------------- pictures
    chooseImage() { if (this.imgInput.el) { this.imgInput.el.click(); } }
    async uploadFile(file) {
        if (!file) { return null; }
        try {
            const data = await readBase64(file);
            const res = await this.orm.call(FACADE, "upload_image", [this.state.doc.id, { name: file.name, mime: file.type, data }]);
            if (!res || !res.ok) {
                this.notification.add((res && res.msg) || _t("The picture could not be added."), { type: "warning" });
            }
            return res;
        } catch (e) {
            this.notification.add(errorText(e, _t("The picture could not be read.")), { type: "warning" });
            return null;
        }
    }
    async onImageChosen(ev) {
        const file = ev.target.files && ev.target.files[0];
        ev.target.value = "";
        const res = await this.uploadFile(file);
        if (res && res.ok && this.api) { this.api.insertImage(res.url, res.name); }
    }

    // ---------------------------------------------------------------- page
    get styles() {
        const out = {};
        for (const s of (this.state.doc && this.state.doc.page_styles) || []) { out[s.key] = s; }
        return out;
    }
    get page() { return (this.state.draft && this.state.draft.page) || {}; }
    setPage(key, value) {
        this.state.draft.page[key] = value;
        this.touched();
    }
    onPageText(key, ev) { this.setPage(key, ev.target.value); }
    fontCss(key) {
        const opt = ((this.styles.font || {}).options || []).find((o) => o.value === key);
        return opt ? opt.css : "inherit";
    }
    get paperStyle() {
        const p = this.page;
        const m = MARGIN_PX[p.margins] || MARGIN_PX.normal;
        const top = Math.max(m[0] - 18, 14) * MM;
        const bottom = Math.max(m[1] - 10, 12) * MM;
        return `font-family: ${this.fontCss(p.font)}; font-size: ${p.size || 13}px; padding: ${top}px ${m[3] * MM}px ${bottom}px ${m[2] * MM}px; zoom: ${this.state.zoom};`;
    }
    get todayText() {
        const lang = (this.state.lang || "en_US").replace("_", "-");
        try {
            return new Date().toLocaleDateString(lang, { day: "numeric", month: "long", year: "numeric" });
        } catch {
            return new Date().toLocaleDateString();
        }
    }
    get signName() { return this.page.sign_name || (this.state.doc && this.state.doc.company.name) || ""; }
    get signTitle() { return this.page.sign_title || _t("Authorised signatory"); }
    get signUrl() {
        const s = this.state.draft && this.state.draft.sign;
        if (s === false) { return false; }
        if (s && s.url) { return s.url; }
        return this.state.doc && this.state.doc.sign_image_url;
    }
    chooseSign() { if (this.signInput.el) { this.signInput.el.click(); } }
    async onSignChosen(ev) {
        const file = ev.target.files && ev.target.files[0];
        ev.target.value = "";
        if (!file) { return; }
        if (!["image/png", "image/jpeg"].includes(file.type)) {
            this.notification.add(_t("Use a PNG or JPEG picture for the signature."), { type: "warning" });
            return;
        }
        if (file.size > 2 * 1024 * 1024) {
            this.notification.add(_t("The signature picture must be 2 MB or smaller."), { type: "warning" });
            return;
        }
        const data = await readBase64(file);
        this.state.draft.sign = { mime: file.type, data, url: `data:${file.type};base64,${data}` };
        if (this.page.sign !== "image") { this.state.draft.page.sign = "image"; }
        this.touched();
    }
    removeSign() { this.state.draft.sign = false; this.touched(); }

    // ---------------------------------------------------------------- desk
    measureDesk() {
        const el = this.desk.el;
        if (!el) { return; }
        const zoom = Math.max(0.5, Math.min(1, (el.clientWidth - 56) / A4_W));
        if (Math.abs(zoom - this.state.zoom) > 0.01) { this.state.zoom = Math.round(zoom * 100) / 100; }
    }
    measurePages() {
        const el = this.paper.el;
        if (!el) { return; }
        const pages = Math.max(1, Math.ceil((el.scrollHeight - 2) / A4_H));
        if (pages !== this.state.pages) { this.state.pages = pages; }
    }
    get pageBreaks() {
        const out = [];
        for (let i = 1; i < this.state.pages; i++) { out.push({ n: i + 1, top: i * A4_H, label: _t("Page %s", i + 1) }); }
        return out;
    }

    // ---------------------------------------------------------------- preview
    payload() {
        const d = this.state.draft;
        if (!d) { return {}; }
        const out = { name: d.name, subject: d.subject, body: d.body, versions: d.versions, rules: d.rules, page: d.page };
        if (d.sign === false) { out.sign_image = false; }
        else if (d.sign && d.sign.data) { out.sign_image = { mime: d.sign.mime, data: d.sign.data }; }
        return out;
    }
    schedulePreview(delay = 400) {
        clearTimeout(this._pvTimer);
        this._pvTimer = setTimeout(() => this.runPreview(), delay);
    }
    async runPreview() {
        const doc = this.state.doc;
        if (!doc || !this.state.person) { this.state.pv.loading = false; return; }
        const seq = ++this.pvSeq;
        this.state.pv.loading = true;
        try {
            const res = await this.orm.silent.call(FACADE, "preview",
                [doc.id, this.payload(), this.state.person.id, this.state.previewLang || false]);
            if (seq !== this.pvSeq || !this.state.doc) { return; }
            this.prevValues = this.state.pv.values || {};
            this.state.pv = { ...res, loading: false, error: "" };
            if (res.lang && res.lang !== this.state.previewLang) { this.state.previewLang = res.lang; }
        } catch (e) {
            if (seq !== this.pvSeq) { return; }
            this.state.pv.loading = false;
            this.state.pv.error = errorText(e, _t("The preview could not be drawn."));
        }
    }
    get pvDoc() {
        const html = this.state.pv.html || "";
        const cls = this.state.ghosts ? "pbds-show-ghosts" : "";
        return `<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src * data: blob:; font-src *"><style>${PV_STYLE}</style></head><body class="${cls}">${html}</body></html>`;
    }
    onPvLoad(ev) {
        const frame = ev.target;
        let doc = null;
        try { doc = frame.contentDocument; } catch { doc = null; }
        if (!doc || !doc.body) { return; }
        const h = Math.max(A4_H, doc.body.scrollHeight);
        frame.style.height = `${h}px`;
        if (frame === this.pvFrame.el) {
            this.state.pvHeight = h;
            this.measurePreview();
        }
        // values that changed since the last person glow for a moment
        const prev = this.prevValues || {};
        const now = this.state.pv.values || {};
        const changed = Object.keys(now).filter((k) => prev[k] !== undefined && prev[k] !== now[k]);
        for (const key of changed) {
            for (const span of doc.querySelectorAll(`.pbds-k-${CSS.escape(key)}`)) {
                span.classList.add("pbds-flash");
                setTimeout(() => span.classList.remove("pbds-flash"), 1400);
            }
        }
        this.prevValues = now;
    }
    measurePreview() {
        const box = this.pvBox.el;
        if (!box) { return; }
        const scale = Math.max(0.2, Math.min(1, (box.clientWidth - 2) / A4_W));
        if (Math.abs(scale - this.state.pvScale) > 0.005) { this.state.pvScale = scale; }
    }
    get pvWrapStyle() { return `height: ${Math.round(this.state.pvHeight * this.state.pvScale)}px;`; }
    get pvFrameStyle() { return `transform: scale(${this.state.pvScale}); height: ${this.state.pvHeight}px;`; }
    get hiddenText() {
        const n = this.state.pv.hidden;
        return n === 1 ? _t("1 paragraph is hidden for this person") : _t("%s paragraphs are hidden for this person", n);
    }
    toggleGhosts() { this.state.ghosts = !this.state.ghosts; }
    setRightTab(tab) { this.state.rightTab = tab; if (tab === "preview") { this.schedulePreview(0); } }
    onPreviewLang(ev) { this.state.previewLang = ev.target.value; this.schedulePreview(0); }
    get personLangName() {
        const p = this.state.person;
        return p ? p.lang_name : "";
    }
    initials(name) {
        return String(name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
    }
    openPeople() {
        this.state.peopleOpen = true;
        this.state.peopleTerm = "";
        this.searchPeople("");
        setTimeout(() => { if (this.peopleInput.el) { this.peopleInput.el.focus(); } }, 0);
    }
    onPeopleTerm(ev) {
        this.state.peopleTerm = ev.target.value;
        clearTimeout(this._peopleTimer);
        this._peopleTimer = setTimeout(() => this.searchPeople(this.state.peopleTerm), 250);
    }
    onPeopleKey(ev) {
        if (ev.key === "Escape") { ev.stopPropagation(); this.state.peopleOpen = false; }
        if (ev.key === "Enter" && this.state.people.length) { ev.preventDefault(); this.choosePerson(this.state.people[0]); }
    }
    async searchPeople(term) {
        this.state.peopleBusy = true;
        try {
            this.state.people = await this.orm.call(FACADE, "people", [term]);
        } catch {
            this.state.people = [];
        } finally {
            this.state.peopleBusy = false;
        }
    }
    choosePerson(p) {
        this.state.person = p;
        this.state.previewLang = p.lang;
        this.state.peopleOpen = false;
        this.schedulePreview(0);
    }
    async downloadPdf() {
        if (this.state.pdfBusy || !this.state.person) { return; }
        this.state.pdfBusy = true;
        try {
            const res = await this.orm.call(FACADE, "sample_pdf", [this.state.doc.id, this.payload(), this.state.person.id, this.state.previewLang || false]);
            if (!res.ok) {
                this.notification.add(res.msg, { type: "warning" });
                return;
            }
            const bytes = Uint8Array.from(atob(res.data), (c) => c.charCodeAt(0));
            const url = URL.createObjectURL(new Blob([bytes], { type: "application/pdf" }));
            const a = document.createElement("a");
            a.href = url;
            a.download = res.name;
            document.body.append(a);
            a.click();
            a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 4000);
            this.notification.add(_t("Sample PDF ready. Nothing was filed or sent."), { type: "success" });
        } catch (e) {
            this.notification.add(errorText(e, _t("The PDF could not be made right now.")), { type: "danger" });
        } finally {
            this.state.pdfBusy = false;
        }
    }

    // ---------------------------------------------------------------- save
    async save() {
        const doc = this.state.doc;
        if (!doc || this.state.saving) { return false; }
        if (!String(this.state.draft.name || "").trim()) {
            this.notification.add(_t("Give the document a name."), { type: "warning" });
            return false;
        }
        const open = Object.entries(this.state.draft.rules || {}).find(([, r]) => !(r.lines || []).length);
        if (open) {
            this.onRule(open[0], false);
            return false;
        }
        this.state.saving = true;
        try {
            const fresh = await this.orm.call(FACADE, "save", [doc.id, this.payload()]);
            this.store.drop(doc.id);
            // Keep the editor (caret, undo) — take the server's answers.
            Object.assign(this.state.doc, {
                revision: fresh.revision, edited: fresh.edited, can_reset: fresh.can_reset,
                catalogue: fresh.catalogue, missing: fresh.missing, sign_image: fresh.sign_image,
                sign_image_url: fresh.sign_image_url ? `${fresh.sign_image_url}?t=${Date.now()}` : false,
                versions: fresh.versions, changed_on: fresh.changed_on, changed_by: fresh.changed_by,
                name: fresh.name, rules: fresh.rules, page_set: fresh.page_set,
            });
            this.state.draft.sign = null;
            this.state.draft.rules = clone(fresh.rules) || {};
            this.state.dirty = false;
            this.state.savedAt = fresh.changed_on;
            this.notification.add(_t("Saved. Letters made from now on use this wording."), { type: "success" });
            return true;
        } catch (e) {
            this.notification.add(errorText(e, _t("Not saved. Try again.")), { type: "danger" });
            return false;
        } finally {
            this.state.saving = false;
        }
    }
    get saveText() {
        if (this.state.saving) { return _t("Saving…"); }
        if (this.state.dirty) { return _t("Unsaved changes"); }
        return this.state.savedAt ? _t("Saved %s", ago(this.state.savedAt)) : _t("No changes yet");
    }
    restoreLocal() {
        const kept = this.state.restore;
        this.state.restore = null;
        if (!kept || !kept.draft) { return; }
        const d = kept.draft;
        Object.assign(this.state.draft, {
            name: d.name, subject: d.subject, body: d.body, versions: d.versions || {},
            rules: d.rules || {}, page: { ...this.state.draft.page, ...(d.page || {}) },
        });
        this.state.editorKey += 1;
        this.api = null;
        this.touched();
        this.notification.add(_t("Your unsaved changes are back. Save to keep them."), { type: "info" });
    }
    discardLocal() {
        if (this.state.doc) { this.store.drop(this.state.doc.id); }
        this.state.restore = null;
    }
    get restoreWhen() {
        const r = this.state.restore;
        return r ? new Date(r.at).toLocaleString() : "";
    }

    // ---------------------------------------------------------------- keys
    onKey(ev) {
        const mod = ev.metaKey || ev.ctrlKey;
        if (ev.key === "Escape") {
            if (this.state.picker) { this.state.picker = null; return; }
            if (this.state.large) { this.state.large = false; return; }
            if (this.state.ruleEdit) { return; }
            if (this.state.dialog) { this.closeDialog(); return; }
            if (this.state.menu) { this.state.menu = 0; return; }
            if (this.state.peopleOpen) { this.state.peopleOpen = false; }
            return;
        }
        if (this.state.view === "designer" && mod && ev.key.toLowerCase() === "s") {
            ev.preventDefault();
            this.save();
            return;
        }
        if (this.state.view === "gallery" && ev.key === "/" && !mod) {
            const t = ev.target;
            const typing = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable);
            if (!typing && this.searchRef.el) {
                ev.preventDefault();
                this.searchRef.el.focus();
            }
        }
    }
}

registry.category("actions").add("pb_doc_studio", DocStudio);
