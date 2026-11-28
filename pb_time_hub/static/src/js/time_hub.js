/** @odoo-module **/
/**
 * The Time hub — one surface, lens tabs, one shared context (mockup A).
 *
 * Timecards + Weekly Entry + Attendance Control collapse into this page. The
 * hub itself owns only four things:
 *
 *   1. the page header + the shared <WfContextBar/> (W4 — no private pickers);
 *   2. the lens tabs and which one is showing;
 *   3. the exception <WfRibbon/>, whose count comes from `pb.time.hub` through
 *      the SAME cohort the Exceptions lens uses;
 *   4. the person drawer — the door every avatar in every lens opens (W5).
 *
 * The lenses themselves are the EXISTING cockpit components mounted with
 * `embedded="true"` (W17). Nothing about their logic is re-implemented here.
 */
import { Component, useState, useEffect, onWillStart, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { WfContextBar } from "@pb_wf_kit/js/wf_context_bar";
import { WfDrawer } from "@pb_wf_kit/js/wf_drawer";
import { WfPersonWeek } from "@pb_wf_kit/js/wf_person_week";
import { WfRibbon } from "@pb_wf_kit/js/wf_ribbon";
import { AttendanceWeekGrid } from "@pb_hr_workforce/js/attendance_weekgrid";
import { PbAttendanceFlow } from "@pb_attendance_flow/js/pb_attendance_flow";
import { TimelineLens } from "./timeline_lens";

const MODEL = "pb.time.hub";
const LENS_KEY = "pbth.lens.v1";
// The four lenses this module mounts itself. Other modules add lenses through
// the "pb_time_hub.lenses" registry (CLOCK-1): each entry is
// { key, label, icon, Component, props?, sequence } and is shown AFTER these,
// in sequence order. A registered lens is mounted with embedded=true and the
// same host doors as the built-ins (onPerson, onChanged, onOpenLens) plus
// `seed`, the props another lens handed over when it opened this one.
const BUILTIN_LENSES = ["timeline", "grid", "exceptions", "import"];
export const lensRegistry = registry.category("pb_time_hub.lenses");

// a stable empty seed, so a registered lens without one never re-renders on
// every hub tick (see the STABLE prop references note in setup)
const EMPTY_SEED = Object.freeze({});

export class PbTimeHub extends Component {
    static template = "pb_time_hub.PbTimeHub";
    static components = {
        WfContextBar, WfDrawer, WfPersonWeek, WfRibbon,
        TimelineLens, AttendanceWeekGrid, PbAttendanceFlow,
    };
    static props = {
        // Also the ARRIVAL channel when the hub is embedded: Mission Control
        // hands it a synthetic `{ context: { pb_lens, pb_focus } }` rather than
        // inventing a second protocol, so `_arrival()` below is unchanged and
        // the deep-link contract (W26) has exactly one implementation.
        action: { type: Object, optional: true },
        // W17 (P3a): the shell owns the page title and the shared context bar.
        // `embedded` suppresses those two ONLY — the lens tabs, the exception
        // ribbon, the person drawer and every facade call stay put.
        embedded: { type: Boolean, optional: true },
        "*": true,
    };
    static defaultProps = { embedded: false };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.actionService = useService("action");

        // Shared context (W4). useState() on the service's reactive is what
        // subscribes the hub — including to changes another surface made.
        this.ctxSvc = useService("wf_context");
        this.wf = useState(this.ctxSvc.state);

        // An incoming deep-link may name the lens to open and ask for the
        // drawer to stay shut — see `_arrival` for why that is not the same as
        // "no person pinned".
        const arrival = this._arrival();

        this.state = useState({
            // props handed to a registered lens when another lens opened it
            // (e.g. the Import lens's "Assign now" → Time clocks on the
            // unknown numbers); keyed by lens, a nonce remounts the lens
            lensSeed: {},
            lensNonce: 0,
            lens: arrival.lens || this._restoreLens(),
            // The Today board hands a person over so the Exceptions queue lands
            // FILTERED; the drawer would sit on top of the very queue the
            // officer was sent to read. Any later person door clears this.
            drawerHidden: arrival.hideDrawer,
            summary: null,
            person: null,
            personLoading: false,
            // remount nonce for the Exceptions lens — bumped when the drawer
            // hands it a correction to seed (see fileCorrection)
            excNonce: 0,
            // guards a double-click while the create RPC is in flight
            filing: false,
            // `{}` rather than null: the prop is a typed optional Object, and a
            // stable identity keeps the lens from re-rendering on every tick.
            seed: {},
        });

        // STABLE prop references. Fresh inline arrows / object literals on every
        // render make OWL treat a child's props as changed and recreate it,
        // which restarts its onWillStart fetch — the infinite-refetch trap the
        // Weekly Entry cockpit already had to fix once.
        this._h = {
            onPerson: (id) => this.openPerson(id),
            onChanged: () => this._loadSummary(),
            onEscalate: (id) => this.escalate(id),
            onFileCorrection: () => this.fileCorrection(),
            onOpenProfile: () => this.openProfile(),
            onOpenLens: (key, seed) => this.openLens(key, seed),
        };

        // Ribbon follows the context week/department, like every lens.
        const off = this.ctxSvc.onChange(() => this._loadSummary());
        onWillUnmount(off);

        // The person drawer is driven ENTIRELY by ctx.personId, so all three
        // doors — a lens avatar, the bar's typeahead, a deep link restoring a
        // pinned person — land on exactly the same code path (§2.4).
        useEffect(
            (personId, weekStart) => { this._loadPerson(personId, weekStart); },
            () => [this.wf.personId, this.wf.weekStart],
        );

        onWillStart(async () => { await this._loadSummary(); });
    }

    ic(n, s = 15) { return ic(n, s); }

    // ------------------------------------------------------------ lenses
    get lenses() {
        return [
            { key: "timeline", label: _t("Timeline"), icon: "activity" },
            { key: "grid", label: _t("Week Grid"), icon: "table" },
            { key: "exceptions", label: _t("Exceptions"), icon: "alert" },
            { key: "import", label: _t("Import"), icon: "upload" },
            ...this.extraLenses.map((l) => ({ key: l.key, label: l.label, icon: l.icon })),
        ];
    }

    /** Lenses other modules registered, in sequence order, never shadowing a
     *  built-in key. */
    get extraLenses() {
        return lensRegistry.getAll()
            .filter((l) => l && l.key && l.Component && !BUILTIN_LENSES.includes(l.key))
            .sort((a, b) => (a.sequence || 100) - (b.sequence || 100));
    }

    get lensKeys() {
        return [...BUILTIN_LENSES, ...this.extraLenses.map((l) => l.key)];
    }

    /** The registered lens showing now, or null when a built-in is. */
    get activeExtra() {
        return this.extraLenses.find((l) => l.key === this.state.lens) || null;
    }

    /** A registered lens's own static props (stable identity). */
    get activeExtraProps() {
        const l = this.activeExtra;
        return (l && l.props) || EMPTY_SEED;
    }

    lensSeedFor(key) {
        return this.state.lensSeed[key] || EMPTY_SEED;
    }

    /** One lens opens another, handing it props (a click handler only). */
    openLens(key, seed) {
        if (!this.lensKeys.includes(key)) { return; }
        if (key === "exceptions") {
            // the Exceptions lens already has its own hand-off: a correction
            // id to open, with a nonce that remounts it (see fileCorrection)
            if (seed && seed.correction_id) {
                this.state.seed = { correction_id: seed.correction_id };
                this.state.excNonce += 1;
            }
            this.setLens(key);
            return;
        }
        this.state.lensSeed = { ...this.state.lensSeed, [key]: seed || {} };
        this.state.lensNonce += 1;
        if (this.state.lens === key) {
            // already showing: the nonce in its t-key remounts it with the seed
            return;
        }
        this.setLens(key);
    }

    lensCount(key) {
        const counts = (this.state.summary && this.state.summary.lens_counts) || {};
        return counts[key] || 0;
    }

    /**
     * What the action that opened this hub asked for.
     *
     * `pb_lens`  — open on this lens instead of the remembered one.
     * `pb_focus` — "queue" means "the person on the context is a FILTER, not a
     *              drawer to open": the Today board pins the person so the
     *              Exceptions lens narrows to them, and popping the drawer on
     *              arrival would cover the queue it just filtered.
     *
     * Read once, in setup, from props — never written back anywhere.
     */
    _arrival() {
        const ctx = (this.props.action && this.props.action.context) || {};
        const lens = this.lensKeys.includes(ctx.pb_lens) ? ctx.pb_lens : null;
        return { lens, hideDrawer: ctx.pb_focus === "queue" && !!lens };
    }

    _restoreLens() {
        try {
            const v = window.localStorage.getItem(LENS_KEY);
            if (this.lensKeys.includes(v)) { return v; }
        } catch { /* private mode */ }
        // Default to the grid: it is the surface the owner named as the pain
        // point ("time entry in a table format"), so the hub opens on it.
        return "grid";
    }

    setLens(key) {
        if (!this.lensKeys.includes(key) || this.state.lens === key) { return; }
        this.state.lens = key;
        try { window.localStorage.setItem(LENS_KEY, key); } catch { /* private mode */ }
    }

    // -------------------------------------------------------------- data
    async _loadSummary() {
        try {
            // personId travels with it: the Exceptions lens narrows its queue
            // by the same pin, so an unfiltered summary would badge the tab
            // with the whole week's count above a queue showing one person's
            // (P1b §2.4).
            this.state.summary = await this.orm.call(MODEL, "get_hub_summary", [
                this.wf.departmentId || false, this.wf.weekStart,
                this.wf.personId || false,
            ]);
        } catch (e) {
            // A ribbon that cannot load must never take the hub down with it —
            // the lenses below it are the actual work surface.
            this.state.summary = null;
            console.warn("Time hub: summary unavailable", e);
        }
    }

    get ribbon() {
        const s = this.state.summary;
        if (!s || !s.ribbon || !(s.open_exceptions || s.ribbon.extra)) { return null; }
        return s.ribbon;
    }

    /** CLOCK-3: with only time-clock alerts open, the ribbon's door opens
     *  the Time clocks lens instead of Exceptions. */
    get ribbonLens() {
        const r = this.ribbon;
        const lens = r && r.lens;
        return lens && this.lensKeys.includes(lens) ? lens : "exceptions";
    }

    get ribbonActionLabel() {
        return this.ribbonLens === "exceptions" ? _t("Review exceptions →") : _t("Open time clocks →");
    }

    openRibbonLens() { this.setLens(this.ribbonLens); }

    // ------------------------------------------------------- person door
    /** The ONE way to open the drawer: pin the person on the shared context. */
    openPerson(employeeId) {
        if (!employeeId) { return; }
        // A person door was CLICKED, so the drawer is wanted again even if this
        // hub was opened by a deep-link that asked for the queue.
        this.state.drawerHidden = false;
        this.ctxSvc.set({ personId: employeeId });
        // Re-clicking the person already pinned by a deep-link changes nothing
        // on the context, so nothing would re-render; the flag above is the
        // whole state change and it must land on its own.
    }

    closePerson() {
        // Clearing the pin is what closes the drawer — the bar's person chip
        // and the drawer are two views of the same piece of context.
        this.state.drawerHidden = false;
        this.ctxSvc.set({ personId: false });
    }

    async _loadPerson(personId, weekStart) {
        if (!personId) {
            this.state.person = null;
            return;
        }
        this.state.personLoading = true;
        try {
            const data = await this.orm.call(MODEL, "get_person_week", [personId, weekStart]);
            // A late reply must not paint over a person the officer has since
            // changed (or a drawer they have since closed).
            if (this.wf.personId !== personId) { return; }
            this.state.person = data && data.employee ? data : null;
            if (!this.state.person) {
                this.notif.add(_t("That employee is not available in this company."),
                    { type: "warning" });
                this.ctxSvc.set({ personId: false });
            }
        } catch (e) {
            this.state.person = null;
            this.notif.add((e && e.data && e.data.message) || _t("Could not load that person."),
                { type: "danger" });
        } finally {
            this.state.personLoading = false;
        }
    }

    get drawerTitle() {
        const p = this.state.person;
        return (p && p.employee.name) || _t("Loading…");
    }

    get drawerSubtitle() {
        const p = this.state.person;
        if (!p) { return ""; }
        return [p.employee.job, p.employee.dept, p.employee.badge]
            .filter((x) => x).join(" · ");
    }

    // ------------------------------------------------------ drawer actions
    /**
     * Hand the Exceptions lens a correction to open, prefilled for this person
     * and the most useful day of their week: the first flagged day, else today
     * if it is in the week, else the Monday. Remounting the lens (nonce) is what
     * makes the hand-off unambiguous — see PbAttendanceFlow.seedCorrection.
     */
    async fileCorrection() {
        const p = this.state.person;
        if (!p || this.state.filing) { return; }
        const flagged = p.days.find(
            (d) => d.flags.includes("missing") || d.flags.includes("open"))
            || p.days.find((d) => d.is_today)
            || p.days[0];
        const missing = flagged.flags.includes("missing");

        // The WRITE happens HERE, in the click handler — never in the lens's
        // mount (W21). OWL restarts an in-flight mount whenever the parent
        // re-renders, so a create in `onWillStart` fires twice; two concurrent
        // transactions cannot see each other's row, so even the server-side
        // reuse guard cannot dedupe them. The lens is handed an ID and only
        // READS it, which is safe to repeat.
        this.state.filing = true;
        try {
            const corr = await this.orm.call("pb.attendance.flow", "create_correction", [{
                employee_id: p.employee.id,
                date: flagged.date,
                correction_type: missing ? "create" : "adjust",
                exception_kind: missing ? "missing_punch" : false,
                reason: _t("Correction filed from the person drawer for %(date)s.",
                           { date: flagged.date }),
                // repeated hand-offs for the same person+day reopen the same
                // draft rather than stacking duplicates in the pipeline
                reuse_draft: true,
            }]);
            this.state.seed = { correction_id: corr.id };
            this.state.excNonce += 1;
            this.setLens("exceptions");
            this.closePerson();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("Could not file a correction."),
                { type: "danger" });
        } finally {
            this.state.filing = false;
        }
    }

    /**
     * The Week Grid's over-ceiling door: an employee past their monthly or
     * annual OT cap is a problem the exceptions queue exists to resolve, so
     * the grid hands them here rather than dead-ending on a red bar.
     */
    escalate(employeeId) {
        this.setLens("exceptions");
        // Carry the person across with them: the drawer's "File correction" is
        // the concrete next step for someone past their ceiling, and the queue
        // stays visible behind it.
        this.openPerson(employeeId);
    }

    /** Native-form escape as a DIALOG with a return path (W5). */
    openProfile() {
        const p = this.state.person;
        if (!p) { return; }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.employee",
            res_id: p.employee.id,
            views: [[false, "form"]],
            target: "new",
        });
    }

    // The drawer's number formatting (fmt / fmtDelta / deltaTone / dayTone)
    // moved to <WfPersonWeek/> in pb_wf_kit with the markup it serves (W6).
}

registry.category("actions").add("pb_time_hub", PbTimeHub);
