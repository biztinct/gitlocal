/** @odoo-module **/
/**
 * Offer letters in the Document studio (DOCSTUDIO phase A1).
 *
 * A patch of the studio's own component, nothing copied:
 *   - "Preview with: an offer" — the picker lists real offers the user may
 *     read (`pb.doc.studio.offers`) instead of people;
 *   - the Hiring gallery group gets its icon, the offer's field groups theirs;
 *   - "Make a copy for…" speaks of offers when the document is an offer.
 * The server answers `preview` / `sample_pdf` for an offer letter with the
 * offer picked (same call shape), so the hero preview works unchanged.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { DocStudio } from "@pb_doc_studio/js/doc_studio";
import { FIELD_GROUP_ICON, KIND_ICON } from "@pb_doc_studio/js/doc_icons";
import { FACADE } from "@pb_doc_studio/js/doc_words";

KIND_ICON.hiring = "briefcase";
FIELD_GROUP_ICON.candidate = "user";
FIELD_GROUP_ICON.pay = "banknote";

patch(DocStudio.prototype, {
    /** The document open in the designer is an offer letter. */
    get isOfferDoc() {
        return Boolean(this.state.doc && this.state.doc.preview_kind === "offer");
    },
    get previewWithText() {
        return this.isOfferDoc ? _t("An offer") : _t("A person");
    },
    get findPreviewText() {
        return this.isOfferDoc ? _t("Find an offer") : _t("Find a person");
    },
    get candidateSignName() {
        const p = this.state.person;
        return (this.isOfferDoc && p && p.name) || _t("The candidate");
    },
    /** The studio keeps the preview person from one document to the next;
     *  between a letter and an offer letter the kind changes, so the
     *  document's own sample (a person or an offer) is used instead. */
    applyDoc(doc) {
        const p = this.state.person;
        const want = doc && doc.preview_kind === "offer" ? "offer" : "person";
        const have = p && p.kind === "offer" ? "offer" : "person";
        if (p && want !== have) {
            this.state.person = null;
        }
        return super.applyDoc(doc);
    },
    offerRowText(p) {
        return [p.ref, p.job || p.company, p.state].filter((v) => v).join(" · ");
    },
    async searchPeople(term) {
        if (!this.isOfferDoc) {
            return super.searchPeople(term);
        }
        this.state.peopleBusy = true;
        try {
            this.state.people = await this.orm.call(FACADE, "offers", [term]);
        } catch {
            this.state.people = [];
        } finally {
            this.state.peopleBusy = false;
        }
    },
    /** The copy sentence for an offer letter speaks of offers and roles. */
    get copySentence() {
        const d = this.state.dialog;
        const card = d && d.card;
        const offer = Boolean(card && (card.kind === "hiring" || (!card.kind && this.isOfferDoc)));
        if (!offer) {
            return super.copySentence;
        }
        const b = this.state.board;
        const company = d.company ? (b.companies.find((c) => c.id === Number(d.company)) || {}).name : "";
        const countries = b.countries.filter((c) => d.countries.includes(c.id)).map((c) => c.name).join(", ");
        if (company && countries) {
            return _t("Offers for roles at %(company)s in %(countries)s will use this copy.", { company, countries });
        }
        if (company) { return _t("Offers for roles at %s will use this copy.", company); }
        if (countries) { return _t("Offers for roles in %s will use this copy.", countries); }
        return super.copySentence;
    },
});
