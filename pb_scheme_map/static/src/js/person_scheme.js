/** @odoo-module **/
/**
 * PSCHEME P1 F — the person's own pay scheme on screen.
 *
 *  * `PersonSchemeBlock` — the "Pay scheme" block of the employee side panel
 *    (a panel group of kind `pb_scheme`, drawn inside the panel's own section
 *    by template inheritance; the server sends `person_scheme` in it).
 *  * `ChangePaySchemeDialog` — "Change pay scheme": radio cards, the
 *    mid-month advance switch, the From date with the one-payslip-a-month
 *    sentence live under it, one primary button whose words follow the
 *    approval lane. Reused by the contract drawer through the registry
 *    category `pb_person_scheme` (pb_contracts never depends on this module).
 *
 * Hero moment: open a person, read in one line who pays them and since when;
 * press Change, pick a card, and the line behind the dialog rewrites itself
 * with the date before the dialog is closed.
 *
 * OWL markup flicker (ledger): icons are cached markup objects, never a new
 * `markup()` per paint; the "just changed" motion is keyed on a counter.
 */
import { Component, onMounted, onWillStart, useRef, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { Employee360Drawer } from "@pb_employee_vault/js/employee_360";
import { ic } from "@pb_import_kit/js/import_icons";

const { DateTime } = luxon;
const BOARD = "pb.scheme.board";

// The shared Lucide set of the import kit (never a glyph font, never an
// emoji). The kit's `ic()` makes a NEW markup object per call; a new markup
// per paint re-inserts the DOM (ledger: OWL markup flicker), so one object is
// kept per icon and size.
const CACHE = {};
export function psIc(name, size = 15) {
    const key = name + ":" + size;
    if (!CACHE[key]) {
        CACHE[key] = ic(name, size);
    }
    return CACHE[key];
}

function errorText(e, fallback) {
    const data = (e && e.data) || (e && e.message && e.message.data);
    return (data && data.message) || fallback || _t("That did not work. Try again.");
}

function day(iso) { return iso ? DateTime.fromISO(iso) : null; }
export function dayWords(iso) {
    const d = day(iso);
    return d && d.isValid ? d.toFormat("d LLL yyyy") : "";
}
export function monthWords(iso) {
    const d = day(iso);
    return d && d.isValid ? d.toFormat("LLLL yyyy") : "";
}

export async function loadPersonScheme(orm, employeeId) {
    return orm.call(BOARD, "person_scheme", [Number(employeeId)]);
}

// ===================================================================
//  The dialog
// ===================================================================
export class ChangePaySchemeDialog extends Component {
    static template = "pb_scheme_map.ChangePaySchemeDialog";
    static components = { Dialog };
    static props = {
        employeeId: Number,
        data: { type: Object, optional: true },
        onSaved: { type: Function, optional: true },
        close: Function,
        // PSCHEME P2a D: preselect a card, lead with a question, name Cancel
        pick: { type: Number, optional: true },
        lead: { type: String, optional: true },
        cancelLabel: { type: String, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.ic = psIc;
        this.cards = useRef("cards");
        this.state = useState({
            loading: !this.props.data, data: this.props.data || null,
            pick: 0, advance: false, date: "", others: false,
            busy: false, error: "", done: null,
        });
        onWillStart(async () => {
            if (!this.state.data) {
                try {
                    this.state.data = await loadPersonScheme(this.orm, this.props.employeeId);
                } catch (e) {
                    this.state.error = errorText(e, _t("The pay scheme could not be read. Close this and try again."));
                }
                this.state.loading = false;
            }
            this.reset();
        });
        onMounted(() => setTimeout(() => this.focusCard(), 60));
    }

    reset() {
        const d = this.state.data;
        if (!d || !d.found) {
            return;
        }
        this.state.date = d.default_date;
        const wanted = this.props.pick
            || (d.country_mismatch && d.country_mismatch.target_id) || 0;
        // a person paid by another country's scheme: never preselect the
        // scheme that is wrong for them — the fitting one, or nothing
        const fallback = d.country_mismatch ? 0 : ((d.main && d.main.id) || 0);
        const mine = (wanted && d.choices.concat(d.others).some((c) => c.id === wanted))
            ? wanted : fallback;
        const inMine = d.choices.some((c) => c.id === mine);
        const inOthers = d.others.some((c) => c.id === mine);
        this.state.pick = mine && (inMine || inOthers) ? mine : 0;
        this.state.others = Boolean(mine && !inMine && inOthers) || !d.choices.length && !d.employee.country_name;
        this.state.advance = this.defaultAdvance(this.state.pick);
    }

    // ---------------------------------------------------------- the words
    get d() { return this.state.data || {}; }
    get title() { return _t("Change pay scheme"); }
    get person() { return (this.d.employee && this.d.employee.name) || ""; }
    get firstName() { return (this.d.employee && this.d.employee.first_name) || this.person; }
    get countryName() { return (this.d.employee && this.d.employee.country_name) || ""; }
    get lead() {
        return this.countryName
            ? _t("Pay schemes for %(country)s come first, because %(name)s works there.",
                { country: this.countryName, name: this.firstName })
            : _t("%s has no Country of work yet, so every pay scheme is shown.", this.firstName);
    }
    get choices() { return this.d.choices || []; }
    get others() { return this.d.others || []; }
    get shownCards() {
        if (!this.countryName) {
            return this.choices.concat(this.others);
        }
        return this.state.others ? this.choices.concat(this.others) : this.choices;
    }
    get noneForCountry() { return Boolean(this.countryName) && !this.choices.length; }
    get noneLine() { return _t("No pay scheme for %s yet", this.countryName); }
    get othersLabel() {
        return this.state.others ? _t("Hide pay schemes of other countries")
            : _t("Show pay schemes of other countries (%s)", this.others.length);
    }
    toggleOthers() { this.state.others = !this.state.others; }
    meta(c) {
        const people = c.people === 1 ? _t("pays 1 person") : _t("pays %s people", c.people || 0);
        return [c.currency, c.kind_words, people].filter(Boolean).join(" · ");
    }
    isCurrent(c) { return Boolean(this.d.main && this.d.main.id === c.id); }
    isOther(c) { return Boolean(this.countryName) && !this.choices.some((x) => x.id === c.id); }
    get pickedIsOther() {
        const c = this.shownCards.find((x) => x.id === this.state.pick);
        return Boolean(c && this.isOther(c));
    }

    // ---------------------------------------------------------- the cards
    pick(c) {
        if (this.state.pick === c.id) {
            return;
        }
        this.state.pick = c.id;
        this.state.advance = this.defaultAdvance(c.id);
        this.state.error = "";
    }
    onCardKey(c, ev) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.pick(c);
            return;
        }
        const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[ev.key];
        if (!step) {
            return;
        }
        ev.preventDefault();
        const list = this.shownCards;
        const at = list.findIndex((x) => x.id === c.id);
        const next = list[(at + step + list.length) % list.length];
        if (next) {
            this.pick(next);
            setTimeout(() => this.focusCard(), 60);
        }
    }
    focusCard() {
        const host = this.cards.el;
        const el = host && (host.querySelector(".smp-ps-card.is-on") || host.querySelector(".smp-ps-card"));
        if (el) {
            el.focus();
        }
    }

    // ---------------------------------------------------------- the advance
    advancesFor(id) {
        const paired = ((this.d.advances || {})[String(id)] || []).slice();
        const now = this.d.advance;
        if (now && id && !paired.some((a) => a.id === now.id)) {
            const card = this.choices.concat(this.others).find((c) => c.id === id);
            if (card && card.country_code === now.country_code) {
                paired.push({ id: now.id, name: now.name });
            }
        }
        return paired;
    }
    defaultAdvance(id) {
        if (!id) {
            return false;
        }
        const list = this.advancesFor(id);
        const now = this.d.advance;
        if (now && list.some((a) => a.id === now.id)) {
            return now.id;
        }
        return list.length === 1 ? list[0].id : false;
    }
    get advances() { return this.advancesFor(this.state.pick); }
    get oneAdvance() { return this.advances.length === 1 ? this.advances[0] : null; }
    get advanceOn() { return Boolean(this.state.advance); }
    toggleAdvance() {
        const one = this.oneAdvance;
        this.state.advance = this.state.advance ? false : (one ? one.id : false);
    }
    onAdvanceSelect(ev) { this.state.advance = Number(ev.target.value) || false; }
    isAdvance(a) { return this.state.advance === a.id; }
    get advanceLine() {
        const one = this.oneAdvance;
        return one ? _t("Mid-month advance: %s", one.name) : "";
    }

    // ---------------------------------------------------------- the date
    onDate(ev) { this.state.date = ev.target.value; this.state.error = ""; }
    get dateLine() {
        const iso = this.state.date;
        const d = day(iso);
        if (!d || !d.isValid) {
            return _t("Pick the first day the new pay scheme pays.");
        }
        const own = this.d.main && this.d.main.own;
        if (d.day !== 1 && own) {
            return _t("A change during a month starts with the next pay run. %(old)s still pays %(month)s.",
                { old: this.d.main.name, month: monthWords(iso) });
        }
        if (d.day !== 1) {
            return _t("First pay run: %s. A first pay scheme pays that whole month.", monthWords(iso));
        }
        return _t("First pay run: %s", monthWords(iso));
    }
    get dateIsMid() {
        const d = day(this.state.date);
        return Boolean(d && d.isValid && d.day !== 1 && this.d.main && this.d.main.own);
    }

    // ------------------------------------------- PSCHEME P2a E.2: currency
    get cancelLabel() { return this.props.cancelLabel || _t("Cancel"); }
    get currencyLine() {
        const c = this.choices.concat(this.others).find((x) => x.id === this.state.pick);
        const k = this.d.contract;
        if (!c || !k || !c.contract_currency || c.contract_currency === k.currency
                || !c.country_code || c.country_code === k.country) {
            return "";
        }
        return _t("This also changes their contract's currency to %(currency)s from %(date)s.",
            { currency: c.contract_currency, date: dayWords(this.state.date) });
    }

    // ---------------------------------------------------------- the button
    get route() { return this.d.lane === "route"; }
    get primaryLabel() { return this.route ? _t("Ask for this change") : _t("Change pay scheme"); }
    get sameReason() {
        const d = this.d;
        if (!this.state.pick || !d.main || d.main.id !== this.state.pick || !d.main.own) {
            return "";
        }
        const now = (d.advance && d.advance.id) || false;
        if ((this.state.advance || false) !== now) {
            return "";
        }
        return _t("%s is already their pay scheme. Pick another card, or change the advance.", d.main.name);
    }
    get disabledReason() {
        if (this.d.blocked) {
            return this.d.blocked;
        }
        if (this.d.waiting) {
            return _t("A change is already waiting for approval: %(scheme)s from %(date)s.",
                { scheme: this.d.waiting.scheme, date: this.d.waiting.date_words });
        }
        if (!this.state.pick) {
            return _t("Pick a pay scheme first.");
        }
        if (!this.state.date) {
            return _t("Pick the first day the new pay scheme pays.");
        }
        return this.sameReason;
    }
    get canSave() { return !this.state.busy && !this.disabledReason; }
    get pickedName() {
        const c = this.choices.concat(this.others).find((x) => x.id === this.state.pick);
        return c ? c.name : "";
    }
    async save() {
        if (!this.canSave) {
            return;
        }
        this.state.busy = true;
        this.state.error = "";
        try {
            const answer = await this.orm.call(BOARD, "person_set", [
                [this.props.employeeId], this.state.pick, this.state.advance || false, this.state.date]);
            if (answer && answer.ok === false) {
                this.state.error = answer.message || _t("That did not work. Try again.");
                return;
            }
            const saved = Boolean(answer && (answer.applied || answer.saved));
            this.state.done = {
                saved,
                head: saved ? _t("Saved") : _t("Sent for approval"),
                line: saved
                    ? _t("%(name)s is paid by %(scheme)s from %(date)s.",
                        { name: this.firstName, scheme: this.pickedName, date: dayWords(this.state.date) })
                    : (answer && answer.message) || _t("Sent for approval."),
            };
            if (this.props.onSaved) {
                await this.props.onSaved(answer);
            }
            setTimeout(() => document.querySelector(".smp-ps-done-go")?.focus(), 60);
        } catch (e) {
            this.state.error = errorText(e);
        } finally {
            this.state.busy = false;
        }
    }
    onKeydown(ev) {
        if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) {
            ev.preventDefault();
            this.save();
        }
    }
    openMapping() {
        this.props.close();
        this.action.doAction("pb_formula_studio.action_pb_mapping_studio",
            { additionalContext: { pb_focus: "scheme" } }).catch(() => {});
    }
}

