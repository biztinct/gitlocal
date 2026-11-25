/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubShell } from "@pb_hub/js/hub_shell";
import { resolveLensAccess } from "@pb_hub/js/hub_gates";
import { featureGate } from "@pb_hub/js/hub_features";
import { openHub } from "@pb_hub/js/hub_nav";
import { allCategories } from "./settings_hub";

// Keys refer to the effective registry after optional modules have registered
// their overrides. A slash selects just one card within a shared category.
const catalogue = {
    home: ["announcements"],
    calendar: ["calendars"],
    pay: ["bank_layouts", "statutory"],
    people: ["documents"],
    hiring: ["hiring"],
    workforce: ["workforce_workspace", "leave_kinds", "attendance_connectors", "attendance_calculation"],
    expenses: [], insights: [],
    compliance: ["statutory"],
    talent: ["reviews", "voice/voice_library"],
    learning: ["learning"],
};
const workspaceSections = {
    calendar: [[_t("My account"), ["connections"]], [_t("Company connections"), ["*"]]],
    hiring: [[_t("Assessment and offers"), ["hiring_criteria", "hiring_bgv_lines", "hiring_doc_lines"]],
        [_t("Recruitment"), ["*"]]],
    people: [[_t("Jobs and pay"), ["pb_org_structure.action_pb_org_jobs", "pb_pay_scales.action_pb_pay_scales", "pb_pay.action_pb_pay_band"]],
        [_t("Employee lifecycle"), ["*"]]],
    workforce: [[_t("Guided setup"), ["setup"]], [_t("Leave and devices"), ["leave_kinds", "attendance_connectors"]]],
    expenses: [[_t("Travel policy"), ["pb_business_trip.action_pb_trip_policy", "pb_business_trip.action_pb_trip_expense_category"]],
        [_t("Claim rules"), ["*"]]],
    pay: [[_t("Payment and statutory rules"), ["*"]]],
    insights: [[_t("Reporting"), ["*"]]],
    compliance: [[_t("Safeguards"), ["pb_young_worker.action_pb_young_worker_rule"]], [_t("Statutory rules"), ["*"]]],
    talent: [[_t("Employee voice"), ["voice_library"]], [_t("Performance"), ["*"]]],
    learning: [[_t("Course administration"), ["country_packs", "day_one"]], [_t("Communications"), ["*"]]],
};
const system = "base.group_system";
const payManager = "pb_pay.group_pay_manager";
const expenseManagers = ["hr_expense.group_hr_expense_manager", "pb_hr_payroll_base.group_payroll_base_manager", "om_hr_payroll.group_hr_payroll_manager"];
function actionCard(xmlid, label, sub, icon, groups) {
    return { id: xmlid, xmlid, label, sub, icon, groups: [...groups, system] };
}
const shortcuts = {
    people: [
        actionCard("pb_org_structure.action_pb_org_jobs", _t("Job structure"), _t("Maintain jobs and levels."), "briefcase", ["hr.group_hr_user", "pb_hiring.group_hiring_manager"]),
        actionCard("pb_pay_scales.action_pb_pay_scales", _t("Pay scales"), _t("Configure scales and grades."), "layers", [payManager]),
        actionCard("pb_pay.action_pb_pay_band", _t("Pay bands"), _t("Maintain salary ranges by job level."), "banknote", [payManager]),
        actionCard("pb_lifecycle.action_journey_template", _t("Journey checklists"), _t("Configure joiner, mover and leaver checklists."), "list", ["pb_lifecycle.group_lifecycle_admin"]),
    ],
    expenses: [
        actionCard("pb_business_trip.action_pb_trip_policy", _t("Per-diem policies"), _t("Set daily travel allowances and payment channels."), "globe", ["hr.group_hr_manager"]),
        actionCard("pb_business_trip.action_pb_trip_expense_category", _t("Trip expense categories"), _t("Maintain categories for trip costs."), "list", ["hr.group_hr_manager"]),
        actionCard("pb_expense_allowance.action_pb_expense_allowance", _t("Yearly claim limits"), _t("Set annual expense allowances."), "sliders", expenseManagers),
        actionCard("pb_expense_payroll.action_pb_expense_pay_setup", _t("How claims are paid"), _t("Choose how approved claims are reimbursed."), "banknote", expenseManagers),
    ],
    talent: [
        actionCard("pb_goals.action_pb_goal_cycle", _t("Goal years"), _t("Configure goal cycles."), "calendar", ["pb_goals.group_goals_manager", "pb_goals.group_goals_admin"]),
        actionCard("pb_goals.action_pb_goal_template", _t("Goal templates"), _t("Set starting goals for new goal sheets."), "target", ["pb_goals.group_goals_manager", "pb_goals.group_goals_admin"]),
    ],
    compliance: [
        actionCard("pb_young_worker.action_pb_young_worker_rule", _t("Young worker rules"), _t("Maintain rules for young workers."), "shield", ["om_hr_payroll.group_hr_payroll_manager"]),
    ],
};

