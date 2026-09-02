/** @odoo-module **/
/**
 * `pb_settings_hub` — the cog.
 *
 * Option A's rail is six missions and a cog, and this is what is behind the cog:
 * a left column of eight categories, a right pane of one or two cards each, and
 * nothing else. Every card OPENS something that already exists. The hub stores
 * no setting, computes no default and owns no model — if it ever did, it would
 * become a second place where a configuration lives, which is precisely the
 * problem the one-door law exists to end.
 *
 * Four rules the surface is built to, each of them scar tissue:
 *
 *  1. **A card that opens nothing is not rendered.** Client-action cards are
 *     probed against the actions registry; `act_window` cards are probed
 *     server-side (`pb.settings.resolve_actions`). A tile pointing at a deleted
 *     action renders normally and answers a click with silence (W79), and a
 *     door that can only produce an error is worse than no door (W29). A
 *     category whose every card is missing disappears with them.
 *  2. **A category this persona cannot use is ABSENT, not disabled** — the same
 *     answer HubShell gives a lens it may not show. Group resolution FAILS OPEN
 *     per group: an xmlid that will not resolve means the module is not
 *     installed, and reading that as "denied" hides a category for the wrong
 *     reason. Nothing here is a security boundary; every action keeps its own.
 *  3. **A cockpit is opened with a back chip; a native form is opened with a
 *     breadcrumb.** The bespoke cockpits render `<HubBackChip/>` from the
 *     `pb_back` context key. The four native `act_window` cards cannot — they
 *     are Odoo's own views — so they are opened WITHOUT clearing the
 *     breadcrumbs, and "Settings" is the crumb that brings you back. Both are
 *     real return paths; neither is a dead end (W5).
 *  4. **Every door is a CLICK handler.** Nothing in this file writes anything
 *     from a mount hook, and `_opening` makes a double-click one navigation
 *     rather than two (C1's flag, W21.1's lesson).
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { isMacOS } from "@web/core/browser/feature_detection";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack, openHub } from "@pb_hub/js/hub_nav";

/** localStorage: which category was open last. Namespaced and versioned. */
const STORAGE_KEY = "pbst.cat.v1";

/**
 * The gates — derived from what each target's OWN `ir.model.access` grants,
 * never from the rail item that used to open it.
 *
 * That is a deliberate departure from Cycle 1's palette rule ("every gate
 * mirrors the rail item that owns the same door"), and it was forced by the
 * live run rather than chosen: the rail's Formula Engine item is gated at the
 * pb_hr_payroll_base OFFICER tier, `hr.formula.config` grants read to
 * `pb_hr_payroll_formula.group_formula_user` / `_manager`, and NEITHER tier
 * implies the other on this database. A persona holding the first and not the
 * second sees the item, clicks it, and gets an access dialog — W29's door that
 * can only produce an error, and it has been shipping on the rail. Cycle 3 does
 * not fix the rail (that is C5's data), and it does not reproduce the bug in a
 * second place either.
 *
 * So each list below is ANY-of the groups the model ACL actually grants READ
 * to, verified against `ir_model_access` on the live database:
 *
 *   Formula Studio      hr.formula.config          formula user | manager
 *   Salary Structures   hr.payroll.structure       hr user | payroll user
 *   Statutory           vietnam.insurance.policy   payroll base user | manager
 *   Integrations        hr.integration.connector   formula user | formula admin
 *   Payroll defaults    res.config.settings        base.group_system ONLY
 *
 * The demo group (`pb_demo.group_payobook_demo`) appears in three of those
 * ACLs and is deliberately NOT listed: it is a read-only demo persona, and a
 * settings hub is where configuration is changed.
 *
 * Consequence worth stating because it differs from the handover's table:
 * **Payroll defaults is an ADMINISTRATOR card, not a manager one.** Odoo grants
 * `res.config.settings` to `base.group_system` alone, and its own (hidden) menu
 * says the same. Offering it to a payroll manager would be the exact error door
 * the paragraph above exists to prevent.
 */
