/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";

const STATUS_CHIPS = [
    { id: "all", label: "All" }, { id: "connected", label: "Connected" },
    { id: "error", label: "Error" }, { id: "disconnected", label: "Disconnected" },
];
const RECENCY_CHIPS = [
    { id: "all", label: "Any time" }, { id: "1h", label: "Synced ≤1h" },
    { id: "1d", label: "Synced ≤1d" }, { id: "old", label: "Older" }, { id: "never", label: "Never" },
];

export class PbIntegrations extends Component {
    static template = "pb_integrations.PbIntegrations";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loaded: false, kpis: {}, connectors: [], types: [], links: [], total: 0,
            search: "", status: "all", type: "", recency: "all",
        });
        onWillStart(async () => { await this.load(); });
    }

    async load() {
        const d = await this.orm.call("pb.integrations", "get_board", []);
        Object.assign(this.state, { kpis: d.kpis, connectors: d.connectors, types: d.types, links: d.links, total: d.total, loaded: true });
    }

    ic(n, s = 16) { return ic(n, s); }
    get statusChips() { return STATUS_CHIPS; }
    get recencyChips() { return RECENCY_CHIPS; }

    setStatus(s) { this.state.status = s; }
    setType(t) { this.state.type = this.state.type === t ? "" : t; }
    setRecency(r) { this.state.recency = r; }
    onSearch(ev) { this.state.search = (ev.target.value || "").toLowerCase(); }

    _hoursSince(iso) {
        if (!iso) return null;
        const t = new Date(iso.replace(" ", "T") + "Z").getTime();
        if (isNaN(t)) return null;
        return (Date.now() - t) / 3600000;
    }
    syncLabel(c) {
        const h = this._hoursSince(c.last_sync);
        if (h === null) return "Never synced";
        if (h < 1) return "Synced <1h ago";
        if (h < 24) return "Synced " + Math.round(h) + "h ago";
        return "Synced " + Math.round(h / 24) + "d ago";
    }
    _matchStatus(c, st) { return st === "all" ? true : c.status === st; }
    _matchRecency(c) {
        const r = this.state.recency;
        if (r === "all") return true;
        const h = this._hoursSince(c.last_sync);
        if (r === "never") return h === null;
        if (h === null) return false;
        if (r === "1h") return h <= 1;
        if (r === "1d") return h <= 24;
        if (r === "old") return h > 24;
        return true;
    }
    get filtered() {
        const q = this.state.search, ty = this.state.type;
        return this.state.connectors.filter(c => {
            if (ty && c.type !== ty) return false;
            if (!this._matchStatus(c, this.state.status)) return false;
            if (!this._matchRecency(c)) return false;
            if (q && !((c.name || "").toLowerCase().includes(q) || (c.type_label || "").toLowerCase().includes(q))) return false;
            return true;
        });
    }
    countStatus(id) { return this.state.connectors.filter(c => this._matchStatus(c, id)).length; }

    openConnector(id) {
        this.action.doAction({
            type: "ir.actions.client", tag: "pb_import_connector_cockpit", name: "Connector",
            params: { connector_id: id, back_to: "pb_integrations.action_pb_integrations", back_label: "Integrations" },
        });
    }
    launch(xmlid) { if (xmlid) this.action.doAction(xmlid, { clearBreadcrumbs: true }); }
}

registry.category("actions").add("pb_integrations", PbIntegrations);
