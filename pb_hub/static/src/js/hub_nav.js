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
 *   `pb_back`   `{ label, tag|xmlid, lens, context }` — the return door, rendered
 *               by <HubShell/> as a <HubBackChip/> in the command bar, and by any
 *               plain cockpit that asks `hubBack(this.props)` for one
 *
 * `pb_mission` reads its lens from `pb_shell_lens` instead, because it forwards
 * `pb_lens` unchanged to the Time hub inside it. That is not a second protocol
 * to support forever, it is one existing consumer — so `openHub` takes a
 * `lensKey` and the palette's Mission Control entries set it. Nothing is
 * rewritten in pb_mission for this cycle (binding non-goal).
 */
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
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
 * @param {object} [opts.back]     `{ label, tag|xmlid, lens, context }`, the
 *                                 return door. Its own `context` is what a
 *                                 non-hub cockpit needs to be re-opened ON the
 *                                 record you left it on (a connector id, say) —
 *                                 without it the chip lands on an empty shell.
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
            // Plain object or nothing. `_t()` returns a String SUBCLASS, so a
            // lazy translation dropped in here would not survive the JSON round
            // trip a context takes — keep ids and technical keys only.
            context: (back.context && typeof back.context === "object")
                ? { ...back.context } : {},
        };
    }
    return actionService.doAction(target, { additionalContext, clearBreadcrumbs });
}

/**
 * The return door a client action was opened with, or `null`.
 *
 * <HubShell/> reads this for itself; every OTHER cockpit — one that owns its own
 * header instead of a hub's command bar — asks for it here and renders the same
 * <HubBackChip/> with `tone="light"`. That is the whole of the one-door law on a
 * non-hub surface: the door that sent you says how to get back, and the surface
 * does not have to know who that was.
 *
 * Returns null for a `pb_back` with no destination, because a back door with
 * nowhere to go is not a back door — the chip must be ABSENT, never inert.
 */
export function hubBack(props) {
    const b = (props && props.action && props.action.context
               && props.action.context.pb_back) || null;
    return (b && (b.tag || b.xmlid)) ? b : null;
}

/**
 * The return door, as a chip.
 *
 * <HubShell/> renders it in the command bar whenever the action it was opened
 * with carries `pb_back`; it is exported separately so a lens that owns its own
 * header can render one too. It navigates itself — a back chip that needs its
 * host to wire a callback is a back chip somebody will forget to wire.
 *
 * TWO TONES, because the chip has two backgrounds to sit on. `dark` (the
 * default) is the hub's #241F52 command bar and its styles live inside the
 * `.pbim.pbhub` block. `light` is a white cockpit header — Integrations,
 * Structures, Statutory, Tenants — and it is a SEPARATE root-scoped block,
 * because a cockpit that is not a hub never matches `.pbhub` and would
 * otherwise render white-on-white: styled by accident is how a control
 * disappears without anyone seeing an error (W14's shape).
 */
export class HubBackChip extends Component {
    static template = "pb_hub.HubBackChip";
    static props = {
        // { label, tag|xmlid, lens, context } — exactly what openHub() wrote
        back: { type: Object },
        // "dark" (a hub command bar) | "light" (a white cockpit header)
        tone: { type: String, optional: true },
    };

    setup() {
        this.actionService = useService("action");
    }

    get lite() { return this.props.tone === "light"; }

    ic(n, s = 12) { return ic(n, s); }

    get label() { return this.props.back.label || _t("Back"); }

    /** Translated here rather than interpolated in the template. */
    get title() { return _t("Back to %s", this.label); }

    /** A CLICK handler, never a lifecycle hook (W21). */
    goBack() {
        const b = this.props.back;
        openHub(this.actionService, {
            tag: b.tag, xmlid: b.xmlid, lens: b.lens, lensKey: b.lensKey,
            context: b.context || {},
        });
    }
}