const FORMULA_MANAGER = "pb_hr_payroll_formula.group_formula_manager";
const FORMULA_USER = "pb_hr_payroll_formula.group_formula_user";
const FORMULA_ADMIN = "pb_hr_payroll_formula.group_formula_admin";
const HR_USER = "hr.group_hr_user";
const PAYROLL_USER = "om_hr_payroll.group_hr_payroll_user";
const PB_BASE_USER = "pb_hr_payroll_base.group_payroll_base_user";
const PB_MANAGER = "pb_hr_payroll_base.group_payroll_base_manager";
const SYSTEM = "base.group_system";

const G_FORMULA = [FORMULA_MANAGER, FORMULA_USER];
const G_STRUCTURES = [PAYROLL_USER, HR_USER];
const G_STATUTORY = [PB_BASE_USER, PB_MANAGER];
const G_INTEGRATIONS = [FORMULA_ADMIN, FORMULA_USER];
const ADMIN = [SYSTEM];

/**
 * The eight categories, in the order the mockup fixes them.
 *
 * A card is one of two kinds and never both:
 *   `tag`    a bespoke client action — opened through `openHub` with a `pb_back`
 *            return door, which the cockpit renders as a chip;
 *   `xmlid`  a native `act_window` — opened WITHOUT clearing breadcrumbs, so
 *            Odoo's own crumb is the return path.
 *
 * `sub` is the one line that says what lives there. It is a SENTENCE, built as
 * one string, because a translator cannot reorder fragments (W80).
 */
export const CATEGORIES = [
    {
        key: "formula", icon: "calculator", label: _t("Formula Engine"),
        blurb: _t("Configurations, components and shadow runs — the calculation itself."),
        groups: G_FORMULA,
        cards: [
            { id: "studio", tag: "pb_formula_studio", icon: "calculator",
              label: _t("Formula Studio"),
              sub: _t("Every configuration, its columns and its formulas, full screen.") },
        ],
    },
    {
        key: "structures", icon: "layers", label: _t("Salary Structures"),
        blurb: _t("Pay structures, their salary rules and category make-up."),
        groups: G_STRUCTURES,
        cards: [
            { id: "structures", tag: "pb_structures", icon: "layers",
              label: _t("Salary Structures"),
              sub: _t("Structures, rules and the employees each one covers.") },
        ],
    },
    {
        key: "statutory", icon: "shield", label: _t("Statutory"),
        blurb: _t("Insurance policies, tax tables and dependent relief."),
        groups: G_STATUTORY,
        cards: [
            { id: "statutory", tag: "pb_statutory", icon: "shield",
              label: _t("Insurance & Tax"),
              sub: _t("Contribution rates, ceilings, tax brackets and actuals.") },
        ],
    },
    {
        key: "integrations", icon: "database", label: _t("Integrations"),
        blurb: _t("Connectors, their field mappings and everything they have pulled."),
        groups: G_INTEGRATIONS,
        cards: [
            { id: "integrations", tag: "pb_integrations", icon: "database",
              label: _t("Integrations"),
              sub: _t("The only home for connectors — Import deep-links into it.") },
            // Integrations Cycle 2. The category's SECOND card, which is also
            // what retires Cycle 1's single-card auto-open here: `soleCard`
            // stays exactly as written and the section page comes back on its
            // own, with nothing to remember to undo.
            // JOURNEY J1 — one board, one name. The tag is unchanged: this card
            // is asserted by test_settings.py and it opens the same cockpit.
            { id: "mapping", tag: "pb_mapping_studio", icon: "gitMerge",
              label: _t("Mapping"),
              sub: _t("Wire any source — API feeds, spreadsheets, employee records — onto your payroll schemes.") },
        ],
    },
    {
        key: "payroll", icon: "settings", label: _t("Payroll defaults"),
        blurb: _t("The payroll settings screen, reachable in the product at last."),
        groups: ADMIN,
        cards: [
            { id: "payroll_defaults",
              xmlid: "om_hr_payroll.action_hr_payroll_configuration",
              icon: "settings", label: _t("Payroll settings"),
              sub: _t("The native payroll configuration form — use the crumb to come back.") },
        ],
    },
    {
        key: "roles", icon: "lock", label: _t("Roles & Access"),
        blurb: _t("Who may see and do what, across the whole product."),
        groups: ADMIN,
        cards: [
            { id: "users", xmlid: "base.action_res_users", icon: "users",
              label: _t("Users & permission groups"),
              sub: _t("Every internal user and the groups their access comes from.") },
        ],
    },
    {
        key: "org", icon: "building", label: _t("Companies & Tenants"),
        blurb: _t("The organisational scope everything else is measured in."),
        groups: ADMIN,
        cards: [
            { id: "companies", xmlid: "base.action_res_company_form",
              icon: "building", label: _t("Companies"),
              sub: _t("Legal entities, their currency and their working calendar.") },
            { id: "tenants", tag: "pb_tenants", icon: "server",
              label: _t("Tenants"),
              sub: _t("Tenant Mission Control — one platform, many databases.") },
        ],
    },
    {
        key: "nav", icon: "compass", label: _t("Navigation"),
        blurb: _t("What the left rail offers, and in what order."),
        groups: ADMIN,
        cards: [
            { id: "sidebar_items", xmlid: "pb_sidebar.action_pb_sidebar_item",
              icon: "list", label: _t("Sidebar items"),
              sub: _t("Each rail entry, the surface behind it and who may see it.") },
            { id: "sidebar_sections", xmlid: "pb_sidebar.action_pb_sidebar_section",
              icon: "layers", label: _t("Sidebar sections"),
              sub: _t("The blocks the rail entries are grouped into.") },
        ],
    },
];

