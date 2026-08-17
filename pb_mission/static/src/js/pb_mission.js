/** @odoo-module **/
/**
 * Mission Control — the Workforce workspace (mockup B).
 *
 * Seven rail items become one room. The shell owns exactly four things:
 *
 *   1. the command bar: brand, the ONE <WfContextBar/> (its person typeahead is
 *      the bar's search — P3b replaces it with the palette), and the user;
 *   2. the lens rail and which lens is showing;
 *   3. the canvas — a definite-height box, because five of the seven cockpits
 *      scroll themselves and three of those pin sticky chrome to their own root
 *      (W20);
 *   4. arrival routing and the in-shell hand-off between lenses.
 *
 * The lenses themselves are the EXISTING cockpit components mounted with
 * `embedded="true"` (W17). Not one line of their logic is re-implemented here,
 * and every one of them still has its own registered client action.
 *
 * What this file deliberately does NOT have: a dock, a person popover, a
 * command palette (all P3b), and any RPC of its own — the only server call it
 * makes is `hasGroup`, to decide which lenses to put on the rail.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { WfContextBar } from "@pb_wf_kit/js/wf_context_bar";
import { WfDock } from "@pb_mission/js/pb_dock";
import { PbToday } from "@pb_today/js/pb_today";
import { PbSchedule } from "@pb_schedule/js/pb_schedule";
import { PbTimeHub } from "@pb_time_hub/js/time_hub";
import { PbTimeoff } from "@pb_timeoff/js/pb_timeoff";
import { PbOtDesk } from "@pb_hr_workforce/js/pb_ot_desk";
import { PbTrips } from "@pb_business_trip/js/pb_trips";
import { PbTeamCockpit } from "@pb_team/js/pb_team";

const LENS_KEY = "pbms.lens.v1";

/**
 * The seven lenses, in rail order.
 *
 * `features` is the per-lens context map (§3.3) and every object here is
 * MODULE-LEVEL on purpose: it is handed straight to <WfContextBar/> as a prop,
 * and a fresh literal per render would make OWL treat the bar's props as changed
 * and recreate it — restarting its department fetch on every keystroke elsewhere
 * on the page. Stable identity per lens, so the bar is only ever updated when
 * the lens actually changes.
 *
 *   department — only the three lenses that actually scope by it. A chip that
 *                changes nothing is worse than no chip.
 *   week / day — Schedule and Time are week-scoped; Today is the `day` segment's
 *                only consumer (§2.3).
 *   person     — ALWAYS. This is the command bar's search: it is the one control
 *                that means the same thing on every lens, and P3b takes it over.
 *   search     — the free-text filter, so only where a lens reads `ctx.search`.
 *                Time Off / Overtime / Trips / Approvals do not (an accepted gap
 *                this phase does not close), so they do not advertise it.
 *
 * `groups` mirrors the gate the lens's RETIRED rail item carried, so collapsing
 * seven doors into one cannot advertise a surface that would answer with an
 * AccessError. It is a visibility hint only — every facade still enforces its
 * own gate server-side, and nothing here widens anything (W12).
 */
const LENSES = [
    {
        key: "today", icon: "activity",
        groups: ["hr_attendance.group_hr_attendance_officer"],
        features: { department: true, week: false, person: true, day: true, search: true },
    },
    {
        key: "schedule", icon: "calendar",
        groups: ["hr_attendance.group_hr_attendance_officer"],
        features: { department: true, week: true, person: true, day: false, search: true },
    },
    {
        key: "time", icon: "clock",
        groups: ["hr_attendance.group_hr_attendance_officer"],
        features: { department: true, week: true, person: true, day: false, search: true },
    },
    {
        key: "timeoff", icon: "umbrella",
        groups: ["hr_holidays.group_hr_holidays_user", "hr.group_hr_manager",
                 "om_hr_payroll.group_hr_payroll_manager"],
        features: { department: false, week: false, person: true, day: false, search: false },
    },
    {
        key: "overtime", icon: "zap",
        groups: ["hr_attendance.group_hr_attendance_manager",
                 "om_hr_payroll.group_hr_payroll_manager"],
        features: { department: false, week: false, person: true, day: false, search: false },
    },
    {
        // its retired rail item was ungated — every internal user could open it
        key: "trips", icon: "plane", groups: [],
        features: { department: false, week: false, person: true, day: false, search: false },
    },
    {
        key: "approvals", icon: "inbox", groups: [],
        features: { department: false, week: false, person: true, day: false, search: false },
    },
];

