// ========================
// REAGENTS MANAGEMENT SYSTEM
// ========================

// ========================
// MODAL MANAGER SECTION
// ========================
class ModalManager {
    constructor() {
        this.modals = {};
        this.currentItemId = null;
        this.currentProject = null;
    }
    
    registerModal(containerClass, popupId) {
        const container = document.querySelector(containerClass);
        const popup = document.getElementById(popupId);
        
        if (!container || !popup) return;
        
        this.modals[popupId] = { container, popup };
        
        container.addEventListener("click", (e) => {
            if (e.target === container) this.hideModal(popupId);
        });
    }
    
    showModal(popupId, itemId = null, projectName = null) {
        if (this.modals[popupId]) {
            this.currentItemId = itemId;
            this.currentProject = projectName;
            this.modals[popupId].popup.style.display = 'flex';
            
            // If it's the edit modal, fetch item info
            if (popupId === 'editPopup' && itemId) {
                this.getItemInfo(itemId);
            }
        }
    }
    
    hideModal(popupId) {
        if (this.modals[popupId]) {
            this.modals[popupId].popup.style.display = 'none';
        }
    }
    
    getItemInfo(id) {
        fetch(`/get_reagent_info/${id}`, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
        })
        .then(response => response.json())
        .then(data => {
            const form = document.getElementById('edit-form');
            if (!form) return;
            
            form.elements.name.value = data.name;
            form.elements.product_code.value = data.product_code;
            form.elements.pack_size.value = data.pack_size;
            form.elements.quantity.value = data.quantity;
            form.elements.expiry_date.value = data.expiry_date;
            form.elements.storage_location.value = data.storage_location;
            form.elements.threshold_value.value = data.threshold_value;
        })
        .catch(error => {
            console.error(`Error retrieving reagent information:`, error);
            // Show error to user
        });
    }
}

// ========================
// FORM HANDLER SECTION
// ========================
class FormHandler {
    constructor() {
        this.csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        this.setupFormSubmissions();
    }
    
    setupFormSubmissions() {
        // Add form
        this.setupForm('reagent-form', 'POST', '/add_reagent', this.handleAddResponse);
        
        // Edit form
        this.setupForm('edit-form', 'PUT', (id) => `/edit_reagent/${id}`, this.handleEditResponse);
        
        // Retrieve form
        this.setupForm('retrieve-form', 'PUT', (id) => `/retrieve_reagent/${id}`, this.handleRetrieveResponse);
        
        // Return form
        this.setupForm('return-form', 'PUT', (id) => `/return_reagent/${id}`, this.handleReturnResponse);
    }
    
    setupForm(formId, method, url, callback) {
        const form = document.getElementById(formId);
        if (!form) return;
        
        form.addEventListener('submit', (event) => {
            event.preventDefault();
            const formData = new FormData(form);
            const jsonData = this.formDataToJson(formData);
            
            // Resolve URL (could be function or string)
            const resolvedUrl = typeof url === 'function' 
                ? url(window.modalManager?.currentItemId) 
                : url;
            
            fetch(resolvedUrl, {
                method: method,
                headers: {
                    'X-CSRFToken': this.csrfToken,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(jsonData),
            })
            .then(response => {
                if (!response.ok) throw new Error('Network response was not ok');
                return response.json();
            })
            .then(data => callback(data))
            .catch(error => {
                console.error(`Error with ${formId} submission:`, error);
                // Show error to user
            });
        });
    }
    
    formDataToJson(formData) {
        const jsonData = {};
        formData.forEach((value, key) => {
            jsonData[key] = value;
        });
        return jsonData;
    }
    
    handleAddResponse(data) {
        window.modalManager?.hideModal('addPopup');
        window.tableManager?.refreshTable();
    }
    
    handleEditResponse(data) {
        window.modalManager?.hideModal('editPopup');
        window.tableManager?.refreshTableRow(data.id, data);
    }
    
    handleRetrieveResponse(data) {
        window.modalManager?.hideModal('retrievePopup');
        window.tableManager?.refreshTableRow(data.id, data);
        document.getElementById('retrieveFilterInput').value = '';
    }
    
    handleReturnResponse(data) {
        window.modalManager?.hideModal('returnPopup');
        window.tableManager?.refreshTableRow(data.id, data);
        document.getElementById('returnFilterInput').value = '';
    }
}

// ========================
// TABLE MANAGER SECTION
// ========================
class TableManager {
    constructor() {
        this.table = document.getElementById('reagentsTable');
    }
    
    refreshTable() {
        console.log('Refreshing entire table');
        location.reload(); // Simple implementation - could be optimized
    }
    
