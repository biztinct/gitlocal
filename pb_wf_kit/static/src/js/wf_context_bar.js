/** @odoo-module **/
/**
 * <WfContextBar/> — the shared department / week / person selector (W4).
 *
 * Cockpits must NOT ship private pickers any more: they drop this in, and read
 * whatever they need off the wf_context service. Every segment is opt-in via
 * `features`, so the Weekly Entry pilot can show dept+week while a future
 * person-centric board shows week+person.
 *
 * Degradation: if the persona cannot read hr.department or hr.employee the RPC
 * is swallowed and that segment simply does not render — the bar never blocks a
 * cockpit from loading (the handover's "degrade to week-only" rail).
 */
import {
    Component, useState, useRef, useEffect, onWillStart, onWillUpdateProps, onWillUnmount,
} from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { ic } from "@pb_import_kit/js/import_icons";
import { dayLabel, weekLabel } from "./wf_context_service";

const PERSON_LIMIT = 8;
const TYPEAHEAD_MS = 220;

export class WfContextBar extends Component {
    static template = "pb_wf_kit.WfContextBar";
    static props = {
        // which segments to render; omit for dept + week + person
        features: { type: Object, optional: true },
        // extra classes for the host cockpit
        className: { type: String, optional: true },
    };
    static defaultProps = { className: "" };

    setup() {
        this.ctxSvc = useService("wf_context");
        this.orm = useService("orm");

        // useState() on the service's reactive object is what subscribes THIS
        // component to context changes — including changes made by another
        // surface. No manual re-render, and nothing to leak on unmount.
        this.ctx = useState(this.ctxSvc.state);

        this.state = useState({
            departments: [],
            deptDenied: false,     // no read access → hide the segment
            personDenied: false,
            personQuery: "",
            personLabel: "",
            matches: [],
            open: false,
        });

        this._timer = null;
        // which employee id `state.personLabel` currently describes
        this._labelFor = false;
        this.deptRef = useRef("dept");

        // A <select>'s current choice is DOM state, not an attribute: re-rendering
        // with a different `selected` option does not move an already-touched
        // select. Push the value imperatively so a department set by another
        // surface (P1 cross-cockpit sync) is reflected here.
        useEffect(
            (el, id) => { if (el) { el.value = id ? String(id) : ""; } },
            () => [this.deptRef.el, this.ctx.departmentId],
        );

        // The chip's label must follow the PIN wherever it was set. `pickPerson`
        // is only ONE of the doors: a lens avatar calls `openPerson`, which pins
        // straight on the service, and a P3-style shell keeps ONE bar mounted
        // across every lens — so without this the chip renders with no name at
        // all. Effects run AFTER the patch, so this is a plain read, never a
        // write inside somebody else's render fiber (W21).
        useEffect(
            (personId) => { this._syncPersonLabel(personId); },
            () => [this.ctx.personId],
        );

        // A host may turn a segment ON after mount — Mission Control does
        // exactly that when the officer switches from a lens with no department
        // scope to one that has it. `onWillStart` has long since run, so without
        // this the select would render permanently empty.
        onWillUpdateProps(async (next) => {
            const wantsDept = ((next.features || {}).department) !== false;
            if (wantsDept && !this.state.deptDenied && !this.state.departments.length) {
                await this._loadDepartments();
            }
        });

        onWillUnmount(() => { if (this._timer) { clearTimeout(this._timer); } });

        onWillStart(async () => {
            if (this.features.department) { await this._loadDepartments(); }
            if (this.features.person && this.ctx.personId) {
                this._labelFor = this.ctx.personId;
                await this._resolvePersonLabel(this.ctx.personId);
            }
        });
    }

    // ------------------------------------------------------------- accessors
    get features() {
        const f = this.props.features || {};
        return {
            department: f.department !== false,
            week: f.week !== false,
            person: f.person !== false,
            search: f.search === true,      // opt-IN: most surfaces have their own search
            // opt-IN: only day-scoped surfaces (P1b's Today board, day lenses)
            // want a focused day; a week grid would only be confused by it.
            day: f.day === true,
        };
    }

    get weekLabel() { return weekLabel(this.ctx.weekStart); }
    get dayLabel() { return dayLabel(this.ctx.day); }

    ic(n, s = 14) { return ic(n, s); }

