/** @odoo-module **/
/**
 * `pb_hiring_hub` — Hiring as its own place on the left menu (NAV P2).
 *
 * Until NAV P2 the Hiring board was the first tab of the Lifecycle hub. The
 * owner's revised menu (design review §12.4) gives it its own entry under
 * OPERATE, with three tabs on the rail:
 *
 *     overview · interviews · bank
 *
 * All three are the SAME board (`PbHiringBoard`) opened on a different inner
 * tab — the board already owns roles / interviews / the resume bank, so the
 * rail is a quicker way to the tab you want, never a second copy of it.
 *
 * Gates (W95): the board's own question, exactly as the Lifecycle tab asked it.
 * The group list is advisory and fails open; `pb.hiring.can_open` is the probe
 * that decides, and `pb.hiring._can_read()` enforces server-side regardless.
 * The resume bank is the hiring team's own, never a line manager's.
 *
 * Other modules may add a lens through `HIRING_LENSES` (the soft-registry
 * pattern every hub uses).
 *
 * `config` is built ONCE per instance, never in a getter (W21).
 */
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { HubShell } from "@pb_hub/js/hub_shell";
import { openHub } from "@pb_hub/js/hub_nav";
import { HUB_LENS_GATES } from "@pb_hub/js/hub_gates";
import { LIFECYCLE_GATE } from "@pb_lifecycle/js/lifecycle_hub";
import { PbHiringBoard } from "@pb_hiring/js/hiring_board";

/** Who is offered the board — unchanged from the old Lifecycle tab. */
export const HIRING_HUB_GATE = LIFECYCLE_GATE.concat([
    "pb_hiring.group_hiring_user",
    "pb_hiring.group_hiring_manager",
    "pb_hiring.group_hiring_admin",
    // RECRUIT P1 (RC-D1): a line manager reads the board of their own roles
    // and holds no hiring group — the probe is what decides.
    "base.group_user",
]);

/** The resume bank: the hiring team only (manager and admin imply user). */
export const HIRING_BANK_GATE = ["pb_hiring.group_hiring_user"];

const PROBE = { model: "pb.hiring", method: "can_open" };

/** Where a later module bolts a lens onto the Hiring hub. */
export const HIRING_LENSES = "pb_hiring_hub_lens";

export class PbHiringHub extends Component {
    static template = "pb_hiring.PbHiringHub";
    static components = { HubShell };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.actionService = useService("action");
        const ctx = (this.props.action && this.props.action.context) || {};
        // A deep link may name the role to open on arrival (RECRUIT P1).
        const role = ctx.pb_role_id ? { roleId: ctx.pb_role_id } : {};

        this.config = {
            key: "hiring",                    // -> pbhub.hiring.lens.v1
            brand: { label: _t("Hiring"), icon: "userPlus" },
            // FLEET P4: hiring is part of the Lifecycle product switch.
            feature: "lifecycle",
            defaultLens: "overview",
            cog: () => this.openSettings(),
            lenses: [
                { key: "overview", icon: "layoutGrid", label: _t("Overview"),
                  title: _t("Who we are hiring"),
                  Component: PbHiringBoard, groups: HIRING_HUB_GATE, probe: PROBE,
                  props: { ...role, placeLens: "overview" } },
                { key: "interviews", icon: "calendarClock", label: _t("Interviews"),
                  Component: PbHiringBoard, groups: HIRING_HUB_GATE, probe: PROBE,
                  props: { startTab: "interviews", placeLens: "interviews" } },
                { key: "bank", icon: "bookOpen", label: _t("Talent pool"),
                  title: _t("Talent pool (resume bank)"),
                  Component: PbHiringBoard, groups: HIRING_BANK_GATE, probe: PROBE,
                  props: { startTab: "bank", placeLens: "bank" } },
                ...this.extraLenses(),
            ],
        };
    }

    /** Lenses other modules registered, resolved ONCE (never in a getter, W21). */
    extraLenses() {
        const ctx = (this.props.action && this.props.action.context) || {};
        return registry.category(HIRING_LENSES).getAll().map((def) => {
            const props = typeof def.propsFromContext === "function"
                ? def.propsFromContext(ctx) : (def.props || {});
            return { ...def, props };
        });
    }

    /** The cog. A CLICK handler — the shell calls it, nothing else does. */
    openSettings() {
        openHub(this.actionService, {
            xmlid: "pb_settings.action_pb_settings_hub",
            back: { label: _t("Hiring"), xmlid: "pb_hiring.action_pb_hiring_hub" },
        });
    }
}

registry.category("actions").add("pb_hiring_hub", PbHiringHub);

// The tabs' gates, as the config above declares them, so a lesson and the
// Access board can say "not for you" before anybody opens the hub.
registry.category(HUB_LENS_GATES).add("pb_hiring_hub", () => [
    { key: "overview", groups: HIRING_HUB_GATE, probe: PROBE },
    { key: "interviews", groups: HIRING_HUB_GATE, probe: PROBE },
    { key: "bank", groups: HIRING_BANK_GATE, probe: PROBE },
    ...registry.category(HIRING_LENSES).getAll(),
].map((l) => ({ ...l, hubFeature: "lifecycle" })));
