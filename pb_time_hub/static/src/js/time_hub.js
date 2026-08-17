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
import { WfRibbon } from "@pb_wf_kit/js/wf_ribbon";
import { AttendanceWeekGrid } from "@pb_hr_workforce/js/attendance_weekgrid";
import { PbAttendanceFlow } from "@pb_attendance_flow/js/pb_attendance_flow";
import { TimelineLens } from "./timeline_lens";

const MODEL = "pb.time.hub";
const LENS_KEY = "pbth.lens.v1";
const LENSES = ["timeline", "grid", "exceptions", "import"];

export class PbTimeHub extends Component {
    static template = "pb_time_hub.PbTimeHub";
    static components = {
        WfContextBar, WfDrawer, WfRibbon,
        TimelineLens, AttendanceWeekGrid, PbAttendanceFlow,
    };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.actionService = useService("action");

        // Shared context (W4). useState() on the service's reactive is what
        // subscribes the hub — including to changes another surface made.
        this.ctxSvc = useService("wf_context");
        this.wf = useState(this.ctxSvc.state);

        this.state = useState({
            lens: this._restoreLens(),
            summary: null,
            person: null,
            personLoading: false,
            // remount nonce for the Exceptions lens — bumped when the drawer
            // hands it a correction to seed (see fileCorrection)
            excNonce: 0,
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
        ];
    }

    lensCount(key) {
        const counts = (this.state.summary && this.state.summary.lens_counts) || {};
        return counts[key] || 0;
    }

    _restoreLens() {
        try {
            const v = window.localStorage.getItem(LENS_KEY);
            if (LENSES.includes(v)) { return v; }
        } catch { /* private mode */ }
        // Default to the grid: it is the surface the owner named as the pain
        // point ("time entry in a table format"), so the hub opens on it.
        return "grid";
    }

    setLens(key) {
        if (!LENSES.includes(key) || this.state.lens === key) { return; }
        this.state.lens = key;
        try { window.localStorage.setItem(LENS_KEY, key); } catch { /* private mode */ }
    }

    // -------------------------------------------------------------- data
    async _loadSummary() {
        try {
            this.state.summary = await this.orm.call(MODEL, "get_hub_summary", [
                this.wf.departmentId || false, this.wf.weekStart,
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
        if (!s || !s.ribbon || !s.open_exceptions) { return null; }
        return s.ribbon;
    }

    // ------------------------------------------------------- person door
    /** The ONE way to open the drawer: pin the person on the shared context. */
    openPerson(employeeId) {
        if (!employeeId) { return; }
        this.ctxSvc.set({ personId: employeeId });
    }

    closePerson() {
        // Clearing the pin is what closes the drawer — the bar's person chip
        // and the drawer are two views of the same piece of context.
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
    fileCorrection() {
        const p = this.state.person;
        if (!p) { return; }
        const flagged = p.days.find(
            (d) => d.flags.includes("missing") || d.flags.includes("open"))
            || p.days.find((d) => d.is_today)
            || p.days[0];
        this.state.seed = {
            employee_id: p.employee.id,
            date: flagged.date,
            kind: flagged.flags.includes("missing") ? "missing_punch" : false,
        };
        this.state.excNonce += 1;
        this.setLens("exceptions");
        this.closePerson();
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

    // ------------------------------------------------------------ format
    /** "8.0" / "—" — an unplanned day has no schedule, it is not a 0 h one. */
    fmt(v, planned = true) {
        if (!planned) { return "—"; }
        if (!v) { return "0"; }
        return String(Math.round(v * 10) / 10);
    }

    fmtDelta(v) {
        if (!v) { return "0"; }
        const n = Math.round(v * 10) / 10;
        return n > 0 ? `+${n}` : String(n);
    }

    deltaTone(v) {
        if (!v || Math.abs(v) < 0.05) { return ""; }
        return v > 0 ? "pos" : "neg";
    }

    dayTone(d) {
        if (d.flags.includes("missing")) { return "miss"; }
        if (d.flags.includes("over")) { return "ed"; }
        if (!d.entered) { return "zero"; }
        return "";
    }
}

registry.category("actions").add("pb_time_hub", PbTimeHub);
