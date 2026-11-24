/** @odoo-module **/
/**
 * Workforce setup (WFSETUP P2) — the 480 px slide-over of step 3.
 *
 * `WfDrawer` is 320 px (facts H), the design of record is 480 px with a scrim,
 * a header, a scrolling body and a footer, so the screen has its own.
 * Behaviour: Escape and a click on the scrim close it; focus moves onto the
 * drawer when it opens and stays inside it (Tab wraps); the caller decides
 * where focus goes when it closes (back to the bulk bar).
 */
import { Component, onMounted, useRef } from "@odoo/owl";
import { icon } from "./setup_util";

const FOCUSABLE = 'button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

let SEQ = 0;

export class SetupDrawer extends Component {
    static template = "pb_workforce_setup.SetupDrawer";
    static props = {
        title: String,
        subtitle: { type: String, optional: true },
        onClose: Function,
        slots: Object,
    };

    setup() {
        this.icon = icon;
        this.panel = useRef("panel");
        this.titleId = `pbws-drawer-t-${++SEQ}`;
        onMounted(() => {
            const el = this.panel.el;
            if (!el) {
                return;
            }
            // the panel itself: a ring on the first option reads as a second choice
            el.focus({ preventScroll: true });
        });
    }

    onScrim(ev) {
        if (ev.target === ev.currentTarget) {
            this.props.onClose();
        }
    }

    onKey(ev) {
        if (ev.key === "Escape") {
            ev.preventDefault();
            ev.stopPropagation();
            this.props.onClose();
            return;
        }
        if (ev.key !== "Tab") {
            return;
        }
        const items = [...this.panel.el.querySelectorAll(FOCUSABLE)].filter((n) => n.offsetParent !== null);
        if (!items.length) {
            return;
        }
        const first = items[0];
        const last = items[items.length - 1];
        if (ev.shiftKey && document.activeElement === first) {
            ev.preventDefault();
            last.focus();
        } else if (!ev.shiftKey && document.activeElement === last) {
            ev.preventDefault();
            first.focus();
        }
    }
}
