/**
 * Inventory Management System - Unified JavaScript for all inventory types
 * Handles: Consumables, Equipment, Reagents, Samples
 */

// Utility functions
class InventoryUtils {
    static getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }

    static showLoading(button) {
        button.dataset.originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<span class="spinner">Loading...</span>';
    }

    static resetLoading(button) {
        button.disabled = false;
        button.innerHTML = button.dataset.originalText;
    }

    static showNotification(message, type = 'success') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.classList.add('fade-out');
            setTimeout(() => notification.remove(), 500);
        }, 3000);
    }

    static handleResponse(response) {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    }

    static handleError(error) {
        console.error('Error:', error);
        this.showNotification('An error occurred. Please try again.', 'error');
    }

    // Safe HTML escaping function
    static escapeHTML(unsafe) {
        if (!unsafe) return '';
        return unsafe
            .toString()
            .replace(/&/g, "&amp;")
            .replace(/</g, "&alt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}

// Main Inventory Manager
class InventoryManager {
    constructor() {
        this.currentType = this.detectInventoryType();
        this.currentItemId = null;
        this.currentProject = null;
        this.modalManager = new ModalManager(this.currentType);
        this.init();
    }

    detectInventoryType() {
        const path = window.location.pathname;
        if (path.includes('consumables')) return 'consumable';
        if (path.includes('equipment')) return 'equipment';
        if (path.includes('reagents')) return 'reagent';
        if (path.includes('samples')) return 'sample';
        return 'consumable'; // default
    }

    init() {
        this.initTable();
        this.initFilters();
        this.initSorting();
        this.setupEventListeners();
    }

    initTable() {
        const tableConfig = {
            consumable: {
                columns: ['name', 'product_code', 'pack_size', 'quantity', 'date_recorded', 'expiry_date', 'storage_location'],
                sortable: ['name', 'product_code', 'quantity', 'date_recorded', 'expiry_date', 'storage_location'],
                filterable: ['name', 'product_code', 'quantity', 'date_recorded', 'expiry_date', 'storage_location']
            },
            equipment: {
                columns: ['name', 'equip_id', 'serial_num', 'quantity', 'status', 'service_contract_start', 'service_contract_end', 'date_recorded', 'donated_by', 'storage_location'],
                sortable: ['name', 'equip_id', 'serial_num', 'quantity', 'status', 'service_contract_start', 'service_contract_end', 'date_recorded', 'donated_by', 'storage_location'],
                filterable: ['name', 'equip_id', 'serial_num', 'quantity', 'status', 'service_contract_start', 'service_contract_end', 'date_recorded', 'donated_by', 'storage_location']
            },
            reagent: {
                columns: ['name', 'product_code', 'pack_size', 'quantity', 'date_recorded', 'expiry_date', 'storage_location'],
                sortable: ['name', 'product_code', 'quantity', 'date_recorded', 'expiry_date', 'storage_location'],
                filterable: ['name', 'product_code', 'quantity', 'date_recorded', 'expiry_date', 'storage_location']
            },
            sample: {
                columns: ['sample_id', 'sample_type', 'description', 'country', 'volume', 'date_recorded', 'well_id', 'storage_location'],
                sortable: ['sample_id', 'sample_type', 'country', 'volume', 'date_recorded', 'well_id', 'storage_location'],
                filterable: ['sample_id', 'sample_type', 'country', 'volume', 'date_recorded', 'well_id', 'storage_location']
            }
        };

        this.config = tableConfig[this.currentType];
    }

    initFilters() {
        const filterInputs = document.querySelectorAll('.filter-input');
        filterInputs.forEach(input => {
            input.addEventListener('input', () => this.applyFilters());
        });

        document.getElementById('resetButton')?.addEventListener('click', () => {
            document.querySelectorAll('.filter-input').forEach(input => {
                input.value = '';
            });
            this.applyFilters();
        });
    }

    applyFilters() {
        const filters = {};
        const filterInputs = document.querySelectorAll('.filter-input');
        
        filterInputs.forEach(input => {
            const filterName = input.id.replace('FilterInput', '').replace(/([A-Z])/g, '_$1').toLowerCase();
            filters[filterName] = input.value.toLowerCase();
        });

        const rows = document.querySelectorAll(`#${this.currentType}Table tbody tr`);
        
        rows.forEach(row => {
            let shouldShow = true;
            
            this.config.filterable.forEach(filterKey => {
                const cellValue = row.querySelector(`td[data-column="${filterKey}"]`)?.textContent.toLowerCase() || '';
                const filterValue = filters[filterKey.replace('_', '')] || '';
                
                if (filterValue && !cellValue.includes(filterValue)) {
                    shouldShow = false;
                }
            });

            row.style.display = shouldShow ? '' : 'none';
        });
    }

    initSorting() {
        const sortDropdown = document.getElementById('sortColumnDropdown');
        if (sortDropdown) {
            sortDropdown.addEventListener('change', () => {
                const columnIndex = sortDropdown.value;
                if (columnIndex === '0') {
                    location.reload();
                    return;
                }
                this.sortTable(columnIndex);
            });
        }
    }

    sortTable(columnIndex) {
        const table = document.querySelector(`#${this.currentType}Table`);
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        
        rows.sort((a, b) => {
            const aValue = a.cells[columnIndex].textContent;
            const bValue = b.cells[columnIndex].textContent;
            
            // Numeric sorting for quantity, volume, etc.
            if (['quantity', 'volume', 'pack_size'].includes(this.config.columns[columnIndex])) {
                return parseFloat(aValue) - parseFloat(bValue);
            }
            // Date sorting
            else if (['date_recorded', 'expiry_date', 'service_contract_start', 'service_contract_end'].includes(this.config.columns[columnIndex])) {
                return new Date(aValue) - new Date(bValue);
            }
            // Default text sorting
            else {
                return aValue.localeCompare(bValue);
            }
        });

        rows.forEach(row => tbody.appendChild(row));
    }

    setupEventListeners() {
        // Add item button
        document.getElementById('addItemBtn')?.addEventListener('click', () => {
            this.modalManager.showAddPopup();
        });

        // Export buttons
        document.querySelectorAll('.export-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const format = e.target.dataset.format;
                this.exportData(format);
            });
        });
    }

    exportData(format) {
        const endpoint = `/${this.currentType}s/export_${format}/${this.currentProject}`;
        window.location.href = endpoint;
    }
}

