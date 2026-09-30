/** @odoo-module **/
/**
 * `pb_hiring_forms` — Application forms (RECRUIT P2, G-01 / G-02 / G-22 / G-23).
 *
 * Three panes: the forms on the left (templates, then each role's own copy),
 * the REAL public page in the middle (an iframe of `/hiring/preview/<id>` in
 * the language being edited), and the questions on the right.
 *
 * HERO MOMENT: type a question in Vietnamese on the right and watch the real
 * page change on the left as you type. The words are patched straight into
 * the preview (same origin), then saved 400 ms after the last key; anything
 * that changes the page's shape (order, required, a new question) redraws it.
 *
 * Undo, not confirm: removing a question, moving one, the required switch,
 * the default template and "Use this form for…" all offer Undo for five
 * seconds. The server (`pb.hiring._require_write`) decides who may change
 * anything; `can_edit` only decides what is OFFERED.
 */
import { Component, useState, onWillStart, useRef, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { useSortable } from "@web/core/utils/sortable_owl";

const TOAST_MS = 5000;
const SAVE_MS = 400;
const TEXTS = ["label", "help", "placeholder", "options"];

export class PbHiringForms extends Component {
    static template = "pb_hiring.PbHiringForms";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        if (this.env.config && this.env.config.setDisplayName) {
            this.env.config.setDisplayName(_t("Application forms"));
        }
        const ctx = (this.props.action && this.props.action.context) || {};
        this.state = useState({
            loaded: false, error: "", data: null,
            formId: ctx.pb_form_id || null, lang: "en_US",
            form: null, formBusy: false, formError: "",
            open: null, drafts: {}, consentDraft: "", nameDraft: "", editingName: false,
            device: "desktop", frameLoading: true, frameKey: 1, frameBroken: false,
            toast: null, showMissing: false, addOpen: false,
            roleTarget: "", changeTo: "", newName: "", naming: false, filter: "",
            saving: 0,
        });
        this.frameRef = useRef("frame");
        this.listRef = useRef("fields");
        this._timers = {};
        useSortable({
            enable: () => !!(this.state.form && this.state.form.can_edit),
            ref: this.listRef,
            elements: ".pbhr-ff-row.is-sortable",
            handle: ".pbhr-ff-grip",
            cursor: "grabbing",
            placeholderClasses: ["pbhr-ff-ph"],
            onDrop: ({ element, previous }) => this.onDrop(element, previous),
        });
        onWillStart(() => this.loadAll());
        onWillUnmount(() => {
            clearTimeout(this._toastTimer);
            for (const t of Object.values(this._timers)) { clearTimeout(t); }
        });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ================================================================ loading
    async loadAll() {
        try {
            const data = await this.orm.call("pb.hiring", "get_forms", []);
            this.state.data = data;
            const all = [...data.templates, ...data.role_forms];
            if (!this.state.formId || !all.find((f) => f.id === this.state.formId)) {
                const def = data.templates.find((t) => t.is_default) || data.templates[0] || data.role_forms[0];
                this.state.formId = def ? def.id : null;
            }
            this.state.loaded = true;
            if (this.state.formId) { await this.loadForm(); }
        } catch (e) {
            this.state.loaded = true;
            this.state.error = (e && e.data && e.data.message) || _t("Application forms could not be read.");
        }
    }

    async refreshList() {
        try {
            this.state.data = await this.orm.call("pb.hiring", "get_forms", []);
        } catch { /* the list is a courtesy; the open form still works */ }
    }

    async loadForm({ frame = true, keepOpen = true } = {}) {
        if (!this.state.formId) { return; }
        this.state.formBusy = true;
        try {
            const form = await this.orm.call("pb.hiring", "get_form", [this.state.formId, this.state.lang]);
            const drafts = {};
            for (const f of form.fields) {
                const miss = (f.missing && f.missing[this.state.lang]) || [];
                drafts[f.id] = {};
                for (const k of TEXTS) {
                    drafts[f.id][k] = this.state.lang !== "en_US" && miss.includes(k) ? "" : (f[k] || "");
                }
            }
            this.state.drafts = drafts;
            const consentMissing = this.state.lang !== "en_US" && form.form.consent_missing[this.state.lang];
            this.state.consentDraft = consentMissing ? "" : form.form.consent_text;
            this.state.nameDraft = form.form.name_en;
            if (!keepOpen || !form.fields.find((f) => f.id === this.state.open)) {
                if (this.state.open !== "consent") { this.state.open = null; }
            }
            this.state.form = form;
            this.state.formError = "";
            if (frame) { this.reloadFrame(); }
        } catch (e) {
            this.state.formError = (e && e.data && e.data.message) || _t("This form could not be read.");
        } finally {
            this.state.formBusy = false;
        }
    }

    async pickForm(id) {
        if (id === this.state.formId) { return; }
        this.state.formId = id;
        this.state.open = null;
        this.state.showMissing = false;
        this.state.addOpen = false;
        await this.loadForm();
    }

    async setLang(code) {
        const lg = this.langs.find((l) => l.code === code);
        if (!lg || !lg.installed || code === this.state.lang) { return; }
        this.state.lang = code;
        this.state.showMissing = false;
        await this.loadForm();
    }

    // ================================================================ getters
    get data() { return this.state.data || { templates: [], role_forms: [], roles: [], languages: [] }; }

    get langs() { return this.data.languages || []; }

    get form() { return this.state.form && this.state.form.form; }

    get fields() { return (this.state.form && this.state.form.fields) || []; }

    get canEdit() { return !!(this.state.form && this.state.form.can_edit); }

    get roleForms() {
        const f = (this.state.filter || "").trim().toLowerCase();
        const rows = this.data.role_forms || [];
        return f ? rows.filter((r) => (r.role || "").toLowerCase().includes(f) || (r.name || "").toLowerCase().includes(f)) : rows;
    }

    get langWord() {
        const lg = this.langs.find((l) => l.code === this.state.lang);
        return lg ? lg.label : "";
    }

    get notInstalled() { return this.langs.filter((l) => !l.installed); }

    get offLangs() {
        const on = (this.form && this.form.languages) || [];
        return this.langs.filter((l) => l.installed && on.includes(l.code) && !l.on_website);
    }

    get frameSrc() {
        if (!this.form) { return "about:blank"; }
        return `${this.form.preview_url}?lang=${this.state.lang}&v=${this.state.frameKey}`;
    }

    get missingHere() {
        const m = (this.state.form && this.state.form.missing) || {};
        return m[this.state.lang] || 0;
    }

    get missingList() {
        const m = (this.state.form && this.state.form.missing_list) || {};
        return m[this.state.lang] || [];
    }

    missingFor(code) {
        const m = (this.state.form && this.state.form.missing) || {};
        return m[code] || 0;
    }

    whatWord(what) {
        return { label: _t("question"), help: _t("help line"), placeholder: _t("example answer"),
            options: _t("options"), consent_text: _t("consent sentence") }[what] || what;
    }

    isOffered(code) { return ((this.form && this.form.languages) || []).includes(code); }

    fieldMissing(f) {
        return this.state.lang !== "en_US" && ((f.missing && f.missing[this.state.lang]) || []).length > 0;
    }

    formTitle(row) { return row.is_template ? row.name : (row.role || row.name); }

    formSub(row) {
        if (row.is_template) {
            const n = (row.used_by || []).length;
            return n ? (n === 1 ? _t("%s questions · used by 1 role", row.n_fields) : _t("%(q)s questions · used by %(n)s roles", { q: row.n_fields, n }))
                : _t("%s questions · not used by a role yet", row.n_fields);
        }
        return row.origin ? _t("From %(t)s · %(q)s questions", { t: row.origin, q: row.n_fields }) : _t("%s questions", row.n_fields);
    }

    rowMissing(row) {
        return Object.values(row.missing || {}).reduce((a, b) => a + b, 0);
    }

    kindWord(f) {
        if (f.locked) { return _t("Always asked"); }
        return f.builtin ? _t("Built-in · saved to the candidate") : f.kind_label;
    }

    isChoice(f) { return ["choice", "multi"].includes(f.widget); }

    isFile(f) { return ["file", "portfolio"].includes(f.widget); }

    hasKind(f, k) { return (f.file_kinds || "").split(",").includes(k); }

    get fileKinds() {
        return [
            { key: "pdf", label: "PDF" }, { key: "doc", label: _t("Word") },
            { key: "image", label: _t("JPG / PNG") }, { key: "zip", label: "ZIP" },
        ];
    }

    get portfolioModes() {
        return [
            { key: "either", label: _t("A file or a link") },
            { key: "file", label: _t("A file") },
            { key: "link", label: _t("A link") },
        ];
    }

    get consentPreview() {
        const d = this.data;
        return (this.state.consentDraft || (this.form && this.form.consent_text_en) || "")
            .replaceAll("{brand}", d.brand || "").replaceAll("{months}", String(d.retention_months || 12));
    }

    get rolesToOffer() {
        return (this.data.roles || []).filter((r) => r.state !== "closed");
    }

    get templates() { return this.data.templates || []; }

    get usedByCount() {
        const row = this.templates.find((t) => this.form && t.id === this.form.id);
        return row ? (row.used_by || []).length : 0;
    }

    // ================================================================ calls
    async call(verb, payload, { undo = null, reload = true, frame = true, quiet = false } = {}) {
        this.state.saving++;
        try {
            const res = await this.orm.call("pb.hiring", "act", [verb, payload]);
            if (reload) {
                await this.loadForm({ frame });
                await this.refreshList();
            }
            if (res && res.note && !quiet) { this.toast(res.note, undo ? () => undo(res) : null); }
            return res;
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
            if (reload) { await this.loadForm({ frame }); }
            return null;
        } finally {
            this.state.saving--;
        }
    }

    toast(text, undo) {
        clearTimeout(this._toastTimer);
        this.state.toast = { text, undo };
        this._toastTimer = setTimeout(() => { this.state.toast = null; }, TOAST_MS);
    }

    async runUndo() {
        const t = this.state.toast;
        this.state.toast = null;
        clearTimeout(this._toastTimer);
        if (t && t.undo) { await t.undo(); }
    }

    // ================================================================ preview
    frameDoc() {
        try {
            const el = this.frameRef.el;
            return el && el.contentDocument;
        } catch { return null; }
    }

    reloadFrame() {
        const doc = this.frameDoc();
        try { this._scrollY = doc && doc.defaultView ? doc.defaultView.scrollY : 0; } catch { this._scrollY = 0; }
        this.state.frameLoading = true;
        this.state.frameBroken = false;
        this.state.frameKey++;
    }

    onFrameLoad() {
        const doc = this.frameDoc();
        this.state.frameLoading = false;
        if (!doc || !doc.querySelector(".pb-apply")) {
            this.state.frameBroken = !!(this.form);
            return;
        }
        try {
            if (this._scrollY) { doc.defaultView.scrollTo(0, this._scrollY); }
        } catch { /* cross-origin: fine */ }
        if (this.state.open) { this.focusInPreview(this.state.open, false); }
    }

    frameQ(key) {
        const doc = this.frameDoc();
        return doc ? doc.querySelector(`.pba-q[data-key="${CSS.escape(key)}"]`) : null;
    }

    focusInPreview(fid, scroll = true) {
        const doc = this.frameDoc();
        if (!doc) { return; }
        for (const q of doc.querySelectorAll(".pba-q.pba-focus")) { q.classList.remove("pba-focus"); }
        const f = this.fields.find((x) => x.id === fid) || (fid === "consent" ? this.fields.find((x) => x.kind === "consent") : null);
        const q = f && this.frameQ(f.key);
        if (q) {
            q.classList.add("pba-focus");
            if (scroll) { q.scrollIntoView({ block: "center", behavior: "smooth" }); }
        }
    }

    /** The hero: the words land on the real page as they are typed. */
    patchPreview(f, what, text) {
        const q = this.frameQ(f.key);
        if (!q) { return; }
        const shown = text || f[what + "_en"] || "";
        if (what === "label") {
            const el = q.querySelector(".pba-label-text");
            if (el) { el.textContent = shown; }
            const en = q.querySelector(".pba-label .pba-en");
            if (en) { en.hidden = !!text; }
        } else if (what === "help") {
            const el = q.querySelector(".pba-help");
            if (el) { el.textContent = shown; el.hidden = !shown; }
        } else if (what === "placeholder") {
            const el = q.querySelector(".pba-in");
            if (el) { el.setAttribute("placeholder", shown); }
        }
        q.classList.remove("pba-flash");
        void q.offsetWidth;
        q.classList.add("pba-flash");
    }

    // ================================================================ editing
    toggleOpen(f) {
        this.state.open = this.state.open === f.id ? null : f.id;
        this.state.addOpen = false;
        if (this.state.open) { this.focusInPreview(f.id); }
    }

    openConsent() {
        this.state.open = this.state.open === "consent" ? null : "consent";
        if (this.state.open) { this.focusInPreview("consent"); }
    }

    onText(f, what, ev) {
        const value = ev.target.value;
        this.state.drafts[f.id][what] = value;
        if (what !== "options") { this.patchPreview(f, what, value); }
        const k = `${f.id}:${what}`;
        clearTimeout(this._timers[k]);
        this._timers[k] = setTimeout(() => this.saveText(f, what), SAVE_MS);
    }

    async saveText(f, what) {
        delete this._timers[`${f.id}:${what}`];
        const value = this.state.drafts[f.id] ? this.state.drafts[f.id][what] : "";
        if (what === "label" && this.state.lang === "en_US" && !(value || "").trim()) { return; }
        this.state.saving++;
        try {
            const res = await this.orm.call("pb.hiring", "act", ["form_field_save",
                { id: f.id, lang: this.state.lang, values: { [what]: value } }]);
            if (res && res.missing && this.state.form) { this.state.form.missing = res.missing; }
            const miss = (f.missing[this.state.lang] = (f.missing[this.state.lang] || []).filter((w) => w !== what));
            if (this.state.lang !== "en_US" && !(value || "").trim() && f[what + "_en"]) { miss.push(what); }
            if (this.state.lang === "en_US") { f[what + "_en"] = value; }
            f[what] = value;
            if (what === "options") { this.reloadFrame(); }
            const list = this.state.form.missing_list[this.state.lang] || [];
            this.state.form.missing_list[this.state.lang] = list.filter((m) => !(m.field_id === f.id && m.what === what))
                .concat(miss.includes(what) ? [{ field_id: f.id, key: f.key, what, label_en: f.label_en }] : []);
            if (what === "label") { this.refreshList(); }
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not save."), { type: "danger" });
        } finally {
            this.state.saving--;
        }
    }

    onConsent(ev) {
        this.state.consentDraft = ev.target.value;
        const q = this.fields.find((x) => x.kind === "consent");
        const el = q && this.frameQ(q.key) && this.frameQ(q.key).querySelector(".pba-consent-s");
        if (el) { el.textContent = this.consentPreview; }
        clearTimeout(this._timers.consent);
        this._timers.consent = setTimeout(() => this.saveConsent(), SAVE_MS);
    }

    async saveConsent() {
        delete this._timers.consent;
        const text = this.state.consentDraft;
        if (this.state.lang === "en_US" && !(text || "").trim()) { return; }
        await this.call("form_save", { id: this.form.id, lang: this.state.lang, values: { consent_text: text } },
            { reload: false, quiet: true });
        const cm = this.form.consent_missing;
        if (cm) { cm[this.state.lang] = this.state.lang !== "en_US" && !(text || "").trim(); }
        await this.loadForm({ frame: false });
    }

    async toggleRequired(f) {
        if (!this.canEdit || f.locked) { return; }
        const on = !f.required;
        await this.call("form_field_save", { id: f.id, lang: "en_US", values: { required: on } }, {
            undo: () => this.call("form_field_save", { id: f.id, lang: "en_US", values: { required: !on } }),
        });
    }

    async setPlain(f, values) {
        await this.call("form_field_save", { id: f.id, lang: "en_US", values }, { quiet: true });
    }

    async toggleFileKind(f, k) {
        const kinds = (f.file_kinds || "").split(",").filter((x) => x);
        const next = kinds.includes(k) ? kinds.filter((x) => x !== k) : [...kinds, k];
        if (!next.length) {
            this.notif.add(_t("Pick at least one kind of file."), { type: "warning" });
            return;
        }
        await this.setPlain(f, { file_kinds: next });
    }

    async setNumber(f, what, ev) {
        const n = parseInt(ev.target.value || "0", 10);
        await this.setPlain(f, { [what]: Number.isFinite(n) ? n : 0 });
    }

    async removeField(f) {
        if (f.locked) {
            this.notif.add(_t("%s is always asked, so it cannot be removed. You can rename it.", f.label_en), { type: "warning" });
            return;
        }
        this.state.open = null;
        await this.call("form_field_remove", { id: f.id }, {
            undo: (res) => this.call("form_field_restore", { saved: res.saved }),
        });
    }

    async addField(kind) {
        this.state.addOpen = false;
        const res = await this.call("form_field_add", { form_id: this.form.id, kind, lang: this.state.lang });
        if (res && res.id) {
            this.state.open = res.id;
            setTimeout(() => {
                const el = document.querySelector(`.pbhr-ff-row[data-id="${res.id}"] .pbhr-ff-label-in`);
                if (el) { el.focus(); el.select(); }
            }, 60);
        }
    }

    // ------------------------------------------------------------ order
    async onDrop(element, previous) {
        const id = Number(element.dataset.id);
        const order = this.fields.filter((f) => f.kind !== "consent").map((f) => f.id).filter((x) => x !== id);
        const prevId = previous ? Number(previous.dataset.id) : null;
        const at = prevId ? order.indexOf(prevId) + 1 : 0;
        order.splice(at, 0, id);
        await this.reorder(order);
    }

    async reorder(order) {
        const before = this.fields.map((f) => f.id);
        const consent = this.fields.filter((f) => f.kind === "consent").map((f) => f.id);
        await this.call("form_reorder", { form_id: this.form.id, ids: [...order, ...consent] }, {
            undo: () => this.call("form_reorder", { form_id: this.form.id, ids: before }),
        });
    }

    async nudge(f, delta) {
        const order = this.fields.filter((x) => x.kind !== "consent").map((x) => x.id);
        const i = order.indexOf(f.id);
        const j = i + delta;
        if (i < 0 || j < 0 || j >= order.length) { return; }
        [order[i], order[j]] = [order[j], order[i]];
        await this.reorder(order);
        setTimeout(() => {
            const el = document.querySelector(`.pbhr-ff-row[data-id="${f.id}"] .pbhr-ff-main`);
            if (el) { el.focus(); }
        }, 80);
    }

    onRowKey(ev, f) {
        if (ev.altKey && (ev.key === "ArrowUp" || ev.key === "ArrowDown")) {
            ev.preventDefault();
            if (this.canEdit && f.kind !== "consent") { this.nudge(f, ev.key === "ArrowUp" ? -1 : 1); }
            return;
        }
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            if (f.kind === "consent") { this.openConsent(); } else { this.toggleOpen(f); }
            return;
        }
        if (ev.key === "Escape") { this.state.open = null; }
        if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
            ev.preventDefault();
            const rows = [...document.querySelectorAll(".pbhr-ff-main")];
            const i = rows.indexOf(ev.currentTarget);
            const next = rows[i + (ev.key === "ArrowDown" ? 1 : -1)];
            if (next) { next.focus(); }
        }
    }

    onEditorKey(ev) {
        if (ev.key === "Escape") {
            ev.stopPropagation();
            const id = this.state.open;
            this.state.open = null;
            setTimeout(() => {
                const el = document.querySelector(`.pbhr-ff-row[data-id="${id}"] .pbhr-ff-main`);
                if (el) { el.focus(); }
            }, 30);
        }
    }

    // ------------------------------------------------------------ the form itself
    async toggleOffered(code) {
        if (code === "en_US" || !this.canEdit) { return; }
        const on = new Set(this.form.languages);
        if (on.has(code)) { on.delete(code); } else { on.add(code); }
        const before = [...this.form.languages];
        await this.call("form_save", { id: this.form.id, lang: "en_US", values: { language_codes: [...on] } }, {
            undo: () => this.call("form_save", { id: this.form.id, lang: "en_US", values: { language_codes: before } }),
        });
    }

    startName() {
        if (!this.canEdit) { return; }
        this.state.nameDraft = this.form.name_en;
        this.state.editingName = true;
        setTimeout(() => { const el = document.querySelector(".pbhr-ff-name-in"); if (el) { el.focus(); el.select(); } }, 30);
    }

    async saveName() {
        if (!this.state.editingName) { return; }
        this.state.editingName = false;
        const name = (this.state.nameDraft || "").trim();
        if (!name || name === this.form.name_en) { return; }
        const old = this.form.name_en;
        await this.call("form_save", { id: this.form.id, lang: "en_US", values: { name } }, {
            frame: false,
            undo: () => this.call("form_save", { id: this.form.id, lang: "en_US", values: { name: old } }, { frame: false }),
        });
    }

    onNameKey(ev) {
        if (ev.key === "Enter") { ev.preventDefault(); this.saveName(); }
        if (ev.key === "Escape") { ev.preventDefault(); this.state.editingName = false; }
    }

    async makeDefault() {
        const res = await this.call("form_set_default", { id: this.form.id }, {
            frame: false,
            undo: (r) => r.old_id && this.call("form_set_default", { id: r.old_id }, { frame: false }),
        });
        return res;
    }

    async useForRole() {
        const rid = Number(this.state.roleTarget);
        if (!rid) {
            this.notif.add(_t("Pick the role first."), { type: "warning" });
            return;
        }
        const res = await this.call("form_copy_to_role", { template_id: this.form.id, requisition_id: rid }, {
            frame: false,
            undo: (r) => this.call("form_restore_role", { requisition_id: rid, old_id: r.old_id }, { frame: false }),
        });
        if (res) { this.state.roleTarget = ""; }
    }

    async changeRoleForm() {
        const tid = Number(this.state.changeTo);
        const rid = this.form.requisition_id;
        if (!tid || !rid) {
            this.notif.add(_t("Pick the template first."), { type: "warning" });
            return;
        }
        const res = await this.call("form_copy_to_role", { template_id: tid, requisition_id: rid }, {
            reload: false,
            undo: async (r) => {
                const back = await this.call("form_restore_role", { requisition_id: rid, old_id: r.old_id }, { reload: false });
                if (back && back.id) { this.state.formId = back.id; await this.refreshList(); await this.loadForm(); }
            },
        });
        if (res && res.id) {
            this.state.changeTo = "";
            this.state.formId = res.id;
            await this.refreshList();
            await this.loadForm();
        }
    }

    startNewTemplate() {
        this.state.naming = true;
        this.state.newName = _t("%s (my version)", this.form.name_en);
        setTimeout(() => { const el = document.querySelector(".pbhr-ff-newname"); if (el) { el.focus(); el.select(); } }, 30);
    }

    onNewNameKey(ev) {
        if (ev.key === "Enter") { ev.preventDefault(); this.saveNewTemplate(); }
        if (ev.key === "Escape") { ev.preventDefault(); this.state.naming = false; }
    }

    async saveNewTemplate() {
        const name = (this.state.newName || "").trim();
        if (!name) { this.notif.add(_t("Name the new template."), { type: "warning" }); return; }
        const res = await this.call("form_new_template", { name, from_id: this.form.id }, { reload: false });
        if (res && res.id) {
            this.state.naming = false;
            this.state.formId = res.id;
            await this.refreshList();
            await this.loadForm();
        }
    }

    async archive() {
        const id = this.form.id;
        const res = await this.call("form_archive", { id }, {
            reload: false,
            undo: async () => { await this.call("form_archive", { id, undo: true }, { reload: false }); this.state.formId = id; await this.refreshList(); await this.loadForm(); },
        });
        if (res) {
            this.state.formId = null;
            await this.loadAll();
        }
    }

    openMissing(m) {
        this.state.showMissing = false;
        if (!m.field_id) { this.state.open = "consent"; this.focusInPreview("consent"); return; }
        this.state.open = m.field_id;
        this.focusInPreview(m.field_id);
        setTimeout(() => {
            const el = document.querySelector(`.pbhr-ff-row[data-id="${m.field_id}"] [data-what="${m.what}"]`);
            if (el) { el.focus(); }
        }, 60);
    }

    openInTab() {
        if (this.form) { window.open(`${this.form.preview_url}?lang=${this.state.lang}`, "_blank", "noopener"); }
    }

    openPublic() {
        if (this.form && this.form.public_url) { window.open(this.form.public_url, "_blank", "noopener"); }
    }

    async openBrand() {
        try {
            const res = await this.orm.call("pb.hiring", "act", ["open_brand", {}]);
            if (res && res.type) { await this.action.doAction(res, { onClose: () => this.reloadFrame() }); }
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That did not work."), { type: "danger" });
        }
    }

    openSetup() { this.action.doAction("pb_hiring.action_pb_hiring_setup"); }

    langTitle(lg) {
        if (!lg.installed) {
            return _t("%s is not installed on this system — ask your administrator to add it under Settings → Languages.", lg.label);
        }
        return "";
    }
}

registry.category("actions").add("pb_hiring_forms", PbHiringForms);
