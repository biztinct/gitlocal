/** @odoo-module **/

import { Component, useState, onWillStart, onWillUpdateProps, onWillUnmount,
         useRef, useEffect } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { openHub } from "@pb_hub/js/hub_nav";

import { STEP_META } from "./blueprint_steps";
import {
    statusPill, statusHint, coverageLine, payslipLine, changedLine, removedLine,
    manageLater, canMarkDone, connectProgress,
} from "./connect_text";

/**
 * Step 3 — Connect: where the numbers come from, and where they land.
 *
 * Three cards, and the whole design rests on one idea: **the tools already
 * exist**. This step does not rebuild the mapping screen or the payslip
 * designer — it opens them ON THIS DRAFT, with a way back, and then reports in
 * plain numbers what came of it ("12 of 19 inputs have a source", "31 of 38
 * components placed · 7 in the tray"). The third card is honest information: pay
 * runs already follow an approval chain, this step does not change it, and
 * saying so is better than a button that pretends.
 *
 * Every task can be skipped and un-skipped, and skipping weakens nothing: the
 * card says where to find the same tool later, because the commonest fear at
 * this point in a setup is that "not now" means "never".
 */
export class StepConnect extends Component {
    static template = "pb_blueprint.StepConnect";
    static props = {
        configId: { type: [Number, Boolean] },
        configName: { type: String, optional: true },
        configCode: { type: String, optional: true },
        company: { type: String, optional: true },
        revision: { type: Number, optional: true },
        reloadKey: { type: Number, optional: true },
        // Which card to ring on arrival — set when a studio sent us back.
        highlight: { type: String, optional: true },
        onRevision: { type: Function },
        onGrid: { type: Function },
        onContinue: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");

        this.state = useState({
            loading: true,
            error: "",
            data: null,
            busy: "",              // the task key a call is running for
            ring: this.props.highlight || "",
            howOpen: false,        // "How approvals work today"
        });

        this._ringTimer = null;
        this.howRef = useRef("how");

        onWillStart(async () => {
            await this.load();
            this.state.loading = false;
            this._fadeRing();
        });

        onWillUpdateProps(async (next) => {
            if (next.reloadKey !== this.props.reloadKey) {
                await this.load();
            }
            if (next.highlight && next.highlight !== this.props.highlight) {
                this.state.ring = next.highlight;
                this._fadeRing();
            }
        });

        // A hand-built modal is not a framework Dialog: nothing claims focus,
        // so Escape reaches nothing and a keyboard user cannot dismiss it
        // (BP20). It takes focus on mount and handles its own keys.
        useEffect(
            (el) => { if (el) { el.focus(); } },
            () => [this.howRef.el]
        );

        onWillUnmount(() => {
            if (this._ringTimer) { clearTimeout(this._ringTimer); }
        });
    }

    ic(name, size = 16) { return ic(name, size); }

    get meta() { return STEP_META.connect; }

    /** The purple ring that says "this is the card you just came back from". */
    _fadeRing() {
        if (!this.state.ring) { return; }
        if (this._ringTimer) { clearTimeout(this._ringTimer); }
        this._ringTimer = setTimeout(() => { this.state.ring = ""; }, 1400);
    }

    async rpc(method, args) {
        try {
            return await this.orm.call("pb.blueprint.studio", method, args || []);
        } catch (e) {
            const reason = (e && e.data && e.data.message) || (e && e.message) || "";
            this.notif.add(reason || _t("The server could not be reached."),
                           { type: "danger" });
            return { ok: false, reason };
        }
    }

    async load() {
        const res = await this.rpc("bp_readiness", [this.props.configId]);
        if (!res || !res.ok) {
            this.state.error = (res && res.reason)
                || _t("What is connected could not be read. Reload the page to try again.");
            return;
        }
        this.state.error = "";
        this.state.data = res;
        if (res.revision !== undefined) { this.props.onRevision(res.revision); }
    }

    // ==================================================================
    // Reading
    // ==================================================================
    get data() { return this.state.data || {}; }
    get editable() { return !!this.data.editable; }

    get progressLine() {
        const p = connectProgress(this.data.status || {});
        if (p.done === p.total) {
            return _t("Both tasks are done. Nothing here is holding you up.");
        }
        return _t("%(done)s of %(total)s tasks done. Neither one has to be finished before you carry on.",
                  { done: p.done, total: p.total });
    }

