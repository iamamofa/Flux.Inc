(function () {
    'use strict';
    var sidebar = document.getElementById('navigation');
    var shade = document.getElementById('screen-shade');
    var open = document.getElementById('sidebar-open');
    var close = document.getElementById('sidebar-close');
    function setNav(show) {
        if (!sidebar) return;
        sidebar.classList.toggle('is-open', show);
        shade.classList.toggle('is-open', show);
        document.body.classList.toggle('navigation-open', show);
        if (open) open.setAttribute('aria-expanded', String(show));
        if (show && close) close.focus();
        else if (open && window.innerWidth <= 950) open.focus();
    }
    if (open) open.addEventListener('click', function () { setNav(true); });
    if (close) close.addEventListener('click', function () { setNav(false); });
    if (shade) shade.addEventListener('click', function () { setNav(false); });
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && sidebar.classList.contains('is-open')) setNav(false);
        if (event.key !== 'Tab' || !sidebar.classList.contains('is-open')) return;
        var items = Array.from(sidebar.querySelectorAll('a, button')).filter(function (item) { return item.getClientRects().length; });
        if (event.shiftKey && document.activeElement === items[0]) { event.preventDefault(); items[items.length - 1].focus(); }
        else if (!event.shiftKey && document.activeElement === items[items.length - 1]) { event.preventDefault(); items[0].focus(); }
    });
    window.matchMedia('(min-width: 951px)').addEventListener('change', function (event) {
        if (event.matches) setNav(false);
    });
    document.querySelectorAll('.nav-link.selected').forEach(function (link) { link.setAttribute('aria-current', 'page'); });
    document.querySelectorAll('form[data-confirm]').forEach(function (form) {
        form.addEventListener('submit', function (event) { if (!window.confirm(form.dataset.confirm || 'Confirm this action?')) event.preventDefault(); });
    });
    document.querySelectorAll('.form-field').forEach(function (field) {
        var input = field.querySelector('input, select, textarea');
        if (!input) return;
        var descriptions = Array.from(field.querySelectorAll('small[id], .form-error[id]')).map(function (item) { return item.id; });
        if (descriptions.length) input.setAttribute('aria-describedby', descriptions.join(' '));
        if (field.classList.contains('form-field-invalid')) input.setAttribute('aria-invalid', 'true');
    });
}());
