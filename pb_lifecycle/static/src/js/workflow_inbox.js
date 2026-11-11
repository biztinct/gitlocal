/** @odoo-module **/
/**
 * WF2 P4a (D1) — workflow tasks in the one Approvals inbox.
 *
 * ADD-ONLY. The inbox keeps every approval card, filter, tab, sort and count
 * exactly as it was: the tasks arrive in their own key (`tasks`) on the
 * first page of the inbox's own read and are drawn in their own "Tasks"
 * group above the approval cards on "My turn" and "All I can see". A task
 * is not an approval, so its card has no route and no decide buttons.
 * Opening one shows Workflow Studio's own task page (the same renderer,
 * buttons, note box and sent-back card) inside the inbox's slide-over;
 * nothing is drawn twice.
 */
import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { onMounted, onWillUnmount } from "@odoo/owl";
import { PbInbox } from "@pb_approval_config/js/inbox";
import { day } from "@pb_approval_config/js/sentence";

const WORKBENCH = "/pb_lifecycle/static/workflow/index.html";
const CACHE_KEY = "wf2-p4b";
const LEAVE_MS = 320;

patch(PbInbox.prototype, {
    setup() {
        super.setup(...arguments);
        this.taskDay = day;
        Object.assign(this.state, {
            tasks: [], taskCounts: { mine: 0, late: 0 }, taskOpen: null,
            taskLeaving: {}, taskBusy: false,
        });
        // Keep the tasks the inbox's own page read already carries (one
        // read, no second round trip). Approvals are read exactly as before.
        const orm = this.orm;
        const wrapped = Object.create(orm);
        wrapped.call = async (model, method, args, kwargs) => {
            const result = await orm.call(model, method, args, kwargs);
            if (model === "pb.approval.inbox" && method === "get_inbox_page" && result
                    && !((kwargs && kwargs.offset) > 0)) {
                this.state.tasks = result.tasks || [];
            }
            return result;
        };
        this.orm = wrapped;
        this._onTaskMessage = (ev) => {
            const frame = document.querySelector(".pbwfi-frame");
            if (ev.origin !== window.location.origin || !frame || ev.source !== frame.contentWindow) { return; }
            const data = ev.data || {};
            if (data.type === "pb.workflow.task.done") { this.taskDone(data.id); }
        };
        onMounted(() => window.addEventListener("message", this._onTaskMessage));
        onWillUnmount(() => window.removeEventListener("message", this._onTaskMessage));
    },

    async load() {
        await super.load(...arguments);
        const counts = this.state.data && this.state.data.task_counts;
        if (counts) { this.state.taskCounts = counts; }
    },

    /** The group shows on "My turn" and "All I can see" only. */
    get showTasks() {
        return Boolean(this.state.tasks && this.state.tasks.length) && (this.tab === "mine" || this.tab === "all");
    },

    get taskLateCount() { return (this.state.tasks || []).filter((t) => t.late).length; },

    taskUrl(card) {
        const company = (user.context.allowed_company_ids || [])[0] || "";
        const params = new URLSearchParams({ v: CACHE_KEY, embed: "1", company: String(company) });
        if (card.open && card.open.type === "workflow_progress") { params.set("run", String(card.open.id)); }
        else { params.set("task", String(card.id)); }
        return WORKBENCH + "?" + params.toString();
    },

    openTask(card) { this.state.taskOpen = card; },
    onTaskKey(ev, card) {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); this.openTask(card); }
    },
    closeTask() { this.state.taskOpen = null; },

    async takeTask(card) {
        if (this.state.taskBusy) { return; }
        this.state.taskBusy = true;
        try {
            await this.orm.call("pb.workflow.studio", "take", [card.id]);
            this.notif.add(_t("It is yours now. The rest of the team sees that you have it."), { type: "success" });
            await this.refreshTasks();
            const fresh = (this.state.tasks || []).find((t) => t.id === card.id);
            if (this.state.taskOpen && this.state.taskOpen.id === card.id) { this.state.taskOpen = fresh || null; }
        } catch (error) {
            this.notif.add((error.data && error.data.message) || _t("This could not be taken."), { type: "warning" });
            await this.refreshTasks();
            if (this.state.taskOpen && this.state.taskOpen.id === card.id) { this.state.taskOpen = null; }
        } finally {
            this.state.taskBusy = false;
        }
    },

    async releaseTask(card) {
        if (this.state.taskBusy) { return; }
        this.state.taskBusy = true;
        try {
            await this.orm.call("pb.workflow.studio", "release", [card.id]);
            this.notif.add(_t("Put back for the team."), { type: "info" });
            this.state.taskOpen = null;
            await this.refreshTasks();
        } catch (error) {
            this.notif.add((error.data && error.data.message) || _t("This could not be put back."), { type: "warning" });
        } finally {
            this.state.taskBusy = false;
        }
    },

    async taskDone(id) {
        this.state.taskOpen = null;
        this.state.taskLeaving = { ...this.state.taskLeaving, [id]: true };
        this.notif.add(_t("Done. It has moved on to the next step."), { type: "success" });
        await new Promise((resolve) => setTimeout(resolve, LEAVE_MS));
        await this.refreshTasks();
        const leaving = { ...this.state.taskLeaving };
        delete leaving[id];
        this.state.taskLeaving = leaving;
    },

    async refreshTasks() {
        await Promise.all([this.load(), this.kit.refresh()]);
    },

    onEscape(ev) {
        if (ev.key === "Escape" && this.state.taskOpen) { this.state.taskOpen = null; return; }
        return super.onEscape(...arguments);
    },
});
