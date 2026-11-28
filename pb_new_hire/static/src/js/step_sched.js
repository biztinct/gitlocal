/** @odoo-module **/
/**
 * Step 4 — Schedule and time off (NEWHIRE P2). Everything here comes from the
 * team, so HR can leave the step alone: the working week (the team's own one
 * suggested, its first week drawn as a seven-day strip that re-draws when the
 * week changes), the late and overtime rule (only where the feature exists),
 * the clock (a plain clock-number box, checked live — there is no "next free
 * number" in the product), the leave this country earns and the company's
 * holiday list. Nothing here blocks sending.
 */
import { Component, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { icon, fmtDay, siteNameOf } from "./studio_util";

export class StepSched extends Component {
    static template = "pb_new_hire.StepSched";
    static props = { api: Object };

    setup() {
        this.icon = icon;
        this.nh = useState(this.props.api.nh);
    }

    get api() { return this.props.api; }
    get d() { return this.nh.draft; }
    get s() { return this.nh.sched; }
    get first() { return this.api.first; }
    err(field) { return this.nh.fieldErr[field] || ""; }
    isAuto(field) { return Boolean(this.nh.auto[field]); }

    get heading() { return _t("When does %s work?", this.first); }
    get teamChip() {
        return this.api.teamName ? _t("Defaults from %s", this.api.teamName) : _t("Defaults from the team");
    }

    // ------------------------------------------------------------ the week
    get weeks() { return (this.s && this.s.weeks) || []; }
    get week() { return this.weeks.find((w) => w.id === this.d.week_id) || null; }
    get teamWeek() { return this.weeks.find((w) => w.team_default) || null; }
    weekLabel(w) { return _t("%(name)s, %(when)s", { name: w.name, when: w.when }); }
    onWeek(ev) {
        const id = Number(ev.target.value) || false;
        this.api.set("week_id", id);
    }
    get usualHours() { return _t("The company's usual working hours"); }
    get strip() {
        const w = this.week;
        if (!w) {
            return [];
        }
        return w.days.map((day, i) => ({ key: `${w.id}-${i}`, ...day }));
    }
    get stripKey() { return String(this.d.week_id || "none"); }
    get hoursLine() {
        const w = this.week;
        if (!w) {
            return "";
        }
        const h = Number(w.hours_per_week) || 0;
        return h ? _t("%s hours in the first week", String(Math.round(h * 10) / 10)) : "";
    }
    openSetup() { this.api.openWorkforceSetup(); }

    // ------------------------------------------------------------ late rule
    setGroup(group) { this.api.set("late_group", group); }

    // ------------------------------------------------------------ clock
    get siteName() { return siteNameOf(this.nh) || _t("the site"); }
    get clockTitle() { return _t("Clocks in at %s", this.siteName); }
    get clockSub() {
        return this.d.clock_on
            ? _t("Type the number %s has on the attendance machine. Leave it empty to add it later.", this.first)
            : _t("Hours come from the working week, with no clocking.");
    }
    toggleClock() { this.api.set("clock_on", !this.d.clock_on); }
    onClock(ev) { this.api.set("clock_code", ev.target.value); }
    get clockCheck() { return this.nh.clockCheck; }
    get clockBad() { return Boolean(this.clockCheck && this.clockCheck.ok === false); }
    get clockOk() { return Boolean(this.clockCheck && this.clockCheck.ok && this.clockCheck.message); }

    // ------------------------------------------------------------ leave and holidays
    get leave() { return (this.s && this.s.leave) || []; }
    leaveTitle(row) {
        return _t("%(name)s: %(n)s days a year", { name: row.name, n: String(row.days_per_year).replace(/\.0+$/, "") });
    }
    leaveSub(row) { return [row.how, row.wait].filter(Boolean).join(" · "); }
    get holidays() { return (this.s && this.s.holidays) || { count: 0, next: false }; }
    get holidayTitle() {
        const n = this.holidays.count;
        return n
            ? _t("Your company's holiday list applies: %s days off in the next 12 months.", n)
            : _t("No public holidays are loaded for your company yet.");
    }
    get holidaySub() {
        const next = this.holidays.next;
        return next ? _t("Next: %(name)s, %(day)s", { name: next.name, day: fmtDay(next.date) }) : "";
    }
}
