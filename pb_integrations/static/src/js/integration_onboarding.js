/** @odoo-module **/
/**
 * `pb_integration_onboarding` — "Connect an HR system", as a flow.
 *
 * Flow doctrine 1: a stock Odoo modal becomes a full-screen stepped flow. The
 * modal it replaces (`hr.integration.onboarding.wizard`, `target=new`) is a
 * 30-field form with four `invisible="step != …"` groups stacked inside one
 * sheet and seven footer buttons, five of which are hidden at any moment. It
 * still exists, it is still registered, and nothing in Payobook opens it.
 *
 * What this is NOT is a second implementation. Every decision is still the
 * transient's: `pb.integration.onboarding` writes its fields, presses its
 * buttons, discards the `act_window` dicts they return and re-reads its state.
 * A fix to the vendor-template logic reaches this flow without anyone
 * remembering that this flow exists.
 *
 * Three rails worth stating:
 *
 *  1. **the mount READS, the buttons WRITE.** `onWillStart` calls `start()`,
 *     which creates a TRANSIENT and nothing else — no connector exists until a
 *     button is pressed. OWL restarts an in-flight mount whenever the parent
 *     re-renders (W21.1), so anything with a real side effect had to be out of
 *     there.
 *  2. **`state.busy` is the concurrency guard, not a uniqueness check.** The
 *     wizard's `_ensure_connector` creates a connector when it does not already
 *     have one. Two clicks in flight at once would both read an empty
 *     `connector_id`, in separate read-committed transactions where neither can
 *     see the other's row — a uniqueness guard cannot fix a concurrency problem
 *     (W21.1). So every step button is disabled while one is running, and every
 *     step call goes through `_run`.
 *  3. **no credential is ever read back.** The facade reports whether a key is
 *     set, never what it is. Typed values live in this component until they are
 *     written, and the inputs are `password` where they hold a secret.
 */
import { Component, useState, onWillStart, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack, openHub } from "@pb_hub/js/hub_nav";

const MODEL = "pb.integration.onboarding";

/** The four steps, in the order the transient's own `action_back` walks them. */
const STEPS = [
    { id: "vendor", label: _t("Choose the system") },
    { id: "auth", label: _t("Connect") },
    { id: "mappings", label: _t("Field mapping") },
    { id: "activate", label: _t("Confirm & test") },
];

/** Which auth inputs a method actually uses. Anything else is noise on screen. */
const AUTH_FIELDS = {
    oauth2: ["client_id", "client_secret"],
    api_key: ["api_key"],
    bearer: ["api_key"],
    basic: ["client_id", "client_secret"],
};

export class IntegrationOnboarding extends Component {
    static template = "pb_integrations.IntegrationOnboarding";
    static components = { HubBackChip };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");

        this.back = hubBack(this.props);

        this.state = useState({
            ready: false,
            busy: false,
            busyMsg: "",
            error: "",
            s: null,                       // the transient's state, from the server
            vendors: [], configs: [], authTypes: [],
            // Local edits. They are pushed to the transient on every step, so a
            // Back-then-Next round trip does not lose what was typed.
            form: { name: "", api_endpoint: "", auth_type: "oauth2",
                    api_key: "", client_id: "", client_secret: "",
                    connector_type: "", config_id: "" },
        });

