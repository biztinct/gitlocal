/** @odoo-module **/
/* =============================================================================
   Mount the demo chrome once, in the web client shell.

   Same pattern as pb_learn/static/src/coach/coach_patch.js and pb_sidebar's own
   WebClient patch, which is this repo's precedent for a component that has to
   exist on every screen. Kept in its own file so the component and its mounting
   can be reasoned about separately — the component is testable chrome, this is
   two lines of wiring.
   ========================================================================== */
import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";
import { DemoChrome } from "./demo_chrome";

patch(WebClient, {
    components: { ...WebClient.components, DemoChrome },
});
