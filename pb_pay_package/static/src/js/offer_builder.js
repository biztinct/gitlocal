/** @odoo-module **/
import { Component, onWillStart, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { PbHiringBoard } from "@pb_hiring/js/hiring_board";
import { PayBuilder } from "@pb_pay_builder/js/pay_builder";
import { money } from "@pb_pay_builder/js/pay_format";

const MODEL = "pb.pay.builder";

export class OfferPayBuilder extends Component {
    static template = "pb_pay_package.OfferPayBuilder";
    static components = { Dialog, PayBuilder };
    static props = ["offerId", "afterUse", "close"];
    setup() {
        this.orm = useService("orm");
        this.ui = useState({ schemes: [], scheme_id: 0, values: {}, tries: {}, letter_table: true, answer: null, error: "", saving: false });
        onWillStart(async () => {
            try {
                Object.assign(this.ui, await this.orm.call(MODEL, "offer_builder_open", [this.props.offerId]));
            } catch (error) {
                this.ui.error = error.data?.message || _t("The offer could not be opened.");
            }
        });
    }
    get title() { return _t("Pay Builder"); }
    get ready() { return this.ui.answer?.state === "ok" && !this.ui.answer.has_failed && this.ui.answer.totals.gross != null; }
    get earnings() { return this.ui.answer?.sections.find(s => s.key === "earn")?.lines.filter(r => r.amount > 0) || []; }
    get netSentence() { return _t("Take-home after the usual deductions is about %s a month.", this.format(this.ui.answer.totals.net)); }
    get grossSentence() { return _t("Gross pay of %s a month.", this.format(this.ui.answer.totals.gross)); }
    format(value) { return money(value, { ...this.ui.answer.currency, builder: true }); }
    choose(ev) {
        this.letterRequest = (this.letterRequest || 0) + 1;
        this.ui.scheme_id = Number(ev.target.value);
        this.ui.tries = {};
        this.ui.values = {};
        this.ui.answer = null;
        this.ui.error = "";
    }
    async readLetter(answer) {
        const request = this.letterRequest = (this.letterRequest || 0) + 1;
        if (!Object.keys(this.ui.tries).length) {
            this.ui.answer = answer;
            return;
        }
        // The contract and the letter use the usual month. What-ifs stay in the block.
        const reference = { offer_id: this.props.offerId, scheme_id: this.ui.scheme_id };
        try {
            const usual = await this.orm.call(MODEL, "work_out", ["offer", reference, this.ui.values]);
            if (request === this.letterRequest) this.ui.answer = usual;
        } catch {
            if (request === this.letterRequest) this.ui.answer = null;
        }
    }
    change(code, value) {
        this.letterRequest = (this.letterRequest || 0) + 1;
        this.ui.answer = null;
        if (value == null) delete this.ui.values[code];
        else this.ui.values[code] = value;
    }
    async use() {
        if (!this.ready || this.ui.saving) return;
        this.ui.saving = true;
        this.ui.error = "";
        try {
            await this.orm.call(MODEL, "offer_builder_use", [this.props.offerId, this.ui.scheme_id, this.ui.values, this.ui.letter_table]);
            await this.props.afterUse();
            this.props.close();
        } catch (error) {
            this.ui.error = error.data?.message || _t("The offer could not be saved. Try again.");
        } finally {
            this.ui.saving = false;
        }
    }
}

patch(PbHiringBoard.prototype, {
    setup() {
        super.setup(...arguments);
        this.payBuilderDialog = useService("dialog");
    },
    openOfferBuilder(offer) {
        if (this.pbpkCanBuild(offer)) this.payBuilderDialog.add(OfferPayBuilder, { offerId: offer.id, afterUse: () => this.refresh() });
    },
    async setOfferPayTable(offer, event) {
        const input = event.target;
        input.disabled = true;
        try {
            await this.orm.call(MODEL, "offer_builder_letter", [offer.id, input.checked]);
            await this.refresh();
        } catch (error) {
            input.checked = offer.pbpb_letter_table;
            this.notif.add(error.data?.message || _t("The offer could not be saved. Try again."), { type: "warning" });
        } finally {
            input.disabled = false;
        }
    },
});
