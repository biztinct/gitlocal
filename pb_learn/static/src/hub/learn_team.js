/** @odoo-module **/
/**
 * LEARN v3 — Learn > Team: who is ready for month-end.
 *
 * One row per person who works on payroll: their path, how many of its
 * required lessons they have finished, what is next, and when they last
 * opened Learn. One button sends them a short note pointing at their next
 * lesson. Progress only: the questions people asked are never read here, and
 * the page says so.
 *
 * Gated to payroll managers and administrators in learn_hub.js; the server
 * (`learn.path.readiness` / `remind`) re-asks on every call.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

import { RT, T, tx } from "../engine/runtime";
import { loadContent } from "../content/content_loader";

const ROLE_LABEL = { officer: "roleOfficer", approver: "roleApprover", hr: "roleHr",
                     manager: "roleManager", owner: "roleOwner" };
const STATUS = {
    ready: { label: "teamReady", cls: "ok" },
    started: { label: "teamStarted", cls: "warn" },
    not_started: { label: "teamNot", cls: "muted" },
};

export class LearnTeam extends Component {
    static template = "pb_learn.LearnTeam";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            loading: true, allowed: false, rows: [],
            sending: 0, sent: {}, failed: 0,
        });
        onWillStart(async () => {
            try {
                const content = await loadContent();
                if (!Object.keys(RT.chrome || {}).length) {
                    RT.chrome = content.chrome || {};
                }
                this.state.allowed = await this.orm.call("learn.path", "can_see_team", []);
                if (this.state.allowed) {
                    this.state.rows = await this.orm.call("learn.path", "readiness", []);
                }
            } catch {
                this.state.allowed = false;
            } finally {
                this.state.loading = false;
            }
        });
    }

    t(key) {
        return T(key);
    }

    get readyCount() {
        return this.state.rows.filter((r) => r.status === "ready").length;
    }

    view(row) {
        const st = STATUS[row.status] || STATUS.not_started;
        const pct = row.required ? Math.round(row.done / row.required * 100) : 100;
        let seen = T("teamNever");
        if (row.last_seen) {
            try {
                const d = new Date(row.last_seen + "Z");
                seen = d.toLocaleDateString(RT.lang === "vi" ? "vi-VN" : "en-GB",
                    { day: "numeric", month: "short" });
            } catch {
                seen = row.last_seen.slice(0, 10);
            }
        }
        const initials = (row.name || "?").split(/\s+/).filter(Boolean)
            .slice(-2).map((w) => w[0]).join("").toUpperCase();
        return {
            ...row,
            initials,
            roleLabel: T(ROLE_LABEL[row.role] || "roleOfficer"),
            statusLabel: T(st.label),
            statusCls: st.cls,
            pct,
            seen,
            next: (row.todo || []).map((s) => tx(s.name)).join(" · "),
        };
    }

    async remind(row) {
        if (this.state.sending) {
            return;
        }
        this.state.sending = row.id;
        this.state.failed = 0;
        try {
            await this.orm.call("learn.path", "remind", [row.id]);
            this.state.sent = { ...this.state.sent, [row.id]: true };
        } catch {
            this.state.failed = row.id;
        } finally {
            this.state.sending = 0;
        }
    }
}
