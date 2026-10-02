/** @odoo-module **/
/**
 * Public holidays — every company's year, side by side.
 *
 * The hero moment is the sentence at the top: **"Next: Tết on Tue 17 Feb —
 * 12 days away"**, over a year strip and one column per company. That is the
 * question a person actually arrives with; the list underneath is the answer
 * they check afterwards.
 *
 * READ BY EVERYBODY, WRITTEN BY THE HR TEAM. The lens carries no group gate at
 * all (the rail item it joins is Mission Control's), and `pb.holidays` decides
 * what the buttons may do: `can_edit` comes back from the server, so the Add
 * and Paste doors are absent for a reader rather than present and refused
 * (W29/W5).
 *
 * Icons come from the shared `ic()` registry in `pb_import_kit`, never from a
 * module-local map and never an emoji.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.holidays";

/** "1 day" / "2 days", never "1 day(s)" (R46/R219). */
function counted(n, one, many) {
    return `${n} ${n === 1 ? one : many}`;
}

export class PbHolidays extends Component {
    static template = "pb_timeoff.PbHolidays";
    static props = {
        action: { type: Object, optional: true },
        // Mission Control owns the page identity, so `embedded` drops the
        // hero's eyebrow and title and nothing else — the year strip and the
        // two doors are this surface's own and must survive (W17).
        embedded: { type: Boolean, optional: true },
        "*": true,
    };
    static defaultProps = { embedded: false };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.ic = ic;
        this.state = useState({
            loaded: false,
            view: "month", month: new Date().getMonth(), company: "all", workspace: {batches:[],policies:[]},
            importing: null, importBusy: false,
            busy: false,
            data: null,
            year: false,
            // the dialog: null | {mode: "one"|"many", companyId, …}
            dialog: null,
            form: { name: "", date_from: "", date_to: "", lines: "" },
        });
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        this.state.busy = true;
        try {
            this.state.data = await this.orm.call(MODEL, "year",
                                                  [this.state.year]);
            this.state.year = this.state.data.year;
            this.state.workspace = await this.orm.call(MODEL, "import_workspace", [this.state.year]);
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
            this.state.loaded = true;
        }
    }

    // ------------------------------------------------------------- getters
    get d() { return this.state.data || {}; }
    get columns() { return (this.d.companies || []).filter(c => this.state.company === "all" || String(c.id) === this.state.company); }
    get years() { return this.d.years || []; }
    get canEdit() { return !!this.d.can_edit; }

    /**
     * The headline, built as ONE expression.
     *
     * A sentence split across several `t-esc` nodes loses the whitespace
     * between them and reads "Next: Tếton Tue" (R34).
     */
    get headline() {
        const n = this.d.next || this.d.next_ahead;
        if (!n) {
            return _t("No public holidays are on any calendar yet.");
        }
        const away = n.days_away;
        const when = away <= 0 ? _t("today")
            : away === 1 ? _t("tomorrow")
            : _t("%s away", counted(away, _t("day"), _t("days")));
        const line = _t("Next: %(what)s at %(where)s on %(when_date)s — %(away)s",
                        { what: n.name, where: n.company,
                          when_date: n.label || n.date, away: when });
        // The year being looked at runs out before the question does, so the
        // sentence says which year it has had to look past. Built as ONE
        // expression: a sentence split across several `t-esc` nodes loses the
        // whitespace between them (R34).
        return this.d.next
            ? line
            : _t("Nothing else in %(year)s. %(line)s",
                 { year: this.state.year, line });
    }

    columnNote(col) {
        if (!col.has_calendar) {
            return _t("This company has no working hours set up yet, so it "
                      + "cannot hold a holiday calendar.");
        }
        if (!col.count) {
            return _t("No days on this calendar for %s yet.", this.state.year);
        }
        return counted(col.count, _t("day off"), _t("days off"));
    }

    get monthLabel() { return new Date(this.state.year, this.state.month, 1).toLocaleDateString(undefined, {month:"long", year:"numeric"}); }
    get calendarDays() {
        const first = new Date(this.state.year, this.state.month, 1);
        const offset = (first.getDay() + 6) % 7;
        return Array.from({length:42}, (_,index) => {
            const day = new Date(this.state.year, this.state.month, index - offset + 1);
            const iso = `${day.getFullYear()}-${String(day.getMonth()+1).padStart(2,"0")}-${String(day.getDate()).padStart(2,"0")}`;
            const events = this.columns.flatMap(col => col.rows.filter(r => r.date <= iso && (r.date_to || r.date) >= iso).map(r => ({...r,company:col.name,country:col.country_code})));
            return {iso, day:day.getDate(), current:day.getMonth() === this.state.month, today:iso === this.d.today, events};
        });
    }
    changeMonth(delta) { const date = new Date(this.state.year, this.state.month + delta, 1); this.state.month = date.getMonth(); if (date.getFullYear() !== this.state.year) this.pickYear(date.getFullYear()); }
    startImport(companyId) { this.state.importing = {company_id:String(companyId || this.columns[0]?.id || ""),source:"",lines:"",batch:null,ack:false}; }
    async prepareImport(useSource=false) {
        const form = this.state.importing; if (this.state.importBusy) return;
        this.state.importBusy = true;
        try { form.batch = await this.orm.call(MODEL,"prepare_import",[Number(form.company_id),this.state.year,useSource ? "Supplied 2026 workbook · country sheets" : form.source,form.lines,useSource]); }
        catch(e) { this.notif.add(this._err(e),{type:"danger"}); }
        finally { this.state.importBusy = false; }
    }
    openBatch(batch) { this.state.importing = {batch:JSON.parse(JSON.stringify(batch)),ack:false}; }
    get importReady() { const form=this.state.importing; return !!(form?.batch && form.ack && form.batch.rows.every(r=>r.decision !== "review") && form.batch.rows.some(r=>r.decision === "include")); }
    async saveImport(publish=false) {
        const form=this.state.importing; if (this.state.importBusy || (publish && !this.importReady)) return;
        this.state.importBusy=true;
        try {
            await this.orm.call(MODEL,"resolve_import",[form.batch.id,Object.fromEntries(form.batch.rows.map(r=>[String(r.id),r.decision]))]);
            if (publish) { const result=await this.orm.call(MODEL,"publish_import",[form.batch.id]); this.notif.add(`${result.added} holidays published to the calendar.`,{type:"success"}); }
            else this.notif.add("Review decisions saved. The calendar has not changed.",{type:"success"});
            this.state.importing=null;await this.load();
        } catch(e) { this.notif.add(this._err(e),{type:"danger"}); }
        finally { this.state.importBusy=false; }
    }
    async editPolicies() { try {await this.action.doAction(await this.orm.call(MODEL,"policy_action",[]));} catch(e) {this.notif.add(this._err(e),{type:"danger"});} }

    // -------------------------------------------------------------- year
    pickYear(year) {
        if (year === this.state.year) { return; }
        this.state.year = year;
        this.load();
    }

    // ------------------------------------------------------------ dialogs
    openOne(companyId) {
        this.state.form = { name: "", date_from: "", date_to: "", lines: "" };
        this.state.dialog = { mode: "one", companyId };
    }

    openMany(companyId) { this.startImport(companyId); }

    closeDialog() { this.state.dialog = null; }

    onField(field, ev) { this.state.form[field] = ev.target.value; }

    get dialogCompany() {
        const id = this.state.dialog && this.state.dialog.companyId;
        return this.columns.find((c) => c.id === id) || { name: "" };
    }

    get canSaveOne() {
        const f = this.state.form;
        return !!(f.name.trim() && f.date_from);
    }

    get canSaveMany() {
        return !!(this.state.form.lines || "").trim();
    }

    async saveOne() {
        const f = this.state.form;
        await this._write(async () => {
            await this.orm.call(MODEL, "add", [
                this.state.dialog.companyId, f.name, f.date_from,
                f.date_to || false]);
            this.notif.add(_t("Added."), { type: "success" });
        });
    }

    async saveMany() {
        await this._write(async () => {
            const res = await this.orm.call(MODEL, "add_many", [
                this.state.dialog.companyId, this.state.form.lines]);
            const added = counted(res.added, _t("day"), _t("days"));
            this.notif.add(
                res.already.length
                    ? _t("%(added)s added. Already there: %(names)s.",
                         { added, names: res.already.join(", ") })
                    : _t("%s added.", added),
                { type: "success" });
        });
    }

    async remove(row) {
        await this._write(async () => {
            await this.orm.call(MODEL, "remove", [row.id]);
            this.notif.add(_t("Taken off the calendar."), { type: "success" });
        });
    }

    /** One write, one refusal path, one reload. */
    async _write(fn) {
        this.state.busy = true;
        try {
            await fn();
            this.state.dialog = null;
            await this.load();
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    _err(e) {
        return (e && e.data && e.data.message) || (e && e.message)
            || _t("That did not work.");
    }
}

registry.category("actions").add("pb_holidays", PbHolidays);
