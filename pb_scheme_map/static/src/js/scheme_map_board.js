/** @odoo-module **/
/**
 * "Who is paid by what" — the Mapping screen's scheme board.
 *
 * THE HERO IS THE DRAFTED MAP. On a company that has been paying people for
 * months, the map already exists — it is just not written down anywhere. One
 * button reads the last runs and proposes it back: for every team, the scheme
 * that actually paid its people, with the sentence that says so ("Every one of
 * Retail's 902 people on the last 3 end-of-month runs was paid under Retail
 * End-Month Payroll") and a ring showing how many agreed. Accept the confident
 * ones in a click; look at the amber ones, which say what disagreed.
 *
 * THE SECOND PICTURE IS THE WIRES. Teams and divisions on the left, schemes on
 * the right, and a drawn line for every attachment carrying the kind of run it
 * answers. The lines are measured from the real elements on every paint and
 * every resize, because this board lives inside a tab whose width changes.
 *
 * WHAT IT NEVER SAYS. "Config", "assignment", "domain", "cycle_type". On
 * screen it is a payroll scheme, a line on the map, a rule, and a kind of run.
 *
 * THE RULES THIS FILE KEEPS
 *   * Every icon comes from the shared `ic()` set — no emoji, no glyph arrows.
 *   * Every sentence is ONE expression: JavaScript has no implicit string
 *     concatenation and a Python habit here kills the whole asset bundle (W74).
 *   * Escape is registered with `{ capture: true }`, because the platform's own
 *     hotkey service listens on `window` and stops propagation for the keys it
 *     claims — Escape among them (WFPLAN WF4).
 *   * Colour is never the only message: every ring and every badge carries a
 *     word as well.
 */
