/** @odoo-module **/
/**
 * ApprovalStepper — a read-only field widget that renders a vertical approval
 * stepper (avatars, timestamps, pending pulse, refusal banner) from a JSON
 * field produced by biz.approval.chain.mixin._approval_widget_payload().
 *
 * Zero product dependency: it themes itself through --bac-* CSS custom
 * properties (defaults in approval_stepper.scss); a consuming app overrides
 * those on any ancestor to tint it.
 *
 * Field value shape (JSON):
 *   { steps:[{state,label,group_label?}], current, dead_states:[...],
 *     trail:[{from_state,to_state,user,avatar,stamp,note}] }
 */
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class ApprovalStepper extends Component {
    static template = "biz_approval_chain.ApprovalStepper";
    static props = { ...standardFieldProps };

    get data() {
        try {
            return JSON.parse(this.props.record.data[this.props.name] || "{}");
        } catch {
            return {};
        }
    }

    get isRefused() {
        const d = this.data;
        return (d.dead_states || []).includes(d.current);
    }

    get refusal() {
        // the terminal transition into the current dead state, for the banner
        if (!this.isRefused) {
            return null;
        }
        const trail = this.data.trail || [];
        for (let i = trail.length - 1; i >= 0; i--) {
            if (trail[i].to_state === this.data.current) {
                return trail[i];
            }
        }
        return { to_state: this.data.current };
    }

    get steps() {
        const d = this.data;
        const steps = d.steps || [];
        const trail = d.trail || [];
        const byTo = {};
        for (const t of trail) {
            byTo[t.to_state] = t; // last transition into a state wins (latest actor)
        }
        const curIdx = steps.findIndex((s) => s.state === d.current);
        const refused = this.isRefused;
        return steps.map((s, i) => {
            const actor = byTo[s.state] || null;
            let status;
            if (refused) {
                status = actor ? "done" : "pending";
            } else if (i < curIdx) {
                status = "done";
            } else if (i === curIdx) {
                status = "current";
            } else {
                status = "pending";
            }
            return { ...s, status, actor };
        });
    }

    get refusalTitle() {
        // translatable — the template can't wrap a literal ternary in _t
        const r = this.refusal;
        return r && r.to_state === "cancelled" ? _t("Cancelled") : _t("Refused");
    }

    fmtStamp(s) {
        if (!s) {
            return "";
        }
        // server datetime "YYYY-MM-DD HH:MM:SS" → a compact local-ish label
        const [d, t] = String(s).split(" ");
        return t ? `${d} ${t.slice(0, 5)}` : d;
    }
}

export const approvalStepper = {
    component: ApprovalStepper,
    supportedTypes: ["char", "text"],
};

registry.category("fields").add("biz_approval_stepper", approvalStepper);
