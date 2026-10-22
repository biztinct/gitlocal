/** @odoo-module ignore **/
/* =============================================================================
   LEARNING L7 — the lesson page on a phone (`/my/training/...`).

   A small plain script, PROGRESSIVE ENHANCEMENT ONLY: every page works the
   same without it (every form still posts, every link still goes). It is in
   the frontend bundle, so it does nothing at all on a page that is not a
   training page (no `.pbtr` on it).

   What it adds:
     1. THE PLACE IS KEPT. On a lesson page the scroll position (and a local
        video's time) is saved on the phone every 5 seconds and when the page
        is put away, under `pbtr.lesson.<lesson id>`, and put back when the
        lesson is opened again. A YouTube or Vimeo player keeps its own time;
        only the scroll is kept for those.
     2. "MARK AS DONE" AND A QUIZ GO BY FETCH. The same routes, asking for
        JSON (`X-Requested-With`); the server's answer moves on to the next
        lesson (or marks the questions). When the signal is gone the press is
        SAVED ON THE PHONE (`pbtr.queue`, at most 50, oldest dropped first)
        with a quiet line saying so, and sent when the signal comes back
        (`online`) or on the next training page that opens — oldest first,
        stopping at the first one that cannot get through. A quiz sent late
        is checked then; the answer shows on the page: "Sent while you were
        offline: … · passed".
     3. "SHOW BOTH LANGUAGES" toggles in place and the phone remembers it
        (`pbtr.both`).

   What the queue holds: the lesson's course and lesson ids, the answer ids
   picked, the next lesson id and the time. Nothing about the person.

   NO SERVICE WORKER (owner decision LD7): nothing is cached for offline use
   and nothing here registers one. Every storage read and write is wrapped:
   a phone with storage switched off simply gets the plain page.

   The words it says are written on the page by the server
   (`pb_training.tr_phone_kit`), so they arrive in the reader's language.
   The node suite (`pb_training/tests/js/portal_lesson.test.mjs`) runs the
   queue functions below against a fake fetch.
   ========================================================================== */
