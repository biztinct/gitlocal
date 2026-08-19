/** @odoo-module **/
/**
 * The Plan lens — a launcher, and DELIBERATELY nothing more.
 *
 * The owner's ruling for this programme is that Workforce Planning gets a
 * minimal MENU change and no product change: its screens, its actions and its
 * flows are a separate piece of work. Seven rail items used to sit in a
 * PLANNING section of their own; this is where they go, and every one of them
 * opens the same thing it opened yesterday.
 *
 * So there is no embedding here, no re-skin, no descriptor over a planning
 * model and no facade of any kind. This component knows two things about
 * Planning: the xmlid of each action, and which groups may read the model
 * behind it. Both are checked by the tests against the real files, and
 * `pb_people_hub/tests` walks the whole `pb_hr_workforce_planning` directory to
 * assert this cycle changed none of it.
 *
 * Three rules it shares with the Settings hub, each of them scar tissue:
 *
 *  1. **A card that opens nothing is not rendered.** The client-action card is
 *     probed against the actions registry; the six `act_window` cards are
 *     probed server-side through `pb.settings.resolve_actions`. A tile pointing
 *     at an action that is not installed renders normally and answers a click
 *     with silence — no traceback, nothing in the log (W79).
 *  2. **A card this persona cannot use is ABSENT, not disabled** (W29), and the
 *     gate is derived from the target model's own `ir.model.access` rather than
 *     from the rail item that used to open it (W95). The seven planning models
 *     do NOT all grant read to the same tier — `wfp.pay.grade` and
 *     `wfp.merit.matrix` are admin+user while the rest are manager+user, and
 *     `wfp.tagging.wizard` is manager only — so one gate for the lens would
 *     have been a gate that is wrong for three of its cards.
 *  3. **Every door is a CLICK handler**, and `_opening` makes a double-click
 *     one navigation rather than two (W21.1's lesson applied to navigation).
 *
 * The way back, per card kind:
 *   - the six native lists render Odoo's own control panel, so they are opened
 *     WITHOUT clearing the breadcrumbs and "People" is the crumb home;
 *   - the Planning Dashboard is a full-bleed cockpit with no control panel, so
 *     its way back is the rail — which is precisely the way back it has today
 *     from the rail's own Planning Dashboard item. Giving it a back chip would
 *     mean editing a Planning screen.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const WFP_USER = "pb_hr_workforce_planning.group_wfp_user";
const WFP_MANAGER = "pb_hr_workforce_planning.group_wfp_manager";
const WFP_ADMIN = "pb_hr_workforce_planning.group_wfp_admin";

/**
 * Anyone who holds any planning tier at all. `wfp_admin` implies `wfp_manager`
 * implies `wfp_user` on this database, so this is really one question asked
 * three ways — written out because an implication is a fact about the data and
 * a list is a fact about the code.
 */
export const PLAN_GATE = [WFP_USER, WFP_MANAGER, WFP_ADMIN];

/**
 * The seven cards, in the order the retired PLANNING section had them.
 *
 * `gate` is the set of groups `ir.model.access` grants READ on `model` — read
 * off `pb_hr_workforce_planning/security/ir.model.access.csv` and asserted
 * against `ir_model_access` by the tests, because a gate that fails open is
 * invisible at runtime in both directions (W95).
 */
export const PLAN_CARDS = [
    {
        id: "dashboard", icon: "activity", label: _t("Planning Dashboard"),
        sub: _t("Scenario headlines, labour analytics and the compensation view."),
        xmlid: "pb_hr_workforce_planning.action_wfp_dashboard",
        tag: "wfp_dashboard",
        model: "wfp.planning.scenario", gate: [WFP_USER, WFP_MANAGER],
    },
    {
        id: "scenarios", icon: "compass", label: _t("Planning Scenarios"),
        sub: _t("Increase rules, the configuration they run on, and their results."),
        xmlid: "pb_hr_workforce_planning.action_wfp_scenario",
        model: "wfp.planning.scenario", gate: [WFP_USER, WFP_MANAGER],
    },
    {
        id: "forecasts", icon: "trendingUp", label: _t("Employee Forecasts"),
        sub: _t("Per-employee projections, pivoted and graphed."),
        xmlid: "pb_hr_workforce_planning.action_wfp_forecast",
        model: "wfp.employee.forecast", gate: [WFP_USER, WFP_MANAGER],
    },
    {
        id: "grades", icon: "layers", label: _t("Pay Grades"),
        sub: _t("The bands a salary is measured against."),
        xmlid: "pb_hr_workforce_planning.action_wfp_grade",
        model: "wfp.pay.grade", gate: [WFP_USER, WFP_ADMIN],
    },
    {
        id: "merit", icon: "calculator", label: _t("Merit Matrix"),
        sub: _t("Performance against position in band, and what each cell awards."),
        xmlid: "pb_hr_workforce_planning.action_wfp_merit_matrix",
        model: "wfp.merit.matrix", gate: [WFP_USER, WFP_ADMIN],
    },
    {
        id: "cycles", icon: "calendar", label: _t("Compensation Cycles"),
        sub: _t("The review periods a scenario is proposed and approved inside."),
        xmlid: "pb_hr_workforce_planning.action_wfp_cycle",
        model: "wfp.compensation.cycle", gate: [WFP_USER, WFP_MANAGER],
    },
    {
        id: "tagging", icon: "database", label: _t("Tag Formula Components"),
        sub: _t("Mark which salary components a planning run may move."),
        xmlid: "pb_hr_workforce_planning.action_wfp_tagging_wizard",
        model: "wfp.tagging.wizard", gate: [WFP_MANAGER],
    },
];

