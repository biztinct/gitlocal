/** @odoo-module **/
/**
 * useFormStudio — what a host screen adds to offer the Form builder.
 *
 *     setup() {
 *         this.studio = useFormStudio({
 *             hostKey: "employee_detail",
 *             recordId: () => this.props.employeeId,     // optional, for the preview
 *             onPublished: () => this.reload(),          // this screen AND others' (bus)
 *         });
 *     }
 *
 *     <FormStudioWand studio="studio"/>               (toolbar: administrator only)
 *     <FormStudioOverlay t-if="studio.state.open" t-props="studio.overlayProps"/>
 *
 * The wand is drawn only when the server says this person may edit this
 * screen (`pb.form.studio.can_edit`, the administrator — R2). A publish by
 * anybody, on any device, reaches every open copy of the host through the
 * bus (`pb_form_studio/published`), and `onPublished` reloads it.
 */
import { Component, useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { fsIc } from "./fs_icons";
import { FACADE } from "./fs_words";

export function useFormStudio({ hostKey, recordId, onPublished }) {
    const orm = useService("orm");
    const bus = useService("bus_service");
    const state = useState({ canEdit: false, open: false, focusField: "" });
    const key = () => (typeof hostKey === "function" ? hostKey() : hostKey);
    const rec = () => (typeof recordId === "function" ? recordId() : recordId || false);

    onWillStart(async () => {
        try {
            state.canEdit = Boolean(await orm.call(FACADE, "can_edit", [key()]));
        } catch {
            state.canEdit = false;
        }
    });

    const onBus = (payload) => {
        if (payload && payload.host_key === key() && onPublished && !state.open) {
            onPublished(payload);
        }
    };
    bus.subscribe("pb_form_studio/published", onBus);
    onWillUnmount(() => bus.unsubscribe("pb_form_studio/published", onBus));

    const api = {
        state,
        open(focusField = "") {
            if (!state.canEdit) { return; }
            state.focusField = focusField;
            state.open = true;
        },
        close() { state.open = false; },
        get overlayProps() {
            return {
                hostKey: key(),
                recordId: rec(),
                focusField: state.focusField || undefined,
                onClose: () => { state.open = false; },
                onPublished: async (res) => { if (onPublished) { await onPublished(res); } },
            };
        },
    };
    return api;
}

/** The toolbar button. Draws nothing for anybody but the administrator. */
export class FormStudioWand extends Component {
    static template = "pb_form_studio.Wand";
    static props = { studio: { type: Object }, compact: { type: Boolean, optional: true } };
    ic(n, s = 15) { return fsIc(n, s); }
    get title() { return _t("Add or move fields on this screen"); }
    open() { this.props.studio.open(); }
}
