/** @odoo-module **/
import { Component, useState, onWillStart, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useFullCalendar } from "@web/views/calendar/hooks/full_calendar_hook";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { HubShell } from "@pb_hub/js/hub_shell";
import { SETTINGS_CATEGORIES } from "@pb_settings/js/settings_hub";
import { COMP_GATE } from "@pb_comp_ben/js/comp_ben_palette";
import { PbPaycalBoard } from "@pb_comp_ben/js/paycal_board";
import { PbHiringBoard } from "./hiring_board";
const { DateTime } = luxon;
const SOURCES = { meetings: _t("Meetings"), interviews: _t("Interviews"), payroll: _t("Payroll"), google: _t("Google"), microsoft: _t("Microsoft"), leave: _t("Time off") };


class CalendarGrid extends Component {
    static template = "pb_hiring.CalendarGrid";
    static props = { "*": true };
    setup() {
        this.fc = useFullCalendar("calendar", {
            initialView: { day: "timeGridDay", week: "timeGridWeek", month: "dayGridMonth" }[this.props.view],
            initialDate: this.props.date, timeZone: this.props.zone, firstDay: 1,
            headerToolbar: false, height: 650, fixedWeekCount: false, weekends: true,
            nowIndicator: true, editable: false, selectable: false, allDaySlot: true,
            scrollTime: "07:00:00", dayMaxEventRows: 4, eventMinHeight: 35,
            slotLabelFormat: { hour: "2-digit", minute: "2-digit", hour12: false },
            eventTimeFormat: { hour: "2-digit", minute: "2-digit", hour12: false },
            events: (_, done) => done(this.props.events.map(e => ({ id: e.key, title: e.title,
                start: e.allday ? e.start.slice(0,10) : e.start.replace(" ","T") + "Z",
                end: e.allday ? e.stop.slice(0,10) : e.stop.replace(" ","T") + "Z",
                allDay: e.allday, classNames: ["pbcal-fc-event",e.source] }))),
            eventClick: info => this.props.onSelect(this.props.events.find(e => e.key === info.event.id)),
            eventDidMount: info => { info.el.title = `${info.timeText || ""} ${info.event.title}`; },
        });
    }
}

