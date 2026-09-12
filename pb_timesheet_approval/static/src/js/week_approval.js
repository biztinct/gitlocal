/** @odoo-module **/
/**
 * The weekly grid learns one more verb: send the WEEK in.
 *
 * A PATCH AND NOT A FORK. `pb_hr_workforce` owns the weekly grid and knows
 * nothing about approvals — it must not, or the workforce module would end up
 * depending on the approval engine. So this module patches the component it
 * already ships: one extra piece of state, one fetch, two presses. The grid's
 * own behaviour is untouched; every call still goes through the grid's own
 * facade, which gates itself exactly as before.
 *
 * WHAT THE PERSON SEES. A panel at the top of the right-hand rail listing, for
 * the week and department on screen, who has been sent in and who has not —
 * with the name of whoever it is waiting on, because "pending" without a name
 * is a dead end. One press sends the whole visible week in; one press per row
 * sends one person's.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AttendanceWeekGrid } from "@pb_hr_workforce/js/attendance_weekgrid";

patch(AttendanceWeekGrid.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.packets = { rows: [], summary: { draft: 0, pending: 0, approved: 0 } };
        this.state.packetBusy = false;
    },

    /** The tray stays on screen while there is a week left to send in. */
    get hasQueue() {
        const summary = this.state.packets.summary || {};
        return super.hasQueue || (summary.draft || 0) > 0 || (summary.pending || 0) > 0;
    },

    async _doFetch() {
        const data = await super._doFetch(...arguments);
        await this._loadPackets();
        return data;
    },

    async _loadPackets() {
        try {
            this.state.packets = await this._rpc("week_packets", [
                this.wf.weekStart, this.wf.departmentId || false, false,
            ]);
        } catch {
            // A status panel must never be the thing that stops the grid
            // loading: an empty panel is a worse screen, a broken grid is a
            // worse day.
            this.state.packets = { rows: [], summary: { draft: 0, pending: 0, approved: 0 } };
        }
    },

    /** Rows worth showing: everybody with hours, or anything already moving. */
    get packetRows() {
        return (this.state.packets.rows || []).filter(
            (row) => row.hours > 0 || row.state !== "draft");
    },

    /** The send-back reasons, so nobody has to open a request to read one. */
    get packetNotes() {
        return this.packetRows.filter((row) => row.note);
    },

    get packetsToSend() {
        return this.packetRows.filter(
            (row) => row.state === "draft" || row.state === "returned").length;
    },

    async submitWeekPackets() {
        if (this.state.packetBusy) { return; }
        this.state.packetBusy = true;
        try {
            const result = await this._rpc("submit_week_packets", [
                this.wf.weekStart, this.wf.departmentId || false, false,
            ]);
            const sent = result.weeks_submitted || 0;
            const problems = result.weeks_problems || [];
            if (sent) {
                this.notif.add(
                    _t("%s week(s) sent in for approval.", sent),
                    { type: "success" });
            }
            for (const problem of problems.slice(0, 3)) {
                this.notif.add(`${problem.employee}: ${problem.why}`,
                    { type: "warning", sticky: true });
            }
            if (!sent && !problems.length) {
                this.notif.add(
                    _t("Every week on screen has already been sent in."),
                    { type: "info" });
            }
            await this._loadPackets();
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                    || error.message || _t("The week could not be sent in."),
                { type: "danger" });
        } finally {
            this.state.packetBusy = false;
        }
    },

    async submitWeekFor(employeeId) {
        if (this.state.packetBusy) { return; }
        this.state.packetBusy = true;
        try {
            await this._rpc("submit_week_for", [employeeId, this.wf.weekStart]);
            this.notif.add(_t("Sent in for approval."), { type: "success" });
            await this._loadPackets();
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                    || error.message || _t("The week could not be sent in."),
                { type: "danger" });
        } finally {
            this.state.packetBusy = false;
        }
    },

    /** The door into the one inbox, on the request this week is waiting in. */
    openWeekRequest(requestId) {
        if (!requestId) { return; }
        this.actionService.doAction({
            type: "ir.actions.client",
            tag: "pb_approval_inbox",
            name: _t("Approvals"),
            params: { request_id: requestId },
        });
    },
});
