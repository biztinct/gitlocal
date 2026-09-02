/** @odoo-module **/
/**
 * `pb_access_board` — the Access home behind the Settings cog.
 *
 * ONE HOME, AND LENSES OVER THE SAME TRUTH.
 *
 *   **Roles** — "who can do what". Each role is a card carrying its plain name,
 *   the sentence saying WHAT IT LETS SOMEONE DO, and the faces of the people
 *   who hold it. The sentence is the hero: a permission group called "Manager"
 *   tells nobody anything, and every mistake this screen exists to prevent
 *   starts with somebody granting a thing they could not name. Opened out, a
 *   card answers the three questions in the order somebody asks them: what does
 *   it OPEN, what does it LET THEM DO, and who HOLDS it.
 *
 *   **Hand-overs** — "who is covering for whom". A running hand-over shows the
 *   days left on it, because the thing worth knowing about temporary access is
 *   when it stops being temporary.
 *
 * THE LENS BAR IS A REGISTRY, NOT A ROW OF BUTTONS. `LENS_REGISTRY` below is
 * the list, the bar draws whatever is in it, and the body switches on the key.
 * Two more lenses are coming — the person passport and the menu editor — and
 * they are a line in that array plus a branch in the template, not a rewrite of
 * this file.
 *
 * WHICH SCREENS A ROLE OPENS IS NOT DECIDED HERE, AND MUST NOT BE. It is worked
 * out on the server, by the same rule the left menu itself uses, and arrives
 * ready to draw (`pb.access.role_detail` / `preview_rail`). A copy of that rule
 * in this file would be a second answer to a question that must only ever have
 * one — and it would be the answer somebody trusts while it is wrong.
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
import { Component, useState, onWillStart, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
import { PbMiniRail } from "@pb_vendor_access/js/mini_rail";

/**
 * The lenses this home offers, in the order they are offered.
 *
 * The person passport and the left-menu editor are the next two, and adding
 * either is a line here plus a branch in the template — which is the point of
 * writing it down as data rather than as two hard-coded buttons.
 */
const LENS_REGISTRY = [
    { key: "roles", icon: "idCard", label: _t("Roles") },
    { key: "handovers", icon: "arrowLeftRight", label: _t("Hand-overs") },
];

export class PbAccessBoard extends Component {
    static template = "pb_vendor_access.PbAccessBoard";
    static components = { HubBackChip, PbMiniRail };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");

        this.back = hubBack(this.props);
        //: An answer to an older tick must never overwrite the answer to a
        //: newer one — ticking three boxes quickly is three requests, and the
        //: slowest is not the one that is true.
        this.previewSeq = 0;

        // CAPTURE, NOT BUBBLE. Escape is a hotkey the web client already
        // handles, and its own handler stops the event before it ever reaches
        // a listener waiting on the way back up — which is why the first
        // version of this line did nothing at all. On the way DOWN nothing can
        // have swallowed it yet. Nothing here consumes the event either, so
        // the client still gets its turn.
        useExternalListener(window, "keydown", this.onKeyDown, { capture: true });

