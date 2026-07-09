/** @odoo-module **/
/**
 * biz_theme — sidebar collapse state helper (pure utility, patches nothing).
 *
 * Persists a per-user preference in localStorage and mirrors it as body
 * classes consumed by biz_sidebar.scss:
 *
 *   mode "auto"      → (no class)          expanded ≥ md, icon rail < md
 *   mode "collapsed" → body.biz-sb-collapsed   rail at every width
 *   mode "expanded"  → body.biz-sb-expanded    expanded at every width
 *
 * The owning sidebar component (pb_sidebar's PbSidebar, biz_theme's
 * BizSidebar, …) calls applySidebarMode() on mount and toggleSidebarMode()
 * from its pin button, and removes classes on unmount via clearSidebarMode().
 */

const MODES = ["auto", "collapsed", "expanded"];

function storageKey(uid) {
    return `biz.sidebar.mode.${uid || "anon"}`;
}

export function getSidebarMode(uid) {
    try {
        const stored = window.localStorage.getItem(storageKey(uid));
        return MODES.includes(stored) ? stored : "auto";
    } catch {
        return "auto";
    }
}

export function applySidebarMode(mode) {
    const cls = document.body.classList;
    cls.toggle("biz-sb-collapsed", mode === "collapsed");
    cls.toggle("biz-sb-expanded", mode === "expanded");
}

export function clearSidebarMode() {
    document.body.classList.remove("biz-sb-collapsed", "biz-sb-expanded");
}

/**
 * Cycle based on the user's *effective* state so the button always does what
 * it looks like it does: if the sidebar currently renders expanded → collapse;
 * if it renders as a rail → expand (pinned, so it survives small screens).
 */
export function toggleSidebarMode(uid) {
    const belowAutoBp = window.matchMedia("(max-width: 1099px)").matches;
    const mode = getSidebarMode(uid);
    const effectivelyCollapsed =
        mode === "collapsed" || (mode === "auto" && belowAutoBp);
    const next = effectivelyCollapsed ? "expanded" : "collapsed";
    try {
        window.localStorage.setItem(storageKey(uid), next);
    } catch {
        // private mode — state just won't persist
    }
    applySidebarMode(next);
    return next;
}
