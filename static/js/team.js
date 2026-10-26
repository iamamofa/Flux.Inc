(function () {
    'use strict';
    var table = document.getElementById('teamTable');
    if (!table) return;
    var search = document.getElementById('team-search');
    var filter = document.getElementById('team-access-filter');
    var activeRow = null;
    var pending = false;
    var toastTimer;
    function updateDirectory() {
        var rows = Array.from(table.querySelectorAll('tr[data-id]'));
        var query = search.value.trim().toLocaleLowerCase();
        var matches = 0;
        rows.forEach(function (row) {
            row.hidden = !row.dataset.search.toLocaleLowerCase().includes(query) || (filter.value !== 'all' && row.dataset.access !== filter.value);
            if (!row.hidden) matches++;
        });
        document.getElementById('team-no-results').hidden = matches !== 0;
        document.getElementById('team-results').textContent = 'Showing ' + matches + ' of ' + rows.length + ' team members';
        document.querySelectorAll('[data-count]').forEach(function (count) {
            count.textContent = count.dataset.count === 'all' ? rows.length : rows.filter(function (row) { return row.dataset.access === count.dataset.count; }).length;
        });
    }
    search.addEventListener('input', updateDirectory);
    filter.addEventListener('change', updateDirectory);
    document.getElementById('team-clear-filters').addEventListener('click', function () { search.value = ''; filter.value = 'all'; updateDirectory(); search.focus(); });
    function openDialog(id, row) {
        activeRow = row;
        var dialog = document.getElementById(id);
        dialog.querySelector('.team-form-error').hidden = true;
        dialog.querySelectorAll('[data-member-name]').forEach(function (name) { name.textContent = row.dataset.name; });
        if (id === 'team-edit-dialog') document.getElementById('edit-role').value = row.dataset.access;
        dialog.showModal();
    }
    document.querySelectorAll('[data-open-add]').forEach(function (button) {
        button.addEventListener('click', function () { openDialog('team-add-dialog', null); });
    });
    table.addEventListener('click', function (event) {
        var edit = event.target.closest('[data-edit-member]');
        var remove = event.target.closest('[data-remove-member]');
        if (edit || remove) openDialog(edit ? 'team-edit-dialog' : 'team-remove-dialog', (edit || remove).closest('tr'));
    });
    document.querySelectorAll('.team-dialog').forEach(function (dialog) {
        dialog.addEventListener('cancel', function (event) { if (pending) event.preventDefault(); });
        dialog.querySelectorAll('[data-close-dialog]').forEach(function (button) { button.addEventListener('click', function () { if (!pending) dialog.close(); }); });
        dialog.addEventListener('click', function (event) {
            if (!pending && event.target === dialog) {
                var bounds = dialog.getBoundingClientRect();
                if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
            }
        });
        dialog.querySelector('form').addEventListener('submit', async function (event) {
            event.preventDefault();
            if (pending) return;
            var form = event.target;
            var button = form.querySelector('[type="submit"]');
            var originalText = button.textContent;
            var error = form.querySelector('.team-form-error');
            var row = activeRow;
            var url = form.id === 'member-form' ? form.action : form.id === 'edit-form' ? row.dataset.editUrl : row.dataset.removeUrl;
            pending = true;
            error.hidden = true;
            button.disabled = true;
            button.textContent = 'Saving…';
            form.setAttribute('aria-busy', 'true');
            try {
                var response = await fetch(url, {method:'POST',body:new FormData(form),headers:{'X-Requested-With':'XMLHttpRequest'}});
                var data;
                try { data = await response.json(); } catch (_) { throw new Error('Your session may have expired. Refresh the page and try again.'); }
                if (!response.ok || !data.success) throw new Error(data.message || data.error || 'The change could not be saved. Please try again.');
                if (form.id === 'member-form') { window.location.reload(); return; }
                if (form.id === 'edit-form') {
                    var role = form.elements.role.value;
                    row.dataset.access = role;
                    var badge = row.querySelector('.team-badge');
                    badge.dataset.role = role;
                    badge.textContent = role + ' access';
                } else { row.remove(); }
                dialog.close();
                updateDirectory();
                if (!row.isConnected || row.hidden) search.focus();
                var toast = document.getElementById('team-notification');
                toast.textContent = data.message;
                toast.hidden = false;
                window.clearTimeout(toastTimer);
                toastTimer = window.setTimeout(function () { toast.hidden = true; }, 5000);
            } catch (failure) { error.textContent = failure.message || 'A network error occurred. Please try again.'; error.hidden = false; }
            finally { pending = false; button.disabled = false; button.textContent = originalText; form.removeAttribute('aria-busy'); }
        });
    });
}());
