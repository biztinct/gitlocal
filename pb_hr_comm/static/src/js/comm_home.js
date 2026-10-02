/** @odoo-module **/
/**
 * `pb_hr_comm_home` — "Coming up", on the Home screen.
 *
 * TWO THINGS BELONG HERE AND THEY ARE NOT THE SAME THING: what the company is
 * about to tell everybody in the next seven days, and the colleagues with a
 * birthday or a work anniversary in those same seven days. The first is what
 * somebody needs to know before they send their own email; the second is the
 * one thing on the whole screen that is about a person rather than a process.
 *
 * EVERY ROW IS A DOOR. Somebody opening Home should be able to see what is
 * coming without knowing this module exists — an announcement opens itself,
 * and a celebration opens the wall where a colleague can be thanked.
 *
 * A DEAD END IS THE ONE THING THIS CARD MUST NOT BE. With nothing coming up
 * it still says so in a sentence and still shows the week's celebrations,
 * rather than disappearing off a screen somebody has learnt to look at.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

export class PbHrCommHome extends Component {
    static template = "pb_hr_comm.PbHrCommHome";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");

        this.state = useState({
            loaded: false,
            busy: false,
            count: 0,
            mine: 0,
            more: 0,
            rows: [],
            celebrations: [],
            celebrationMore: 0,
            headline: "",
            mayPlan: false,
        });

        onWillStart(async () => {
            await this.load();
        });
    }

    ic(name, size = 16) { return ic(name, size); }

    async load() {
        this.state.busy = true;
        try {
            const d = await this.orm.call("pb.hr.comm.home", "get_home", []);
            Object.assign(this.state, {
                loaded: true,
                count: d.count || 0,
                mine: d.mine || 0,
                more: d.more || 0,
                rows: d.rows || [],
                celebrations: d.celebrations || [],
                celebrationMore: d.celebration_more || 0,
                headline: d.headline || "",
                mayPlan: !!d.may_plan,
            });
        } catch (e) {
            this.state.loaded = true;
            this.state.headline = _t(
                "What is coming up could not be read just now.");
            console.warn("pb_hr_comm: the Home card could not be read", e);
        } finally {
            this.state.busy = false;
        }
    }

    async openRow(row) {
        try {
            const action = await this.orm.call(
                "pb.hr.comm.home", "open_row", [row.kind, row.id]);
            if (action) { await this.action.doAction(action); }
        } catch (e) {
            this.notif.add(
                _t("That could not be opened. Try the announcements calendar."),
                { type: "warning" });
            console.warn("pb_hr_comm: a Home row could not be opened", e);
        }
    }

    async openCalendar() {
        await this.action.doAction({
            type: "ir.actions.client",
            tag: "pb_hr_comm_calendar",
            name: _t("Announcements"),
        });
    }
}

registry.category("actions").add("pb_hr_comm_home", PbHrCommHome);