const LENS_KEYS = LENSES.map((l) => l.key);

export class PbMission extends Component {
    static template = "pb_mission.PbMission";
    static components = {
        WfContextBar, WfDock,
        PbToday, PbSchedule, PbTimeHub, PbTimeoff, PbOtDesk, PbTrips, PbTeamCockpit,
    };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.ctxSvc = useService("wf_context");
        // useState() on the service's reactive is what subscribes the shell —
        // the command bar's chips follow a change made by any lens below.
        this.wf = useState(this.ctxSvc.state);

        const arrival = this._arrival();

        this.state = useState({
            lens: arrival.lens || this._restoreLens(),
            // key -> boolean, resolved once in onWillStart; null while unknown
            allowed: null,
            // The Time lens's arrival payload, shaped as a synthetic `action`
            // prop: `PbTimeHub._arrival()` reads `props.action.context`, so the
            // hub needs no new code and the deep-link protocol keeps exactly one
            // implementation (W26).
            // `{}` rather than null — the hub's `action` prop is a TYPED optional
            // Object, and OWL's dev-mode validation rejects a null on a typed
            // prop that is present (pb_time_hub's own `seed: {}` precedent).
            timeArrival: arrival.timeArrival,
            // bumped on every hand-off so the hub REMOUNTS and re-reads arrival
            timeNonce: 0,
        });

        // Stable handler identity: a fresh inline arrow makes OWL treat the
        // child's props as changed and recreate it, restarting its onWillStart
        // fetch — the refetch trap P1a had to fix twice.
        this._h = {
            onHandOff: (lens, context) => this.handOff(lens, context),
            // Both fire from a dock CLICK, never from its mount or its poll
            // (W21.1) — the dock's lifecycle hooks are pure reads.
            onDockPerson: (employeeId) => this.openPerson(employeeId),
            onDockQueue: () => this.setLens("approvals"),
        };