export async function workspaceCards(env, orm, key, lenses = []) {
    try {
        return await resolveWorkspaceCards(env, orm, key, lenses);
    } catch (error) {
        console.warn("Could not resolve workspace settings", key, error);
        return [];
    }
}

async function resolveWorkspaceCards(env, orm, key, lenses) {
    const categories = allCategories().flatMap(cat => {
        const cards = cat.cards.filter(card => catalogue[key].some(ref =>
            ref === cat.key || ref === cat.key + "/" + card.id));
        return cards.length ? [{...cat, cards}] : [];
    });
    const extra = shortcuts[key] || [];
    const xmlids = [...categories.flatMap(c => c.cards), ...extra].map(c => c.xmlid).filter(Boolean);
    const lensKey = {calendar: "connections", insights: "report_builder"}[key];
    const lens = lenses.find(l => l.key === lensKey);
    const [gates, present, allowed] = await Promise.all([
        orm.call("pb.settings", "resolve_gates", [categories.map(c => ({
            key: c.key, groups: c.groups, feature: c.feature,
            cards: c.cards.map(({id, tag, xmlid, feature}) => ({id, tag, xmlid, feature})),
        }))]),
        orm.call("pb.settings", "resolve_actions", [xmlids]),
        resolveLensAccess([...extra.map(c => ({...c, key: c.id})), ...(lens ? [lens] : [])], orm),
    ]);
    const actions = registry.category("actions");
    const cards = categories.flatMap(cat => gates.categories[cat.key] ? cat.cards.filter(c =>
        gates.cards[cat.key + ":" + c.id] && (c.tag ? actions.contains(c.tag) : present[c.xmlid])
    ).map(c => ({...c, section: cat.label, feature: c.feature || cat.feature})) : []);
    for (const card of extra) if (present[card.xmlid] && allowed[card.id]) cards.push(card);
    if (lens && allowed[lens.key]) cards.unshift({
        id: lens.key, lens: lens.key, icon: lens.icon, feature: lens.feature,
        label: key === "calendar" ? _t("Personal connections") : _t("Report definitions"),
        sub: key === "calendar" ? _t("Connect your own calendar.") : _t("Build and save reusable reports."),
    });
    return cards.filter(c => !featureGate(env, c.feature || "").locked && featureGate(env, c.feature || "").shown);
}

