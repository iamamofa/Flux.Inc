// consumables.js - Complete Implementation

class ConsumablesManager {
    constructor() {
        // Current state
        this.currentItemId = null;
        this.currentProject = null;
        
        // Initialize when DOM is ready
        document.addEventListener('DOMContentLoaded', () => this.init());
    }

    init() {
        // Cache DOM elements
        this.dom = {
            popups: {
                add: document.getElementById('addPopup'),
                edit: document.getElementById('editPopup'),
                retrieve: document.getElementById('retrievePopup'),
                return: document.getElementById('returnPopup'),
                delete: document.getElementById('deletePopup')
            },
            forms: {
                add: document.getElementById('add-form'),
                edit: document.getElementById('edit-form'),
                retrieve: document.getElementById('retrieve-form'),
                return: document.getElementById('return-form')
            },
            filters: {
                name: document.getElementById('nameFilterInput'),
                productCode: document.getElementById('productCodeFilterInput'),
                minQuantity: document.getElementById('minQuantityFilterInput'),
                maxQuantity: document.getElementById('maxQuantityFilterInput'),
                minDateExpired: document.getElementById('minDateExpiredFilterInput'),
                maxDateExpired: document.getElementById('maxDateExpiredFilterInput'),
                minDateCreated: document.getElementById('minDateCreatedFilterInput'),
                maxDateCreated: document.getElementById('maxDateCreatedFilterInput'),
                storageLocation: document.getElementById('storageLocationFilterInput')
            }
        };

        // Initialize event listeners
        this.initEventListeners();
        
        // Apply initial filters if any
        this.filterTable();
    }

    initEventListeners() {
        // Add button
        document.getElementById('showAddPopupBtn')?.addEventListener('click', () => this.showAddPopup());
        
        // Popup close handlers (event delegation)
        document.addEventListener('click', (e) => {
            if (e.target.closest('.popup-close')) {
                this.closePopup(e.target.closest('.popup-overlay'));
            }
            if (e.target === document.querySelector('.popup-overlay.popup-container1')) {
                this.closeAddPopup();
            }
            if (e.target === document.querySelector('.popup-overlay.popup-container2')) {
                this.closeEditPopup();
            }
            if (e.target === document.querySelector('.popup-overlay.popup-container3')) {
                this.closeRetrievePopup();
            }
            if (e.target === document.querySelector('.popup-overlay.popup-container4')) {
                this.closeReturnPopup();
            }
        });

        // Table actions (event delegation)
        document.getElementById('consumablesTable')?.addEventListener('click', (e) => {
            const row = e.target.closest('tr[data-id]');
            if (!row) return;
            
            this.currentItemId = row.dataset.id;
            this.currentProject = row.dataset.project || '';
            
            if (e.target.closest('[onclick*="showEditPopup"]')) {
                this.showEditPopup(this.currentItemId);
            }
            else if (e.target.closest('[onclick*="showRetrievePopup"]')) {
                this.showRetrievePopup(this.currentItemId);
            }
            else if (e.target.closest('[onclick*="showReturnPopup"]')) {
                this.showReturnPopup(this.currentItemId);
            }
            else if (e.target.closest('[onclick*="showDeletePopup"]')) {
                this.showDeletePopup(this.currentProject, this.currentItemId);
            }
        });

        // Form submissions
        if (this.dom.forms.edit) {
            this.dom.forms.edit.addEventListener('submit', (e) => this.handleEditSubmit(e));
        }
        if (this.dom.forms.retrieve) {
            this.dom.forms.retrieve.addEventListener('submit', (e) => this.handleRetrieveSubmit(e));
        }
        if (this.dom.forms.return) {
            this.dom.forms.return.addEventListener('submit', (e) => this.handleReturnSubmit(e));
        }
        
        // Delete confirmation
        document.getElementById('confirmDeleteBtn')?.addEventListener('click', () => this.deleteItem());
        
        // Filters and sorting
        document.getElementById('resetButton')?.addEventListener('click', () => this.resetFilters());
        document.getElementById('sortColumnDropdown')?.addEventListener('change', () => this.sortTableByColumn());
        
        // Filter inputs with debouncing
        const debouncedFilter = this.debounce(() => this.filterTable(), 300);
        Object.values(this.dom.filters).forEach(filter => {
            if (filter) filter.addEventListener('input', debouncedFilter);
        });
    }

