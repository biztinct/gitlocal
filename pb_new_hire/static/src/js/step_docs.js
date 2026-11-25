/** @odoo-module **/
/**
 * Step 5 — Details and documents (NEWHIRE P3a).
 *
 * The hero: flipping one row between "Ask <first name>" and "I have it". The
 * row opens its own little form or file drop, the right panel's "Who does
 * what" bar slides, and Payroll-ready tells the truth about the bank account.
 *
 * The list is the server's (`details_options`): which items this country of
 * work needs, whether the new person can be asked for each one on My
 * Payobook, and whether it may be left out. A choice that is not possible is
 * shown, disabled, with its reason (tooltip and sub-line) — never hidden.
 *
 * Files live in component memory only (`nh.files`), never in sessionStorage:
 * after a reload the rows that had one say "Add the file again".
 */
import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatFloat } from "@web/core/utils/numbers";
import { MODEL, icon, errorText, docItemsOf, docChoiceOf, docGapOf, haveValueOf, docTallyOf,
         FILE_MIMES, FILE_MAX, FILES_MAX } from "./studio_util";

const FOCUSABLE = 'button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
let SEQ = 0;

/** The 480 px slide-over (cloned from the Workforce setup studio's, WS14):
 *  Esc and the scrim close it, focus starts on the panel and Tab wraps. */
export class NhDrawer extends Component {
    static template = "pb_new_hire.Drawer";
    static props = { title: String, subtitle: { type: String, optional: true }, onClose: Function, slots: Object };

    setup() {
        this.icon = icon;
        this.panel = useRef("panel");
        this.titleId = `pbnh-drawer-t-${++SEQ}`;
        onMounted(() => this.panel.el?.focus({ preventScroll: true }));
    }
    onScrim(ev) {
        if (ev.target === ev.currentTarget) {
            this.props.onClose();
        }
    }
    onKey(ev) {
        if (ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();
            this.props.onClose();
            return;
        }
        if (ev.key !== "Tab") {
            return;
        }
        const items = [...this.panel.el.querySelectorAll(FOCUSABLE)].filter((n) => n.offsetParent !== null);
        if (!items.length) {
            return;
        }
        const first = items[0];
        const last = items[items.length - 1];
        if (ev.shiftKey && document.activeElement === first) {
            ev.preventDefault();
            last.focus();
        } else if (!ev.shiftKey && document.activeElement === last) {
            ev.preventDefault();
            first.focus();
        }
    }
}

export class StepDocs extends Component {
    static template = "pb_new_hire.StepDocs";
    static components = { NhDrawer };
    static props = { api: Object };

    setup() {
        this.icon = icon;
        this.nh = useState(this.props.api.nh);
        this.ui = useState({ drag: "", fileErr: {}, editor: null, editorBusy: false, editorErr: "", adding: "" });
        this.root = useRef("root");
        onWillUnmount(() => { this.ui.editor = null; });
    }

    get api() { return this.props.api; }
    get d() { return this.nh.draft; }
    get first() { return this.api.first; }
    get docs() { return this.nh.docs; }
    get loading() { return this.d.payroll_country && !this.docs; }
    get items() { return docItemsOf(this.nh); }
    get details() { return this.items.filter((i) => i.group === "details"); }
    get papers() { return this.items.filter((i) => i.group === "papers"); }
    get country() { return (this.docs && this.docs.country_name) || this.api.countryName; }
    get heading() { return _t("Who fills in the rest?"); }
    get intro() {
        return _t("For each item, choose whether you have it now or %s should give it. What you ask for is noted when the hire is approved.", this.first);
    }
    get papersTitle() { return _t("Papers for %s", this.country); }
    get detailsSub() { return _t("What %s gives is checked by HR before it is saved.", this.first); }
    err(field) { return this.nh.fieldErr[field] || ""; }