import {
    Component, onMounted, onPatched, onWillStart, onWillUnmount, useRef,
    useState,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.scheme.board";

/** The order the right column groups schemes in, most common run first. */
export const CYCLE_ORDER = ["end_cycle", "regular", "mid_cycle", "full_final"];

/** A ring's circumference, for the dash arithmetic. r = 15 → 2πr. */
const RING = 94.25;

/** Below this share of agreement a proposal is amber and says what disagreed. */
export const CONFIDENT = 0.9;

/** Schemes grouped by kind of run, in a fixed order. Pure, so it is testable. */
export function groupSchemes(schemes) {
    const out = [];
    const seen = new Map();
    for (const scheme of schemes || []) {
        const key = scheme.cycle_type || "regular";
        if (!seen.has(key)) {
            seen.set(key, { key, label: scheme.cycle_label || "", items: [] });
        }
        seen.get(key).items.push(scheme);
    }
    for (const key of CYCLE_ORDER) {
        if (seen.has(key)) { out.push(seen.get(key)); seen.delete(key); }
    }
    for (const group of seen.values()) { out.push(group); }
    return out;
}

export class SchemeMapBoard extends Component {
    static template = "pb_scheme_map.SchemeMapBoard";
    static props = {
        companyId: { type: Number, optional: true },
        focus: { type: String, optional: true },
        onLoaded: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");

        this.rootRef = useRef("root");
        this.wireRef = useRef("wires");

        this.state = useState({
            loaded: false,
            busy: false,
            failed: "",
            board: null,

            companyId: this.props.companyId || 0,
            picked: [],          // ticked segments, for a bulk attach
            hover: "",           // the segment or scheme the pointer is on
            open: "",            // which expandable team is open

            attaching: null,     // { segments: [...], cycle: "any" }
            attachQuery: "",

            drafting: false,
            draft: null,         // { rows: [...] }
            skipped: [],         // draft rows the reader said no to

            showExceptions: false,
            dialogError: "",     // a refusal about the thing in front of you

            paths: [],           // the drawn wires, measured from the DOM
        });

        this._escape = (ev) => this.onEscape(ev);
        this._observer = null;

        onWillStart(async () => { await this.load(); });
        onMounted(() => {
            window.addEventListener("keydown", this._escape, { capture: true });
            this.watchSize();
            this.measure();
            if ((this.props.focus || "") === "exceptions") {
                this.state.showExceptions = true;
            }
        });
        onPatched(() => { this.measure(); });
        onWillUnmount(() => {
            window.removeEventListener("keydown", this._escape,
                                       { capture: true });
            if (this._observer) { this._observer.disconnect(); }
        });
    }

    ic(n, s = 16) { return ic(n, s); }
    num(value) { return Number(value || 0).toLocaleString(); }
    pct(value) { return Math.round(Number(value || 0) * 100); }

    peopleWord(value) {
        return Number(value || 0) === 1 ? _t("person") : _t("people");
    }

    // ================================================================ reading
    async load() {
        this.state.busy = true;
        try {
            this.state.board = await this.orm.call(MODEL, "get_board",
                                                   [this.state.companyId || 0]);
            this.state.companyId = this.state.board.company_id || 0;
            this.state.failed = "";
            if (this.props.onLoaded) {
                this.props.onLoaded(this.state.board);
            }
        } catch (e) {
            this.state.board = null;
            this.state.failed = this._msg(
                e, _t("The map could not be read."));
        } finally {
            this.state.busy = false;
            this.state.loaded = true;
        }
    }

    /**
     * The server's own sentence, or ours — and never the platform's.
     *
     * TWO TRAPS IN ONE THREE-LINE FUNCTION (gotcha GR17).
     *
     * First, the sentence is at `error.data.message` on this platform's RPC
     * error, not at `error.message.data.message`; the older shape survives in
     * several cockpits and quietly never matches.
     *
     * Second — and this is the one that matters — the top-level `.message` of
     * every server error is the literal string "Odoo Server Error". Falling
     * back to it puts the word this product may never say in front of a user,
     * inside a red box, on the screen they are looking at. So it is not a rung
     * on this ladder at all: either the server told us something a person can
     * act on, or we say our own sentence.
     */
    _msg(error, fallback) {
        const data = (error && error.data)
            || (error && error.message && error.message.data);
        return (data && data.message) || fallback;
    }

    get board() { return this.state.board || {}; }
    get allowed() { return !!this.board.allowed; }
    get canEdit() { return !!this.board.can_edit; }
    get segments() { return this.board.segments || []; }
    get schemes() { return this.board.schemes || []; }
    get wires() { return this.board.wires || []; }
    get schemeGroups() { return groupSchemes(this.schemes); }
    get companies() { return this.board.companies || []; }
    get manyCompanies() { return this.companies.length > 1; }
    get exceptionCount() { return (this.board.exceptions || {}).total || 0; }
    get exceptionPeople() { return (this.board.exceptions || {}).people || []; }
    get hasSchemes() { return this.schemes.length > 0; }
    get hasWires() { return this.wires.length > 0; }
    get staleCount() { return this.board.stale || 0; }

    /** The headline sentence: how much of this company the map reaches. */
    get coverLine() {
        const people = this.board.people || 0;
        const covered = this.board.covered || 0;
        if (!people) { return _t("Nobody is on the payroll of this company yet."); }
        if (covered === people) {
            return _t("Every one of this company's %(people)s people is covered by a scheme.",
                      { people: this.num(people) });
        }
        return _t("%(covered)s of %(people)s people are covered by a scheme.",
                  { covered: this.num(covered), people: this.num(people) });
    }

    /** The wires that hang off one segment, in kind-of-run order. */
    wiresFor(key) {
        return this.wires.filter((w) => w.segment === key);
    }

    /** The wires that land on one scheme. */
    wiresOn(configId) {
        return this.wires.filter((w) => w.config_id === configId);
    }

    schemeById(configId) {
        return this.schemes.find((s) => s.id === configId) || null;
    }

    /** A segment's share of coverage, as a ring offset. */
    ringOffset(part, whole) {
        const share = whole ? Math.min(1, Number(part || 0) / whole) : 0;
        return (RING * (1 - share)).toFixed(2);
    }

    ringWord(part, whole) {
        if (!whole) { return _t("nobody yet"); }
        if (part >= whole) { return _t("everyone"); }
        return _t("%(part)s of %(whole)s", { part: this.num(part),
                                             whole: this.num(whole) });
    }

    // ============================================================== the wires
    watchSize() {
        if (!window.ResizeObserver || !this.rootRef.el) { return; }
        this._observer = new ResizeObserver(() => this.measure());
        this._observer.observe(this.rootRef.el);
    }

    /**
     * Measure the real elements and draw one curve per attachment.
     *
     * Positions come from `getBoundingClientRect()` on every paint rather than
     * from anything this component believes about its own width: the board
     * lives in a tab whose canvas the reader can narrow, and a wire drawn from
     * a remembered coordinate is a wire pointing at nothing.
     */
    measure() {
        const host = this.wireRef.el;
        if (!host || !this.state.loaded) { return; }
        const frame = host.getBoundingClientRect();
        if (!frame.width) { return; }
        const paths = [];
        for (const wire of this.wires) {
            const from = host.querySelector(
                `[data-smp-seg="${CSS.escape(wire.segment)}"]`);
            const to = host.querySelector(`[data-smp-scheme="${wire.config_id}"]`);
            if (!from || !to) { continue; }
            const a = from.getBoundingClientRect();
            const b = to.getBoundingClientRect();
            const x1 = a.right - frame.left;
            const y1 = a.top + a.height / 2 - frame.top;
            const x2 = b.left - frame.left;
            const y2 = b.top + b.height / 2 - frame.top;
            const mid = (x2 - x1) / 2;
            paths.push({
                id: wire.id,
                d: `M ${x1} ${y1} C ${x1 + mid} ${y1}, ${x2 - mid} ${y2}, ${x2} ${y2}`,
                lit: this.state.hover === wire.segment
                     || this.state.hover === `scheme-${wire.config_id}`,
                drafted: wire.source !== "manual",
            });
        }
        this.state.paths = paths;
    }

    setHover(key) { this.state.hover = key; }
    clearHover() { this.state.hover = ""; }

    // ================================================================ company
    async pickCompany(ev) {
        this.state.companyId = Number(ev.target.value) || 0;
        this.state.picked = [];
        await this.load();
    }

    setCycleFilterFromSchemes() { /* the board shows every kind at once */ }

    // ============================================================== choosing
    isPicked(key) { return this.state.picked.includes(key); }

    togglePick(key) {
        const at = this.state.picked.indexOf(key);
        if (at >= 0) { this.state.picked.splice(at, 1); }
        else { this.state.picked.push(key); }
    }

    clearPicked() { this.state.picked = []; }

    toggleOpen(key) {
        this.state.open = this.state.open === key ? "" : key;
    }

    onSegmentKey(ev, segment) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.openAttach([segment.key]);
        }
        if (ev.key === " " || ev.key === "Spacebar") {
            ev.preventDefault();
            this.togglePick(segment.key);
        }
    }

    // ============================================================== attaching
    openAttach(keys) {
        if (!this.canEdit) { return; }
        this.state.dialogError = "";
        this.state.attachQuery = "";
        this.state.attaching = { segments: keys.slice(), cycle: "any" };
    }

    openAttachForPicked() {
        if (this.state.picked.length) { this.openAttach(this.state.picked); }
    }

    /** From the exceptions drawer: fix the team this person is in. */
    openAttachForDepartment(departmentId) {
        if (!departmentId) {
            this.notif.add(
                _t("This person is not in a team yet, so there is nothing on the map to attach. Give them a team first."),
                { type: "warning" });
            return;
        }
        this.state.showExceptions = false;
        this.openAttach([`department-${departmentId}`]);
    }

    closeAttach() {
        this.state.attaching = null;
        this.state.dialogError = "";
    }

    setAttachCycle(cycle) {
        if (this.state.attaching) { this.state.attaching.cycle = cycle; }
    }

    onAttachQuery(ev) { this.state.attachQuery = ev.target.value; }

    get attachSegmentLabel() {
        const keys = (this.state.attaching || {}).segments || [];
        if (keys.length > 1) {
            return _t("%(count)s teams", { count: keys.length });
        }
        const found = this._segmentByKey(keys[0]);
        return found ? found.label : "";
    }

    _segmentByKey(key) {
        for (const segment of this.segments) {
            if (segment.key === key) { return segment; }
            for (const child of segment.children || []) {
                if (child.key === key) { return child; }
            }
        }
        return null;
    }

    get attachChoices() {
        const q = this.state.attachQuery.trim().toLowerCase();
        const rows = q
            ? this.schemes.filter(
                (s) => `${s.name} ${s.code}`.toLowerCase().includes(q))
            : this.schemes;
        return groupSchemes(rows);
    }

    get cycleChoices() { return this.board.cycles || []; }

    async attachTo(configId) {
        const chosen = this.state.attaching;
        if (!chosen) { return; }
        this.state.busy = true;
        this.state.dialogError = "";
        let done = 0;
        try {
            for (const key of chosen.segments) {
                const board = await this.orm.call(
                    MODEL, "attach",
                    [key, configId, chosen.cycle, this.state.companyId || 0]);
                this.state.board = board;
                done += 1;
            }
            this.state.picked = [];
            this.closeAttach();
            this.notif.add(
                done === 1
                    ? _t("Attached. The people in that team are paid by this scheme from now on.")
                    : _t("Attached %(count)s teams to this scheme.",
                         { count: done }),
                { type: "success" });
        } catch (e) {
            // GR12 — a refusal about something the reader is LOOKING AT belongs
            // beside it. A toast over an open panel is a sentence about a
            // control the reader can no longer see.
            this.state.dialogError = this._msg(
                e, _t("That scheme could not be attached."));
        } finally {
            this.state.busy = false;
        }
    }

    async detach(wire) {
        if (!this.canEdit) { return; }
        this.state.busy = true;
        try {
            this.state.board = await this.orm.call(
                MODEL, "detach", [wire.id, this.state.companyId || 0]);
            this.notif.add(
                _t("%(segment)s is no longer attached to %(scheme)s.",
                   { segment: wire.segment_label, scheme: wire.config }),
                { type: "info" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("That line could not be removed.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ================================================================= draft
    async startDraft() {
        if (!this.hasSchemes) { return; }
        this.state.drafting = true;
        this.state.skipped = [];
        try {
            this.state.draft = await this.orm.call(
                MODEL, "draft", [this.state.companyId || 0]);
        } catch (e) {
            this.state.draft = null;
            this.notif.add(
                this._msg(e, _t("The last runs could not be read.")),
                { type: "danger" });
            this.state.drafting = false;
        }
    }

    closeDraft() {
        this.state.drafting = false;
        this.state.draft = null;
        this.state.skipped = [];
    }

    get draftRows() { return (this.state.draft || {}).rows || []; }

    draftKey(row) {
        return `${row.department_id}-${row.cycle_type}-${row.config_id}`;
    }

    isSkipped(row) { return this.state.skipped.includes(this.draftKey(row)); }

    toggleSkip(row) {
        const key = this.draftKey(row);
        const at = this.state.skipped.indexOf(key);
        if (at >= 0) { this.state.skipped.splice(at, 1); }
        else { this.state.skipped.push(key); }
    }

    get keptRows() { return this.draftRows.filter((r) => !this.isSkipped(r)); }
    get confidentRows() {
        return this.draftRows.filter((r) => r.confident && !this.isSkipped(r));
    }
    get unsureCount() {
        return this.draftRows.filter((r) => !r.confident).length;
    }

    async acceptDraft(rows) {
        if (!rows.length) { return; }
        this.state.busy = true;
        try {
            const result = await this.orm.call(
                MODEL, "accept_draft", [rows, this.state.companyId || 0]);
            this.state.board = result.board;
            this.closeDraft();
            this.notif.add(
                _t("%(count)s lines written to the map. Every person under them now knows what pays them.",
                   { count: result.created }),
                { type: "success" });
        } catch (e) {
            this.notif.add(
                this._msg(e, _t("The map could not be written.")),
                { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    acceptConfident() { return this.acceptDraft(this.confidentRows); }
    acceptAllKept() { return this.acceptDraft(this.keptRows); }

    // ============================================================ exceptions
    toggleExceptions() {
        this.state.showExceptions = !this.state.showExceptions;
    }

    // ============================================================= recompute
    async recompute() {
        this.state.busy = true;
        try {
            const result = await this.orm.call(
                MODEL, "recompute", [this.state.companyId || 0]);
            this.state.board = result.board;
            this.notif.add(
                result.changed
                    ? _t("%(count)s people now show a different scheme.",
                         { count: this.num(result.changed) })
                    : _t("Everybody was already up to date."),
                { type: "success" });
        } catch (e) {
            this.notif.add(
                this._msg(e, _t("Who is paid by what could not be worked out.")),
                { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // =============================================================== chrome
    /**
     * A click INSIDE a panel is not a click on the scrim behind it.
     *
     * The handler is empty on purpose and it is a method rather than an inline
     * arrow: OWL's `.stop` modifier does the work, and an inline `() => {}` in
     * the markup reads like a control that forgot to be wired.
     */
    onPanelClick() { }

    onEscape(ev) {
        if (ev.key !== "Escape") { return; }
        if (this.state.attaching) { this.closeAttach(); return; }
        if (this.state.drafting) { this.closeDraft(); return; }
        if (this.state.showExceptions) { this.state.showExceptions = false; }
    }

    openStudio() {
        this.action.doAction(this.board.studio_action || "", {
            clearBreadcrumbs: false,
        }).catch(() => this.notif.add(
            _t("The Formula Studio is not installed on this database."),
            { type: "warning" }));
    }
}

// The soft board registry the Mapping screen consults for its scheme tab. The
// dependency runs one way: this module knows the Mapping screen exists, the
// Mapping screen only knows that something may have registered a board.
registry.category("pb_mapping_boards").add("scheme", SchemeMapBoard);
