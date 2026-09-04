/** @odoo-module **/
// Lucide icon paths + ic() for the Analytics Explorer. 24x24 viewBox,
// currentColor stroke, no fills. NEVER emoji, never Font Awesome (C11).
import { markup } from "@odoo/owl";

export const IC = {
    alert:      '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4M12 17h.01"/>',
    arrowRight: '<path d="M5 12h14M12 5l7 7-7 7"/>',
    check:      '<path d="M20 6 9 17l-5-5"/>',
    chevronDown:'<path d="m6 9 6 6 6-6"/>',
    columns:    '<rect width="6" height="12" x="3" y="9" rx="1"/><rect width="6" height="18" x="15" y="3" rx="1"/><path d="M3 21h18"/>',
    compass:    '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
    download:   '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><path d="M12 15V3"/>',
    filter:     '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
    grid:       '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>',
    layers:     '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 12.5-9.17 4.16a2 2 0 0 1-1.66 0L2 12.5"/><path d="m22 17.5-9.17 4.16a2 2 0 0 1-1.66 0L2 17.5"/>',
    lineChart:  '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="m19 9-5 5-4-4-3 3"/>',
    pie:        '<path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>',
    refresh:    '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    ruler:      '<path d="M21.3 8.7 8.7 21.3a1 1 0 0 1-1.4 0l-4.6-4.6a1 1 0 0 1 0-1.4L15.3 2.7a1 1 0 0 1 1.4 0l4.6 4.6a1 1 0 0 1 0 1.4Z"/><path d="m7.5 10.5 2 2M10.5 7.5l2 2M13.5 4.5l2 2M4.5 13.5l2 2"/>',
    search:     '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    sparkles:   '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/>',
    table:      '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18M3 15h18M12 3v18"/>',
    thermo:     '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18M15 3v18M3 9h18M3 15h18"/>',
    trending:   '<path d="M16 7h6v6"/><path d="m22 7-8.5 8.5-5-5L2 17"/>',
    users:      '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/>',
    wallet:     '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
    x:          '<path d="M18 6 6 18M6 6l12 12"/>',
};

/** Inline an icon at `size` px. Returns markup (safe: our own constants). */
export function ic(name, size = 16, cls = "") {
    const path = IC[name] || IC.grid;
    return markup(
        `<svg class="pbex-ic ${cls}" width="${size}" height="${size}" viewBox="0 0 24 24" ` +
        `fill="none" stroke="currentColor" stroke-width="1.9" ` +
        `stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${path}</svg>`
    );
}
