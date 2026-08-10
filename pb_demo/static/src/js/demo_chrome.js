/** @odoo-module **/
/* =============================================================================
   The demo world's own chrome.

   WHY THIS IS HERE AND NOT IN pb_coach
   ------------------------------------
   Two things pb_coach did for demo users had nothing to do with guided tours:
   it tagged the body so a trial user stays inside Payroll, and it showed the
   ephemeral-data disclaimer. Both are facts about THE DEMO WORLD — that its
   records are shared and get overwritten, that a prospect should not wander
   into Discuss — and pb_demo is what knows those facts. They were in the tour
   module only because that is where the overlay happened to be mounted.

   Phase C2 retires pb_coach, so they move to their owner. The CLASS NAME does
   not change (`body.pb-demo-user`): it is a CSS contract, and anything keyed
   off it keeps working.

   COEXISTENCE UNTIL THE UNINSTALL
   -------------------------------
   pb_coach is still installed during the transition and still does both of
   these. Two disclaimer chips stacked on one screen is a worse outcome than
   either module owning it, so this stands down when pb_coach is present —
   checked two ways, because the two answer different questions:

     · the SERVICE tells us pb_coach is installed in this database;
     · a `.pbc-disclaimer` in the DOM tells us it has already drawn one.

   Either is enough to do nothing. Once pb_coach is uninstalled neither is true
   and this takes over, with no deploy step in between.
   ========================================================================== */
import { Component, onMounted, useState } from "@odoo/owl";
import { user } from "@web/core/user";

const DEMO_GROUP = "pb_demo.group_payobook_demo";
const DISMISSED = "pb_demo_disclaimer_off";

export class DemoChrome extends Component {
    static template = "pb_demo.DemoChrome";
    static props = {};

    setup() {
        this.state = useState({ show: false });

        onMounted(async () => {
            let isDemo = false;
            try {
                isDemo = await user.hasGroup(DEMO_GROUP);
            } catch {
                isDemo = false;
            }
            if (!isDemo) {
                return;
            }

            // The body tag. Idempotent by construction — adding a class that is
            // already there is a no-op — but written as a check so the intent
            // is visible: while pb_coach is installed it sets this too, and
            // both modules agree about who is a demo user.
            try {
                if (!document.body.classList.contains("pb-demo-user")) {
                    document.body.classList.add("pb-demo-user");
                }
            } catch {
                /* ignore */
            }

            // The chip. Not drawn while pb_coach can draw its own.
            if (this._coachPresent() || this._coachChipInDom()) {
                return;
            }
            this.state.show = !this._dismissed();
        });
    }

    _coachPresent() {
        try {
            return !!(this.env && this.env.services && this.env.services.pb_coach);
        } catch {
            return false;
        }
    }

    _coachChipInDom() {
        try {
            return !!document.querySelector(".pbc-disclaimer");
        } catch {
            return false;
        }
    }

    _dismissed() {
        try {
            return window.localStorage.getItem(DISMISSED) === "1";
        } catch {
            return false;
        }
    }

    dismiss() {
        this.state.show = false;
        try {
            window.localStorage.setItem(DISMISSED, "1");
        } catch {
            /* ignore */
        }
    }

    /* The branded private-demo request page (pb_demo_portal), not a mailto: —
       it captures the lead in a form and emails the team. Same destination
       pb_coach's chip used. */
    requestPrivateDemo() {
        window.open("/demo/private", "_blank");
    }
}
