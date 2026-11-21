/** @odoo-module **/
/**
 * WF2 P5c — "Repeat for each…" in the one Approvals inbox.
 *
 * ADD-ONLY, on top of the P4a Tasks group (`workflow_inbox.js`): a task from
 * one line of a repeat shows its line ("receipt 2 of 5"); a person's line
 * tasks of one repeat sit under one heading with "Do all in turn", which
 * opens the first and, each time one is done, the next — until none is left.
 * Beyond five such tasks the server sends them as one card ("Check receipt ·
 * 12 to do") that is worked through the same way. Nothing else changes.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PbInbox } from "@pb_approval_config/js/inbox";

patch(PbInbox.prototype, {
    setup() {
        super.setup(...arguments);
        Object.assign(this.state, { taskTurn: null });
    },

    /** Every task, a grouped card counting for each task it holds. */
    get taskCountAll() {
        return (this.state.tasks || []).reduce((n, t) => n + (t.kind === "task_group" ? t.group_count : 1), 0);
    },

    /** The heading above a group: shown once, on its first card. */
    taskGroupHead(tk) {
        const g = tk.group;
        return Boolean(g && tk.kind !== "task_group" && g.size > 1 && g.ids && g.ids[0] === tk.id);
    },

    taskTurnLeft() {
        const turn = this.state.taskTurn;
        if (!turn) { return 0; }
        return (this.state.tasks || []).filter((t) => t.group && t.group.key === turn.key)
            .reduce((n, t) => n + (t.kind === "task_group" ? t.group_count : 1), 0);
    },

    startTurn(tk) {
        this.state.taskTurn = { key: tk.group.key, title: tk.group.title };
        this.openTask(tk);
    },

    openTask(card) {
        if (this.state.taskTurn && (!card.group || card.group.key !== this.state.taskTurn.key)) {
            this.state.taskTurn = null;
        }
        return super.openTask(...arguments);
    },

    closeTask() {
        this.state.taskTurn = null;
        return super.closeTask(...arguments);
    },

    async taskDone(id) {
        const turn = this.state.taskTurn;
        await super.taskDone(...arguments);
        if (!turn) { return; }
        const next = (this.state.tasks || []).find((t) => t.group && t.group.key === turn.key && t.id !== id);
        if (next) {
            this.state.taskTurn = turn;
            this.openTask(next);
        } else {
            this.state.taskTurn = null;
            this.notif.add(_t("All done for “%s”.", turn.title), { type: "success" });
        }
    },
});
