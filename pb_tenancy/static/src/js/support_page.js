/** @odoo-module **/
/**
 * FLEET P6 — "Support access": the page that makes our access to your data
 * something you can see and something you can stop.
 *
 * THIS IS THE HERO OF THE PHASE, and the reason it is the hero is that it is
 * the only screen in the whole programme written for somebody who does not
 * trust us yet. It answers three questions, in this order, because that is the
 * order they are asked in:
 *
 *   1. Can Payobook get into my data at all?      — the switch, at the top.
 *   2. Have they?                                 — the trail, underneath.
 *   3. What exactly did they look at?             — the screens, on each row.
 *
 * THE SWITCH IS REAL AND THERE IS NO OVERRIDE. When it is off, the platform's
 * own button is disabled and says why; nothing on the platform side can turn it
 * back on. That is stated on this page in as many words, because a promise that
 * is not written down is not a promise.
 *
 * NOTHING HERE CAN BE EDITED OR DELETED. The trail is written by the server and
 * has no delete button on any screen, ours included.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ic } from "@pb_import_kit/js/import_icons";
import { HubBackChip, hubBack } from "@pb_hub/js/hub_nav";
import { _t } from "@web/core/l10n/translation";

/** The words and the colour each state wears on a trail row. */
const ROW_STATE = {
    active: ["warn", _t("In progress")],
    ended: ["ok", _t("Finished")],
    expired: ["ok", _t("Finished — time ran out")],
    refused: ["muted", _t("Refused")],
    issued: ["info", _t("Link sent, not used")],
};

/** "3 September 2026, 14:02" from the server's UTC stamp, in the reader's clock. */
export function stampText(stamp) {
    if (!stamp) { return ""; }
    const d = new Date(`${String(stamp).replace(" ", "T")}Z`);
    if (isNaN(d.getTime())) { return String(stamp); }
    try {
        return d.toLocaleString(undefined, {
            day: "numeric", month: "long", year: "numeric",
            hour: "2-digit", minute: "2-digit",
        });
    } catch {
        return String(stamp);
    }
}

/** "just under 2 hours", "35 minutes". PURE. */
export function durationText(minutes) {
    const m = Math.max(0, Math.round(Number(minutes) || 0));
    if (!m) { return ""; }
    if (m < 60) { return _t("%(m)s minutes", { m }); }
    const h = Math.floor(m / 60);
    const rest = m % 60;
    if (!rest) {
        return h === 1 ? _t("1 hour") : _t("%(h)s hours", { h });
    }
    return _t("%(h)s hours %(m)s minutes", { h, m: rest });
}

/**
 * How long a session actually lasted, in words, or "" if it is still running.
 * PURE, and it is arithmetic the template must never do (ledger F16).
 */
export function lastedText(usedAt, endedAt) {
    if (!usedAt || !endedAt) { return ""; }
    const a = new Date(`${String(usedAt).replace(" ", "T")}Z`).getTime();
    const b = new Date(`${String(endedAt).replace(" ", "T")}Z`).getTime();
    if (isNaN(a) || isNaN(b) || b < a) { return ""; }
    const mins = Math.max(1, Math.round((b - a) / 60000));
    return durationText(mins);
}

export class PbTenancySupportPage extends Component {
    static template = "pb_tenancy.SupportPage";
    static components = { HubBackChip };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.back = hubBack(this.props);
        this.state = useState({
            loaded: false, d: null, error: "", busy: false, open: null,
        });
        onWillStart(async () => { await this.load(); });
    }

    ic(name, size = 16) { return ic(name, size); }

    async load() {
        try {
            this.state.d = await this.orm.silent.call(
                "pb.tenancy", "support_page", []);
            this.state.error = "";
        } catch (e) {
            console.error("pb_tenancy: could not read the support trail", e);
            this.state.error = e && e.data && e.data.message
                ? e.data.message
                : _t("This page could not be read just now. Try again in a " +
                     "moment — nothing is wrong with your data.");
        }
        this.state.loaded = true;
    }

    get d() { return this.state.d || {}; }

    get allowed() { return !!this.d.allowed; }

    /**
     * May this reader work the switch and read the trail?
     *
     * A "no" is a calm panel on this page, not an error dialog: somebody who
     * arrived here from a link deserves a sentence saying who in their company
     * can help, and a page about trust that greets people with a fault is a
     * poor advertisement for it.
     */
    get mayManage() { return this.state.d ? !!this.d.may_manage : true; }

    get company() { return this.d.company || _t("your company"); }

    /** The one sentence under the switch. It changes with the answer. */
    get switchSentence() {
        if (this.allowed) {
            return _t("Payobook support can open %(company)s's data when you " +
                      "ask us to. Every time we do, it is written down below " +
                      "— who, why, and which screens were opened.",
                      { company: this.company });
        }
        return _t("Payobook support cannot open %(company)s's data, even if " +
                  "you ask us to. Nobody at Payobook can turn this back on — " +
                  "switch it on here first.", { company: this.company });
    }

    get rows() {
        return (this.d.rows || []).map((r) => ({
            ...r,
            tone: (ROW_STATE[r.state] || ROW_STATE.ended)[0],
            state_label: (ROW_STATE[r.state] || ROW_STATE.ended)[1],
            when: stampText(r.used_at || r.issued_at),
            allowed_for: durationText(r.minutes),
            lasted: lastedText(r.used_at, r.ended_at),
            screen_count: (r.screens || []).length,
        }));
    }

    get empty() { return !this.rows.length; }

    /** A CLICK handler. */
    toggleRow(id) {
        this.state.open = this.state.open === id ? null : id;
    }

    screenLabel(screen) {
        const title = (screen.title || "").replace(/\s*[|·-]\s*Payobook\s*$/i, "");
        return title || screen.action || "";
    }

    /** A CLICK handler. The customer's own decision, and the only writer of it. */
    async setAllowed(on) {
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            this.state.d = await this.orm.call(
                "pb.tenancy", "support_set_allowed", [on]);
            this.notif.add(
                on ? _t("Payobook support can open your data when you ask.")
                   : _t("Payobook support can no longer open your data."),
                { type: on ? "success" : "warning" });
        } catch (e) {
            console.error("pb_tenancy: the switch could not be changed", e);
            this.notif.add(
                e && e.data && e.data.message
                    ? e.data.message
                    : _t("That could not be changed just now."),
                { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
}

registry.category("actions").add("pb_tenancy_support", PbTenancySupportPage);
