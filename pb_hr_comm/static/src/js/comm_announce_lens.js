/** @odoo-module **/
/**
 * Home › ANNOUNCE (NAV P2, 2026-10-21) — two tabs in one lens.
 *
 *   Coming up   what goes out in the next seven days, and the week's
 *               birthdays and anniversaries (PbHrCommHome, unchanged)
 *   Calendar    the announcements calendar (PbHrCommCalendar, unchanged) —
 *               it used to be People › Announce; the revised menu keeps
 *               everything about announcements on Home
 *
 * The Calendar tab is the HR team's planning screen and keeps its gate
 * (COMM_GATE): somebody without it sees Coming up only, with no tab strip.
 * The standalone calendar action stays for every old link.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { setPlaceSub } from "@pb_hub/js/hub_place";
import { PbHrCommCalendar } from "@pb_hr_comm/js/comm_calendar";
import { PbHrCommHome } from "@pb_hr_comm/js/comm_home";

/** Same list as comm_palette.js COMM_GATE (the calendar's own gate). */
const CALENDAR_GATE = [
    "pb_hr_comm.group_comm_user",
    "pb_hr_comm.group_comm_manager",
    "pb_hr_comm.group_comm_admin",
];

export class PbHrCommAnnounceLens extends Component {
    static template = "pb_hr_comm.PbHrCommAnnounceLens";
    static components = { PbHrCommHome, PbHrCommCalendar };
    static props = ["*"];

    setup() {
        this.state = useState({ tab: "coming", canPlan: false });
        // Stable props per tab (W21): built once.
        this.homeProps = { embedded: true, onOpenCalendar: () => this.setTab("calendar") };
        this.calendarProps = { embedded: true };
        onWillStart(async () => {
            const flags = await Promise.all(CALENDAR_GATE.map(async (g) => {
                try { return await user.hasGroup(g); } catch { return true; }
            }));
            this.state.canPlan = flags.some(Boolean);
        });
    }

    ic(n, s = 14) { return ic(n, s); }

    get tabs() {
        return [
            { key: "coming", label: _t("Coming up"), icon: "megaphone" },
            { key: "calendar", label: _t("Calendar"), icon: "calendar" },
        ];
    }

    /** A CLICK handler. */
    setTab(key) {
        if (key === "calendar" && !this.state.canPlan) { return; }
        this.state.tab = key;
        setPlaceSub("pb_home_hub", "coming_up", key === "calendar" ? "calendar" : "");
    }
}
