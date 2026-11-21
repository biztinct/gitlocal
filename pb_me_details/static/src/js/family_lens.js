/** @odoo-module **/
/**
 * People › Family — family members waiting for the pay team's tax tick, and
 * what employees asked to change on My Payobook.
 *
 * The tick is the ONLY place an approved family change reaches pay (owner
 * ruling E1). "Waiting for HR to confirm for tax" is the one coloured number;
 * everything else is grey at zero.
 *
 * R1 — no `t-as` variable is named lt/gt/lte/gte/and/or/not/in.
 * R2 — icons are the filter kit's CACHED markup (`pbfIcon`).
 * R3 — every sentence a person reads is a `_t()` literal or comes from the
 *      server already translated; template sentences sit on one line.
 */
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { pbfIcon } from "@pb_filter_kit/js/filter_kit";
import { PEOPLE_LENSES } from "@pb_people_hub/js/people_hub";

export const FAMILY_GATE = ["hr.group_hr_user", "om_hr_payroll.group_hr_payroll_user"];

export class PbFamilyLens extends Component {
    static template = "pb_me_details.PbFamilyLens";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.state = useState({
            loaded: false, allowed: true, why: "", view: "waiting",
            counts: { waiting: 0, open: 0, recent: 0, members: 0 },
            rows: [], canTick: false, search: "", busy: 0,
        });
        this._seq = 0;
        onWillStart(() => this.load());
    }

    icon(name, size = 16) { return pbfIcon(name, size); }

    async load() {
        const seq = ++this._seq;
        try {
            const d = await this.orm.call("pb.family.board", "get_board", [], {
                view: this.state.view, search: this.state.search,
            });
            if (seq !== this._seq) { return; }
            if (d.allowed === false) {
                Object.assign(this.state, { allowed: false, why: d.why || "" });
                return;
            }
            Object.assign(this.state, {
                allowed: true, counts: d.counts || {}, rows: d.rows || [],
                canTick: !!d.can_tick,
            });
        } catch (e) {
            console.warn("pb_me_details: the board could not be read", e);
            this.state.allowed = false;
            this.state.why = _t("The family list could not be read just now. Try again in a moment.");
        } finally {
            this.state.loaded = true;
        }
    }

    get glance() {
        const c = this.state.counts || {};
        const go = (view) => () => this.show(view);
        return [
            { key: "waiting", n: c.waiting || 0, label: _t("waiting for HR to confirm for tax"), tone: c.waiting ? "amber" : "", run: go("waiting") },
            { key: "open", n: c.open || 0, label: _t("changes waiting for approval"), tone: "", run: go("open") },
            { key: "recent", n: c.recent || 0, label: _t("decided in the last 30 days"), tone: "", run: go("recent") },
        ];
    }
    get glanceOn() { return this.state.view; }

    stateLabel(st) {
        return {
            hr_review: _t("Waiting for approval"),
            approved: _t("Approved"),
            refused: _t("Turned down"),
            draft: _t("Sent back"),
        }[st] || "";
    }

    show(view) {
        if (this.state.view === view) { return; }
        this.state.view = view;
        this.state.rows = [];
        this.load();
    }
    onSearch(ev) {
        this.state.search = ev.target.value || "";
        clearTimeout(this._timer);
        this._timer = setTimeout(() => this.load(), 250);
    }

    async tick(row, confirm) {
        if (this.state.busy) { return; }
        this.state.busy = row.id;
        try {
            await this.orm.call("pb.family.board", confirm ? "confirm_tax" : "leave_tax", [row.id]);
            this.notif.add(confirm
                ? _t("%s: confirmed for tax. Pay uses it from the next pay run.", row.member)
                : _t("%s: pay is left as it is.", row.member), { type: "success" });
            await this.load();
        } catch (e) {
            const msg = (e && e.data && e.data.message) || _t("That did not go through. Please try again.");
            this.notif.add(msg, { type: "warning" });
        } finally {
            this.state.busy = 0;
        }
    }

    async openMember(row) {
        const act = await this.orm.call("pb.family.board", "open_member", [row.id]);
        this.action.doAction(act, { onClose: () => this.load() });
    }

    async openApprovals() {
        this.action.doAction("pb_approval_config.action_pb_approval_inbox").catch(() => {
            this.notif.add(_t("Open Approvals from Home to decide these."), { type: "info" });
        });
    }
}

registry.category(PEOPLE_LENSES).add("family", {
    key: "family",
    icon: "users",
    label: _t("Family"),
    title: _t("Family · confirm family members for tax"),
    Component: PbFamilyLens,
    groups: FAMILY_GATE,
}, { sequence: 88 });
