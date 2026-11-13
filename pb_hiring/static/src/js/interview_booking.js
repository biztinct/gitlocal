/** @odoo-module **/
// Show candidate slots in the browser timezone on the first visit.
document.addEventListener("DOMContentLoaded", () => {
    if (!window.location.pathname.startsWith("/hiring/book/")) return;
    const url = new URL(window.location.href);
    const select = document.getElementById("timezone");
    if (!select || url.searchParams.has("tz")) return;
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (zone && zone !== select.value && Array.from(select.options).some(o => o.value === zone)) {
        url.searchParams.set("tz", zone);
        window.location.replace(url.toString());
    }
});
