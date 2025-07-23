console.log("INVENTORY.JS LOADED - VERSION 2.0");
// Manual override binding
function handleAddButton() {
    console.log("Add button CLICKED - manual handler");
    document.getElementById('addPopup').style.display = 'flex';
}

function handleResetButton() {
    console.log("Reset button CLICKED - manual handler");
    document.querySelectorAll('input[type="text"], input[type="number"], input[type="date"]').forEach(input => {
        input.value = '';
    });
}

// Remove any existing listeners first
const addBtn = document.getElementById('addItemBtn');
const resetBtn = document.getElementById('resetButton');

addBtn?.replaceWith(addBtn.cloneNode(true)); // Fresh clone
resetBtn?.replaceWith(resetBtn.cloneNode(true)); // Fresh clone

// Rebind
document.getElementById('addItemBtn')?.addEventListener('click', handleAddButton);
document.getElementById('resetButton')?.addEventListener('click', handleResetButton);

console.log("Forced event rebinding complete");
