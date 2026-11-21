/** @odoo-module **/
/**
 * ORG CHART P4 — the arrival payload, as a pure function with no imports
 * (so `pb_orgchart/tests/js/arrival.test.mjs` can run it in node).
 */
const VIEWS = ["tree", "lr", "teams", "list"];
const COLORS = ["dept", "loc", "type", "tenure"];

/**
 * What a ⌘K row (`focus`) or a shared link (`search`, a query string) asks
 * the chart to show. Pure: ids are kept as numbers and never trusted — an id
 * the reader may not see simply does not focus.
 *
 * @param {string} focus   the hub's `pb_focus` ("me" | "plan" | "suggest" | "")
 * @param {string} search  a query string, with or without "?"
 * @returns {object|null} { focus, me, mode, view, color, asOf, plan } or null
 */
export function parseArrival(focus, search) {
    const out = { focus: null, me: false, mode: null, view: null, color: null, asOf: null, plan: null };
    let any = false;
    const f = String(focus || "");
    if (f === "me") { out.me = true; any = true; }
    if (f === "plan" || f === "suggest") { out.mode = f; any = true; }
    let q = null;
    try { q = new URLSearchParams(String(search || "").replace(/^\?/, "")); } catch { q = null; }
    if (q && q.get("oc")) {
        any = true;
        const id = parseInt(q.get("oc_focus"), 10);
        if (id > 0) { out.focus = id; }
        const v = q.get("oc_view");
        if (VIEWS.includes(v)) { out.view = v; }
        const c = q.get("oc_color");
        if (COLORS.includes(c)) { out.color = c; }
        const d = q.get("oc_as_of");
        if (d && /^\d{4}-\d{2}-\d{2}$/.test(d)) { out.asOf = d; }
        const p = parseInt(q.get("oc_plan"), 10);
        if (p > 0) { out.plan = p; }
        if (q.get("oc_me") === "1") { out.me = true; }
    }
    return any ? out : null;
}

