/** @odoo-module **/
/**
 * `<PbInbox/>` — one inbox for every decision, whoever you are.
 *
 * THE OLD WAY WAS THREE INBOXES. A pay-run board, a workforce list and a
 * scheme queue, each with its own idea of what "waiting for me" meant, and none
 * of them able to say what a person actually owed anybody today. This is the
 * one screen that replaces them: every process, one set of tabs, one card
 * shape, one drawer.
 *
 * "MY TURN" IS A SEAT AND NOTHING ELSE. A card is mine when an open seat on the
 * step that is waiting names me — my own, or one I am covering while somebody
 * is away. Never "somebody in my team", never "anyone in HR". The server
 * decides it; the ring around the card is only how it is drawn.
 *
 * MONEY IS NEVER ADDED ACROSS CURRENCIES. The summary line above the cards says
 * "620,000,000 VND · 4,200 SGD", because one number there would be a lie.
 *
 * A BLOCKED CARD CARRIES ITS OWN REPAIR. "Nobody holds HR lead for Operations"
 * is not an error to report to somebody; it is a sentence with a door under it.
 *
 * AND "ASK FOR A SIGN-OFF" IS HERE. Anything that has no process of its own can
 * still be sent to the right person, through the same route machinery and the
 * same trail as everything else.
 */
