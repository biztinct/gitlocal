/** @odoo-module **/
/**
 * R31 (FS-15) — the country picker of the Form builder, one component for
 * every place a country is added: own fields and standard fields, in the
 * Studio's settings column and in the Field library's sheets.
 *
 * On focus it opens a list: first the Countries of Work in use on this site
 * with the number of people (the People list's Country of Work figures,
 * `pb.form.studio._pbfs_countries_in_use`), then "Other countries", found by
 * typing (accents and case do not matter: "viet" finds "Việt Nam").
 * Keyboard: Arrow up / down, Enter picks, Escape closes (on the box itself —
 * FS10-5: a window listener inside the Studio never hears it).
 *
 * Also the small "Shown for" helpers the Studio and the Field library share,
 * so both read a standard field's rule the same way.
 */
import { Component, useState, useRef, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { fsIc } from "./fs_icons";
import { fold } from "./fs_words";

let SEQ = 0;
const MAX_OTHER = 8;

export class CountryPicker extends Component {
    static template = "pb_form_studio.CountryPicker";
    static props = {
        countries: { type: Array },                       // every country {id, name, code}
        inUse: { type: Array, optional: true },           // [{id, name, code, n}], most first
        noneCount: { type: Number, optional: true },      // people with no Country of Work
        chosen: { type: Array, optional: true },          // ids already picked
        offerNone: { type: Boolean, optional: true },     // offer "No Country of Work"
        noneChosen: { type: Boolean, optional: true },
        disabled: { type: Boolean, optional: true },
        placeholder: { type: String, optional: true },
        note: { type: Function, optional: true },         // (country) → a short note, e.g. "not used there"
        onPick: { type: Function },                       // (country | "none")
    };

    setup() {
        this.state = useState({ open: false, term: "", active: 0 });
        this.input = useRef("input");
        this.uid = "pbfb-cp-" + ++SEQ;
        this._blur = null;
        onWillUnmount(() => clearTimeout(this._blur));
    }

    ic(n, s = 14) { return fsIc(n, s); }
    get ph() { return this.props.placeholder || _t("Add a country…"); }
    get chosenSet() { return new Set(this.props.chosen || []); }
    get term() { return fold(this.state.term); }
    hit(c) {
        const t = this.term;
        return !t || fold(c.name).includes(t) || fold(c.code) === t;
    }
    get useItems() {
        return (this.props.inUse || []).filter((c) => !this.chosenSet.has(c.id) && this.hit(c))
            .map((c) => ({ key: "u" + c.id, country: c, n: c.n || 0 }));
    }
    get noneItem() {
        if (!this.props.offerNone || this.props.noneChosen) { return null; }
        const t = this.term;
        const label = _t("No Country of Work");
        if (t && !fold(label).includes(t)) { return null; }
        return { key: "none", none: true, n: this.props.noneCount || 0, label };
    }
    get otherItems() {
        const t = this.term;
        if (!t) { return []; }
        const used = new Set((this.props.inUse || []).map((c) => c.id));
        const chosen = this.chosenSet;
        const rank = (c) => (fold(c.name).startsWith(t) || fold(c.code) === t ? 0 : 1);
        return (this.props.countries || [])
            .filter((c) => !used.has(c.id) && !chosen.has(c.id) && this.hit(c))
            .sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name))
            .slice(0, MAX_OTHER)
            .map((c) => ({ key: "o" + c.id, country: c }));
    }
    /** Every pickable line, in screen order (the keyboard walks this). */
    get items() {
        const out = [...this.useItems];
        if (this.noneItem) { out.push(this.noneItem); }
        return out.concat(this.otherItems);
    }
    get hasInUse() { return (this.props.inUse || []).length > 0 || Boolean(this.props.offerNone); }
    get empty() { return !this.items.length; }
    get emptyText() {
        return this.term ? _t("No country matches") : _t("Every Country of Work in use is already chosen");
    }
    isActive(item) { return this.items.findIndex((x) => x.key === item.key) === this.state.active; }
    optId(item) { return this.uid + "-" + item.key; }
    get activeId() {
        const item = this.items[this.state.active];
        return this.state.open && item ? this.optId(item) : "";
    }
    peopleText(n) { return n === 1 ? _t("1 person") : _t("%s people", (n || 0).toLocaleString()); }
    noteOf(c) { return this.props.note ? this.props.note(c) || "" : ""; }

    onFocus() {
        if (this.props.disabled) { return; }
        clearTimeout(this._blur);
        this.state.open = true;
        this.state.active = 0;
    }
    onBlur() {
        // a click on a line lands first (the lines keep the focus on mousedown)
        this._blur = setTimeout(() => { this.state.open = false; }, 120);
    }
    onInput(ev) {
        this.state.term = ev.target.value;
        this.state.open = true;
        this.state.active = 0;
    }
    onKeydown(ev) {
        const n = this.items.length;
        if (ev.key === "ArrowDown") {
            ev.preventDefault();
            if (!this.state.open) { this.state.open = true; return; }
            this.state.active = n ? (this.state.active + 1) % n : 0;
            this.reveal();
        } else if (ev.key === "ArrowUp") {
            ev.preventDefault();
            this.state.active = n ? (this.state.active - 1 + n) % n : 0;
            this.reveal();
        } else if (ev.key === "Enter") {
            ev.preventDefault();
            const item = this.items[this.state.active];
            if (this.state.open && item) { this.pick(item); }
        } else if (ev.key === "Escape") {
            if (this.state.open || this.state.term) {
                ev.preventDefault();
                ev.stopPropagation();
                this.state.open = false;
                this.state.term = "";
            }
        } else if (ev.key === "Tab") {
            this.state.open = false;
        }
    }
    reveal() {
        setTimeout(() => {
            const el = document.getElementById(this.activeId);
            if (el && el.scrollIntoView) { el.scrollIntoView({ block: "nearest" }); }
        }, 0);
    }
    onItemDown(ev) { ev.preventDefault(); }
    pick(item) {
        if (this.props.disabled) { return; }
        this.props.onPick(item.none ? "none" : item.country);
        this.state.term = "";
        this.state.active = 0;
        if (this.input.el) { this.input.el.focus(); }
    }
    itemClass(item) { return { on: this.isActive(item) }; }
}

