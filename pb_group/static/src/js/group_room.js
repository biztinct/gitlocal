/** @odoo-module **/
/**
 * `pb_group` — the Group screen.
 *
 * THE HERO IS THE TREE. The group is one card at the top carrying the currency
 * the board reads in, how rates are picked and when the year starts; the member
 * companies hang under it as cards with their country, their money, their
 * people and their pay schemes, joined by drawn lines. Ticking a company slides
 * it into the tree and its people count runs up to its number. That is the
 * whole idea of a group in one picture, and it is the picture every later
 * screen in this programme is built on.
 *
 * THE SECOND HERO IS THE COVERAGE STRIP. One row per pair of currencies the
 * group actually needs, twelve cells for the year, and three honest answers per
 * cell: a rate from that month, a rate from earlier (with the date), or nothing
 * at all. Colour is never the message — every cell also carries a word, so the
 * strip reads identically to somebody who cannot tell the amber from the green.
 *
 * WHAT IT NEVER SAYS. "Presentation currency", "FX", "rate policy". On screen
 * it is the group currency, exchange rates, and how rates are picked.
 *
 * THE RULES THIS FILE KEEPS
 *   * Every icon comes from the shared `ic()` set — no emoji, no glyph arrows.
 *   * Every sentence is ONE expression: JavaScript has no implicit string
 *     concatenation and a Python habit here kills the whole asset bundle.
 *   * Escape is registered with `{capture: true}`, because the platform's own
 *     hotkey service listens on `window` and stops propagation for the keys it
 *     claims — Escape among them (WFPLAN WF4).
 *   * Motion lives in the stylesheet inside a `prefers-reduced-motion` guard;
 *     the one animation JavaScript owns — the count-up — asks the machine
 *     first and simply writes the number when the answer is "less movement".
 */