/**
 * THE SOFT REGISTRY — how a later module bolts a category on.
 *
 * A module that adds a Settings category DEPENDS on this hub, so this hub can
 * never import it back; the registry is what lets the dependency run one way
 * only. It is the exact shape `pb_people_hub` has always had for its lenses,
 * and the one P7 gave `pb_payhub` (R73), P8 `pb_home_hub` (R83) and P9
 * `pb_insights_hub` (R96) — here applied to CATEGORIES rather than lenses,
 * because that is the unit this hub is made of.
 *
 *     registry.category(SETTINGS_CATEGORIES).add("vendors", {
 *         key: "vendors", icon: "briefcase", label: _t("Vendors"),
 *         blurb: _t("…"), groups: [...],
 *         cards: [{ id: "vendors", tag: "pb_vendors_board", … }],
 *     }, { sequence: 20 });
 *
 * A registered descriptor is EXACTLY a `CATEGORIES` entry and goes through
 * every rule this file already has: its gates are resolved with the same
 * fail-open pass, its cards are probed for existence, a single-card category
 * opens its one door directly, and a category nobody can use is absent rather
 * than disabled. Nothing about it is special-cased.
 *
 * The eight shipped categories carry no sequence, so bolted-on ones land after
 * them and start at 20.
 */
export const SETTINGS_CATEGORIES = "pb_settings_category";

/**
 * The registered categories, resolved ONCE per component (see `setup`).
 *
 * A getter would rebuild the array on every render and hand OWL a fresh object
 * for every card on every keystroke (W21), which is exactly the bug the
 * insights-hub test was written to prevent.
 */
export function extraCategories() {
    return registry.category(SETTINGS_CATEGORIES).getAll().filter(Boolean);
}

/**
 * The eight shipped categories plus anything a later module registered.
 *
 * A REGISTERED CATEGORY WITH A SHIPPED CATEGORY'S KEY REPLACES IT, IN PLACE.
 * That is the seam a module needs when it does not add a new door but builds a
 * BETTER ONE for a door that is already here: Navigation shipped as two raw
 * list views, and the module that owns the Access home replaces it with the
 * lens that draws the same rows as the rail itself. Registering a second "nav"
 * would leave the hub showing the word twice, and editing this file from the
 * other module would put the dependency the wrong way round.
 *
 * IN PLACE, so a replacement keeps the position the reader learnt. And only
 * where the module is actually installed: on a build without it, nothing is
 * registered and the shipped category stands exactly as it always did — which
 * is what keeps this safe on the databases the replacing module never reaches.
 */
