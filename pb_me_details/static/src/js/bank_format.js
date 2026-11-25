/**
 * NEWHIRE P7 — My Payobook › bank account: the country's codes take their
 * shape while typing (an IFSC in capitals, a BSB with its dash, digits only),
 * and picking "Bank account in" shows that country's boxes at once. The page
 * works the same without this file (the Change button, and the server stores
 * every code in its shape); this only saves a click and a retype.
 */
(function () {
    "use strict";
    function shape(kind, raw) {
        var text = String(raw || "");
        if (kind === "ifsc" || kind === "swift") {
            return text.replace(/[\s.\-/]/g, "").toUpperCase();
        }
        if (kind === "bsb") {
            var digits = text.replace(/\D/g, "").slice(0, 6);
            return digits.length > 3 ? digits.slice(0, 3) + "-" + digits.slice(3) : digits;
        }
        if (kind === "digits") {
            return text.replace(/\D/g, "");
        }
        return text;
    }
    document.addEventListener("input", function (ev) {
        var el = ev.target;
        if (!el || !el.getAttribute || !el.getAttribute("data-pbmd-code")) {
            return;
        }
        var shaped = shape(el.getAttribute("data-pbmd-code"), el.value);
        if (shaped !== el.value) {
            el.value = shaped;
        }
    });
    document.addEventListener("change", function (ev) {
        var el = ev.target;
        var form = el && el.form;
        if (form && form.getAttribute("data-pbmd-autosubmit") && el.name === "pb_bank_format") {
            form.submit();
        }
    });
    document.addEventListener("DOMContentLoaded", function () {
        var buttons = document.querySelectorAll("[data-pbmd-autosubmit] .pbmd-bank-country-go");
        for (var i = 0; i < buttons.length; i++) {
            buttons[i].hidden = true;
        }
    });
})();
