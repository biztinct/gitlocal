/** @odoo-module **/
/**
 * Hiring › Staff moves (WDGAP S6-B).
 *
 * The hiring team's view of staff applications and of who may apply for
 * each open role. One read (`pb.hiring.internal.get_board`), one write per
 * press (`set_posting`, `start_job_change`); the server gates every call on
 * the hiring team's own group, so a line manager never reaches it (E4).
 *
 * Quiet board: grey at zero; the only colour is the thing to act on — a
 * job change still to do.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { HIRING_LENSES } from "@pb_hiring/js/hiring_hub";

const MODEL = "pb.hiring.internal";

export class PbStaffMoves extends Component {
    static template = "pb_hiring_internal.PbStaffMoves";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notif = useService("notification");
        this.ic = ic;
        this.state = useState({ loading: true, failed: false, d: null, tab: "applications", busy: false });
        onWillStart(() => this.load());
    }

    async load() {
        try {
            this.state.d = await this.orm.call(MODEL, "get_board", []);
            this.state.failed = false;
        } catch (e) {
            console.warn("pb_hiring_internal: could not read staff moves", e);
            this.state.failed = true;
        } finally {
            this.state.loading = false;
        }
    }

    setTab(tab) { this.state.tab = tab; }

    async setPosting(role, key) {
        if (this.state.busy || role.posting === key) { return; }
        this.state.busy = true;
        try {
            this.state.d = await this.orm.call(MODEL, "set_posting", [role.id, key]);
            this.notif.add(_t("Saved. %s", this.postingLabel(key)), { type: "success" });
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That could not be saved."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async startJobChange(app) {
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            const res = await this.orm.call(MODEL, "start_job_change", [app.id]);
            if (res && res.action) {
                await this.action.doAction(res.action);
            } else if (res && res.note) {
                this.notif.add(res.note, { type: "info", sticky: true });
            }
            await this.load();
        } catch (e) {
            this.notif.add((e && e.data && e.data.message) || _t("That could not be opened."), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    postingLabel(key) {
        const row = ((this.state.d && this.state.d.postings) || []).find((p) => p.key === key);
        return row ? row.label : "";
    }

    initials(name) {
        return (name || "").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
    }

    stateWord(state) {
        return {
            received: _t("Received"),
            considered: _t("Being considered"),
            offer: _t("Offer being prepared"),
            accepted: _t("Offer accepted"),
            moved: _t("Moved"),
            closed: _t("Not this time"),
            withdrawn: _t("Withdrawn"),
        }[state] || "";
    }

    lockedWord(role) {
        if (role.confidential) { return _t("Confidential roles are never shown to staff."); }
        if (role.quiet_replacement) { return _t("Quiet replacements are never shown to staff."); }
        return "";
    }
}

registry.category(HIRING_LENSES).add("staff_moves", {
    key: "staff_moves",
    icon: "users",
    label: _t("Staff moves"),
    title: _t("Staff moves"),
    Component: PbStaffMoves,
    groups: ["pb_hiring.group_hiring_user"],
    probe: { model: MODEL, method: "can_open" },
}, { sequence: 40 });
