(function () {
    const item = document.querySelector('#borrow-share-item');
    const quantity = document.querySelector('#borrow-share-quantity');
    const available = document.querySelector('#borrow-share-available');
    if (!item || !quantity || !available) return;
    function sync() {
        const selected = item.options[item.selectedIndex];
        const max = Number(selected && selected.dataset.available);
        if (!max) {
            quantity.removeAttribute('max');
            available.textContent = 'Choose an item to see available packs.';
            return;
        }
        quantity.max = String(max);
        if (Number(quantity.value) > max) quantity.value = String(max);
        available.textContent = `${max} unopened pack${max === 1 ? '' : 's'} available`;
    }
    item.addEventListener('change', sync);
    sync();
}());
