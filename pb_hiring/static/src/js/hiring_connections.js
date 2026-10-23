/** @odoo-module **/
import { Component, useState, useRef, useEffect, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class HiringConnections extends Component {
    static template = "pb_hiring.Connections";
    static props = ["*"];
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ cards: [], company: "", selected: null, step: 0, busy: false, error: "", values: {} });
        this.dialog = useRef("dialog");
        useEffect(() => {
            if (!this.dialog.el) return;
            const previous = document.activeElement;
            this.dialog.el.querySelector("button")?.focus();
            return () => previous?.focus?.();
        }, () => [this.state.selected?.key]);
        onWillStart(() => this.load());
    }
    async load() {
        try { Object.assign(this.state, await this.orm.call("pb.hiring", "connection_overview", [])); }
        catch (e) { this.state.error = e.data?.message || "Could not load hiring connections."; }
    }
    select(card) {
        this.state.selected = card;
        this.state.values = Object.fromEntries(card.fields.map(f => [f.key, f.value || ""]));
        this.state.step = 0; this.state.error = "";
    }
    close() { if (!this.state.busy) this.state.selected = null; }
    onDialogKey(event) {
        if (event.key === "Escape") { event.preventDefault(); this.close(); }
        if (event.key !== "Tab") return;
        const items = Array.from(this.dialog.el.querySelectorAll("button:not(:disabled), input:not(:disabled), a[href]"));
        const first = items[0], last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
    async run(method, args, next) {
        this.state.busy = true; this.state.error = "";
        try {
            this.state.selected = await this.orm.call("pb.hiring", method, args);
            this.state.values = Object.fromEntries(this.state.selected.fields.map(f => [f.key, f.value || ""]));
            this.state.step = next;
            await this.load();
        } catch (e) { this.state.error = e.data?.message || "The check did not finish. Try again."; }
        finally { this.state.busy = false; }
    }
    save() { return this.run("connection_save", [this.state.selected.key, this.state.values], 2); }
    check() { return this.run("connection_check", [this.state.selected.key], 2); }
    enable() { return this.run("connection_enable", [this.state.selected.key, !this.state.selected.enabled], 3); }
    openAction(xmlid) { return this.action.doAction(xmlid); }
    back() { return this.action.doAction("pb_hiring.action_pb_hiring_setup"); }
}
registry.category("actions").add("pb_hiring_connections", HiringConnections);

import { patch } from "@web/core/utils/patch";
import { PbHiringBoard } from "./hiring_board";
patch(PbHiringBoard.prototype, {
    async candidateConnection(method) {
        const id = this.state.cand?.id;
        if (!id) return;
        try {
            const result = await this.orm.call("hr.applicant", method, [[id]]);
            if (result?.type) await this.action.doAction(result);
        } catch (e) { this.notif.add(e.data?.message || "This step could not be completed.", { type: "danger" }); }
    },
    candidateConnectionDetails() {
        return this.action.doAction({type: "ir.actions.act_window", res_model: "hr.applicant", res_id: this.state.cand.id, views: [[false,"form"]], target: "current"});
    },
});
