/** @odoo-module **/
/**
 * `pb_voice_board` — Talent › Voice: employee surveys for HR.
 *
 * QUIET BOARD: the glance is grey at zero and lights only what needs a hand
 * (a round being set up, plans that are late). A round is at exactly one of
 * three places: being set up, open for answers, closed.
 *
 * NO ANSWER IS EVER SENT TO THIS SCREEN. Results come from `pb.voice`
 * (`get_results`) with the floor and the secondary suppression applied on
 * the server; a hidden group arrives with no figure at all. Results open
 * only after a round closes.
 *
 * R1 — no `t-as` variable is named lt/gt/lte/gte/and/or/not/in (UPDATES G60).
 * R2 — icons are the filter kit's CACHED markup (`pbfIcon`; OWL flicker).
 * R3 — every sentence is a `_t()` literal or comes translated from the server.
 */
import { Component, useState, onWillStart, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { pbfIcon } from "@pb_filter_kit/js/filter_kit";
import { openHub } from "@pb_hub/js/hub_nav";

const TABS_OPEN = ["overview", "who"];
const TABS_CLOSED = ["overview", "who", "results", "plans"];

export class PbVoiceBoard extends Component {
    static template = "pb_voice.PbVoiceBoard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.state = useState({
            loaded: false, allowed: true, why: "",
            rounds: [], kpis: {}, mailOn: true, hasValues: false,
            filter: "",
            round: null, roundBusy: false, tab: "overview",
            results: null, resultsBusy: false, group: "all",
            plan: null, owners: [], planBusy: false,
            confirm: null,
        });
        useExternalListener(window, "keydown", (ev) => this.onKey(ev));
        onWillStart(async () => { await this.load(); });
    }

    icon(name, size = 16) { return pbfIcon(name, size); }

    // ------------------------------------------------------------ loading
    async load() {
        try {
            const d = await this.orm.call("pb.voice", "get_board", []);
            Object.assign(this.state, {
                allowed: d.allowed !== false, why: d.why || "",
                rounds: d.rounds || [], kpis: d.kpis || {},
                mailOn: !!d.mail_on, hasValues: !!d.has_values,
            });
        } catch (e) {
            console.warn("pb_voice: the board could not be read", e);
            this.state.allowed = false;
            this.state.why = _t("The surveys could not be read just now.");
        } finally {
            this.state.loaded = true;
        }
    }

    // --------------------------------------------------------- the glance
    get glance() {
        const k = this.state.kpis || {};
        const pick = (key) => () => { this.state.filter = this.state.filter === key ? "" : key; };
        return [
            { key: "draft", n: k.draft || 0, label: _t("being set up"), tone: k.draft ? "amber" : "", run: pick("draft") },
            { key: "open", n: k.open || 0, label: _t("open for answers"), tone: "", run: pick("open") },
            { key: "closed", n: k.results || 0, label: _t("with results"), tone: "", run: pick("closed") },
            { key: "actions", n: k.actions || 0, label: k.late ? _t("action plans, some late") : _t("action plans to do"), tone: k.late ? "rose" : "", run: null },
        ];
    }
    get glanceOn() { return this.state.filter; }
    get rounds() {
        const f = this.state.filter;
        return f ? this.state.rounds.filter((r) => r.state === f) : this.state.rounds;
    }
    barStyle(pct) { return `width: ${Math.max(0, Math.min(100, pct || 0))}%`; }

    // ------------------------------------------------------------ a round
    async openRound(row, tab = null) {
        this.state.roundBusy = true;
        this.state.results = null;
        this.state.plan = null;
        if (!this.state.round || this.state.round.id !== row.id) {
            this.state.round = { ...row, loading: true };
            this.state.tab = tab || (row.state === "closed" ? "results" : "overview");
            this.state.group = "all";
        } else if (tab) {
            this.state.tab = tab;
        }
        try {
            this.state.round = await this.orm.call("pb.voice", "get_round", [row.id]);
            if (this.state.tab === "results" || this.state.tab === "plans") {
                await this.loadResults();
            }
        } catch (e) {
            this.notif.add(this._msg(e, _t("This survey could not be opened.")), { type: "danger" });
            this.state.round = null;
        } finally {
            this.state.roundBusy = false;
        }
    }
    closeRound() { this.state.round = null; this.state.results = null; this.state.plan = null; }
    get tabs() {
        const r = this.state.round;
        if (!r) { return []; }
        const keys = r.state === "closed" ? TABS_CLOSED : TABS_OPEN;
        const labels = {
            overview: _t("Overview"), who: _t("Who can answer"),
            results: _t("Results"), plans: _t("Action plans"),
        };
        return keys.map((k) => ({ key: k, label: labels[k] }));
    }
    async pickTab(key) {
        this.state.tab = key;
        if ((key === "results" || key === "plans") && !this.state.results) {
            await this.loadResults();
        }
    }

    async loadResults() {
        const r = this.state.round;
        if (!r) { return; }
        this.state.resultsBusy = true;
        try {
            this.state.results = await this.orm.call("pb.voice", "get_results", [r.id], {
                group: this.state.group,
            });
        } catch (e) {
            this.notif.add(this._msg(e, _t("The results could not be read.")), { type: "danger" });
        } finally {
            this.state.resultsBusy = false;
        }
    }
    async pickGroup(ev) {
        const v = ev.target.value;
        this.state.group = v === "all" ? "all" : parseInt(v, 10);
        await this.loadResults();
    }
    groupLabel(g) {
        const base = g.parent ? `${g.name} · ${g.parent}` : g.name;
        return g.shown ? base : `${base} — ${_t("hidden")}`;
    }
    pct(n) { return `${n || 0}%`; }
    signed(n) { return (n > 0 ? "+" : "") + (n || 0); }
    downloadUrl() { return `/pb_voice/results/${this.state.round.id}.xlsx`; }

    // ------------------------------------------------------------- moves
    newRound() {
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "pb.voice.round",
            views: [[false, "form"]], target: "current", name: _t("New survey"),
        });
    }
    editRound() {
        const r = this.state.round;
        if (!r) { return; }
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "pb.voice.round", res_id: r.id,
            views: [[false, "form"]], target: "current", name: r.name,
        });
    }
    openLibrary() { this.action.doAction("pb_voice.action_pb_voice_library"); }
    openAccess() {
        openHub(this.action, {
            xmlid: "biz_access.action_pb_access_board", lens: "people",
            back: { label: _t("Talent"), xmlid: "pb_talent_hub.action_pb_talent_hub" },
        });
    }
    ask(verb) {
        const texts = {
            open: [_t("Send this survey out now?"), _t("People see it on My Payobook at once. Its questions and who is asked cannot change afterwards."), _t("Send out")],
            close: [_t("Close this survey now?"), _t("Nobody can answer afterwards. The answers go in all at once and the results open."), _t("Close now")],
            delete: [_t("Delete this survey?"), _t("It has not been sent out, so nobody has seen it."), _t("Delete")],
            copy: [_t("Copy this survey?"), _t("Same questions and people, as a new survey being set up."), _t("Copy")],
        };
        const [title, body, button] = texts[verb];
        this.state.confirm = { verb, title, body, button };
    }
    cancelAsk() { this.state.confirm = null; }
    async doAsk() {
        const c = this.state.confirm;
        const r = this.state.round;
        if (!c || !r) { return; }
        this.state.roundBusy = true;
        try {
            const res = await this.orm.call("pb.voice", "round_move", [r.id, c.verb]);
            this.state.confirm = null;
            this.notif.add(res.msg || _t("Done."), { type: "success" });
            await this.load();
            if (res.deleted) {
                this.closeRound();
            } else if (c.verb === "close") {
                this.state.results = null;
                await this.openRound({ id: r.id }, "results");
            } else {
                await this.openRound({ id: res.id || r.id });
            }
        } catch (e) {
            this.state.confirm = null;
            this.notif.add(this._msg(e, _t("That could not be done.")), { type: "danger" });
        } finally {
            this.state.roundBusy = false;
        }
    }

    // ------------------------------------------------------- action plans
    newPlan(theme = "") {
        const themes = (this.state.round && this.state.round.themes) || [];
        this.state.plan = {
            id: 0, name: "", theme: theme || (themes[0] && themes[0].key) || "other",
            owner_id: 0, owner: "", date_due: "", state: "open", progress: "",
        };
        this.state.owners = [];
    }
    editPlan(p) { this.state.plan = { ...p }; this.state.owners = []; }
    cancelPlan() { this.state.plan = null; }
    onPlan(field, ev) { this.state.plan[field] = ev.target.value; }
    async onOwnerSearch(ev) {
        const term = ev.target.value;
        this.state.plan.owner = term;
        this.state.plan.owner_id = 0;
        if (!term || term.length < 2) { this.state.owners = []; return; }
        try {
            this.state.owners = await this.orm.call("pb.voice", "owner_options", [term]);
        } catch {
            this.state.owners = [];
        }
    }
    pickOwner(u) { this.state.plan.owner_id = u.id; this.state.plan.owner = u.name; this.state.owners = []; }
    async savePlan() {
        const p = this.state.plan;
        if (!p.name.trim()) { this.notif.add(_t("Say what will be done, in a few words."), { type: "warning" }); return; }
        if (!p.owner_id && !p.id) { this.notif.add(_t("Pick who owns it."), { type: "warning" }); return; }
        this.state.planBusy = true;
        try {
            const vals = { name: p.name, theme: p.theme, date_due: p.date_due || false, state: p.state, progress: p.progress };
            if (p.owner_id) { vals.owner_id = p.owner_id; }
            await this.orm.call("pb.voice", "save_action", [this.state.round.id, vals], { action_id: p.id || null });
            this.state.plan = null;
            this.notif.add(_t("Saved. The owner sees it on their home page."), { type: "success" });
            await this.loadResults();
            await this.load();
        } catch (e) {
            this.notif.add(this._msg(e, _t("The action plan could not be saved.")), { type: "danger" });
        } finally {
            this.state.planBusy = false;
        }
    }

    // ------------------------------------------------------------ plumbing
    onKey(ev) {
        if (ev.key !== "Escape") { return; }
        if (this.state.confirm) { this.state.confirm = null; return; }
        if (this.state.plan) { this.state.plan = null; return; }
        if (this.state.round) { this.closeRound(); }
    }
    _msg(e, fallback) {
        if (e && e.message && e.message.data && e.message.data.message) { return e.message.data.message; }
        if (e && e.data && e.data.message) { return e.data.message; }
        return fallback;
    }
}

registry.category("actions").add("pb_voice_board", PbVoiceBoard);
