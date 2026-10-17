/** @odoo-module **/
/**
 * <WfRibbon/> — the exception ribbon from mockup A: one line that names what
 * needs attention on this surface and offers the single action that resolves it.
 *
 * Tone is a pbim semantic, never a free colour (W1):
 *   amber  — needs attention / over a soft limit
 *   rose   — blocked / breached
 *   green  — cleared, nothing outstanding
 */
import { Component } from "@odoo/owl";
import { ic } from "@pb_import_kit/js/import_icons";

const TONE_ICON = { amber: "alert", rose: "alert", green: "checkCircle" };

export class WfRibbon extends Component {
    static template = "pb_wf_kit.WfRibbon";
    static props = {
        tone: { type: String, optional: true },       // amber | rose | green
        text: { type: String },
        actionLabel: { type: String, optional: true },
        onAction: { type: Function, optional: true },
    };
    static defaultProps = { tone: "amber", actionLabel: "" };

    get tone() {
        return ["amber", "rose", "green"].includes(this.props.tone) ? this.props.tone : "amber";
    }

    get icon() { return TONE_ICON[this.tone]; }

    ic(n, s = 15) { return ic(n, s); }
}