    /** The three cards, built once per render from the server's own numbers. */
    get cards() {
        const d = this.data;
        const status = d.status || {};
        const mapping = d.mapping || {};
        const payslip = d.payslip || {};
        const doors = d.doors || {};
        const mappingDoor = doors.mapping || {};
        const payslipDoor = doors.payslip || {};
        return [
            {
                key: "mapping",
                icon: "arrowLeftRight",
                title: _t("Source mapping"),
                lead: _t("Connect a payroll system, spreadsheets or employee records to the inputs of this configuration."),
                sub: _t("Anything you do not connect can still be typed in, or imported, on the pay run itself."),
                coverage: coverageLine(mapping),
                status: status.mapping || "not_started",
                pill: statusPill(status.mapping || "not_started"),
                hint: statusHint(status.mapping || "not_started", mapping.mapped),
                changed: changedLine("mapping", mapping.changed_since),
                removed: "",
                cta: _t("Open source mapping"),
                available: !!mappingDoor.available
                    && registry.category("actions").contains("pb_mapping_studio"),
                selectable: mappingDoor.selectable !== false,
                blocked: mappingDoor.reason || _t(
                    "The mapping screen is not installed on this database, so there is nothing to open. Everything else on this step still works."),
                canDone: canMarkDone("mapping", d),
                later: manageLater("mapping"),
                unmapped: mapping.unmapped || [],
                unmappedMore: mapping.unmapped_more || 0,
            },
            {
                key: "payslip",
                icon: "layoutList",
                title: _t("Payslip layout"),
                lead: _t("Place the components on the payslip, name the sections, choose which values people see."),
                sub: _t("A component with nowhere to go sits in the tray until you put it somewhere — it is never lost."),
                coverage: payslipLine(payslip),
                status: status.payslip || "not_started",
                pill: statusPill(status.payslip || "not_started"),
                hint: statusHint(status.payslip || "not_started", payslip.placed),
                changed: changedLine("payslip", payslip.changed_since),
                removed: removedLine(payslip.removed_placed),
                cta: _t("Open payslip designer"),
                available: !!payslipDoor.available
                    && registry.category("actions").contains("pb_formula_studio"),
                selectable: true,
                blocked: _t("The payslip designer is not installed on this database, so there is nothing to open. Everything else on this step still works."),
                canDone: canMarkDone("payslip", d),
                later: manageLater("payslip"),
                unmapped: payslip.tray_names || [],
                unmappedMore: payslip.tray_more || 0,
            },
        ];
    }

    get approvals() { return this.data.approvals || { tiers: [] }; }

    get approvalsPill() { return statusPill("info"); }

    get approvalsText() {
        return _t("Pay runs already follow Officer → HR → Finance approval. Custom approval rules per configuration are coming in a later release.");
    }

    get approvalsLater() { return manageLater("approvals"); }

    /** The identity strip: which company, and which configuration. */
    get identity() {
        const cfg = this.data.config || {};
        return {
            company: cfg.company || this.props.company || "",
            name: cfg.name || this.props.configName || "",
            code: cfg.code || this.props.configCode || "",
        };
    }

    ringed(key) { return this.state.ring === key; }

    // ==================================================================
    // Doors
    // ==================================================================
    /** The way back into this journey, from whichever tool we open. */
    _back(task) {
        return {
            label: _t("New configuration"),
            tag: "pb_blueprint",
            context: {
                config_id: this.props.configId,
                step: "connect",
                task: task,
            },
        };
    }

    async openMapping() {
        const card = this.cards[0];
        if (!card.available || !card.selectable) { return; }
        this.state.busy = "mapping";
        await this.rpc("bp_task_open", [this.props.configId, "mapping"]);
        this.state.busy = "";
        // BY TAG, never by xmlid: opened by xmlid the URL becomes
        // `/odoo/action-<id>` and every extra parameter is dropped, so the way
        // back would land on an empty journey (BP14).
        openHub(this.action, {
            tag: "pb_mapping_studio",
            context: { pb_config: this.props.configId, pb_mode: "journey" },
            back: this._back("mapping"),
        });
    }

    async openPayslip() {
        const card = this.cards[1];
        if (!card.available) { return; }
        this.state.busy = "payslip";
        await this.rpc("bp_task_open", [this.props.configId, "payslip"]);
        this.state.busy = "";
        this.action.doAction({
            type: "ir.actions.client",
            tag: "pb_formula_studio",
            target: "current",
            params: { config_id: this.props.configId, pbfs_open_payslip: true },
            context: { config_id: this.props.configId, pbfs_open_payslip: true },
        }, {
            additionalContext: { pb_back: this._back("payslip") },
            clearBreadcrumbs: true,
        });
    }

    // ==================================================================
    // The status machine
    // ==================================================================
    async setStatus(task, status) {
        this.state.busy = task;
        const res = await this.rpc("bp_task_set", [this.props.configId, task, status]);
        this.state.busy = "";
        if (!res || !res.ok) {
            this.notif.add((res && res.reason) || _t("That could not be changed."),
                           { type: "warning", sticky: true });
            return;
        }
        this.state.data = res;
        if (res.revision !== undefined) { this.props.onRevision(res.revision); }
        if (status === "configured") {
            this.notif.add(_t("Marked as done."), { type: "success" });
        }
    }

    async skipRest() {
        this.state.busy = "rest";
        const res = await this.rpc("bp_skip_rest", [this.props.configId]);
        this.state.busy = "";
        if (!res || !res.ok) {
            this.notif.add((res && res.reason) || _t("Nothing could be skipped."),
                           { type: "warning" });
            return;
        }
        this.state.data = res;
        if (res.revision !== undefined) { this.props.onRevision(res.revision); }
        const n = (res.skipped || []).length;
        this.notif.add(
            n ? _t("%s task skipped for now. You can come back to it any time.", n)
              : _t("Nothing was left to skip."),
            { type: "info" });
        this.props.onContinue();
    }

    // ==================================================================
    // "How approvals work today"
    // ==================================================================
    openHow() { this.state.howOpen = true; }
    closeHow() { this.state.howOpen = false; }

    onModalKey(ev) {
        // Enter inside this panel belongs to the panel, not to the journey's
        // "continue" (BP20); Escape closes it rather than reaching nothing.
        if (ev.key === "Escape") { ev.stopPropagation(); this.closeHow(); }
        if (ev.key === "Enter") { ev.stopPropagation(); }
    }

    onKeydown(ev) {
        if (ev.key === "Enter") { ev.stopPropagation(); }
    }
}
