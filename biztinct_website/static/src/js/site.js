/* Progressive enhancement: all links, forms and FAQ work without JavaScript. */
(() => {
    'use strict';
    const header = document.querySelector('.site-header');
    const toggle = document.querySelector('.menu-toggle');
    const nav = document.querySelector('#site-nav');
    const syncHeader = () => header?.classList.toggle('scrolled', window.scrollY > 12);
    syncHeader();
    window.addEventListener('scroll', syncHeader, { passive: true });
    function closeMenu() {
        nav?.classList.remove('open');
        toggle?.setAttribute('aria-expanded', 'false');
        toggle?.setAttribute('aria-label', 'Open menu');
    }
    toggle?.addEventListener('click', () => {
        const open = toggle.getAttribute('aria-expanded') !== 'true';
        nav.classList.toggle('open', open);
        toggle.setAttribute('aria-expanded', String(open));
        toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    });
    nav?.addEventListener('click', event => {
        if (event.target.closest('a')) closeMenu();
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && toggle?.getAttribute('aria-expanded') === 'true') {
            closeMenu();
            toggle.focus();
        }
    });
    const form = document.querySelector('.contact-form');
    const submit = form?.querySelector('button[type="submit"]');
    form?.addEventListener('submit', () => {
        submit.disabled = true;
        submit.textContent = 'Saving your enquiry…';
    });
    window.addEventListener('pageshow', () => {
        if (submit) {
            submit.disabled = false;
            submit.replaceChildren(document.createTextNode('Send your enquiry '));
            const arrow = document.createElement('span');
            arrow.setAttribute('aria-hidden', 'true');
            arrow.textContent = '↗';
            submit.append(arrow);
        }
    });
    document.querySelector('.form-error-summary')?.focus();
})();