    refreshTableRow(id, data) {
        const row = this.table.querySelector(`tr[data-id="${id}"]`);
        if (!row) return;
        
        const columns = row.querySelectorAll('td');
        columns[0].setAttribute('data-fulltext', data.name);
        columns[0].textContent = truncateText(data.name, 20);
        columns[1].textContent = data.product_code;
        columns[2].textContent = `${data.pack_size_rem}/${data.pack_size}`;
        columns[3].textContent = data.quantity;
        columns[4].textContent = data.date_recorded;
        columns[5].textContent = data.expiry_date;
        columns[6].setAttribute('data-fulltext', data.storage_location);
        columns[6].textContent = truncateText(data.storage_location, 15);
    }

    function truncateText(text, maxLength) {
        return text.length > maxLength 
            ? text.substring(0, maxLength - 3) + '...' 
            : text;
    }
    
    removeTableRow(id) {
        const row = this.table.querySelector(`tr[data-id="${id}"]`);
        if (row) row.remove();
    }
    
    sortTableByColumn(columnNum) {
        if (columnNum === '0') {
            this.resetSort();
            return;
        }
        
        const rows = Array.from(this.table.querySelectorAll('tr'));
        
        rows.sort((row1, row2) => {
            const value1 = this.getColumnValue(row1, columnNum);
            const value2 = this.getColumnValue(row2, columnNum);
            
            if (columnNum === '4') {
                return value1 - value2;
            }
            
            return value1.localeCompare(value2);
        });
        
        rows.forEach(row => this.table.appendChild(row));
    }
    
    resetSort() {
        location.reload(); // Simple implementation - could be optimized
    }
    
    getColumnValue(row, columnNum) {
        const column = row.querySelector(`td:nth-child(${columnNum})`);
        if (!column) return '';
        
        const value = column.textContent.trim();
        return columnNum === '4' ? parseFloat(value) : value.toLowerCase();
    }
}

// ========================
// FILTER MANAGER SECTION
// ========================
class FilterManager {
    constructor(tableManager) {
        this.tableManager = tableManager;
        this.setupFilters();
    }
    
    setupFilters() {
        // Text filters
        this.setupTextFilter('nameFilterInput');
        this.setupTextFilter('productCodeFilterInput');
        this.setupTextFilter('storageLocationFilterInput');
        
        // Quantity filters
        this.setupNumberFilter('minQuantityFilterInput');
        this.setupNumberFilter('maxQuantityFilterInput');
        
        // Date filters
        this.setupDateFilter('minDateCreatedFilterInput');
        this.setupDateFilter('maxDateCreatedFilterInput');
        this.setupDateFilter('minDateExpiredFilterInput');
        this.setupDateFilter('maxDateExpiredFilterInput');
    }
    
    setupTextFilter(inputId) {
        const input = document.getElementById(inputId);
        if (input) input.addEventListener('input', () => this.filterTable());
    }
    
    setupNumberFilter(inputId) {
        const input = document.getElementById(inputId);
        if (input) input.addEventListener('input', () => this.filterTable());
    }
    
    setupDateFilter(inputId) {
        const input = document.getElementById(inputId);
        if (input) input.addEventListener('change', () => this.filterTable());
    }
    
    filterTable() {
        const filters = this.getCurrentFilters();
        const rows = this.tableManager.table.querySelectorAll('tr');
        
        rows.forEach(row => {
            const rowData = this.getRowData(row);
            const isVisible = this.applyFilters(rowData, filters);
            row.style.display = isVisible ? '' : 'none';
        });
    }
    
    getCurrentFilters() {
        return {
            name: document.getElementById('nameFilterInput')?.value.toLowerCase() || '',
            productCode: document.getElementById('productCodeFilterInput')?.value.toLowerCase() || '',
            minQuantity: parseInt(document.getElementById('minQuantityFilterInput')?.value) || 0,
            maxQuantity: parseInt(document.getElementById('maxQuantityFilterInput')?.value) || Infinity,
            minDateCreated: document.getElementById('minDateCreatedFilterInput')?.value || '1900-01-01',
            maxDateCreated: document.getElementById('maxDateCreatedFilterInput')?.value || '9999-12-31',
            minDateExpired: document.getElementById('minDateExpiredFilterInput')?.value || '1900-01-01',
            maxDateExpired: document.getElementById('maxDateExpiredFilterInput')?.value || '9999-12-31',
            storageLocation: document.getElementById('storageLocationFilterInput')?.value.toLowerCase() || ''
        };
    }
    