export class WorkspaceSettings extends Component {
    static template = "pb_settings.WorkspaceSettings";
    static props = ["*"];
    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.state = useState({ search: "", cards: this.props.cards || [] });
        if (!this.props.cards) onWillStart(async () => {
            this.state.cards = await workspaceCards(this.env, this.orm, this.props.workspace);
        });
    }
    ic(name) { return ic(name, 18); }
    get visibleCards() {
        const term = this.state.search.trim().toLocaleLowerCase();
        return this.state.cards.filter(c => (c.label + " " + c.sub).toLocaleLowerCase().includes(term));
    }
    get sections() {
        const groups = new Map();
        for (const card of this.visibleCards) {
            const grouping = workspaceSections[this.props.workspace] || [];
            const section = grouping.find(([, ids]) => ids.includes(card.id) || ids.includes("*"));
            const name = String(section?.[0] || card.section || _t("Configuration"));
            if (!groups.has(name)) groups.set(name, []);
            groups.get(name).push(card);
        }
        return [...groups].map(([name, cards]) => ({name, cards}));
    }
    open(card) {
        if (card.lens) return this.props.select(card.lens);
        if (card.id === "attendance_connectors" && registry.category("actions").contains("pb_workforce_setup_studio")) {
            return openHub(this.action, {xmlid: "pb_workforce_setup.action_setup_studio", context: {pb_wfs_step: "clocks"}, back: this.props.back});
        }
        return openHub(this.action, {xmlid: card.xmlid, tag: card.tag, context: card.context, back: this.props.back, clearBreadcrumbs: false});
    }
}

patch(HubShell.prototype, {
    setup() {
        const config = this.props.config;
        if (config.key === "learn") {
            this.settingsConfig = {...config, lenses: config.lenses.map(l =>
                l.key === "settings" ? {...l, icon: "settings", label: _t("Settings"), pinned: true} : l)};
        } else if (catalogue[config.key]) {
            this.settingsLens = {key: "workspace_settings", label: _t("Settings"), title: _t("Workspace settings"),
                icon: "settings", pinned: true, Component: WorkspaceSettings};
            this.settingsConfig = {...config, lenses: [...config.lenses.filter(l => l.key !== "access"),
                this.settingsLens, ...config.lenses.filter(l => l.key === "access")]};
            if (["expenses", "insights", "compliance", "talent", "learning"].includes(config.key)
                    && registry.category("actions").contains("pb_access_board")
                    && !config.lenses.some(l => l.key === "access")) {
                this.settingsConfig.lenses.push({key: "access", label: _t("Access"), icon: "shield", pinned: true,
                    groups: ["base.group_user"], Component: WorkspaceAccess, props: {workspace: config.key,
                        back: {tag: this.props.action?.tag, label: config.brand.label, lens: "access"}}});
            }
        }
        super.setup(...arguments);
    },
    get config() { return this.settingsConfig || super.config; },
    async _resolveAccess() {
        if (this.settingsLens) {
            const config = this.config;
            const cards = await workspaceCards(this.env, this.orm, config.key, config.lenses);
            if (cards.length) {
                this.settingsLens.props = {cards, workspace: config.key, label: config.brand.label, select: key => this.setLens(key),
                    back: {label: config.brand.label, tag: this.props.action?.tag || this.actionService.currentController?.action?.tag, lens: this.settingsLens.key}};
            } else {
                this.settingsConfig = {...config, lenses: config.lenses.filter(l => l !== this.settingsLens)};
            }
        }
        return super._resolveAccess(...arguments);
    },
    get pinnedLenses() {
        return super.pinnedLenses.filter(l => !(this.config.key === "hiring" && l.key === "setup"
            && this.state.lens !== "setup" && this.lenses.some(item => item.key === "workspace_settings")));
    },
});

export class WorkspaceAccess extends Component {
    static template = "pb_settings.WorkspaceAccess";
    static props = ["*"];
    setup() {
        const orm = useService("orm");
        this.action = useService("action");
        onWillStart(async () => {
            this.screen = await orm.call("pb.settings", "workspace_access", [this.props.workspace]);
        });
    }
    manage() {
        return openHub(this.action, {xmlid: "biz_access.action_pb_access_board", lens: "screens",
            context: {pb_screen_id: this.screen.id}, back: this.props.back, clearBreadcrumbs: false});
    }
}