import {
    Component, onMounted, onPatched, onWillStart, onWillUnmount, useRef,
    useState,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";

/** Month names, built when they are needed so the translator is loaded. */
function monthNames() {
    return [
        _t("January"), _t("February"), _t("March"), _t("April"), _t("May"),
        _t("June"), _t("July"), _t("August"), _t("September"), _t("October"),
        _t("November"), _t("December"),
    ];
}

/** Short month names for the twelve cells of the coverage strip. */
function monthShort() {
    return [
        _t("Jan"), _t("Feb"), _t("Mar"), _t("Apr"), _t("May"), _t("Jun"),
        _t("Jul"), _t("Aug"), _t("Sep"), _t("Oct"), _t("Nov"), _t("Dec"),
    ];
}

const BLANK_GROUP = {
    id: 0, name: "", code: "", currency_id: 0, fx_policy: "month_end",
    fiscal_start_month: 1, note: "", company_ids: [],
};

/** A number that counts up to its value, unless the machine asked for calm. */
function countUp(el, to) {
    const from = Number(el.dataset.pbgFrom || 0);
    el.dataset.pbgFrom = to;
    const calm = window.matchMedia
        && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (calm || from === to || to > 100000) {
        el.textContent = to.toLocaleString();
        return;
    }
    const started = performance.now();
    const step = (now) => {
        const share = Math.min((now - started) / 600, 1);
        const eased = 1 - Math.pow(1 - share, 3);
        el.textContent = Math.round(from + (to - from) * eased).toLocaleString();
        if (share < 1) { window.requestAnimationFrame(step); }
    };
    window.requestAnimationFrame(step);
}

export class PbGroupRoom extends Component {
    static template = "pb_group.PbGroupRoom";
    static components = { HubBackChip };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");

        // Read ONCE, from props, never written back (HubShell's rule).
        this.back = hubBack(this.props);

        // THE NAME IN THE BREADCRUMB. A client action with no control panel
        // never sets one, so anything it opens — the exchange-rate list, the
        // group's own history — draws a trail whose first crumb reads
        // "Unnamed" and takes the reader nowhere they recognise.
        if (this.env.config && this.env.config.setDisplayName) {
            this.env.config.setDisplayName(_t("Group"));
        }
        this.stripRef = useRef("strip");
        this.rootRef = useRef("root");

        this.state = useState({
            loaded: false,
            failed: "",
            busy: false,
            room: null,

            // the group drawer
            editing: false,
            draft: { ...BLANK_GROUP },

            // the divisions
            openDivision: 0,
            divisionDraft: { name: "", code: "", color: 0, note: "" },
            adding: false,
            newDivision: { name: "", code: "", color: 0 },

            // the pickers
            attaching: 0,
            attachSearch: "",
            attachDate: "",
            // GROUP P7 — ticking many, then one press (polish item P1)
            attachPicks: [],
            detaching: 0,
            detachDate: "",

            // GROUP P7 — who sees what
            visOpen: false,
            visDraft: { user_id: 0, kind: "all", ref_id: 0, note: "" },
            preview: null,
            previewBusy: false,

            // the suggestions
            suggesting: false,
            picks: [],

            // a refusal about the thing in front of you, shown beside it
            dialogError: "",
        });

        this._counts = new Map();
        this._escape = (ev) => this.onEscape(ev);

        onWillStart(async () => { await this.load(); });
        onMounted(() => {
            window.addEventListener("keydown", this._escape, { capture: true });
            this.paintCounts();
            this.focusRequested();
        });
        onPatched(() => { this.paintCounts(); });
        onWillUnmount(() => {
            window.removeEventListener("keydown", this._escape,
                                       { capture: true });
        });
    }

    ic(n, s = 16) { return ic(n, s); }

    /** A count with the reader's own thousands separator. */
    num(value) { return Number(value || 0).toLocaleString(); }

    /**
     * "person" or "people" — because "1 people" is the kind of sentence that
     * makes somebody trust the rest of the number less.
     */
    peopleWord(value) {
        return Number(value || 0) === 1 ? _t("person") : _t("people");
    }

    // ================================================================ reading
    async load() {
        try {
            this.state.room = await this.orm.call("pb.group.room", "get_room",
                                                  []);
            this.state.failed = "";
        } catch (e) {
            this.state.room = null;
            this.state.failed = this._msg(
                e, _t("The group could not be read."));
        } finally {
            this.state.loaded = true;
        }
    }

    async reload() {
        this.state.loaded = false;
        await this.load();
    }

    /**
     * The server's own sentence, or ours — and never the platform's (GR17).
     *
     * The top-level `.message` of every RPC error on this platform is the
     * literal string "Odoo Server Error". Falling back to it printed the one
     * word this product may never say, in a red box, on the screen the reader
     * was looking at. So it is not a rung on this ladder at all: either the
     * server told us something a person can act on — `error.data.message`, or
     * the older `error.message.data.message` shape some cockpits still raise
     * — or we say our own sentence.
     */
    _msg(error, fallback) {
        const data = (error && error.data)
            || (error && error.message && error.message.data);
        const message = data && (data.message
            || (data.arguments && data.arguments[0]));
        return message || fallback;
    }

    /**
     * One write, one re-read, one place that catches. Every write on this
     * screen returns the whole room, so nothing on it can drift out of step
     * with what the server actually stored.
     */
    async _write(method, args, done, inline = false) {
        if (this.state.busy) { return false; }
        this.state.busy = true;
        this.state.dialogError = "";
        try {
            this.state.room = await this.orm.call("pb.group.room", method,
                                                  args);
            this.state.failed = "";
            // A POLICY CHANGE MAY HAVE BECOME A REQUEST. Which rate to use,
            // which currency the group reads in, when its year starts: those
            // travel a route where one is published, and the room comes back
            // with the proposal instead of the change. Saying "Saved" over a
            // group that is exactly as it was is a control that lies.
            const held = this.state.room && this.state.room.proposal;
            if (held && !held.applied) {
                this.notif.add(held.message || _t("Sent for approval."),
                               { type: "info" });
            } else if (done) {
                this.notif.add(done, { type: "success" });
            }
            return true;
        } catch (e) {
            const message = this._msg(
                e, _t("That change could not be saved."));
            // A refusal about something the person is LOOKING AT belongs next
            // to it, not in a corner of the screen they have to find: a toast
            // over an open dialog is a sentence about a control you can no
            // longer see.
            if (inline) {
                this.state.dialogError = message;
            } else {
                this.notif.add(message, { type: "danger", sticky: true });
            }
            return false;
        } finally {
            this.state.busy = false;
        }
    }

    // ================================================================ getters
    get room() { return this.state.room || {}; }
    get allowed() { return !!this.room.allowed; }
    get canEdit() { return !!this.room.can_edit; }
    get group() { return this.room.group || null; }
    get companies() { return this.room.companies || []; }
    get members() { return this.companies.filter((c) => c.member); }
    get outsiders() { return this.companies.filter((c) => !c.member); }
    get divisions() { return this.room.divisions || []; }
    get suggestions() { return this.room.suggestions || []; }
    get departments() { return this.room.departments || []; }
    get policies() { return this.room.policies || []; }
    /** GROUP P5 — the two ways a split month can be paid (ruling G8). */
    get splitPolicies() { return this.room.split_policies || []; }
    /** Drawn only where something acts on it. */
    get hasWorkseg() { return !!this.room.has_workseg; }
    get currencies() { return this.room.currencies || []; }
    get coverage() { return this.room.coverage || { pairs: [] }; }
    get months() { return monthShort(); }

    get policyLabel() {
        const found = this.policies.find(
            (p) => this.group && p.key === this.group.fx_policy);
        return found ? found.label : "";
    }

    get policyHelp() {
        const found = this.policies.find(
            (p) => this.group && p.key === this.group.fx_policy);
        return found ? found.help : "";
    }

    get fiscalLabel() {
        const month = this.group ? this.group.fiscal_start_month : 1;
        return monthNames()[Math.max(Math.min(month, 12), 1) - 1];
    }

    get monthChoices() {
        return monthNames().map((label, i) => ({ value: i + 1, label }));
    }

    get openDivisionRow() {
        return this.divisions.find((d) => d.id === this.state.openDivision)
            || null;
    }

    /** The departments the attach picker offers, narrowed by what was typed. */
    get attachChoices() {
        const needle = (this.state.attachSearch || "").trim().toLowerCase();
        const rows = this.departments.filter(
            (d) => d.division_id !== this.state.attaching);
        const matched = needle
            ? rows.filter((d) => (d.complete_name || "").toLowerCase()
                .includes(needle) || (d.company || "").toLowerCase()
                .includes(needle))
            : rows;
        const byCompany = new Map();
        for (const row of matched.slice(0, 300)) {
            if (!byCompany.has(row.company_id)) {
                byCompany.set(row.company_id,
                              { id: row.company_id, name: row.company,
                                rows: [] });
            }
            byCompany.get(row.company_id).rows.push(row);
        }
        return [...byCompany.values()];
    }

    /** The division cards, plus the honest tail: everybody in none of them. */
    get unassigned() { return this.room.unassigned || 0; }

    get coverageEmpty() {
        return !this.coverage.pairs || !this.coverage.pairs.length;
    }

    get memberCurrencyWord() {
        const names = [...new Set(this.members.map((c) => c.currency))];
        return names.join(", ");
    }

    // ================================================================= counts
    /** Every `[data-pbg-count]` on the page runs up to its number. */
    paintCounts() {
        const root = this.rootRef.el;
        if (!root) { return; }
        for (const el of root.querySelectorAll("[data-pbg-count]")) {
            const to = Number(el.dataset.pbgCount || 0);
            const key = el.dataset.pbgKey || "";
            if (this._counts.get(key) === to) { continue; }
            this._counts.set(key, to);
            countUp(el, to);
        }
    }

    focusRequested() {
        // ⌘K's "Divisions" row asks for the board rather than the top of the
        // page, and a deep link that lands on the wrong half of a screen is a
        // deep link nobody uses twice.
        const context = (this.props.action && this.props.action.context) || {};
        const focus = context.pb_focus || "";
        if (!focus || !this.rootRef.el) { return; }
        const target = this.rootRef.el.querySelector(`#pbg-${focus}`);
        if (target) {
            target.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }

    // ============================================================== the group
    openCreate() {
        this.state.draft = {
            ...BLANK_GROUP,
            name: "",
            currency_id: this.companies.length
                ? this.companies[0].currency_id : 0,
            company_ids: [],
        };
        this.state.editing = true;
    }

    openEdit() {
        if (!this.group) { this.openCreate(); return; }
        this.state.draft = {
            id: this.group.id,
            name: this.group.name,
            code: this.group.code,
            currency_id: this.group.currency_id,
            fx_policy: this.group.fx_policy,
            fiscal_start_month: this.group.fiscal_start_month,
            note: this.group.note,
            company_ids: [...(this.group.company_ids || [])],
        };
        this.state.editing = true;
    }

    closeEdit() { this.state.editing = false; }

    draftHas(companyId) {
        return (this.state.draft.company_ids || []).includes(companyId);
    }

    toggleDraftCompany(companyId) {
        const list = this.state.draft.company_ids || [];
        this.state.draft.company_ids = list.includes(companyId)
            ? list.filter((id) => id !== companyId)
            : [...list, companyId];
    }

    setDraft(field, ev) {
        const value = ev.target.value;
        if (field === "currency_id" || field === "fiscal_start_month") {
            this.state.draft[field] = Number(value || 0);
        } else {
            this.state.draft[field] = value;
        }
    }

    setPolicy(key) { this.state.draft.fx_policy = key; }

    /**
     * GROUP P5 — how a split month is paid, saved the moment it is picked.
     *
     * Not inside the group drawer with the currency and the year, on purpose:
     * this is a choice somebody comes here to change, alone, having read the
     * two sentences beside it — not one field of a form about the group's
     * name. One press, one write, one sentence back.
     */
    async setSplitPolicy(key) {
        if (!this.group || this.group.split_pay_policy === key) { return; }
        const found = this.splitPolicies.find((p) => p.key === key);
        await this._write("set_split_policy", [this.group.id, key],
                          found
                              ? _t("Split months: %(pattern)s.",
                                   { pattern: found.label })
                              : _t("Saved."));
    }

    /**
     * Day-based pay for people who join or leave part-way through a month.
     *
     * The sentence names the company AND says when it starts, because the
     * thing a person needs to know here is not that a tick moved — it is that
     * somebody's payslip will be a different number next month.
     */
    async toggleProrate(company) {
        const on = !company.prorate;
        await this._write("set_prorate_joiners", [company.id, on],
                          on
                              ? _t("%(company)s will pay joiners and leavers for the days they work, from the next pay run.",
                                   { company: company.name })
                              : _t("%(company)s pays joiners and leavers a full month, as before.",
                                   { company: company.name }));
    }

    async saveGroup() {
        const draft = this.state.draft;
        if (!(draft.name || "").trim()) {
            this.notif.add(_t("Give the group a name first."),
                           { type: "warning" });
            return;
        }
        if (!draft.currency_id) {
            this.notif.add(_t("Pick the currency the group reads in."),
                           { type: "warning" });
            return;
        }
        const done = await this._write("save_group", [{
            id: draft.id || 0,
            name: draft.name,
            code: draft.code,
            presentation_currency_id: draft.currency_id,
            fx_policy: draft.fx_policy,
            fiscal_start_month: draft.fiscal_start_month,
            note: draft.note,
            company_ids: draft.company_ids,
        }], _t("Your group is saved."));
        if (done) { this.state.editing = false; }
    }

    openHistory() {
        this.action.doAction("pb_group.action_pb_group_records",
                             { clearBreadcrumbs: false });
    }

    // ============================================================== the rates
    async setLivePolicy(ev) {
        if (!this.group) { return; }
        await this._write("save_group", [{
            id: this.group.id,
            name: this.group.name,
            code: this.group.code,
            presentation_currency_id: this.group.currency_id,
            fx_policy: ev.target.value,
            fiscal_start_month: this.group.fiscal_start_month,
            note: this.group.note,
        }], _t("Saved. Every converted figure now uses that rate."));
    }

    /**
     * The word inside a cell. Colour is never the message: the strip has to
     * read the same way to somebody who cannot tell the amber from the green,
     * so every cell carries a word as well as a tone. Short, because there are
     * twelve of them in a row; the whole sentence is in the cell's title and
     * its `aria-label`.
     */
    cellWord(cell) {
        if (cell.state === "ok") { return _t("Rate"); }
        if (cell.state === "old") { return _t("Older"); }
        return _t("None");
    }

    cellTitle(pair, cell) {
        const month = monthNames()[cell.month - 1];
        if (cell.state === "ok") {
            return _t("%(month)s: a rate from this month. Click to open it.",
                      { month });
        }
        if (cell.state === "old") {
            return _t("%(month)s: the newest rate is from %(date)s. Click to add one.",
                      { month, date: cell.rate_date });
        }
        return _t("%(month)s: nothing on file, so %(src)s stays in %(src)s. Click to add a rate.",
                  { month, src: pair.src });
    }

    /**
     * A cell is a door, and it lands on the month it was clicked.
     *
     * The action carries its own NAME and its own empty state: a month with no
     * rate is the most likely thing a person clicks, and an empty list with
     * nothing to read is the dead end this screen exists to remove.
     */
    openRates(pair, cell) {
        const year = this.coverage.year || new Date().getFullYear();
        const month = cell ? cell.month : 1;
        const last = new Date(year, month, 0).getDate();
        const pad = month < 10 ? `0${month}` : `${month}`;
        const start = `${year}-${pad}-01`;
        const end = `${year}-${pad}-${last}`;
        const label = cell
            ? _t("Exchange rates · %(src)s to %(dst)s · %(month)s %(year)s",
                 { src: pair.src, dst: pair.dst,
                   month: monthNames()[month - 1], year })
            : _t("Exchange rates · %(src)s to %(dst)s",
                 { src: pair.src, dst: pair.dst });
        this.action.doAction({
            type: "ir.actions.act_window",
            name: label,
            res_model: "res.currency.rate",
            views: [[false, "list"], [false, "form"]],
            domain: cell
                ? [["currency_id", "in", [pair.src_id, pair.dst_id]],
                   ["name", ">=", start], ["name", "<=", end]]
                : [["currency_id", "in", [pair.src_id, pair.dst_id]]],
            context: { default_currency_id: pair.src_id,
                       default_name: start },
            // PLAIN TEXT, not markup. An action built in the browser has its
            // `help` ESCAPED on the way to the empty state, so a paragraph tag
            // arrives on screen as a paragraph tag — which is worse than no
            // empty state at all.
            help: _t("No rate for this month yet. Add one with New and every group figure that needs it appears. Until then, the amounts stay in the money they were paid in."),
        }, { clearBreadcrumbs: false });
    }

    openRateList() {
        this.action.doAction("pb_group.action_pb_exchange_rates",
                             { clearBreadcrumbs: false });
    }

    /** Arrow keys walk the twelve cells of a row, which is what a grid is. */
    onCellKeydown(ev) {
        const keys = ["ArrowRight", "ArrowLeft", "ArrowUp", "ArrowDown"];
        if (!keys.includes(ev.key)) { return; }
        const cell = ev.target.closest("[data-pbg-cell]");
        const strip = this.stripRef.el;
        if (!cell || !strip) { return; }
        ev.preventDefault();
        const cells = [...strip.querySelectorAll("[data-pbg-cell]")];
        const row = Number(cell.dataset.pbgRow || 0);
        const col = Number(cell.dataset.pbgCol || 0);
        const step = { ArrowRight: [0, 1], ArrowLeft: [0, -1],
                       ArrowUp: [-1, 0], ArrowDown: [1, 0] }[ev.key];
        const wanted = cells.find(
            (c) => Number(c.dataset.pbgRow) === row + step[0]
                && Number(c.dataset.pbgCol) === col + step[1]);
        if (wanted) { wanted.focus(); }
    }

    // ========================================================== the divisions
    openDivision(id) {
        const row = this.divisions.find((d) => d.id === id);
        this.state.openDivision = id;
        this.state.divisionDraft = row
            ? { name: row.name, code: row.code, color: row.color,
                note: row.note }
            : { name: "", code: "", color: 0, note: "" };
    }

    closeDivision() {
        this.state.openDivision = 0;
        this.state.attaching = 0;
        this.state.detaching = 0;
    }

    onCardKeydown(ev, id) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.openDivision(id);
        }
    }

    setDivisionDraft(field, ev) {
        this.state.divisionDraft[field] = field === "color"
            ? Number(ev.target.value || 0) : ev.target.value;
    }

    pickColour(index) { this.state.divisionDraft.color = index; }

    get colourChoices() { return [0, 1, 2, 3, 4, 5, 6, 7]; }

    async saveDivision() {
        const id = this.state.openDivision;
        if (!id) { return; }
        await this._write("update_division",
                          [id, { ...this.state.divisionDraft }],
                          _t("Division saved."));
    }

    openAdd() {
        this.state.newDivision = { name: "", code: "",
                                   color: this.divisions.length % 8 };
        this.state.dialogError = "";
        this.state.adding = true;
    }

    closeAdd() {
        this.state.adding = false;
        this.state.dialogError = "";
    }

    setNewDivision(field, ev) {
        this.state.newDivision[field] = ev.target.value;
    }

    async createDivision() {
        if (!(this.state.newDivision.name || "").trim()) {
            this.notif.add(_t("Give the division a name first."),
                           { type: "warning" });
            return;
        }
        const done = await this._write("create_division",
                                       [{ ...this.state.newDivision }],
                                       _t("Division added."), true);
        if (done) { this.state.adding = false; }
    }

    async archiveDivision() {
        const id = this.state.openDivision;
        if (!id) { return; }
        const done = await this._write("archive_division", [id],
                                       _t("Division put away."));
        if (done) { this.closeDivision(); }
    }

    // ============================================================ attachments
    openAttach(divisionId) {
        this.state.attaching = divisionId;
        this.state.attachSearch = "";
        this.state.attachDate = "";
        this.state.attachPicks = [];
    }

    closeAttach() {
        this.state.attaching = 0;
        this.state.attachPicks = [];
    }

    setAttachSearch(ev) { this.state.attachSearch = ev.target.value; }
    setAttachDate(ev) { this.state.attachDate = ev.target.value; }

    async attach(departmentId) {
        const done = await this._write(
            "attach_department",
            [this.state.attaching, departmentId,
             this.state.attachDate || false],
            _t("Department attached."));
        if (done) { this.closeAttach(); }
    }

    // ------------------------------------------------ many at once (P7, P1)
    /**
     * TICK MANY, PRESS ONCE.
     *
     * The picker used to attach on click, one department per press — which on
     * a company with forty teams is forty presses and forty rebuilds of a
     * screen that draws four thousand people. Ticking is the gesture the list
     * already looks like it wants; a row is now a checkbox, the footer counts
     * what is ticked and how many people it brings, and the whole set goes in
     * ONE call.
     */
    isPicked(departmentId) {
        return this.state.attachPicks.includes(departmentId);
    }

    togglePickDept(departmentId) {
        const picks = this.state.attachPicks;
        this.state.attachPicks = picks.includes(departmentId)
            ? picks.filter((id) => id !== departmentId)
            : [...picks, departmentId];
    }

    onDeptKeydown(ev, departmentId) {
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.togglePickDept(departmentId);
        }
    }

    /** Everything the search currently shows, ticked or untied in one press. */
    toggleAllShown() {
        const shown = this.attachChoices.flatMap((cg) => cg.rows)
            .map((d) => d.id);
        const every = shown.length
            && shown.every((id) => this.state.attachPicks.includes(id));
        this.state.attachPicks = every
            ? this.state.attachPicks.filter((id) => !shown.includes(id))
            : [...new Set([...this.state.attachPicks, ...shown])];
    }

    get allShownPicked() {
        const shown = this.attachChoices.flatMap((cg) => cg.rows)
            .map((d) => d.id);
        return !!shown.length
            && shown.every((id) => this.state.attachPicks.includes(id));
    }

    get pickedCount() { return this.state.attachPicks.length; }

    /** How many people the ticked departments bring, so the press is informed. */
    get pickedPeople() {
        const picked = new Set(this.state.attachPicks);
        return this.departments
            .filter((d) => picked.has(d.id))
            .reduce((sum, d) => sum + (d.heads || 0), 0);
    }

    /** How many of the ticked ones are being MOVED out of another division. */
    get pickedMoves() {
        const picked = new Set(this.state.attachPicks);
        return this.departments
            .filter((d) => picked.has(d.id) && d.division_id).length;
    }

    async attachPicked() {
        const picks = [...this.state.attachPicks];
        if (!picks.length) {
            this.notif.add(_t("Tick at least one department first."),
                           { type: "warning" });
            return;
        }
        const done = await this._write(
            "attach_departments",
            [this.state.attaching, picks, this.state.attachDate || false],
            _t("%(count)s attached.", { count: picks.length }));
        if (done) {
            const room = this.state.room || {};
            if (room.attach_failed) {
                this.notif.add(
                    _t("%(count)s could not be attached — they may already be in this division.",
                       { count: room.attach_failed }),
                    { type: "warning" });
            }
            this.closeAttach();
        }
    }

    openDetach(linkId) {
        this.state.detaching = linkId;
        this.state.detachDate = "";
        this.state.dialogError = "";
    }

    closeDetach() {
        this.state.detaching = 0;
        this.state.dialogError = "";
    }
    setDetachDate(ev) { this.state.detachDate = ev.target.value; }

    async detach() {
        const done = await this._write(
            "detach", [this.state.detaching, this.state.detachDate || false],
            _t("Department taken out. The history is kept."), true);
        if (done) { this.state.detaching = 0; }
    }

    // ============================================================ suggestions
    openSuggest() {
        this.state.picks = this.suggestions.map((s, i) => ({
            key: `${s.key}-${i}`,
            name: s.name,
            chosen: true,
            merging: false,
            existing_id: s.existing_id,
            people: s.people,
            departments: s.departments.map((d) => d.id),
            labels: s.departments.map(
                (d) => `${d.company} · ${d.complete_name}`),
        }));
        this.state.suggesting = true;
    }

    closeSuggest() { this.state.suggesting = false; }

    togglePick(key) {
        const pick = this.state.picks.find((p) => p.key === key);
        if (pick) { pick.chosen = !pick.chosen; }
    }

    toggleMerge(key) {
        const pick = this.state.picks.find((p) => p.key === key);
        if (pick) { pick.merging = !pick.merging; }
    }

    renamePick(key, ev) {
        const pick = this.state.picks.find((p) => p.key === key);
        if (pick) { pick.name = ev.target.value; }
    }

    get mergeCount() {
        return this.state.picks.filter((p) => p.merging).length;
    }

    /** Two ticked rows become one, keeping the first one's name. */
    mergePicks() {
        const chosen = this.state.picks.filter((p) => p.merging);
        if (chosen.length < 2) { return; }
        const first = chosen[0];
        const rest = chosen.slice(1);
        first.departments = [
            ...new Set([...first.departments,
                        ...rest.flatMap((p) => p.departments)]),
        ];
        first.labels = [...first.labels, ...rest.flatMap((p) => p.labels)];
        first.people = chosen.reduce((sum, p) => sum + (p.people || 0), 0);
        first.merging = false;
        const dropped = new Set(rest.map((p) => p.key));
        this.state.picks = this.state.picks.filter(
            (p) => !dropped.has(p.key));
    }

    async acceptSuggestions() {
        const chosen = this.state.picks.filter(
            (p) => p.chosen && p.departments.length);
        if (!chosen.length) {
            this.notif.add(_t("Tick at least one to create."),
                           { type: "warning" });
            return;
        }
        const done = await this._write(
            "accept_suggestions",
            [chosen.map((p) => ({ name: p.name,
                                  departments: p.departments }))],
            _t("Divisions created from your departments."));
        if (done) { this.state.suggesting = false; }
    }

    // =========================================================== who sees what
    /**
     * THE HERO OF THIS PHASE: "as this person".
     *
     * A permission model is the hardest thing in any product to be sure of,
     * because the only way to check it is normally to log in as somebody else
     * and look. So the card does that for you: pick a person, and it says in
     * one sentence exactly what they would see — the division, the companies,
     * the head count — and lists every screen in the product with the same
     * answer beside it. It is the SAME `scope_for` the screens themselves
     * call, so it cannot drift away from the thing it describes.
     */
    get visibility() {
        return this.room.visibility || {
            rows: [], people: [], kinds: [], countries: [], companies: [],
            divisions: [], warnings: [], mine: "",
        };
    }

    get visRows() { return this.visibility.rows || []; }
    get visKinds() { return this.visibility.kinds || []; }
    get visWarnings() { return this.visibility.warnings || []; }
    get visPeople() { return this.visibility.people || []; }
    get scopeNote() { return this.room.scope_note || ""; }

    /** The one list the second dropdown offers, whichever kind is picked. */
    get visRefChoices() {
        const kind = this.state.visDraft.kind;
        if (kind === "country") { return this.visibility.countries || []; }
        if (kind === "company") { return this.visibility.companies || []; }
        if (kind === "division") { return this.visibility.divisions || []; }
        return [];
    }

    get visNeedsRef() {
        return ["country", "company", "division"]
            .includes(this.state.visDraft.kind);
    }

    get visDraftReady() {
        const draft = this.state.visDraft;
        if (!draft.user_id) { return false; }
        return !this.visNeedsRef || !!draft.ref_id;
    }

    openVisibility(row) {
        this.state.visDraft = row
            ? { user_id: row.user_id, kind: row.kind,
                ref_id: row.ref_id || 0, note: row.note || "" }
            : { user_id: 0, kind: "all", ref_id: 0, note: "" };
        this.state.dialogError = "";
        this.state.visOpen = true;
        if (row) { this.previewAs(row.user_id); }
        else { this.state.preview = null; }
    }

    closeVisibility() {
        this.state.visOpen = false;
        this.state.preview = null;
        this.state.dialogError = "";
    }

    pickVisKind(key) {
        this.state.visDraft.kind = key;
        this.state.visDraft.ref_id = 0;
    }

    setVisDraft(field, ev) {
        const value = ev.target.value;
        if (field === "kind") {
            this.state.visDraft.kind = value;
            this.state.visDraft.ref_id = 0;
        } else if (field === "note") {
            this.state.visDraft.note = value;
        } else {
            this.state.visDraft[field] = Number(value || 0);
        }
        if (field === "user_id" && this.state.visDraft.user_id) {
            this.previewAs(this.state.visDraft.user_id);
        }
    }

    /** What this person would see, read from the server, never guessed here. */
    async previewAs(userId) {
        const id = Number(userId || 0);
        if (!id) { this.state.preview = null; return; }
        this.state.previewBusy = true;
        try {
            this.state.preview = await this.orm.call(
                "pb.group.room", "preview_visibility", [id]);
        } catch (e) {
            this.state.preview = null;
            this.state.dialogError = this._msg(
                e, _t("That preview could not be read."));
        } finally {
            this.state.previewBusy = false;
        }
    }

    async saveVisibility() {
        const draft = this.state.visDraft;
        if (!draft.user_id) {
            this.notif.add(_t("Pick a person first."), { type: "warning" });
            return;
        }
        if (this.visNeedsRef && !draft.ref_id) {
            this.notif.add(_t("Pick the one they should see."),
                           { type: "warning" });
            return;
        }
        const done = await this._write(
            "set_visibility",
            [draft.user_id, draft.kind, draft.ref_id || false,
             draft.note || false],
            _t("Saved. They see that from their next screen."), true);
        if (done) { this.closeVisibility(); }
    }

    /** Take the limit away — back to whatever their companies allow. */
    async liftVisibility(row) {
        await this._write(
            "set_visibility", [row.user_id, false, false, false],
            _t("%(name)s is no longer limited.", { name: row.user }));
    }

    // ================================================================ keyboard
    onEscape(ev) {
        if (ev.key !== "Escape") { return; }
        // Never `preventDefault` on Escape: the platform still gets its turn.
        if (this.state.visOpen) { this.closeVisibility(); return; }
        if (this.state.suggesting) { this.state.suggesting = false; return; }
        if (this.state.attaching) { this.closeAttach(); return; }
        if (this.state.detaching) { this.state.detaching = 0; return; }
        if (this.state.adding) { this.state.adding = false; return; }
        if (this.state.editing) { this.state.editing = false; return; }
        if (this.state.openDivision) { this.state.openDivision = 0; }
    }
}

registry.category("actions").add("pb_group", PbGroupRoom);
