/** @odoo-module **/
// My Team (MSS) cockpit — a bespoke OWL client action. Reads pb.team.get_team_data
// and routes approve/refuse through pb.team.act (which calls each model's OWN gated
// action as the real user; a model refusal comes back as {ok:false,error} and is
// shown as a toast — the row stays). No state is ever written here.

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic, SOURCE_IC } from "@pb_team/js/pbteam_icons";

const MODEL = "pb.team";

export class PbTeamCockpit extends Component {
    static template = "pb_team.Cockpit";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.ic = ic;
        this.sourceIc = (s) => ic(SOURCE_IC[s] || "inbox", 15);
        this.state = useState({
            loading: true,
            data: null,
            recursive: false,
            busy: {},            // res-key → true while acting
            refuseFor: null,     // "model:res_id" whose note popover is open
            refuseNote: "",
            removed: {},         // optimistic-removal set (res-key → true)
        });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(MODEL, "get_team_data", [
                this.state.recursive,
            ]);
        } finally {
            this.state.loading = false;
        }
    }

    key(it) {
        return `${it.model}:${it.res_id}`;
    }

    get items() {
        const items = (this.state.data?.queues?.items) || [];
        return items.filter((it) => !this.state.removed[this.key(it)]);
    }

    get pendingCount() {
        return this.items.length;
    }

    get compliancePct() {
        const mix = this.state.data?.metrics?.compliance || {};
        let ok = 0;
        let total = 0;
        for (const [k, v] of Object.entries(mix)) {
            total += v;
            if (k === "on_time" || k === "overtime") {
                ok += v;
            }
        }
        return total ? Math.round((100 * ok) / total) : 0;
    }

    get otMtd() {
        return this.state.data?.metrics?.ot?.mtd || 0;
    }

    get otCap() {
        return this.state.data?.metrics?.ot?.cap_month || 0;
    }

    get otPct() {
        return this.state.data?.metrics?.ot?.pct || 0;
    }

    async toggleScope() {
        this.state.recursive = !this.state.recursive;
        this.state.removed = {};
        await this.load();
    }

    async refresh() {
        this.state.removed = {};
        this.state.refuseFor = null;
        await this.load();
    }

    // --- approve (optimistic) ---
    async approve(it) {
        const k = this.key(it);
        if (this.state.busy[k]) {
            return;
        }
        this.state.busy[k] = true;
        try {
            const res = await this.orm.call(MODEL, "act", [
                it.model, it.res_id, "approve",
            ]);
            this.afterAct(it, res, _t("Approved"));
        } catch (e) {
            this.showError(e);
        } finally {
            delete this.state.busy[k];
        }
    }

    // --- refuse: open the note popover ---
    openRefuse(it) {
        this.state.refuseFor = this.key(it);
        this.state.refuseNote = "";
    }

    cancelRefuse() {
        this.state.refuseFor = null;
        this.state.refuseNote = "";
    }

    async confirmRefuse(it) {
        const k = this.key(it);
        this.state.busy[k] = true;
        try {
            const res = await this.orm.call(MODEL, "act", [
                it.model, it.res_id, "refuse", this.state.refuseNote || false,
            ]);
            this.state.refuseFor = null;
            this.afterAct(it, res, _t("Refused"));
        } catch (e) {
            this.showError(e);
        } finally {
            delete this.state.busy[k];
        }
    }

    afterAct(it, res, okLabel) {
        if (res && res.ok && res.state === "refused" && okLabel !== _t("Refused")) {
            // the model accepted the click but REFUSED the record (e.g. a
            // young-worker guard on apply) — never toast that as approved
            this.state.removed[this.key(it)] = true;
            this.notif.add(
                _t("Refused by a server guard · %s", it.employee.name),
                { type: "warning", title: _t("Not applied") });
        } else if (res && res.ok) {
            this.state.removed[this.key(it)] = true;
            this.notif.add(`${okLabel} · ${it.employee.name}`, { type: "success" });
        } else {
            // the target model refused — quote its own message, keep the row
            this.notif.add(res?.error || _t("The request could not be processed."), {
                type: "warning",
                title: _t("Not allowed"),
            });
        }
    }

    showError(e) {
        const msg = (e && e.data && e.data.message) || (e && e.message) || _t("Something went wrong.");
        this.notif.add(msg, { type: "danger" });
    }
}

registry.category("actions").add("pb_team", PbTeamCockpit);