/** Opens the dialog; focus goes back to `opener` when it closes (F.2). */
export function openChangePayScheme(dialog, { employeeId, data, onSaved, opener, onClose, pick, lead, cancelLabel }) {
    const props = { employeeId: Number(employeeId), data, onSaved };
    if (pick) { props.pick = Number(pick); }
    if (lead) { props.lead = lead; }
    if (cancelLabel) { props.cancelLabel = cancelLabel; }
    dialog.add(ChangePaySchemeDialog, props, {
        onClose: () => {
            if (onClose) {
                onClose();
            }
            setTimeout(() => opener && opener.isConnected && opener.focus(), 30);
        },
    });
}

// ===================================================================
//  The block on the side panel
// ===================================================================
export class PersonSchemeBlock extends Component {
    static template = "pb_scheme_map.PersonSchemeBlock";
    static props = { block: Object, employeeId: [Number, String] };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.action = useService("action");
        this.ic = psIc;
        this.button = useRef("change");
        this.state = useState({ data: this.props.block, history: false, flash: 0 });
        // PSCHEME P2a D.2: the pay scheme changed elsewhere on this screen
        // (the Country of work prompt, the contract drawer) — read it again.
        useBus(this.env.bus, "PB_PERSON_SCHEME_CHANGED", (ev) => {
            const detail = ev.detail || {};
            if (detail.source !== "block" && Number(detail.empId) === Number(this.props.employeeId)) {
                this.reload(true);
            }
        });
    }
    get mismatch() { return this.d.country_mismatch || null; }
    get contractNote() { return this.d.contract_note || null; }
    openFix() {
        const m = this.mismatch;
        openChangePayScheme(this.dialog, {
            employeeId: this.props.employeeId, data: this.state.data, pick: m && m.target_id,
            onSaved: () => this.reload(), opener: this.button.el,
        });
    }
    openContract() {
        const note = this.contractNote;
        if (!note) { return; }
        const ws = this.env.pbEmployeeWorkspace;
        if (ws && typeof ws.openContract === "function") {
            ws.openContract(note.contract_id);
            return;
        }
        this.action.doAction({ type: "ir.actions.act_window", res_model: "hr.contract",
            res_id: note.contract_id, views: [[false, "form"]], target: "current" }).catch(() => {});
    }
    async dismissNote() {
        const note = this.contractNote;
        if (!note) { return; }
        try {
            await this.orm.call(BOARD, "contract_note_dismiss", [note.contract_id]);
        } finally {
            await this.reload(true);
        }
    }
    get d() { return this.state.data || {}; }
    get main() { return this.d.main; }
    get advance() { return this.d.advance; }
    get nextLine() {
        const n = this.d.next;
        if (!n) {
            return "";
        }
        return n.advance ? _t("Mid-month advance changes to %(scheme)s on %(date)s", { scheme: n.scheme, date: n.date_words })
            : _t("Changes to %(scheme)s on %(date)s", { scheme: n.scheme, date: n.date_words });
    }
    get waitingLine() {
        const w = this.d.waiting;
        return w ? _t("Waiting for approval: %(scheme)s from %(date)s", { scheme: w.scheme, date: w.date_words }) : "";
    }
    get waitingWho() {
        const w = this.d.waiting;
        return w && w.with_whom ? _t("With %s", w.with_whom) : "";
    }
    get advanceLine() { return this.advance ? _t("Mid-month advance: %s", this.advance.name) : ""; }
    get canChange() { return Boolean(this.d.can_propose && this.d.employee && this.d.employee.active); }
    get historyLabel() {
        const n = (this.d.history || []).length;
        return n === 1 ? _t("History (1)") : _t("History (%s)", n);
    }
    historyDates(h) {
        return h.until_words ? _t("%(from)s to %(until)s", { from: h.from_words, until: h.until_words })
            : _t("From %s", h.from_words);
    }
    toggleHistory() { this.state.history = !this.state.history; }
    async reload(quiet = false) {
        try {
            this.state.data = await loadPersonScheme(this.orm, this.props.employeeId);
            this.state.flash += 1;
            if (quiet) {
                return;
            }
            this.env.bus.trigger("PB_PERSON_SCHEME_CHANGED", { empId: Number(this.props.employeeId), source: "block" });
        } catch (e) {
            console.warn("pb_scheme_map: the pay scheme could not be read again", e);
        }
    }
    openChange() {
        openChangePayScheme(this.dialog, {
            employeeId: this.props.employeeId, data: this.state.data,
            onSaved: () => this.reload(), opener: this.button.el,
        });
    }
}

registry.category("pb_person_scheme").add("api", {
    load: loadPersonScheme,
    open: openChangePayScheme,
    dayWords,
});

// The side panel draws the block inside its own section (template
// inheritance in person_scheme.xml); it only needs to know the component.
Employee360Drawer.components = { ...(Employee360Drawer.components || {}), PersonSchemeBlock };
