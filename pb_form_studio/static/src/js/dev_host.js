/** @odoo-module **/
/**
 * The dev-only test screen (host `pbfs_sample`): the smallest REAL host, and
 * the worked example of THE HOST CONTRACT.
 *
 * Not on any menu. Opened by its tag (`pb_form_dev_host`) in developer mode by
 * the administrator; anybody else gets one plain sentence. It does exactly
 * what a real host must repeat:
 *   1. `useFormStudio({hostKey, recordId, onPublished})` + `<FormStudioWand/>`
 *      + `<FormStudioOverlay t-if="studio.state.open" t-props=…/>`;
 *   2. `render(host_key, record_id)` → `<PbFieldGrid sections=…/>`, with the
 *      host's own locked sections passed as slots;
 *   3. edits staged by the grid, saved through `write_values`, field errors
 *      shown in place, then re-rendered;
 *   4. reload on publish (own and other people's, through the bus).
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { fsIc } from "./fs_icons";
import { FACADE } from "./fs_words";
import { PbFieldGrid } from "./field_grid";
import { FormStudioOverlay } from "./studio_overlay";
import { useFormStudio, FormStudioWand } from "./use_form_studio";

const HOST = "pbfs_sample";
const MODEL = "pb.form.sample";

export class FormStudioDevHost extends Component {
    static template = "pb_form_studio.DevHost";
    static components = { PbFieldGrid, FormStudioOverlay, FormStudioWand };
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ allowed: false, loading: true, recordId: 0, data: null,
                                staged: {}, errors: {}, saving: false, error: "" });
        this.studio = useFormStudio({
            hostKey: HOST,
            recordId: () => this.state.recordId,
            onPublished: () => this.reload(),
        });
        onWillStart(async () => {
            const debug = Boolean(this.env.debug);
            const allowed = debug && Boolean(await this.orm.call(FACADE, "can_edit", [HOST]));
            this.state.allowed = allowed;
            if (allowed) {
                this.state.recordId = await this.orm.call(FACADE, "dev_sample", []);
                await this.reload();
            }
            this.state.loading = false;
        });
    }

    ic(n, s = 16) { return fsIc(n, s); }
    get model() { return MODEL; }

    async reload() {
        try {
            this.state.data = await this.orm.call(FACADE, "render", [HOST, this.state.recordId]);
            this.state.staged = {};
            this.state.errors = {};
            this.state.error = "";
        } catch (e) {
            this.state.error = (e && e.data && e.data.message) || _t("The record could not be read.");
        }
    }

    get sections() { return (this.state.data && this.state.data.sections) || []; }
    get currency() { return (this.state.data && this.state.data.currency) || ""; }
    get name() {
        for (const s of this.sections) {
            for (const f of s.fields) { if (f.name === "name") { return f.display; } }
        }
        return "";
    }
    get initials() { return (this.name || "?").split(/\s+/).filter(Boolean).slice(-2).map((w) => w[0]).join("").toUpperCase(); }
    get dirtyCount() { return Object.keys(this.state.staged).length; }
    get dirtyText() { return this.dirtyCount === 1 ? _t("1 unsaved change") : _t("%s unsaved changes", this.dirtyCount); }

    onChange(name, value, display) {
        this.state.staged[name] = { value, display };
        delete this.state.errors[name];
    }
    discard() { this.state.staged = {}; this.state.errors = {}; }
    async save() {
        const vals = Object.fromEntries(Object.entries(this.state.staged).map(([k, v]) => [k, v.value]));
        this.state.saving = true;
        try {
            const res = await this.orm.call(FACADE, "write_values", [MODEL, this.state.recordId, vals]);
            if (!res.ok) {
                this.state.errors = res.errors || {};
                if (res.error) { this.notification.add(res.error, { type: "danger" }); }
                return;
            }
            this.notification.add(_t("Saved."), { type: "success" });
            await this.reload();
        } finally {
            this.state.saving = false;
        }
    }
}

registry.category("actions").add("pb_form_dev_host", FormStudioDevHost);
