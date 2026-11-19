/** @odoo-module **/
/**
 * Form builder on the employee screens (FS-2) — by `patch()` and template
 * inheritance only (no edit of pb_people / pb_employee_vault; precedent
 * `pb_job_change/static/src/js/job_change_patches.js:51`).
 *
 *   1. The side panel (`Employee360Drawer`): a "Company details" tab drawn
 *      with the engine's `PbFieldGrid` — editable for HR with ONE Save (R8),
 *      look-only for a reader who may not change the employee — and, for the
 *      administrator only, the Form builder wand in the panel header.
 *      The Studio overlay is mounted through the overlay service, NOT inside
 *      the panel: the panel slides in with a CSS transform, and a fixed
 *      element inside a transformed parent is trapped in that parent's box.
 *   2. The employee full page (`PbEmployeeDetail`): the same sections,
 *      look-only.
 *   3. The engine's publish sheet: one plain line when new fields are in it
 *      (ADDENDUM item 3; merge-time task: move it into the engine).
 *
 * Data: `profile.form_sections` (server `get_employee_detail` + this
 * module), reloaded with `pb.people.pbfs_employee_sections`, saved with
 * `pb.people.pbfs_save_employee` → `pb.form.studio.write_values`.
 * A publish anywhere reaches an open panel through the bus (`useFormStudio`).
 */
import { useState, onWillUnmount } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { Employee360Drawer } from "@pb_employee_vault/js/employee_360";
import { PbEmployeeDetail } from "@pb_people/js/employee_detail";
import { PbFieldGrid } from "@pb_form_studio/js/field_grid";
import { FormStudioOverlay } from "@pb_form_studio/js/studio_overlay";
import { useFormStudio } from "@pb_form_studio/js/use_form_studio";
import { fsIc } from "@pb_form_studio/js/fs_icons";

export const PBFS_PEOPLE_HOST = "employee_detail";
const PEOPLE = "pb.people";
const TAB = "company";
/** Keys pressed inside the grid's own editors are theirs, never the panel's. */
const OWN_KEYS = ".pbfb-ed, .pbfb-pick, .pbfb-overlay, .pbfb-sheet";

function msgOf(e, fallback) {
    const data = (e && e.data) || (e && e.message && e.message.data);
    return (data && data.message) || fallback;
}

// ===================================================================
//  1. The side panel
// ===================================================================
Employee360Drawer.components = Object.assign({}, Employee360Drawer.components, { PbFieldGrid });