    // ======================
    // POPUP METHODS
    // ======================
    
    showPopup(popupElement) {
        if (popupElement) {
            popupElement.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }
    }

    closePopup(popupElement) {
        if (popupElement) {
            popupElement.style.display = 'none';
            document.body.style.overflow = '';
        }
    }

    showAddPopup() {
        this.showPopup(this.dom.popups.add);
    }

    closeAddPopup() {
        this.closePopup(this.dom.popups.add);
    }

    showEditPopup(id) {
        this.currentItemId = id;
        this.showPopup(this.dom.popups.edit);
        this.getItemInfo();
    }

    closeEditPopup() {
        this.closePopup(this.dom.popups.edit);
    }

    showRetrievePopup(id) {
        this.currentItemId = id;
        this.showPopup(this.dom.popups.retrieve);
    }

    closeRetrievePopup() {
        this.closePopup(this.dom.popups.retrieve);
    }

    showReturnPopup(id) {
        this.currentItemId = id;
        this.showPopup(this.dom.popups.return);
    }

    closeReturnPopup() {
        this.closePopup(this.dom.popups.return);
    }

    showDeletePopup(project, id) {
        this.currentItemId = id;
        this.currentProject = project;
        this.showPopup(this.dom.popups.delete);
    }

    closeDeletePopup() {
        this.closePopup(this.dom.popups.delete);
    }

    // ======================
    // ITEM MANAGEMENT
    // ======================