    getRowData(row) {
        return {
            name: row.querySelector('td:first-child')?.textContent.toLowerCase() || '',
            productCode: row.querySelector('td:nth-child(2)')?.textContent.toLowerCase() || '',
            quantity: parseInt(row.querySelector('td:nth-child(4)')?.textContent) || 0,
            dateCreated: row.querySelector('td:nth-child(5)')?.textContent || '',
            expiryDate: row.querySelector('td:nth-child(6)')?.textContent || '',
            storageLocation: row.querySelector('td:nth-child(7)')?.textContent.toLowerCase() || ''
        };
    }
    
    applyFilters(rowData, filters) {
        return (
            rowData.name.includes(filters.name) &&
            rowData.productCode.includes(filters.productCode) &&
            rowData.quantity >= filters.minQuantity &&
            rowData.quantity <= filters.maxQuantity &&
            this.isDateInRange(rowData.dateCreated, filters.minDateCreated, filters.maxDateCreated) &&
            this.isDateInRange(rowData.expiryDate, filters.minDateExpired, filters.maxDateExpired) &&
            rowData.storageLocation.includes(filters.storageLocation)
        );
    }
    
    isDateInRange(date, minDate, maxDate) {
        if (!date) return true;
        const currentDate = new Date(date);
        const min = new Date(minDate);
        const max = new Date(maxDate);
        return currentDate >= min && currentDate <= max;
    }
    
    resetFilters() {
        // Clear all filter inputs
        const inputs = [
            'nameFilterInput', 'productCodeFilterInput', 'minQuantityFilterInput',
            'maxQuantityFilterInput', 'minDateCreatedFilterInput', 'maxDateCreatedFilterInput',
            'minDateExpiredFilterInput', 'maxDateExpiredFilterInput', 'storageLocationFilterInput'
        ];
        
        inputs.forEach(id => {
            const input = document.getElementById(id);
            if (input) input.value = '';
        });
        
        // Reset sort dropdown
        const sortDropdown = document.getElementById('sortColumnDropdown');
        if (sortDropdown) sortDropdown.value = '0';
        
        // Refresh the table
        this.filterTable();
    }
}


// ========================
// DROPDOWN MANAGER SECTION
// ========================
class DropdownManager {
    constructor() {
        this.setupDropdowns();
    }
    
    setupDropdowns() {
        // Toggle logic
        document.querySelectorAll('.dropdown-trigger').forEach(trigger => {
            trigger.addEventListener('click', (e) => {
                e.stopPropagation();
                trigger.closest('.dropdown').classList.toggle('active');
            });
        });

        // Close on outside click
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.dropdown')) {
                document.querySelectorAll('.dropdown').forEach(dropdown => {
                    dropdown.classList.remove('active');
                });
            }
        });
    }
}

// ========================
// MAIN APPLICATION SECTION
// ========================
document.addEventListener('DOMContentLoaded', function() {
    // Initialize all components
    window.modalManager = new ModalManager();
    window.formHandler = new FormHandler();
    window.tableManager = new TableManager();
    window.filterManager = new FilterManager(window.tableManager);
    window.dropdownManager = new DropdownManager();
    
    // Register modals
    window.modalManager.registerModal('.popup-container1', 'addPopup');
    window.modalManager.registerModal('.popup-container2', 'editPopup');
    window.modalManager.registerModal('.popup-container3', 'retrievePopup');
    window.modalManager.registerModal('.popup-container4', 'returnPopup');
    
    // Set up event listeners
    document.getElementById('addItemBtn')?.addEventListener('click', () => {
        window.modalManager.showModal('addPopup');
    });
    
    document.getElementById('resetButton')?.addEventListener('click', () => {
        window.filterManager.resetFilters();
    });
    
    document.getElementById('sortColumnDropdown')?.addEventListener('change', (e) => {
        window.tableManager.sortTableByColumn(e.target.value);
    });
    
    // Set up delete functionality if needed
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const id = e.target.dataset.id;
            const projectName = e.target.dataset.project;
            if (id && projectName) {
                if (confirm('Are you sure you want to delete this reagent?')) {
                    fetch(`/delete_reagent/${projectName}/${id}`, {
                        method: 'DELETE',
                        headers: {
                            'X-CSRFToken': window.formHandler.csrfToken,
                            'Content-Type': 'application/json',
                        },
                    })
                    .then(response => {
                        if (response.ok) {
                            window.tableManager.removeTableRow(id);
                        }
                    })
                    .catch(error => console.error('Error deleting reagent:', error));
                }
            }
        });
    });
});