        onWillStart(async () => { await this._resolveAccess(); });
    }

    ic(n, s = 17) { return ic(n, s); }

    // --------------------------------------------------------------- arrival
    /**
     * What the action that opened the shell asked for.
     *
     * `pb_shell_lens` — which lens to raise.
     * `pb_lens` / `pb_focus` — the Time hub's OWN protocol, forwarded verbatim
     *   so a caller writes the same context whether it targets the hub directly
     *   or the workspace around it. `pb_focus: "queue"` still means "the pinned
     *   person is a FILTER, not a drawer to pop over the queue" (W26).
     *
     * Read ONCE, in setup, from props — never written back anywhere.
     */
    _arrival() {
        const ctx = (this.props.action && this.props.action.context) || {};
        const lens = LENS_KEYS.includes(ctx.pb_shell_lens) ? ctx.pb_shell_lens : null;
        const fwd = {};
        if (ctx.pb_lens) { fwd.pb_lens = ctx.pb_lens; }
        if (ctx.pb_focus) { fwd.pb_focus = ctx.pb_focus; }
        return { lens, timeArrival: Object.keys(fwd).length ? { context: fwd } : {} };
    }

    _restoreLens() {
        try {
            const v = window.localStorage.getItem(LENS_KEY);
            if (LENS_KEYS.includes(v)) { return v; }
        } catch { /* private mode */ }
        // Today: the workspace opens on the question the officer arrives with.
        return "today";
    }

    // ---------------------------------------------------------------- access
    /**
     * Which lenses go on the rail.
     *
     * Seven rail items had five different gates between them. Collapsing them
     * into one door must not advertise a lens whose facade would answer with an
     * AccessError, so the rail asks the same questions the retired rail items
     * asked. `hasGroup` is cached by the user service, so this is one round of
     * small parallel calls per session.
     *
     * Fails OPEN, per group: an xmlid that cannot be resolved means the module
     * is not installed, in which case its lens component is not on the page
     * either — swallowing that as "denied" would hide a lens for the wrong
     * reason. Nothing here is a security boundary; every facade keeps its own.
     */
    async _resolveAccess() {
        const names = [...new Set(LENSES.flatMap((l) => l.groups))];
        const flags = {};
        await Promise.all(names.map(async (g) => {
            try { flags[g] = await user.hasGroup(g); }
            catch { flags[g] = true; }
        }));
        const allowed = {};
        for (const l of LENSES) {
            allowed[l.key] = !l.groups.length || l.groups.some((g) => flags[g]);
        }
        this.state.allowed = allowed;
        // Never open on a lens this persona cannot read — a remembered lens or a
        // stale deep link would otherwise land them on an error state.
        if (!allowed[this.state.lens]) {
            const first = LENSES.find((l) => allowed[l.key]);
            if (first) { this.state.lens = first.key; }
        }
    }

    // ---------------------------------------------------------------- lenses
    get lenses() {
        const labels = {
            today: _t("Today"),
            schedule: _t("Schedule"),
            time: _t("Time"),
            timeoff: _t("Time Off"),
            overtime: _t("Overtime"),
            trips: _t("Trips"),
            // The shell's rail, not the sidebar's: `pb_sidebar.item_approvals`
            // owns the label "Approvals" on the SIDEBAR (the payroll payslip-run
            // cockpit), and W28's uniqueness rule is about that table. Inside
            // this workspace there is only one approvals surface, so the extra
            // word the rail needs would only be noise here.
            approvals: _t("Approvals"),
        };
        const allowed = this.state.allowed;
        return LENSES
            .filter((l) => !allowed || allowed[l.key])
            .map((l) => ({ key: l.key, icon: l.icon, label: labels[l.key] }));
    }

    get lensDef() {
        return LENSES.find((l) => l.key === this.state.lens) || LENSES[0];
    }

    /** The per-lens context map — a STABLE object per lens (see LENSES). */
    get features() { return this.lensDef.features; }

    setLens(key) {
        if (!LENS_KEYS.includes(key) || this.state.lens === key) { return; }
        if (this.state.allowed && !this.state.allowed[key]) { return; }
        this.state.lens = key;
        try { window.localStorage.setItem(LENS_KEY, key); } catch { /* private mode */ }
    }

    /**
     * A lens handing the officer to a sibling lens (§3.5).
     *
     * This is what makes Today's "File correction" stay in the room: standalone
     * it is a `doAction` into the Time hub, embedded it is this — the same W26
     * payload, delivered as the hub's synthetic `action` prop instead of an
     * action context, plus a nonce so the hub remounts and re-reads it.
     *
     * It runs from the child's CLICK handler, never from a mount hook: a child
     * that writes host state during `onWillStart` invalidates the host's render
     * fiber and loops forever, silently (W21/W21.1).
     */
    handOff(lens, context) {
        this.state.timeArrival = context ? { context: { ...context } } : {};
        this.state.timeNonce += 1;
        this.setLens(lens);
    }

    // ---------------------------------------------------------- person door
    /**
     * The shell's ONE person door (W5): the dock, the palette and any lens all
     * arrive here, and all of them arrive from a CLICK.
     *
     * Pinning on the shared context is the whole action — the command bar's
     * chip, the three lenses that own a drawer and (WP-3) the shell's own drawer
     * are all views of the same piece of context (W4/W16).
     */
    openPerson(employeeId) {
        if (!employeeId) { return; }
        this.ctxSvc.set({ personId: employeeId });
    }

    // ------------------------------------------------------------------ user
    get userName() { return user.name || ""; }

    get userInitials() {
        return (this.userName || "U").split(" ").filter(Boolean)
            .map((p) => p[0]).join("").slice(0, 2).toUpperCase() || "U";
    }
}

registry.category("actions").add("pb_workforce", PbMission);