// Modal Management
class ModalManager {
    constructor(inventoryType) {
        this.inventoryType = inventoryType;
        this.modals = {
            add: document.getElementById('addPopup'),
            edit: document.getElementById('editPopup'),
            retrieve: document.getElementById('retrievePopup'),
            return: document.getElementById('returnPopup'),
            delete: document.getElementById('deletePopup')
        };
        this.init();
    }

    init() {
        // Close modals when clicking outside
        Object.values(this.modals).forEach(modal => {
            if (modal) {
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) this.hide(modal.id.replace('Popup', ''));
                });
            }
        });

        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            const activeModal = Object.values(this.modals).find(m => 
                m && (m.style.display === 'flex' || m.style.display === '')
            );
            
            if (!activeModal) return;
            
            if (e.key === 'Escape') {
                this.hide(activeModal.id.replace('Popup', ''));
            }
        });
    }

    show(modalName, itemId = null, projectName = null) {
        this.hideAll();
        this.currentItemId = itemId;
        this.currentProject = projectName || document.querySelector('.project-name-text').textContent;
        
        const modal = this.modals[modalName];
        if (!modal) return;

        modal.style.display = 'flex';
        
        if (modalName === 'edit' && itemId) {
            this.loadItemData(itemId);
        }
    }

    hide(modalName) {
        const modal = this.modals[modalName];
        if (modal) modal.style.display = 'none';
    }

    hideAll() {
        Object.keys(this.modals).forEach(key => this.hide(key));
    }

    async loadItemData(itemId) {
        try {
            const response = await fetch(`/get_${this.inventoryType}_info/${itemId}`);
            const data = await InventoryUtils.handleResponse(response);
            
            const form = document.getElementById('edit-form');
            if (form) {
                Object.entries(data).forEach(([key, value]) => {
                    const input = form.querySelector(`[name="${key}"]`);
                    if (input) input.value = value || '';
                });
            }
        } catch (error) {
            InventoryUtils.handleError(error);
        }
    }

    // Specific modal show methods
    showAddPopup() {
        this.show('add');
    }

    showEditPopup(itemId) {
        this.show('edit', itemId);
    }

    showRetrievePopup(itemId) {
        this.show('retrieve', itemId);
    }

    showReturnPopup(itemId) {
        this.show('return', itemId);
    }

    showDeletePopup(projectName, itemId) {
        this.show('delete', itemId, projectName);
    }
}

