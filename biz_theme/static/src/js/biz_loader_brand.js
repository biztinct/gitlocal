/** @odoo-module **/
// Part of biz_theme — reusable Odoo 19 backend theme. License LGPL-3.
//
// Which logo the centre-screen loader animates (biz_loading.scss) is decided
// here, once, before the web client mounts — the loading indicator is itself
// an OWL component, so nothing can show before this module has run.
//
// Sources, in order (all are <meta> tags biz_debrand's web.layout emits):
//   1. biz-loader-logo      an explicit picture for this database → image mode
//   2. biz-brand ≠ biz-brand-product
//                           a white-labelled tenant with no picture → the brand
//                           name animates as text; the master product's mark
//                           is NEVER shown on such a database
//   3. otherwise            nothing is set and the stylesheet default applies
//                           (the product overlay compiles its own logo in)
//
// Inline custom properties on <html> win over every stylesheet rule, which is
// what lets one compiled bundle serve every database correctly.

const meta = (name) => {
    const el = document.querySelector(`meta[name="${name}"]`);
    return (el && el.getAttribute("content") || "").trim();
};

export function applyLoaderBrand(doc = document) {
    const root = doc.documentElement;
    const logo = meta("biz-loader-logo");
    const brand = meta("biz-brand");
    const product = meta("biz-brand-product");
    if (logo) {
        root.style.setProperty("--biz-loader-logo", `url("${logo.replace(/"/g, "%22")}")`);
        root.dataset.bizLoader = "image";
        return "image";
    }
    if (brand && product && brand.toLowerCase() !== product.toLowerCase()) {
        root.style.setProperty("--biz-loader-logo", "none");
        root.style.setProperty("--biz-loader-text", JSON.stringify(brand));
        root.dataset.bizLoader = "text";
        return "text";
    }
    return "default";
}

applyLoaderBrand();
