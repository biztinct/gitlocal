/** @odoo-module **/
import { ic } from "./joining_icons";

function showIcons() {
    for (const element of document.querySelectorAll(".pbjp [data-joining-icon]")) {
        element.innerHTML = ic(element.dataset.joiningIcon, 20);
    }
}
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", showIcons, { once: true });
} else {
    showIcons();
}
