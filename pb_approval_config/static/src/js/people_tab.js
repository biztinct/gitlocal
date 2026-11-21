/** @odoo-module **/
/**
 * People & backups — who fills each responsibility, where.
 *
 * THE GRID IS THE WHOLE SCREEN. Responsibilities down the side, the parts of
 * the business across the top, and in every cell exactly one of four honest
 * answers: a named person, a group of people, "covered by the company-wide
 * person" where the responsibility allows that, or a gap in rose with the one
 * button that mends it. There is deliberately no fifth answer — no "anybody in
 * HR", no "the first match", nothing the engine would have had to guess.
 *
 * A GAP IS NOT A WARNING, IT IS A PLACE REQUESTS CANNOT COME FROM. So it is
 * said at the top, in a bar that names the seats, before anybody scrolls.
 *
 * FILLING A SEAT GRANTS NOBODY ANYTHING. The picker offers people who cannot
 * yet open this kind of request, marks them "Needs permission" and says where
 * that is given — because hiding them would leave the reader unable to finish
 * the job and unable to see why.
 *
 * HAND-OVERS ARE TIME-BOXED AND END BY THEMSELVES. Every card in the inbox says
 * "covering for", and the decision is recorded under both names.
 */
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { ic } from "@pb_import_kit/js/import_icons";
import { day, initials } from "@pb_approval_config/js/sentence";

export class PeopleTab extends Component {
    static template = "pb_approval_config.PeopleTab";
    static props = {
        companyId: { type: Number, optional: true },
        focus: { type: Object, optional: true },
    };

    setup() {
        this.ic = ic;
        this.initials = initials;
        this.day = day;
        this.orm = useService("orm");
        this.notif = useService("notification");

        this.state = useState({
            loading: true,
            failed: "",
            data: null,
            assign: null,
            candidates: [],
            search: "",
            handover: null,
            busy: false,
        });

        onWillStart(async () => {
            await this.load();
            const focus = this.props.focus;
            if (focus && focus.role_key) {
                this.openAssign(focus.role_key, focus.scope_key || "");
            }
        });
    }

    async load() {
        this.state.loading = true;
        this.state.failed = "";
        try {
            this.state.data = await this.orm.call(
                "pb.approval.matrix", "get_people",
                [this.props.companyId || false]);
        } catch (error) {
            this.state.failed = (error.data && error.data.message)
                || _t("This could not be read.");
        } finally {
            this.state.loading = false;
        }
    }

    get data() { return this.state.data || { roles: [], scopes: [], gaps: [] }; }
    get gaps() { return this.data.gaps || []; }

    get gapSentence() {
        const names = this.gaps.map(
            (gap) => _t("%(role)s for %(scope)s",
                        { role: gap.role, scope: gap.scope }));
        return names.join(", ");
    }

    // ---------------------------------------------------------- the drawer
    async openAssign(roleKey, scopeKey) {
        const role = (this.data.roles || []).find((one) => one.key === roleKey);
        const scope = (this.data.scopes || [])
            .find((one) => one.key === (scopeKey || ""));
        this.state.assign = {
            roleKey,
            roleName: role ? role.name : roleKey,
            pool: Boolean(role && role.pool),
            scopeKey: scopeKey || "",
            scopeLabel: scope ? scope.label : this.data.company_name,
            picked: [],
            backup: 0,
        };
        this.state.search = "";
        await this.loadCandidates();
    }

    closeAssign() { this.state.assign = null; }

    async loadCandidates() {
        this.state.candidates = await this.orm.call(
            "pb.approval.matrix", "user_options",
            [this.state.search, this.state.assign.roleKey,
             this.props.companyId || false, false]);
    }

    async onSearch(ev) {
        this.state.search = ev.target.value;
        await this.loadCandidates();
    }

    pick(id) {
        const assign = this.state.assign;
        if (assign.pool) {
            assign.picked = assign.picked.includes(id)
                ? assign.picked.filter((one) => one !== id)
                : assign.picked.concat(id);
        } else {
            assign.picked = [id];
        }
    }

    setBackup(ev) {
        this.state.assign.backup = Number(ev.target.value || 0);
    }

    get canAssign() {
        return Boolean(this.state.assign
                       && this.state.assign.picked.length);
    }

    async saveAssign() {
        const assign = this.state.assign;
        this.state.busy = true;
        try {
            await this.orm.call(
                "pb.approval.matrix", "set_responsibility",
                [this.data.company_id, assign.roleKey, assign.scopeKey,
                 assign.picked[0], assign.backup || false, false, "",
                 assign.pool ? assign.picked : []]);
            this.state.assign = null;
            await this.load();
            this.notif.add(
                _t("Saved. New requests use this; anything already under way keeps the people it was given."),
                { type: "success" });
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                || _t("That person could not be given this responsibility."),
                { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async clear(roleKey, scopeKey) {
        try {
            await this.orm.call(
                "pb.approval.matrix", "clear_responsibility",
                [this.data.company_id, roleKey, scopeKey || ""]);
            await this.load();
            this.notif.add(
                _t("Left empty. Requests from there will say so rather than go to the wrong person."),
                { type: "warning" });
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                || _t("That could not be changed."), { type: "danger" });
        }
    }

    // ------------------------------------------------------- the hand-overs
    async openHandover() {
        this.state.handover = {
            principal: 0, delegate: 0, from: "", to: "", reason: "",
        };
        this.state.search = "";
        this.state.candidates = await this.orm.call(
            "pb.approval.matrix", "user_options",
            ["", false, this.props.companyId || false, false]);
    }

    closeHandover() { this.state.handover = null; }

    setHandover(field, ev) {
        const value = ["principal", "delegate"].includes(field)
            ? Number(ev.target.value || 0) : ev.target.value;
        this.state.handover[field] = value;
    }

    get canHandover() {
        const held = this.state.handover;
        return Boolean(held && held.delegate && held.from && held.to
                       && held.reason.trim().length > 2
                       && held.delegate !== held.principal);
    }

    async saveHandover() {
        const held = this.state.handover;
        this.state.busy = true;
        try {
            await this.orm.call("pb.approval.matrix", "set_delegation", [{
                company_id: this.data.company_id,
                principal_user_id: held.principal || false,
                delegate_user_id: held.delegate,
                date_from: held.from,
                date_to: held.to,
                reason: held.reason,
            }]);
            this.state.handover = null;
            await this.load();
            this.notif.add(_t("Cover arranged. It ends by itself."),
                           { type: "success" });
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                || _t("That cover could not be arranged."),
                { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async endHandover(id) {
        try {
            await this.orm.call("pb.approval.matrix", "end_delegation", [id]);
            await this.load();
            this.notif.add(_t("Stopped. They keep their own seats again."),
                           { type: "info" });
        } catch (error) {
            this.notif.add(
                (error.data && error.data.message)
                || _t("That could not be stopped."), { type: "danger" });
        }
    }
}
