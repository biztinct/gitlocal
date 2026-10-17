/** @odoo-module **/
/**
 * The bridge's three rows in the global ⌘K palette.
 *
 * NO RAIL ITEM, deliberately. The rail is eight missions and a cog, and an
 * inbound connection is not a ninth mission — it is something an administrator
 * visits when they are wiring the product up or when a joiner did not appear.
 * The palette is exactly the right door for that: you reach it by knowing what
 * you want, not by scanning a list of everything.
 *
 * Every row obeys the two rules the seed file sets out. Each is GATED, because
 * all three open native admin screens whose ACL genuinely would refuse a plain
 * user — unlike a hub, a native list answers a refusal with an access dialog,
 * so offering it ungated would be a door that can only produce an error. And
 * each carries a `requires` tag, the presence probe the palette service runs
 * before offering an xmlid door.
 *
 * `requires` names the LIFECYCLE hub's tag rather than one of ours, for the
 * plain reason that this module ships no client action of its own: it has no
 * cockpit. `pb_lifecycle` is a hard dependency, so its tag is present exactly
 * when this file is, which is what the probe is actually asking.
 *
 * Sequences 2150-2152, in the deep-link band, clear of P0's 2100-2120.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { G_ADMIN } from "@pb_hub/js/hub_palette_entries";

const palette = registry.category("pb_hub_palette");
const REQUIRES = "pb_lifecycle_hub";

// Who may see these rows. The integration tier wires connections up; the
// lifecycle tiers own the joiners and leavers that come down them; System is
// there because an administrator holds the groups by implication, not by name.
const MANAGER = [
    "pb_hr_payroll_base.group_payroll_integration_user",
    "pb_lifecycle.group_lifecycle_manager",
    "pb_lifecycle.group_lifecycle_admin",
    "base.group_system",
];
const ADMIN = [
    "pb_lifecycle.group_lifecycle_admin",
    "base.group_system",
];

palette.add("zoho_upload", {
    id: "zoho_upload",
    label: _t("Upload a joiner file"),
    sublabel: _t("Connected system"),
    icon: "upload",
    groups: MANAGER,
    action: { xmlid: "pb_zoho_bridge.action_zoho_upload_wizard" },
    requires: REQUIRES,
}, { sequence: 2150 });

palette.add("zoho_inbox", {
    id: "zoho_inbox",
    label: _t("Arrivals from the connected system"),
    sublabel: _t("Connected system"),
    icon: "inbox",
    groups: MANAGER,
    action: { xmlid: "pb_zoho_bridge.action_zoho_inbox" },
    requires: REQUIRES,
}, { sequence: 2151 });

palette.add("zoho_rules", {
    id: "zoho_rules",
    label: _t("Arrival rules"),
    sublabel: _t("Connected system"),
    icon: "plug",
    group: G_ADMIN,
    groups: ADMIN,
    action: { xmlid: "pb_zoho_bridge.action_zoho_event_rule" },
    requires: REQUIRES,
}, { sequence: 2152 });
