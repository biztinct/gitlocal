/** @odoo-module **/
/* Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
 *
 * Client-side half of the white-label layer. Two global seams replace what
 * would otherwise be ~30 brittle per-component patches:
 *
 *  1. TranslatedString.prototype.valueOf — every `_t(...)` in every module.
 *     web_debranding cannot reach these: its only surviving hook rewrites the
 *     translation *catalogue*, and Odoo ships no catalogue for the source
 *     language, so in en_US `_t("Install Odoo")` returns its own msgid.
 *     Patching valueOf() is language-independent and covers modules that are
 *     installed later. (Same reasoning as biz_theme/js/biz_error_dialogs.js,
 *     which had to strip "Odoo " from core dialog titles by hand.)
 *
 *  2. registerTemplateProcessor — prose inside static OWL templates
 *     (`static/src/xml/**`), e.g. the scoped-app install page and the import
 *     wizard's "Odoo Field" column header.
 *
 * The rewrite rules mirror biz_debrand/models/brand.py character for
 * character; keep the two in step.
 */
import { TranslatedString } from "@web/core/l10n/translation";
import { registerTemplateProcessor } from "@web/core/templates";

const DEFAULT_BRAND = "BizApp";
const DEFAULT_WEBSITE = "https://example.com";

// Cheap pre-filter. Deliberately NOT global: `.test()` on a /g regex is
// stateful via lastIndex and would return alternating results.
const HAS_ODOO = /odoo/i;

const DOC_URL = /https?:\/\/(?:www\.)?odoo\.com\/documentation\/?/gi;
// Leading capture group instead of a lookbehind (browser support), anchoring
// the match at a label boundary so a vendor SUBDOMAIN is left intact:
// rewriting only the tail of `apps.odoo.com` would yield a host that does not
// exist. Mirrors DOMAIN_RE in models/brand.py.
const DOMAIN = /(^|[^.\w])(?:www\.)?odoo\.com\b/gi;
const BOT = /\bodoo[\s_-]*bot\b/gi;
const SA = /\bodoo\s+s\.?\s?a\.?(?![\w.])/gi;
// Generic rule. Written with a leading capture group rather than a lookbehind
// so it works on browsers without lookbehind support. The guards keep code
// intact: `odoo.define`, `odoo[`, `odoo =`, `@odoo-module`, `/odoo/`.
const WORD = /(^|[^.\w/-])odoo(?![\w/[-])(?!\.\w)(?!\s*=)/gi;

/**
 * Read the brand injected by biz_debrand's web.layout inherit. Synchronous and
 * available on both backend and frontend pages, unlike web_debranding's
 * post-mount ORM round-trip.
 */
function readBrand() {
    let name = DEFAULT_BRAND;
    let website = DEFAULT_WEBSITE;
    try {
        const nameMeta = document.querySelector('meta[name="biz-brand"]');
        const siteMeta = document.querySelector('meta[name="biz-brand-website"]');
        if (nameMeta && nameMeta.content) {
            name = nameMeta.content;
        }
        if (siteMeta && siteMeta.content) {
            website = siteMeta.content;
        }
    } catch {
        // Keep the defaults; branding must never break the page.
    }
    return { name, website };
}

const brand = readBrand();
const host = brand.website.replace(/^https?:\/\//, "").replace(/\/+$/, "") || "example.com";
const docUrl = brand.website.replace(/\/+$/, "") + "/documentation/";

/**
 * @param {string} text
 * @returns {string} the text with every user-visible vendor reference replaced
 */
export function debrandText(text) {
    if (!text || typeof text !== "string" || !HAS_ODOO.test(text)) {
        return text;
    }
    return text
        .replace(DOC_URL, docUrl)
        .replace(DOMAIN, (m, prefix) => prefix + host)
        .replace(BOT, brand.name)
        .replace(SA, brand.name)
        .replace(WORD, (match, prefix) => prefix + brand.name);
}

/**
 * Repoint vendor URLs at the brand's own site. Only the domain rules apply —
 * never the generic word rule — so `/odoo/action-1` and `odoocdn.com` asset
 * URLs keep working while a visitable https://odoo.com link does not.
 *
 * @param {string} url
 * @returns {string}
 */
export function debrandUrl(url) {
    if (!url || typeof url !== "string" || !HAS_ODOO.test(url)) {
        return url;
    }
    return url.replace(DOC_URL, docUrl).replace(DOMAIN, (m, prefix) => prefix + host);
}

// ---------------------------------------------------------------------------
// Seam 1 — every _t() call
// ---------------------------------------------------------------------------
const originalValueOf = TranslatedString.prototype.valueOf;
TranslatedString.prototype.valueOf = function () {
    const value = originalValueOf.call(this);
    // Markup results are String subclasses, not primitives; leave them alone
    // rather than risk flattening escaped HTML into a plain string.
    return typeof value === "string" ? debrandText(value) : value;
};

// ---------------------------------------------------------------------------
// Seam 2 — prose inside static OWL templates
// ---------------------------------------------------------------------------

// Attributes holding prose a human reads. Anything else — and anything
// starting with "t-" — is an expression or a technical value.
const PROSE_ATTRS = new Set([
    "alt",
    "aria-label",
    "aria-placeholder",
    "confirm",
    "content",
    "data-tooltip",
    "help",
    "label",
    "placeholder",
    "string",
    "title",
]);

// Attributes holding a URL — domain rules only, see debrandUrl.
const URL_ATTRS = new Set(["href", "src", "action", "data-url", "data-src"]);

// Executable/stylistic payloads, and code samples — help panels quote real
// Python and JS that the generic word rule would rewrite into broken code.
const OPAQUE_TAGS = new Set(["script", "style", "code", "pre", "samp", "kbd"]);

registerTemplateProcessor((doc) => {
    try {
        const walker = doc.createTreeWalker(doc, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
        let node = walker.currentNode;
        while (node) {
            if (node.nodeType === Node.TEXT_NODE) {
                const parentTag = (node.parentNode?.nodeName || "").toLowerCase();
                if (!OPAQUE_TAGS.has(parentTag) && node.nodeValue) {
                    const next = debrandText(node.nodeValue);
                    if (next !== node.nodeValue) {
                        node.nodeValue = next;
                    }
                }
            } else if (node.attributes) {
                for (const attr of [...node.attributes]) {
                    if (attr.name.startsWith("t-")) {
                        continue; // QWeb expression
                    }
                    let next;
                    if (PROSE_ATTRS.has(attr.name)) {
                        next = debrandText(attr.value);
                    } else if (URL_ATTRS.has(attr.name)) {
                        next = debrandUrl(attr.value);
                    } else {
                        continue;
                    }
                    if (next !== attr.value) {
                        node.setAttribute(attr.name, next);
                    }
                }
            }
            node = walker.nextNode();
        }
    } catch (error) {
        console.warn("biz_debrand: template debranding skipped", error);
    }
});
