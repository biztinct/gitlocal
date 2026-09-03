/** @odoo-module **/
/**
 * <HubFeatureOff/> — what a workspace shows when the company has not got it.
 *
 * WHY THIS IS A COMPONENT AND NOT THREE LINES IN THE SHELL. Taking an entry off
 * the left menu stops people FINDING a door. It does nothing at all for the
 * people who already know where it is: a bookmark from before, an address typed
 * from memory, a link pasted by a colleague at another company. Every one of
 * those arrives at the workspace itself, and without this they would get an
 * empty screen, a spinner that never stops, or a stack trace — the exact dead
 * end the design bar forbids.
 *
 * Mission Control has its own shell rather than the kit's, so the page has to
 * be reusable to be honest: two implementations would drift, and the customer
 * who sees the drift is the one being sold something.
 *
 * IT IS NOT A LOCK ON ANYTHING. The data behind the door keeps its own
 * permissions, exactly as before, and this page never claims otherwise — it
 * says the part of the product is not switched on for this company, which is
 * what is true.
 */
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

export class HubFeatureOff extends Component {
    static template = "pb_hub.HubFeatureOff";
    static props = {
        /** What the workspace is called, e.g. "Insights". */
        label: { type: String },
        /** The workspace's own glyph, so the page still feels like the place. */
        icon: { type: String, optional: true },
        /** The platform's own sentence. A standard one is used when empty. */
        text: { type: String, optional: true },
        /** Optional: open the search panel, so there is somewhere to go. */
        onSearch: { type: Function, optional: true },
        slots: { type: Object, optional: true },
        "*": true,
    };

    ic(n, s = 15) { return ic(n, s); }

    get title() {
        return _t("%s is not switched on", this.props.label);
    }

    get sentence() {
        return this.props.text
            || _t("This part of Payobook is not switched on for your company.");
    }

    get hint() {
        return _t("Ask Payobook to switch it on. Everything else you use is "
                  "unaffected.");
    }

    get hasSearch() { return typeof this.props.onSearch === "function"; }

    search() { if (this.hasSearch) { this.props.onSearch(); } }
}