    // ------------------------------------------------------------ choices
    choice(item) { return docChoiceOf(this.nh, item); }
    options(item) {
        const ask = { key: "ask", label: _t("Ask %s", this.first), on: item.can_ask, why: item.ask_why_not };
        const have = { key: "have", label: _t("I have it"), on: item.can_have, why: "" };
        const skip = { key: "skip", label: _t("Not needed"), on: item.can_skip,
                       why: item.can_skip ? "" : _t("Needed before the first pay, so it cannot be left out.") };
        const later = { key: "later", label: _t("Later"), on: true, why: "" };
        return item.can_ask ? [ask, have, skip] : (item.can_skip ? [ask, have, later, skip] : [ask, have, later]);
    }
    setChoice(item, opt) {
        if (!opt.on) {
            this.api.toast(opt.why || _t("This is not possible for this item."), { kind: "info" });
            return;
        }
        this.api.setChoice(item.key, opt.key);
        if (opt.key === "have") {
            this.later(() => this.focusRow(item));
        }
    }
    focusRow(item) {
        const el = this.root.el?.querySelector(`[data-row="${item.key}"] .pbnh-doc-x input, [data-row="${item.key}"] .pbnh-doc-x select, [data-row="${item.key}"] .pbnh-drop`);
        el?.focus();
    }
    /** Arrows move between the possible answers; Enter on "I have it" opens its form. */
    onSegKey(ev, item) {
        const opts = this.options(item).filter((o) => o.on);
        const i = opts.findIndex((o) => o.key === this.choice(item));
        if (ev.key === "ArrowRight" || ev.key === "ArrowDown" || ev.key === "ArrowLeft" || ev.key === "ArrowUp") {
            ev.preventDefault();
            const step = ev.key === "ArrowRight" || ev.key === "ArrowDown" ? 1 : -1;
            const next = opts[(i + step + opts.length) % opts.length];
            this.api.setChoice(item.key, next.key);
            this.later(() => this.root.el?.querySelector(`[data-row="${item.key}"] .pbnh-seg button.is-on`)?.focus());
        } else if (ev.key === "Enter" && !(ev.metaKey || ev.ctrlKey)) {
            ev.preventDefault();
            ev.stopPropagation();
            if (this.choice(item) !== "have" && item.can_have) {
                this.api.setChoice(item.key, "have");
            }
            this.later(() => this.focusRow(item));
        }
    }
    /** After OWL has drawn the change (the opened form is no longer inert). */
    later(fn) {
        setTimeout(fn, 60);
    }
    optClass(item, opt) {
        return (this.choice(item) === opt.key ? "is-on" : "") + (opt.on ? "" : " is-off");
    }
    tabIndex(item, opt) { return this.choice(item) === opt.key ? "0" : "-1"; }
    needChip(item) {
        return item.need === "first_pay" ? { cls: "pbnh-chip--warn", text: _t("Needed before first pay") }
            : item.need === "joining" ? { cls: "pbnh-chip--p", text: _t("Asked at joining") }
            : { cls: "", text: _t("Optional") };
    }
    rowSub(item) {
        const c = this.choice(item);
        if (c === "ask") {
            return item.ask_note || _t("%s gives it on My Payobook after the hire is approved.", this.first);
        }
        if (c === "later") {
            return item.ask_why_not || _t("Left for later. Add it on the record.");
        }
        if (c === "skip") {
            return _t("Not asked for.");
        }
        const gap = docGapOf(this.nh, item);
        if (gap === "again") {
            return _t("The page was reloaded, so the file is no longer here. Add the file again.");
        }
        if (gap === "file") {
            return _t("Attach the %s to finish this row.", item.upload.label);
        }
        if (gap === "expiry") {
            return _t("Type the date the %s is valid until.", item.upload.label);
        }
        return item.sub;
    }
    rowClass(item) {
        const c = this.choice(item);
        const gap = docGapOf(this.nh, item);
        return `pbnh-row pbnh-doc is-${c}${gap ? " is-gap" : ""}${gap === "again" ? " is-again" : ""}`;
    }
    isOpen(item) { return this.choice(item) === "have"; }

    // ------------------------------------------------------------ presets
    get canAskAll() { return this.items.some((i) => this.choice(i) !== (i.can_ask ? "ask" : "later")); }
    get canHaveAll() { return this.items.some((i) => i.can_have && this.choice(i) !== "have"); }
    /** Everything the person can give is asked; what only HR keeps goes
     *  back to "Later" (nothing is left half-typed). */
    askAll() { this.api.setChoices(Object.fromEntries(this.items.map((i) => [i.key, i.can_ask ? "ask" : "later"]))); }
    haveAll() { this.api.setChoices(Object.fromEntries(this.items.filter((i) => i.can_have).map((i) => [i.key, "have"]))); }
    get askAllLabel() { return _t("Ask %s for everything", this.first); }

