/** @odoo-module **/
/**
 * Pay & Deliver — a bespoke full-screen experience launched from the Pay Runs
 * cockpit (or the sidebar, which shows a run picker first).
 *   · Bank file       — prepare it, follow it, download the approved one.
 *   · Payment release — ask for the money to be sent; see it land.
 *   · Payslips out    — password-PDF batch delivery with per-slip status pills.
 *
 * PHASE 5. Every lane used to be a button that did the thing. Each is now a
 * button that ASKS — and where the business published "no approval needed" the
 * button says so on its face, so nobody is ever surprised by what a press
 * costs. A lane that is waiting names the person it is waiting for and offers
 * the door to the request: waiting is never a dead end.
 *
 * RPC facade: pb.pay.delivery. pbim-tokenized (.pbpd.pbim). Lucide icons only.
 */
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { download } from "@web/core/network/download";
import { ic } from "@pb_import_kit/js/import_icons";

const MODEL = "pb.pay.delivery";

export class PbPayDelivery extends Component {
    static template = "pb_pay_delivery.PbPayDelivery";
    static props = { action: { type: Object, optional: true }, "*": true };

    setup() {
        this.orm = useService("orm");
        this.notif = useService("notification");
        this.action = useService("action");
        this.ic = ic;
        const runId = this.props.action?.params?.run_id;
        // Somewhere else sent the person here and has to be able to take them
        // back. Deliberately read from the action's own context rather than
        // imported from the hub: this cockpit does not depend on that module,
        // and an import it does not have takes the whole bundle down.
        this.back = this.props.action?.context?.pb_back || null;
        this.state = useState({
            loaded: false,
            busy: false,
            runId: runId || null,
            picking: !runId,     // no run → show the picker
            runs: [],
            data: null,
            bank: null,
            companyAccount: "",
            bankReference: "",
            showExcl: false,
            netShown: 0,         // count-up display
            // WDGAP PR-E — "Paid another way": who is ticked in the left-out
            // list, the open form (method, note, day), and the one undo box
            sel: {},
            payOther: null,
            undo: null,
            // WDGAP S2-C — the payment list in a bank's own layout: which
            // layout ("" = the general list), the payment date, the company
            // account, and what that layout would leave out (preview)
            plLayout: "",
            plDate: "",
            plAccount: "",
            plPreview: null,
            plLayoutSet: false,
        });
        onWillStart(async () => {
            if (this.state.runId) { await this.load(); }
            else { await this.loadRuns(); }
        });
        onMounted(() => this._startCountUp());
        onWillUnmount(() => this._stopCountUp());
    }

    // --------------------------------------------------------------- loaders
    async loadRuns() {
        try {
            this.state.runs = await this.orm.call(MODEL, "get_recent_runs", []);
            this.state.loaded = true;
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
            this.state.loaded = true;
        }
    }

    /** Back to whatever sent us here, with everything it was holding. */
    goBack() {
        if (!this.back) { return; }
        const context = this.back.context || {};
        this.action.doAction({
            type: "ir.actions.client",
            tag: this.back.tag,
            name: this.back.label,
            target: "current",
            params: { ...context },
            context: { ...context },
        }, { clearBreadcrumbs: true });
    }

    async pickRun(id) {
        this.state.runId = id;
        this.state.picking = false;
        this.state.loaded = false;
        await this.load();
        this._startCountUp();
    }

    async load() {
        try {
            const d = await this.orm.call(MODEL, "get_delivery_data", [this.state.runId]);
            this.state.data = d;
            if (!this.state.bank && d.banks.length) {
                // default to the bank the last file used, else Vietcombank,
                // else the first layout there is
                const used = d.banks.find(b => b.key === d.bank_file.bank_format);
                const vcb = d.banks.find(b => b.key === "vietcombank");
                this.state.bank = (used || vcb || d.banks[0]).key;
            }
            const pl = d.payment_list || {};
            if (!this.state.plDate) { this.state.plDate = pl.today || ""; }
            if (!this.state.plLayoutSet) {
                // the layout the last list was prepared with, else the general list
                this.state.plLayoutSet = true;
                const key = (pl.file && pl.file.layout_key) || "";
                if (key && (pl.layouts || []).some((l) => l.key === key)) {
                    this.state.plLayout = key;
                    this.loadPlPreview();
                }
            }
            if (d.release && d.release.bank_reference) {
                this.state.bankReference = d.release.bank_reference;
            } else if (d.release && !d.release.exists) {
                // a new file (a follow-up) has no release yet: never carry
                // the previous transfer's reference over to it (WDGAP PR-C)
                this.state.bankReference = "";
            }
            this.state.loaded = true;
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
            this.state.loaded = true;
        }
    }