export function allCategories() {
    const extra = extraCategories();
    const byKey = new Map(extra.map((c) => [c.key, c]));
    const shipped = CATEGORIES.map((c) => byKey.get(c.key) || c);
    const replaced = new Set(CATEGORIES.map((c) => c.key));
    return [...shipped, ...extra.filter((c) => !replaced.has(c.key))];
}

/** Every action xmlid the descriptor names, for one probe round trip. */
export function settingsActionXmlids() {
    return [...new Set(allCategories().flatMap(
        (c) => (c.cards || []).filter((k) => k.xmlid).map((k) => k.xmlid)))];
}

export class PbSettingsHub extends Component {
    static template = "pb_settings.PbSettingsHub";
    static components = { HubBackChip };
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.palette = useService("pb_hub_palette");

        // Read ONCE, from props, never written back (HubShell's rule).
        this.back = hubBack(this.props);

        // Resolved ONCE, here, never in a getter (W21). The registry cannot
        // change while a component is mounted — a module either loaded before
        // this one or it did not.
        this.all = allCategories();

        this.state = useState({
            resolved: false,
            // category key -> boolean; null while unresolved
            allowed: null,
            // action xmlid -> boolean
            present: {},
            cat: this._restoreCat(),
        });

        // One navigation at a time. Two clicks on a card 40ms apart are one
        // intent, and doAction is happy to run both (W21.1's lesson, applied to
        // navigation rather than to writes).
        this._opening = false;

