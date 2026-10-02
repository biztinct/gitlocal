/** @odoo-module **/
/**
 * LEARN v3 — Learn > Settings: every learning switch on one card.
 *
 * Five features were built and shipped off, and four of them had no screen at
 * all. This lens is that screen. It writes nothing of its own: each toggle is
 * one call to `learn.settings.set_switch`, which re-asks for administrator
 * rights, writes the parameter the feature already reads, and returns the
 * whole card re-read — so what is drawn is always what the server holds.
 *
 * The lens is gated to administrators in learn_hub.js. The server gate is the
 * real one; this component still draws a plain "only an administrator" line if
 * it is ever mounted for someone else, rather than a card whose switches fail.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

import { RT, T } from "../engine/runtime";
import { loadContent } from "../content/content_loader";

/* The words for each switch. Keys into the content plane's chrome, so the
   card follows the same English / Vietnamese preference as the helper. */
const COPY = {
    next_best: { title: "swNextTitle", body: "swNextBody", icon: "compass" },
    skill_tree: { title: "swSkillTitle", body: "swSkillBody", icon: "award" },
    compose: { title: "swComposeTitle", body: "swComposeBody", icon: "sparkles",
               leaves: "swComposeLeaves", notReady: "swNoProvider" },
    voice: { title: "swVoiceTitle", body: "swVoiceBody", icon: "message-circle",
             leaves: "swVoiceLeaves", notReady: "swNoSpeech" },
    collect: { title: "swCollectTitle", body: "swCollectBody", icon: "lightbulb" },
};

export class LearnSettings extends Component {
    static template = "pb_learn.LearnSettings";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true,
            allowed: false,
            switches: [],
            busy: "",          // key of the switch being saved
            saved: "",         // key of the switch just saved
            failed: "",        // key of the switch that failed to save
        });
        onWillStart(async () => {
            try {
                const content = await loadContent();
                if (!Object.keys(RT.chrome || {}).length) {
                    RT.chrome = content.chrome || {};
                }
                this.state.allowed = await this.orm.call("learn.settings", "can_manage", []);
                if (this.state.allowed) {
                    this.state.switches = await this.orm.call("learn.settings", "get_switches", []);
                }
            } catch {
                this.state.allowed = false;
            } finally {
                this.state.loading = false;
            }
        });
    }

    t(key) {
        return T(key);
    }

    rows() {
        return this.state.switches.map((s) => {
            const c = COPY[s.key] || {};
            return {
                ...s,
                title: T(c.title),
                body: T(c.body),
                icon: c.icon || "info",
                note: s.leaves && c.leaves ? T(c.leaves) : T("swStays"),
                warn: !s.ready && c.notReady ? T(c.notReady) : "",
            };
        });
    }

    async toggle(row) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = row.key;
        this.state.saved = "";
        this.state.failed = "";
        try {
            this.state.switches = await this.orm.call(
                "learn.settings", "set_switch", [row.key, !row.on]);
            this.state.saved = row.key;
            setTimeout(() => {
                if (this.state.saved === row.key) {
                    this.state.saved = "";
                }
            }, 2200);
        } catch {
            this.state.failed = row.key;
        } finally {
            this.state.busy = "";
        }
    }
}
