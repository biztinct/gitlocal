/** @odoo-module **/
import { Component, useState, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useRecordObserver } from "@web/model/relational_model/utils";

// Presentation only. Keep the installed chart endpoint's company context,
// access checks and reporting relationships; never write an employee here.
export class PremiumOrgChart extends Component {
    static template = "pb_form_studio_people.PremiumOrgChart";
    static props = { ...standardFieldProps };
    setup() {
        this.state = useState({ loading: true, error: false, managers: [], children: [], self: null, more: false });
        this.requestGeneration = 0;
        this.lastRecord = null;
        this.maxLevel = null;
        useRecordObserver((record) => {
            const key = `${record.resId || 0}:${record.data.parent_id?.id || 0}`;
            if (key !== this.lastRecord) {
                this.lastRecord = key;
                this.maxLevel = null;
                return this.load();
            }
        });
        onWillUnmount(() => { this.requestGeneration++; });
    }
    async load() {
        const generation = ++this.requestGeneration;
        this.state.loading = true;
        this.state.error = false;
        try {
            const record = this.props.record;
            const data = record.resId ? await rpc("/hr/get_org_chart", {
                employee_id: record.resId,
                new_parent_id: record.data.parent_id?.id || false,
                context: { ...user.context, max_level: this.maxLevel },
            }) : {};
            if (generation !== this.requestGeneration) { return; }
            Object.assign(this.state, { managers: data.managers || [], children: data.children || [],
                self: data.self || null, more: Boolean(data.managers_more && this.maxLevel === null) });
        } catch {
            if (generation === this.requestGeneration) { this.state.error = true; }
        } finally {
            if (generation === this.requestGeneration) { this.state.loading = false; }
        }
    }
    showManagers() { this.maxLevel = 100; return this.load(); }
    openEmployee(id) { return this.env.pbEmployeeWorkspace?.openRelatedEmployee(id); }
    initials(name) {
        const words = (name || "").trim().split(/\s+/).filter(Boolean);
        return ((words[0]?.[0] || "?") + (words.length > 1 ? words.at(-1)[0] : "")).toUpperCase();
    }
    reportsLabel(employee) {
        const count = employee.indirect_sub_count || 0;
        return count === 1 ? _t("1 report") : _t("%s reports", count);
    }
}
registry.category("fields").add("pb_premium_org_chart", { component: PremiumOrgChart });
