/** @odoo-module **/
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

// Optional Settings extension: the existing hub owns navigation and gates.
registry.category("pb_settings_category").add("attendance_connectors", {
    key: "attendance_connectors", group: "integrations", icon: "clock",
    label: _t("Attendance"),
    blurb: _t("Connect an office PC and follow its attendance uploads."),
    groups: ["hr_attendance.group_hr_attendance_manager"],
    cards: [{ id: "attendance_connectors", xmlid: "pb_clock.action_clock_connectors", icon: "clock",
        label: _t("Attendance connectors"),
        sub: _t("Guided Windows setup, secure IT invitations and connection health.") }],
}, { sequence: 35 });