// Form Handlers
class FormHandler {
    static async handleAddForm(form, inventoryType) {
        const submitButton = form.querySelector('button[type="submit"]');
        InventoryUtils.showLoading(submitButton);

        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: {
                    'X-CSRFToken': InventoryUtils.getCSRFToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            const data = await InventoryUtils.handleResponse(response);
            
            if (data.success) {
                InventoryUtils.showNotification(`${inventoryType.charAt(0).toUpperCase() + inventoryType.slice(1)} added successfully`);
                this.addTableRow(data.new_item, inventoryType);
                document.querySelector(`#${inventoryType}Popup`).style.display = 'none';
                form.reset();
            } else {
                this.showFormErrors(form, data.errors);
            }
        } catch (error) {
            InventoryUtils.handleError(error);
        } finally {
            InventoryUtils.resetLoading(submitButton);
        }
    }

    static async handleEditForm(form, inventoryType, itemId) {
        const submitButton = form.querySelector('button[type="submit"]');
        InventoryUtils.showLoading(submitButton);

        try {
            const response = await fetch(`/edit_${inventoryType}/${itemId}`, {
                method: 'PUT',
                body: new FormData(form),
                headers: {
                    'X-CSRFToken': InventoryUtils.getCSRFToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            const data = await InventoryUtils.handleResponse(response);
            
            if (data.success) {
                InventoryUtils.showNotification(`${inventoryType.charAt(0).toUpperCase() + inventoryType.slice(1)} updated successfully`);
                this.updateTableRow(itemId, data.updated_item, inventoryType);
                document.querySelector(`#editPopup`).style.display = 'none';
            } else {
                this.showFormErrors(form, data.errors);
            }
        } catch (error) {
            InventoryUtils.handleError(error);
        } finally {
            InventoryUtils.resetLoading(submitButton);
        }
    }

    static async handleDelete(inventoryType, projectName, itemId) {
        const submitButton = document.querySelector('#deletePopup .btn-danger');
        InventoryUtils.showLoading(submitButton);

        try {
            const response = await fetch(`/delete_${inventoryType}/${projectName}/${itemId}`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': InventoryUtils.getCSRFToken(),
                    'Content-Type': 'application/json',
                }
            });

            const data = await InventoryUtils.handleResponse(response);
            
            if (data.success) {
                InventoryUtils.showNotification(`${inventoryType.charAt(0).toUpperCase() + inventoryType.slice(1)} deleted successfully`);
                document.querySelector(`tr[data-id="${itemId}"]`)?.remove();
                document.querySelector(`#deletePopup`).style.display = 'none';
            }
        } catch (error) {
            InventoryUtils.handleError(error);
        } finally {
            InventoryUtils.resetLoading(submitButton);
        }
    }

    static addTableRow(itemData, inventoryType) {
        const table = document.querySelector(`#${inventoryType}Table tbody`);
        if (!table) return;

        const row = document.createElement('tr');
        row.dataset.id = InventoryUtils.escapeHtml(itemData.id);

        // Create cells based on inventory type
        const columns = {
            consumable: ['name', 'product_code', 'pack_size', 'quantity', 'date_recorded', 'expiry_date', 'storage_location'],
            equipment: ['name', 'equip_id', 'serial_num', 'quantity', 'status', 'service_contract_start', 'service_contract_end', 'date_recorded', 'donated_by', 'storage_location'],
            reagent: ['name', 'product_code', 'pack_size', 'quantity', 'date_recorded', 'expiry_date', 'storage_location'],
            sample: ['sample_id', 'sample_type', 'description', 'country', 'volume', 'date_recorded', 'well_id', 'storage_location']
        };

        columns[inventoryType].forEach(col => {
            const cell = document.createElement('td');
            cell.textContent = itemData[col] ? InventoryUtils.escapeHtml(itemData[col]) : '';
            cell.dataset.column = col;
            row.appendChild(cell);
        });

        // Add action cell
        const actionCell = document.createElement('td');
        actionCell.innerHTML = this.getActionButtons(inventoryType, itemData.id);
        row.appendChild(actionCell);

        table.appendChild(row);
    }

    static updateTableRow(itemId, itemData, inventoryType) {
        const row = document.querySelector(`tr[data-id="${InventoryUtils.escapeHtml(itemId)}"]`);
        if (!row) return;

        const columns = {
            consumable: ['name', 'product_code', 'pack_size', 'quantity', 'date_recorded', 'expiry_date', 'storage_location'],
            equipment: ['name', 'equip_id', 'serial_num', 'quantity', 'status', 'service_contract_start', 'service_contract_end', 'date_recorded', 'donated_by', 'storage_location'],
            reagent: ['name', 'product_code', 'pack_size', 'quantity', 'date_recorded', 'expiry_date', 'storage_location'],
            sample: ['sample_id', 'sample_type', 'description', 'country', 'volume', 'date_recorded', 'well_id', 'storage_location']
        };

        columns[inventoryType].forEach((col, index) => {
            const cell = row.cells[index];
            if (cell) cell.textContent = itemData[col] ? InventoryUtils.escapeHtml(itemData[col]) : '';
        });
    }

    static getActionButtons(inventoryType, itemId) {
        // Escape the itemId to prevent XSS
        const escapedId = InventoryUtils.escapeHtml(itemId);
        
        // Create elements safely instead of using innerHTML
        const dropdown = document.createElement('div');
        dropdown.className = 'dropdown';
        
        const button = document.createElement('button');
        button.className = 'dropbtn';
        button.textContent = '...';
        
        const content = document.createElement('div');
        content.className = 'dropdown-content';
        
        // Create links safely
        const actions = [
            { text: 'Retrieve', action: 'Retrieve' },
            { text: 'Return', action: 'Return' },
            { text: 'Edit', action: 'Edit' },
            { text: 'Delete', action: 'Delete' }
        ];
        
        actions.forEach(action => {
            const link = document.createElement('a');
            link.href = '#';
            link.textContent = action.text;
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const modalName = `show${action.action}Popup`;
                if (window.inventoryManager?.modalManager?.[modalName]) {
                    window.inventoryManager.modalManager[modalName](escapedId);
                }
            });
            content.appendChild(link);
        });
        
