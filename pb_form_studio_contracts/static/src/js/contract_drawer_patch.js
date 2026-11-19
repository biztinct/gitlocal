/** @odoo-module **/
/**
 * FS-3 — the contract side panel learns the administrator's own fields.
 *
 * Reached from OUTSIDE pb_contracts (FS_HOST_FACTS §B.2), nothing there is
 * edited:
 *   - the Terms tab already loops `d.terms` groups, so the "Company details"
 *     group the server appends (`_cd_terms`) draws itself; text, numbers,
 *     money, dates, choice lists and links use the panel's own editor;
 *   - `CdEditor` is patched for the three kinds the panel never had: a real
 *     Yes / No (the stock `toggle` reads a selection), long text, and a file;
 *   - the Form builder wand sits in the panel header (administrator only)
 *     and the Studio opens over the panel;
 *   - a quiet "Add your own fields" card ends the Terms tab for the
 *     administrator while no field exists yet (R13: doable from the screen).
 *
 * Saving is the panel's own Save bar → `save_contract_360` → the same
 * approval as every other term (R9). Nothing here writes.
 */
import { onMounted } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { CdEditor, Contract360Drawer } from "@pb_contracts/js/contract_360";
import { FormStudioOverlay } from "@pb_form_studio/js/studio_overlay";
import { useFormStudio, FormStudioWand } from "@pb_form_studio/js/use_form_studio";
import { fsIc, KIND_ICON } from "@pb_form_studio/js/fs_icons";
import { readFileAsDataUrl } from "@pb_form_studio/js/fs_words";

export const FS3_HOST = "contract";
const NEW_KINDS = ["bool", "longtext", "file"];
const CUSTOM = "x_pbfs_";

// ---------------------------------------------------------------------------
//  CdEditor — three more kinds
// ---------------------------------------------------------------------------
patch(CdEditor.prototype, {
    setup() {
        super.setup(...arguments);
        onMounted(() => {
            // Like the stock Yes / No pair: no input, so the first button
            // takes the focus and Escape has somebody listening.
            if (this.kind === "bool" && this.rootRef.el) {
                const first = this.rootRef.el.querySelector("button");
                (first || this.rootRef.el).focus();
            }
        });
    },
    get kind() {
        const k = this.entry && this.entry.kind;
        return NEW_KINDS.includes(k) ? k : super.kind;
    },
    fsIc(n, s = 14) { return fsIc(n, s); },
    boolClass(on) { return { on: Boolean(this.props.value) === on }; },
    onBool(on) { this.commit(on, on ? this.yesLabel : this.noLabel); },
    get chooseFileLabel() { return _t("Choose a file"); },
    get fileHint() { return _t("PDF or image, up to 10 MB"); },
    async onFile(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) { return; }
        const data = await readFileAsDataUrl(file);
        this.commit(data, file.name);
    },
    onBlur() {
        if (this.kind === "longtext") {
            if (!this._committed) { this.commit(this.state.draft); }
            return;
        }
        return super.onBlur(...arguments);
    },
    onKey(ev) {
        if ((this.kind === "bool" || this.kind === "file") && ev.key !== "Escape") {
            // Their own buttons own Enter and Space (as the stock toggle).
            return;
        }
        if (this.kind === "longtext" && ev.key === "Enter" && !(ev.ctrlKey || ev.metaKey)) {
            // A new line, not a commit; kept from the panel's own keys.
            ev.stopPropagation();
            return;
        }
        return super.onKey(...arguments);
    },
});

// ---------------------------------------------------------------------------
//  Contract360Drawer — the wand, the Studio, the new group's look
// ---------------------------------------------------------------------------
Contract360Drawer.components = {
    ...Contract360Drawer.components, FormStudioWand, FormStudioOverlay,
};

patch(Contract360Drawer.prototype, {
    setup() {
        super.setup(...arguments);
        this.fs3Studio = useFormStudio({
            hostKey: FS3_HOST,
            recordId: () => Number(this.props.contractId) || false,
            onPublished: () => this.fs3OnPublished(),
        });
    },
    async fs3OnPublished() {
        // A publish (here or anywhere) re-reads the panel — unless the person
        // has typed something: their changes are never thrown away for a
        // layout change, they are told instead.
        if (this.isDirty) {
            this.notif.add(
                _t("The fields on this screen were changed. Save or discard your changes to see them."),
                { type: "info" });
            return;
        }
        await this.load();
    },
    fs3Ic(n, s = 14) { return fsIc(n, s); },
    fs3IsGroup(grp) { return Boolean(grp && grp.pbfs); },
    fs3GroupClass(grp) { return { "pbfs3-sec": this.fs3IsGroup(grp) }; },
    groupIcon(key) {
        if (String(key || "").startsWith("pbfs_")) {
            const grp = this.terms.find((g) => g.key === key);
            return fsIc((grp && grp.icon) || "sparkles", 14);
        }
        return super.groupIcon(...arguments);
    },
    fieldIcon(name) {
        if (String(name || "").startsWith(CUSTOM)) {
            const entry = this.termEntry(name);
            return fsIc(KIND_ICON[(entry && entry.kind) || "text"] || "type", 14);
        }
        return super.fieldIcon(...arguments);
    },
    cellClass(f) {
        const out = super.cellClass(...arguments);
        if (f && f.pbfs) {
            out["pbfs3-cell"] = true;
            out["pbfs3-long"] = f.kind === "longtext";
        }
        return out;
    },
    fs3FileUrl(f) {
        return f && f.kind === "file" && f.url && !this.isTermDirty(f.name) ? f.url : "";
    },
    get fs3DownloadLabel() { return _t("Download"); },
    /** The administrator's "Add your own fields" card: only while no field
     *  of theirs is on this contract's Terms yet. */
    get fs3ShowPrompt() {
        return Boolean(this.fs3Studio.state.canEdit) && !this.terms.some((g) => g.pbfs);
    },
    fs3Open() { this.fs3Studio.open(); },
});
