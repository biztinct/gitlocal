/** @odoo-module **/
/**
 * <WfPersonWeek/> — the body of the person drawer: one employee's week as a
 * table (scheduled / actual / entered / Δ per day), the week's overtime chips,
 * the compliance chip, and the two doors onwards.
 *
 * P1a built this inside the Time hub. P1b needs the identical panel on the
 * Today board, and W6 says shared UI lives in the kit and is IMPORTED, never
 * forked — so the markup moved here verbatim and both hubs mount it. There is
 * one copy of the "why do the timesheet and the payslip disagree" answer, and
 * one place to fix it.
 *
 * Pure presentation: it fetches nothing and owns no state. The host loads
 * `pb.time.hub.get_person_week` (whose data contract is documented in
 * pb_time_hub/models/time_hub.py) and passes the payload down; the host also
 * owns both actions, because filing a correction WRITES and writes belong to
 * event handlers in the host, never to a child's mount (W21/W21.1).
 */
import { Component } from "@odoo/owl";
import { ic } from "@pb_import_kit/js/import_icons";

export class WfPersonWeek extends Component {
    static template = "pb_wf_kit.WfPersonWeek";
    static props = {
        // the get_person_week payload; null/undefined renders the loader
        data: { type: [Object, { value: null }], optional: true },
        // host-owned actions; omit one and its button is not rendered (W5 still
        // holds — the host must offer at least one way onwards)
        onFileCorrection: { type: Function, optional: true },
        onOpenProfile: { type: Function, optional: true },
        // true while the host's correction RPC is in flight (double-click guard)
        filing: { type: Boolean, optional: true },
    };
    static defaultProps = { data: null, filing: false };

    ic(n, s = 14) { return ic(n, s); }

    get p() { return this.props.data; }

    get subtitle() {
        const p = this.p;
        if (!p) { return ""; }
        return [p.employee.job, p.employee.dept, p.employee.badge]
            .filter((x) => x).join(" · ");
    }

    // ------------------------------------------------------------ format
    /** "8.0" / "—" — an unplanned day has no schedule, it is not a 0 h one. */
    fmt(v, planned = true) {
        if (!planned) { return "—"; }
        if (!v) { return "0"; }
        return String(Math.round(v * 10) / 10);
    }

    fmtDelta(v) {
        if (!v) { return "0"; }
        const n = Math.round(v * 10) / 10;
        return n > 0 ? `+${n}` : String(n);
    }

    deltaTone(v) {
        if (!v || Math.abs(v) < 0.05) { return ""; }
        return v > 0 ? "pos" : "neg";
    }

    dayTone(d) {
        if (d.flags.includes("missing")) { return "miss"; }
        if (d.flags.includes("over")) { return "ed"; }
        if (!d.entered) { return "zero"; }
        return "";
    }
}