export class SharedCalendar extends Component {
    static template = "pb_hiring.SharedCalendar";
    static components = { CalendarGrid };
    static props = { "*": true };
    setup() {
        this.orm = useService("orm"); this.actions = useService("action");
        this.notification = useService("notification"); this.dialog = useService("dialog");
        this.state = useState({ busy: true, error: "", events: [], caps: {}, date: DateTime.now().toISODate(),
            zone: "UTC", view: window.innerWidth < 700 ? "agenda" : "week", query: "", hidden: [], selected: null, truncated: false, syncing: "" });
        useExternalListener(window, "keydown", ev => { if (ev.key === "Escape") this.state.selected = null; });
        this.zones = [...new Set([DateTime.local().zoneName, "UTC", "Australia/Sydney", "Asia/Ho_Chi_Minh", "Asia/Singapore", "Asia/Kolkata", "Europe/London", "America/New_York"])];
        this.views = [{ key: "day", label: _t("Day") }, { key: "week", label: _t("Week") }, { key: "month", label: _t("Month") }, { key: "agenda", label: _t("Agenda") }];
        this.hours = Array.from({ length: 24 }, (_, i) => ({ key: i, label: String(i).padStart(2,"0") + ":00" }));
        onWillStart(async () => {
            try {
                this.state.caps = await this.orm.call("pb.shared.calendar", "capabilities", []);
                this.state.zone = this.state.caps.timezone;
                this.zones = [...new Set([this.state.zone, ...this.zones])];
                this.state.date = DateTime.now().setZone(this.state.zone).toISODate();
                await this.load();
            } catch (e) { this.fail(e); }
        });
    }
    fail(e) { this.state.busy = false; this.state.error = e.data?.message || e.message || _t("Calendar could not load. Please retry."); }
    get anchor() { return DateTime.fromISO(this.state.date, { zone: this.state.zone }); }
    get range() {
        let start = this.anchor.startOf("day"), end;
        if (this.state.view === "month") { start = start.startOf("month").startOf("week"); end = this.anchor.endOf("month").endOf("week").plus({ milliseconds: 1 }); }
        else if (this.state.view === "week") { start = start.startOf("week"); end = start.plus({ days: 7 }); }
        else { end = start.plus({ days: this.state.view === "agenda" ? 31 : 1 }); }
        return { start, end };
    }
    async load() {
        const generation = this._generation = (this._generation || 0) + 1;
        this.state.busy = true; this.state.error = ""; this.state.selected = null;
        try {
            const r = this.range;
            const payload = await this.orm.call("pb.shared.calendar", "events", [r.start.toUTC().toFormat("yyyy-MM-dd HH:mm:ss"), r.end.toUTC().toFormat("yyyy-MM-dd HH:mm:ss"), r.start.toISODate(), r.end.toISODate()]);
            if (generation !== this._generation) return;
            this.state.events = payload.events; this.state.truncated = payload.truncated;
            this.state.busy = false;
        } catch (e) { if (generation === this._generation) this.fail(e); }
    }
    async setView(v) { this.state.view = v; await this.load(); }
    async move(n) { this.state.date = this.anchor.plus(this.state.view === "month" ? { months: n } : { days: n * (this.state.view === "week" ? 7 : this.state.view === "agenda" ? 31 : 1) }).toISODate(); await this.load(); }
    async today() { this.state.date = DateTime.now().setZone(this.state.zone).toISODate(); await this.load(); }
    get heading() { return this.state.view === "month" ? this.anchor.toFormat("LLLL yyyy") : this.range.start.toFormat("d LLL") + " – " + this.range.end.minus({ days: 1 }).toFormat("d LLL yyyy"); }
    get sources() {
        const keys = this.props.interviewsOnly ? ["interviews"] : this.props.payrollOnly ? ["payroll"] : ["meetings", "interviews", "leave", "google", "microsoft", ...(this.state.caps.payroll ? ["payroll"] : [])];
        return keys.map(key => ({ key, label: SOURCES[key], on: !this.state.hidden.includes(key), count: this.state.events.filter(e => e.source === key).length }));
    }
    toggle(key) { this.state.hidden = this.state.hidden.includes(key) ? this.state.hidden.filter(k => k !== key) : [...this.state.hidden,key]; }
    stamp(e, end = false) { const raw = end ? e.stop : e.start; return e.allday ? DateTime.fromISO(raw.slice(0,10), { zone: this.state.zone }) : DateTime.fromSQL(raw,{ zone: "UTC" }).setZone(this.state.zone); }
    get visible() { const q = this.state.query.toLocaleLowerCase().trim(); return this.state.events.filter(e => (!this.props.interviewsOnly || e.source === "interviews") && (!this.props.payrollOnly || e.source === "payroll") && !this.state.hidden.includes(e.source) && (!q || `${e.title} ${e.subtitle} ${e.location}`.toLocaleLowerCase().includes(q))).sort((a,b) => this.stamp(a).toMillis() - this.stamp(b).toMillis()); }
    when(e) { return e.allday ? _t("All day") : this.stamp(e).toFormat("HH:mm") + "–" + this.stamp(e,true).toFormat("HH:mm"); }
    source(e) { return SOURCES[e.source]; }
    dateLabel(e) { return this.stamp(e).toFormat("ccc, d LLL yyyy"); }
    get days() {
        const { start, end } = this.range; const days = [];
        for (let d = start; d < end; d = d.plus({ days: 1 })) {
            const events = this.visible.filter(e => this.stamp(e) < d.plus({days:1}) && this.stamp(e,true) > d);
            days.push({ key: d.toISODate(), label: d.toFormat("ccc d"), number: d.day, today: d.toISODate() === DateTime.now().setZone(this.state.zone).toISODate(), outside: d.month !== this.anchor.month, events });
        }
        return days;
    }
    async openSelected() {
        const e = this.state.selected; if (!e) return;
        try { const action = await this.orm.call("pb.shared.calendar", "open_record", [e.key]); await this.actions.doAction(action, { onClose: () => this.load() }); } catch (err) { this.notification.add(err.data?.message || err.message, { type: "danger" }); }
    }
    async newEvent() { await this.actions.doAction(await this.orm.call("pb.shared.calendar", "new_event", []), { onClose: () => this.load() }); }
    async payrollDates() { await this.actions.doAction(await this.orm.call("pb.shared.calendar", "payroll_dates_action", []), { onClose: () => this.load() }); }
    async settings() { await this.actions.doAction(await this.orm.call("pb.shared.calendar", "settings_action", [])); }
    get providers() { return ["google", "microsoft"].map(key => ({ key, label: key === "google" ? "Google Calendar" : "Microsoft 365", status: this.state.caps.connections?.[key + "_calendar"] || "missing_credentials" })); }
    providerStatus(p) { return { sync_active: _t("Connected"), sync_stopped: _t("Not syncing"), sync_paused: _t("Paused by administrator"), missing_credentials: _t("Administrator setup required") }[p.status] || p.status; }
    async providerChange(p, op) { try { this.state.caps = await this.orm.call("pb.shared.calendar", "provider_action", [p.key,op]); } catch(e) { this.notification.add(e.data?.message || e.message, { type: "warning" }); } }
    connect(p) {
        if (this.providers.some(x => x.key !== p.key && x.status === "sync_active")) { this.notification.add(_t("Pause your other calendar connection first to avoid copying meetings between accounts."), { type: "warning" }); return; }
        this.dialog.add(ConfirmationDialog, { title: _t("Connect your calendar"), body: _t("This connects your primary calendar with two-way synchronisation. Meeting changes can update your connected calendar and invitations. Payroll deadlines stay inside Payobook. Continue to your provider to consent?"), confirmLabel: _t("Continue"), confirm: () => this.sync(p) });
    }
    async sync(p) {
        this.state.syncing = p.key;
        try {
            const result = await rpc(`/${p.key}_calendar/sync_data`, { model: "calendar.event", fromurl: window.location.href });
            if (result.status === "need_auth" && result.url) { window.location.assign(result.url); return; }
            if (result.status === "need_config_from_admin") this.notification.add(_t("Ask an administrator to configure this provider in Settings → Connect → Calendars."), { type: "warning" });
            else if (result.status === "sync_stopped") this.notification.add(_t("Resume the connection, then synchronise again."), { type: "info" });
            else if (result.status === "sync_paused") this.notification.add(_t("Your administrator has paused synchronisation."), { type: "warning" });
            else this.notification.add(_t("Calendar synchronisation completed."), { type: "success" });
            this.state.caps = await this.orm.call("pb.shared.calendar", "capabilities", []); await this.load();
        } catch(e) { this.notification.add(_t("Could not synchronise. Reconnect your account or ask your administrator to check provider access."), { type: "danger", sticky: true }); }
        finally { this.state.syncing = ""; }
    }
}
class FindInterviewTime extends Component {
    static template = "pb_hiring.FindInterviewTime"; static props = { "*": true };
    setup() { this.actions = useService("action"); }
    open() { return this.actions.doAction("pb_hiring.action_pb_hiring_hub", { additionalContext: { pb_lens: "applicants" } }); }
}
export class CalendarHub extends Component {
    static template = "pb_hiring.CalendarHub"; static components = { HubShell }; static props = { "*": true };
    setup() { this.config = { key: "calendar", brand: { label: _t("Calendar"), icon: "calendar" }, defaultLens: "calendar", lenses: [
        { key: "calendar", label: _t("My calendar"), icon: "calendar", Component: SharedCalendar },
        { key: "availability", label: _t("Find a time"), icon: "clock", Component: FindInterviewTime, probe: { model: "pb.hiring", method: "can_open" } },
        { key: "connections", label: _t("Connect"), icon: "link", Component: SharedCalendar, props: { connectionsOnly: true } },
    ] }; }
}
registry.category("actions").add("pb_shared_calendar", CalendarHub);
class CalendarAdmin extends Component {
    static template = "pb_hiring.CalendarAdmin"; static props = { "*": true };
    setup() { this.orm = useService("orm"); this.actions = useService("action"); }
    async open() { await this.actions.doAction(await this.orm.call("pb.shared.calendar", "settings_action", [])); }
}
registry.category("actions").add("pb_calendar_admin", CalendarAdmin);
registry.category(SETTINGS_CATEGORIES).add("calendars", { key: "calendars", group: "integrations", label: _t("Calendars"), icon: "calendar", groups: ["base.group_system"], blurb: _t("Google and Microsoft application setup. Each person connects their own account."), cards: [{ id: "calendars", tag: "pb_calendar_admin", icon: "calendar", label: _t("Calendar providers"), sub: _t("Configure Google and Microsoft OAuth. This does not grant access to payroll or private meetings.") }] });
PbHiringBoard.components = { ...(PbHiringBoard.components || {}), SharedCalendar };
patch(PbHiringBoard.prototype, { setup() { super.setup(...arguments); this.state.interviewCalendar = false; } });

