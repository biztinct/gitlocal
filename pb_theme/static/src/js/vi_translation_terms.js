/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

// Odoo 19's upstream Vietnamese catalogs leave these backend terms untranslated.
// Keeping them in an installed custom asset makes the reviewed vi_VN values
// available to the shared frontend translation dictionary.
export const viTranslationTerms = [
    _t("Shortcuts"),
    _t("My Preferences"),
    _t("Online"),
    _t("Offline"),
    _t("You will not receive any notifications"),
    _t("Chat"),
];