    // --------------------------------------------------------------- count-up
    _startCountUp() {
        this._stopCountUp();
        const target = (this.state.data && this.state.data.run.total_net) || 0;
        if (!target) { this.state.netShown = 0; return; }
        const t0 = 900, start = performance.now();
        const step = (now) => {
            const p = Math.min(1, (now - start) / t0);
            const eased = 1 - Math.pow(1 - p, 3);
            this.state.netShown = Math.round(target * eased);
            if (p < 1) { this._raf = requestAnimationFrame(step); }
        };
        this._raf = requestAnimationFrame(step);
    }
    _stopCountUp() { if (this._raf) { cancelAnimationFrame(this._raf); this._raf = null; } }

    // --------------------------------------------------------------- bank file
    selectBank(key) { this.state.bank = key; }
    onCompanyAccount(ev) { this.state.companyAccount = ev.target.value; }
    onBankReference(ev) { this.state.bankReference = ev.target.value; }
    toggleExcl() { this.state.showExcl = !this.state.showExcl; }

    get bankFile() { return (this.state.data && this.state.data.bank_file) || {}; }
    get release() { return (this.state.data && this.state.data.release) || {}; }
    get delivery() { return (this.state.data && this.state.data.delivery) || {}; }

    // --------------------------------------------------- WDGAP PR-C: holds
    get holds() { return (this.state.data && this.state.data.holds) || { count: 0, people: [] }; }
    get followUp() { return (this.state.data && this.state.data.follow_up) || {}; }
    get moneyRows() { return (this.state.data && this.state.data.money) || []; }
    /** Everybody who can be paid has been: a released file, nobody ready. */
    get paidUp() {
        const v = (this.state.data && this.state.data.validation) || {};
        // WDGAP PR-E: also a run whose people were all paid another way
        const runPaid = !!(this.state.data && this.state.data.run.paid);
        return !!((this.followUp.released_files || runPaid) && !v.eligible);
    }
    /** Nobody is ready because everybody left to pay is on hold. */
    get allHeld() {
        const v = (this.state.data && this.state.data.validation) || {};
        return !v.eligible && !(v.excluded || []).length && (v.held_count || 0) > 0;
    }
    /** Of a currency's total: on hold, paid, still to pay — said only when
     *  any of it is not simply "still to pay". */
    get moneySplit() {
        return this.moneyRows.filter((m) => m.held || m.paid || m.paid_other);
    }
    get otherCurrencies() { return this.moneyRows.slice(1); }
    /** Releases already gone out for this run, other than the current one. */
    get releasedBefore() {
        const current = this.release.id;
        return (this.release.history || []).filter((h) => h.id !== current);
    }
    peopleLabel(n) { return n === 1 ? _t("1 person") : _t("%s people", n); }
    get holdsTitle() {
        const n = this.holds.count || 0;
        return n === 1 ? _t("1 person's pay is on hold") : _t("%s people's pay is on hold", n);
    }
    get followUpTitle() {
        const f = this.followUp;
        if (f.from_hold) {
            return f.count === 1
                ? _t("1 person released from hold can be paid now")
                : _t("%s people released from hold can be paid now", f.count);
        }
        return f.count === 1
            ? _t("1 person has not been paid yet")
            : _t("%s people have not been paid yet", f.count);
    }
    get sendHeldLabel() {
        const n = this.delivery.held_ready || 0;
        return n === 1 ? _t("Send the 1 that was held") : _t("Send the %s that were held", n);
    }
    get heldSinceText() {
        const names = this.bankFile.held_since || [];
        return names.length === 1
            ? _t("%s has been put on hold since this file was prepared. Prepare it again before the money is released.", names[0])
            : _t("%(n)s people in this file have been put on hold since it was prepared (%(names)s). Prepare it again before the money is released.",
                 { n: names.length, names: names.join(", ") });
    }

