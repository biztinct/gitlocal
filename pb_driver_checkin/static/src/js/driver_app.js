/* Payobook Driver PWA — standalone phone app.
 * Plain JS (IIFE): the assets_pwa bundle has NO Odoo module loader / webclient,
 * only Leaflet (global `L`) + this file. Auth is the Odoo session (page is
 * auth='user'); unauthenticated hits get Odoo's login redirect on their own. */
(function () {
    "use strict";

    // ---------------------------------------------------------------- i18n
    var LANG = (document.documentElement.lang || "en").slice(0, 2).toLowerCase();
    var STRINGS = {
        en: {
            off_duty: "Off duty", on_duty: "On duty", check_in: "Check in",
            check_out: "Check out", getting_gps: "Getting GPS…",
            gps_failed: "Couldn't get your location", retry: "Retry",
            add_photo: "Add photo evidence", optional: "optional", skip: "Skip",
            take_photo: "Take photo", today_hours: "Today", pings_sent: "Pings",
            accuracy: "Accuracy", last_sent: "Last sent", ago: "ago",
            just_now: "just now", offline_queued: "Offline — pings queued",
            checking_in: "Checking in…", checking_out: "Checking out…",
            your_location: "Your location", sending: "Sending…", photo_added: "Photo added",
        },
        vi: {
            off_duty: "Chưa làm việc", on_duty: "Đang làm việc", check_in: "Vào ca",
            check_out: "Ra ca", getting_gps: "Đang lấy GPS…",
            gps_failed: "Không lấy được vị trí", retry: "Thử lại",
            add_photo: "Thêm ảnh xác thực", optional: "tùy chọn", skip: "Bỏ qua",
            take_photo: "Chụp ảnh", today_hours: "Hôm nay", pings_sent: "Vị trí",
            accuracy: "Độ chính xác", last_sent: "Gửi lần cuối", ago: "trước",
            just_now: "vừa xong", offline_queued: "Ngoại tuyến — đã xếp hàng",
            checking_in: "Đang vào ca…", checking_out: "Đang ra ca…",
            your_location: "Vị trí của bạn", sending: "Đang gửi…", photo_added: "Đã thêm ảnh",
        },
    };
    var T = STRINGS[LANG] || STRINGS.en;
    function _t(k) { return T[k] || STRINGS.en[k] || k; }

    // ---------------------------------------------------------------- rpc
    function rpc(url, params) {
        return fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: params || {}, id: Date.now() }),
        }).then(function (r) { return r.json(); }).then(function (j) {
            if (j.error) { throw new Error((j.error.data && j.error.data.message) || j.error.message || "RPC error"); }
            return j.result;
        });
    }

    // ---------------------------------------------------------------- state
    var S = {
        state: null,          // /driver/state payload
        map: null, marker: null, accuracyCircle: null,
        lastFix: null,        // freshest geolocation fix {lat, lon, acc, speed, heading}
        watchId: null, pingTimer: null, wakeLock: null,
        pingsSent: 0, lastPingAt: null, offline: false,
        battery: null,
    };
    var QKEY = "pbdrv_ping_queue";
    var QCAP = 200;

    // ---------------------------------------------------------------- helpers
    function el(tag, cls, html) {
        var e = document.createElement(tag);
        if (cls) { e.className = cls; }
        if (html !== undefined) { e.innerHTML = html; }
        return e;
    }
    function fmtDuration(sec) {
        if (sec == null) { return "—"; }
        sec = Math.max(0, Math.floor(sec));
        var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60);
        if (h) { return h + "h " + m + "m"; }
        if (m) { return m + "m"; }
        return sec + "s";
    }
    function sinceSeconds(iso) {
        if (!iso) { return null; }
        var t = new Date(iso.replace(" ", "T") + "Z").getTime();
        return (Date.now() - t) / 1000;
    }
    var TRUCK = '<svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 17h4V5H2v12h3"/><path d="M20 17h2v-3.34a4 4 0 0 0-1.17-2.83L19 9h-5v8h1"/><circle cx="7.5" cy="17.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/></svg>';

    // ---------------------------------------------------------------- battery
    if (navigator.getBattery) {
        navigator.getBattery().then(function (b) {
            S.battery = b;
        }).catch(function () {});
    }
    function batteryPct() {
        return S.battery ? Math.round(S.battery.level * 100) : null;
    }

    // ---------------------------------------------------------------- geolocation
    function getOnce() {
        return new Promise(function (resolve, reject) {
            if (!navigator.geolocation) { reject(new Error("no_geo")); return; }
            navigator.geolocation.getCurrentPosition(function (pos) {
                resolve(fix(pos));
            }, function (err) { reject(err); },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 });
        });
    }
    function fix(pos) {
        var c = pos.coords;
        return {
            lat: c.latitude, lon: c.longitude, acc: c.accuracy,
            speed: c.speed || 0, heading: c.heading || 0,
        };
    }

    // ---------------------------------------------------------------- wake lock
    function acquireWake() {
        if (!("wakeLock" in navigator)) { return; }
        navigator.wakeLock.request("screen").then(function (wl) {
            S.wakeLock = wl;
        }).catch(function () {});
    }
    function releaseWake() {
        if (S.wakeLock) { try { S.wakeLock.release(); } catch (e) {} S.wakeLock = null; }
    }
    document.addEventListener("visibilitychange", function () {
        if (document.visibilityState === "visible" && S.state && S.state.checked_in) {
            acquireWake();
        }
    });

    // ---------------------------------------------------------------- offline queue
    function loadQueue() {
        try { return JSON.parse(localStorage.getItem(QKEY) || "[]"); } catch (e) { return []; }
    }
    function saveQueue(q) {
        try { localStorage.setItem(QKEY, JSON.stringify(q.slice(-QCAP))); } catch (e) {}
    }
    function enqueue(p) {
        var q = loadQueue(); q.push(p); saveQueue(q);
        S.offline = true; renderStatusLine();
    }
    function flushQueue() {
        var q = loadQueue();
        if (!q.length) { S.offline = false; renderStatusLine(); return Promise.resolve(); }
        var next = q[0];
        return rpc("/driver/ping", next).then(function (res) {
            if (res && res.error === "not_checked_in") { saveQueue([]); return; }
            q.shift(); saveQueue(q);
            if (q.length) { return flushQueue(); }
            S.offline = false; renderStatusLine();
        }).catch(function () { /* still offline, keep queue */ });
    }
    window.addEventListener("online", flushQueue);

    // ---------------------------------------------------------------- ping loop
    function sendPing() {
        var f = S.lastFix;
        if (!f) { return; }
        var payload = {
            latitude: f.lat, longitude: f.lon, accuracy: f.acc,
            speed: f.speed, heading: f.heading, battery: batteryPct(),
        };
        rpc("/driver/ping", payload).then(function (res) {
            if (res && res.error) {
                if (res.error === "not_checked_in") { stopTracking(); refresh(); }
                return;
            }
            S.pingsSent += 1; S.lastPingAt = Date.now();
            S.offline = false;
            renderStatusLine(); renderFooter();
            flushQueue();
        }).catch(function () { enqueue(payload); });
    }
    function startTracking() {
        stopTracking();
        if (navigator.geolocation) {
            S.watchId = navigator.geolocation.watchPosition(function (pos) {
                S.lastFix = fix(pos);
                if (S.map && S.marker) {
                    S.marker.setLatLng([S.lastFix.lat, S.lastFix.lon]);
                    if (S.accuracyCircle) { S.accuracyCircle.setLatLng([S.lastFix.lat, S.lastFix.lon]).setRadius(S.lastFix.acc || 0); }
                    S.map.setView([S.lastFix.lat, S.lastFix.lon]);
                }
            }, function () {}, { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 });
        }
        // Battery courtesy: post at 15 s, not on every watch fire (safety rail 8).
        S.pingTimer = setInterval(sendPing, 15000);
        acquireWake();
    }
    function stopTracking() {
        if (S.watchId != null && navigator.geolocation) { navigator.geolocation.clearWatch(S.watchId); S.watchId = null; }
        if (S.pingTimer) { clearInterval(S.pingTimer); S.pingTimer = null; }
        releaseWake();
    }

    // ---------------------------------------------------------------- map
    function ensureMap(lat, lon) {
        if (!window.L) { return; }
        var host = document.getElementById("pbdrv-map");
        if (!host) { return; }
        if (!S.map) {
            S.map = L.map(host, { zoomControl: false, attributionControl: false })
                .setView([lat, lon], 15);
            L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19 }).addTo(S.map);
            var icon = L.divIcon({ className: "pbdrv-selfpin", html: '<span></span>', iconSize: [22, 22], iconAnchor: [11, 11] });
            S.marker = L.marker([lat, lon], { icon: icon }).addTo(S.map);
            S.accuracyCircle = L.circle([lat, lon], { radius: 0, color: "#2e7dea", weight: 1, fillOpacity: 0.08 }).addTo(S.map);
            setTimeout(function () { S.map.invalidateSize(); }, 120);
        } else {
            S.marker.setLatLng([lat, lon]);
            S.map.setView([lat, lon]);
        }
    }

    // ---------------------------------------------------------------- render
    function renderStatusLine() {
        var e = document.getElementById("pbdrv-heartbeat");
        if (!e) { return; }
        if (S.offline) {
            e.className = "pbdrv-heartbeat is-offline";
            e.innerHTML = '<span class="pbdrv-dot"></span>' + _t("offline_queued");
            return;
        }
        if (!S.state || !S.state.checked_in) { e.innerHTML = ""; e.className = "pbdrv-heartbeat"; return; }
        var ago = S.lastPingAt ? Math.round((Date.now() - S.lastPingAt) / 1000) : null;
        var txt = ago == null ? _t("sending") : (_t("last_sent") + " " + (ago < 2 ? _t("just_now") : ago + "s " + _t("ago")));
        e.className = "pbdrv-heartbeat is-live";
        e.innerHTML = '<span class="pbdrv-dot"></span>' + txt;
    }
    function renderFooter() {
        var f = document.getElementById("pbdrv-footer");
        if (!f) { return; }
        var acc = S.lastFix ? Math.round(S.lastFix.acc) + " m" : "—";
        f.innerHTML =
            statCell(_t("today_hours"), fmtDuration((S.state && S.state.today_hours ? S.state.today_hours * 3600 : 0))) +
            statCell(_t("pings_sent"), String(S.pingsSent)) +
            statCell(_t("accuracy"), acc);
    }
    function statCell(label, val) {
        return '<div class="pbdrv-stat"><div class="pbdrv-stat__v">' + val +
            '</div><div class="pbdrv-stat__l">' + label + '</div></div>';
    }

    function render() {
        var root = document.getElementById("pbdrv-root");
        if (!root) { return; }
        root.innerHTML = "";
        var st = S.state || {};
        var on = !!st.checked_in;

        // header
        var header = el("div", "pbdrv-header");
        var av = el("div", "pbdrv-avatar");
        if (st.avatar_url) { av.style.backgroundImage = 'url(' + st.avatar_url + ')'; }
        header.appendChild(av);
        var hi = el("div", "pbdrv-hi");
        hi.appendChild(el("div", "pbdrv-name", st.employee || root.dataset.userName || "Driver"));
        var chip = el("div", "pbdrv-chip " + (on ? "is-on" : "is-off"));
        var sinceTxt = on && st.checked_in_since ? " · " + fmtDuration(sinceSeconds(st.checked_in_since)) : "";
        chip.innerHTML = '<span class="pbdrv-cdot"></span>' + (on ? _t("on_duty") + sinceTxt : _t("off_duty"));
        hi.appendChild(chip);
        header.appendChild(hi);
        root.appendChild(header);

        // check-in button
        var btnWrap = el("div", "pbdrv-btnwrap");
        var btn = el("button", "pbdrv-cta " + (on ? "is-on" : "is-off"));
        btn.innerHTML = '<span class="pbdrv-cta__glyph">' + TRUCK + '</span>' +
            '<span class="pbdrv-cta__label">' + (on ? _t("check_out") : _t("check_in")) + '</span>';
        btn.addEventListener("click", on ? doCheckOut : doCheckIn);
        btnWrap.appendChild(btn);
        root.appendChild(btnWrap);

        // heartbeat status line
        var hb = el("div", "pbdrv-heartbeat"); hb.id = "pbdrv-heartbeat";
        root.appendChild(hb);

        // map card
        var mapCard = el("div", "pbdrv-mapcard");
        var mapEl = el("div", ""); mapEl.id = "pbdrv-map";
        mapCard.appendChild(mapEl);
        root.appendChild(mapCard);

        // footer stats
        var footer = el("div", "pbdrv-footer"); footer.id = "pbdrv-footer";
        root.appendChild(footer);

        renderStatusLine(); renderFooter();

        if (S.lastFix) { ensureMap(S.lastFix.lat, S.lastFix.lon); }
        else { getOnce().then(function (f) { S.lastFix = f; ensureMap(f.lat, f.lon); renderFooter(); }).catch(function () {}); }
    }

    // ---------------------------------------------------------------- actions
    function toast(msg) {
        var t = el("div", "pbdrv-toast", msg);
        document.body.appendChild(t);
        setTimeout(function () { t.classList.add("show"); }, 10);
        setTimeout(function () { t.classList.remove("show"); setTimeout(function () { t.remove(); }, 300); }, 2200);
    }

    function doCheckIn() {
        var sheet = openSheet(_t("getting_gps"), '<div class="pbdrv-spin"></div>');
        getOnce().then(function (f) {
            S.lastFix = f;
            return rpc("/driver/check_in_out", { latitude: f.lat, longitude: f.lon, accuracy: f.acc });
        }).then(function (st) {
            S.state = st; S.pingsSent = 0; S.lastPingAt = null;
            closeSheet(sheet);
            render();
            startTracking();
            offerSelfie();
        }).catch(function (err) {
            sheet.querySelector(".pbdrv-sheet__title").textContent = _t("gps_failed");
            sheet.querySelector(".pbdrv-sheet__body").innerHTML =
                '<button class="pbdrv-btn pbdrv-btn--primary" id="pbdrv-retry">' + _t("retry") + '</button>';
            sheet.querySelector("#pbdrv-retry").addEventListener("click", function () { closeSheet(sheet); doCheckIn(); });
        });
    }

    function doCheckOut() {
        var sheet = openSheet(_t("checking_out"), '<div class="pbdrv-spin"></div>');
        var f = S.lastFix;
        var go = f ? Promise.resolve(f) : getOnce().catch(function () { return { lat: null, lon: null, acc: null }; });
        go.then(function (fix) {
            return rpc("/driver/check_in_out", { latitude: fix.lat, longitude: fix.lon, accuracy: fix.acc });
        }).then(function (st) {
            S.state = st;
            stopTracking();
            closeSheet(sheet);
            render();
        }).catch(function () { closeSheet(sheet); refresh(); });
    }

    // ---------------------------------------------------------------- selfie
    function offerSelfie() {
        var sheet = openSheet(_t("add_photo") + " · " + _t("optional"),
            '<label class="pbdrv-btn pbdrv-btn--primary">' + _t("take_photo") +
            '<input id="pbdrv-file" type="file" accept="image/*" capture="user" hidden="hidden"/></label>' +
            '<button class="pbdrv-btn pbdrv-btn--ghost" id="pbdrv-skip">' + _t("skip") + '</button>');
        sheet.querySelector("#pbdrv-skip").addEventListener("click", function () { closeSheet(sheet); });
        sheet.querySelector("#pbdrv-file").addEventListener("change", function (ev) {
            var file = ev.target.files && ev.target.files[0];
            if (!file) { return; }
            sheet.querySelector(".pbdrv-sheet__body").innerHTML = '<div class="pbdrv-spin"></div>';
            sheet.querySelector(".pbdrv-sheet__title").textContent = _t("sending");
            var reader = new FileReader();
            reader.onload = function () {
                var b64 = String(reader.result).split(",")[1];
                rpc("/driver/selfie", { image_b64: b64, mimetype: file.type }).then(function (res) {
                    closeSheet(sheet);
                    if (res && res.ok) { toast(_t("photo_added")); refresh(); }
                }).catch(function () { closeSheet(sheet); });
            };
            reader.readAsDataURL(file);
        });
    }

    // ---------------------------------------------------------------- sheet
    function openSheet(title, bodyHtml) {
        var scrim = el("div", "pbdrv-scrim");
        var sheet = el("div", "pbdrv-sheet",
            '<div class="pbdrv-sheet__title">' + title + '</div><div class="pbdrv-sheet__body">' + bodyHtml + '</div>');
        scrim.appendChild(sheet);
        document.body.appendChild(scrim);
        setTimeout(function () { scrim.classList.add("show"); }, 10);
        return scrim;
    }
    function closeSheet(scrim) {
        if (!scrim) { return; }
        scrim.classList.remove("show");
        setTimeout(function () { scrim.remove(); }, 260);
    }

    // ---------------------------------------------------------------- boot
    function refresh() {
        return rpc("/driver/state", {}).then(function (st) {
            S.state = st;
            if (st.checked_in && !S.pingTimer) { startTracking(); }
            render();
        });
    }
    function boot() {
        refresh().catch(function (e) {
            var root = document.getElementById("pbdrv-root");
            if (root) { root.innerHTML = '<div class="pbdrv-gate"><div class="pbdrv-gate__card"><h1>Unavailable</h1><p>' + (e.message || "") + '</p></div></div>'; }
        });
        // heartbeat refresh so "last sent Ns ago" ticks
        setInterval(renderStatusLine, 3000);
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else { boot(); }
})();
