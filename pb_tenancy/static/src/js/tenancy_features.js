/** @odoo-module **/
/**
 * `pb_tenancy_features` — which parts of the product this company has, in the
 * browser, live.
 *
 * ============================== why a second service ==========================
 * `pb_tenancy` already holds everything the platform has said, and features are
 * three more keys in the same payload. They get their own service anyway, and
 * for one reason: the things that ASK are not the things that draw a banner.
 * The hub kit, the command palette and the Settings hub all need the answer,
 * and none of them may depend on this module — `pb_tenancy` depends on THEM.
 * A service is the one seam that runs the right way round: they look it up by
 * name at run time and carry on perfectly well when it is not there.
 *
 * ================================= fail open =================================
 * Three separate ways this ends up saying "yes, they have it": the module is not
 * installed (the lookup finds nothing), the platform has never told this
 * database anything (the maps are empty), or the key is one nobody has heard of
 * (absent from the maps). All three are the same answer on purpose. The
 * alternative — a database losing half its product because a setting had not
 * arrived yet — is a payroll office that cannot pay people.
 *
 * ================================= live update ===============================
 * The state object is the SAME reactive object `pb_tenancy` polls into once a
 * minute (F14: while the tab is visible). So a switch flipped on the platform
 * reaches an open page within a minute, and everything reading through
 * `useState` here re-renders on its own with no reload and no event bus.
 */
import { registry } from "@web/core/registry";

/** The name the kit looks this service up by. Exported so both ends agree. */
export const FEATURES_SERVICE = "pb_tenancy_features";

export const featuresService = {
    dependencies: ["pb_tenancy"],

    start(env, { pb_tenancy }) {
        const state = pb_tenancy.state;

        /** Everything on, unless this database has been told otherwise. */
        function isOn(key) {
            if (!key) { return true; }
            const map = state.features || {};
            return !(key in map) || !!map[key];
        }

        /** "hide" or "lock" — how an OFF part of the product looks here. */
        function mode(key) {
            if (!key) { return "hide"; }
            return (state.feature_mode || {})[key] === "lock" ? "lock" : "hide";
        }

        /** The one line under a padlock. Never empty for a locked feature. */
        function lockText(key) {
            return (state.feature_lock_text || {})[key] || "";
        }

        /**
         * (shown, locked) for one part of the product — the shape every caller
         * actually wants, worked out once here rather than three times each in
         * the shell, the palette and the Settings hub.
         */
        function gate(key) {
            if (isOn(key)) { return { shown: true, locked: false, text: "" }; }
            if (mode(key) === "lock") {
                return { shown: true, locked: true, text: lockText(key) };
            }
            return { shown: false, locked: false, text: lockText(key) };
        }

        return {
            // The reactive object itself, so a component can `useState` it and
            // repaint when the once-a-minute read brings a change.
            state,
            isOn, mode, lockText, gate,
            /** Has the platform ever said anything about features here? */
            get known() { return !!state.features_known; },
        };
    },
};

registry.category("services").add(FEATURES_SERVICE, featuresService);