import {
    Component, onMounted, onPatched, onWillStart, onWillUnmount, useExternalListener,
    useState, useRef,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { useNavigationState } from "@pb_hub/js/navigation_state";
import { RequestDrawer } from "@pb_approval_config/js/request_drawer";
import { initials, money, when } from "@pb_approval_config/js/sentence";
import { FilterKit } from "@pb_filter_kit/js/filter_kit";
import { PbFilterLayout } from "@pb_filter_kit/js/filter_components";

const PAGE = 60;
/** The four tabs, as the filter panel's first four views (same words). */
const TAB_FILTERS = {
    mine: { my_turn: ["yes"] },
    all: { pile: ["waiting"] },
    returned: { pile: ["returned"] },
    done: { pile: ["done"] },
};

/**
 * PAYAI P4 — a door may open the inbox ON one request: the arrival carries
 * `pb_focus: "request:<id>"` (or `"request:<id>:<scope>"` when the request was
 * found under "My team" / "Everyone"). Anything else in `pb_focus` ("queue",
 * "month:2026-06") is another screen's word and is left alone. Navigation
 * only: the drawer re-reads the request with the person's own rights, exactly
 * as a click on its card would.
 *
 * Takes either an action context (`pb_focus`) or the hub's arrival payload
 * (`focus`, see `inboxArrival`).
 */
const FOCUS_SCOPES = ["me", "team", "org"];
export function focusRequest(context) {
    const raw = context && (context.pb_focus || context.focus);
    const m = /^request:(\d+)(?::(me|team|org))?$/.exec(String(raw || ""));
    if (!m) { return null; }
    const scope = FOCUS_SCOPES.includes(m[2]) ? m[2] : "me";
    return { id: Number(m[1]), scope };
}

/**
 * NAV P3c — a door may open the inbox with one AREA already chosen:
 * `pb_focus: "area:time"` lights the Time chip, exactly as pressing it would
 * (Home › TEAM's "Waiting on you" tiles). An unknown area is ignored; the
 * `request:<id>` form above keeps working and wins when both could apply.
 */
const FOCUS_AREAS = ["pay", "money", "data", "people", "time", "setup",
                     "platform", "other"];
export function focusArea(context) {
    const raw = context && (context.pb_focus || context.focus);
    const m = /^area:([a-z]+)$/.exec(String(raw || ""));
    return m && FOCUS_AREAS.includes(m[1]) ? m[1] : "";
}

/**
 * PAYAI FIX-1 (P4:link-1) — WHERE THE DEEP LINK REACHES THE INBOX.
 *
 * As the Home hub's Approvals lens, the inbox is handed the hub's arrival
 * payload as the `arrival` prop (the lens says `wantsArrival`, exactly like
 * Pulse); as the standalone client action, its own `action.context`. Those
 * two and nothing else. The action service's current action is NOT a source:
 * on this version it is a Promise, and while a lens is being set up it is
 * still the PREVIOUS screen's action — the deep link silently did nothing.
 *
 * The object returned is the one a "consumed once" guard keys on, so it must
 * keep its identity: the hub builds its arrival payload once per visit.
 */
export function inboxArrival(props) {
    const arrival = props && props.arrival;
    if (arrival && arrival.focus) { return arrival; }
    const own = props && props.action && props.action.context;
    if (own && own.pb_focus) { return own; }
    // The Records Desk, Statutory and the tenant console open the inbox ON a
    // request with `params: { request_id }` — the same door, a different key.
    const params = props && props.action && props.action.params;
    if (params && params.request_id) {
        // one arrival object per door, so "consumed once" still holds
        if (!_paramArrivals.has(params)) {
            _paramArrivals.set(params, { focus: "request:" + Number(params.request_id) });
        }
        return _paramArrivals.get(params);
    }
    return null;
}
const _paramArrivals = new WeakMap();
// One arrival opens one drawer: a lens re-mounted later (tab away and back)
// does not pop the same request open again.
const _consumedFocus = new WeakSet();
// The same for an area: chosen once on arrival, never again on a re-mount.
const _consumedArea = new WeakSet();

export class PbInbox extends Component {
    static template = "pb_approval_config.PbInbox";
    static components = { RequestDrawer, PbFilterLayout };
    static props = {
        embedded: { type: Boolean, optional: true },
        action: { type: Object, optional: true },
        // The Home hub's deep link (`wantsArrival`): `{ lens, focus }`.
        arrival: { type: Object, optional: true },
        // WHOSE QUEUE THIS IS. "me" is everything I am part of; "team" is
        // everything waiting about somebody who works for me — the Workforce
        // screen a manager used to have, now the same inbox as everything
        // else. A scope is a way of LOOKING, never a permission: the decide
        // buttons come from the seat, which the server re-checks every time.
        scope: { type: String, optional: true },
        "*": true,
    };

    setup() {
        this.ic = ic;
        this.initials = initials;
        this.money = money;
        this.when = when;
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.actionService = useService("action");

        if (!this.props.embedded && this.env.config
                && this.env.config.setDisplayName) {
            this.env.config.setDisplayName(_t("Approvals"));
        }

        this.state = useState({
            loading: true,
            failed: "",
            scope: this.props.scope || "me",
            data: null,
            // the cards the filter panel produced, one page at a time
            cards: [],
            total: 0,
            money: [],
            listLoaded: false,
            loadingMore: false,
            openId: 0,
            asking: false,
            ask: { name: "", description: "", amount: 0, area_key: "" },
            askOptions: null,
            busy: false,
        });

        this.navigationRoot = useRef("navigationRoot");
        // Going to a record and back: the scope and the open drawer come back
        // from here; the filters, from the panel's own memory of this tab.
        const savedNavigation = useNavigationState(this, "approvals", () => ({
            scope: this.state.scope, openId: this.state.openId,
            scrollTop: this.navigationRoot.el?.scrollTop || 0,
        }));
        if (savedNavigation) {
            if (FOCUS_SCOPES.includes(savedNavigation.scope)) {
                this.state.scope = savedNavigation.scope;
            }
            this.state.openId = savedNavigation.openId || 0;
        }

        // The shared filter panel (pb_filter_kit). Built by hand rather than
        // with useFilterKit, because a door has to find its request's pile
        // and scope BEFORE the panel's first load (one read, on the right
        // queue). The scope rides on every panel call as `pbf_ctx.scope`.
        this.kit = useState(new FilterKit({
            orm: this.orm,
            notification: this.notif,
            model: "pb.approval.inbox",
            noun: _t("requests"),
            ctx: { scope: this.state.scope },
            onChange: () => this.loadPage(),
        }));
        useExternalListener(window, "resize", () => this.kit.onResize());
        onWillUnmount(() => this.kit.destroy());
        // ai-tabs (42 lessons) points at the four tabs, which are now the
        // panel's view row: the anchor is put on that row (see report: a kit
        // option for it is a kit gap).
        const tagTabs = () => {
            const row = this.navigationRoot.el && this.navigationRoot.el.querySelector(".pbf-views");
            if (row && row.getAttribute("data-coach") !== "ai-tabs") {
                row.setAttribute("data-coach", "ai-tabs");
            }
        };
        let observer = null;
        onMounted(() => {
            tagTabs();
            if (this.navigationRoot.el && window.MutationObserver) {
                observer = new MutationObserver(tagTabs);
                observer.observe(this.navigationRoot.el, { childList: true, subtree: true });
            }
        });
        onPatched(tagTabs);
        onWillUnmount(() => observer && observer.disconnect());
        onMounted(() => {
            if (this.navigationRoot.el && savedNavigation) {
                this.navigationRoot.el.scrollTop = savedNavigation.scrollTop || 0;
            }
        });
        this.onEscape = this.onEscape.bind(this);
        const arrival = inboxArrival(this.props);
        const focus = focusRequest(arrival);
        // A request focus always wins (PayAI's doors): it is never combined
        // with an area, so the drawer opens on whatever area the request is.
        const area = focus ? "" : focusArea(arrival);
        if (area && !_consumedArea.has(arrival)) {
            _consumedArea.add(arrival);
            // "Waiting on you" in one area (Home › Team): my turn, that area
            this.kit.initial = { filters: { my_turn: ["yes"], area: [area] } };
        }
        onWillStart(async () => {
            // Find the pile first, so the list is read ONCE, on the view and
            // scope where the request really is.
            if (focus && !_consumedFocus.has(arrival)) {
                _consumedFocus.add(arrival);
                await this.locateFocused(focus);
            }
            this.kit.ctx = { scope: this.state.scope };
            await Promise.all([this.load(), this.kit.load()]);
        });
        onMounted(() => {
            window.addEventListener("keydown", this.onEscape,
                                    { capture: true });
        });
        onWillUnmount(() => {
            window.removeEventListener("keydown", this.onEscape,
                                       { capture: true });
        });
    }

    /**
     * Open one request's drawer on the tab and scope that list it — "My turn"
     * when it is waiting for me, else "All I can see", "Sent back" or
     * "Finished" (P4:link-3: a decided request is not in flight any more).
     * The server says which pile; a request that is gone or not mine to read
     * is a notice, never a drawer over the wrong list (P4:link-4).
     */
    async locateFocused(focus) {
        let where = null;
        try {
            where = await this.orm.call(
                "pb.approval.inbox", "locate_request", [focus.id, focus.scope]);
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                || _t("This request could not be opened."), { type: "warning" });
            return;
        }
        if (!where || !where.tab) {
            this.notif.add(_t("This request could not be opened."),
                           { type: "warning" });
            return;
        }
        if (FOCUS_SCOPES.includes(where.scope)) { this.state.scope = where.scope; }
        // the panel opens on the tab's view, so closing the drawer leaves the
        // reader on the pile that lists the request
        this.kit.initial = { filters: TAB_FILTERS[where.tab] || {}, viewKey: where.tab };
        this.state.openId = where.id;
    }

    onEscape(ev) {
        if (ev.key !== "Escape") { return; }
        if (this.state.openId) { this.state.openId = 0; return; }
        if (this.state.asking) { this.state.asking = false; }
    }

    // ============================================================== reading
    /** What does not depend on the filters: who may look wider, the cover
     *  notes, the areas. */
    async load() {
        this.state.loading = true;
        this.state.failed = "";
        try {
            this.state.data = await this.orm.call(
                "pb.approval.inbox", "get_inbox_head", [],
                { context: { pbf_ctx: { scope: this.state.scope } } });
            if (this.state.data && FOCUS_SCOPES.includes(this.state.data.scope)) {
                this.state.scope = this.state.data.scope;
            }
        } catch (error) {
            this.state.failed = (error.data && error.data.message)
                || _t("Your approvals could not be read.");
        } finally {
            this.state.loading = false;
        }
    }

    /** One page of cards for the panel's current filters, in this scope. */
    async loadPage({ more = false } = {}) {
        const q = this.kit.query;
        const offset = more ? this.state.cards.length : 0;
        if (more) { this.state.loadingMore = true; }
        try {
            const d = await this.orm.call("pb.approval.inbox", "get_inbox_page", [], {
                filters: q.filters, search: q.search, sort: q.sort, offset, limit: PAGE,
                context: { pbf_ctx: { scope: this.state.scope } },
            });
            if (!this.kit.isCurrent(q.seq)) { return; }
            this.state.cards = more ? [...this.state.cards, ...d.cards] : d.cards;
            this.state.total = d.total;
            this.state.money = more ? this._mergeMoney(this.state.money, d.money) : (d.money || []);
            this.state.listLoaded = true;
        } catch (error) {
            if (this.kit.isCurrent(q.seq)) {
                this.notif.add((error.data && error.data.message)
                    || _t("Your approvals could not be listed. Try again in a moment."),
                    { type: "danger" });
                this.state.listLoaded = true;
            }
        } finally {
            this.state.loadingMore = false;
        }
    }

    /** Amounts per currency, added within one currency only. */
    _mergeMoney(a, b) {
        const out = {};
        for (const row of [...(a || []), ...(b || [])]) {
            out[row.currency] = (out[row.currency] || 0) + row.amount;
        }
        return Object.entries(out).sort().map(([currency, amount]) => ({ currency, amount }));
    }

    loadMore() {
        if (!this.state.loadingMore) { this.loadPage({ more: true }); }
    }
    get hasMore() { return this.state.cards.length < this.state.total; }
    get nextPage() { return Math.min(PAGE, this.state.total - this.state.cards.length); }

    get data() {
        return this.state.data
            || { areas: [], covering_for: [], covered_by: [] };
    }

    get cards() { return this.state.cards; }

    /** Which of the four tabs is showing, when one is (exactly, unchanged). */
    get tab() {
        const key = this.kit.viewKey;
        return TAB_FILTERS[key] && !this.kit.dirty ? key : "";
    }

    get filtered() {
        return Boolean(this.kit.activeCount || this.kit.search);
    }

    get emptyCopy() {
        const copy = {
            mine: {
                title: _t("Nothing is waiting for you"),
                sub: _t("When a request reaches your step it lands here, with the facts and everything attached."),
            },
            all: {
                title: _t("Nothing is in flight"),
                sub: _t("Requests appear here from every part of the product as people send them in."),
            },
            returned: {
                title: _t("Nothing has been sent back"),
                sub: _t("Anything a decider returns for changes shows up here."),
            },
            done: {
                title: _t("Nothing is finished yet"),
                sub: _t("Approved, applied and turned-down requests are kept here."),
            },
        }[this.tab];
        if (copy) { return copy; }
        if (this.kit.search && !this.kit.chips.length) {
            return {
                title: _t("No request matches “%s”", this.kit.search),
                sub: _t("Check the spelling, or search by what it is, who sent it in or the kind of request."),
            };
        }
        return {
            title: _t("No request matches these filters"),
            sub: _t("Remove a filter above, or go back to what is waiting for you."),
        };
    }

    get moneyLine() {
        return (this.state.money || [])
            .map((row) => money(row.amount, row.currency)).join(" · ");
    }

    // =============================================================== acting
    async setScope(key) {
        if (this.state.scope === key) { return; }
        this.state.scope = key;
        this.state.openId = 0;
        this.state.listLoaded = false;
        // the same view in the new queue: the panel recounts for it
        const keep = { filters: this.kit.filters, search: this.kit.search, viewKey: this.kit.viewKey };
        await Promise.all([
            this.load(),
            this.kit.reconfigure({ ctx: { scope: key }, initial: keep }),
        ]);
    }

    get scopes() {
        const data = this.data;
        const rows = [{ key: "me", label: _t("Mine") }];
        if (data.has_team || this.state.scope === "team") {
            rows.push({ key: "team", label: _t("My team") });
        }
        if (data.can_org || this.state.scope === "org") {
            rows.push({ key: "org", label: _t("Everyone") });
        }
        return rows.length > 1 ? rows : [];
    }

    /** Back to the start view (My turn). */
    showMine() { this.kit.useView("mine"); }

    open(card) { this.state.openId = card.id; }
    close() { this.state.openId = 0; }

    async refresh() {
        await Promise.all([this.load(), this.kit.refresh()]);
    }

    openMatrix() {
        this.actionService.doAction(
            "pb_approval_config.action_pb_approval_matrix");
    }

    // ------------------------------------------------- ask for a sign-off
    async openAsk() {
        this.state.asking = true;
        this.state.ask = { name: "", description: "", amount: 0,
                           area_key: "" };
        if (!this.state.askOptions) {
            try {
                this.state.askOptions = await this.orm.call(
                    "pb.approval.inbox", "ask_options", []);
            } catch (error) {
                this.state.askOptions = { areas: [], currency_name: "" };
            }
        }
    }

    closeAsk() { this.state.asking = false; }

    setAsk(field, ev) {
        const value = field === "amount"
            ? Number(ev.target.value || 0) : ev.target.value;
        this.state.ask[field] = value;
    }

    get canAsk() {
        return this.state.ask.name.trim().length > 2;
    }

    async sendAsk() {
        this.state.busy = true;
        try {
            const options = this.state.askOptions || { areas: [] };
            const area = (options.areas || []).find(
                (one) => one.key === this.state.ask.area_key);
            const made = await this.orm.call("pb.approval.inbox", "ask", [{
                name: this.state.ask.name,
                description: this.state.ask.description,
                amount: this.state.ask.amount,
                area_key: this.state.ask.area_key || false,
                area_label: area ? area.label : "",
            }]);
            this.state.asking = false;
            await this.refresh();
            if (made.request_id) { this.state.openId = made.request_id; }
            this.notif.add(
                _t("Sent. It is on its way to whoever decides this kind of request."),
                { type: "success" });
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                || _t("That could not be sent."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category("actions").add("pb_approval_inbox", PbInbox);
