/** @odoo-module **/
/**
 * The hub navigation protocol — one door in, one door back.
 *
 * Every hub in the Option-A IA is reached the same way, and every hand-off says
 * where it came from, so a surface can never be a dead end (W5). Three context
 * keys carry the whole thing:
 *
 *   `pb_lens`   which lens to raise on arrival
 *   `pb_focus`  what a pinned selection MEANS on arrival — `"queue"` says it is
 *               a FILTER, not a drawer to pop over the thing the user came to
 *               read (W26, kept verbatim so hosts write one vocabulary)
 *   `pb_back`   `{ label, tag|xmlid, lens }` — the return door, rendered by
 *               <HubShell/> as a <HubBackChip/> in the command bar
 *
 * `pb_mission` reads its lens from `pb_shell_lens` instead, because it forwards
 * `pb_lens` unchanged to the Time hub inside it. That is not a second protocol
 * to support forever, it is one existing consumer — so `openHub` takes a
 * `lensKey` and the palette's Mission Control entries set it. Nothing is
 * rewritten in pb_mission for this cycle (binding non-goal).
 */
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";

/** The context key a plain pb_hub shell reads its arrival lens from. */
export const HUB_LENS_KEY = "pb_lens";

/**
 * Open a hub (or any client action) with the arrival protocol filled in.
 *
 * @param {object} actionService  the "action" service (the caller's, so the
 *                                notification/breadcrumb behaviour is the
 *                                caller's too)
 * @param {object}  opts
 * @param {string} [opts.tag]      client action tag, e.g. "pb_hub_demo"
 * @param {string} [opts.xmlid]    action xmlid — wins over `tag` when both given
 * @param {string} [opts.lens]     lens key to raise on arrival
 * @param {string} [opts.lensKey]  context key for `lens` (default `pb_lens`)
 * @param {string} [opts.focus]    `"queue"` etc. — see W26
 * @param {object} [opts.back]     `{ label, tag|xmlid, lens }`, the return door
 * @param {object} [opts.context]  extra context, merged last
 * @param {boolean} [opts.clearBreadcrumbs=true]
 * @returns {Promise} whatever doAction returns
 */
export function openHub(actionService, opts = {}) {
    const {
        tag, xmlid, lens, lensKey = HUB_LENS_KEY, focus, back,
        context = {}, clearBreadcrumbs = true,
    } = opts;
    const target = xmlid || tag;
    if (!target) {
        // A door with no destination is a bug in the CALLER, and swallowing it
        // would make the click look like a slow screen (W40: never catch{}).
        throw new Error("openHub: one of `tag` or `xmlid` is required");
    }
    const additionalContext = { ...context };
    if (lens) { additionalContext[lensKey] = lens; }
    if (focus) { additionalContext.pb_focus = focus; }
    // Plain data only: the context crosses `doAction` and may be serialised.
    if (back && (back.tag || back.xmlid)) {
        additionalContext.pb_back = {
            label: back.label || "",
            tag: back.tag || "",
            xmlid: back.xmlid || "",
            lens: back.lens || "",
            // carried so a back door into a hub that reads another key (e.g.
            // pb_mission's `pb_shell_lens`) still lands on the right lens
            lensKey: back.lensKey || HUB_LENS_KEY,
        };
    }
    return actionService.doAction(target, { additionalContext, clearBreadcrumbs });
}

/**
 * The return door, as a chip.
 *
 * <HubShell/> renders it in the command bar whenever the action it was opened
 * with carries `pb_back`; it is exported separately so a lens that owns its own
 * header can render one too. It navigates itself — a back chip that needs its
 * host to wire a callback is a back chip somebody will forget to wire.
 */
export class HubBackChip extends Component {
    static template = "pb_hub.HubBackChip";
    static props = {
        // { label, tag|xmlid, lens } — exactly what openHub() wrote
        back: { type: Object },
    };

    setup() {
        this.actionService = useService("action");
    }

    ic(n, s = 12) { return ic(n, s); }

    get label() { return this.props.back.label || "Back"; }

    /** A CLICK handler, never a lifecycle hook (W21). */
    goBack() {
        const b = this.props.back;
        openHub(this.actionService, {
            tag: b.tag, xmlid: b.xmlid, lens: b.lens, lensKey: b.lensKey,
        });
    }
}
