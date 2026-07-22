/** @odoo-module **/
import { Component, useState, useRef, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { GeoMap } from "@biz_geo_tracking/js/geo_map";

const POLL_MS = 5000;
const NAVY = "#0b1f3a";

function fmtDur(sec) {
    if (sec == null) { return "—"; }
    sec = Math.max(0, Math.floor(sec));
    const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60);
    if (h) { return `${h}h ${m}m`; }
    if (m) { return `${m}m`; }
    return `${sec}s`;
}

export class DriverMap extends Component {
    static template = "pb_driver_checkin.DriverMap";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.mapRef = useRef("map");
        this.geo = null;
        this._timer = null;
        this.state = useState({
            loaded: false,
            drivers: [],
            kpis: {},
            isAdmin: false,
            demoActive: false,
            selectedId: null,
            trailFor: null,
        });
        onWillStart(async () => { await this.load(); });
        onMounted(() => {
            this._initMap();
            this._timer = setInterval(() => this.refresh(), POLL_MS);
        });
        onWillUnmount(() => {
            if (this._timer) { clearInterval(this._timer); this._timer = null; }
            if (this.geo) { this.geo.destroy(); this.geo = null; }
        });
    }

    async load() {
        const d = await this.orm.call("pb.driver.map", "get_live_data", []);
        this._apply(d);
        this.state.loaded = true;
    }

    async refresh() {
        // Silent poll: keep the global loading indicator quiet.
        let d;
        try {
            d = await this.orm.silent.call("pb.driver.map", "get_live_data", []);
        } catch (e) { return; }
        this._apply(d);
        this._syncMarkers();
    }

    _apply(d) {
        this.state.drivers = d.drivers || [];
        this.state.kpis = d.kpis || {};
        this.state.isAdmin = !!d.is_admin;
        this._mapConfig = d.map_config || {};
        // infer demo state from any live sim marker
        this.state.demoActive = (d.drivers || []).some((x) => x.source === "sim" && x.checked_in);
    }

    _initMap() {
        if (!this.mapRef.el) { return; }
        this.geo = new GeoMap(this.mapRef.el, {
            center: [16.0, 106.0], zoom: 6,
            tileUrl: this._mapConfig.tile_url,
            attribution: this._mapConfig.tile_attribution,
        });
        setTimeout(() => this.geo && this.geo.invalidate(), 150);
        this._syncMarkers();
    }

    _syncMarkers() {
        if (!this.geo) { return; }
        const keep = [];
        for (const dvr of this.state.drivers) {
            if (dvr.last_lat == null || dvr.last_lon == null) { continue; }
            keep.push(dvr.id);
            this.geo.upsertMarker(dvr.id, {
                lat: dvr.last_lat, lon: dvr.last_lon,
                label: dvr.initials, sim: dvr.source === "sim", color: NAVY,
                popupHtml: this._popup(dvr),
            });
        }
        this.geo.removeMissing(keep);
    }

    _popup(dvr) {
        const sim = dvr.source === "sim"
            ? `<span class="dm-simchip">SIMULATED</span>` : "";
        const selfie = dvr.selfie_url
            ? `<img class="dm-pop__selfie" src="${dvr.selfie_url}"/>` : "";
        return `<div class="dm-pop">${selfie}<div class="dm-pop__name">${dvr.name} ${sim}</div>` +
            `<div class="dm-pop__row">Since ${dvr.since ? dvr.since.slice(11, 16) : "—"}</div>` +
            `<div class="dm-pop__row">Last ping ${fmtDur(dvr.last_ping_age_s)} ago</div>` +
            (dvr.phone ? `<div class="dm-pop__row">${dvr.phone}</div>` : "") + `</div>`;
    }

    // ---- interactions ----
    freshness(dvr) {
        if (!dvr.checked_in) { return "off"; }
        const a = dvr.last_ping_age_s;
        if (a == null) { return "stale"; }
        if (a < 30) { return "fresh"; }
        if (a < 120) { return "warm"; }
        return "stale";
    }
    fmtAge(sec) { return fmtDur(sec); }
    sinceTime(iso) { return iso ? iso.slice(11, 16) : "—"; }

    selectDriver(dvr) {
        this.state.selectedId = dvr.id;
        if (this.geo) { this.geo.flyTo(dvr.id); }
    }

    async togglePlayback(dvr) {
        if (this.state.trailFor === dvr.id) {
            this.state.trailFor = null;
            if (this.geo) { this.geo.clearTrail(); }
            return;
        }
        const res = await this.orm.call("pb.driver.map", "get_driver_trail", [dvr.id]);
        const latlngs = (res.trail || []).map((p) => [p[0], p[1]]);
        if (this.geo) { this.geo.drawTrail(latlngs); }
        this.state.trailFor = dvr.id;
    }

    async toggleDemo() {
        const next = !this.state.demoActive;
        try {
            await this.orm.call("pb.driver.map", "toggle_demo", [next]);
            this.state.demoActive = next;
            this.notif.add(next ? "Demo mode ON — simulated routes running." : "Demo mode OFF.",
                { type: next ? "success" : "info" });
            await this.refresh();
        } catch (e) {
            this.notif.add(e.message || "Demo toggle failed.", { type: "danger" });
        }
    }
}

registry.category("actions").add("pb_driver_map", DriverMap);
