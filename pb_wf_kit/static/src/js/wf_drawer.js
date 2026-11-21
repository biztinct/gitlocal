/** @odoo-module **/
/**
 * <WfDrawer/> — right-side slide-in panel; the person-drawer chassis from
 * mockup A. P0 ships the chassis only: callers own the content through the
 * default slot, so P1 can put a person's week, exceptions and actions inside
 * without touching this file.
 *
 * "Every record is a door" (W5) needs a door that is cheap to open — a drawer,
 * not a route change — which is why this exists before anything uses it.
 */
import { Component, useExternalListener } from "@odoo/owl";
import { ic } from "@pb_import_kit/js/import_icons";

export class WfDrawer extends Component {
    static template = "pb_wf_kit.WfDrawer";
    static props = {
        title: { type: String },
        subtitle: { type: String, optional: true },
        onClose: { type: Function },
        slots: { type: Object, optional: true },
    };
    static defaultProps = { subtitle: "" };

    setup() {
        // Bound on document: the drawer is not focusable itself, and an officer
        // reaching for ESC has usually just clicked a row in the grid behind it.
        useExternalListener(document, "keydown", this.onKeydown);
    }

    ic(n, s = 16) { return ic(n, s); }

    onKeydown(ev) {
        if (ev.key === "Escape") {
            ev.stopPropagation();
            this.props.onClose();
        }
    }
}