    async getItemInfo() {
        if (!this.currentItemId) return;

        try {
            this.showLoading(true);
            const response = await fetch(`/get_consumable_info/${this.currentItemId}`, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });

            if (!response.ok) throw new Error('Network response was not ok');
            
            const data = await response.json();
            this.populateEditForm(data);
        } catch (error) {
            console.error('Error fetching item info:', error);
            this.showAlert('error', 'Failed to load item information');
        } finally {
            this.showLoading(false);
        }
    }

    populateEditForm(data) {
        if (!this.dom.forms.edit) return;

        const fields = ['name', 'product_code', 'pack_size', 'quantity', 
                       'expiry_date', 'storage_location', 'threshold_value'];
        
        fields.forEach(field => {
            if (this.dom.forms.edit.elements[field] && data[field] !== undefined) {
                this.dom.forms.edit.elements[field].value = data[field];
            }
        });
    }

    async deleteItem() {
        if (!this.currentItemId || !this.currentProject) return;

        try {
            this.showLoading(true);
            const response = await fetch(`/delete_consumable/${this.currentProject}/${this.currentItemId}`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': this.getCSRFToken(),
                    'Content-Type': 'application/json',
                },
            });

            if (!response.ok) throw new Error('Failed to delete item');
            
            this.showAlert('success', 'Item deleted successfully');
            this.removeTableRow(this.currentItemId);
            this.closeDeletePopup();
        } catch (error) {
            console.error('Error deleting item:', error);
            this.showAlert('error', 'Failed to delete item');
        } finally {
            this.showLoading(false);
        }
    }

    // ======================
    // FORM HANDLERS
    // ======================

    async handleEditSubmit(e) {
        e.preventDefault();
        if (!this.currentItemId || !this.dom.forms.edit) return;

        try {
            this.showLoading(true, this.dom.forms.edit);
            const formData = new FormData(this.dom.forms.edit);
            const jsonData = Object.fromEntries(formData.entries());

            const response = await fetch(`/edit_consumable/${this.currentItemId}`, {
                method: 'PUT',
                headers: {
                    'X-CSRFToken': this.getCSRFToken(),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(jsonData),
            });

            if (!response.ok) throw new Error('Failed to update item');
            
            const data = await response.json();
            this.showAlert('success', 'Item updated successfully');
            this.refreshTableRow(this.currentItemId, data);
            this.closeEditPopup();
        } catch (error) {
            console.error('Error updating item:', error);
            this.showAlert('error', 'Failed to update item');
        } finally {
            this.showLoading(false, this.dom.forms.edit);
        }
    }

    async handleRetrieveSubmit(e) {
        e.preventDefault();
        if (!this.currentItemId || !this.dom.forms.retrieve) return;

        try {
            this.showLoading(true, this.dom.forms.retrieve);
            const formData = new FormData(this.dom.forms.retrieve);
            const jsonData = Object.fromEntries(formData.entries());

            const response = await fetch(`/retrieve_consumable/${this.currentItemId}`, {
                method: 'PUT',
                headers: {
                    'X-CSRFToken': this.getCSRFToken(),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(jsonData),
            });

            if (!response.ok) throw new Error('Failed to retrieve item');
            
            const data = await response.json();
            this.showAlert('success', 'Item retrieved successfully');
            this.refreshTableRow(this.currentItemId, data);
            this.closeRetrievePopup();
        } catch (error) {
            console.error('Error retrieving item:', error);
            this.showAlert('error', 'Failed to retrieve item');
        } finally {
            this.showLoading(false, this.dom.forms.retrieve);
        }
    }

    async handleReturnSubmit(e) {
        e.preventDefault();
        if (!this.currentItemId || !this.dom.forms.return) return;

        try {
            this.showLoading(true, this.dom.forms.return);
            const formData = new FormData(this.dom.forms.return);
            const jsonData = Object.fromEntries(formData.entries());

            const response = await fetch(`/return_consumable/${this.currentItemId}`, {
                method: 'PUT',
                headers: {
                    'X-CSRFToken': this.getCSRFToken(),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(jsonData),
            });

            if (!response.ok) throw new Error('Failed to return item');
            
            const data = await response.json();
            this.showAlert('success', 'Item returned successfully');
            this.refreshTableRow(this.currentItemId, data);
            this.closeReturnPopup();
        } catch (error) {
            console.error('Error returning item:', error);
            this.showAlert('error', 'Failed to return item');
        } finally {
            this.showLoading(false, this.dom.forms.return);
        }
    }

    // ======================
    // TABLE METHODS
    // ======================

    removeTableRow(id) {
        const row = document.querySelector(`tr[data-id="${id}"]`);
        if (row) row.remove();
    }

    refreshTableRow(id, data) {
        const row = document.querySelector(`tr[data-id="${id}"]`);
        if (!row || !data) return;

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

    // ======================
    // FILTER & SORT METHODS
    // ======================

    filterTable() {
        const table = document.getElementById('consumablesTable');
        if (!table) return;

        const filterValues = {
            name: this.dom.filters.name?.value.toLowerCase() || '',
            productCode: this.dom.filters.productCode?.value.toLowerCase() || '',
            minQuantity: this.dom.filters.minQuantity?.value ? parseInt(this.dom.filters.minQuantity.value) : 0,
            maxQuantity: this.dom.filters.maxQuantity?.value ? parseInt(this.dom.filters.maxQuantity.value) : Infinity,
            minDateExpired: this.dom.filters.minDateExpired?.value || '1900-01-01',
            maxDateExpired: this.dom.filters.maxDateExpired?.value || '9999-12-31',
            minDateCreated: this.dom.filters.minDateCreated?.value || '1900-01-01',
            maxDateCreated: this.dom.filters.maxDateCreated?.value || '9999-12-31',
            storageLocation: this.dom.filters.storageLocation?.value.toLowerCase() || ''
        };

        const rows = table.querySelectorAll('tr[data-id]');
        rows.forEach(row => {
            const rowData = {
                name: row.dataset.name?.toLowerCase() || '',
                productCode: row.dataset.productCode?.toLowerCase() || '',
                quantity: parseInt(row.dataset.quantity) || 0,
                dateCreated: row.dataset.dateCreated || '',
                expiryDate: row.dataset.expiryDate || '',
                storageLocation: row.dataset.storageLocation?.toLowerCase() || ''
            };

            const isVisible = (
                rowData.name.includes(filterValues.name) &&
                rowData.productCode.includes(filterValues.productCode) &&
                rowData.quantity >= filterValues.minQuantity &&
                rowData.quantity <= filterValues.maxQuantity &&
                this.isDateInRange(rowData.dateCreated, filterValues.minDateCreated, filterValues.maxDateCreated) &&
                this.isDateInRange(rowData.expiryDate, filterValues.minDateExpired, filterValues.maxDateExpired) &&
                rowData.storageLocation.includes(filterValues.storageLocation)
            );

            row.style.display = isVisible ? '' : 'none';
        });
    }

    sortTableByColumn() {
        const dropdown = document.getElementById('sortColumnDropdown');
        if (!dropdown) return;

        const columnNum = dropdown.value;
        if (!columnNum || columnNum === '0') {
            this.resetFilters();
            return;
        }

        const table = document.getElementById('consumablesTable');
        if (!table) return;

        const rows = Array.from(table.querySelectorAll('tr[data-id]'));
        if (rows.length === 0) return;

        rows.sort((a, b) => {
            const aValue = this.getColumnValue(a, columnNum);
            const bValue = this.getColumnValue(b, columnNum);

            if (columnNum === '4') { // Quantity column
                return aValue - bValue;
            }
            return aValue.localeCompare(bValue);
        });

        rows.forEach(row => table.appendChild(row));
    }

    resetFilters() {
        // Reset all filter inputs
        Object.values(this.dom.filters).forEach(filter => {
            if (filter) filter.value = '';
        });
        
        // Show all rows
        const rows = document.querySelectorAll('#consumablesTable tr[data-id]');
        rows.forEach(row => row.style.display = '');
        
        // Reset sort dropdown
        const dropdown = document.getElementById('sortColumnDropdown');
        if (dropdown) dropdown.value = '0';
    }

    // ======================
    // UTILITY METHODS
    // ======================

    getCSRFToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content || '';
    }

    isDateInRange(dateString, minDateString, maxDateString) {
        if (!dateString) return true;
        try {
            const date = new Date(dateString);
            const minDate = new Date(minDateString);
            const maxDate = new Date(maxDateString);
            return date >= minDate && date <= maxDate;
        } catch (e) {
            console.error('Date parsing error:', e);
            return true;
        }
    }

    getColumnValue(row, columnNum) {
        const column = row.querySelector(`td:nth-child(${columnNum})`);
        if (!column) return '';
        const value = column.textContent.trim();
        return columnNum === '4' ? parseFloat(value) || 0 : value.toLowerCase();
    }

    debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    showLoading(show, element = document.body) {
        const overlay = document.getElementById('loading-overlay');
        if (!overlay) return;

        if (show) {
            overlay.style.display = 'flex';
            if (element) element.style.pointerEvents = 'none';
        } else {
            overlay.style.display = 'none';
            if (element) element.style.pointerEvents = '';
        }
    }

    showAlert(type, message) {
        const container = document.getElementById('notification-container');
        if (!container) return;

        const alert = document.createElement('div');
        alert.className = `notification ${type}`;
        alert.textContent = message;
        container.appendChild(alert);

        setTimeout(() => {
            alert.classList.add('fade-out');
            setTimeout(() => alert.remove(), 500);
        }, 3000);
    }
}

// Initialize the manager
// new ConsumablesManager();