    // ------------------------------------------- WDGAP PR-E: paid another way
    get paidOther() {
        return (this.state.data && this.state.data.paid_other)
            || { count: 0, people: [], methods: [], can_mark: false };
    }
    get paidOtherTitle() {
        const n = this.paidOther.count || 0;
        return n === 1 ? _t("1 person was paid another way") : _t("%s people were paid another way", n);
    }
    /** The left-out rows that can be marked (not the people on hold). */
    get markable() {
        const v = (this.state.data && this.state.data.validation) || {};
        return this.paidOther.can_mark ? (v.excluded || []).filter((x) => x.slip_id) : [];
    }
    get selectedIds() {
        return this.markable.map((x) => x.slip_id).filter((id) => this.state.sel[id]);
    }
    get allSelected() {
        return this.markable.length > 0 && this.selectedIds.length === this.markable.length;
    }
    isSelected(x) { return !!this.state.sel[x.slip_id]; }
    toggleSel(x) {
        if (!x.slip_id) { return; }
        this.state.sel[x.slip_id] = !this.state.sel[x.slip_id];
    }
    toggleAll() {
        const on = !this.allSelected;
        for (const x of this.markable) { this.state.sel[x.slip_id] = on; }
    }
    get markLabel() {
        const n = this.selectedIds.length;
        return n === 1 ? _t("Mark 1 person as paid") : _t("Mark %s people as paid", n);
    }
    get payOtherTooMany() {
        return this.selectedIds.length > (this.paidOther.max_at_once || 50);
    }
    get payOtherReady() {
        const f = this.state.payOther;
        return !!(f && f.method && (f.note || "").trim().length >= 6
                  && this.selectedIds.length && !this.payOtherTooMany
                  && (!f.date || f.date <= (this.paidOther.today || f.date)));
    }
    openPayOther() {
        if (!this.selectedIds.length) {
            this.notif.add(_t("Tick the people who were paid another way first."), { type: "warning" });
            return;
        }
        this.state.undo = null;
        this.state.payOther = { method: "", note: "", date: this.paidOther.today || "" };
    }
    closePayOther() { this.state.payOther = null; }
    setPayMethod(key) { if (this.state.payOther) { this.state.payOther.method = key; } }
    onPayNote(ev) { if (this.state.payOther) { this.state.payOther.note = ev.target.value; } }
    onPayDate(ev) { if (this.state.payOther) { this.state.payOther.date = ev.target.value; } }
    onPayOtherKey(ev) {
        if (ev.key === "Escape") { ev.preventDefault(); this.closePayOther(); }
        else if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); this.confirmPayOther(); }
    }
    async confirmPayOther() {
        if (this.state.busy || !this.payOtherReady) { return; }
        const f = this.state.payOther;
        const ids = this.selectedIds;
        this.state.busy = true;
        try {
            this.state.data = await this.orm.call(MODEL, "mark_paid_other",
                [this.state.runId, ids, f.method, f.note.trim(), f.date || false]);
            this.state.payOther = null;
            this.state.sel = {};
            this.notif.add(ids.length === 1
                ? _t("1 person is marked as paid. They will not be in any bank file.")
                : _t("%s people are marked as paid. They will not be in any bank file.", ids.length),
                { type: "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    openUndo(person) {
        this.state.payOther = null;
        this.state.undo = { slipId: person.slip_id, reason: "" };
    }
    closeUndo() { this.state.undo = null; }
    onUndoReason(ev) { if (this.state.undo) { this.state.undo.reason = ev.target.value; } }
    get undoReady() { return !!(this.state.undo && (this.state.undo.reason || "").trim().length >= 6); }
    onUndoKey(ev) {
        if (ev.key === "Escape") { ev.preventDefault(); this.closeUndo(); }
        else if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); this.confirmUndo(); }
    }
    async confirmUndo() {
        if (this.state.busy || !this.undoReady) { return; }
        const u = this.state.undo;
        this.state.busy = true;
        try {
            this.state.data = await this.orm.call(MODEL, "undo_paid_other",
                [this.state.runId, u.slipId, u.reason.trim()]);
            this.state.undo = null;
            this.notif.add(_t("Marked as not paid. Their pay is still to pay."), { type: "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }
    get paidOtherSinceText() {
        const names = this.bankFile.paid_other_since || [];
        return names.length === 1
            ? _t("%s has been marked as paid another way since this file was prepared. Prepare it again before the money is released.", names[0])
            : _t("%(n)s people in this file have been marked as paid another way since it was prepared (%(names)s). Prepare it again before the money is released.",
                 { n: names.length, names: names.join(", ") });
    }
    get tooManyText() {
        return _t("Mark at most %s people at once.", this.paidOther.max_at_once || 50);
    }

    async releaseHold(person) {
        if (this.state.busy || !person) { return; }
        this.state.busy = true;
        try {
            this.state.data = await this.orm.call(MODEL, "release_hold",
                [this.state.runId, person.slip_id]);
            this.notif.add(
                _t("%s's hold is released. Their pay can go in a payment file now.", person.employee),
                { type: "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    /** What the bank-file button says, so a press never surprises anybody. */
    get prepareLabel() {
        const f = this.followUp;
        if (f.offer && this.bankFile.released) {
            if (f.from_hold) {
                return f.count === 1
                    ? _t("Prepare a payment file for the 1 person released from hold")
                    : _t("Prepare a payment file for the %s people released from hold", f.count);
            }
            return f.count === 1
                ? _t("Prepare a payment file for the 1 person not paid yet")
                : _t("Prepare a payment file for the %s people not paid yet", f.count);
        }
        const again = this.bankFile.exists;
        if (this.bankFile.fast_lane) {
            return again ? _t("Prepare again — approved on the spot")
                         : _t("Prepare and approve now (no approval needed)");
        }
        return again ? _t("Prepare it again and send it in")
                     : _t("Prepare bank file for approval");
    }

    get releaseLabel() {
        return this.release.fast_lane
            ? _t("Release the money now (no approval needed)")
            : _t("Send the release for approval");
    }

    get sendLabel() {
        return this.delivery.fast_lane
            ? _t("Send payslips")
            : _t("Send payslips for approval");
    }

    async prepareBankFile() {
        if (!this.state.bank || this.state.busy) { return; }
        this.state.busy = true;
        try {
            await this.orm.call(MODEL, "prepare_bank_file",
                [this.state.runId, this.state.bank, this.state.companyAccount || false]);
            await this.load();
            const f = this.bankFile;
            this.notif.add(
                f.state === "approved"
                    ? _t("The bank file is ready to download.")
                    : _t("The bank file is with %s for approval.",
                         f.with_whom || _t("its approver")),
                { type: "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async downloadFile() {
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            const act = await this.orm.call(MODEL, "download_bank_file", [this.state.runId]);
            await this.action.doAction(act);
            await this.load();
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // ------------------------------------- WDGAP IDB1: payment list (any bank)
    get payList() {
        return (this.state.data && this.state.data.payment_list)
            || { count: 0, check_count: 0, totals: [], left_out: {}, approved: false };
    }
    /** People of the run the list leaves out (on hold, paid, paid another way). */
    get payListLeftOut() {
        const l = this.payList.left_out || {};
        return (l.held || 0) + (l.paid || 0) + (l.paid_other || 0);
    }
    get payListPeople() { return this.peopleLabel(this.payList.count || 0); }
    get payListChecks() {
        const n = this.payList.check_count || 0;
        if (!n) { return _t("none need a check"); }
        return n === 1 ? _t("1 needs a check") : _t("%s need a check", n);
    }
    get payListLeftOutText() {
        const l = this.payList.left_out || {};
        const bits = [];
        if (l.held) { bits.push(_t("%s on hold", l.held)); }
        if (l.paid) { bits.push(_t("%s paid already", l.paid)); }
        if (l.paid_other) { bits.push(_t("%s paid another way", l.paid_other)); }
        return _t("Not in the list: %s.", bits.join(", "));
    }
    get payListHint() {
        const n = (this.state.data && this.state.data.validation.payment_list_can_pay) || 0;
        return n === 1
            ? _t("1 person left out has an approved bank account and can be paid from the payment list (any bank) below.")
            : _t("%s people left out have an approved bank account and can be paid from the payment list (any bank) below.", n);
    }
    plainMoney(n) { return Math.round(n || 0).toLocaleString("en-US"); }

    // WDGAP IDB2 — the payment list waits for the bank file's own approval
    get payListFile() { return this.payList.file || { exists: false, route: [] }; }
    /** Why the download buttons are off, in plain words ("" when they are on). */
    get payListWhyNot() {
        const f = this.payListFile;
        if (!this.payList.approved) { return _t("Ready once the pay run is approved."); }
        if (!this.payList.count) { return ""; }
        if (f.downloadable) { return ""; }
        if (!f.exists) {
            return _t("The payment list needs the same approval as the bank file before it can be downloaded.");
        }
        if (f.state === "pending") {
            return f.with_whom
                ? _t("It can be downloaded once it is approved. It is with %s.", f.with_whom)
                : _t("It can be downloaded once it is approved.");
        }
        if (f.state === "returned") { return _t("It was sent back. Prepare it again."); }
        if (f.state === "rejected") { return _t("It was turned down. Prepare it again."); }
        return _t("It can be downloaded once it is approved.");
    }
    get payListPrepareLabel() {
        const again = this.payListFile.exists;
        if (this.payListFile.fast_lane) {
            return again ? _t("Prepare the payment list again — approved on the spot")
                         : _t("Prepare the payment list (no approval needed)");
        }
        return again ? _t("Prepare the payment list again and send it in")
                     : _t("Prepare the payment list for approval");
    }
    // ---------------------------- WDGAP S2-C: the bank's own layout
    get plLayouts() { return this.payList.layouts || []; }
    get plLayoutInfo() {
        return this.plLayouts.find((l) => l.key === this.state.plLayout) || null;
    }
    async selectPlLayout(key) {
        this.state.plLayout = key || "";
        this.state.plPreview = null;
        if (key) { await this.loadPlPreview(); }
    }
    onPlDate(ev) { this.state.plDate = ev.target.value; this.loadPlPreview(); }
    onPlAccount(ev) { this.state.plAccount = ev.target.value; }
    async loadPlPreview() {
        if (!this.state.plLayout || !this.state.runId) { this.state.plPreview = null; return; }
        try {
            this.state.plPreview = await this.orm.call(MODEL, "payment_list_layout_preview",
                [this.state.runId, this.state.plLayout, this.state.plDate || false,
                 this.state.plAccount || false]);
        } catch (e) {
            this.state.plPreview = null;
            this.notif.add(this._err(e), { type: "danger" });
        }
    }
    get plPreviewLine() {
        const p = this.state.plPreview;
        if (!p) { return ""; }
        const people = this.peopleLabel(p.count || 0);
        return _t("%(people)s in the %(name)s file • total %(total)s %(currency)s", {
            people, name: p.name, total: (p.total || 0).toLocaleString("en-US",
                { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
            currency: p.currency || "",
        });
    }
    get plLeftOutTitle() {
        const n = ((this.state.plPreview && this.state.plPreview.excluded) || []).length;
        return n === 1 ? _t("1 person is left out of this bank file")
                       : _t("%s people are left out of this bank file", n);
    }
    /** What the people left out are owed, per money (ruling BL1). */
    get plLeftOutTotals() {
        const rows = (this.state.plPreview && this.state.plPreview.left_totals) || [];
        return rows.map((t) => _t("%(people)s · %(total)s %(currency)s to pay another way", {
            people: this.peopleLabel(t.count || 0),
            total: (t.amount || 0).toLocaleString("en-US",
                { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
            currency: t.currency || "",
        })).join(" • ");
    }
    /** Ruling BL4 "Pay by file": in the file, paid into another person's account. */
    get plOtherNameLine() {
        const rows = (this.state.plPreview && this.state.plPreview.other_name_totals) || [];
        return rows.map((t) => _t("%(people)s paid into another person's account · %(total)s %(currency)s", {
            people: this.peopleLabel(t.count || 0),
            total: (t.amount || 0).toLocaleString("en-US",
                { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
            currency: t.currency || "",
        })).join(" • ");
    }
    get plLeftOutRows() {
        return ((this.state.plPreview && this.state.plPreview.excluded) || []).slice(0, 12);
    }
    get plLeftOutMore() {
        const n = ((this.state.plPreview && this.state.plPreview.excluded) || []).length;
        return n > 12 ? _t("and %s more — every one is in the Check column of the list", n - 12) : "";
    }
    get plBankFileLabel() {
        return _t("%s file", this.payListFile.layout_name || "");
    }

    async preparePayList() {
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            await this.orm.call(MODEL, "prepare_payment_list", [this.state.runId,
                this.state.plLayout || false, this.state.plDate || false,
                this.state.plAccount || false]);
            await this.load();
            const f = this.payListFile;
            this.notif.add(
                f.state === "approved"
                    ? _t("The payment list is ready to download.")
                    : _t("The payment list is with %s for approval.", f.with_whom || _t("its approver")),
                { type: "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async downloadPayList(fmt) {
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            // a refusal is a plain sentence here, not a failed download
            await this.orm.call(MODEL, "payment_list_check", [this.state.runId, fmt]);
            await download({
                url: "/pb_pay_delivery/payment_list",
                data: { run_id: this.state.runId, fmt },
            });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // --------------------------------------------------------------- release
    async requestRelease() {
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            await this.orm.call(MODEL, "request_release",
                [this.state.runId, this.state.bankReference || false]);
            await this.load();
            const r = this.release;
            this.notif.add(
                r.state === "released"
                    ? _t("The money is marked as released.")
                    : _t("The release is with %s.", r.with_whom || _t("its approver")),
                { type: "success" });
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // --------------------------------------------------------------- payslips
    async send(forceAll) {
        if (this.state.busy) { return; }
        this.state.busy = true;
        try {
            await this.orm.call(MODEL, "send_payslips", [this.state.runId, !!forceAll]);
            await this.load();
            const d = this.delivery;
            if (d.state === "pending") {
                this.notif.add(
                    _t("The payslips are with %s for approval.",
                       d.with_whom || _t("their approver")), { type: "success" });
            } else {
                const held = d.held
                    ? " " + _t("%s not sent: pay on hold.", d.held) : "";
                this.notif.add(
                    _t("Delivery complete — %s sent, %s failed, %s skipped.",
                       d.sent, d.failed, d.skipped) + held,
                    { type: d.failed ? "warning" : "success" });
            }
        } catch (e) {
            this.notif.add(this._err(e), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    // --------------------------------------------------------------- the door
    async openRequest(requestId) {
        if (!requestId) { return; }
        const act = await this.orm.call(MODEL, "open_request", [requestId]);
        this.action.doAction(act);
    }

    backToRuns() {
        this.state.picking = true;
        this.state.data = null;
        this.state.runId = null;
        this.state.bank = null;
        this.loadRuns();
    }

    // --------------------------------------------------------------- helpers
    get bankName() {
        const b = this.state.data && this.state.data.banks.find(x => x.key === this.state.bank);
        return b ? b.name : "";
    }
    money(n, symbol) {
        if (n === null || n === undefined) { return "—"; }
        const cur = symbol || (this.state.data && this.state.data.currency) || "₫";
        return cur + " " + Math.round(n).toLocaleString("en-US");
    }
    fileSize(bytes) {
        if (!bytes) { return "0 B"; }
        if (bytes >= 1024 * 1024) { return (bytes / 1048576).toFixed(1) + " MB"; }
        if (bytes >= 1024) { return (bytes / 1024).toFixed(1) + " KB"; }
        return bytes + " B";
    }
    /** The tone of a lane's status chip. One vocabulary for all three. */
    toneOf(state) {
        return {
            approved: "ok", released: "ok", done: "ok", posted: "ok",
            pending: "wait", draft: "", returned: "warn", sending: "wait",
            rejected: "bad", superseded: "muted",
        }[state] || "";
    }
    stepTone(status) {
        return { done: "ok", active: "wait", blocked: "bad",
                 returned: "warn", skipped: "muted" }[status] || "";
    }
    pillClass(state) {
        return { sent: "ok", failed: "bad", skipped_no_email: "warn",
                 held: "hold" }[state] || "";
    }
    pillLabel(state) {
        return { sent: _t("Sent"), failed: _t("Failed"),
                 skipped_no_email: _t("No email"), held: _t("On hold") }[state] || state;
    }
    /** A date-time from the server ("2026-11-14 05:01:02") as a short date. */
    shortDate(value) {
        if (!value) { return ""; }
        const d = new Date(value.replace(" ", "T") + "Z");
        if (isNaN(d)) { return value; }
        return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
    }
    reasonList(reasons) { return (reasons || []).join(" · "); }
    // deep-link an excluded row to the employee's record so the reviewer can go
    // straight to the bank account that failed validation (payload carries the id)
    openEmployeeBank(employeeId) {
        if (!employeeId) { return; }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.employee",
            res_id: employeeId,
            views: [[false, "form"]],
            target: "current",
        });
    }
    _err(e) {
        return (e && e.data && e.data.message) || (e && e.message) || _t("Action failed.");
    }
}

registry.category("actions").add("pb_pay_delivery", PbPayDelivery);
