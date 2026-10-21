/** @odoo-module **/
/**
 * Home › TEAM (NAV P3c, 2026-10-21) — one screen for somebody who manages
 * people.
 *
 * THE HERO MOMENT is one sentence and a row of faces: "Your team of 8 · 6 in
 * today · 1 on leave · 1 not started yet · 3 things waiting on you", with a
 * coloured dot on every face. Each number lights the faces it counts (press it
 * again to see everybody); "waiting on you" opens the inbox on My turn.
 *
 * WHO IS ON IT. The lens is offered only to somebody with at least one active
 * direct report (`pb.home.team.can_open`, the probe below). Everything on it
 * comes from ONE read, `pb.home.team.get_team`, which asks every other module
 * softly — a section whose module is not installed is absent, never a zero.
 *
 * EVERY TILE IS A DOOR into the screen that already does the work, already
 * filtered: the inbox on the tile's area, the probation board on the person,
 * the goals board on its check-ins or reviews tab, the manager's own training
 * page, the hiring role. Every door carries a way back to this tab.
 *
 * NO MONEY ANYWHERE. The payload carries no amount, salary, budget or growth
 * plan, and this file draws nothing it does not get.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { openHub, railKeydown } from "@pb_hub/js/hub_nav";
import { featureOn } from "@pb_hub/js/hub_features";
import { HOME_LENSES } from "@pb_home_hub/js/home_hub";

const HOME = "pb_home_hub.action_pb_home_hub";

/** The return door every hand-off carries: back to this tab. */
function backToTeam() {
    return { label: _t("My team"), xmlid: HOME, lens: "team" };
}

/** The five "Waiting on you" tiles, in the server's order. */
const TILE_LABEL = {
    time_off: _t("Time off"),
    overtime: _t("Overtime and timesheets"),
    expenses: _t("Expenses and trips"),
    people: _t("People"),
    other: _t("Other"),
};

