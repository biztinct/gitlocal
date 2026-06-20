/** @odoo-module **/
import { Dialog } from "@web/core/dialog/dialog";
import { ActionDialog } from "@web/webclient/actions/action_dialog";

// Odoo's Dialog hard-codes its default title to the literal "Odoo"
// (web/core/dialog/dialog.js). ActionDialog extends Dialog and SPREADS
// Dialog.defaultProps at class-definition time, so it keeps its own "Odoo"
// copy. Any record opened in a dialog without an explicit title then shows
// "Odoo" in the header. Blank both defaults — dialogs that pass a real title
// (e.g. "Open: Payslips", or a named action) are unaffected.
for (const Comp of [Dialog, ActionDialog]) {
    if (Comp && Comp.defaultProps) {
        Comp.defaultProps.title = "";
    }
}