    // ------------------------------------------------------------ typed values
    fid(f) { return `pbnh-f-have-${f.name}`; }
    value(f) {
        const v = haveValueOf(this.nh, f.name);
        return v === undefined || v === null || v === false ? "" : String(v);
    }
    placeholder(item, f) {
        if (item.key === "bank" && f.name === "account_holder") {
            return String(this.d.name || "").trim();
        }
        return "";
    }
    onValue(f, ev) {
        const v = ev.target.value;
        if (f.name === "private_phone" && !String(this.d.personal || "").includes("@")
                && (this.d.have || {}).private_phone === undefined) {
            // one source of truth: step 1's personal phone
            this.api.set("personal", v);
            return;
        }
        this.api.setHave(f.name, v);
    }
    inputType(f) { return f.kind === "date" ? "date" : f.kind === "phone" ? "tel" : "text"; }
    listId(f) { return `pbnh-banks-${f.name}`; }
    isRequired(item, f) { return f.required && !(item.key === "bank" && f.name === "account_holder"); }

    // ------------------------------------------------------------ files
    file(item) { return (this.nh.files || {})[item.key] || null; }
    meta(item) { return (this.d.file_meta || {})[item.key] || null; }
    fileErr(item) { return this.ui.fileErr[item.key] || this.err(`file-${item.key}`); }
    dropLabel(item) {
        return this.ui.drag === item.key ? _t("Let go to attach it") : _t("Drop the %s here, or choose it", item.upload.label);
    }
    size(bytes) {
        const mb = bytes / (1024 * 1024);
        return mb >= 1 ? _t("%s MB", formatFloat(mb, { digits: [69, 1] })) : _t("%s KB", Math.max(1, Math.round(bytes / 1024)));
    }
    pick(item) {
        this.root.el?.querySelector(`#pbnh-file-${item.key}`)?.click();
    }
    onDragOver(item, ev) {
        ev.preventDefault();
        this.ui.drag = item.key;
    }
    onDragLeave(item) {
        if (this.ui.drag === item.key) {
            this.ui.drag = "";
        }
    }
    onDrop(item, ev) {
        ev.preventDefault();
        this.ui.drag = "";
        const f = ev.dataTransfer?.files?.[0];
        if (f) {
            this.take(item, f);
        }
    }
    onFileInput(item, ev) {
        const f = ev.target.files && ev.target.files[0];
        ev.target.value = "";
        if (f) {
            this.take(item, f);
        }
    }
    /** The side panel's own rules and sentences, before anything is read. */
    take(item, f) {
        delete this.ui.fileErr[item.key];
        if (!FILE_MIMES.includes(f.type)) {
            this.ui.fileErr[item.key] = _t("Only JPG, PNG or PDF documents are accepted.");
            return;
        }
        if (!f.size || f.size > FILE_MAX) {
            this.ui.fileErr[item.key] = _t("Choose a non-empty file up to 10 MB.");
            return;
        }
        const others = Object.entries(this.nh.files || {}).filter(([k]) => k !== item.key)
            .reduce((n, [, x]) => n + (x.size || 0), 0);
        if (others + f.size > FILES_MAX) {
            this.ui.fileErr[item.key] = _t("The selected files must total 50 MB or less.");
            return;
        }
        const reader = new FileReader();
        reader.onload = () => {
            const data = String(reader.result || "").split(",")[1] || "";
            this.api.setFile(item.key, { name: f.name, mime: f.type, size: f.size, data });
            this.later(() => this.root.el?.querySelector(`[data-row="${item.key}"] .pbnh-file-x`)?.focus());
        };
        reader.onerror = () => { this.ui.fileErr[item.key] = _t("The selected file could not be read."); };
        reader.readAsDataURL(f);
    }
    removeLabel(item) { return _t("Remove %s", (this.file(item) || {}).name || ""); }
    removeFile(item) {
        this.api.setFile(item.key, null);
        this.later(() => this.root.el?.querySelector(`[data-row="${item.key}"] .pbnh-drop`)?.focus());
    }
    onDate(item, which, ev) { this.api.setFileDate(item.key, which, ev.target.value); }
    dateValue(item, which) { return (this.meta(item) || {})[which] || ""; }
    expiryLabel(item) { return item.upload.needs_expiry ? _t("Valid until") : _t("Valid until (if it has a date)"); }

