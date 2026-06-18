/** @odoo-module **/

import { Component, useState, onWillStart, markup } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const ICONS = {
    users:'<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    wallet:'<path d="M19 7V5a2 2 0 0 0-2-2H5a2 2 0 0 0 0 4h14a1 1 0 0 1 1 1v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5"/><path d="M18 12a2 2 0 0 0 0 4h3v-4Z"/>',
    clock:'<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    calculator:'<rect width="16" height="20" x="4" y="2" rx="2"/><path d="M8 6h8"/><path d="M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01M16 18h.01"/>',
    zap:'<path d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"/>',
    "trending-up":'<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
    shield:'<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/>',
};

export class PbDashboard extends Component {
    static template = "pb_dashboard.PbDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ d: null, loaded: false });
        onWillStart(async () => {
            this.state.d = await this.orm.call("pb.dashboard", "get_dashboard_data", []);
            this.state.loaded = true;
        });
    }

    icon(name, size = 18) {
        const p = ICONS[name] || ICONS.users;
        return markup(`<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${p}</svg>`);
    }

    ring(value, size = 66) {
        const v = Math.max(0, Math.min(100, value || 0));
        const c = v >= 70 ? "#10B981" : v >= 40 ? "#B7791F" : "#C0332A";
        const r = (size - 8) / 2, circ = 2 * Math.PI * r, off = circ * (1 - v / 100);
        return markup(`<span class="pbd-ring" style="width:${size}px;height:${size}px">
            <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
              <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="#E7E5F2" stroke-width="6"/>
              <circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="${c}" stroke-width="6" stroke-linecap="round"
                stroke-dasharray="${circ}" stroke-dashoffset="${off}" transform="rotate(-90 ${size/2} ${size/2})"/>
            </svg><span class="pbd-ring-n" style="color:${c};font-size:${size*0.3}px">${v}</span></span>`);
    }

    vnd(n) {
        n = n || 0;
        if (n >= 1e9) return "₫" + (n / 1e9).toFixed(1) + "B";
        if (n >= 1e6) return "₫" + (n / 1e6).toFixed(1) + "M";
        if (n >= 1e3) return "₫" + (n / 1e3).toFixed(0) + "K";
        return "₫" + Math.round(n);
    }

    open(xmlid) {
        if (xmlid) this.action.doAction(xmlid, { clearBreadcrumbs: true });
    }
}

registry.category("actions").add("pb_dashboard", PbDashboard);