        onWillStart(async () => { await this._resolve(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------- resolution
    _restoreCat() {
        try {
            return window.localStorage.getItem(STORAGE_KEY) || "";
        } catch { return ""; }         // private mode
    }

    /**
     * Two questions, asked in parallel: what may this persona see, and what is
     * actually installed here.
     */
    async _resolve() {
        const [allowed, present] = await Promise.all([
            this._resolveGroups(), this._resolveActions(),
        ]);
        this.state.allowed = allowed;
        this.state.present = present;
        this.state.resolved = true;

        // Never open on a category this persona cannot read, or one whose cards
        // all turned out to be absent: a remembered key is a preference, not a
        // permission.
        const first = this.categories[0];
        if (!this.categories.some((c) => c.key === this.state.cat)) {
            this.state.cat = first ? first.key : "";
        }
    }

    /** Fails OPEN per group — see the header. */
    async _resolveGroups() {
        const names = [...new Set(this.all.flatMap((c) => c.groups || []))];
        const flags = {};
        await Promise.all(names.map(async (g) => {
            try { flags[g] = await user.hasGroup(g); }
            catch (e) {
                console.warn("pb_settings: could not resolve group", g, e);
                flags[g] = true;
            }
        }));
        const allowed = {};
        for (const c of this.all) {
            allowed[c.key] = !(c.groups || []).length
                || c.groups.some((g) => flags[g]);
        }
        return allowed;
    }

    /**
     * Which `act_window` cards exist. One RPC for the whole descriptor.
     *
     * On failure every xmlid card is treated as ABSENT rather than present:
     * the alternative offers doors the server has just told us nothing about,
     * and an empty category is a smaller lie than a broken one. It is reported,
     * never swallowed into a decoration (W40).
     */
    async _resolveActions() {
        const xmlids = settingsActionXmlids();
        if (!xmlids.length) { return {}; }
        try {
            return await this.orm.call("pb.settings", "resolve_actions", [xmlids]);
        } catch (e) {
            console.warn("pb_settings: could not probe the action xmlids", e);
            return {};
        }
    }

    // --------------------------------------------------------------- the tree
    /** Is the thing behind this card on this database at all? */
    _cardPresent(card) {
        if (card.tag) {
            return registry.category("actions").contains(card.tag);
        }
        return !!this.state.present[card.xmlid];
    }

    cardsOf(cat) {
        return (cat.cards || []).filter((k) => this._cardPresent(k));
    }

    /**
     * The categories on the left: allowed AND with something behind them.
     *
     * While `allowed` is null the answer is "everything present", so the nav
     * never flashes empty and then fills in — the same choice HubShell makes.
     */
    get categories() {
        const allowed = this.state.allowed;
        return this.all.filter(
            (c) => (!allowed || allowed[c.key]) && this.cardsOf(c).length);
    }

    get current() {
        return this.categories.find((c) => c.key === this.state.cat)
            || this.categories[0] || null;
    }

    get currentCards() {
        const c = this.current;
        return c ? this.cardsOf(c) : [];
    }

    /**
     * A category with exactly ONE door is not a page, it is that door.
     *
     * Integrations is the case that forced it: a category headline, a blurb, a
     * single card and an "Open" button, so reaching the connectors cost two
     * clicks and one screen that said the same word three times. The rule is
     * GENERIC rather than a special case for that key — the moment Cycle 2 adds
     * a second card to the category, the section page comes back on its own,
     * with nothing to remember to undo.
     *
     * Resolved AFTER `_resolveGroups` and `_cardPresent`, so "one card" means
     * one card THIS persona can actually see on THIS database: a category whose
     * second card is absent behaves like a single-card one, which is the honest
     * answer rather than a page listing one tile.
     */
    soleCard(cat) {
        const cards = this.cardsOf(cat);
        return cards.length === 1 ? cards[0] : null;
    }

    /** A CLICK handler. */
    setCat(key) {
        const cat = this.categories.find((c) => c.key === key);
        const sole = cat && this.soleCard(cat);
        if (sole) {
            // Straight through. `state.cat` is NOT moved and nothing is
            // persisted: the remembered rail state is a preference about which
            // PAGE to show, and this category does not have one — writing it
            // would bring the user back to a section page that only exists to
            // be skipped. The way back is the `pb_back` chip openCard writes.
            this.openCard(sole);
            return;
        }
        if (this.state.cat === key) { return; }
        this.state.cat = key;
        try { window.localStorage.setItem(STORAGE_KEY, key); }
        catch { /* private mode */ }
    }

    // ----------------------------------------------------------------- doors
    /**
     * The return door every cockpit card hands out.
     *
     * By XMLID, not by tag. A bare tag makes the action service build
     * `{type: "ir.actions.client", tag}` with no NAME, and the breadcrumb the
     * four native cards return through then reads "Unnamed" — a way back that
     * does not say where it goes. Found on the live run; the xmlid carries the
     * record, and the record is called Settings.
     */
    get backToSettings() {
        return { label: _t("Settings"),
                 xmlid: "pb_settings.action_pb_settings_hub" };
    }

    /**
     * Open what a card names.
     *
     * A CLICK handler, and the only place in this file that navigates.
     * `_opening` is not reset on success on purpose: the surface is being
     * replaced, so there is no second click to serve — and if the navigation
     * FAILS, the catch puts it back so the card is not left dead.
     */
    openCard(card) {
        if (this._opening) { return; }
        this._opening = true;
        try {
            if (card.tag) {
                // `context` is per-card and optional: a card that wants to land
                // its cockpit on a particular lens or scope says so in the
                // descriptor, and `openHub` merges it (hub_nav.js:63). Nothing
                // needs it today; the alternative is every future deep-linking
                // card editing this method.
                openHub(this.actionService, {
                    tag: card.tag,
                    context: card.context || {},
                    back: this.backToSettings,
                });
            } else {
                // Native Odoo views. `clearBreadcrumbs: false` keeps "Settings"
                // in the trail — these render Odoo's control panel, so the crumb
                // is visible and is the return path a back chip cannot be here.
                this.actionService.doAction(card.xmlid, { clearBreadcrumbs: false });
            }
        } catch (e) {
            this._opening = false;
            console.warn("pb_settings: card failed to open", card.id, e);
        }
    }

    openPalette() { this.palette.open(); }

    /** "Command K" on macOS, "Ctrl K" elsewhere — the label must match the key. */
    get paletteHint() { return isMacOS() ? "\u2318K" : "Ctrl K"; }

    // ----------------------------------------------------------------- empty
    get emptyTitle() { return _t("Nothing here is available to you."); }

    get emptyNote() {
        return _t("Settings collects the surfaces that change how payroll is "
                  + "configured. Your account holds none of the groups that "
                  + "may change them.");
    }
}

registry.category("actions").add("pb_settings_hub", PbSettingsHub);
