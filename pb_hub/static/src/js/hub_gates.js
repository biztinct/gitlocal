/** @odoo-module **/
/**
 * Who may open which tab — asked WITHOUT opening the hub.  (LEARN REFRESH step 4)
 *
 * A hub decides its tabs when it mounts (`HubShell._resolveAccess`, and
 * pb_mission's own copy): a tab this person cannot use is simply absent. The
 * learning surfaces need the same answer BEFORE anybody opens the hub — the
 * lesson map has to say "you don't have access to this in your company" on a
 * station whose tab is gated, and a walkthrough has to stop before it lands on
 * a screen that will refuse its reader.
 *
 * So each hub REGISTERS the lens gates it already declares, as a function that
 * returns them (read at ask time, so a lens another module bolts on through a
 * registry is included):
 *
 *     registry.category(HUB_LENS_GATES).add("pb_lifecycle_hub",
 *         () => [{ key, groups?, probe?, feature?, hubFeature? }, …]);
 *
 * and the SAME resolver answers for the shell and for the learner. Nothing here
 * is a security boundary — every facade keeps its own gate (W12); this is only
 * the question "would the hub show this tab".
 */
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { featureGate } from "@pb_hub/js/hub_features";

export const HUB_LENS_GATES = "pb_hub_lens_gates";

/**
 * {lensKey: boolean} for a list of lens definitions — groups (any-of, failing
 * OPEN when a group will not resolve: the module is not installed, which is not
 * a refusal), then the lens's own probe for a door a group list cannot express.
 * The body HubShell ran inline until step 4, moved here so there is one copy.
 */
export async function resolveLensAccess(lenses, orm) {
    const list = lenses || [];
    const names = [...new Set(list.flatMap((l) => l.groups || []))];
    const flags = {};
    await Promise.all(names.map(async (g) => {
        try { flags[g] = await user.hasGroup(g); }
        catch (e) {
            console.warn("pb_hub: could not resolve group", g, e);
            flags[g] = true;
        }
    }));
    const allowed = {};
    for (const l of list) {
        allowed[l.key] = !(l.groups || []).length
            || l.groups.some((g) => flags[g]);
    }
    await Promise.all(list.filter((l) => allowed[l.key] && l.probe && orm)
        .map(async (l) => {
            try {
                allowed[l.key] = !!(await orm.call(l.probe.model, l.probe.method, []));
            } catch (e) {
                console.warn("pb_hub: could not ask", l.probe.model, e);
            }
        }));
    return allowed;
}

const asked = new Map();   // tag -> Promise<{lens: boolean} | null>

/**
 * Would hub `tag` show this person each of its tabs? `{lens: bool}`, or null
 * when the hub registered no gates (unknown — never read as "no"). A tab the
 * company has not got counts as not openable. Memoised per page load: groups
 * are cached by the user service anyway, and a probe is one call per tab.
 */
export function hubLensAccess(env, orm, tag) {
    if (!tag) { return Promise.resolve(null); }
    if (!asked.has(tag)) {
        const fn = registry.category(HUB_LENS_GATES).get(tag, null);
        if (typeof fn !== "function") { return Promise.resolve(null); }
        let lenses = [];
        try { lenses = fn() || []; } catch { lenses = []; }
        asked.set(tag, resolveLensAccess(lenses, orm).then((allowed) => {
            for (const l of lenses) {
                for (const f of [l.feature, l.hubFeature]) {
                    const g = featureGate(env, f);
                    if (!g.shown || g.locked) { allowed[l.key] = false; }
                }
            }
            return allowed;
        }).catch(() => null));
    }
    return asked.get(tag);
}
