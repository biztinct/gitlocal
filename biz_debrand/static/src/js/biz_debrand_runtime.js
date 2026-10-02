/** @odoo-module **/
/* Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
 *
 * Client-side half of the white-label layer. Three global seams replace what
 * would otherwise be ~100 brittle per-call-site edits:
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
 *  Seams 1 and 2 rewrite SOURCE text, so they also carry ERRORS E3-2's product
 *  rule (our own product name, on a tenant's screen). Seam 3 does not: it sees
 *  the finished message, record names and all. See models/brand.py.
 *
 *  3. notificationService.add — every toast, message AND title, at the last
 *     moment before it is drawn. Seam 1 rewrites a translation TEMPLATE and
 *     deliberately never its interpolated arguments (so a partner genuinely
 *     called "Odoo Ltd" survives a rename), which means the ~64 legacy call
 *     sites that build `_('Error: %s') % str(e)` put a raw Python failure —
 *     vendor name, module path and all — straight on the screen. Wrapping the
 *     service catches all of them, every future one, and the stock
 *     error_notifications messages besides. See ERRORS E2-3.
 *
 * The rewrite rules mirror biz_debrand/models/brand.py character for
 * character; keep the two in step.
 */
import { TranslatedString } from "@web/core/l10n/translation";
import { registerTemplateProcessor } from "@web/core/templates";
import { notificationService } from "@web/core/notifications/notification_service";
import { patch } from "@web/core/utils/patch";

const DEFAULT_BRAND = "BizApp";
const DEFAULT_WEBSITE = "https://example.com";

/* --- biz_debrand:rules:begin -------------------------------------------------
 * Everything between these two markers is PURE: no imports, no DOM, no module
 * state, nothing but the rewrite rules and the two functions that apply them.
 *
 * models/brand.py mirrors this region rule for rule, and
 * tests/test_rewrite.py slices it out of this file and RUNS it under node
 * against the very same table it runs the Python one against — so the two
 * halves cannot drift apart without a test going red. Keep the region
 * self-contained; anything that needs the page itself belongs below the end
 * marker.
 * -------------------------------------------------------------------------- */

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

// Whole sentences that must be REPLACED, not word-swapped, and therefore run
// before every rule above. They point the reader at a vendor SERVICE the brand
// does not operate, so rewriting the domain would invent a help desk that does
// not answer — worse than leaving the vendor name in. Mirrors PHRASES in
// models/brand.py. See ERRORS E2-4.
const PHRASES = [
    // o_spreadsheet's own crash line, which reaches the screen through the
    // library's setTranslationMethod(_t) bridge and so through seam 1.
    [
        /An unexpected error occurred\.\s*Submit a support ticket at (?:www\.)?odoo\.com\/help\.?/gi,
        "Something went wrong on our side. If it keeps happening, let your administrator know.",
    ],
    [
        /Submit a support ticket at (?:www\.)?odoo\.com\/help\.?/gi,
        "If it keeps happening, let your administrator know.",
    ],
];

// ERRORS E4-6. A URL another layer has already broken: `web_debranding`
// substitutes a FULL URL (`https://payobook.com`) where a bare HOST belongs, so
// `https://www.odoo.com/pricing` comes out as
// `https://www.https://payobook.com/pricing` — a dead link, not a naming bug.
// The rule is "a URL prefix immediately followed by another complete URL": drop
// the dead prefix, keep the real address. A URL that legitimately carries
// another one (`?next=https://…`) is not matched, because the character class
// stops at `/` and `?`. Mirrors NESTED_URL_RE / repair_nested_url in
// models/brand.py.
const NESTED_URL = /\bhttps?:\/\/[\w.\-]*(?=https?:\/\/)/gi;

function bizRepairNestedUrl(text) {
    if (!text || typeof text !== "string" || text.split("://").length < 3) {
        return text;
    }
    return text.replace(NESTED_URL, "");
}

// The product rule — ERRORS E3-2. OUR OWN name, shown to a tenant as if it
// were theirs ("Welcome to Payobook" on a Rize employee's screen). Mirrors
// product_rules() in models/brand.py, including the four shapes that must
// survive: `payobook.com`, `payobook_template`, `/payobook/`, `Payobook-navy`.
//
// Cached on the cfg object because building two RegExps per string would make
// the hot path allocate; cfg is created once per bundle below.
function bizProductRules(cfg) {
    if (cfg.rules === undefined) {
        const product = (cfg.product || "").trim();
        const name = (cfg.name || "").trim();
        if (product.length < 2 || product.toLowerCase() === name.toLowerCase()) {
            cfg.rules = null;
        } else {
            const escaped = product.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
            cfg.rules = {
                has: new RegExp("odoo|" + escaped, "i"),
                word: new RegExp(
                    "(^|[^.\\w/-])" + escaped + "(?![\\w/[-])(?!\\.\\w)(?!\\s*=)",
                    "gi"
                ),
            };
        }
    }
    return cfg.rules;
}

