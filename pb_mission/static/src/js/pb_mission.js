/** @odoo-module **/
/**
 * Mission Control — the Workforce workspace (mockup B).
 *
 * Seven rail items become one room. The shell owns exactly six things:
 *
 *   1. the command bar: brand, the ONE <WfContextBar/>, the ⌘K palette that
 *      takes over its search, and the user;
 *   2. the lens rail and which lens is showing;
 *   3. the canvas — a definite-height box, because five of the seven cockpits
 *      scroll themselves and three of those pin sticky chrome to their own root
 *      (W20);
 *   4. arrival routing and the in-shell hand-off between lenses;
 *   5. the ambient Needs-you dock (pb_dock.js), mounted once beside every lens;
 *   6. the PERSON SURFACE: one shared <WfPersonWeek/> drawer for the four
 *      lenses that do not own one, so a person pinned from the dock, the
 *      palette or a deep link opens SOMEWHERE, on every lens.
 *
 * The lenses themselves are the EXISTING cockpit components mounted with
 * `embedded="true"` (W17). Not one line of their logic is re-implemented here,
 * and every one of them still has its own registered client action.
 *
 * The shell ships no model, no ACL and no facade of its own: it reads
 * `hasGroup` for the rail, `pb.team` for the dock (the Team Approvals cockpit's
 * own queue) and `pb.time.hub.get_person_week` for the drawer (the panel the
 * Time, Today and Schedule lenses already fetch). Everything it calls existed
 * before it did.
 */
