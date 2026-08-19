/** @odoo-module **/
/**
 * `pb_hub_demo` — the kit's test surface and its living documentation.
 *
 * A HIDDEN client action: it has an `ir.actions.client` record so it can be
 * opened by URL (`/odoo/action-pb_hub_demo`, `/bizapp/...` on the live server),
 * and deliberately no menu and no `pb.sidebar.item`, because it is not a product
 * surface. It exists so that every part of the shell contract can be exercised
 * without waiting for Cycle 2 to build a real hub, and so that the next person to
 * build one has a worked example in the repository rather than a paragraph in a
 * handover.
 *
 * What it demonstrates, in order:
 *   - three lenses with real components, plus a FOURTH gated to a group no
 *     backend user has (`base.group_portal`), which must therefore be ABSENT
 *     from the rail rather than present and disabled;
 *   - a lens declared with no `Component`, which renders the shell's honest
 *     placeholder instead of an error;
 *   - the period tracker chip;
 *   - a 268px dock;
 *   - the cog callback;
 *   - `openHub()` with a `back` door, and the `<HubBackChip/>` the shell renders
 *     when it arrives.
 */
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubShell } from "@pb_hub/js/hub_shell";
import { openHub } from "@pb_hub/js/hub_nav";

/** A lens body. Takes `embedded` like every real cockpit does (W17). */
export class HubDemoLens extends Component {
    static template = "pb_hub.HubDemoLens";
    static props = {
        embedded: { type: Boolean, optional: true },
        title: { type: String },
        note: { type: String },
        // present only on the lens that declares `wantsArrival`
        arrival: { type: Object, optional: true },
        onDeepLink: { type: Function, optional: true },
    };

    setup() { this.state = useState({ clicks: 0 }); }
    ic(n, s = 16) { return ic(n, s); }

    /** A CLICK handler. Nothing in this component writes from a mount hook. */
    bump() { this.state.clicks += 1; }

    deepLink() { if (this.props.onDeepLink) { this.props.onDeepLink(); } }
}

/** The dock placeholder: the 268px right column, with nothing real in it yet. */
export class HubDemoDock extends Component {
    static template = "pb_hub.HubDemoDock";
    static props = {};
    ic(n, s = 15) { return ic(n, s); }
}

export class PbHubDemo extends Component {
    static template = "pb_hub.PbHubDemo";
    static components = { HubShell };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.actionService = useService("action");
        this.notif = useService("notification");

        // Built ONCE per instance, never in a getter: the shell's `config` prop
        // must keep a stable identity or every render recreates every lens
        // (the refetch trap, W21).
        this.config = {
            key: "demo",                        // -> pbhub.demo.lens.v1
            brand: { label: _t("Hub Demo"), icon: "compass" },
            defaultLens: "overview",
            tracker: {
                label: _t("Aug cycle"),
                stage: 2,
                total: 5,
                onClick: () => this.notif.add(
                    _t("Cycle 2 wires this chip to the real period."),
                    { type: "info" }),
            },
            dock: HubDemoDock,
            cog: () => this.openSettings(),
            lenses: [
                {
                    key: "overview", icon: "activity", label: _t("Overview"),
                    Component: HubDemoLens,
                    wantsArrival: true,
                    props: {
                        title: _t("Overview"),
                        note: _t("Switch lens, reload the page: the shell "
                                 + "remembers it in pbhub.demo.lens.v1."),
                        onDeepLink: () => this.demoDeepLink(),
                    },
                },
                {
                    key: "records", icon: "table", label: _t("Records"),
                    Component: HubDemoLens,
                    props: {
                        title: _t("Records"),
                        note: _t("A second lens, mounted with embedded=true — "
                                 + "exactly how a real cockpit joins a hub."),
                    },
                },
                {
                    // No `Component`: the shell renders its placeholder rather
                    // than a broken lens. A hub may declare a lens before the
                    // surface behind it exists, as long as it does not pretend.
                    key: "later", icon: "settings", label: _t("Later"),
                },
                {
                    // Gated to a group no backend user holds, so it must be
                    // ABSENT from the rail — not present and disabled (W29).
                    key: "portal", icon: "lock", label: _t("Portal"),
                    groups: ["base.group_portal"],
                    Component: HubDemoLens,
                    props: { title: _t("Portal"), note: _t("You should never see this.") },
                },
            ],
        };
    }

    /**
     * Re-enter this same hub on the Records lens, carrying a back door.
     *
     * This is the whole one-door law in four lines: the caller says where it is
     * sending you AND how to get back, and the shell renders the return chip
     * (W5 — no dead ends).
     */
    demoDeepLink() {
        openHub(this.actionService, {
            tag: "pb_hub_demo",
            lens: "records",
            back: { label: _t("Overview"), tag: "pb_hub_demo", lens: "overview" },
        });
    }

    /**
     * The cog, wired in Cycle 3 — to a tag, by name, never by import.
     *
     * `pb_settings` DEPENDS ON this module, so importing its hub here would be a
     * cycle the module graph refuses. The registry is the honest test instead: a
     * module that is not installed did not ship its JS, so its tag is simply not
     * there (the same probe the palette service uses). A cog that opened nothing
     * would be W29's door that can only produce an error, so on a database
     * without pb_settings it SAYS so rather than doing nothing at all.
     */
    openSettings() {
        if (!registry.category("actions").contains("pb_settings_hub")) {
            this.notif.add(_t("The Settings hub is not installed on this database."),
                           { type: "warning" });
            return;
        }
        openHub(this.actionService, {
            // The registry probe above is on the TAG (that is what a module
            // ships); the door is the XMLID, because only the record carries a
            // name for the breadcrumb.
            xmlid: "pb_settings.action_pb_settings_hub",
            back: { label: _t("Hub Demo"), tag: "pb_hub_demo" },
        });
    }
}

registry.category("actions").add("pb_hub_demo", PbHubDemo);
