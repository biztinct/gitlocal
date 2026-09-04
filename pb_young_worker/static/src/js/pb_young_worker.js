/** @odoo-module **/
/**
 * Young Worker Guard cockpit — a calm compliance screen over the under-18
 * roster: KPI strip, roster cards with days-to-18 countdown chips and week-hour
 * gauges, a 30-day violation feed, and the read-only VN band table.
 * RPC facade: pb.young.worker.guard. pbim-tokenized (.pbim.pbyw).
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_young_worker/js/pbyw_icons";

const MODEL = "pb.young.worker.guard";

// Violation kind → Lucide icon key (see pbyw_icons.js). No Font Awesome glyphs.
const KIND_ICON = {
    day_cap: "clock",
    week_cap: "calendar",
    night: "moon",
    ot: "ban",
    no_birthday: "help",
};

export class PbYoungWorker extends Component {
    static template = "pb_young_worker.PbYoungWorker";
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false,
            busy: false,
            data: { kpis: {}, roster: [], feed: [], missing: [], rules: [], can_edit: false },
        });
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        try {
            this.state.data = await this.orm.call(MODEL, "get_guard_data", []);
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.loaded = true;
        }
    }

    // ------------------------------------------------------------- gauges
    gaugePct(r) {
        if (!r.week_cap) { return 0; }
        return Math.min(100, Math.round((r.week_hours / r.week_cap) * 100));
    }
    gaugeBand(r) {
        const p = this.gaugePct(r);
        if (p >= 100) { return "rose"; }
        if (p >= 80) { return "amber"; }
        return "ok";
    }

    // ------------------------------------------------------------- chips
    countdown(r) {
        if (r.days_to_adult === false || r.days_to_adult === null || r.days_to_adult === undefined) {
            return _t("age unknown");
        }
        const age = `${r.age_years}y ${r.age_months}m`;
        if (r.days_to_adult <= 0) { return _t("adult"); }
        return `${age} · ${_t("adult in")} ${r.days_to_adult} ${_t("days")}`;
    }
    countdownClass(r) {
        if (r.days_to_adult !== false && r.days_to_adult <= 30) { return "pbyw-chip--soon"; }
        return "";
    }

    // ------------------------------------------------------------- icons
    ic(name, size = 16) { return ic(name, size); }
    kindIcon(kind, size = 15) { return ic(KIND_ICON[kind] || "alertCircle", size); }
    kindLabel(kind) {
        return {
            day_cap: _t("Daily cap"), week_cap: _t("Weekly cap"),
            night: _t("Night work"), ot: _t("Overtime"), no_birthday: _t("Missing birthday"),
        }[kind] || kind;
    }

    // ------------------------------------------------------------- rules
    async editRules() {
        this.state.busy = true;
        try {
            const act = await this.orm.call(MODEL, "open_rules", []);
            this.actionService.doAction(act, { onClose: () => this.load() });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    _err(e) { return (e && e.data && e.data.message) || (e && e.message) || _t("Action failed."); }
}

registry.category("actions").add("pb_young_worker", PbYoungWorker);