/** Every action xmlid the descriptor names, for one probe round trip. */
export function planActionXmlids() {
    return [...new Set(PLAN_CARDS.map((c) => c.xmlid))];
}

export class PlanLauncher extends Component {
    static template = "pb_people_hub.PlanLauncher";
    static props = {
        embedded: { type: Boolean, optional: true },
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");

        this.state = useState({
            resolved: false,
            allowed: null,      // card id -> boolean; null while unresolved
            present: {},        // action xmlid -> boolean
        });

        // One navigation at a time. Two clicks 40ms apart are one intent, and
        // doAction is happy to run both.
        this._opening = false;

        onWillStart(async () => { await this._resolve(); });
    }

    ic(n, s = 17) { return ic(n, s); }

    // ------------------------------------------------------------- resolution
    async _resolve() {
        const [allowed, present] = await Promise.all([
            this._resolveGroups(), this._resolveActions(),
        ]);
        this.state.allowed = allowed;
        this.state.present = present;
        this.state.resolved = true;
    }

    /**
     * Fails OPEN per group: an xmlid that will not resolve means the module is
     * not installed here, and reading that as "denied" would hide a card for
     * the wrong reason. Nothing here is a security boundary — every action
     * keeps its own (W12).
     */
    async _resolveGroups() {
        const names = [...new Set(PLAN_CARDS.flatMap((c) => c.gate))];
        const flags = {};
        await Promise.all(names.map(async (g) => {
            try { flags[g] = await user.hasGroup(g); }
            catch (e) {
                console.warn("pb_people_hub: could not resolve group", g, e);
                flags[g] = true;
            }
        }));
        const allowed = {};
        for (const c of PLAN_CARDS) {
            allowed[c.id] = c.gate.some((g) => flags[g]);
        }
        return allowed;
    }

    /**
     * Which actions exist here. One RPC for the whole descriptor, through the
     * Settings hub's existing probe — `resolve_actions` asks "does this xmlid
     * resolve" and nothing else, so it is the right question whoever is asking.
     *
     * On failure every card is treated as ABSENT rather than present: an empty
     * lens is a smaller lie than a broken one. Reported, never swallowed into a
     * decoration (W40).
     */
    async _resolveActions() {
        try {
            return await this.orm.call(
                "pb.settings", "resolve_actions", [planActionXmlids()]);
        } catch (e) {
            console.warn("pb_people_hub: could not probe the planning actions", e);
            return {};
        }
    }

    // --------------------------------------------------------------- the grid
    _present(card) {
        // A client action also has to be REGISTERED — the server can resolve an
        // `ir.actions.client` record whose JS never shipped, and that opens a
        // blank screen rather than nothing at all.
        if (card.tag && !registry.category("actions").contains(card.tag)) {
            return false;
        }
        return !!this.state.present[card.xmlid];
    }

    get cards() {
        const allowed = this.state.allowed;
        return PLAN_CARDS.filter(
            (c) => (!allowed || allowed[c.id]) && this._present(c));
    }

    // ----------------------------------------------------------------- doors
    /**
     * Open the existing screen, exactly as the rail opened it.
     *
     * `clearBreadcrumbs: false` for every card: the six native lists render
     * Odoo's control panel, so the crumb is the way back. The Planning
     * Dashboard renders no control panel and therefore shows no crumb — its way
     * back is the rail, unchanged from today, and adding a chip to it would be
     * editing a Planning screen.
     */
    openCard(card) {
        if (this._opening) { return; }
        this._opening = true;
        Promise.resolve(
            this.actionService.doAction(card.xmlid, { clearBreadcrumbs: false })
        ).catch((e) => {
            this._opening = false;
            console.warn("pb_people_hub: planning card failed to open", card.id, e);
        });
    }

    // ----------------------------------------------------------------- empty
    get emptyTitle() { return _t("Workforce Planning is not open to you."); }

    get emptyNote() {
        return _t("Planning scenarios, forecasts, pay grades and merit "
                  + "matrices are read by the Workforce Planning roles. Your "
                  + "account holds none of them.");
    }
}
