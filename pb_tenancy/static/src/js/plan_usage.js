/** @odoo-module **/
/**
 * Plan & usage — what this company pays for, and what it has used.
 *
 * THE QUESTION IT ANSWERS. "How many people are we being charged for, how close
 * are we to our limit, and where is last month's invoice?" Until now the only
 * answer to any of those was to email us.
 *
 * EVERYTHING ON IT IS ALREADY HERE. The counts are two queries on this
 * database; the invoice list and the PDFs were pushed onto this database when
 * the invoice was sent. Nothing on this page needs the platform to be
 * reachable — which is exactly the morning somebody goes looking for an
 * invoice.
 *
 * ZERO DEAD ENDS. A company the platform has not put on a plan yet does not see
 * an empty screen: it sees its own counts and a sentence saying a plan has not
 * been set. A company with no invoices yet is told when the first one will
 * arrive.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
import { _t } from "@web/core/l10n/translation";

/** The words on an invoice's chip, and the colour it wears. */
const INVOICE_STATE = {
    sent: ["info", _t("Waiting for payment")],
    paid: ["ok", _t("Paid")],
    overdue: ["err", _t("Overdue")],
    void: ["muted", _t("Cancelled")],
    draft: ["muted", _t("Not sent")],
};

/** "3 September 2026" — the day, in the reader's locale. */
export function longDate(iso) {
    if (!iso) { return ""; }
    const d = new Date(String(iso).length <= 10 ? `${iso}T00:00:00` : iso);
    if (isNaN(d.getTime())) { return String(iso); }
    try {
        return d.toLocaleDateString(undefined,
            { day: "numeric", month: "long", year: "numeric" });
    } catch {
        return String(iso).slice(0, 10);
    }
}

/**
 * The stroke offset that draws `pct` of a circle. PURE.
 *
 * Kept out of the template because JavaScript built-ins are not in scope
 * inside one (ledger F16) and because a ring that is arithmetic in markup is a
 * ring nobody can test.
 */
export function ringDash(pct, radius) {
    const circumference = 2 * Math.PI * radius;
    const share = Math.max(0, Math.min(100, Number(pct) || 0)) / 100;
    return { total: circumference, offset: circumference * (1 - share) };
}

export class PbTenancyPlanUsage extends Component {
    static template = "pb_tenancy.PlanUsage";
    static components = { HubBackChip };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.tenancy = useService("pb_tenancy");
        // Subscribed (ledger F47): a plan changed on the platform reaches this
        // page within a minute, without a reload.
        this.tstate = useState(this.tenancy.state);
        this.back = hubBack(this.props);
        this.state = useState({ loaded: false, d: null, error: "" });
        onWillStart(async () => { await this.load(); });
    }

    ic(name, size = 16) { return ic(name, size); }

    async load() {
        try {
            this.state.d = await this.orm.silent.call(
                "pb.tenancy", "plan_usage", []);
            this.state.error = "";
        } catch (e) {
            console.error("pb_tenancy: could not read the plan and usage", e);
            this.state.error = _t(
                "Your plan and usage could not be read just now. Try again in " +
                "a moment — nothing is wrong with your data.");
        }
        this.state.loaded = true;
    }

    get d() { return this.state.d || {}; }

    get planName() { return this.d.plan_name || ""; }

    get seat() {
        return this.d.seat || { verdict: "ok", limit: 0, count: 0, left: -1, pct: 0 };
    }

    get hasLimit() { return !!this.seat.limit; }

    get ring() { return ringDash(this.hasLimit ? this.seat.pct : 100, 46); }

    /** The colour of the ring and of the number inside it. */
    get ringTone() {
        if (!this.hasLimit) { return "ok"; }
        return { full: "bad", near: "warn" }[this.seat.verdict] || "ok";
    }

    /** The one sentence under the ring. */
    get seatSentence() {
        const s = this.seat;
        if (!s.limit) {
            return _t("Your plan has no employee limit.");
        }
        if (s.verdict === "full") {
            return _t("You have reached the number of employees your plan " +
                      "allows. Ask your Payobook administrator for a larger plan.");
        }
        if (s.verdict === "near") {
            return _t("You can add %(left)s more before you reach your plan's limit.",
                      { left: s.left });
        }
        return _t("You can add %(left)s more employees on this plan.", { left: s.left });
    }

    get trial() { return this.d.trial || { phase: "none" }; }

    get onTrial() {
        return this.trial.phase && this.trial.phase !== "none";
    }

    get invoices() {
        return (this.d.invoices || []).map((i) => ({
            ...i,
            tone: (INVOICE_STATE[i.state] || INVOICE_STATE.sent)[0],
            state_label: (INVOICE_STATE[i.state] || INVOICE_STATE.sent)[1],
            issued_h: longDate(i.issued_at),
            due_h: longDate(i.due_date),
            href: `/pb_tenancy/invoice/${encodeURIComponent(i.number)}`,
        }));
    }

    get lede() {
        if (this.planName) {
            return _t("You are on the %(plan)s plan. Everything below is read " +
                      "from your own data — nobody else can see it.",
                      { plan: this.planName });
        }
        return _t("Your plan has not been set yet. The counts below are your " +
                  "own, and your invoices will appear here as they are sent.");
    }
}

registry.category("actions").add("pb_tenancy_plan_usage", PbTenancyPlanUsage);
