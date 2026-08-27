/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.import.sync.wizard";
const STEPS = [_t("Configure"), _t("Preview"), _t("Done")];

export class SyncWizard extends Component {
    static template = "pb_import_advanced.SyncWizard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        const p = (this.props.action && (this.props.action.params || this.props.action.context)) || {};
        this.connectorId = p.connector_id || p.active_id;
        this.state = useState({
            step: 1, loading: false, busyMsg: "", defaults: null, summary: null,
            form: { connector_id: this.connectorId, date_from: "", date_to: "",
                    max_records: "", run_transformations: true,
                    pull_employee: true, pull_salary: true, pull_dependent: true,
                    pull_attendance: true, pull_leave: true },
        });
        onWillStart(async () => {
            const d = await this.orm.call(MODEL, "get_defaults", [this.connectorId]);
            this.state.defaults = d;
            this.state.form.connector_id = d.connector_id || this.connectorId;
            this.state.form.date_from = d.date_from;
            this.state.form.date_to = d.date_to;
        });
    }

    ic(n, s = 16) { return ic(n, s); }
    get steps() { return STEPS; }
    onField(f, ev) { this.state.form[f] = ev.target.value; }
    toggle(f) { this.state.form[f] = !this.state.form[f]; }

    async _run(promise, msg, nextStep) {
        this.state.loading = true; this.state.busyMsg = msg;
        try {
            const res = await promise;
            this.state.summary = res;
            if (res.error) this.notif.add(res.error, { type: "warning" });
            else if (nextStep) this.state.step = nextStep;
        } catch (e) {
            this.notif.add((e && e.message && e.message.toString()) || _t("Step failed."), { type: "danger" });
        } finally { this.state.loading = false; }
    }
    toPreview() { return this._run(this.orm.call(MODEL, "create_and_preview", [this.state.form]), "Building preview…", 2); }
    doPull() { return this._run(this.orm.call(MODEL, "do_pull", [this.state.summary.wizard_id]), "Pulling data…", 3); }

    back() { if (this.state.step > 1) this.state.step -= 1; }
    close() {
        if (this.connectorId) {
            this.action.doAction({ type: "ir.actions.client", tag: "pb_import_connector_cockpit",
                                   name: "Connector", params: { connector_id: this.connectorId } });
        } else {
            this.action.doAction("pb_import.action_pb_import", { clearBreadcrumbs: true });
        }
    }
}

registry.category("actions").add("pb_import_sync_wizard", SyncWizard);