// ------------------------------------------------------------ "Shown for"
/** R31 — a standard field's "Shown for": {mode: 'all'|'only'|'none',
 * countries: [{id, name, code}], unset: people with no Country of Work}. */
export const SHOW_ALL = { mode: "all", countries: [], unset: true };
export const SHOW_NONE = { mode: "none", countries: [], unset: false };

export function showOnly(countries, unset = false) {
    const list = (countries || []).filter(Boolean);
    if (!list.length && !unset) { return SHOW_NONE; }
    const seen = new Set();
    const uniq = list.filter((c) => (seen.has(c.id) ? false : seen.add(c.id)));
    uniq.sort((a, b) => String(a.name).localeCompare(String(b.name)));
    return { mode: "only", countries: uniq, unset: Boolean(unset) };
}

export function showSame(a, b) {
    if (!a || !b || a.mode !== b.mode) { return false; }
    if (a.mode !== "only") { return true; }
    const ids = (s) => s.countries.map((c) => c.id).sort().join(",");
    return ids(a) === ids(b) && Boolean(a.unset) === Boolean(b.unset);
}

/** Shown wherever either says shown (a locked field is never shown less). */
export function showUnion(a, b) {
    if (a.mode === "all" || b.mode === "all") { return SHOW_ALL; }
    if (a.mode === "none") { return b; }
    if (b.mode === "none") { return a; }
    return showOnly([...a.countries, ...b.countries], a.unset || b.unset);
}

export function showCovers(a, b) { return showSame(showUnion(a, b), a); }

/** Does a field with `show` appear for people of this Country of Work? */
export function showApplies(show, countryId) {
    if (!show || show.mode === "all") { return true; }
    if (show.mode === "none") { return false; }
    if (!countryId) { return Boolean(show.unset); }
    return show.countries.some((c) => c.id === countryId);
}

/** "Only Vietnam", "Vietnam + Indonesia", "Vietnam + Indonesia + 2 more". */
export function showChipText(show) {
    if (!show) { return ""; }
    if (show.mode === "all") { return _t("All countries"); }
    if (show.mode === "none") { return _t("Hidden for everyone"); }
    const names = show.countries.map((c) => c.name);
    if (show.unset) { names.push(_t("no Country of Work")); }
    if (names.length === 1) { return _t("Only %s", names[0]); }
    if (names.length === 2) { return _t("%(a)s + %(b)s", { a: names[0], b: names[1] }); }
    return _t("%(a)s + %(b)s + %(n)s more", { a: names[0], b: names[1], n: names.length - 2 });
}

/** The words of a "Shown for" in a sentence (the settings column). */
export function showLongText(show) {
    if (!show) { return ""; }
    if (show.mode === "all") { return _t("All countries"); }
    if (show.mode === "none") { return _t("Hidden for everyone"); }
    const names = show.countries.map((c) => c.name);
    if (show.unset) { names.push(_t("people with no Country of Work")); }
    return _t("Only %s", names.join(", "));
}
