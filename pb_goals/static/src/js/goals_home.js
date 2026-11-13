/** @odoo-module **/
/**
 * `pb_goals_home` — "Goals waiting on you", on the Home screen.
 *
 * EVERY ROW IS A DOOR. Somebody opening Home should be able to clear their
 * goals obligations without knowing this module exists: a sign-off opens the
 * one approvals screen, a conversation opens the check-in, a review opens the
 * review, and their own sheet opens their own page.
 *
 * THE COUNT AND THE LIST ARE THE SAME NUMBER, computed once on the server. A
 * chip that counts one thing over a list that shows another is two bugs (R80),
 * and this card has four sections that could each drift on their own.
 *
 * THE SIGN-OFFS COME FROM THE ONE INBOX and never from a search for records
 * with a status on them — `pb.approval.inbox` already knows what "my turn"
 * means on this database, quietly including anybody covering for somebody
 * else. That is the server's problem; this file only draws what comes back.
 *
 * A DEAD END IS THE ONE THING THIS CARD MUST NOT BE. With nothing waiting it
 * still says so in a sentence and still offers the two doors somebody might
 * have come for, rather than disappearing.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

export class PbGoalsHome extends Component {
    static template = "pb_goals.PbGoalsHome";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");

        this.state = useState({
            loaded: false,
            busy: false,
            count: 0,
            more: 0,
            rows: [],
            sections: [],
            headline: "",
        });

        onWillStart(async () => {
            await this.load();
        });
    }

    ic(name, size = 16) { return ic(name, size); }

    async load() {
        this.state.busy = true;
        try {
            const d = await this.orm.call("pb.goals.home", "get_home", []);
            Object.assign(this.state, {
                loaded: true,
                count: d.count || 0,
                more: d.more || 0,
                rows: d.rows || [],
                sections: (d.sections || []).filter((s) => s.count > 0),
                headline: d.headline || "",
            });
        } catch (e) {
            this.state.loaded = true;
            this.state.headline = _t(
                "Your goals could not be read just now.");
            console.warn("pb_goals: the Home card could not be read", e);
        } finally {
            this.state.busy = false;
        }
    }

    async openRow(row) {
        try {
            const action = await this.orm.call(
                "pb.goals.home", "open_row", [row.kind, row.id]);
            await this.action.doAction(action);
        } catch (e) {
            this.notif.add(
                _t("That could not be opened. Try the Goals board."),
                { type: "warning" });
            console.warn("pb_goals: a Home row could not be opened", e);
        }
    }

    async openBoard() {
        await this.action.doAction({
            type: "ir.actions.client",
            tag: "pb_goals_board",
            name: _t("Goals"),
        });
    }
}

registry.category("actions").add("pb_goals_home", PbGoalsHome);
