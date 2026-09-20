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
        this.ic = ic;
        this.state = useState({
            loaded: false,
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
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
            this.state.loaded = true;
        }
    }

    // ------------------------------------------------------------- getters
    get d() { return this.state.data || {}; }
    get columns() { return this.d.companies || []; }
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

    openMany(companyId) {
        this.state.form = { name: "", date_from: "", date_to: "", lines: "" };
        this.state.dialog = { mode: "many", companyId };
    }

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