import { Component, useState, useEffect, onWillStart, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { isMacOS } from "@web/core/browser/feature_detection";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { WfContextBar } from "@pb_wf_kit/js/wf_context_bar";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
// FLEET P4. Workforce is sold on its own, so a company can be on Payobook
// without it. Mission Control keeps its own shell (not refactoring it onto
// the kit is a standing non-goal), so it borrows the ONE page the kit draws
// for "your company has not got this" rather than growing a second one that
// would drift from it.
import { featureGate, featuresState } from "@pb_hub/js/hub_features";
import { HubFeatureOff } from "@pb_hub/js/hub_feature_off";
import { WfCommandPalette } from "@pb_wf_kit/js/wf_command_palette";
import { WfDrawer } from "@pb_wf_kit/js/wf_drawer";
import { WfPersonWeek } from "@pb_wf_kit/js/wf_person_week";
import { WfDock } from "@pb_mission/js/pb_dock";
import { PbToday } from "@pb_today/js/pb_today";
import { PbSchedule } from "@pb_schedule/js/pb_schedule";
import { PbTimeHub } from "@pb_time_hub/js/time_hub";
import { PbTimeoff } from "@pb_timeoff/js/pb_timeoff";
import { PbOtDesk } from "@pb_hr_workforce/js/pb_ot_desk";
import { PbTrips } from "@pb_business_trip/js/pb_trips";
import { PbTeamCockpit } from "@pb_team/js/pb_team";
import { PbCloseLens } from "@pb_mission/js/pb_close_lens";

const LENS_KEY = "pbms.lens.v1";
/** The person drawer's data contract, documented in pb_time_hub/models. */
const PERSON_MODEL = "pb.time.hub";

/**
 * The ⌘K ACTION registry (§3.5) — the "verbs" third of the palette.
 *
 * Each entry names a lens plus ONE of two hand-off channels, and there is a
 * hard rule about which: an action is listed here only where the target
 * affordance ALREADY EXISTS. A palette entry that opens nothing is worse than
 * no palette entry (W5, and W29's lesson about doors that can only error).
 *
 *   `arrival` — the W26 deep-link protocol (`pb_lens` / `pb_focus`), already
 *               implemented by the Time hub. Nothing new is invented for it.
 *   `cmd`     — the P3b `pb_cmd` protocol: a one-shot instruction handed to the
 *               lens as a prop and consumed by nonce. Only four lenses
 *               implement it, and a lens ignoring an unknown cmd is CORRECT.
 */
const PALETTE_ACTIONS = [
    { id: "new_shift", lens: "schedule", cmd: "quick_create", icon: "plus",
      label: _t("New shift"), sublabel: _t("Schedule") },
    { id: "copy_week", lens: "schedule", cmd: "copy_week", icon: "copy",
      label: _t("Copy week forward"), sublabel: _t("Schedule") },
    { id: "set_budget", lens: "schedule", cmd: "set_budget", icon: "banknote",
      label: _t("Set labour budget"), sublabel: _t("Schedule") },
    { id: "import_punches", lens: "time", arrival: { pb_lens: "import" },
      icon: "upload", label: _t("Import punches"), sublabel: _t("Time") },
    { id: "file_correction", lens: "time",
      arrival: { pb_lens: "exceptions", pb_focus: "queue" },
      icon: "fileText", label: _t("File a correction"), sublabel: _t("Time") },
    { id: "open_map", lens: "today", cmd: "map", icon: "mapPin",
      label: _t("Open the driver map"), sublabel: _t("Today") },
    { id: "apply_leave", lens: "timeoff", cmd: "apply", icon: "umbrella",
      label: _t("Apply time off on behalf"), sublabel: _t("Time Off") },
    { id: "bonus_review", lens: "overtime", cmd: "bonus", icon: "sigma",
      label: _t("Bonus hours review"), sublabel: _t("Overtime") },
    { id: "lock_week", lens: "close", cmd: "lock_week", icon: "lock",
      label: _t("Lock the week"), sublabel: _t("Close") },
];

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
 *   person     — OFF on every lens, since P3b. The bar's person typeahead WAS
 *                the command bar's search; the ⌘K palette replaces it with one
 *                input that finds people, lenses AND actions, and the shell
 *                renders the pinned-person chip itself beside the launcher. The
 *                kit's `person` feature is untouched and still serves every
 *                standalone cockpit — this is the shell's opinion, not a
 *                deletion (W6).
 *   search     — the free-text filter, so only where a lens reads `ctx.search`.
 *                Time Off / Overtime / Trips / Approvals do not (an accepted gap
 *                this phase does not close), so they do not advertise it.
 *
 * `groups` mirrors the gate the lens's RETIRED rail item carried, so collapsing
 * seven doors into one cannot advertise a surface that would answer with an
 * AccessError. It is a visibility hint only — every facade still enforces its
 * own gate server-side, and nothing here widens anything (W12).
 *
 * `ownsPersonDrawer` is P3b's capability flag. Time, Today and Schedule each
 * already mount their OWN <WfPersonWeek/> drawer, wired to their own actions
 * (Time's "File correction" hand-off, Schedule's roster). The shell's drawer is
 * for the other four, and the flag is what stops the officer getting TWO panels
 * for one person on the three that already work. It is a declaration, not a
 * behaviour: a lens that grows its own drawer sets the flag in the same commit.
 */
const LENSES = [
    {
        key: "today", icon: "activity",
        groups: ["hr_attendance.group_hr_attendance_officer"],
        features: { department: true, week: false, person: false, day: true, search: true },
        ownsPersonDrawer: true,
    },
    {
        key: "schedule", icon: "calendar",
        groups: ["hr_attendance.group_hr_attendance_officer"],
        features: { department: true, week: true, person: false, day: false, search: true },
        ownsPersonDrawer: true,
    },
    {
        key: "time", icon: "clock",
        groups: ["hr_attendance.group_hr_attendance_officer"],
        features: { department: true, week: true, person: false, day: false, search: true },
        ownsPersonDrawer: true,
    },
    {
        key: "timeoff", icon: "umbrella",
        groups: ["hr_holidays.group_hr_holidays_user", "hr.group_hr_manager",
                 "om_hr_payroll.group_hr_payroll_manager"],
        features: { department: false, week: false, person: false, day: false, search: false },
    },
    {
        key: "overtime", icon: "zap",
        groups: ["hr_attendance.group_hr_attendance_manager",
                 "om_hr_payroll.group_hr_payroll_manager"],
        features: { department: false, week: false, person: false, day: false, search: false },
    },
    {
        // its retired rail item was ungated — every internal user could open it
        key: "trips", icon: "plane", groups: [],
        features: { department: false, week: false, person: false, day: false, search: false },
    },
    {
        key: "approvals", icon: "inbox", groups: [],
        features: { department: false, week: false, person: false, day: false, search: false },
    },
    {
        // P4's eighth lens, and the only one that is not an embedded cockpit —
        // there was no Close surface to embed (W17 is about REUSE, not about
        // forbidding a new surface). It sits LAST on the rail on purpose: the
        // manager's week is Today -> Plan -> Approve -> Close, and Close is the
        // end of the loop.
        //
        // Gated like the lock gates it drives (§3.5): a plain attendance
        // officer may READ the board's facade, but locking a week and waiving a
        // flag are manager decisions, so offering them a lens whose every
        // action would be refused is W29's door that can only produce an error.
        key: "close", icon: "lock",
        groups: ["hr_attendance.group_hr_attendance_manager",
                 "om_hr_payroll.group_hr_payroll_manager"],
        features: { department: true, week: true, person: false, day: false, search: true },
    },
];

const LENS_KEYS = LENSES.map((l) => l.key);

export class PbMission extends Component {
    static template = "pb_mission.PbMission";
    static components = {
        WfContextBar, WfDock, WfDrawer, WfPersonWeek,
        PbToday, PbSchedule, PbTimeHub, PbTimeoff, PbOtDesk, PbTrips, PbTeamCockpit,
        PbCloseLens, HubBackChip, HubFeatureOff,
    };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.actionService = useService("action");
        this.overlay = useService("overlay");
        this.ctxSvc = useService("wf_context");
        // useState() on the service's reactive is what subscribes the shell —
        // the command bar's chips follow a change made by any lens below.
        this.wf = useState(this.ctxSvc.state);
        // FLEET P4. The same subscription, for the same reason: a switch
        // flipped on the platform reaches an open page within a minute, and
        // this shell has to repaint when it does. Null when the Platform Link
        // is not installed here — and then Workforce is simply on.
        this._features = featuresState(this.env);
        if (this._features) { useState(this._features); }

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

            // ----- the shell person surface (§3.3) -----
            // the get_person_week payload, or null while loading / unresolved
            person: null,
            /**
             * A PRE-EXISTING pin is context, not a request (W26's corollary,
             * and PbSchedule's own `drawerHidden` precedent). The shared context
             * is persisted, so without this every arrival in Workforce would
             * open a drawer over whatever the officer actually came to look at.
             * Any explicit person DOOR — a dock card, a palette pick, a lens
             * avatar — goes through `openPerson`, which clears it.
             *
             * `pb_focus: "queue"` says the same thing louder: the deep link
             * pinned a person as a FILTER, so the drawer must stay shut (W26).
             */
            personHidden: !!this.ctxSvc.state.personId
                || arrival.focus === "queue",
            // the pinned person's NAME, for the command bar's chip
            personName: "",

            // ----- the pb_cmd channel (§3.6) -----
            // ONE instruction at a time, consumed by NONCE. The lens tracks the
            // last nonce it ran, so the shell never has to clear this — and
            // never has to be written to by a child, which is what a "consumed"
            // callback from a mount hook would be (W21.1).
            // An arriving pb_cmd seeds it at nonce 1 — the lens tracks the last
            // nonce it ran and 0 is its initial value, so a seeded 1 is a real
            // instruction while a bare mount stays inert.
            cmd: arrival.cmd
                ? { name: arrival.cmd, nonce: 1 }
                : { name: "", nonce: 0 },
        });

        // Which employee `state.personName` currently describes.
        // The return door a caller wrote onto the context (openHub). Read ONCE
        // from props and never written back — the arrival protocol's rule since
        // Cycle 1. `null` when nobody sent us, so the chip is ABSENT rather than
        // inert (W5/W29).
        this.back = hubBack(this.props);
        this._nameFor = false;
        // The overlay's remove() while the palette is up; null when it is not.
        this._closePalette = null;

        // Stable handler identity: a fresh inline arrow makes OWL treat the
        // child's props as changed and recreate it, restarting its onWillStart
        // fetch — the refetch trap P1a had to fix twice.
        this._h = {
            onHandOff: (lens, context) => this.handOff(lens, context),
            // Both fire from a dock CLICK, never from its mount or its poll
            // (W21.1) — the dock's lifecycle hooks are pure reads.
            onDockPerson: (employeeId) => this.openPerson(employeeId),
            onDockQueue: () => this.setLens("approvals"),
            onClosePerson: () => this.closePerson(),
            onOpenProfile: () => this.openProfile(),
        };

        // ⌘K on macOS, Ctrl-K everywhere else — the hotkey service already maps
        // meta→"control" per platform. `bypassEditableProtection` because the
        // officer is usually mid-type in a lens filter when they reach for it,
        // and a shortcut that only works when nothing is focused is a shortcut
        // nobody learns. Registered by the SHELL, so it exists exactly as long
        // as the workspace does.
        useHotkey("control+k", () => this.openPalette(),
                  { bypassEditableProtection: true });

        /**
         * The palette lives in the OVERLAY container, which is a sibling of the
         * whole action host — so it does NOT unmount when this shell does. Leave
         * it up and it becomes an orphan whose every row calls back into a
         * destroyed component: open ⌘K, click a sidebar item, and the palette is
         * still floating over the next screen (found live, P3b).
         *
         * This is the price of W43's "win by location, not by z-index": the
         * thing that makes the overlay immune to the shell's stacking also makes
         * it immune to the shell's lifecycle, so the host has to close what it
         * opened.
         */
        onWillUnmount(() => this.closePalette());

        // The chip's label follows the PIN wherever it was set — the dock, the
        // palette, a lens avatar or a restored context. An effect runs AFTER
        // the patch, so resolving the name is a read, never a write inside
        // somebody else's render fiber (W21/W36).
        useEffect(
            (personId) => { this._syncPersonName(personId); },
            () => [this.wf.personId],
        );

        /**
         * Load the drawer's week when — and only when — the SHELL is the one
         * showing it. On Time, Today and Schedule the lens fetches its own copy,
         * so firing here as well would be two requests for one panel.
         *
         * An EFFECT, not a mount hook wired to the lens: effects run after the
         * patch, so this is a plain read outside anybody's render fiber (W21,
         * and the WfContextBar person-label precedent, W36). `get_person_week`
         * is a pure read with no write path in it, which is what makes it safe
         * to re-enter at all.
         */
        useEffect(
            (personId, weekStart) => {
                if (!personId) {
                    this.state.person = null;
                    return;
                }
                this._loadPerson(personId, weekStart);
            },
            () => [this.shellOwnsDrawer ? this.wf.personId : false,
                   this.wf.weekStart],
        );

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
        return {
            lens,
            // the shell's OWN reading of pb_focus: it decides whether the person
            // surface opens on arrival, exactly as the hub decides for its own
            focus: ctx.pb_focus || "",
            // IA Cycle 6: pb_cmd on ARRIVAL. W44's channel already carries one
            // instruction to one lens by nonce; until now only this shell's own
            // palette could put a verb on it, so a foreign cockpit could deep
            // link to the Overtime lens but not to its BONUS view — the surface
            // Insights' bonus-hours tile is actually about. The verb is accepted
            // only for the lens being opened, and a lens that does not know it
            // ignores it, which is correct behaviour (W44.3) and the reason the
            // protocol is safe to widen: an unknown verb lands on nothing rather
            // than on the wrong thing.
            cmd: (lens && typeof ctx.pb_cmd === "string") ? ctx.pb_cmd : "",
            timeArrival: Object.keys(fwd).length ? { context: fwd } : {},
        };
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
            close: _t("Close"),
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

    // -------------------------------------------------------- person surface
    /**
     * The shell's ONE person door (W5): the dock, the palette and any lens all
     * arrive here, and all of them arrive from a CLICK.
     *
     * Pinning on the shared context is the whole action — the command bar's
     * chip, the three lenses that own a drawer and the shell's own drawer are
     * all views of the same piece of context (W4/W16).
     */
    openPerson(employeeId) {
        if (!employeeId) { return; }
        // A door was CLICKED, so the drawer is wanted even if this session
        // arrived with a restored pin (or a `pb_focus: "queue"` deep link).
        // Re-clicking the person already pinned changes nothing on the context,
        // so this flag is the whole state change and it must land on its own.
        this.state.personHidden = false;
        this.ctxSvc.set({ personId: employeeId });
    }

    closePerson() {
        // Clearing the pin is what closes it: the bar's chip and the drawer are
        // two views of one piece of context, so closing one must not leave the
        // other insisting a person is selected.
        this.state.personHidden = false;
        this.ctxSvc.set({ personId: false });
    }

    /** True on the four lenses that do NOT bring their own person drawer. */
    get shellOwnsDrawer() { return !this.lensDef.ownsPersonDrawer; }

    get personDrawerOpen() {
        return !!this.wf.personId && this.shellOwnsDrawer && !this.state.personHidden;
    }

    /**
     * §2's documented failure mode, applied here: the palette and the dock can
     * both hand over a person `get_person_week` cannot resolve — a different
     * company, or a persona without attendance-officer access on a lens that
     * does not need it (Trips is ungated). The pattern is toast-and-clear, not
     * a drawer stuck on "Loading…".
     *
     * W40: the catch narrows nothing. It reports the server's own words, clears
     * the pin so the surface is usable again, and warns on the console so the
     * failure stays observable.
     */
    async _loadPerson(personId, weekStart) {
        try {
            const data = await this.orm.call(PERSON_MODEL, "get_person_week",
                                             [personId, weekStart]);
            // a late reply must not paint over a person since changed or closed
            if (this.wf.personId !== personId) { return; }
            if (data && data.employee) {
                this.state.person = data;
                return;
            }
            this.state.person = null;
            this.notif.add(_t("That employee is not available in this company."),
                           { type: "warning" });
            this.ctxSvc.set({ personId: false });
        } catch (e) {
            if (this.wf.personId !== personId) { return; }
            this.state.person = null;
            console.warn("pb_mission: could not load the person week", e);
            this.notif.add((e && e.data && e.data.message)
                || _t("Could not load that person."), { type: "danger" });
            this.ctxSvc.set({ personId: false });
        }
    }

    get personTitle() {
        const p = this.state.person;
        return (p && p.employee.name) || _t("Loading…");
    }

    get personSubtitle() {
        const p = this.state.person;
        if (!p) { return ""; }
        return [p.employee.job, p.employee.dept, p.employee.badge]
            .filter((x) => x).join(" · ");
    }

    /**
     * The command bar's chip needs a NAME, and every door that pins a person
     * writes only an id. One `read`, cached against the id it describes, and a
     * failure degrades to an id-less chip rather than clearing a pin the
     * officer just set — the drawer's own load is where an unusable person is
     * detected and cleared.
     */
    async _syncPersonName(id) {
        if (!id) {
            this._nameFor = false;
            this.state.personName = "";
            return;
        }
        if (this._nameFor === id) { return; }
        this._nameFor = id;
        // the drawer may already have the answer — no second round trip for it
        const p = this.state.person;
        if (p && p.employee && p.employee.id === id) {
            this.state.personName = p.employee.name;
            return;
        }
        try {
            const [rec] = await this.orm.read("hr.employee", [id], ["name"]);
            if (this._nameFor !== id) { return; }
            this.state.personName = rec ? rec.name : "";
        } catch (e) {
            console.warn("pb_mission: could not resolve the pinned person", e);
            this.state.personName = "";
        }
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

    // ------------------------------------------- is this company on Workforce
    //
    // Not a permission — a sale. Somebody who has not bought Workforce has
    // no rail entry for it and no palette rows, but a bookmark still points
    // here, and an empty workspace is the dead end this answers.
    get workforceOff() {
        const g = featureGate(this.env, "workforce");
        return !g.shown || g.locked;
    }

    get workforceOffText() { return featureGate(this.env, "workforce").text; }

    // ------------------------------------------------------------ ⌘K palette
    /** "⌘K" on macOS, "Ctrl K" elsewhere — the label must match the key. */
    get paletteHint() { return isMacOS() ? "⌘K" : "Ctrl K"; }

    /**
     * Mounted through the Odoo OVERLAY service, deliberately.
     *
     * The palette has to paint above a lens's `position: fixed; z-index 1050`
     * modals. Doing that from inside the workspace would mean stacking shell
     * chrome above 1050, which is exactly the fight W37 exists to prevent — and
     * the 60px biz rail overlay at 25 would lose it too. The overlay container
     * is a sibling of the whole action host at 1600, so the palette wins by
     * LOCATION rather than by z-index, and the shell's stacking rules are
     * untouched: nothing in pb_mission.scss changes for this feature.
     */
    openPalette() {
        if (this._closePalette) { return; }      // already up; ⌘K is not a toggle
        this._closePalette = this.overlay.add(WfCommandPalette, {
            lenses: this.lenses,
            actions: this.paletteActions,
            onPickLens: (key) => this.setLens(key),
            onPickPerson: (id) => this.openPerson(id),
            onRunAction: (id) => this.runPaletteAction(id),
            onClose: () => this.closePalette(),
        }, {
            onRemove: () => { this._closePalette = null; },
        });
    }

    closePalette() {
        if (this._closePalette) { this._closePalette(); }
        this._closePalette = null;
    }

    /**
     * Only the actions whose LENS this persona can open. The rail already hides
     * a lens the facade would refuse; offering a verb that lands on it would
     * put the same dead end back through another door.
     */
    get paletteActions() {
        const allowed = this.state.allowed;
        return PALETTE_ACTIONS
            .filter((a) => !allowed || allowed[a.lens])
            .map((a) => ({ id: a.id, label: a.label, sublabel: a.sublabel,
                           icon: a.icon }));
    }

    /**
     * Run one — from the palette's click/Enter, never from a lifecycle hook.
     *
     * Two channels, and which one an action uses is a property of the TARGET,
     * not a preference: the Time hub already implements the W26 arrival
     * protocol, so its two verbs ride that unchanged; the other four lenses get
     * the `pb_cmd` nonce.
     */
    runPaletteAction(id) {
        const a = PALETTE_ACTIONS.find((x) => x.id === id);
        if (!a) { return; }
        if (this.state.allowed && !this.state.allowed[a.lens]) { return; }
        if (a.arrival) {
            this.handOff(a.lens, a.arrival);
            return;
        }
        this.state.cmd = { name: a.cmd, nonce: this.state.cmd.nonce + 1 };
        this.setLens(a.lens);
    }

    // ------------------------------------------------------------------ user
    get userName() { return user.name || ""; }

    get userInitials() {
        return (this.userName || "U").split(" ").filter(Boolean)
            .map((p) => p[0]).join("").slice(0, 2).toUpperCase() || "U";
    }
}

registry.category("actions").add("pb_workforce", PbMission);
