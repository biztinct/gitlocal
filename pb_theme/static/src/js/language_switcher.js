/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { loadLanguages, _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";

/**
 * A direct language preference in the main Payobook chrome.
 *
 * The list deliberately comes from res.lang.get_installed() rather than a
 * Payobook-owned list. Activating a third language in Odoo therefore makes it
 * available here on the next page load without another code change.
 */
export class PbLanguageSwitcher extends Component {
    static template = "pb_theme.LanguageSwitcher";
    static components = { Dropdown, DropdownItem };
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({ languages: [], switching: false });

        onWillStart(async () => {
            const languages = await loadLanguages(this.orm);
            this.state.languages = languages.map(([code, name]) => ({ code, name }));
        });
    }

    get currentCode() {
        return user.context.lang || "en_US";
    }

    get currentLanguage() {
        return this.state.languages.find(({ code }) => code === this.currentCode);
    }

    get currentLabel() {
        return this.currentLanguage?.name || this.currentCode;
    }

    get currentShortCode() {
        return this.currentCode.split(/[_@-]/)[0].toUpperCase();
    }

    get toggleAriaLabel() {
        return _t("Change language. Current language: %s", this.currentLabel);
    }

    async selectLanguage(code) {
        if (this.state.switching || code === this.currentCode) {
            return;
        }
        this.state.switching = true;
        try {
            await this.orm.write("res.users", [user.userId], { lang: code });
            user.updateContext({ lang: code });
            browser.location.reload();
        } catch (_error) {
            this.state.switching = false;
            this.notification.add(_t("Could not change language. Please try again."), {
                type: "danger",
            });
        }
    }
}

registry.category("systray").add(
    "pb_theme.language_switcher",
    { Component: PbLanguageSwitcher },
    // The navbar reverses systray sequence order. A value above the standard
    // messaging/activity entries places this control immediately to their left.
    { sequence: 30 }
);