/**
 * The rewrite itself. `cfg` is `{name, host, docUrl, product}` — `product`
 * empty or absent turns E3-2's product rule off, which is what every seam that
 * can see interpolated DATA passes.
 *
 * @param {string} text
 * @param {object} cfg
 * @returns {string}
 */
function bizRewrite(text, cfg) {
    if (!text || typeof text !== "string") {
        return text;
    }
    // E4-6, BEFORE the pre-filter: a mangled link no longer carries the
    // vendor's name, so the pre-filter would return early and leave it broken.
    const repaired = bizRepairNestedUrl(text);
    const rules = cfg.product ? bizProductRules(cfg) : null;
    if (!(rules ? rules.has : HAS_ODOO).test(repaired)) {
        return repaired;
    }
    let out = repaired;
    for (const [pattern, replacement] of PHRASES) {
        out = out.replace(pattern, replacement);
    }
    out = out
        .replace(DOC_URL, cfg.docUrl)
        .replace(DOMAIN, (m, prefix) => prefix + cfg.host)
        .replace(BOT, cfg.name)
        .replace(SA, cfg.name)
        .replace(WORD, (match, prefix) => prefix + cfg.name);
    if (rules) {
        out = out.replace(rules.word, (match, prefix) => prefix + cfg.name);
    }
    return out;
}

/**
 * Repoint vendor URLs at the brand's own site. Only the domain rules apply —
 * never the generic word rule, and never the product rule: `payobook.com` is a
 * host that resolves and rewriting it would invent one that does not. So
 * `/odoo/action-1` and `odoocdn.com` asset URLs keep working while a visitable
 * https://odoo.com link does not.
 *
 * @param {string} url
 * @param {object} cfg
 * @returns {string}
 */
function bizRewriteUrl(url, cfg) {
    // E4-6 first, and outside the pre-filter — see bizRewrite.
    url = bizRepairNestedUrl(url);
    if (!url || typeof url !== "string" || !HAS_ODOO.test(url)) {
        return url;
    }
    return url.replace(DOC_URL, cfg.docUrl).replace(DOMAIN, (m, prefix) => prefix + cfg.host);
}
/* --- biz_debrand:rules:end ------------------------------------------------ */

/**
 * Read the brand injected by biz_debrand's web.layout inherit. Synchronous and
 * available on both backend and frontend pages, unlike web_debranding's
 * post-mount ORM round-trip.
 */
function readBrand() {
    let name = DEFAULT_BRAND;
    let website = DEFAULT_WEBSITE;
    let product = "";
    let poweredBy = "";
    try {
        const nameMeta = document.querySelector('meta[name="biz-brand"]');
        const siteMeta = document.querySelector('meta[name="biz-brand-website"]');
        const productMeta = document.querySelector('meta[name="biz-brand-product"]');
        const poweredMeta = document.querySelector('meta[name="biz-brand-powered-by"]');
        if (poweredMeta && poweredMeta.content) {
            poweredBy = poweredMeta.content;
        }
        if (nameMeta && nameMeta.content) {
            name = nameMeta.content;
        }
        if (siteMeta && siteMeta.content) {
            website = siteMeta.content;
        }
        if (productMeta && productMeta.content) {
            product = productMeta.content;
        }
    } catch {
        // Keep the defaults; branding must never break the page.
    }
    return { name, website, product, poweredBy };
}

const brand = readBrand();
const host = brand.website.replace(/^https?:\/\//, "").replace(/\/+$/, "") || "example.com";
const docUrl = brand.website.replace(/\/+$/, "") + "/documentation/";

// Two configurations, and which one a seam gets is the whole of E3-2's trap 1.
// SOURCE_CFG carries the product rule and is for text that came from a template
// or a _t() msgid. DATA_CFG leaves it off and is for text that may already have
// a record's own name interpolated into it — see seam 3.
const SOURCE_CFG = { name: brand.name, host, docUrl, product: brand.product };
const DATA_CFG = { name: brand.name, host, docUrl, product: "" };

/**
 * @param {string} text source text — a msgid or a static template's prose
 * @returns {string} the text with every user-visible vendor reference replaced
 */
export function debrandText(text) {
    return bizRewrite(text, SOURCE_CFG);
}

/**
 * The same rewrite for text that may carry interpolated record DATA. Identical
 * except that E3-2's product rule is off, so a partner genuinely named
 * "Payobook Vietnam JSC" is not renamed on its way to a toast.
 *
 * @param {string} text
 * @returns {string}
 */
export function debrandDataText(text) {
    return bizRewrite(text, DATA_CFG);
}

/**
 * @param {string} url
 * @returns {string}
 */
export function debrandUrl(url) {
    return bizRewriteUrl(url, SOURCE_CFG);
}

// ---------------------------------------------------------------------------
// ERRORS E4-1 — the "powered by" credit, on the page it belongs on
//
// The middle branding level gives a customer their own name on everything their
// people see AND says who built the platform. That credit is drawn here rather
// than by a view inherit, and the reason is measured: on this build `website`
// REPLACES the whole body of `web.login_layout` (verified on rize, 2026-09-11),
// so an inherit aimed at the stock footer would find no such node and take the
// sign-in page down on every database. A node that is not there cannot be
// xpath'd; a node that is not there simply gets no credit line.
//
// Deliberately narrow: the sign-in page only, one element, appended once, the
// whole thing inside a try/catch. A branding flourish must never be able to
// stop somebody signing in.
// ---------------------------------------------------------------------------
function renderPoweredBy() {
    try {
        if (!brand.poweredBy) {
            return; // every other level, which is almost every customer
        }
        const form =
            document.querySelector(".oe_login_form") ||
            document.querySelector(".oe_website_login_container") ||
            document.querySelector("form.oe_signup_form");
        if (!form || document.querySelector(".biz-powered-by")) {
            return;
        }
        const credit = document.createElement("p");
        credit.className = "biz-powered-by";
        // The one line on the page that must NOT be rewritten: it is a
        // statement about who built the platform, not a name that leaked onto
        // a tenant's screen. Same reasoning as the hatch in the tree walkers
        // (ER24) — and, being built here, after every seam has run, it is out
        // of their reach anyway. The attribute says so to the next reader.
        credit.setAttribute("data-biz-brand", "keep");
        credit.style.cssText =
            "margin:18px 0 0;text-align:center;font-size:12px;opacity:.65";
        credit.textContent = `Powered by ${brand.poweredBy}`;
        (form.closest(".card-body") || form.parentNode || form).appendChild(credit);
    } catch (error) {
        console.warn("biz_debrand: powered-by credit skipped", error);
    }
}

if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", renderPoweredBy, { once: true });
    } else {
        renderPoweredBy();
    }
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

