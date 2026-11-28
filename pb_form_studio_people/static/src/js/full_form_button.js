/** @odoo-module **/
/**
 * R22 (2026-11-20) — a "Form builder" button on the employee's Full details
 * page (the restyled native form `hr.view_employee_form`), next to
 * "Set up workflow" in the form's top bar.
 *
 *   - Who: the side panel wand's own gate — `pb.form.studio.can_edit` for
 *     this host (R2, the administrator) — asked through
 *     `pb.form.studio.pbfs_people_full_form(view_id)`, which also answers
 *     False for every other employee form. Opening the Form builder is
 *     refused by the engine itself for anybody else (`get_studio` →
 *     `_pbfs_check_admin`).
 *   - Where: only the employee form shown full page (never in a dialog, an
 *     x2many sub-form or an embedded form without a top bar), so no other
 *     form view pays for an extra request.
 *   - What: the SAME overlay as the panel wand (`FormStudioOverlay`, through
 *     the overlay service like `people_form_patches.js` does). Unsaved
 *     changes are saved first, exactly like "Set up workflow".
 *   - After Publish: the engine has already re-drawn the "Company details"
 *     page of this form (`pb.form.native.view`, `_pbfs_resync_native`), so
 *     the cached screen design is dropped and the form is drawn again — no
 *     manual reload.
 *
 * Reached from OUTSIDE pb_lifecycle (which draws "Set up workflow" in the
 * same slot, `pb_lifecycle/static/src/xml/workflow_record.xml`): a patch of
 * the standard form controller, guarded by model, and a template extension.
 */
import { onWillUnmount, useState } from "@odoo/owl";
import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { rpcBus } from "@web/core/network/rpc";
import { FormStudioOverlay } from "@pb_form_studio/js/studio_overlay";
import { fsIc } from "@pb_form_studio/js/fs_icons";
import { PBFS_PEOPLE_HOST } from "./people_form_patches";

const MODEL = "hr.employee";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.pbfsFull = useState({ can: false, busy: false });
        this._pbfsFullRemove = null;
        this._pbfsFullDirty = false;
        if (this.props.resModel !== MODEL || this.env.inDialog || !this.display.controlPanel) {
            return;
        }
        this._pbfsFullOverlay = useService("overlay");
        const viewId = (this.env.config && this.env.config.viewId) || false;
        this.orm.call("pb.form.studio", "pbfs_people_full_form", [viewId])
            .then((ok) => { this.pbfsFull.can = Boolean(ok); })
            .catch(() => { this.pbfsFull.can = false; });
        onWillUnmount(() => this.pbfsFullClose(false));
    },

    pbfsFullIc(name, size = 15) { return fsIc(name, size); },

    async pbfsFullOpen() {
        if (!this.pbfsFull.can || this.pbfsFull.busy || this._pbfsFullRemove) { return; }
        this.pbfsFull.busy = true;
        try {
            // As "Set up workflow": the record is saved first (a new person
            // gets an id, so the Form builder can preview it).
            if (!(await this.model.root.save())) { return; }
            this._pbfsFullDirty = false;
            this._pbfsFullRemove = this._pbfsFullOverlay.add(FormStudioOverlay, {
                hostKey: PBFS_PEOPLE_HOST,
                recordId: this.model.root.resId || false,
                // FS-11: this page's own tabs are the fixed sections.
                surface: "full",
                returnLabel: "Back to record",
                onClose: () => this.pbfsFullClose(true),
                onPublished: () => { this._pbfsFullDirty = true; },
            });
        } finally {
            this.pbfsFull.busy = false;
        }
    },

    pbfsFullClose(reload) {
        const remove = this._pbfsFullRemove;
        this._pbfsFullRemove = null;
        if (remove) { remove(); }
        if (reload && this._pbfsFullDirty) {
            this._pbfsFullDirty = false;
            return this.pbfsFullReload();
        }
    },

    /** Draw this form again from the screen design the publish just wrote. */
    async pbfsFullReload() {
        if (this.isPremiumRecord) { return this.env.pbRecordWorkspace.reloadDesign(); }
        rpcBus.trigger("CLEAR-CACHES", "get_views");
        const ctl = this.actionService.currentController;
        if (ctl) {
            await this.actionService.restore(ctl.jsId);
        }
    },
});
