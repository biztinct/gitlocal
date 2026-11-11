/** @odoo-module **/
/**
 * WF2 P4b — the "where this is" strip on a record's own screen.
 *
 * ADD-ONLY. Drawn above the form sheet (or at the top of a cockpit's own
 * drawer) only when the server says there is something to show: a workflow
 * on the record, or the record sitting in one of the company's own stages.
 * On every other record nothing is drawn — no frame, no reserved space.
 *
 * The data comes from the record hook the form already calls
 * (`record_runs` → `strip`), so a form costs no extra request. A screen
 * that is not a form (the Hiring candidate drawer) renders
 * `WorkflowStripLoader` from the `pb_record_strips` registry, if present,
 * without importing this module.
 *
 * One primary at most: "Do it now" (the viewer's own task, opened in place
 * in the same task page the Approvals inbox shows), else "Move to…" (the
 * company stages the viewer may move it into, through the shipped rules),
 * else a quiet "View workflow".
 */
import { Component, markup, onMounted, onWillUnmount, onWillUpdateProps, useEffect, useState, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";

const WORKBENCH = "/pb_lifecycle/static/workflow/index.html";
export const STRIP_CACHE_KEY = "wf2-p4b";

const svg = (body, size = 14) => markup(
    `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" class="pbwfs-ic" aria-hidden="true">${body}</svg>`);
// Built once: a new markup() on every redraw re-inserts the DOM (flicker).
const ICONS = {
    done: svg('<path d="M20 6 9 17l-5-5"/>', 12),
    here: svg('<circle cx="12" cy="12" r="4" fill="currentColor" stroke="none"/>', 12),
    later: svg('<circle cx="12" cy="12" r="5"/>', 12),
    passed: svg('<path d="M5 12h14"/>', 12),
    stopped: svg('<rect x="6" y="6" width="12" height="12" rx="2"/>', 12),
    flow: svg('<circle cx="6" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><path d="M6 9v3a3 3 0 0 0 3 3h6"/>', 13),
    arrow: svg('<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>'),
    flag: svg('<path d="M4 22V4"/><path d="M4 4h12l-2 4 2 4H4"/>'),
    lock: svg('<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>'),
    chevron: svg('<path d="m6 9 6 6 6-6"/>'),
    mail: svg('<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>'),
    alert: svg('<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/>'),
    check: svg('<path d="M20 6 9 17l-5-5"/>'),
    x: svg('<path d="M18 6 6 18M6 6l12 12"/>', 18),
    task: svg('<path d="M21.8 10A10 10 0 1 1 17 3.34"/><path d="m9 11 3 3L22 4"/>', 18),
};

export class WorkflowStrip extends Component {
    static template = "pb_lifecycle.WorkflowStrip";
    static props = {
        strip: { type: Object },
        onChanged: { type: Function, optional: true },
        onView: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.actionService = useService("action");
        this.icons = ICONS;
        this.state = useState({ strip: this.props.strip, index: 0, menu: false, busy: false, task: null, note: null });
        onWillUpdateProps((next) => {
            if (next.strip !== this.props.strip) {
                this.state.strip = next.strip;
                this.state.note = null;
                if (this.state.index >= ((next.strip && next.strip.workflows) || []).length) { this.state.index = 0; }
            }
        });
        this._onMessage = (ev) => {
            const frame = document.querySelector(".pbwfs-frame");
            if (ev.origin !== window.location.origin || !frame || ev.source !== frame.contentWindow) { return; }
            if ((ev.data || {}).type === "pb.workflow.task.done") { this.taskDone(); }
        };
        this._onKey = (ev) => {
            if (ev.key !== "Escape") { return; }
            if (this.state.task) { this.state.task = null; ev.stopPropagation(); }
            else if (this.state.menu) { this.state.menu = false; }
        };
        this._onDoc = (ev) => {
            if (this.state.menu && !(ev.target.closest && ev.target.closest(".pbwfs-movebox"))) { this.state.menu = false; }
        };
        onMounted(() => {
            window.addEventListener("message", this._onMessage);
            document.addEventListener("keydown", this._onKey, true);
            document.addEventListener("click", this._onDoc, true);
        });
        onWillUnmount(() => {
            window.removeEventListener("message", this._onMessage);
            document.removeEventListener("keydown", this._onKey, true);
            document.removeEventListener("click", this._onDoc, true);
        });
    }

    get s() { return this.state.strip || {}; }
    get workflows() { return this.s.workflows || []; }
    get lead() { return this.workflows[this.state.index] || null; }
    get primary() { return this.lead ? this.lead.action : this.s.action || ""; }
    get sentence() { return this.lead ? this.lead.sentence : this.s.sentence || ""; }
    get tone() { return this.lead ? this.lead.tone : "wait"; }
    get moves() { return this.s.moves || []; }
    get compactLabel() {
        const c = this.s.compact || {};
        return c.index ? _t("Stage %(n)s of %(total)s", { n: c.index, total: c.total }) : "";
    }
    get stopAt() { return (this.s.exits || []).find((e) => e.here) || null; }

    nextWorkflow() {
        this.state.index = (this.state.index + 1) % Math.max(1, this.workflows.length);
        this.state.menu = false;
        this.state.note = null;
    }

    taskUrl() {
        const company = (user.context.allowed_company_ids || [])[0] || "";
        const params = new URLSearchParams({ v: STRIP_CACHE_KEY, embed: "1", company: String(company),
                                             task: String(this.state.task.task_id) });
        return WORKBENCH + "?" + params.toString();
    }

    openTask() { if (this.lead && this.lead.task_id) { this.state.task = this.lead; } }
    closeTask() { this.state.task = null; }

    async taskDone() {
        this.state.task = null;
        this.notif.add(_t("Done. It has moved on to the next step."), { type: "success" });
        await this.refresh();
    }

    async refresh() {
        try {
            const result = await this.orm.call("pb.workflow.studio", "record_strip", [this.s.model, this.s.record_id]);
            this.apply(result.strip || null);
        } catch {
            // The strip keeps what it showed; the record screen is untouched.
        }
    }

    apply(strip) {
        if (strip) { this.state.strip = strip; }
        if (this.props.onChanged) { this.props.onChanged(strip); }
    }

    toggleMenu() { this.state.menu = !this.state.menu; this.state.note = null; }

    async move(m) {
        if (!m.allowed) { this.state.note = { bad: true, text: m.reason }; return; }
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            const result = await this.orm.call("pb.workflow.studio", "strip_move", [this.s.model, this.s.record_id, m.stage_id]);
            this.state.menu = false;
            this.apply(result.strip || null);
            this.state.note = { bad: false, text: _t("Moved to %s.", m.name) };
        } catch (error) {
            // A refusal of the shipped rules is shown in place, in its own words.
            this.state.note = { bad: true, text: (error.data && error.data.message) || _t("This could not be moved.") };
        } finally {
            this.state.busy = false;
        }
    }

    async resend() {
        if (!this.lead || !this.lead.resend_id || this.state.busy) { return; }
        this.state.busy = true;
        try {
            const result = await this.orm.call("pb.workflow.studio", "resend_link", [this.lead.resend_id]);
            this.notif.add(_t("A new link was sent to %s. The old one no longer works.", result.sent_to), { type: "success" });
        } catch (error) {
            this.notif.add((error.data && error.data.message) || _t("The link could not be sent."), { type: "warning" });
        } finally {
            this.state.busy = false;
        }
    }

    view() {
        if (this.props.onView) { return this.props.onView(); }
        return this.actionService.doAction({
            type: "ir.actions.client", tag: "pb_workflow_studio", name: _t("Workflow progress"),
            context: { pb_workflow_record_model: this.s.model, pb_workflow_record_id: this.s.record_id },
        });
    }
}

/** For screens that are not a form: loads its own strip, draws nothing
 *  until (and unless) there is something to show. */
export class WorkflowStripLoader extends Component {
    static template = xml`<WorkflowStrip t-if="state.strip" strip="state.strip" onChanged.bind="onChanged"/>`;
    static components = { WorkflowStrip };
    static props = { model: { type: String }, resId: { type: Number }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ strip: null });
        useEffect(() => {
            let live = true;
            this.state.strip = null;
            loadWorkflowStrip(this.orm, this.props.model, this.props.resId).then((strip) => {
                if (live) { this.state.strip = strip; }
            });
            return () => { live = false; };
        }, () => [this.props.model, this.props.resId]);
    }

    onChanged(strip) { this.state.strip = strip; }
}

export async function loadWorkflowStrip(orm, model, resId) {
    if (!model || !resId) { return null; }
    try {
        return (await orm.call("pb.workflow.studio", "record_strip", [model, resId])).strip || null;
    } catch {
        return null;
    }
}

registry.category("pb_record_strips").add("workflow", WorkflowStripLoader);
