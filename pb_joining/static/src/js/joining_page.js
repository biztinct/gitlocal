/** @odoo-module ignore **/
(() => {
    "use strict";
    async function resizePhoto(file) {
        if (!/^image\/(jpeg|png)$/.test(file.type) || !window.createImageBitmap) return file;
        const image = await createImageBitmap(file);
        try {
            const ratio = Math.min(1, 2000/Math.max(image.width, image.height));
            if (ratio === 1) return file;
            const canvas = document.createElement("canvas");
            canvas.width = Math.round(image.width * ratio);
            canvas.height = Math.round(image.height * ratio);
            canvas.getContext("2d").drawImage(image, 0, 0, canvas.width, canvas.height);
            return await new Promise(resolve => canvas.toBlob(resolve, file.type, .9)) || file;
        } finally {
            image.close();
        }
    }
    function enhance() {
        const root = document.querySelector(".pbjp");
        if (!root) return;
        const original = root.querySelector("#pbjp-code-input");
        if (original) {
            const digits = document.createElement("div");
            digits.className = "pbjp-digits";
            const boxes = Array.from({length: 6}, (_, i) => {
                const box = document.createElement("input");
                box.type = "text";
                box.inputMode = "numeric";
                box.autocomplete = i === 0 ? "one-time-code" : "off";
                box.setAttribute("aria-label", original.labels[0].textContent + " " + (i+1));
                digits.append(box);
                return box;
            });
            function assign(start, text) {
                const chars = text.replace(/\D/g, "").slice(0, 6-start);
                boxes[start].value = "";
                Array.from(chars).forEach((digit, i) => boxes[start+i].value = digit);
                original.value = boxes.map(b => b.value).join("");
                if (original.value.length === 6) original.form.requestSubmit();
                else boxes[Math.min(5, start+chars.length)].focus();
            }
            boxes.forEach((box, i) => {
                box.addEventListener("input", () => assign(i, box.value));
                box.addEventListener("paste", e => { e.preventDefault(); assign(i, e.clipboardData.getData("text")); });
                box.addEventListener("keydown", e => {
                    if (e.key === "Backspace" && !box.value && i) boxes[i-1].focus();
                });
            });
            original.after(digits);
            original.type = "hidden";
        }
        root.querySelectorAll('.pbjp-secret input[name="clear"]').forEach(change => {
            const input = change.closest("label").querySelector("input:not([type=checkbox])");
            if (!input) return;
            input.hidden = true;
            change.addEventListener("change", () => {
                input.hidden = !change.checked;
                if (change.checked) input.focus();
                else input.value = "";
            });
        });
        const country = root.querySelector('select[name="bank_format"]');
        if (country) {
            const refresh = country.form.querySelector('[name="format_only"]');
            refresh.hidden = true;
            country.addEventListener("change", () => country.form.requestSubmit(refresh));
        }
        const resend = root.querySelector("[data-countdown]");
        if (resend) {
            const label = resend.textContent;
            let remaining = Number(resend.dataset.countdown);
            function update() {
                resend.disabled = remaining > 0;
                resend.textContent = remaining ? resend.dataset.wait.replace("{time}", Math.floor(remaining/60) + ":" + String(remaining%60).padStart(2,"0")) : label;
                if (remaining-- > 0) setTimeout(update, 1000);
            }
            update();
        }
        root.querySelectorAll(".pbjp-upload").forEach(tile => {
            const form = tile.closest("form");
            const status = tile.querySelector('[role="status"]');
            const progress = tile.querySelector("progress");
            const replacement = tile.querySelector("select");
            const controls = form.querySelectorAll('.pbjp-foot button');
            tile.querySelectorAll('input[type="file"]').forEach(input => {
                input.addEventListener("change", async () => {
                    const file = input.files[0];
                    if (!file) return;
                    const selected = replacement.value;
                    form.dataset.uploads = Number(form.dataset.uploads || 0) + 1;
                    controls.forEach(button => button.disabled = true);
                    progress.hidden = false;
                    progress.value = 0;
                    try {
                        const blob = await resizePhoto(file);
                        const data = new FormData();
                        data.append("file", blob, file.name);
                        data.append("key", tile.dataset.key);
                        data.append("replace", selected || "0");
                        data.append("json", "1");
                        data.append("csrf_token", form.elements.csrf_token.value);
                        const saved = await new Promise((resolve, reject) => {
                            const xhr = new XMLHttpRequest();
                            xhr.open("POST", tile.dataset.url);
                            xhr.responseType = "json";
                            xhr.upload.onprogress = e => {
                                if (e.lengthComputable) progress.value = 100*e.loaded/e.total;
                            };
                            xhr.onload = () => xhr.status === 200 && xhr.response?.saved ? resolve(xhr.response) : reject();
                            xhr.onerror = reject;
                            xhr.send(data);
                        });
                        if (selected !== "0") {
                            Array.from(replacement.options).find(o => o.value === selected)?.remove();
                        }
                        replacement.add(new Option(saved.name, saved.id));
                        replacement.closest("label").hidden = false;
                        replacement.value = "0";
                        status.textContent = saved.name + " · " + Math.ceil(saved.size/1024) + " KB";
                        input.value = "";
                    } catch {
                        status.textContent = tile.dataset.error;
                    } finally {
                        progress.hidden = true;
                        form.dataset.uploads = Number(form.dataset.uploads) - 1;
                        controls.forEach(button => button.disabled = Number(form.dataset.uploads) > 0);
                    }
                });
            });
        });
    }
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", enhance);
    else enhance();
})();
