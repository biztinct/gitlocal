/* Payobook landing page — motion & interactivity.
 * Plain IIFE (NOT an Odoo module) so it can use the vendored globals
 * gsap / ScrollTrigger / Lenis / Chart. Runs only when .pb_landing exists,
 * and degrades gracefully if any library is missing.
 */
(function () {
  "use strict";

  function boot() {
    var root = document.querySelector(".pb_landing");
    if (!root) return; // only on the landing page

    // Bespoke page owns the whole viewport — drop Odoo's website header/footer
    // (CSS :has handles this with no flash; this is the cross-engine fallback).
    document.querySelectorAll(
      "#wrapwrap > header, #wrapwrap > footer, header.o_header_standard, .o_header_affix, #footer, .o_footer, .o_frontend_to_backend_nav, .o_frontend_to_backend_edit_btn"
    ).forEach(function (el) { el.style.display = "none"; });
    var ww = document.getElementById("wrapwrap");
    if (ww) ww.style.paddingTop = "0";
    document.title = "Payobook — Effortless Payroll Solutions";

    var hasGsap = typeof window.gsap !== "undefined";
    var hasST = typeof window.ScrollTrigger !== "undefined";
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (hasGsap && hasST) window.gsap.registerPlugin(window.ScrollTrigger);

    // ---------------------------------------------------------------- Lenis
    var lenis = null;
    if (typeof window.Lenis !== "undefined" && !reduce) {
      try {
        lenis = new window.Lenis({ lerp: 0.1, smoothWheel: true, wheelMultiplier: 1 });
        if (hasGsap && hasST) {
          lenis.on("scroll", window.ScrollTrigger.update);
          window.gsap.ticker.add(function (t) { lenis.raf(t * 1000); });
          window.gsap.ticker.lagSmoothing(0);
        } else {
          var raf = function (time) { lenis.raf(time); requestAnimationFrame(raf); };
          requestAnimationFrame(raf);
        }
      } catch (e) { lenis = null; }
    }

    // smooth anchor jumps
    root.querySelectorAll('a[href^="#"]').forEach(function (a) {
      a.addEventListener("click", function (ev) {
        var id = a.getAttribute("href");
        if (id.length < 2) return;
        var target = document.querySelector(id);
        if (!target) return;
        ev.preventDefault();
        if (lenis) lenis.scrollTo(target, { offset: -70, duration: 1.1 });
        else target.scrollIntoView({ behavior: "smooth" });
      });
    });

    // ------------------------------------------------------------- Nav stuck
    var nav = root.querySelector('[data-pb="nav"]');
    if (nav) {
      var onScroll = function () { nav.classList.toggle("is-stuck", window.scrollY > 30); };
      onScroll();
      window.addEventListener("scroll", onScroll, { passive: true });
    }

    // ---------------------------------------------------- Headline char split
    var headline = root.querySelector('[data-pb="headline"]');
    if (headline && !reduce) {
      var wrapChars = function (node) {
        var out = [];
        Array.prototype.slice.call(node.childNodes).forEach(function (child) {
          if (child.nodeType === 3) { // text — collapse whitespace, drop indentation-only nodes
            var text = child.textContent.replace(/\s+/g, " ").trim();
            if (!text) { node.removeChild(child); return; }
            var frag = document.createDocumentFragment();
            var words = text.split(" ");
            words.forEach(function (word, wi) {
              // wrap each word so inline-block chars never break mid-word
              var wspan = document.createElement("span");
              wspan.className = "pbw-word";
              word.split("").forEach(function (ch) {
                var s = document.createElement("span");
                s.className = "pbw-ch";
                s.textContent = ch;
                wspan.appendChild(s);
                out.push(s);
              });
              frag.appendChild(wspan);
              if (wi < words.length - 1) frag.appendChild(document.createTextNode(" "));
            });
            node.replaceChild(frag, child);
          } else if (child.nodeType === 1) {
            if (child.classList && child.classList.contains("pbw-grad")) {
              // animate the gradient line as ONE unit — per-char spans break background-clip:text
              child.style.opacity = "0";
              child.style.transform = "translateY(0.5em)";
              out.push(child);
            } else {
              out = out.concat(wrapChars(child));
            }
          }
        });
        return out;
      };
      var chars = wrapChars(headline);
      if (hasGsap && chars.length) {
        window.gsap.to(chars, {
          y: 0, opacity: 1, rotate: 0, duration: 0.9, ease: "power3.out",
          stagger: 0.016, delay: 0.15,
        });
      } else {
        chars.forEach(function (c) { c.style.opacity = 1; c.style.transform = "none"; });
      }
    } else if (headline) {
      headline.querySelectorAll(".pbw-ch").forEach(function (c) { c.style.opacity = 1; });
    }

    // ------------------------------------------------------ Reveal on scroll
    var reveals = [].slice.call(root.querySelectorAll('[data-pb="reveal"]'))
      .concat([].slice.call(root.querySelectorAll(".pbw-sec__head")));
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) { en.target.classList.add("is-in"); io.unobserve(en.target); }
        });
      }, { threshold: 0.18, rootMargin: "0px 0px -8% 0px" });
      reveals.forEach(function (el) { io.observe(el); });
    } else {
      reveals.forEach(function (el) { el.classList.add("is-in"); });
    }

    // dashboard bars trigger
    var bars = root.querySelector(".pbw-dash__bars");
    if (bars && "IntersectionObserver" in window) {
      var bio = new IntersectionObserver(function (e) {
        if (e[0].isIntersecting) { bars.classList.add("is-in"); bio.disconnect(); }
      }, { threshold: 0.4 });
      bio.observe(bars);
    } else if (bars) { bars.classList.add("is-in"); }

    // ----------------------------------------------------------- Counters
    var counters = root.querySelectorAll("[data-count]");
    var animateCount = function (el) {
      var target = parseFloat(el.getAttribute("data-count")) || 0;
      var suffix = el.getAttribute("data-suffix") || "";
      var dur = 1300, start = null;
      var step = function (ts) {
        if (!start) start = ts;
        var p = Math.min((ts - start) / dur, 1);
        var eased = 1 - Math.pow(1 - p, 3);
        el.textContent = Math.round(target * eased) + suffix;
        if (p < 1) requestAnimationFrame(step);
        else el.textContent = target + suffix;
      };
      requestAnimationFrame(step);
    };
    if ("IntersectionObserver" in window && !reduce) {
      var cio = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) { animateCount(en.target); cio.unobserve(en.target); }
        });
      }, { threshold: 0.6 });
      counters.forEach(function (el) { cio.observe(el); });
    } else {
      counters.forEach(function (el) {
        el.textContent = (el.getAttribute("data-count") || "") + (el.getAttribute("data-suffix") || "");
      });
    }

    // ----------------------------------------------------- Country tabs swap
    var COUNTRIES = {
      SG: { name: "Singapore", note: "Resident & non-resident tax, multi-tier CPF, and statutory levies — computed automatically each pay run.", chips: ["CPF", "SDL", "FWL", "Income Tax", "Transport & housing allowances"] },
      MY: { name: "Malaysia", note: "EPF, SOCSO, EIS and monthly tax deduction (PCB) handled to the sen, every cycle.", chips: ["EPF", "SOCSO", "EIS", "PCB (Income Tax)", "Allowances"] },
      ID: { name: "Indonesia", note: "PPh 21 income tax with BPJS Kesehatan and Ketenagakerjaan, plus union dues and allowances.", chips: ["PPh 21", "BPJS Kesehatan", "BPJS Ketenagakerjaan", "Union dues", "Tunjangan"] },
      IN: { name: "India", note: "Provident Fund, Professional Tax and TDS — with bank export and analytics built in.", chips: ["Provident Fund", "Professional Tax", "TDS", "HRA", "Bank export"] },
      VN: { name: "Vietnam", note: "Progressive PIT with social, health and unemployment insurance — and one-click government XLS reports.", chips: ["BHXH", "BHYT", "BHTN", "PIT", "Govt XLS reports", "13th month"] },
      TH: { name: "Thailand", note: "Social Security Fund, provident fund and progressive personal income tax across the board.", chips: ["SSF", "Provident Fund", "Income Tax", "Allowances"] },
      KH: { name: "Cambodia", note: "National Social Security Fund with Tax on Salary and fringe-benefit handling.", chips: ["NSSF", "Tax on Salary", "WTS", "Fringe benefits", "Allowances"] },
    };
    var tabs = root.querySelector('[data-pb="country-tabs"]');
    var panel = root.querySelector('[data-pb="country-panel"]');
    if (tabs && panel) {
      tabs.addEventListener("click", function (ev) {
        var btn = ev.target.closest(".pbw-ctab");
        if (!btn) return;
        var code = btn.getAttribute("data-code");
        var data = COUNTRIES[code];
        if (!data) return;
        tabs.querySelectorAll(".pbw-ctab").forEach(function (t) { t.classList.remove("is-active"); });
        btn.classList.add("is-active");
        panel.classList.add("is-swapping");
        setTimeout(function () {
          panel.innerHTML =
            '<div class="pbw-country__flag"><b>' + code + "</b></div>" +
            '<div class="pbw-country__detail"><h3>' + data.name + "</h3>" +
            '<p class="pbw-country__note">' + data.note + "</p>" +
            '<div class="pbw-chips">' + data.chips.map(function (c) {
              return '<span class="pbw-chip">' + c + "</span>";
            }).join("") + "</div></div>";
          panel.classList.remove("is-swapping");
        }, 220);
      });
    }

    // -------------------------------------------------- Pipeline horizontal
    var pipe = root.querySelector('[data-pb="pipe"]');
    var pipeTrack = root.querySelector('[data-pb="pipe-track"]');
    if (pipe && pipeTrack && hasGsap && hasST && window.innerWidth > 880 && !reduce) {
      var amt = function () { return Math.max(0, pipeTrack.scrollWidth - pipe.clientWidth + 32); };
      window.gsap.to(pipeTrack, {
        x: function () { return -amt(); },
        ease: "none",
        scrollTrigger: {
          trigger: pipe,
          start: "center center",
          end: function () { return "+=" + amt(); },
          pin: true, scrub: 1, invalidateOnRefresh: true, anticipatePin: 1,
        },
      });
    } else if (pipe) {
      pipe.classList.add("is-native");
    }

    // hero mockup parallax
    var mockup = root.querySelector('[data-pb="mockup"]');
    if (mockup && hasGsap && hasST && !reduce) {
      window.gsap.to(mockup, {
        yPercent: -12, ease: "none",
        scrollTrigger: { trigger: ".pbw-hero", start: "top top", end: "bottom top", scrub: true },
      });
    }

    // --------------------------------------------------------- PayAI chart
    var chartCanvas = root.querySelector('[data-pb="payai-chart"]');
    if (chartCanvas && typeof window.Chart !== "undefined") {
      var drawChart = function () {
        var ctx = chartCanvas.getContext("2d");
        var g = ctx.createLinearGradient(0, 0, 0, 180);
        g.addColorStop(0, "rgba(169,196,250,0.95)");
        g.addColorStop(1, "rgba(92,97,157,0.55)");
        new window.Chart(ctx, {
          type: "bar",
          data: {
            labels: ["SG", "MY", "ID", "IN", "VN", "TH", "KH"],
            datasets: [{
              data: [38, 17, 14, 12, 9, 6, 4],
              backgroundColor: g, borderRadius: 6, borderSkipped: false, maxBarThickness: 30,
            }],
          },
          options: {
            responsive: true, maintainAspectRatio: false,
            animation: { duration: 1400, easing: "easeOutQuart" },
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
            scales: {
              x: { grid: { display: false }, ticks: { color: "rgba(255,255,255,0.55)", font: { size: 10 } } },
              y: { display: false, beginAtZero: true },
            },
          },
        });
      };
      if ("IntersectionObserver" in window) {
        var chio = new IntersectionObserver(function (e) {
          if (e[0].isIntersecting) { drawChart(); chio.disconnect(); }
        }, { threshold: 0.4 });
        chio.observe(chartCanvas);
      } else { drawChart(); }
    }

    // --------------------------------------------- Aurora / particle canvas
    var canvases = root.querySelectorAll('[data-pb="aurora"]');
    if (!reduce) canvases.forEach(initAurora);

    function initAurora(canvas) {
      var ctx = canvas.getContext("2d");
      if (!ctx) return;
      var W = 0, H = 0, dpr = Math.min(window.devicePixelRatio || 1, 2);
      var orbs = [], dots = [], running = true;
      var PALETTE = ["92,97,157", "169,196,250", "201,207,245", "159,224,212"];

      function size() {
        var r = canvas.getBoundingClientRect();
        W = r.width; H = r.height;
        canvas.width = W * dpr; canvas.height = H * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      }
      function seed() {
        orbs = []; dots = [];
        var nOrbs = 5;
        for (var i = 0; i < nOrbs; i++) {
          orbs.push({
            x: Math.random() * W, y: Math.random() * H,
            r: 140 + Math.random() * 220,
            vx: (Math.random() - 0.5) * 0.18, vy: (Math.random() - 0.5) * 0.18,
            c: PALETTE[i % PALETTE.length],
          });
        }
        var nDots = Math.min(70, Math.round((W * H) / 22000));
        for (var j = 0; j < nDots; j++) {
          dots.push({
            x: Math.random() * W, y: Math.random() * H,
            r: Math.random() * 1.6 + 0.4,
            vy: -(Math.random() * 0.25 + 0.05),
            a: Math.random() * 0.5 + 0.15, tw: Math.random() * Math.PI * 2,
          });
        }
      }
      function frame() {
        if (!running) return;
        ctx.clearRect(0, 0, W, H);
        ctx.globalCompositeOperation = "lighter";
        orbs.forEach(function (o) {
          o.x += o.vx; o.y += o.vy;
          if (o.x < -o.r) o.x = W + o.r; if (o.x > W + o.r) o.x = -o.r;
          if (o.y < -o.r) o.y = H + o.r; if (o.y > H + o.r) o.y = -o.r;
          var grad = ctx.createRadialGradient(o.x, o.y, 0, o.x, o.y, o.r);
          grad.addColorStop(0, "rgba(" + o.c + ",0.22)");
          grad.addColorStop(1, "rgba(" + o.c + ",0)");
          ctx.fillStyle = grad;
          ctx.beginPath(); ctx.arc(o.x, o.y, o.r, 0, Math.PI * 2); ctx.fill();
        });
        dots.forEach(function (d) {
          d.y += d.vy; d.tw += 0.05;
          if (d.y < -4) { d.y = H + 4; d.x = Math.random() * W; }
          var a = d.a * (0.6 + 0.4 * Math.sin(d.tw));
          ctx.fillStyle = "rgba(220,228,255," + a + ")";
          ctx.beginPath(); ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2); ctx.fill();
        });
        ctx.globalCompositeOperation = "source-over";
        requestAnimationFrame(frame);
      }
      size(); seed(); requestAnimationFrame(frame);

      var rt;
      window.addEventListener("resize", function () {
        clearTimeout(rt); rt = setTimeout(function () { size(); seed(); }, 200);
      });
      // pause when off-screen to save CPU
      if ("IntersectionObserver" in window) {
        new IntersectionObserver(function (e) {
          var vis = e[0].isIntersecting;
          if (vis && !running) { running = true; requestAnimationFrame(frame); }
          running = vis;
        }, { threshold: 0 }).observe(canvas);
      }
    }

    if (hasST) setTimeout(function () { window.ScrollTrigger.refresh(); }, 400);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
