/** @odoo-module **/
/* =============================================================================
   Mount the Coach ONCE, in the web client shell.

   Cloned from pb_sidebar's own WebClient patch
   (pb_sidebar/static/src/js/webclient_patch.js), which is the precedent in this
   repo for a component that has to be present on every screen. Mounting per
   screen would have to be repeated for every new client action and would be
   forgotten the first time — and "always on" is the requirement, not a
   nice-to-have.
   ========================================================================== */
import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";
import { CoachHost } from "@pb_learn/coach/coach";

patch(WebClient, {
    components: {
        ...WebClient.components,
        CoachHost,
    },
});
