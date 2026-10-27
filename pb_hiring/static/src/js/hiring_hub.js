/** @odoo-module **/
/**
 * `pb_hiring_hub` — Hiring as its own place on the left menu (NAV P2).
 *
 * Overview, Roles, Applicants, Offers, Interviews and Resume bank reuse the
 * same board with a different initial tab. The resume-bank name matches its
 * on-screen tab, and Roles has its own direct submenu entry.
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
import { PbHiringSetup } from "@pb_hiring/js/hiring_setup";
import { HiringJobBoards } from "@pb_hiring/js/job_boards";

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

const HIRING_SETUP_GATE = [
    "pb_hiring.group_hiring_manager", "pb_hiring.group_hiring_admin", "base.group_system",
];

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
                { key: "roles", icon: "briefcase", label: _t("Roles"),
                  title: _t("Open roles"),
                  Component: PbHiringBoard, groups: HIRING_HUB_GATE, probe: PROBE,
                  props: { startTab: "roles", placeLens: "roles" } },
                // NAV P3a: every application and every offer, across roles.
                { key: "applicants", icon: "columns", label: _t("Applicants"),
                  title: _t("Applications across jobs"),
                  Component: PbHiringBoard, groups: HIRING_HUB_GATE, probe: PROBE,
                  props: { startTab: "applicants", placeLens: "applicants" } },
                { key: "jobboards", icon: "globe", label: _t("Job boards"),
                  title: _t("Advertise your roles"), Component: HiringJobBoards,
                  groups: HIRING_HUB_GATE, probe: { model: "pb.hiring", method: "can_open_job_boards" } },
                { key: "offers", icon: "send", label: _t("Offers"),
                  title: _t("Offers and joining checks"),
                  Component: PbHiringBoard, groups: HIRING_HUB_GATE, probe: PROBE,
                  props: { startTab: "offers", placeLens: "offers" } },
                { key: "interviews", icon: "calendarClock", label: _t("Interviews"),
                  Component: PbHiringBoard, groups: HIRING_HUB_GATE, probe: PROBE,
                  props: { startTab: "interviews", placeLens: "interviews" } },
                { key: "bank", icon: "bookOpen", label: _t("Resume bank"),
                  title: _t("Resume bank"),
                  Component: PbHiringBoard, groups: HIRING_BANK_GATE, probe: PROBE,
                  props: { startTab: "bank", placeLens: "bank" } },
                { key: "setup", icon: "sliders", label: _t("Set-up"),
                  title: _t("Hiring set-up"), Component: PbHiringSetup,
                  groups: HIRING_SETUP_GATE, probe: PROBE },
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

// Keep bookmarks, Settings cards, palette entries and the board's existing
// setup link working, with the SAME Hiring rail and permission checks.
export class PbHiringSetupWorkspace extends PbHiringHub {
    setup() {
        super.setup();
        this.config.defaultLens = "setup";
        this.config.rememberLens = false;
    }
}
registry.category("actions").add("pb_hiring_setup", PbHiringSetupWorkspace);

// The tabs' gates, as the config above declares them, so a lesson and the
// Access board can say "not for you" before anybody opens the hub.
registry.category(HUB_LENS_GATES).add("pb_hiring_hub", () => [
    { key: "overview", groups: HIRING_HUB_GATE, probe: PROBE },
    { key: "roles", groups: HIRING_HUB_GATE, probe: PROBE },
    { key: "applicants", groups: HIRING_HUB_GATE, probe: PROBE },
    { key: "offers", groups: HIRING_HUB_GATE, probe: PROBE },
    { key: "interviews", groups: HIRING_HUB_GATE, probe: PROBE },
    { key: "bank", groups: HIRING_BANK_GATE, probe: PROBE },
    { key: "jobboards", groups: HIRING_HUB_GATE, probe: { model: "pb.hiring", method: "can_open_job_boards" } },
    { key: "setup", groups: HIRING_SETUP_GATE, probe: PROBE },
    ...registry.category(HIRING_LENSES).getAll(),
].map((l) => ({ ...l, hubFeature: "lifecycle" })));