export class PbTeamLens extends Component {
    static template = "pb_home_hub.PbTeamLens";
    static props = { embedded: { type: Boolean, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.ic = ic;
        this.state = useState({
            loading: true,
            failed: false,
            d: null,
            pick: "",          // the hero number now lighting faces
            drawerEmpId: 0,
        });
        onWillStart(() => this.load());
    }

    // ================================================================ read
    async load() {
        this.state.loading = true;
        this.state.failed = false;
        try {
            this.state.d = await this.orm.call("pb.home.team", "get_team", []);
        } catch (e) {
            console.warn("pb_home_hub: could not read the team", e);
            this.state.failed = true;
        } finally {
            this.state.loading = false;
        }
    }

    get d() { return this.state.d || { people: [], counts: {} }; }
    get counts() { return this.d.counts || {}; }
    get people() { return this.d.people || []; }

    // ================================================================ hero
    /** The hero's numbers. A number at zero is not drawn (quiet board). */
    get heroBits() {
        const c = this.counts;
        const bits = [
            { key: "in", n: c.in || 0, label: _t("%s in today", c.in || 0) },
            { key: "late", n: c.late || 0, label: _t("%s late", c.late || 0), tone: "amber" },
            { key: "on_leave", n: c.on_leave || 0, label: _t("%s on leave", c.on_leave || 0) },
            { key: "not_started", n: c.not_started || 0,
              label: _t("%s not started yet", c.not_started || 0) },
            { key: "off", n: c.off || 0, label: _t("%s not working today", c.off || 0) },
        ];
        return bits.filter((b) => b.n > 0);
    }

    get waitingTotal() {
        return this.d.decisions ? (this.d.decisions.total || 0) : 0;
    }

    get teamWords() {
        return _t("Your team of %s", this.d.size || 0);
    }

    get waitingWords() {
        const n = this.waitingTotal;
        return n === 1 ? _t("1 thing waiting on you")
                       : _t("%s things waiting on you", n);
    }

    pickBit(key) {
        this.state.pick = this.state.pick === key ? "" : key;
    }

    /** Does face `p` belong to the number now picked? */
    lit(p) {
        const k = this.state.pick;
        if (!k) { return true; }
        if (k === "late") { return p.status === "late"; }
        return p.bucket === k;
    }

    faceTitle(p) { return p.short + " · " + p.words; }

    onStripKeydown(ev) { railKeydown(ev, ".pbtm-face"); }

    /** Nothing anywhere asks the reader to act. */
    get calm() { return !this.state.loading && !this.d.due_total; }

    get calmWords() {
        const c = this.counts;
        if ((c.not_started || 0) === 0 && (c.late || 0) === 0) {
            return _t("%s people, all accounted for.", this.d.size || 0);
        }
        return "";
    }

    // ============================================================ waiting
    get glance() {
        const dec = this.d.decisions;
        if (!dec) { return []; }
        return (dec.tiles || []).map((t) => ({
            key: t.key,
            n: t.n,
            label: TILE_LABEL[t.key] || t.key,
            tone: t.n ? "amber" : "",
            run: t.n ? () => this.openInbox(t.area) : null,
        }));
    }

    openInbox(area) {
        openHub(this.action, {
            xmlid: HOME, lens: "approvals",
            focus: area ? "area:" + area : "",
            back: backToTeam(),
        });
    }

    // ======================================================= conversations
    get hasConversations() { return !!(this.d.probation || this.d.goals); }

    /** Can this reader open the probation board? A plain line manager
     *  cannot (it is the HR team's screen); their rows are plain text. */
    get probationDoor() {
        const p = this.d.probation || {};
        return p.door === "board" && featureOn(this.env, "lifecycle");
    }

    openProbation(row) {
        if (!this.probationDoor) { return; }
        openHub(this.action, {
            xmlid: "pb_people_hub.action_pb_people_hub", lens: "probation",
            focus: "person:" + row.employee_id, back: backToTeam(),
        });
    }

    openGoal(row) {
        const g = this.d.goals || {};
        if (g.can_board) {
            openHub(this.action, {
                xmlid: "pb_talent_hub.action_pb_talent_hub", lens: "goals",
                focus: "tab:" + (row.kind === "review" ? "reviews" : "checkins"),
                back: backToTeam(),
            });
            return;
        }
        this.door("pb_goals.action_my_goals");
    }

    // ============================================================ learning
    get trainingWords() {
        const t = this.d.training;
        if (!t) { return ""; }
        const n = t.overdue_people || 0;
        if (!n) { return _t("Nobody on your team is past a training date."); }
        return n === 1 ? _t("1 person has required training past its date")
                       : _t("%s people have required training past its date", n);
    }

    daysOver(p) {
        return p.days_over === 1 ? _t("1 day late") : _t("%s days late", p.days_over);
    }

    openTraining() {
        this.action.doAction({
            type: "ir.actions.act_url", url: "/my/training/team", target: "self",
        });
    }

    // ============================================================== hiring
    /** A request that is theirs to write opens the page they write it on;
     *  otherwise the role on the Hiring board; somebody who cannot open the
     *  board (a plain line manager) gets their own hiring page instead. */
    openRole(row) {
        if (row.write_url) {
            // Theirs to write: the request page the email links to.
            this.action.doAction({
                type: "ir.actions.act_url", url: row.write_url, target: "self",
            });
            return;
        }
        if (!(this.d.hiring && this.d.hiring.can_open)) {
            this.action.doAction({
                type: "ir.actions.act_url", url: "/my/hiring", target: "self",
            });
            return;
        }
        openHub(this.action, {
            xmlid: "pb_hiring.action_pb_hiring_hub", lens: "overview",
            context: { pb_role_id: row.id }, back: backToTeam(),
        });
    }

    // ============================================================== people
    /** The People screen's person drawer, when it is installed and the reader
     *  is HR; everybody else gets the person's public page. */
    get drawerCmp() {
        const r = registry.category("pb_people_drawer");
        return r.contains("employee_360") ? r.get("employee_360") : null;
    }

    get drawerProps() {
        return { empId: this.state.drawerEmpId, onClose: () => this.closeDrawer() };
    }

    closeDrawer() { this.state.drawerEmpId = 0; }

    openPerson(p) {
        if (this.d.can_360 && this.drawerCmp) {
            this.state.drawerEmpId = p.id;
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: p.name,
            res_model: "hr.employee.public",
            res_id: p.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    /** A door by xmlid; a screen this database lacks is a notice. */
    door(xmlid) {
        Promise.resolve(this.action.doAction(xmlid)).catch(() => {
            this.notif.add(_t("That screen is not available here."), { type: "warning" });
        });
    }
}

registry.category(HOME_LENSES).add("team", {
    key: "team",
    icon: "users",
    label: _t("Team"),
    title: _t("My team"),
    Component: PbTeamLens,
    // Offered only to somebody with a direct report. The server answers; no
    // group can say "manages somebody".
    probe: { model: "pb.home.team", method: "can_open" },
}, { sequence: 12 });
