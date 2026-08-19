/** @odoo-module **/
/**
 * `pb_pay_hub` — the Pay Run mission, on Cycle 1's HubShell.
 *
 * Eight surfaces that used to be eight rail items become eight lenses of one
 * workspace, in the order the IA mockup specifies:
 *
 *     run · runs · payslips · results · import · deliver · adjust · settle
 *
 * Every lens is the EXISTING cockpit, mounted with `embedded: true` — one
 * component, one facade, two mount points (W17). Nothing here reimplements a
 * cockpit, nothing here forks one, and every standalone client action still
 * works, because the hub is additive until the rail cutover in Cycle 5.
 *
 * The two things the hub adds that no lens could add for itself:
 *
 *   1. **the escapes are closed.** The wizard's terminal CTA used to dump the
 *      user on a native `hr.payslip.run` form; here it switches to the Runs
 *      lens with the new run focused. The ledgers' "Open full list →" used to
 *      leave for a native list; in a hub they are an in-lens ledger with a
 *      320px drawer and that link is not rendered at all.
 *   2. **the period tracker** — one server read (`pb.pay.hub.get_period_state`)
 *      that says where this month's payroll actually is, and a click that lands
 *      on the lens where the outstanding work lives.
 *
 * `config` is built ONCE per instance, never in a getter: HubShell's `config`
 * prop must keep a stable identity or every render recreates every lens (the
 * refetch trap, W21).
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { HubShell } from "@pb_hub/js/hub_shell";
import { openHub } from "@pb_hub/js/hub_nav";

import { PayrunWizard } from "@pb_payrun_wizard/js/payrun_wizard";
import { PbPayruns } from "@pb_payruns/js/payruns";
import { PayslipReview } from "@pb_payslip_review/js/payslip_review";
import { PbPayrunResults } from "@pb_payrun_results/js/payrun_results";
import { PbImport } from "@pb_import/js/import";
import { PbPayDelivery } from "@pb_pay_delivery/js/pb_pay_delivery";
import { LedgerCockpit } from "@pb_payrun_ledgers/js/ledger";

/**
 * Which lens the tracker's click should land on, per stage.
 *
 * The chip answers "where is this month", so the door answers "and where is
 * the work". Stage 1 has no run, so it opens the wizard; stage 2 has a draft
 * waiting to be submitted and stage 5 is finished, so both open the board.
 */
const STAGE_LENS = { 1: "run", 2: "runs", 3: "payslips", 4: "deliver", 5: "runs" };

export class PbPayHub extends Component {
    static template = "pb_payhub.PbPayHub";
    static components = { HubShell };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.actionService = useService("action");

        // The tracker is the only piece of the config that is DATA, so it is
        // the only piece kept in state. Everything else is declaration.
        this.state = useState({ period: null });

        this.config = {
            key: "pay",                       // -> pbhub.pay.lens.v1
            brand: { label: _t("Pay Run"), icon: "zap" },
            defaultLens: "runs",
            tracker: this.tracker,
            lenses: [
                {
                    key: "run", icon: "zap", label: _t("Run"),
                    Component: PayrunWizard,
                    props: { onOpenRun: (id) => this.openRunInHub(id) },
                },
                {
                    key: "runs", icon: "calendar", label: _t("Runs"),
                    Component: PbPayruns,
                    // the wizard hands over a run id through arrival.focus
                    wantsArrival: true,
                    props: { onRunPayroll: () => this.setLens("run") },
                },
                { key: "payslips", icon: "receipt", label: _t("Payslips"),
                  Component: PayslipReview },
                { key: "results", icon: "table", label: _t("Results"),
                  Component: PbPayrunResults },
                { key: "import", icon: "download", label: _t("Import"),
                  Component: PbImport },
                { key: "deliver", icon: "send", label: _t("Deliver"),
                  Component: PbPayDelivery },
                {
                    // TWO descriptors in ONE lens: retro and proration are the
                    // same question asked about two tables, and an officer
                    // reconciling a month reads them together.
                    key: "adjust", icon: "percent", label: _t("Adjust"),
                    Component: LedgerCockpit,
                    props: {
                        tabs: [
                            { key: "retro", label: _t("Retro"), icon: "rotate",
                              model: "pb.retro" },
                            { key: "proration", label: _t("Proration"),
                              icon: "sigma", model: "pb.proration" },
                        ],
                    },
                },
                {
                    key: "settle", icon: "file", label: _t("Settle"),
                    Component: LedgerCockpit,
                    // One descriptor, still declared as `tabs`: it is what
                    // routes the model, and the strip renders only past one tab.
                    props: {
                        tabs: [{ key: "fullfinal", label: _t("Full & Final"),
                                 icon: "file", model: "pb.fullfinal" }],
                    },
                },
            ],
        };

        onWillStart(async () => { await this.loadPeriod(); });
    }

    // ------------------------------------------------------------- the period
    /**
     * A READ, in a mount hook, that writes only THIS component's own state.
     *
     * The rule W21 exists for is about a child writing its HOST's state during
     * the host's render fiber. This IS the host, and `state.period` is its own;
     * the tracker object handed to the shell reads through a getter, so the
     * shell sees the new numbers on the next render without anyone calling
     * back up.
     */
    async loadPeriod() {
        try {
            this.state.period = await this.orm.call("pb.pay.hub", "get_period_state", []);
        } catch (e) {
            // Reported, never swallowed into a decoration (W40). A hub whose
            // tracker failed still opens; it simply does not claim a stage.
            console.warn("pb_payhub: could not read the period state", e);
            this.state.period = null;
        }
    }

    /**
     * Stable identity, live numbers.
     *
     * The object handed to HubShell is created ONCE (in `config`) and its
     * fields are getters onto `state.period`, so the chip updates when the read
     * lands without the shell's `config` prop ever changing identity.
     */
    get tracker() {
        const self = this;
        return {
            get label() {
                return self.state.period ? self.state.period.label : _t("This month");
            },
            get stage() { return self.state.period ? self.state.period.stage : 0; },
            get total() { return self.state.period ? self.state.period.total : 0; },
            onClick: () => this.onTrackerClick(),
        };
    }

    /** A CLICK handler — the only place in this file that changes a lens. */
    onTrackerClick() {
        const p = this.state.period;
        if (!p) { return; }
        this.notif.add(p.stage_label, { type: "info" });
        this.setLens(STAGE_LENS[p.stage] || "runs");
    }

    // ------------------------------------------------------------ lens switch
    /**
     * Switch lens from OUTSIDE the shell.
     *
     * The shell owns `state.lens` and persists it; reaching into it from here
     * would be two owners for one fact. So the hub re-enters itself through the
     * arrival protocol, which is the door the shell already reads
     * (`pb_lens`, hub_nav.js) — the same mechanism the palette's per-lens
     * entries use, so there is exactly one way a lens is chosen remotely.
     */
    setLens(lens, focus) {
        openHub(this.actionService, {
            xmlid: "pb_payhub.action_pb_pay_hub",
            lens,
            focus: focus ? String(focus) : undefined,
        });
    }

    /** The wizard's terminal CTA: stay in the hub, land on the new run. */
    openRunInHub(runId) { this.setLens("runs", runId); }
}

registry.category("actions").add("pb_pay_hub", PbPayHub);
