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

            // GROUP P7 — the wires as a GESTURE (polish item P2).
            // `dragging` is what is currently in the reader's hand: a team on
            // its way to a scheme, or a wire on its way off the board.
            dragging: null,      // { kind, keys, label, wire }
            dropOn: 0,           // the scheme the pointer is over
            overTrash: false,    // the pointer is over the take-it-off bar
            traced: 0,           // the wire being followed with the pointer
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
                // GROUP P7 — a traced wire lights the same way a hovered end
                // does, so following a line and hovering a row are one idea.
                lit: this.state.hover === wire.segment
                     || this.state.hover === `scheme-${wire.config_id}`
                     || this.state.traced === wire.id,
                dim: !!this.state.traced && this.state.traced !== wire.id,
                drafted: wire.source !== "manual",
            });
        }
        this.state.paths = paths;
    }

    setHover(key) { this.state.hover = key; }
    clearHover() { this.state.hover = ""; }

    // ========================== GROUP P7 · the wires as a gesture (item P2)
    //
    // Three gestures, and each one has a keyboard equivalent beside it,
    // because a board whose only verb is a drag is a board half the people
    // who need it cannot use.
    //
    //   * DRAG A TEAM ONTO A SCHEME   — Enter on the team, or the + button.
    //   * HOVER A WIRE TO TRACE IT    — Tab to the wire chip; it lights both
    //                                   ends and dims everything else.
    //   * PULL A WIRE OFF THE BOARD   — Delete or Backspace on the chip, or
    //                                   the chip's own unlink button.
    //
    // The drop lands on the SAME call the side panel makes — one door, one
    // set of refusals — so a scheme attached by dragging and a scheme
    // attached by pressing are the same record with the same history.

    /** Is this segment part of what is being dragged right now? */
    isDragging(key) {
        const held = this.state.dragging;
        return !!held && held.kind === "segment" && held.keys.includes(key);
    }

    /** The teams a drag carries: the ticked ones if this is one of them. */
    _dragKeys(key) {
        return this.state.picked.includes(key) ? [...this.state.picked] : [key];
    }

    onSegmentDragStart(ev, segment) {
        if (!this.canEdit) { return; }
        const keys = this._dragKeys(segment.key);
        this.state.dragging = {
            kind: "segment", keys, label: segment.label, wire: null,
        };
        this.state.traced = 0;
        if (ev.dataTransfer) {
            ev.dataTransfer.effectAllowed = "link";
            // A payload is required for the drag to start at all in some
            // browsers; nothing ever reads it back.
            ev.dataTransfer.setData("text/plain", keys.join(","));
        }
    }

    onDragEnd() {
        this.state.dragging = null;
        this.state.dropOn = 0;
        this.state.overTrash = false;
    }

    onSchemeDragOver(ev, scheme) {
        const held = this.state.dragging;
        if (!held || held.kind !== "segment") { return; }
        ev.preventDefault();
        if (ev.dataTransfer) { ev.dataTransfer.dropEffect = "link"; }
        this.state.dropOn = scheme.id;
    }

    onSchemeDragLeave(scheme) {
        if (this.state.dropOn === scheme.id) { this.state.dropOn = 0; }
    }

    async onSchemeDrop(ev, scheme) {
        const held = this.state.dragging;
        this.onDragEnd();
        if (!held || held.kind !== "segment") { return; }
        ev.preventDefault();
        // The SAME door the panel uses, with the panel's own default kind of
        // run, so a drop and a press produce the identical line.
        this.state.attaching = { segments: held.keys, cycle: "any" };
        this.state.dialogError = "";
        await this.attachTo(scheme.id);
    }

    // -------------------------------------------------- pulling a wire off
    onWireDragStart(ev, wire) {
        if (!this.canEdit) { return; }
        this.state.dragging = {
            kind: "wire", keys: [], label: wire.config, wire,
        };
        this.state.traced = wire.id;
        if (ev.dataTransfer) {
            ev.dataTransfer.effectAllowed = "move";
            ev.dataTransfer.setData("text/plain", String(wire.id));
        }
    }

    onTrashDragOver(ev) {
        const held = this.state.dragging;
        if (!held || held.kind !== "wire") { return; }
        ev.preventDefault();
        if (ev.dataTransfer) { ev.dataTransfer.dropEffect = "move"; }
        this.state.overTrash = true;
    }

    onTrashDragLeave() { this.state.overTrash = false; }

    async onTrashDrop(ev) {
        const held = this.state.dragging;
        this.onDragEnd();
        if (!held || held.kind !== "wire" || !held.wire) { return; }
        ev.preventDefault();
        await this.detach(held.wire);
    }

    /** The sentence on the bar that appears while a wire is in your hand. */
    get trashLabel() {
        const held = this.state.dragging;
        if (!held || held.kind !== "wire" || !held.wire) { return ""; }
        return _t("Drop here to take %(scheme)s off %(segment)s",
                  { scheme: held.wire.config,
                    segment: held.wire.segment_label });
    }

    get draggingWire() {
        const held = this.state.dragging;
        return !!held && held.kind === "wire";
    }

    // ------------------------------------------------------- tracing a wire
    traceWire(wireId) { this.state.traced = wireId; }
    clearTrace() { if (!this.state.dragging) { this.state.traced = 0; } }

    /** A row is dimmed while a wire is being traced and is not on it. */
    isTraced(kind, key) {
        const id = this.state.traced;
        if (!id) { return false; }
        const wire = this.wires.find((w) => w.id === id);
        if (!wire) { return false; }
        return kind === "segment"
            ? wire.segment === key
            : wire.config_id === key;
    }

    /** Delete or Backspace on a wire chip takes it off — the drag, typed. */
    onWireKey(ev, wire) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.traceWire(wire.id);
            return;
        }
        if (ev.key === "Delete" || ev.key === "Backspace") {
            ev.preventDefault();
            this.detach(wire);
        }
    }

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


    /**
     * What the board says back, now that a wiring change can become a request.
     *
     * Who is paid by which scheme travels a route where one is published, and
     * the board comes back with the proposal instead of the change. A toast
     * saying "attached" over a map that is exactly as it was is a control
     * that lies.
     *
     * Returns true when the change really happened.
     */
    _saidSoFar(board, okMsg, tone = "success") {
        const held = board && board.proposal;
        if (held && !held.applied) {
            this.notif.add(held.message || _t("Sent for approval."),
                           { type: "info" });
            return false;
        }
        if (okMsg) { this.notif.add(okMsg, { type: tone }); }
        return true;
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
            this._saidSoFar(
                this.state.board,
                done === 1
                    ? _t("Attached. The people in that team are paid by this scheme from now on.")
                    : _t("Attached %(count)s teams to this scheme.",
                         { count: done }));
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
            this._saidSoFar(
                this.state.board,
                _t("%(segment)s is no longer attached to %(scheme)s.",
                   { segment: wire.segment_label, scheme: wire.config }),
                "info");
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
            // `accept_draft` answers with the PROPOSAL where a route is
            // published, and with the written map where one is not.
            this._saidSoFar(
                { proposal: result.applied === undefined ? null : result },
                _t("%(count)s lines written to the map. Every person under them now knows what pays them.",
                   { count: result.created }));
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
