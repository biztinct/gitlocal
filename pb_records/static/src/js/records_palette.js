/** @odoo-module **/
/**
 * The Records Desk's two doors.
 *
 *   1. **The People hub's Records lens.** Registered into `pb_people_hub`'s
 *      lens registry rather than imported into its config, because the
 *      dependency runs the other way: this module depends on the hub, so the
 *      hub cannot import this one back. Its gate is `hr.employee`'s READ access
 *      — the same list the Employees lens carries, imported rather than
 *      restated, because a gate that drifts from the surface's own produces
 *      either a lens nobody can open or an offer the facade refuses (W95/W29).
 *
 *   2. **A ⌘K palette row**, in the People hub's 1400 lens block, after the
 *      three the hub ships. The door is an XMLID and not a tag (W98): a bare
 *      tag is synthesised with no action NAME, and anything that later returns
 *      through a breadcrumb comes back to a crumb labelled "Unnamed".
 *
 * The lens icon is `database` — one of the sidebar's fixed Lucide set, which is
 * the constraint the rail puts on every hub icon.
 */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { EMPLOYEE_GATE, PEOPLE_LENSES } from "@pb_people_hub/js/people_hub";
import { PbRecordsDesk } from "@pb_records/js/records_desk";

registry.category(PEOPLE_LENSES).add("records", {
    key: "records",
    icon: "database",
    label: _t("Records"),
    Component: PbRecordsDesk,
    groups: EMPLOYEE_GATE,
    /**
     * The deep link, read once at config time. `records_employee_ids` is what
     * the People roster's Bulk update button sends; the other two are for R3's
     * doors and for a saved link into one scheme's fields.
     */
    propsFromContext(ctx) {
        return {
            employeeIds: ctx.records_employee_ids || null,
            configId: ctx.records_config_id || 0,
            fieldIds: ctx.records_field_ids || null,
        };
    },
}, { sequence: 40 });

const HUB_XMLID = "pb_people_hub.action_pb_people_hub";

registry.category("pb_hub_palette").add("peoplehub_records", {
    id: "peoplehub_records",
    label: _t("Records"),
    sublabel: _t("People"),
    icon: "database",
    groups: EMPLOYEE_GATE,
    // The presence probe: the actions registry holding this tag is what says
    // the module shipped its JS.
    requires: "pb_records_desk",
    action: { xmlid: HUB_XMLID, lens: "records" },
}, { sequence: 1440 });