    // ------------------------------------------------------------------ data
    async _loadDepartments() {
        try {
            const cids = (user.context && user.context.allowed_company_ids) || [];
            // Record rules already scope hr.department, but the explicit company
            // domain keeps the list correct when several companies are active.
            const domain = cids.length
                ? ["|", ["company_id", "=", false], ["company_id", "in", cids]]
                : [];
            this.state.departments = await this.orm.searchRead(
                "hr.department", domain, ["id", "name"], { order: "name", limit: 400 },
            );
        } catch {
            this.state.deptDenied = true;
            this.state.departments = [];
        }
    }

    /** Keep `state.personLabel` in step with `ctx.personId`, whoever pinned it. */
    _syncPersonLabel(id) {
        if (!this.features.person) { return; }
        if (!id) {
            this._labelFor = false;
            this.state.personLabel = "";
            return;
        }
        if (this._labelFor === id) { return; }   // already resolved (or in flight)
        this._labelFor = id;
        this._resolvePersonLabel(id);
    }

    async _resolvePersonLabel(id) {
        try {
            const [rec] = await this.orm.read("hr.employee", [id], ["name"]);
            this.state.personLabel = rec ? rec.name : "";
        } catch {
            // Persona can't read the employee any more — drop the stale pin
            // rather than showing a blank chip that cannot be cleared.
            this.state.personDenied = true;
            this.ctxSvc.set({ personId: false });
        }
    }

    // -------------------------------------------------------------- handlers
    onDeptChange(ev) {
        const v = ev.target.value;
        this.ctxSvc.set({ departmentId: v ? parseInt(v, 10) : false });
    }

    prevWeek() { this.ctxSvc.shiftWeek(-7); }
    nextWeek() { this.ctxSvc.shiftWeek(7); }
    goToday() { this.ctxSvc.today(); }

    prevDay() { this.ctxSvc.shiftDay(-1); }
    nextDay() { this.ctxSvc.shiftDay(1); }

    onPersonInput(ev) {
        this.state.personQuery = ev.target.value;
        if (this._timer) { clearTimeout(this._timer); }
        const q = this.state.personQuery;
        if (!q || q.length < 2) {
            this.state.matches = [];
            this.state.open = false;
            return;
        }
        this._timer = setTimeout(() => this._search(q), TYPEAHEAD_MS);
    }

    async _search(q) {
        try {
            const res = await this.orm.call("hr.employee", "name_search", [], {
                // Odoo 19 renamed name_search's second parameter `args` -> `domain`
                // (`BaseModel.name_search(name, domain, operator, limit)`), so the
                // old kwarg raises `TypeError: got an unexpected keyword argument
                // 'args'` on EVERY keystroke. The catch below used to swallow that
                // and mark the persona denied, which permanently removed the only
                // person-search control on the page — no console error, no toast,
                // the segment simply was not there any more. Found in P3a, live,
                // when the shell made this the command bar's search.
                name: q, domain: [], operator: "ilike", limit: PERSON_LIMIT,
            });
            // The query may have moved on while the RPC was in flight; a late
            // reply must not repopulate the list under the user's fingers.
            if (this.state.personQuery !== q) { return; }
            this.state.matches = (res || []).map(([id, name]) => ({ id, name }));
            this.state.open = this.state.matches.length > 0;
        } catch (e) {
            this.state.matches = [];
            this.state.open = false;
            // Only an ACCESS failure means "this persona has no person search";
            // anything else is a bug or a blip, and retiring the control for the
            // rest of the session hides the very error that needs fixing.
            const name = (e && e.data && e.data.name) || "";
            if (/AccessError|AccessDenied/.test(name)) {
                this.state.personDenied = true;
            } else {
                console.warn("wf_context: person search failed", e);
            }
        }
    }

    pickPerson(m) {
        this.ctxSvc.set({ personId: m.id });
        // record the resolution BEFORE the effect fires, so picking from the
        // typeahead never costs a second name_search round-trip
        this._labelFor = m.id;
        this.state.personLabel = m.name;
        this.state.personQuery = "";
        this.state.matches = [];
        this.state.open = false;
    }

    clearPerson() {
        this.ctxSvc.set({ personId: false });
        this._labelFor = false;
        this.state.personLabel = "";
        this.state.personQuery = "";
        this.state.matches = [];
        this.state.open = false;
    }

    onPersonBlur() {
        // Let a click on a suggestion land before the list disappears. Writing
        // reactive state (rather than calling render()) is what makes this safe
        // if the cockpit was unmounted while the timer was pending.
        setTimeout(() => { this.state.open = false; }, 150);
    }

    onSearchInput(ev) { this.ctxSvc.set({ search: ev.target.value }); }
}
