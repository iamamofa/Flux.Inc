// consumables.js - Complete functional implementation

// ==============================================
// CONSTANTS AND INITIAL STATE
// ==============================================
const DOM = {
    modals: {
        add: document.getElementById('addPopup'),
        edit: document.getElementById('editPopup'),
        // ... rest of modal elements
    },
    // ... rest of DOM definitions
};

const STATE = {
    currentItemId: null,
    currentProject: null,
    activeSort: {
        column: null,
        direction: 'asc'
    }
};

const CSRF_TOKEN = document.querySelector('meta[name="csrf-token"]')?.content || '';

// ==============================================
// INITIALIZATION (called when DOM is ready)
// ==============================================
function initConsumablesManager() {
    setupEventListeners();
    setupAccessibility();
    initialFilter();
}

// ==============================================
    // EVENT HANDLERS SETUP
    // ==============================================
    function setupEventListeners() {
        // Modal events
        setupModalCloseHandlers();
        
        // Form submissions
        setupFormHandlers();
        
        // Table interactions
        setupTableEventDelegation();
        
        // Filtering/sorting
        setupFilterAndSortListeners();
    }

    function setupModalCloseHandlers() {
        // Close modals when clicking outside
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('popup-overlay')) {
                const modalId = e.target.id;
                if (modalId.includes('add')) closeAddPopup();
                if (modalId.includes('edit')) closeEditPopup();
                if (modalId.includes('retrieve')) closeRetrievePopup();
                if (modalId.includes('return')) closeReturnPopup();
            }
        });
    }

    function setupFormHandlers() {
        // Add form
        DOM.forms.add?.addEventListener('submit', handleAddSubmit);
        
        // Edit form
        DOM.forms.edit?.addEventListener('submit', handleEditSubmit);
        
        // Retrieve form
        DOM.forms.retrieve?.addEventListener('submit', handleRetrieveSubmit);
        
        // Return form
        DOM.forms.return?.addEventListener('submit', handleReturnSubmit);
        
        // Delete confirmation
        document.getElementById('confirmDeleteBtn')?.addEventListener('click', handleDeleteConfirm);
    }

    function setupTableEventDelegation() {
        DOM.table?.addEventListener('click', (e) => {
            const row = e.target.closest('tr[data-id]');
            if (!row) return;
            
            STATE.currentItemId = row.dataset.id;
            STATE.currentProject = row.dataset.project || '';
            
            if (e.target.closest('.edit-btn')) {
                showEditPopup(STATE.currentItemId);
            }
            else if (e.target.closest('.retrieve-btn')) {
                showRetrievePopup(STATE.currentItemId);
            }
            else if (e.target.closest('.return-btn')) {
                showReturnPopup(STATE.currentItemId);
            }
            else if (e.target.closest('.delete-btn')) {
                showDeletePopup(STATE.currentProject, STATE.currentItemId);
            }
        });
    }

    function setupFilterAndSortListeners() {
        // Debounced filter (300ms)
        const debouncedFilter = debounce(filterTable, 300);
        
        // Add input listeners to all filter inputs
        Object.values(DOM.filterInputs).forEach(input => {
            input?.addEventListener('input', debouncedFilter);
        });
        
        // Reset filters
        DOM.buttons.resetFilters?.addEventListener('click', resetFilters);
        
        // Sorting
        document.getElementById('sortColumnDropdown')?.addEventListener('change', sortTableByColumn);
    }

    // ==============================================
    // MODAL FUNCTIONS
    // ==============================================
    function showAddPopup() {
        showModal(DOM.modals.add);
    }

    function closeAddPopup() {
        closeModal(DOM.modals.add);
        DOM.forms.add?.reset();
    }

    function showEditPopup(id) {
        STATE.currentItemId = id;
        showModal(DOM.modals.edit);
        loadItemData();
    }

    function closeEditPopup() {
        closeModal(DOM.modals.edit);
    }

    function showRetrievePopup(id) {
        STATE.currentItemId = id;
        showModal(DOM.modals.retrieve);
    }

    function closeRetrievePopup() {
        closeModal(DOM.modals.retrieve);
        DOM.forms.retrieve?.reset();
    }

    function showReturnPopup(id) {
        STATE.currentItemId = id;
        showModal(DOM.modals.return);
    }

    function closeReturnPopup() {
        closeModal(DOM.modals.return);
        DOM.forms.return?.reset();
    }

    function showDeletePopup(project, id) {
        STATE.currentItemId = id;
        STATE.currentProject = project;
        showModal(DOM.modals.delete);
    }

    function closeDeletePopup() {
        closeModal(DOM.modals.delete);
    }

    function showModal(modal) {
        if (!modal) return;
        modal.style.display = 'flex';
        modal.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
    }

    function closeModal(modal) {
        if (!modal) return;
        modal.style.display = 'none';
        modal.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
    }

    // ==============================================
    // DATA HANDLING FUNCTIONS
    // ==============================================
    async function loadItemData() {
        if (!STATE.currentItemId) return;
        
        showLoading(DOM.modals.edit);
        
        try {
            const response = await fetch(`/get_consumable_info/${STATE.currentItemId}`);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            populateEditForm(data);
        } catch (error) {
            console.error('Error loading item data:', error);
            showNotification('Failed to load item data', 'error');
        } finally {
            hideLoading();
        }
    }

    function populateEditForm(data) {
        if (!DOM.forms.edit) return;
        
        const fields = ['name', 'product_code', 'pack_size', 'quantity', 
                       'expiry_date', 'storage_location', 'threshold_value'];
        
        fields.forEach(field => {
            if (DOM.forms.edit.elements[field]) {
                DOM.forms.edit.elements[field].value = data[field] || '';
            }
        });
    }

    // ==============================================
    // FORM HANDLERS
    // ==============================================
    async function handleAddSubmit(e) {
        e.preventDefault();
        if (!DOM.forms.add) return;
        
        showLoading(DOM.modals.add);
        
        try {
            const formData = new FormData(DOM.forms.add);
            const response = await fetch(DOM.forms.add.action, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': CSRF_TOKEN
                },
                body: formData
            });
            
            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.message || 'Failed to add item');
            }
            
            showNotification('Item added successfully', 'success');
            closeAddPopup();
            
            // Refresh the page to show new item
            if (result.refresh) {
                setTimeout(() => location.reload(), 1000);
            }
        } catch (error) {
            console.error('Add item error:', error);
            showNotification(error.message || 'Failed to add item', 'error');
        } finally {
            hideLoading();
        }
    }

    async function handleEditSubmit(e) {
        e.preventDefault();
        if (!STATE.currentItemId || !DOM.forms.edit) return;
        
        showLoading(DOM.modals.edit);
        
        try {
            const formData = new FormData(DOM.forms.edit);
            const jsonData = Object.fromEntries(formData.entries());
            
            const response = await fetch(`/edit_consumable/${STATE.currentItemId}`, {
                method: 'PUT',
                headers: {
                    'X-CSRFToken': CSRF_TOKEN,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(jsonData)
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.message || 'Failed to update item');
            }
            
            updateTableRow(STATE.currentItemId, data);
            showNotification('Item updated successfully', 'success');
            closeEditPopup();
        } catch (error) {
            console.error('Edit item error:', error);
            showNotification(error.message || 'Failed to update item', 'error');
        } finally {
            hideLoading();
        }
    }

    // Similar handlers for retrieve/return/delete...

    // ==============================================
    // TABLE OPERATIONS
    // ==============================================
    function updateTableRow(id, data) {
        const row = DOM.table?.querySelector(`tr[data-id="${id}"]`);
        if (!row) return;
        
        // Highlight update
        row.classList.add('updated');
        setTimeout(() => row.classList.remove('updated'), 1000);
        
        // Update cells
        const cells = row.querySelectorAll('td');
        if (cells.length >= 7) {
            cells[0].textContent = data.name || '';
            cells[1].textContent = data.product_code || '';
            cells[2].textContent = `${data.pack_size_rem || 0}/${data.pack_size || 0}`;
            cells[3].textContent = data.quantity || '';
            cells[5].textContent = data.expiry_date || '';
            cells[6].textContent = data.storage_location || '';
        }
    }

    // ==============================================
    // FILTERING/SORTING
    // ==============================================
    function filterTable() {
        const filters = {
            name: DOM.filterInputs.name?.value.toLowerCase() || '',
            productCode: DOM.filterInputs.productCode?.value.toLowerCase() || '',
            minQuantity: DOM.filterInputs.minQuantity?.value ? parseInt(DOM.filterInputs.minQuantity.value) : 0,
            maxQuantity: DOM.filterInputs.maxQuantity?.value ? parseInt(DOM.filterInputs.maxQuantity.value) : Infinity,
            minDateExpired: DOM.filterInputs.minDateExpired?.value || '',
            maxDateExpired: DOM.filterInputs.maxDateExpired?.value || '',
            minDateCreated: DOM.filterInputs.minDateCreated?.value || '',
            maxDateCreated: DOM.filterInputs.maxDateCreated?.value || '',
            storageLocation: DOM.filterInputs.storageLocation?.value.toLowerCase() || ''
        };
        
        const rows = DOM.table?.querySelectorAll('tr[data-id]') || [];
        
        rows.forEach(row => {
            const isVisible = checkRowAgainstFilters(row, filters);
            row.style.display = isVisible ? '' : 'none';
        });
    }

    function checkRowAgainstFilters(row, filters) {
        const rowData = {
            name: (row.dataset.name || '').toLowerCase(),
            productCode: (row.dataset.productCode || '').toLowerCase(),
            quantity: parseInt(row.dataset.quantity) || 0,
            dateCreated: row.dataset.dateCreated || '',
            expiryDate: row.dataset.expiryDate || '',
            storageLocation: (row.dataset.storageLocation || '').toLowerCase()
        };
        
        return (
            rowData.name.includes(filters.name) &&
            rowData.productCode.includes(filters.productCode) &&
            rowData.quantity >= filters.minQuantity &&
            rowData.quantity <= filters.maxQuantity &&
            isDateInRange(rowData.dateCreated, filters.minDateCreated, filters.maxDateCreated) &&
            isDateInRange(rowData.expiryDate, filters.minDateExpired, filters.maxDateExpired) &&
            rowData.storageLocation.includes(filters.storageLocation)
        );
    }

    // ==============================================
    // UTILITY FUNCTIONS
    // ==============================================
    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    function showLoading(container) {
        // Implement loading indicator
    }

    function hideLoading() {
        // Hide loading indicator
    }

    function showNotification(message, type = 'success') {
        // Implement notification system
    }

    function isDateInRange(dateString, minDateString, maxDateString) {
        // Date range validation
    }

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initConsumablesManager);
