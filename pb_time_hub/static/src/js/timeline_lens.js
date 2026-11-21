/** @odoo-module **/
/**
 * Timeline lens — the one surface in P1a that is genuinely rebuilt.
 *
 * The old Timecards cockpit dies with this phase: an inline-template OWL screen
 * on an orange palette with thirteen gradients. What survives is its READ-MODEL
 * (`hr.attendance.timecard`, plus pb_business_trip's `_inherit` that injects
 * virtual trip bars) — the OT classification and the bar geometry are real work
 * and are reused verbatim through the hub's gated `get_timeline`. The
 * presentation is new: pbim tones, flat fills, no gradients (W1/W3).
 *
 * One row per employee for the context week; each day is its own hour track
 * (06:00–22:00) carrying that day's punch bars at their computed left/width
 * percentages. Avatars are doors to the person drawer (W5).
 */
import { Component, useState, onWillUpdateProps, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.time.hub";

export class TimelineLens extends Component {
    static template = "pb_time_hub.TimelineLens";
    static props = {
        departmentId: { type: [Number, Boolean], optional: true },
        weekStart: { type: String },
        search: { type: String, optional: true },
        onPerson: { type: Function, optional: true },
    };
    static defaultProps = { departmentId: false, search: "" };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.state = useState({ loading: true, data: null });

        onWillStart(() => this._load(this.props));
        // The hub re-renders this lens when the shared context moves; a context
        // change must REFETCH, so compare the query inputs rather than trusting
        // the render.
        onWillUpdateProps((next) => {
            if (this._key(next) !== this._key(this.props)) { return this._load(next); }
        });
    }

    _key(p) {
        return `${p.weekStart}|${p.departmentId || ""}|${p.search || ""}`;
    }

    async _load(p) {
        // Compare against the LAST REQUESTED key, not against `this.props`:
        // inside onWillUpdateProps `this.props` is still the OLD props until the
        // hook resolves, so a props-based guard would discard every update's
        // own reply and the lens would never repaint.
        const key = this._key(p);
        this._reqKey = key;
        this.state.loading = true;
        try {
            const data = await this.orm.call(MODEL, "get_timeline", [
                p.departmentId || false, p.weekStart, p.search || false,
            ]);
            // A slow reply for an abandoned week must not paint over the
            // current one.
            if (this._reqKey !== key) { return; }
            this.state.data = data;
            if (data && data.truncated) {
                this.notif.add(
                    _t("Showing the first %s employees — narrow by department or search to see the rest.",
                       data.employees.length),
                    { type: "warning" });
            }
        } catch (e) {
            if (this._reqKey !== key) { return; }
            this.state.data = null;
            this.notif.add((e && e.data && e.data.message) || _t("Could not load the timeline."),
                { type: "danger" });
        } finally {
            if (this._reqKey === key) { this.state.loading = false; }
        }
    }

    ic(n, s = 14) { return ic(n, s); }

    get days() { return (this.state.data && this.state.data.days) || []; }
    get rows() { return (this.state.data && this.state.data.employees) || []; }
    get legend() { return (this.state.data && this.state.data.legend) || []; }

    /** The hour window the bar percentages are measured against (facade :189). */
    get axisLabel() { return "06:00 – 22:00"; }

    dayCard(row, iso) {
        return (row.days && row.days[iso]) || { entries: [], regular: 0, overtime: 0, total: 0 };
    }

    barStyle(bar) {
        // bar_left / bar_width are the legacy facade's GEOMETRY — reused as-is;
        // only the fill is ours.
        return `left:${bar.bar_left}%;width:${bar.bar_width}%;`;
    }

    barTitle(row, iso, bar) {
        const card = this.dayCard(row, iso);
        if (bar.bar_type === "trip") { return _t("Business trip"); }
        const span = bar.check_in
            ? `${bar.check_in} → ${bar.check_out || _t("now")}`
            : (bar.check_out || "");
        return `${bar.label || ""}${span ? " · " + span : ""}`
            + (card.ot_label ? ` · ${card.ot_label}` : "");
    }

    fmtH(v) { return Math.round((v || 0) * 10) / 10; }

    openPerson(id) {
        if (this.props.onPerson) { this.props.onPerson(id); }
    }
}
