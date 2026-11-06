/** @odoo-module **/
/*  Copyright 2022-2023 Ivan Yelizariev <https://twitter.com/yelizariev>
    License OPL-1 (https://www.odoo.com/documentation/user/14.0/legal/licenses/licenses.html#odoo-apps). */
/*  Odoo 19 compatibility: translatedTerms may not be available */

import { localizationService } from "@web/core/l10n/localization_service";

// Odoo 19: translatedTerms is no longer exported, debranding handled elsewhere
export const debrandTranslation = () => {
    // Stub function for Odoo 19 compatibility
    // Translation debranding is handled via server-side mechanisms
};

// Only patch if localizationService.start exists
if (localizationService && localizationService.start) {
    const start = localizationService.start;
    localizationService.start = async (...args) => {
        const localization = await start(...args);
        debrandTranslation();
        return localization;
    };
}
