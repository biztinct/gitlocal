/** @odoo-module **/
import { Breadcrumbs } from "@web/search/breadcrumbs/breadcrumbs";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { openHub } from "@pb_hub/js/hub_nav";

/** Canonical ownership is independent of the sequence of screens visited. */
export function modelLocation(model) {
    const payroll = { label: _t("Payroll"), tag: "pb_pay_hub", xmlid: "pb_payhub.action_pb_pay_hub" };
    const people = { label: _t("People"), tag: "pb_people_hub", xmlid: "pb_people_hub.action_pb_people_hub" };
    const workforce = { label: _t("Workforce"), tag: "pb_workforce", xmlid: "pb_mission.action_pb_workforce", lensKey: "pb_shell_lens" };
    const routes = {
        "hr.payslip": { ...payroll, lens: "payslips", parent: _t("Payslips") },
        "hr.payslip.run": { ...payroll, lens: "runs", parent: _t("Pay runs") },
        "hr.employee": { ...people, lens: "employees", parent: _t("Employees") },
        "hr.employee.public": { ...people, lens: "employees", parent: _t("Employees") },
        "hr.contract": { ...people, collectionXmlid: "pb_people_hub.action_pb_people_contracts", parent: _t("Contracts") },
        "hr.leave": { ...workforce, lens: "timeoff", parent: _t("Time off") },
        "hr.attendance": { ...workforce, lens: "time", parent: _t("Time") },
    };
    return routes[model] || null;
}

export function hubLocationTitle(key, lens) {
    const names = {
        "pay:runs": _t("Pay runs"), "pay:run": _t("Run payroll"),
        "home:approvals": _t("Approval inbox"),
    };
    return names[`${key}:${lens?.key}`] || lens?.title || lens?.label || "";
}

// Replacing this component retains Odoo's controller callbacks, dirty-form
// guards, pager and status/action slots. We never call browser.history.back().
export class PayobookBreadcrumbs extends Breadcrumbs {
    static template = "pb_hub.ContextNavigation";
    setup() { this.action = useService("action"); }
    ic(name, size = 14) { return ic(name, size); }
    get current() { return this.props.breadcrumbs.filter(Boolean).at(-1) || {}; }
    get previous() { return this.props.breadcrumbs.filter(Boolean).at(-2) || null; }
    get location() {
        const model = this.env.model?.root?.resModel || this.env.searchModel?.resModel;
        const route = modelLocation(model);
        return route && registry.category("actions").contains(route.tag) ? route : null;
    }
    get runParent() {
        if (this.env.model?.root?.resModel !== "hr.payslip") { return null; }
        const run = this.env.model.root.data.payslip_run_id;
        if (!run) { return null; }
        const id = Array.isArray(run) ? run[0] : run.id;
        const name = Array.isArray(run) ? run[1] : run.display_name;
        return Number.isInteger(id) && id > 0 ? { id, name: name || _t("Pay run") } : null;
    }
    get returnLabel() {
        if (this.previous) { return _t("Back to %s", this.previous.name || _t("previous page")); }
        if (this.current.isFormView && this.runParent) { return _t("Pay run overview"); }
        if (this.current.isFormView && this.location) { return _t("View %s", this.location.parent); }
        return "";
    }
    get parents() {
        if (!this.location) { return []; }
        const route = this.location;
        const parents = [{ key: "area", name: route.label, run: () => this.openLocation(false) }];
        // A destination occurs once: in the named return or in the location.
        if (this.previous && this.previous.name !== route.parent && this.previous.name !== route.label) {
            parents.push({ key: "collection", name: route.parent, run: () => this.openLocation(true) });
        }
        if (this.runParent && this.previous && this.previous.name !== this.runParent.name) {
            parents.push({ key: "run", name: this.runParent.name, run: () => this.openRun() });
        }
        return parents.filter(p => p.name !== this.previous?.name && p.name !== this.current.name);
    }
    openLocation(collection) {
        const route = this.location;
        if (!route) { return; }
        return openHub(this.action, { xmlid: collection && route.collectionXmlid ? route.collectionXmlid : route.xmlid, lens: collection ? route.lens : undefined, lensKey: route.lensKey });
    }
    openRun() {
        return this.action.doAction({ type: "ir.actions.act_window", name: this.runParent.name,
            res_model: "hr.payslip.run", res_id: this.runParent.id,
            views: [[false, "form"]], target: "current" });
    }
    goBack() {
        if (this.previous) { return this.previous.onSelected(); }
        if (this.runParent) { return this.openRun(); }
        return this.openLocation(true);
    }
}
patch(ControlPanel, { components: { ...ControlPanel.components, Breadcrumbs: PayobookBreadcrumbs } });
