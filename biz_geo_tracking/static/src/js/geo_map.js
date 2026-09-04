/** @odoo-module **/
/* Thin, framework-agnostic wrapper around vendored Leaflet (global `L`).
 * Used by backend cockpits (loaded in web.assets_backend). The phone PWA
 * uses Leaflet directly — it can't import across asset bundles. */

function L() {
    if (!window.L) {
        throw new Error("Leaflet (window.L) is not loaded.");
    }
    return window.L;
}

// Avatar-initial circular marker, Payobook-navy with a white ring. Sim markers
// get a dashed ring + is-sim class (styled by the consuming cockpit's CSS).
export function initialsIcon(label, { sim = false, color = "#0b1f3a" } = {}) {
    const cls = "bgeo-pin" + (sim ? " bgeo-pin--sim" : "");
    const html =
        `<span class="bgeo-pin__dot" style="--bgeo-pin-color:${color}">` +
        `${(label || "?").slice(0, 2).toUpperCase()}</span>`;
    return L().divIcon({
        className: cls,
        html,
        iconSize: [34, 34],
        iconAnchor: [17, 17],
        popupAnchor: [0, -18],
    });
}

export class GeoMap {
    constructor(el, opts = {}) {
        const l = L();
        this.markers = {};
        this.trail = null;
        this.map = l.map(el, {
            zoomControl: true,
            attributionControl: true,
            preferCanvas: true,
        }).setView(opts.center || [16.0, 106.0], opts.zoom || 6);
        l.tileLayer(opts.tileUrl || "https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: opts.attribution || "© OpenStreetMap contributors",
            maxZoom: 19,
        }).addTo(this.map);
    }

    // Create or move a marker keyed by `key`.
    upsertMarker(key, { lat, lon, label, sim, color, popupHtml } = {}) {
        const l = L();
        const icon = initialsIcon(label, { sim, color });
        let m = this.markers[key];
        if (m) {
            m.setLatLng([lat, lon]);
            m.setIcon(icon);
        } else {
            m = l.marker([lat, lon], { icon }).addTo(this.map);
            this.markers[key] = m;
        }
        if (popupHtml !== undefined) {
            m.bindPopup(popupHtml, { className: "bgeo-popup" });
        }
        return m;
    }

    removeMarker(key) {
        const m = this.markers[key];
        if (m) {
            this.map.removeLayer(m);
            delete this.markers[key];
        }
    }

    removeMissing(keepKeys) {
        const keep = new Set((keepKeys || []).map(String));
        for (const key of Object.keys(this.markers)) {
            if (!keep.has(String(key))) {
                this.removeMarker(key);
            }
        }
    }

    flyTo(key, zoom = 15) {
        const m = this.markers[key];
        if (m) {
            this.map.flyTo(m.getLatLng(), zoom, { duration: 0.8 });
            m.openPopup();
        }
    }

    // latlngs = [[lat, lon], ...]
    drawTrail(latlngs, { color = "#5A4BB0", opacity = 0.6 } = {}) {
        const l = L();
        this.clearTrail();
        if (!latlngs || !latlngs.length) {
            return;
        }
        this.trail = l.polyline(latlngs, { color, opacity, weight: 4 }).addTo(this.map);
        this.map.fitBounds(this.trail.getBounds(), { padding: [40, 40] });
    }

    clearTrail() {
        if (this.trail) {
            this.map.removeLayer(this.trail);
            this.trail = null;
        }
    }

    invalidate() {
        // Leaflet needs this after its container resizes / becomes visible.
        if (this.map) {
            this.map.invalidateSize();
        }
    }

    destroy() {
        if (this.map) {
            this.map.remove();
            this.map = null;
        }
    }
}
