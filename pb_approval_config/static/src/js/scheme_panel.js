/** @odoo-module **/
/**
 * `<ApprovalSchemePanel/>` — "what approval does this place use?", reusable.
 *
 * THE ONE CARD THAT ANSWERS THE QUESTION WHEREVER IT IS ASKED. It is mounted
 * here from the Matrix (a row's "Where it applies"), and Phase 3 mounts exactly
 * this component, with exactly these props, inside the guided setup's Connect
 * step and beside a pay scheme's own settings. There is deliberately one
 * implementation: an approval card that disagrees with the Matrix about who
 * signs a pay run off is worse than no card at all.
 *
 * THREE PLAIN ANSWERS: use the company flow, choose another existing flow, or
 * require no approval. The backend still records whether an explicitly chosen
 * flow is shared or unique; that implementation detail is not a user choice.
 *
 * "WHAT WILL HAPPEN" IS NOT DECORATION. A narrower place inside this one can
 * have an exception of its own, and the most specific always wins. The panel
 * lists those exceptions under the choice, so nobody reads "Inherited" and
 * concludes that every division below it inherits too.
 *
 * PROPS — the contract Phase 3 builds against:
 *   processKey   (String,  required) the process this card is about
 *   scopeKey     (String,  optional) the place, '' meaning the whole company
 *   scopeLabel   (String,  optional) what to call that place on screen
 *   companyId    (Number,  optional) which company; the reader's own by default
 *   embedded     (Boolean, optional) draw without the card's own heading
 *   onOpenMatrix (Function,optional) the door to the full Matrix, if there is one
 */
import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

export class ApprovalSchemePanel extends Component {
    static template = "pb_approval_config.ApprovalSchemePanel";
    static props = {
        processKey: { type: String },
        scopeKey: { type: String, optional: true },
        scopeLabel: { type: String, optional: true },
        companyId: { type: Number, optional: true },
        embedded: { type: Boolean, optional: true },
        onOpenMatrix: { type: Function, optional: true },
    };

    setup() {
        this.ic = ic;
        this.orm = useService("orm");
        this.notif = useService("notification");

        this.state = useState({
            loading: true,
            failed: "",
            data: null,
            changing: false,
            choice: "inherit",
            workflowId: 0,
            busy: false,
        });

        onWillStart(async () => { await this.load(this.props); });
        onWillUpdateProps(async (next) => {
            if (next.processKey !== this.props.processKey
                    || next.scopeKey !== this.props.scopeKey
                    || next.companyId !== this.props.companyId) {
                await this.load(next);
            }
        });
    }

    async load(props) {
        this.state.loading = true;
        this.state.failed = "";
        try {
            const data = await this.orm.call(
                "pb.approval.matrix", "get_scheme_panel",
                [props.processKey, props.scopeKey || "",
                 props.companyId || false]);
            this.state.data = data;
            this.state.choice = ["shared", "custom"].includes(data.selection)
                ? "route" : data.selection;
            this.state.workflowId = data.workflow_id || 0;
        } catch (error) {
            this.state.failed = (error.data && error.data.message)
                || _t("The approvals for this could not be read.");
        } finally {
            this.state.loading = false;
        }
    }

    get data() { return this.state.data || {}; }

    get scopeLabel() {
        return this.props.scopeLabel || this.data.scope_label || "";
    }

    get badge() {
        return {
            inherit: { tone: "info", label: _t("Same as the rest of the company") },
            shared: { tone: "blue", label: _t("Shared with other places") },
            custom: { tone: "green", label: _t("Only for here") },
            none: { tone: "muted", label: _t("No approval required") },
        }[this.data.selection] || { tone: "muted", label: "" };
    }

    get choices() {
        return [
            { key: "inherit",
              title: _t("Use the company flow"),
              sub: _t("This scheme follows future company-wide changes automatically."),
              warn: "" },
            { key: "route",
              title: _t("Use a different flow for this scheme"),
              sub: _t("Choose an existing flow below."),
              warn: "" },
            { key: "none",
              title: _t("No approval required"),
              sub: _t("Scheme changes take effect without waiting for an approver. The change is still recorded."),
              warn: "" },
        ];
    }

    /** Every route this place could be pointed at. */
    get options() {
        return (this.data.choices || []).filter(
            (one) => one.workflow_id !== 0 && !one.is_no_approval);
    }

    get canSave() {
        if (!this.data.can_config) { return false; }
        if (["inherit", "none"].includes(this.state.choice)) { return true; }
        return Boolean(this.state.workflowId);
    }

    /** The whole-company card cannot point at itself; only a narrower one can. */
    get editable() {
        return Boolean(this.data.can_config && (this.props.scopeKey || ""));
    }

    toggleChange() {
        this.state.changing = !this.state.changing;
        if (this.state.changing) {
            this.state.choice = ["shared", "custom"].includes(this.data.selection)
                ? "route" : this.data.selection;
            this.state.workflowId = this.data.workflow_id || 0;
        }
    }

    setChoice(key) { this.state.choice = key; }

    setWorkflow(ev) {
        this.state.workflowId = Number(ev.target.value || 0);
    }

    async save() {
        this.state.busy = true;
        try {
            this.state.data = await this.orm.call(
                "pb.approval.matrix", "set_scheme_binding",
                [this.props.processKey, this.props.scopeKey || "",
                 this.state.choice === "route" ? "custom" : this.state.choice,
                 this.state.workflowId || false,
                 this.props.companyId || false, this.data.revision]);
            this.state.changing = false;
            this.notif.add(
                _t("Saved. New requests from here use this; anything already under way keeps its route."),
                { type: "success" });
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                || _t("That could not be saved."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    openMatrix() {
        if (this.props.onOpenMatrix) {
            this.props.onOpenMatrix(this.data.process_key,
                                    this.data.workflow_id || 0);
        }
    }
}
