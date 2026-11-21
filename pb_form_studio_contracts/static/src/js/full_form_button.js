/** @odoo-module **/
/**
 * R22 (2026-11-20) — a "Form builder" button on the full contract form (the
 * restyled native form `hr_contract.hr_contract_view_form`, "Advanced form"
 * of the contract page), next to "Set up workflow" in the form's top bar.
 * Twin of `pb_form_studio_people/static/src/js/full_form_button.js`.
 *
 *   - Who: the contract panel wand's own gate — `pb.form.studio.can_edit`
 *     for this host (R2, the administrator) — asked through
 *     `pb.form.studio.fs3_full_form(view_id)`, which also answers False for
 *     every other contract form. Opening the Form builder is refused by the
 *     engine itself for anybody else (`get_studio` → `_pbfs_check_admin`).
 *   - Where: only the contract form shown full page (never in a dialog, an
 *     x2many sub-form or an embedded form without a top bar), so no other
 *     form view pays for an extra request.
 *   - What: the SAME overlay as the panel wand (`FormStudioOverlay`, through
 *     the overlay service). Unsaved changes are saved first, exactly like
 *     "Set up workflow".
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
import { FS3_HOST } from "./contract_drawer_patch";

const MODEL = "hr.contract";

patch(FormController.prototype, {
    setup() {
        super.setup(...arguments);
        this.fs3Full = useState({ can: false, busy: false });
        this._fs3FullRemove = null;
        this._fs3FullDirty = false;
        if (this.props.resModel !== MODEL || this.env.inDialog || !this.display.controlPanel) {
            return;
        }
        this._fs3FullOverlay = useService("overlay");
        const viewId = (this.env.config && this.env.config.viewId) || false;
        this.orm.call("pb.form.studio", "fs3_full_form", [viewId])
            .then((ok) => { this.fs3Full.can = Boolean(ok); })
            .catch(() => { this.fs3Full.can = false; });
        onWillUnmount(() => this.fs3FullClose(false));
    },

    fs3FullIc(name, size = 15) { return fsIc(name, size); },

    async fs3FullOpen() {
        if (!this.fs3Full.can || this.fs3Full.busy || this._fs3FullRemove) { return; }
        this.fs3Full.busy = true;
        try {
            // As "Set up workflow": the record is saved first (a new person
            // gets an id, so the Form builder can preview it).
            if (!(await this.model.root.save())) { return; }
            this._fs3FullDirty = false;
            this._fs3FullRemove = this._fs3FullOverlay.add(FormStudioOverlay, {
                hostKey: FS3_HOST,
                recordId: this.model.root.resId || false,
                // FS-11: this page's own tabs are the fixed sections.
                surface: "full",
                onClose: () => this.fs3FullClose(true),
                onPublished: () => { this._fs3FullDirty = true; },
            });
        } finally {
            this.fs3Full.busy = false;
        }
    },

    fs3FullClose(reload) {
        const remove = this._fs3FullRemove;
        this._fs3FullRemove = null;
        if (remove) { remove(); }
        if (reload && this._fs3FullDirty) {
            this._fs3FullDirty = false;
            return this.fs3FullReload();
        }
    },

    /** Draw this form again from the screen design the publish just wrote. */
    async fs3FullReload() {
        rpcBus.trigger("CLEAR-CACHES", "get_views");
        const ctl = this.actionService.currentController;
        if (ctl) {
            await this.actionService.restore(ctl.jsId);
        }
    },
});
