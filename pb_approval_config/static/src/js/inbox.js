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
    Component, onMounted, onWillStart, onWillUnmount, useState,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { RequestDrawer } from "@pb_approval_config/js/request_drawer";
import { initials, money, when } from "@pb_approval_config/js/sentence";

export class PbInbox extends Component {
    static template = "pb_approval_config.PbInbox";
    static components = { RequestDrawer };
    static props = {
        embedded: { type: Boolean, optional: true },
        action: { type: Object, optional: true },
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
            tab: "mine",
            scope: this.props.scope || "me",
            data: null,
            area: "",
            due: "",
            openId: 0,
            asking: false,
            ask: { name: "", description: "", amount: 0, area_key: "" },
            askOptions: null,
            busy: false,
        });

        this.onEscape = this.onEscape.bind(this);
        onWillStart(async () => { await this.load(); });
        onMounted(() => {
            window.addEventListener("keydown", this.onEscape,
                                    { capture: true });
        });
        onWillUnmount(() => {
            window.removeEventListener("keydown", this.onEscape,
                                       { capture: true });
        });
    }

    onEscape(ev) {
        if (ev.key !== "Escape") { return; }
        if (this.state.openId) { this.state.openId = 0; return; }
        if (this.state.asking) { this.state.asking = false; }
    }

    // ============================================================== reading
    async load() {
        this.state.loading = true;
        this.state.failed = "";
        try {
            this.state.data = await this.orm.call(
                "pb.approval.inbox", "list_requests",
                [this.state.tab,
                 { area: this.state.area || false,
                   due: this.state.due || false },
                 false,
                 this.state.scope]);
        } catch (error) {
            this.state.failed = (error.data && error.data.message)
                || _t("Your approvals could not be read.");
        } finally {
            this.state.loading = false;
        }
    }

    get data() {
        return this.state.data
            || { cards: [], counts: {}, areas: [], money: [] };
    }

    get cards() { return this.data.cards || []; }

    get tabs() {
        const counts = this.data.counts || {};
        return [
            { key: "mine", label: _t("My turn"), count: counts.mine || 0 },
            { key: "all", label: _t("All I can see"), count: counts.all || 0 },
            { key: "returned", label: _t("Sent back"),
              count: counts.returned || 0 },
            { key: "done", label: _t("Finished"), count: counts.done || 0 },
        ];
    }

    get emptyCopy() {
        return {
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
        }[this.state.tab];
    }

    get moneyLine() {
        return (this.data.money || [])
            .map((row) => money(row.amount, row.currency)).join(" · ");
    }

    // =============================================================== acting
    async setTab(key) {
        this.state.tab = key;
        this.state.openId = 0;
        await this.load();
    }

    async setScope(key) {
        if (this.state.scope === key) { return; }
        this.state.scope = key;
        this.state.openId = 0;
        await this.load();
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

    async setArea(key) {
        this.state.area = this.state.area === key ? "" : key;
        await this.load();
    }

    async setDue(key) {
        this.state.due = this.state.due === key ? "" : key;
        await this.load();
    }

    open(card) { this.state.openId = card.id; }
    close() { this.state.openId = 0; }

    async refresh() {
        await this.load();
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
            await this.load();
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