class PayrollCalendar extends Component {
    static template = "pb_hiring.PayrollCalendar";
    static components = { SharedCalendar, PbPaycalBoard }; static props = { "*": true };
    setup() {
        this.state = useState({ planning: false, canPlan: false });
        const orm = useService("orm");
        onWillStart(async () => { this.state.canPlan = (await orm.call("pb.shared.calendar", "capabilities", [])).payroll_planning; });
    }
}
// Keep the existing route and planning workflow; one Calendar entry per module.
registry.category("pb_payhub_lens").add("paycal", { key: "paycal", label: _t("Calendar"), icon: "calendar", Component: PayrollCalendar,
    groups: ["om_hr_payroll.group_hr_payroll_user", "pb_hr_payroll_base.group_payroll_base_officer", ...COMP_GATE],
    probe: { model: "pb.shared.calendar", method: "can_payroll" } }, { sequence: 20, force: true });
registry.category("pb_hub_palette").add("hiring_shared_calendar", { id: "hiring_shared_calendar", label: _t("Calendar"),
    sublabel: _t("Your meetings, interviews and permitted payroll dates"), icon: "calendar",
    requires: "pb_shared_calendar", action: { xmlid: "pb_hiring.action_shared_calendar" }, groups: ["base.group_user"] }, { sequence: 3525 });