    // ------------------------------------------------------------ summary card
    get tally() { return docTallyOf(this.nh); }
    get asked() { return this.items.filter((i) => this.choice(i) === "ask"); }
    get summaryTitle() {
        const n = this.asked.length;
        return !n ? _t("Nothing to ask %s for", this.first)
            : n === 1 ? _t("%s will be asked for 1 thing", this.first)
            : _t("%(first)s will be asked for %(n)s things", { first: this.first, n });
    }
    get summaryLine() {
        return this.asked.length
            ? _t("After the hire is approved, %s is asked for these on My Payobook. The welcome message that asks for them is switched on in the next release.", this.first)
            : _t("You have everything, so %s is not asked for anything before the first day.", this.first);
    }

    // ------------------------------------------------------------ the editor
    get editable() { return Boolean(this.docs && this.docs.papers_editable); }
    get editLabel() { return _t("Change what is asked in %s", this.country); }
    get editorTitle() { return _t("Papers for %s", this.country); }
    get editorSub() { return _t("What every new person in %s is asked for. Your changes apply to the next people you add.", this.country); }
    async openEditor() {
        this.ui.editorErr = "";
        try {
            const data = await this.api.orm.call(MODEL, "papers_edit_load", [this.d.payroll_country]);
            this.ui.editor = { ...data, rows: data.rows.map((r) => ({ ...r })) };
            this.ui.adding = "";
        } catch (e) {
            this.api.toast(errorText(e), { kind: "error" });
        }
    }
    closeEditor() {
        this.ui.editor = null;
        requestAnimationFrame(() => this.root.el?.querySelector(".pbnh-doc-edit")?.focus());
    }
    setNeed(row, ev) { row.need = ev.target.value; }
    setLabel(row, ev) { row.label = ev.target.value; }
    addRow() {
        const ed = this.ui.editor;
        const id = Number(this.ui.adding);
        const cat = (ed.others || []).find((o) => o.category_id === id);
        if (!cat) {
            return;
        }
        ed.rows.push({ category_id: cat.category_id, name: cat.name, need: "optional", label: cat.name, usual: "none", usual_label: cat.name });
        ed.others = ed.others.filter((o) => o.category_id !== id);
        this.ui.adding = "";
    }
    changed(row) { return row.need !== row.usual; }
    needLabel(value) { return ((this.ui.editor && this.ui.editor.needs) || []).find((n) => n.value === value)?.label || ""; }
    usualLine(row) {
        return row.usual === "none" ? _t("Not on the usual list") : _t("Usually: %s", this.needLabel(row.usual));
    }
    async saveEditor() {
        const ed = this.ui.editor;
        this.ui.editorBusy = true;
        try {
            await this.api.orm.call(MODEL, "papers_edit_save", [this.d.payroll_country,
                ed.rows.map((r) => ({ category_id: r.category_id, need: r.need, label: r.label }))]);
            this.closeEditor();
            this.api.refreshDocs();
            this.api.refreshDecides();
            this.api.toast(_t("Saved. New people in %s are asked for this list.", this.country));
        } catch (e) {
            this.ui.editorErr = errorText(e);
        } finally {
            this.ui.editorBusy = false;
        }
    }
    async resetEditor() {
        this.ui.editorBusy = true;
        try {
            const data = await this.api.orm.call(MODEL, "papers_edit_reset", [this.d.payroll_country]);
            this.ui.editor = { ...data, rows: data.rows.map((r) => ({ ...r })) };
            this.api.refreshDocs();
            this.api.refreshDecides();
            this.api.toast(_t("Back to the usual list for %s.", this.country));
        } catch (e) {
            this.ui.editorErr = errorText(e);
        } finally {
            this.ui.editorBusy = false;
        }
    }
    goRole() { this.api.go("role", "payroll_country"); }
}
