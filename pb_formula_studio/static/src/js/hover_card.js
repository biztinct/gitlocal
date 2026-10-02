/** @odoo-module **/
import { Component } from "@odoo/owl";

// W100 — Hover card (WP-A / D-A6). Pure client-side, zero RPC: name, code, col,
// category, formula token chips, the live sample value, and validity. Positioned
// fixed like .g2-ac and `pointer-events: none` so it never traps the pointer. The
// studio root owns the open/dismiss lifecycle (350 ms delay, kill on scroll/keydown).
export class HoverCard extends Component {
    static template = "pb_formula_studio.HoverCard";
    static props = {
        data: Object,      // {name, code, col, category, type, tokens, constant, value, valid, message}
        style: String,     // fixed-position left/top
    };
}