        dropdown.appendChild(button);
        dropdown.appendChild(content);
        
        return dropdown.outerHTML;
    }

    static showFormErrors(form, errors) {
        form.querySelectorAll('.error-message').forEach(el => el.remove());
        form.querySelectorAll('.has-error').forEach(el => el.classList.remove('has-error'));

        if (!errors) {
            this.showGenericError(form);
            return;
        }

        Object.entries(errors).forEach(([field, message]) => {
            const input = form.querySelector(`[name="${field}"]`);
            if (input) {
                input.classList.add('has-error');
                const errorEl = document.createElement('div');
                errorEl.className = 'error-message';
                errorEl.textContent = message;
                input.closest('.form-group').appendChild(errorEl);
            }
        });
    }

    static showGenericError(form) {
        const errorEl = document.createElement('div');
        errorEl.className = 'error-message mb-4';
        errorEl.textContent = 'An unexpected error occurred';
        form.prepend(errorEl);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.inventoryManager = new InventoryManager();
    
    // Global functions for HTML onclick attributes
    window.showAddPopup = () => inventoryManager.modalManager.showAddPopup();
    window.showEditPopup = (id) => inventoryManager.modalManager.showEditPopup(InventoryUtils.escapeHtml(id));
    window.showRetrievePopup = (id) => inventoryManager.modalManager.showRetrievePopup(InventoryUtils.escapeHtml(id));
    window.showReturnPopup = (id) => inventoryManager.modalManager.showReturnPopup(InventoryUtils.escapeHtml(id));
    window.showDeletePopup = (project, id) => inventoryManager.modalManager.showDeletePopup(
        InventoryUtils.escapeHtml(project),
        InventoryUtils.escapeHtml(id)
    );
    window.deleteItem = () => FormHandler.handleDelete(
        inventoryManager.currentType, 
        InventoryUtils.escapeHtml(inventoryManager.currentProject), 
        InventoryUtils.escapeHtml(inventoryManager.currentItemId)
    );
});