// The author's own opt-out, mirroring KEEP_ATTR in models/brand.py:
// `data-biz-brand="keep"` takes an element and its whole subtree out of the
// walk. FILTER_REJECT (not FILTER_SKIP) is what makes it cover the subtree.
const KEEP_ATTR = "data-biz-brand";
const KEEP_VALUE = "keep";

registerTemplateProcessor((doc) => {
    try {
        const walker = doc.createTreeWalker(
            doc,
            NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT,
            {
                acceptNode(node) {
                    if (
                        node.nodeType === Node.ELEMENT_NODE &&
                        node.getAttribute &&
                        node.getAttribute(KEEP_ATTR) === KEEP_VALUE
                    ) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    return NodeFilter.FILTER_ACCEPT;
                },
            }
        );
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

// ---------------------------------------------------------------------------
// Seam 3 — every notification, on its way to the screen
//
// Seam 1 rewrites the translation template, never the interpolated argument.
// That is deliberate and must stay that way — it is what keeps a record whose
// own name contains the vendor word intact. The cost is that
// `_('Error: %s') % str(e)`, the shape used at ~64 legacy call sites, hands a
// raw Python failure to `display_notification` and the template seam sees
// nothing wrong with it.
//
// Rather than edit those call sites (and the next one somebody writes), the
// notification service itself is wrapped: whatever the message and title are
// by the time they are handed over, they pass the same rules every other seam
// uses. One place, no churn, and it covers core's own error_notifications
// toasts too.
// ---------------------------------------------------------------------------

/**
 * Debrand a value that may not be a plain string.
 *
 * A Markup result is a String SUBCLASS carrying already-escaped HTML. It is
 * left untouched rather than flattened into a primitive — the same guard the
 * valueOf patch above uses, for the same reason.
 *
 * Uses debrandDataText, NOT debrandText: by the time a message reaches the
 * notification service it is finished prose with a record's own name already
 * interpolated into it — which is the whole reason seam 3 exists (E2-3). So
 * this is the one JS seam that must NOT carry E3-2's product rule, or a
 * customer called "Payobook Vietnam JSC" would be renamed in a toast.
 *
 * @param {*} value
 * @returns {*}
 */
function debrandNotificationValue(value) {
    return typeof value === "string" ? debrandDataText(value) : value;
}

/**
 * Rewrite the prose fields of a notification options object.
 *
 * Returns the SAME object when nothing changed, so the common case allocates
 * nothing and a caller that relies on identity is not surprised.
 *
 * @param {object|undefined} options
 * @returns {object|undefined}
 */
function debrandNotificationOptions(options) {
    if (!options || typeof options !== "object") {
        return options;
    }
    const title = debrandNotificationValue(options.title);
    const message = debrandNotificationValue(options.message);
    if (title === options.title && message === options.message) {
        return options;
    }
    const next = Object.assign({}, options);
    next.title = title;
    next.message = message;
    return next;
}

patch(notificationService, {
    start() {
        const service = super.start(...arguments);
        const originalAdd = service.add;
        service.add = function (message, options) {
            let nextMessage = debrandNotificationValue(message);
            // Some callers pass a single options-shaped object instead of
            // (message, options). Reach its prose too rather than assume the
            // first argument is always the text.
            if (
                nextMessage &&
                typeof nextMessage === "object" &&
                !(nextMessage instanceof String)
            ) {
                nextMessage = debrandNotificationOptions(nextMessage);
            }
            return originalAdd.call(
                this,
                nextMessage,
                options === undefined ? options : debrandNotificationOptions(options)
            );
        };
        return service;
    },
});
