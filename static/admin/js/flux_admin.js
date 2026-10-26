(function () {
    'use strict';
    var search = document.getElementById('flux-model-search');
    var filter = document.getElementById('flux-app-filter');
    if (!search || !filter) return;
    var groups = Array.from(document.querySelectorAll('[data-app]'));
    function update() {
        var query = search.value.toLocaleLowerCase().trim();
        var total = 0;
        groups.forEach(function (group) {
            var count = 0;
            group.querySelectorAll('[data-model-name]').forEach(function (card) {
                card.hidden = !card.dataset.modelName.toLocaleLowerCase().includes(query) || (filter.value && group.dataset.app !== filter.value);
                if (!card.hidden) count++;
            });
            group.hidden = !count;
            total += count;
        });
        document.getElementById('flux-library-empty').hidden = total !== 0;
        document.getElementById('flux-library-status').textContent = query || filter.value ? total + ' matching record type' + (total === 1 ? '' : 's') : '';
    }
    search.addEventListener('input', update);
    filter.addEventListener('change', update);
    search.addEventListener('keydown', function (event) { if (event.key === 'Escape') { search.value = ''; update(); } });
    document.getElementById('flux-clear-search').addEventListener('click', function () { search.value = ''; filter.value = ''; update(); search.focus(); });
}());
