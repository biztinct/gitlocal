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
import { Component, useState, onWillStart, onWillUnmount, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { weekLabel } from "./wf_context_service";

const PERSON_LIMIT = 8;
const TYPEAHEAD_MS = 220;

export class WfContextBar extends Component {
    static template = "pb_wf_kit.WfContextBar";
    static props = {
        // which segments to render; omit for all three
        features: { type: Object, optional: true },
        // extra classes for the host cockpit
        className: { type: String, optional: true },
    };
    static defaultProps = { className: "" };

    setup() {
        this.ctx = useService("wf_context");
        this.orm = useService("orm");
        this.personRef = useRef("person");

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

        // Re-render when ANOTHER surface changes the context (P1 cross-cockpit
        // sync). Unsubscribing on unmount matters: cockpits are mounted and
        // destroyed on every sidebar click, and a leaked subscriber would keep
        // a dead component alive for the whole session.
        this._unsub = this.ctx.onChange(() => this.render());

        onWillUnmount(() => {
            this._unsub();
            if (this._timer) { clearTimeout(this._timer); }
        });

        onWillStart(async () => {
            if (this.features.department) { await this._loadDepartments(); }
            if (this.features.person && this.ctx.state.personId) {
                await this._resolvePersonLabel(this.ctx.state.personId);
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
        };
    }

    get weekLabel() { return weekLabel(this.ctx.state.weekStart); }

    get deptLabel() {
        const id = this.ctx.state.departmentId;
        const d = id && this.state.departments.find((x) => x.id === id);
        return d ? d.name : _t("All departments");
    }

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

    async _resolvePersonLabel(id) {
        try {
            const [rec] = await this.orm.read("hr.employee", [id], ["name"]);
            this.state.personLabel = rec ? rec.name : "";
        } catch {
            // Persona can't read the employee any more — drop the stale pin
            // rather than showing a blank chip that cannot be cleared.
            this.state.personDenied = true;
            this.ctx.set({ personId: false });
        }
    }

    // -------------------------------------------------------------- handlers
    onDeptChange(ev) {
        const v = ev.target.value;
        this.ctx.set({ departmentId: v ? parseInt(v, 10) : false });
    }

    prevWeek() { this.ctx.shiftWeek(-7); }
    nextWeek() { this.ctx.shiftWeek(7); }
    goToday() { this.ctx.today(); }

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
        // The query may have moved on while the RPC was in flight; a late reply
        // must not repopulate the list under the user's fingers.
        try {
            const res = await this.orm.call("hr.employee", "name_search", [], {
                name: q, args: [], operator: "ilike", limit: PERSON_LIMIT,
            });
            if (this.state.personQuery !== q) { return; }
            this.state.matches = (res || []).map(([id, name]) => ({ id, name }));
            this.state.open = this.state.matches.length > 0;
        } catch {
            this.state.personDenied = true;
            this.state.matches = [];
            this.state.open = false;
        }
    }

    pickPerson(m) {
        this.ctx.set({ personId: m.id });
        this.state.personLabel = m.name;
        this.state.personQuery = "";
        this.state.matches = [];
        this.state.open = false;
    }

    clearPerson() {
        this.ctx.set({ personId: false });
        this.state.personLabel = "";
        this.state.personQuery = "";
        this.state.matches = [];
        this.state.open = false;
    }

    onPersonBlur() {
        // Let a click on a suggestion land before the list disappears.
        setTimeout(() => { this.state.open = false; this.render(); }, 150);
    }

    onSearchInput(ev) { this.ctx.set({ search: ev.target.value }); }
}
