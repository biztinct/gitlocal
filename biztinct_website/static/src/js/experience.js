/* Native animation; no third-party runtime, tracking or remote asset requests. */
(() => {
    'use strict';
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
    const finePointer = window.matchMedia('(hover: hover) and (pointer: fine)');
    const progress = document.querySelector('.scroll-progress');
    let scrollTick = false;
    const syncProgress = () => {
        const distance = document.documentElement.scrollHeight - innerHeight;
        if (progress) progress.style.transform = `scaleX(${distance > 0 ? scrollY / distance : 0})`;
        scrollTick = false;
    };
    syncProgress();
    window.addEventListener('scroll', () => {
        if (!scrollTick) { scrollTick = true; requestAnimationFrame(syncProgress); }
    }, { passive: true });
    window.addEventListener('resize', syncProgress, { passive: true });

    if (!reduced.matches && !navigator.connection?.saveData && typeof IntersectionObserver === 'function') {
        document.body.classList.add('motion-ready');
        const revealObserver = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    revealObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.06, rootMargin: '0px 0px -25px 0px' });
        document.querySelectorAll('.intro-grid, .section-heading, .solution-card, .digital-banner, '
            + '.philosophy-art, .philosophy-copy, .process-grid article, .industry-tags, '
            + '.detail-copy, .detail-visual, .approach-step, .principles-grid article, '
            + '.contact-form-wrap, .contact-faq, .cta-inner').forEach(element => {
            element.classList.add('reveal');
            if (element.matches('.solution-card, .process-grid article, .principles-grid article')) {
                const index = [...element.parentElement.children].indexOf(element);
                element.style.setProperty('--reveal-delay', `${Math.min(index, 3) * 90}ms`);
            }
            revealObserver.observe(element);
        });
    }
    reduced.addEventListener('change', event => {
        if (event.matches) document.body.classList.remove('motion-ready');
    });

    const strip = document.querySelector('.capability-strip .shell');
    if (strip && !reduced.matches && !navigator.connection?.saveData) {
        const source = strip.querySelector('div');
        if (source) {
            const track = document.createElement('div');
            track.className = 'marquee-track';
            source.className = 'marquee-run';
            const clone = source.cloneNode(true);
            clone.setAttribute('aria-hidden', 'true');
            source.replaceWith(track);
            track.append(source, clone);
        }
    }

    if (finePointer.matches && !reduced.matches && !navigator.connection?.saveData) {
        document.querySelectorAll('.solution-card').forEach(card => {
            card.addEventListener('pointermove', event => {
                if (reduced.matches || navigator.connection?.saveData) return;
                const box = card.getBoundingClientRect();
                const x = (event.clientX - box.left) / box.width;
                const y = (event.clientY - box.top) / box.height;
                card.style.setProperty('--pointer-x', `${x * 100}%`);
                card.style.setProperty('--pointer-y', `${y * 100}%`);
                card.style.setProperty('--tilt-x', `${(0.5 - y) * 5}deg`);
                card.style.setProperty('--tilt-y', `${(x - 0.5) * 6}deg`);
            }, { passive: true });
            card.addEventListener('pointerleave', () => {
                card.style.setProperty('--tilt-x', '0deg');
                card.style.setProperty('--tilt-y', '0deg');
            });
        });
    }

    // Ambient light and card spotlights update only once per pointer frame.
    const muted = () => reduced.matches || navigator.connection?.saveData || document.hidden;
    const syncPreferences = () => {
        document.body.classList.toggle('effects-muted', Boolean(muted()));
        if (reduced.matches || navigator.connection?.saveData) document.body.classList.remove('motion-ready');
    };
    syncPreferences();
    reduced.addEventListener('change', syncPreferences);
    navigator.connection?.addEventListener('change', syncPreferences);
    document.addEventListener('visibilitychange', syncPreferences);
    const lightTargets = document.querySelectorAll('.hero-stacked, .process-grid article, .principles-grid article');
    lightTargets.forEach(target => {
        let frame = 0, x = 50, y = 30;
        const apply = () => {
            frame = 0;
            if (muted()) return;
            const prefix = target.matches('.hero-stacked') ? 'light' : 'pointer';
            target.style.setProperty(`--${prefix}-x`, `${x}%`);
            target.style.setProperty(`--${prefix}-y`, `${y}%`);
        };
        target.addEventListener('pointermove', event => {
            if (!finePointer.matches || muted()) return;
            const box = target.getBoundingClientRect();
            x = (event.clientX - box.left) / box.width * 100;
            y = (event.clientY - box.top) / box.height * 100;
            if (!frame) frame = requestAnimationFrame(apply);
        }, { passive: true });
        target.addEventListener('pointerleave', () => {
            if (frame) cancelAnimationFrame(frame);
            frame = 0; x = 50; y = 30; apply();
        });
    });

    const effectTargets = document.querySelectorAll('main h1, main h2, .hero-stacked, '
        + '.solution-card, .digital-banner, .process-grid article, .principles-grid article');
    // Keep the original h1/h2 and em elements; wrap text nodes only, preserving whitespace.
    if (!reduced.matches && !navigator.connection?.saveData) {
        document.querySelectorAll('main h1, main h2').forEach(heading => {
            const walker = document.createTreeWalker(heading, NodeFilter.SHOW_TEXT);
            const nodes = [];
            while (walker.nextNode()) nodes.push(walker.currentNode);
            let index = 0;
            nodes.forEach(node => {
                const fragment = document.createDocumentFragment();
                node.textContent.split(/(\s+)/).forEach(word => {
                    if (!word) return;
                    if (/^\s+$/.test(word)) fragment.append(document.createTextNode(word));
                    else {
                        const span = document.createElement('span');
                        span.className = 'effect-word'; span.textContent = word;
                        span.style.setProperty('--word-delay', `${Math.min(index++, 12) * 35}ms`);
                        fragment.append(span);
                    }
                });
                node.replaceWith(fragment);
            });
        });
    }
    if (typeof IntersectionObserver === 'function') {
        const effectsObserver = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                entry.target.classList.toggle('fx-in-view', entry.isIntersecting);
                if (entry.isIntersecting && entry.target.matches('h1, h2')) {
                    entry.target.classList.add('words-revealed');
                }
            });
        }, { threshold: 0.1 });
        effectTargets.forEach(target => effectsObserver.observe(target));
    } else effectTargets.forEach(target => target.classList.add('fx-in-view', 'words-revealed'));
})();