(function (root) {
    "use strict";

    var QUEUE_KEY = "pbtr.queue";
    var BOTH_KEY = "pbtr.both";
    var PLACE_PREFIX = "pbtr.lesson.";
    var CAP = 50;
    var PLACE_DAYS = 30;
    var ROUTE_RE = /^\/my\/training\/\d+\/\d+\/(done|quiz)$/;

    // ------------------------------------------------------------ storage
    function store() {
        try { return root.localStorage || null; } catch (e) { return null; }
    }

    function getJSON(key, fallback) {
        try {
            var s = store();
            var raw = s && s.getItem(key);
            return raw ? JSON.parse(raw) : fallback;
        } catch (e) { return fallback; }
    }

    function setJSON(key, value) {
        try {
            var s = store();
            if (!s) { return false; }
            s.setItem(key, JSON.stringify(value));
            return true;
        } catch (e) { return false; }
    }

    // ------------------------------------------------------------ the queue
    function routeOk(route) { return typeof route === "string" && ROUTE_RE.test(route); }

    function readQueue() {
        var q = getJSON(QUEUE_KEY, []);
        return Array.isArray(q) ? q.filter(function (it) { return it && routeOk(it.route); }) : [];
    }

    function writeQueue(q) { return setJSON(QUEUE_KEY, q.slice(-CAP)); }

    /** Save one press on the phone. Returns how many are waiting. */
    function push(item) {
        var q = readQueue();
        item.id = item.id || (String(Date.now()) + "-" + Math.floor(Math.random() * 1e6));
        item.at = item.at || new Date().toISOString();
        q.push(item);
        if (q.length > CAP) { q = q.slice(q.length - CAP); }
        writeQueue(q);
        return q.length;
    }

    function drop(id) {
        writeQueue(readQueue().filter(function (it) { return it.id !== id; }));
    }

    function waitingFor(lessonId) {
        return readQueue().filter(function (it) { return String(it.slide_id) === String(lessonId); });
    }

    /**
     * Send what waits, OLDEST FIRST, and STOP AT THE FIRST ONE THAT CANNOT
     * GET THROUGH (it and everything after it stay on the phone, in order).
     * `send(item)` answers a promise of the server's JSON, or rejects when
     * the press did not reach the server. A server ANSWER — even a refusal —
     * takes the item off the phone: it has been decided.
     */
    function replay(send) {
        var q = readQueue();
        var sent = [];
        function step(i) {
            if (i >= q.length) { return Promise.resolve({ sent: sent, left: 0, stopped: false }); }
            var item = q[i];
            var tried;
            try { tried = Promise.resolve(send(item)); } catch (e) { tried = Promise.reject(e); }
            return tried.then(function (answer) {
                drop(item.id);
                sent.push({ item: item, answer: answer || {} });
                return step(i + 1);
            }, function () {
                return { sent: sent, left: q.length - i, stopped: true };
            });
        }
        return step(0);
    }

    // ------------------------------------------------------------ the wire
    function csrf() {
        try {
            if (root.odoo && root.odoo.csrf_token) { return root.odoo.csrf_token; }
            var el = root.document && root.document.querySelector("input[name='csrf_token']");
            return el ? el.value : "";
        } catch (e) { return ""; }
    }

    /** POST one press the way the form would, asking for JSON. Rejects when
     *  it did not reach the server or the server did not answer JSON (a
     *  sign-in page after a lost session is not an answer: keep it). */
    function sendReal(item) {
        if (!routeOk(item.route)) { return Promise.reject(new Error("route")); }
        var body = new root.FormData();
        body.append("csrf_token", csrf());
        if (item.next_id) { body.append("next_id", String(item.next_id)); }
        (item.answers || []).forEach(function (a) { body.append("q" + a.q, String(a.a)); });
        return root.fetch(item.route, {
            method: "POST", body: body, credentials: "same-origin",
            headers: { "X-Requested-With": "XMLHttpRequest" },
        }).then(function (res) {
            if (!res || !res.ok) { throw new Error("status"); }
            var type = (res.headers && res.headers.get && res.headers.get("Content-Type")) || "";
            if (type.indexOf("json") < 0) { throw new Error("not json"); }
            return res.json();
        });
    }

    var api = {
        QUEUE_KEY: QUEUE_KEY, CAP: CAP, routeOk: routeOk, readQueue: readQueue,
        push: push, drop: drop, replay: replay, waitingFor: waitingFor,
        sendReal: sendReal,
    };
    root.pbtrLesson = api;

    // ================================================================ page
    var doc = root.document;
    if (!doc || !doc.querySelector) { return; }

    function word(key) {
        var el = doc.querySelector(".pbtr-words [data-w='" + key + "']");
        return el ? el.textContent.trim() : "";
    }

    function banner(text, tone, items) {
        var box = doc.querySelector(".pbtr-offline");
        if (!box) { return; }
        var say = box.querySelector(".pbtr-offline-say");
        box.classList.remove("is-wait", "is-ok");
        if (tone) { box.classList.add(tone); }
        if (say) {
            say.textContent = text || "";
            if (items && items.length) {
                var ul = doc.createElement("ul");
                items.forEach(function (it) {
                    var li = doc.createElement("li");
                    if (it.href) {
                        var a = doc.createElement("a");
                        a.href = it.href;
                        a.textContent = it.text;
                        li.appendChild(a);
                    } else {
                        li.textContent = it.text;
                    }
                    ul.appendChild(li);
                });
                say.appendChild(ul);
            }
        }
        box.hidden = !text;
    }

    function lessonHref(item) {
        var m = /^\/my\/training\/(\d+)\/(\d+)\//.exec(item.route || "");
        return m ? "/my/training/" + m[1] + "/" + m[2] : "/my/training";
    }

    function outcomeLine(entry) {
        var ans = entry.answer || {};
        var name = ans.lesson_name || "";
        var what;
        var href = "";
        if (ans.ok === false) {
            what = word("out_refused");
            href = lessonHref(entry.item);
        } else if (entry.item.kind === "quiz") {
            what = ans.passed ? word("out_passed") : word("out_failed");
            if (!ans.passed) { href = lessonHref(entry.item); }
        } else {
            what = word("out_done");
        }
        return { text: (name ? name + " · " : "") + what, href: href };
    }

    var replaying = false;
    function replayNow() {
        if (replaying || !readQueue().length) { return Promise.resolve(null); }
        if (root.navigator && root.navigator.onLine === false) { return Promise.resolve(null); }
        replaying = true;
        banner(word("sending"), "is-wait");
        return replay(sendReal).then(function (res) {
            replaying = false;
            if (res.sent.length) {
                banner(word("sent_head"), res.left ? "is-wait" : "is-ok",
                       res.sent.map(outcomeLine));
            } else if (res.left) {
                banner(word("saved"), "is-wait");
            }
            markSaved();
            showSentHere(res.sent);
            return res;
        }, function () { replaying = false; return null; });
    }

    // ------------------------------------------------------------ the lesson
    var page = doc.querySelector("[data-pbtr-lesson]");
    var lessonId = page ? page.getAttribute("data-pbtr-lesson") : "";
    var placeKey = PLACE_PREFIX + lessonId;

    function currentPlace() {
        var place = { y: Math.round(root.scrollY || root.pageYOffset || 0), at: Date.now() };
        var video = page && page.querySelector("video");
        if (video && !isNaN(video.currentTime)) { place.t = Math.floor(video.currentTime); }
        return place;
    }

    var lastSaved = "";
    function savePlace() {
        if (!page) { return; }
        var place = currentPlace();
        var sig = place.y + ":" + (place.t || 0);
        if (sig === lastSaved) { return; }
        lastSaved = sig;
        setJSON(placeKey, place);
    }

    function restorePlace() {
        if (!page || root.location.hash) { return; }
        var place = getJSON(placeKey, null);
        if (!place || !place.at || (Date.now() - place.at) > PLACE_DAYS * 86400000) { return; }
        var video = page.querySelector("video");
        if (video && place.t) {
            try { video.currentTime = place.t; } catch (e) { /* not ready: the scroll is enough */ }
        }
        if (place.y > 0) {
            // After the layout has settled (images, the frame), or the page
            // would be scrolled to a place that is not there yet.
            root.setTimeout(function () { root.scrollTo(0, place.y); }, 60);
        }
        lastSaved = place.y + ":" + (place.t || 0);
    }

    function markSaved() {
        if (!page) { return; }
        var waiting = waitingFor(lessonId);
        var btn = page.querySelector("form[data-pbtr-form='done'] button[type='submit']");
        if (btn && waiting.length) {
            btn.disabled = true;
            btn.classList.add("pbtr-btn--saved");
            btn.textContent = word("saved_button");
        }
    }

    /** This lesson's own press went through while the page was open: the
     *  saved button becomes the way on (the server's next page). */
    function showSentHere(sent) {
        if (!page) { return; }
        var mine = (sent || []).filter(function (e) {
            return String(e.item.slide_id) === String(lessonId) && e.answer && e.answer.ok
                && e.item.kind === "done";
        });
        var form = page.querySelector("form[data-pbtr-form='done']");
        if (!mine.length || !form) { return; }
        var link = doc.createElement("a");
        link.className = "pbme-btn pbtr-btn--primary pbtr-btn--big";
        link.href = mine[mine.length - 1].answer.next_url || ("/my/training/" + page.getAttribute("data-pbtr-channel"));
        link.textContent = word("next_lesson");
        form.parentNode.replaceChild(link, form);
    }

    function bodyItem(form, kind) {
        var m = /\/my\/training\/(\d+)\/(\d+)\/(done|quiz)$/.exec(form.getAttribute("action") || "");
        if (!m) { return null; }
        var next = form.querySelector("input[name='next_id']");
        var item = {
            route: "/my/training/" + m[1] + "/" + m[2] + "/" + m[3], kind: kind,
            channel_id: Number(m[1]), slide_id: Number(m[2]),
            next_id: next ? Number(next.value) || 0 : 0, answers: [],
        };
        if (kind === "quiz") {
            Array.prototype.forEach.call(form.querySelectorAll("input[type='radio']:checked"), function (inp) {
                var q = /^q(\d+)$/.exec(inp.name || "");
                if (q) { item.answers.push({ q: Number(q[1]), a: Number(inp.value) || 0 }); }
            });
        }
        return item;
    }

    function showMarks(form, result) {
        var say = form.parentNode.querySelector(".pbtr-quiz-say");
        if (!say) {
            say = doc.createElement("div");
            say.className = "pbtr-quiz-say";
            form.parentNode.insertBefore(say, form);
        }
        say.className = "pbtr-quiz-say " + (result.passed ? "pbtr-quiz-say--ok" : "pbtr-quiz-say--bad");
        say.textContent = result.message || "";
        Array.prototype.forEach.call(form.querySelectorAll("[data-q]"), function (box) {
            var q = Number(box.getAttribute("data-q"));
            box.classList.toggle("pbtr-q--wrong", (result.wrong || []).indexOf(q) >= 0);
            box.classList.toggle("pbtr-q--right", (result.right || []).indexOf(q) >= 0);
        });
        say.scrollIntoView({ block: "center", behavior: "smooth" });
    }

    function intercept(form, kind) {
        form.addEventListener("submit", function (ev) {
            var item = bodyItem(form, kind);
            if (!item || !root.fetch || !root.FormData) { return; }   // plain post
            ev.preventDefault();
            var btn = form.querySelector("button[type='submit']");
            var label = btn ? btn.innerHTML : "";
            if (btn) { btn.disabled = true; }
            savePlace();
            var offline = root.navigator && root.navigator.onLine === false;
            var sent = offline ? Promise.reject(new Error("offline")) : sendReal(item);
            sent.then(function (ans) {
                if (ans && ans.ok && ans.next_url) {
                    root.location.assign(ans.next_url);
                    return;
                }
                if (btn) { btn.disabled = false; btn.innerHTML = label; }
                if (ans && ans.ok && kind === "quiz") {
                    showMarks(form, ans.result || {});
                } else {
                    banner((ans && ans.message) || word("out_refused"), "is-wait");
                }
            }, function () {
                push(item);
                if (kind === "quiz") {
                    if (btn) { btn.disabled = false; btn.innerHTML = label; }
                    banner(word("quiz_saved"), "is-wait");
                } else {
                    banner(word("saved"), "is-wait");
                    markSaved();
                }
            });
        });
    }

    function bothLanguages() {
        if (!page) { return; }
        var toggles = page.querySelectorAll("[data-pbtr-both]");
        if (!toggles.length) { return; }
        if (page.classList.contains("is-both")) { setJSON(BOTH_KEY, 1); }
        else if (getJSON(BOTH_KEY, 0) === 1) { page.classList.add("is-both"); }
        Array.prototype.forEach.call(toggles, function (a) {
            a.addEventListener("click", function (ev) {
                ev.preventDefault();
                var on = !page.classList.contains("is-both");
                page.classList.toggle("is-both", on);
                setJSON(BOTH_KEY, on ? 1 : 0);
            });
        });
    }

    function boot() {
        if (!doc.querySelector(".pbtr")) { return; }
        if (page) {
            restorePlace();
            bothLanguages();
            var done = page.querySelector("form[data-pbtr-form='done']");
            if (done) { intercept(done, "done"); }
            var quiz = page.querySelector("form[data-pbtr-form='quiz']");
            if (quiz) { intercept(quiz, "quiz"); }
            markSaved();
            root.setInterval(savePlace, 5000);
            doc.addEventListener("visibilitychange", function () {
                if (doc.visibilityState === "hidden") { savePlace(); }
            });
            root.addEventListener("pagehide", savePlace);
            root.addEventListener("offline", function () { banner(word("offline"), "is-wait"); });
        }
        root.addEventListener("online", function () {
            if (!readQueue().length) { banner("", ""); }
            replayNow();
        });
        if (readQueue().length) {
            if (root.navigator && root.navigator.onLine === false) { banner(word("saved"), "is-wait"); }
            else { replayNow(); }
        }
    }

    if (doc.readyState === "loading") { doc.addEventListener("DOMContentLoaded", boot); }
    else { boot(); }
})(typeof window !== "undefined" ? window : this);
