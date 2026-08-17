/** @odoo-module **/
/**
 * Overtime Desk — a bespoke cockpit over the OT approval queue + the Bonus
 * Hours engine. Two views: the board (hero KPIs · approval queue with ceiling
 * context + live split chips · config gallery) and the server-gated Bonus Hours
 * review (filter rail + grouped table + CSV export). RPC facade: pb.ot.desk.
 * pbim-tokenized (.pbot.pbim), amber OT tint. Lucide icons only.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_hr_workforce/js/pbot_icons";

const MODEL = "pb.ot.desk";

export class PbOtDesk extends Component {
    static template = "pb_hr_workforce.PbOtDesk";
    static props = {
        action: { type: Object, optional: true },
        // W17 (P3a): Mission Control owns the page identity, so `embedded`
        // suppresses the hero's eyebrow/title/subtitle and nothing else. The
        // Bonus Hours door beside it, the bonus view's own filter rail and every
        // facade call stay exactly as they are — the shell has no department or
        // period opinion to replace them with (P3a §3.4).
        embedded: { type: Boolean, optional: true },
        "*": true,
    };
    static defaultProps = { embedded: false };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.ic = ic;
        this.state = useState({
            loaded: false,
            busy: false,
            view: "board",             // board | bonus
            data: null,
            selected: {},              // id -> true (bulk tray)
            rowResults: {},            // id -> {ok, error} after a bulk act
            refuseOpen: false,
            refuseNote: "",
            refuseIds: [],
            bonus: this._blankBonus(),
        });
        onWillStart(async () => { await this.load(); });
    }

    _blankBonus() {
        return {
            loaded: false,
            data: null,
            group_by: "employee",
            preset: "month",
            date_from: "",
            date_to: "",
            employee: "",
            department: "",
            overtime_type: "",
            min_hours: "",
            page: 0,
        };
    }

    async load() {
        try {
            this.state.data = await this.orm.call(MODEL, "get_desk", []);
            this.state.loaded = true;
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
            this.state.loaded = true;
        }
    }

    // -------------------------------------------------------------- queue
    get queue() { return (this.state.data && this.state.data.queue) || []; }
    get kpis() { return (this.state.data && this.state.data.kpis) || {}; }
    get selectedIds() {
        return Object.keys(this.state.selected).filter((k) => this.state.selected[k]).map(Number);
    }
    get selectedCount() { return this.selectedIds.length; }

    isSelected(id) { return !!this.state.selected[id]; }
    toggle(id) { this.state.selected[id] = !this.state.selected[id]; }
    selectAll() {
        const all = this.queue.every((q) => this.state.selected[q.id]);
        for (const q of this.queue) { this.state.selected[q.id] = !all; }
    }
    clearSel() { this.state.selected = {}; }

    fmt(v) {
        const n = Number(v || 0);
        return Number.isInteger(n) ? String(n) : String(Math.round(n * 100) / 100);
    }
    pct(used, cap) {
        if (!cap) { return 0; }
        return Math.min(100, Math.round((100 * (used || 0)) / cap));
    }
    barTone(used, cap) {
        const p = this.pct(used, cap);
        return p >= 90 ? "rose" : p >= 70 ? "amber" : "ok";
    }

    async approveOne(id) { await this._act([id], "approve"); }
    async refuseOne(id) { this._openRefuse([id]); }
    async bulkApprove() {
        if (!this.selectedCount) { return; }
        await this._act(this.selectedIds, "approve");
    }
    bulkRefuse() {
        if (!this.selectedCount) { return; }
        this._openRefuse(this.selectedIds);
    }

    _openRefuse(ids) {
        this.state.refuseIds = ids;
        this.state.refuseNote = "";
        this.state.refuseOpen = true;
    }
    cancelRefuse() { this.state.refuseOpen = false; this.state.refuseIds = []; }
    onRefuseNote(ev) { this.state.refuseNote = ev.target.value; }
    async confirmRefuse() {
        const ids = this.state.refuseIds;
        this.state.refuseOpen = false;
        await this._act(ids, "refuse", this.state.refuseNote || false);
    }

    async _act(ids, action, note) {
        this.state.busy = true;
        try {
            const res = await this.orm.call(MODEL, "act", [ids, action], { note });
            const results = (res && res.results) || [];
            let ok = 0;
            const fails = [];
            for (const r of results) {
                this.state.rowResults[r.id] = r;
                if (r.ok) { ok += 1; } else { fails.push(r); }
            }
            if (ok) {
                this.notif.add(
                    _t("%s overtime request(s) %s.", ok,
                        action === "approve" ? _t("approved") : _t("refused")),
                    { type: "success" });
            }
            if (fails.length) {
                this.notif.add(
                    fails.map((f) => `${f.name || f.id}: ${f.error}`).join("  ·  "),
                    { type: "warning", sticky: fails.length > 1 });
            }
            this.clearSel();
            await this.load();
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    typeLabel(t) {
        return { weekday: _t("Weekday"), weekend: _t("Weekend"),
                 holiday: _t("Public Holiday"), night: _t("Night") }[t] || t; }

    // ---------------------------------------------------------- config gallery
    get configs() { return (this.state.data && this.state.data.configs) || { cards: [], caps: {} }; }
    openConfig(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.overtime.config",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }
    dayLetters() { return ["M", "T", "W", "T", "F", "S", "S"]; }

    // -------------------------------------------------------------- bonus tab
    openBonus() {
        if (!(this.state.data && this.state.data.can_view_bonus)) { return; }
        this.state.view = "bonus";
        if (!this.state.bonus.loaded) { this.loadBonus(); }
    }
    backToBoard() { this.state.view = "board"; }

    _bonusFilters() {
        const b = this.state.bonus;
        return {
            preset: b.preset,
            date_from: b.date_from || false,
            date_to: b.date_to || false,
            employee: b.employee || false,
            department: b.department || false,
            overtime_type: b.overtime_type || false,
            min_hours: b.min_hours || false,
        };
    }
    async loadBonus() {
        const b = this.state.bonus;
        this.state.busy = true;
        try {
            b.data = await this.orm.call(
                MODEL, "get_bonus_hours", [this._bonusFilters(), b.page, b.group_by]);
            b.loaded = true;
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    setGroupBy(g) { this.state.bonus.group_by = g; this.state.bonus.page = 0; this.loadBonus(); }
    setPreset(p) { this.state.bonus.preset = p; this.state.bonus.page = 0; this.loadBonus(); }
    onBonusField(f, ev) { this.state.bonus[f] = ev.target.value; }
    applyBonusFilters() { this.state.bonus.page = 0; this.loadBonus(); }
    nextBonusPage() { this.state.bonus.page += 1; this.loadBonus(); }
    prevBonusPage() { if (this.state.bonus.page > 0) { this.state.bonus.page -= 1; this.loadBonus(); } }

    async exportBonus() {
        this.state.busy = true;
        try {
            const r = await this.orm.call(MODEL, "export_bonus_csv", [this._bonusFilters()]);
            const a = document.createElement("a");
            a.href = "data:text/csv;base64," + r.csv_b64;
            a.download = r.filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            this.notif.add(
                r.truncated
                    ? _t("Exported %s rows (capped at %s — narrow the filters).", r.count, r.cap)
                    : _t("Exported %s rows.", r.count),
                { type: r.truncated ? "warning" : "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    groupByOptions() {
        return [
            { key: "employee", label: _t("Employee") },
            { key: "department", label: _t("Department") },
            { key: "day", label: _t("Day") },
            { key: "week", label: _t("Week") },
            { key: "month", label: _t("Month") },
        ];
    }

    _err(e) { return (e && e.data && e.data.message) || (e && e.message) || _t("Action failed."); }
}

registry.category("actions").add("pb_ot_desk", PbOtDesk);
