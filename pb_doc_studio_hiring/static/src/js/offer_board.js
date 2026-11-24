/** @odoo-module **/
/**
 * Hiring board, offer panel: the letter's language (owner ruling, DOCSTUDIO
 * A1 follow-up). Empty = automatic (the language the candidate applied in,
 * else the company's); the recruiter may choose another before it goes out.
 * A patch of Hiring's own board — no Hiring file edited.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PbHiringBoard } from "@pb_hiring/js/hiring_board";

patch(PbHiringBoard.prototype, {
    letterLangAutoText(offer) {
        if (!offer || !offer.letter_lang_auto) {
            return _t("Language: automatic");
        }
        return _t("Language: %(lang)s, automatic (%(why)s)", { lang: offer.letter_lang_auto, why: offer.letter_lang_why });
    },
    async setLetterLang(ev) {
        await this.act("offer_letter_lang", { offer_id: this.offer.id, lang: ev.target.value || false });
    },
});