patch(Employee360Drawer.prototype, {
    setup() {
        super.setup(...arguments);
        this.pbfs = useState({
            data: null, staged: {}, errors: {}, saving: false, leaving: false,
        });
        this._pbfsNext = null;
        this._pbfsRemoveStudio = null;
        this.pbfsStudio = useFormStudio({
            hostKey: PBFS_PEOPLE_HOST,
            recordId: () => Number(this.props.empId) || false,
            onPublished: () => this.pbfsReload(),
        });
        onWillUnmount(() => this.pbfsCloseStudio());
    },

    async load() {
        await super.load(...arguments);
        const profile = this.state.d && this.state.d.profile;
        this.pbfs.data = (profile && profile.form_sections) || null;
    },

    // ---------------------------------------------------------- reading
    pbfsIc(name, size = 15) { return fsIc(name, size); },
    get pbfsData() { return this.pbfs.data || {}; },
    get pbfsSections() { return this.pbfsData.sections || []; },
    get pbfsHasFields() { return Boolean(this.pbfsData.total); },
    get pbfsIsAdmin() { return Boolean(this.pbfsStudio.state.canEdit); },
    /** HR sees the tab when there is something to show; the administrator
     *  always (it is where they start adding fields). */
    get pbfsShowTab() { return Boolean(this.pbfs.data) && (this.pbfsHasFields || this.pbfsIsAdmin); },
    get pbfsMode() { return this.pbfsData.editable ? "edit" : "read"; },
    get pbfsReadOnly() { return this.pbfsHasFields && !this.pbfsData.editable; },
    get pbfsDirtyCount() { return Object.keys(this.pbfs.staged).length; },
    get pbfsDirtyText() {
        const n = this.pbfsDirtyCount;
        return n === 1 ? _t("1 unsaved change") : _t("%s unsaved changes", n);
    },
    get pbfsFilledText() {
        return _t("%(filled)s of %(total)s filled in", { filled: this.pbfsData.filled || 0, total: this.pbfsData.total || 0 });
    },
    /** 0..100 for the little meter in the tab header. */
    get pbfsPct() {
        const t = this.pbfsData.total || 0;
        return t ? Math.round((100 * (this.pbfsData.filled || 0)) / t) : 0;
    },
    get pbfsMeterStyle() { return `--pbfp-pct:${this.pbfsPct}`; },
    /** Empty state for the administrator: no field made yet, or none for
     *  this person's Country of Work / visible to this reader. */
    get pbfsNoneYet() { return !(this.pbfsData.custom_count || 0); },
    get pbfsCountryText() {
        const c = this.pbfsData.country;
        return c ? _t("None of the fields made so far apply to people whose Country of Work is %s.", c)
            : _t("This person has no Country of Work recorded, so only fields for all countries show here.");
    },
    get pbfsTabClass() { return { on: this.state.tab === TAB }; },

    // ---------------------------------------------------------- editing
    pbfsOnChange(name, value, display) {
        this.pbfs.staged[name] = { value, display };
        delete this.pbfs.errors[name];
    },
    pbfsDiscard() {
        this.pbfs.staged = {};
        this.pbfs.errors = {};
        this.pbfs.leaving = false;
        this._pbfsNext = null;
    },
    async pbfsSave() {
        if (this.pbfs.saving || !this.pbfsDirtyCount) { return false; }
        const vals = Object.fromEntries(Object.entries(this.pbfs.staged).map(([k, v]) => [k, v.value]));
        this.pbfs.saving = true;
        try {
            const res = await this.orm.call(PEOPLE, "pbfs_save_employee", [Number(this.props.empId), vals]);
            if (!res || !res.ok) {
                this.pbfs.errors = (res && res.errors) || {};
                const n = Object.keys(this.pbfs.errors).length;
                this.notif.add((res && res.error) || (n === 1 ? _t("1 detail needs a look before it can be saved.")
                    : _t("%s details need a look before they can be saved.", n)), { type: "danger" });
                return false;
            }
            this.pbfs.data = res.data || this.pbfs.data;
            this.pbfs.staged = {};
            this.pbfs.errors = {};
            this.notif.add(_t("Company details saved."), { type: "success" });
            return true;
        } catch (e) {
            this.notif.add(msgOf(e, _t("Saving did not work. Nothing was changed.")), { type: "danger" });
            return false;
        } finally {
            this.pbfs.saving = false;
        }
    },
    async pbfsReload() {
        try {
            const data = await this.orm.call(PEOPLE, "pbfs_employee_sections", [Number(this.props.empId)]);
            this.pbfs.data = data || null;
            // A field that left the screen takes its unsaved value with it.
            const names = new Set((this.pbfsSections || []).flatMap((s) => (s.fields || []).map((f) => f.name)));
            for (const k of Object.keys(this.pbfs.staged)) {
                if (!names.has(k)) { delete this.pbfs.staged[k]; delete this.pbfs.errors[k]; }
            }
        } catch {
            // the panel keeps what it shows; the next open reads it again
        }
    },

    // ---------------------------------------------------------- leaving
    /** Every way out of the panel asks first while changes are unsaved. */
    pbfsGuard(next) {
        if (!this.pbfsDirtyCount) { return next(); }
        this._pbfsNext = next;
        this.state.tab = TAB;
        this.pbfs.leaving = true;
    },
    pbfsRequestClose() { return this.pbfsGuard(() => this.close()); },
    pbfsStay() { this.pbfs.leaving = false; this._pbfsNext = null; },
    async pbfsSaveAndGo() {
        const next = this._pbfsNext;
        if (await this.pbfsSave()) {
            this.pbfs.leaving = false;
            this._pbfsNext = null;
            if (next) { next(); }
        }
    },
    pbfsLeaveWithout() {
        const next = this._pbfsNext;
        this.pbfsDiscard();
        if (next) { next(); }
    },
    openFull() { return this.pbfsGuard(() => super.openFull(...arguments)); },
    openContract(contractId, tab) { return this.pbfsGuard(() => super.openContract(contractId, tab)); },
    onKey(ev) {
        if (ev.key !== "Escape") { return super.onKey(ev); }
        if (this.pbfsStudio.state.open) { return; }
        if (ev.target && ev.target.closest && ev.target.closest(OWN_KEYS)) { return; }
        return this.pbfsRequestClose();
    },

    // ---------------------------------------------------------- the Studio
    pbfsOpenStudio() {
        const studio = this.pbfsStudio;
        if (!studio.state.canEdit || this._pbfsRemoveStudio) { return; }
        studio.state.open = true;
        this._pbfsRemoveStudio = this.overlay.add(FormStudioOverlay, {
            ...studio.overlayProps,
            onClose: () => this.pbfsCloseStudio(),
        });
    },
    pbfsCloseStudio() {
        const remove = this._pbfsRemoveStudio;
        this._pbfsRemoveStudio = null;
        if (remove) { remove(); }
        if (this.pbfsStudio) { this.pbfsStudio.state.open = false; }
    },
});

// ===================================================================
//  2. The employee full page (look-only)
// ===================================================================
PbEmployeeDetail.components = Object.assign({}, PbEmployeeDetail.components, { PbFieldGrid });

patch(PbEmployeeDetail.prototype, {
    setup() {
        super.setup(...arguments);
        // Only for the bus: a publish elsewhere re-reads this page.
        this.pbfsStudio = useFormStudio({
            hostKey: PBFS_PEOPLE_HOST,
            recordId: () => Number(this.empId) || false,
            onPublished: () => this.refresh(),
        });
    },
    pbfsIc(name, size = 15) { return fsIc(name, size); },
    get pbfsFull() { return (this.state.d && this.state.d.form_sections) || null; },
    get pbfsHas() { return Boolean(this.pbfsFull && this.pbfsFull.total); },
    get pbfsFilledText() {
        const d = this.pbfsFull || {};
        return _t("%(filled)s of %(total)s filled in", { filled: d.filled || 0, total: d.total || 0 });
    },
});

// ===================================================================
//  3. The publish sheet: say it once, plainly (ADDENDUM item 3)
// ===================================================================
patch(FormStudioOverlay.prototype, {
    get pbfpHasNewFields() { return Object.keys(this.state.creates || {}).length > 0; },
});
