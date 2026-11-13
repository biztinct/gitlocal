/** @odoo-module **/

import { beforeEach, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import {
    contains,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
    serverState,
} from "@web/../tests/web_test_helpers";

import { browser } from "@web/core/browser/browser";
import { loadLanguages } from "@web/core/l10n/translation";
import { PbLanguageSwitcher } from "@pb_theme/js/language_switcher";

beforeEach(() => {
    serverState.lang = "en_US";
    loadLanguages.installedLanguages = null;
});

test("lists every installed language and marks the current one", async () => {
    onRpc("res.lang", "get_installed", () => [
        ["en_US", "English (US)"],
        ["vi_VN", "Vietnamese / Tiếng Việt"],
        ["fr_FR", "French / Français"],
    ]);

    await mountWithCleanup(PbLanguageSwitcher);
    expect(".pb-language-switcher__code").toHaveText("EN");
    await contains(".pb-language-switcher__toggle").click();
    expect(".o-dropdown--menu .dropdown-item").toHaveCount(3);
    expect(".dropdown-item[data-language-code='en_US']").toHaveAttribute(
        "aria-current",
        "true"
    );
    expect(".dropdown-item[data-language-code='fr_FR']").toHaveText(
        "French / FrançaisFR"
    );
});

test("writes the user preference and reloads after a language change", async () => {
    onRpc("res.lang", "get_installed", () => [
        ["en_US", "English (US)"],
        ["vi_VN", "Vietnamese / Tiếng Việt"],
    ]);
    onRpc("res.users", "write", ({ args }) => {
        expect.step(`write:${args[0][0]}:${args[1].lang}`);
        return true;
    });
    patchWithCleanup(browser.location, {
        reload: () => expect.step("reload"),
    });

    await mountWithCleanup(PbLanguageSwitcher);
    await contains(".pb-language-switcher__toggle").click();
    await contains(".dropdown-item[data-language-code='vi_VN']").click();
    await animationFrame();
    expect.verifySteps([`write:${serverState.uid}:vi_VN`, "reload"]);
});