        onWillStart(async () => { await this.begin(); });
    }

    ic(n, s = 16) { return ic(n, s); }
    get steps() { return STEPS; }
    get s() { return this.state.s || {}; }
    get stepIndex() { return this.s.step_index || 0; }
    get step() { return this.s.step || "vendor"; }

    /**
     * A PURE read on mount. `start()` creates the transient and nothing else.
     */
    async begin() {
        try {
            const d = await this.orm.call(MODEL, "start", []);
            this.state.vendors = d.vendors || [];
            this.state.configs = d.configs || [];
            this.state.authTypes = d.auth_types || [];
            this._absorb(d);
        } catch (e) {
            console.warn("pb_integrations: could not start the onboarding flow", e);
            this.state.error = _t("This flow could not be started.");
        } finally {
            this.state.ready = true;
        }
    }

    /** Server state in; the form's untyped fields follow it, secrets do not. */
    _absorb(d) {
        this.state.s = d;
        this.state.form.connector_type = d.connector_type || "";
        this.state.form.config_id = d.config_id ? String(d.config_id) : "";
        this.state.form.name = d.name || "";
        this.state.form.api_endpoint = d.api_endpoint || "";
        this.state.form.auth_type = d.auth_type || "oauth2";
    }

    // -------------------------------------------------------------- one runner
    /**
     * Every step call goes through here, so "busy" and "one at a time" are
     * properties of the flow rather than of each handler.
     *
     * The error is REPORTED and left on screen (W40): a connection test that
     * failed is a normal outcome of step 2 and its message is the whole reason
     * the button exists.
     */
    async _run(method, args, msg) {
        if (this.state.busy) { return; }
        this.state.busy = true;
        this.state.busyMsg = msg || _t("Working…");
        this.state.error = "";
        try {
            const d = await this.orm.call(MODEL, method, args);
            this._absorb(d);
            if (d.error) {
                this.state.error = d.error;
                this.notif.add(d.error, { type: "warning" });
            }
            return d;
        } catch (e) {
            const m = (e && e.data && e.data.message)
                || (e && e.message && e.message.toString())
                || _t("That step could not be completed.");
            this.state.error = m;
            this.notif.add(m, { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    /** The whole form, minus anything the user has not typed. */
    _vals() {
        const f = this.state.form;
        const vals = {
            connector_type: f.connector_type,
            name: f.name,
            api_endpoint: f.api_endpoint,
            auth_type: f.auth_type,
        };
        if (f.config_id) { vals.config_id = Number(f.config_id); }
        // Secrets are sent only when this session typed one — an empty box must
        // never blank a credential the connector already holds.
        for (const k of ["api_key", "client_id", "client_secret"]) {
            if (f[k]) { vals[k] = f[k]; }
        }
        return vals;
    }

    onField(field, ev) { this.state.form[field] = ev.target.value; }
    pickVendor(id) { this.state.form.connector_type = id; }

    /**
     * Is this the selected configuration?
     *
     * A METHOD, because an OWL template expression is compiled against the
     * component's context and NOTHING else — `String(c.id)` in the template
     * became `ctx.String(c.id)` and the whole flow died at mount with
     * "ctx.String is not a function". There is no lint for that and no test
     * short of rendering it: an OWL template error surfaces only at runtime
     * (C18.71/W10), which is why the live pass exists.
     *
     * `==` rather than `===` on purpose: the form holds the id as a string
     * (a `<select>` value always is) and the payload holds it as a number.
     */
    isConfig(id) { return this.state.form.config_id == id; }

    get authFields() { return AUTH_FIELDS[this.state.form.auth_type] || []; }
    usesField(name) { return this.authFields.includes(name); }

    get canContinue() { return !!this.state.form.connector_type && !this.state.busy; }

    // ---------------------------------------------------------------- the steps
    chooseVendor() {
        if (!this.canContinue) { return; }
        return this._run("choose_vendor", [this.s.wizard_id, this._vals()],
                         _t("Setting up…"));
    }
    goBack() { return this._run("back", [this.s.wizard_id], _t("Going back…")); }
    testConnection() {
        return this._run("test_connection", [this.s.wizard_id, this._vals()],
                         _t("Testing the connection…"));
    }
    applyTemplate() {
        return this._run("apply_template", [this.s.wizard_id, this._vals()],
                         _t("Loading the field template…"));
    }
    testMappings() {
        return this._run("test_mappings", [this.s.wizard_id],
                         _t("Testing the mappings against a real payload…"));
    }
    toActivate() {
        return this._run("to_activate", [this.s.wizard_id], _t("Almost there…"));
    }
    async finish() {
        const d = await this._run("finish", [this.s.wizard_id],
                                  _t("Activating the connector…"));
        if (d && d.done) {
            this.notif.add(_t("%s is connected and active.",
                              d.connector_name || _t("The connector")),
                           { type: "success" });
        }
    }

    // ----------------------------------------------------------------- summary
    /**
     * The vendor's setup guide, as markup.
     *
     * `t-out` escapes a plain string, so without this the user reads literal
     * `<b>` and `<code>` tags rather than a formatted instruction — which is
     * how the modal's `alert-info` block renders today, and the reason it is
     * worth stating that this is deliberate rather than lax: the value is a
     * MODULE CONSTANT (`HrIntegrationOnboardingWizard._GUIDE`) keyed by a
     * Selection value. No user, tenant or API payload can reach it.
     */
    get guideHtml() { return markup(this.s.guide || ""); }

    /** One sentence, one msgid (W80) — and it carries two numbers. */
    get mappingSummary() {
        const a = this.s.applied_count || 0;
        const g = this.s.suggested_count || 0;
        if (!a && !g) { return _t("No field template matched this system yet."); }
        return _t("%(applied)s field(s) mapped automatically, %(suggested)s need "
                  + "review before they are used.", { applied: a, suggested: g });
    }

    get moreMappings() {
        const total = this.s.mapping_total || 0;
        const shown = (this.s.mappings || []).length;
        return total > shown
            ? _t("…and %s more on the connector.", total - shown) : "";
    }

    stateTone(st) {
        return { active: "ok", suggested: "warn", ignored: "muted" }[st] || "muted";
    }

    // ------------------------------------------------------------------- doors
    /**
     * Leave the flow.
     *
     * `back` is whatever sent us here (Integrations, today). Falling back to the
     * Integrations cockpit rather than to nothing means an abandoned flow always
     * lands somewhere real — a wizard whose Cancel does nothing is a trap.
     */
    close() {
        if (this.back) {
            openHub(this.action, {
                tag: this.back.tag, xmlid: this.back.xmlid,
                lens: this.back.lens, lensKey: this.back.lensKey,
                context: this.back.context || {},
            });
            return;
        }
        openHub(this.action, { tag: "pb_integrations" });
    }

    /** The terminal door: the connector's own cockpit, not the native form. */
    openConnector() {
        const id = this.s.connector_id;
        if (!id) { return this.close(); }
        this.action.doAction({
            type: "ir.actions.client", tag: "pb_import_connector_cockpit",
            name: "Connector",
            params: { connector_id: id,
                      back_to: "pb_integrations.action_pb_integrations",
                      back_label: _t("Integrations") },
        });
    }
}

registry.category("actions").add("pb_integration_onboarding", IntegrationOnboarding);
