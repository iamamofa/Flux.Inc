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

(function () {
    'use strict';
    document.querySelectorAll('[data-control-password]').forEach(function (button) {
        button.addEventListener('click', function () {
            var input = document.getElementById(button.dataset.controlPassword);
            var visible = input.type === 'password';
            input.type = visible ? 'text' : 'password';
            button.textContent = visible ? 'Hide' : 'Show';
            button.setAttribute('aria-pressed', String(visible));
            var label = document.querySelector('label[for="' + input.id + '"]');
            button.setAttribute('aria-label', (visible ? 'Hide ' : 'Show ') + label.textContent.replace('*', '').trim().toLowerCase());
        });
    });
    document.querySelectorAll('[data-date-range]').forEach(function (form) {
        var start = form.querySelector('[name="from"]');
        var end = form.querySelector('[name="to"]');
        if (!start || !end) return;
        var error = form.querySelector('[data-date-error]');
        function clearError() { error.hidden = true; end.removeAttribute('aria-invalid'); }
        start.addEventListener('input', clearError);
        end.addEventListener('input', clearError);
        form.addEventListener('submit', function (event) {
            if (start.value && end.value && start.value > end.value) {
                event.preventDefault();
                error.hidden = false;
                end.setAttribute('aria-invalid', 'true');
                end.focus();
            }
        });
    });
    var search = document.getElementById('permission-search');
    if (search) {
        var picker = document.getElementById('id_permissions');
        var options = Array.from(picker.querySelectorAll('[data-permission-search]'));
        function updatePermissions() {
            var query = search.value.toLocaleLowerCase().trim();
            var matches = 0;
            var selected = 0;
            options.forEach(function (option) {
                option.hidden = !option.dataset.permissionSearch.toLocaleLowerCase().includes(query);
                if (!option.hidden) matches++;
                if (option.querySelector('input').checked) selected++;
            });
            picker.querySelectorAll('[data-permission-section]').forEach(function (section) {
                var visible = Array.from(section.querySelectorAll('[data-permission-search]')).some(function (option) { return !option.hidden; });
                section.hidden = !visible;
                if (query && visible) section.open = true;
            });
            document.getElementById('permission-count').textContent = selected + ' selected' + (query ? ' · ' + matches + ' matching' : '');
            document.getElementById('permission-empty').hidden = matches !== 0;
        }
        search.addEventListener('input', updatePermissions);
        picker.addEventListener('change', updatePermissions);
        search.addEventListener('keydown', function (event) { if (event.key === 'Escape') { search.value = ''; updatePermissions(); } });
        updatePermissions();
    }
    var summary = document.querySelector('.form-error-summary');
    if (summary) { summary.tabIndex = -1; summary.focus(); }
}());