        this.state = useState({
            loaded: false,
            failed: "",
            board: null,

            lens: "roles",             // see LENS_REGISTRY
            area: "",
            search: "",
            open: 0,                   // the role that is opened out
            detail: {},                // role id -> what it opens / lets / holders
            detailBusy: 0,

            // the role builder
            composer: null,            // { name, description, area, abilities }
            options: null,             // the ability catalogue, read once
            preview: null,             // the left menu as a holder would see it
            creating: false,

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
        // Everything opened out was read BEFORE whatever just happened, so it
        // is now a picture of a moment that has passed. Re-read the one that
        // is still open rather than leaving somebody looking at yesterday.
        this.state.detail = {};
        await this.load();
        if (this.state.open) { await this.loadDetail(this.state.open); }
    }

    get board() { return this.state.board || {}; }
    get profiles() { return this.board.profiles || []; }
    get delegations() { return this.board.delegations || []; }
    get kpis() { return this.board.kpis || {}; }
    get canManage() { return Boolean(this.board.can_manage); }
    get mine() { return this.board.mine || []; }
    get lenses() { return LENS_REGISTRY; }

    setLens(key) { this.state.lens = key; }

    async setArea(key) {
        this.state.area = this.state.area === key ? "" : key;
        await this.reload();
    }

    async onSearch(ev) {
        this.state.search = ev.target.value;
        await this.load();
    }

    // ------------------------------------------------------- a role, opened out
    async toggleRole(id) {
        if (this.state.open === id) { this.state.open = 0; return; }
        this.state.open = id;
        if (!this.state.detail[id]) { await this.loadDetail(id); }
    }

    /** A card is a button, so it opens on Enter and on Space like one. */
    onRoleKey(ev, id) {
        if (ev.key !== "Enter" && ev.key !== " ") { return; }
        ev.preventDefault();
        this.toggleRole(id);
    }

    async loadDetail(id) {
        this.state.detailBusy = id;
        try {
            this.state.detail[id] = await this.orm.call(
                "pb.access", "role_detail", [id]);
        } catch (e) {
            this.state.detail[id] = { failed: this._msg(
                e, _t("That role could not be opened out.")) };
        } finally {
            this.state.detailBusy = 0;
        }
    }

    detailOf(id) { return this.state.detail[id] || null; }

    /** ONE expression per sentence, so the spaces survive (R34). */
    heldByLine(d) {
        if (!d.holder_count) { return _t("Held by nobody yet"); }
        if (d.holder_count === 1) { return _t("Held by 1 person"); }
        return _t("Held by %s people", d.holder_count);
    }

    holderNote(hd) {
        if (hd.source !== "lent") { return hd.login || ""; }
        if (!hd.until) { return _t("Lent by %s", hd.by || ""); }
        return _t("Lent by %s, until %s", hd.by || "", this.day(hd.until));
    }

    /**
     * "Plus Home and Learn, which everybody sees."
     *
     * Capped at three names and a count. A column that listed nine of them
     * would bury the two the role actually opens under the seven it does not.
     */
    everyoneLine(d) {
        const names = d.everyone || [];
        if (!names.length) { return ""; }
        if (names.length === 1) {
            return _t("Plus %s, which everybody sees.", names[0]);
        }
        if (names.length <= 3) {
            return _t("Plus %s and %s, which everybody sees.",
                      names.slice(0, -1).join(", "), names[names.length - 1]);
        }
        return _t("Plus %s and %s more, which everybody sees.",
                  names.slice(0, 3).join(", "), names.length - 3);
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
            this.state.lens = "handovers";
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

    // ------------------------------------------------------------ the builder
    /**
     * BUILD A ROLE OUT OF THINGS SOMEBODY CAN NAME, AND SHOW THE RESULT WHILE
     * THEY BUILD IT. The left-hand side is a name, one honest sentence and a
     * list of abilities; the right-hand side is the left menu, drawn small,
     * lighting up as boxes are ticked. Nobody has to imagine the outcome, which
     * is the only reliable way to stop somebody handing out more than they
     * meant to.
     *
     * ABILITIES, NEVER RAW PERMISSIONS. The list offers whole abilities and
     * nothing else, so a role can only ever be built out of things that carry a
     * sentence. That is structural, not a rule somebody has to remember.
     */
    async openComposer(source) {
        // THE CATALOGUE IS READ BEFORE THE DIALOG OPENS, never after. A dialog
        // that appears and then fills itself in is a dialog somebody starts
        // typing into a field that is about to be replaced.
        if (!this.state.options) {
            this.state.busy = true;
            try {
                this.state.options = await this.orm.call(
                    "pb.access", "composer_options", []);
            } catch (e) {
                this.notif.add(
                    this._msg(e, _t("The role builder could not be opened.")),
                    { type: "danger" });
                return;
            } finally {
                this.state.busy = false;
            }
        }
        this.state.composer = {
            name: source ? _t("Copy of %s", source.name) : "",
            description: source ? (source.description || "") : "",
            area: source ? (source.area || "") : "",
            abilities: source ? (source.ability_ids || []).slice() : [],
            picking: false,
        };
        this.state.preview = null;
        await this.refreshPreview();
    }

    closeComposer() { this.state.composer = null; }

    onComposerField(field, ev) {
        this.state.composer[field] = ev.target.value;
    }

    setComposerArea(key) { this.state.composer.area = key; }

    togglePicking() {
        this.state.composer.picking = !this.state.composer.picking;
    }

    /** Start from an existing role: same abilities, a name that says so. */
    async prefillFrom(role) {
        await this.openComposer(role);
    }

    toggleAbility(id) {
        const list = this.state.composer.abilities;
        const at = list.indexOf(id);
        if (at >= 0) { list.splice(at, 1); } else { list.push(id); }
        this.refreshPreview();
    }

    onAbilityKey(ev, id) {
        if (ev.key !== "Enter" && ev.key !== " ") { return; }
        ev.preventDefault();
        this.toggleAbility(id);
    }

    hasAbility(id) {
        return Boolean(this.state.composer)
            && this.state.composer.abilities.includes(id);
    }

    /** The abilities on offer, in their areas — an ungrouped list of thirty-five
     *  sentences is a list nobody reads to the bottom of. */
    get abilityAreas() {
        const options = this.state.options;
        if (!options) { return []; }
        return (options.areas || [])
            .map((ar) => Object.assign({}, ar, {
                abilities: (options.abilities || []).filter(
                    (ab) => ab.area === ar.key),
            }))
            .filter((ar) => ar.abilities.length);
    }

    get composerRail() {
        if (this.state.preview) { return this.state.preview.sections || []; }
        return (this.state.options && this.state.options.rail) || [];
    }

    get composerArea() {
        const c = this.state.composer;
        if (c && c.area) { return c.area; }
        return (this.state.preview && this.state.preview.area) || "";
    }

    async refreshPreview() {
        const seq = ++this.previewSeq;
        try {
            const res = await this.orm.call(
                "pb.access", "preview_rail",
                [this.state.composer ? this.state.composer.abilities : []]);
            if (seq !== this.previewSeq) { return; }
            this.state.preview = res;
        } catch (e) {
            // The last good picture stays on screen. A preview that blanks
            // itself on one slow answer reads as "this role opens nothing".
        }
    }

    /**
     * "2 abilities ticked, unlocking 3 menu entries. 4 people can already do
     * all of it."
     *
     * The last sentence is not decoration. A role built out of permissions
     * people already have is held by them the moment it is written down, and a
     * dialog promising "nobody holds it yet" would be contradicted by its own
     * board one second later.
     */
    countLine() {
        const p = this.state.preview;
        const n = this.state.composer ? this.state.composer.abilities.length : 0;
        if (!n) { return _t("Nothing ticked yet."); }
        const ticked = n === 1 ? _t("1 ability") : _t("%s abilities", n);
        const held = (p && p.already_held_by) || 0;
        const who = !held
            ? _t("Nobody holds it yet.")
            : (held === 1
                ? _t("1 person can already do all of it.")
                : _t("%s people can already do all of it.", held));
        if (!p || !p.any_gated) {
            return _t("%s ticked. %s", ticked, who);
        }
        const entries = p.lit === 1 ? _t("1 menu entry")
                                    : _t("%s menu entries", p.lit);
        return _t("%s ticked, unlocking %s. %s", ticked, entries, who);
    }

    async createRole() {
        const c = this.state.composer;
        if (!c || !c.abilities.length) { return; }
        this.state.creating = true;
        try {
            const res = await this.orm.call("pb.access", "create_role", [
                c.name, c.description, c.area || false, c.abilities]);
            this.state.composer = null;
            // The new role belongs in "start from an existing role" next time.
            this.state.options = null;
            this.notif.add(res.message, { type: "success", sticky: true });
            this.state.lens = "roles";
            this.state.area = "";
            this.state.open = res.id;
            await this.reload();
        } catch (e) {
            this.notif.add(
                this._msg(e, _t("That role could not be written down.")),
                { type: "danger" });
        } finally {
            this.state.creating = false;
        }
    }

    // ------------------------------------------------------------- the keyboard
    /** Escape closes whatever is on top, innermost first. */
    onKeyDown(ev) {
        if (ev.key !== "Escape") { return; }
        if (this.state.composer) { this.state.composer = null; return; }
        if (this.state.granting) { this.state.granting = null; return; }
        if (this.state.delegating) { this.state.delegating = false; }
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
