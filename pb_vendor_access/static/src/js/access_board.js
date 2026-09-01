/** @odoo-module **/
/**
 * `pb_access_board` — the Access & delegation panel behind the Settings cog.
 *
 * TWO TABS, AND THEY ANSWER THE TWO QUESTIONS PEOPLE ACTUALLY ASK.
 *
 *   **Roles** — "who can do what". Each role is a card carrying its plain name,
 *   the sentence saying WHAT IT LETS SOMEONE DO, and the faces of the people
 *   who hold it. The sentence is the hero: a permission group called "Manager"
 *   tells nobody anything, and every mistake this screen exists to prevent
 *   starts with somebody granting a thing they could not name.
 *
 *   **Hand-overs** — "who is covering for whom". A running hand-over shows the
 *   days left on it, because the thing worth knowing about temporary access is
 *   when it stops being temporary.
 *
 * THE DIALOG SHOWS THE SENTENCE BEFORE THE BUTTON. Granting and delegating both
 * put the description in front of the person doing it, at full size, with the
 * name of the person it will apply to. No confirmation dialog that only says
 * "Are you sure?" — a question nobody can answer is not a safety rail.
 *
 * THE ADMINISTRATOR PERMISSION IS NOT ON THIS SCREEN AND CANNOT BE PUT ON IT.
 * The catalogue excludes it, the model refuses it and the facade refuses it
 * again. This file does not need to know that, and deliberately does not check
 * — a client-side check on a server-side absolute is a check that will one day
 * be the only one.
 *
 * R1 — no `t-as` variable is named lt / gt / lte / gte / and / or / not / in.
 * R2 — every sentence is ONE expression.
 * R82 — people are drawn with `avatar_128`, never `image_128`: the latter
 * renders a grey camera when the field is unset, which answers 200 and looks
 * broken only to a human.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";

export class PbAccessBoard extends Component {
    static template = "pb_vendor_access.PbAccessBoard";
    static components = { HubBackChip };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");

        this.back = hubBack(this.props);

        this.state = useState({
            loaded: false,
            failed: "",
            board: null,

            tab: "roles",              // roles | handovers
            area: "",
            search: "",
            open: 0,                   // the role whose holders are expanded

            // grant / remove
            granting: null,            // { profile, mode: "grant" | "remove" }
            grantTarget: { id: 0, name: "" },
            grantReason: "",
            people: [],

            // delegate
            delegating: false,
            hand: {
                delegate_user_id: 0, delegate: "", profile_ids: [],
                kind: "temporary", date_start: "", date_end: "", reason: "",
            },

            busy: false,
        });

        onWillStart(async () => { await this.load(); });
    }

    ic(n, s = 16) { return ic(n, s); }

    // ------------------------------------------------------------- reading
    async load() {
        try {
            this.state.board = await this.orm.call("pb.access", "get_board", [
                this.state.area || null, this.state.search || null,
            ]);
            this.state.failed = "";
        } catch (e) {
            this.state.board = null;
            this.state.failed = this._msg(
                e, _t("The access board could not be read."));
        } finally {
            this.state.loaded = true;
        }
    }

    async reload() {
        this.state.loaded = false;
        await this.load();
    }

    get board() { return this.state.board || {}; }
    get profiles() { return this.board.profiles || []; }
    get delegations() { return this.board.delegations || []; }
    get kpis() { return this.board.kpis || {}; }
    get canManage() { return Boolean(this.board.can_manage); }
    get mine() { return this.board.mine || []; }

    setTab(tab) { this.state.tab = tab; }

    async setArea(key) {
        this.state.area = this.state.area === key ? "" : key;
        await this.reload();
    }

    async onSearch(ev) {
        this.state.search = ev.target.value;
        await this.load();
    }

    toggleRole(id) {
        this.state.open = this.state.open === id ? 0 : id;
    }

    /** ONE expression per sentence, so the spaces survive (R34). */
    holdersLine(p) {
        if (!p.holder_count) { return _t("Nobody holds this yet."); }
        if (p.holder_count === 1) { return _t("1 person holds this."); }
        return _t("%s people hold this.", p.holder_count);
    }

    daysLine(d) {
        if (d.state !== "active") { return d.state_label; }
        if (!d.date_end) { return _t("Running, with no end date."); }
        if (d.days_left < 0) { return _t("Overdue — it should have ended."); }
        if (d.days_left === 0) { return _t("Ends today."); }
        if (d.days_left === 1) { return _t("Ends tomorrow."); }
        return _t("%s days left.", d.days_left);
    }

    day(s) {
        if (!s) { return ""; }
        const d = new Date(`${s}T00:00:00`);
        if (isNaN(d.getTime())) { return s; }
        return d.toLocaleDateString(undefined, {
            day: "numeric", month: "short", year: "numeric",
        });
    }

    // ------------------------------------------------------ grant and remove
    openGrant(profile) {
        this.state.granting = { profile, mode: "grant" };
        this.state.grantTarget = { id: 0, name: "" };
        this.state.grantReason = "";
        this.state.people = [];
    }

    openRemove(profile, holder) {
        this.state.granting = { profile, mode: "remove" };
        this.state.grantTarget = { id: holder.id, name: holder.name };
        this.state.grantReason = "";
        this.state.people = [];
    }

    closeGrant() { this.state.granting = null; }

    onGrantReason(ev) { this.state.grantReason = ev.target.value; }

    async onPersonSearch(ev) {
        const term = ev.target.value;
        this.state.grantTarget = { id: 0, name: term };
        if (!term || term.length < 2) { this.state.people = []; return; }
        try {
            this.state.people = await this.orm.call(
                "pb.access", "user_options", [term]);
        } catch (e) {
            this.state.people = [];
        }
    }

    pickPerson(person) {
        this.state.grantTarget = { id: person.id, name: person.name };
        this.state.people = [];
    }

    async confirmGrant() {
        const g = this.state.granting;
        if (!g) { return; }
        if (!this.state.grantTarget.id) {
            this.notif.add(_t("Choose who it is for."), { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            const res = await this.orm.call(
                "pb.access", g.mode === "remove" ? "remove" : "grant",
                [g.profile.id, this.state.grantTarget.id,
                 this.state.grantReason]);
            this.state.granting = null;
            this.notif.add(res.message, { type: "success", sticky: true });
            await this.reload();
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be done.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ----------------------------------------------------------- hand it over
    openDelegate() {
        const today = new Date();
        const end = new Date(today.getTime() + 14 * 86400000);
        this.state.hand = {
            delegate_user_id: 0, delegate: "", profile_ids: [],
            kind: "temporary",
            date_start: today.toISOString().slice(0, 10),
            date_end: end.toISOString().slice(0, 10),
            reason: "",
        };
        this.state.people = [];
        this.state.delegating = true;
    }

    closeDelegate() { this.state.delegating = false; }

    onHandField(field, ev) { this.state.hand[field] = ev.target.value; }

    setKind(kind) { this.state.hand.kind = kind; }

    toggleProfile(id) {
        const list = this.state.hand.profile_ids;
        const at = list.indexOf(id);
        if (at >= 0) { list.splice(at, 1); } else { list.push(id); }
    }

    hasProfile(id) { return this.state.hand.profile_ids.includes(id); }

    async onDelegateSearch(ev) {
        const term = ev.target.value;
        this.state.hand.delegate = term;
        this.state.hand.delegate_user_id = 0;
        if (!term || term.length < 2) { this.state.people = []; return; }
        try {
            this.state.people = await this.orm.call(
                "pb.access", "user_options", [term]);
        } catch (e) {
            this.state.people = [];
        }
    }

    pickDelegate(person) {
        this.state.hand.delegate_user_id = person.id;
        this.state.hand.delegate = person.name;
        this.state.people = [];
    }

    async confirmDelegate() {
        const h = this.state.hand;
        if (!h.delegate_user_id) {
            this.notif.add(_t("Choose who is covering for you."),
                           { type: "warning" });
            return;
        }
        if (!h.profile_ids.length) {
            this.notif.add(_t("Choose at least one thing to hand over."),
                           { type: "warning" });
            return;
        }
        if (h.kind === "temporary" && !h.date_end) {
            this.notif.add(
                _t("Say which day it ends. That is what takes it back "
                   + "without anybody having to remember."),
                { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.access", "delegate", [{
                delegate_user_id: h.delegate_user_id,
                profile_ids: h.profile_ids,
                kind: h.kind,
                date_start: h.date_start,
                date_end: h.kind === "temporary" ? h.date_end : false,
                reason: h.reason,
            }]);
            this.state.delegating = false;
            this.state.tab = "handovers";
            this.notif.add(res.message, { type: "success", sticky: true });
            await this.reload();
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be handed over.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async revoke(d) {
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.access", "revoke", [d.id]);
            this.notif.add(res.message, { type: "success" });
            await this.reload();
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be taken back.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async runRevert() {
        this.state.busy = true;
        try {
            const res = await this.orm.call("pb.access", "run_auto_revert", []);
            this.notif.add(res.message, { type: "success", sticky: true });
            await this.reload();
        } catch (e) {
            this.notif.add(this._msg(e, _t("That check could not be run.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ---------------------------------------------------------------- exports
    async exportFile(kind) {
        this.state.busy = true;
        try {
            const res = await this.orm.call(
                "pb.access",
                kind === "roles" ? "export_roles" : "export_delegations", []);
            this.download(res);
            this.notif.add(_t("The spreadsheet has been downloaded."),
                           { type: "success" });
        } catch (e) {
            this.notif.add(this._msg(e, _t("That could not be built.")),
                           { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    download(res) {
        const binary = window.atob(res.file_b64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        const blob = new Blob([bytes], { type: res.mimetype });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = res.filename;
        link.click();
        URL.revokeObjectURL(url);
    }

    openHistory() {
        this.action.doAction("pb_vendor_access.action_pb_access_delegation");
    }

    openRoleList() {
        this.action.doAction("pb_vendor_access.action_pb_role_profile");
    }

    // ----------------------------------------------------------------- errors
    _msg(e, fallback) {
        if (e && e.message && e.message.data && e.message.data.message) {
            return e.message.data.message;
        }
        if (e && e.data && e.data.message) { return e.data.message; }
        return fallback;
    }
}

registry.category("actions").add("pb_access_board", PbAccessBoard);
