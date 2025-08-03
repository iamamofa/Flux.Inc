// consumables.js - Refactored to match equipment_.js patterns

// ==============================================
// CONSTANTS AND CONFIGURATION
// ==============================================
const POPUP_IDS = {
  ADD: 'addPopup',
  EDIT: 'editPopup',
  RETRIEVE: 'retrievePopup',
  RETURN: 'returnPopup',
  DELETE: 'deletePopup'
};

const POPUP_CONTAINERS = {
  ADD: '.popup-container1',
  EDIT: '.popup-container2',
  RETRIEVE: '.popup-container3',
  RETURN: '.popup-container4',
  DELETE: '.popup-container5'
};

// Get CSRF token from meta tag
const CSRF_TOKEN = document.querySelector('meta[name="csrf-token"]')?.content || '';

// Global state
const STATE = {
  currentItemId: null,
  currentProject: null,
  activeSort: {
    column: null,
    direction: 'asc'
  }
};

// DOM Elements
const DOM = {
  table: document.getElementById('consumablesTable'),
  forms: {
    add: document.getElementById('consumable-form'),
    edit: document.getElementById('edit-form'),
    retrieve: document.getElementById('retrieve-form'),
    return: document.getElementById('return-form')
  },
  filterInputs: {
    name: document.getElementById('nameFilterInput'),
    productCode: document.getElementById('productCodeFilterInput'),
    minQuantity: document.getElementById('minQuantityFilterInput'),
    maxQuantity: document.getElementById('maxQuantityFilterInput'),
    minDateCreated: document.getElementById('minDateCreatedFilterInput'),
    maxDateCreated: document.getElementById('maxDateCreatedFilterInput'),
    minDateExpired: document.getElementById('minDateExpiredFilterInput'),
    maxDateExpired: document.getElementById('maxDateExpiredFilterInput'),
    storageLocation: document.getElementById('storageLocationFilterInput')
  },
  buttons: {
    resetFilters: document.getElementById('resetButton'),
    confirmDelete: document.getElementById('confirmDeleteBtn')
  },
  notificationContainer: document.getElementById('notification-container')
};

// ==============================================
// INITIALIZATION
// ==============================================
function initConsumablesManager() {
  setupPopups();
  setupEventListeners();
  initialFilter();
}

// ==============================================
// EVENT HANDLERS SETUP
// ==============================================
function setupEventListeners() {
  // Modal triggers
  document.getElementById('showAddPopupBtn')?.addEventListener('click', showAddPopup);
  
  // Table interactions
  DOM.table?.addEventListener('click', handleTableClick);
  
  // Filter inputs
  Object.values(DOM.filterInputs).forEach(input => {
    if (input) input.addEventListener('input', debounce(filterTable, 300));
  });
  
  // Sorting
  document.getElementById('sortColumnDropdown')?.addEventListener('change', sortTableByColumn);
  
  // Reset filters
  DOM.buttons.resetFilters?.addEventListener('click', resetFilters);
  
  // Form submissions
  setupFormHandlers();
  
  // Delete confirmation
  DOM.buttons.confirmDelete?.addEventListener('click', handleDeleteConfirm);

  // Add dropdown toggle logic
  setupDropdowns();
}

function setupDropdowns() {
  // Toggle dropdown on click
  document.querySelectorAll('.dropdown-trigger').forEach(trigger => {
    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      trigger.closest('.dropdown').classList.toggle('active');
    });
  });

  // Close when clicking outside
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.dropdown')) {
      document.querySelectorAll('.dropdown').forEach(dropdown => {
        dropdown.classList.remove('active');
      });
    }
  });
}

function setupPopups() {
  Object.entries(POPUP_CONTAINERS).forEach(([key, containerClass]) => {
    const popupId = POPUP_IDS[key];
    handlePopup(containerClass, popupId);
  });
}

function handlePopup(containerClass, popupId) {
  const container = document.querySelector(containerClass);
  if (!container) return;

  container.addEventListener("click", (event) => {
    if (event.target === container) {
      closeModal(popupId);
    }
  });
}

function setupFormHandlers() {
  // Add form
  DOM.forms.add?.addEventListener('submit', (e) => {
    e.preventDefault();
    submitForm('consumable-form', DOM.forms.add.action, 'POST', handleAddSuccess);
  });
  
  // Edit form
  DOM.forms.edit?.addEventListener('submit', (e) => {
    e.preventDefault();
    submitForm('edit-form', `/edit_consumable/${STATE.currentItemId}`, 'PUT', handleEditSuccess);
  });
  
  // Retrieve form
  DOM.forms.retrieve?.addEventListener('submit', (e) => {
    e.preventDefault();
    submitForm('retrieve-form', `/retrieve_consumable/${STATE.currentItemId}`, 'PUT', handleRetrieveSuccess);
  });
  
  // Return form
  DOM.forms.return?.addEventListener('submit', (e) => {
    e.preventDefault();
    submitForm('return-form', `/return_consumable/${STATE.currentItemId}`, 'PUT', handleReturnSuccess);
  });
}

function handleTableClick(e) {
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
}

// ==============================================
// MODAL FUNCTIONS
// ==============================================
function showModal(id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.style.display = 'flex';
  document.body.style.overflow = 'hidden';
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.style.display = 'none';
  document.body.style.overflow = '';
}

function showAddPopup() {
  showModal(POPUP_IDS.ADD);
}

function closeAddPopup() {
  closeModal(POPUP_IDS.ADD);
  DOM.forms.add?.reset();
}

function showEditPopup(id) {
  STATE.currentItemId = id;
  showModal(POPUP_IDS.EDIT);
  loadItemData();
}

function closeEditPopup() {
  closeModal(POPUP_IDS.EDIT);
}

function showRetrievePopup(id) {
  STATE.currentItemId = id;
  showModal(POPUP_IDS.RETRIEVE);
}

function closeRetrievePopup() {
  closeModal(POPUP_IDS.RETRIEVE);
  DOM.forms.retrieve?.reset();
}

function showReturnPopup(id) {
  STATE.currentItemId = id;
  showModal(POPUP_IDS.RETURN);
}

function closeReturnPopup() {
  closeModal(POPUP_IDS.RETURN);
  DOM.forms.return?.reset();
}

function showDeletePopup(project, id) {
  STATE.currentItemId = id;
  STATE.currentProject = project;
  showModal(POPUP_IDS.DELETE);
}

function closeDeletePopup() {
  closeModal(POPUP_IDS.DELETE);
}

// ==============================================
// DATA HANDLING FUNCTIONS
// ==============================================
async function loadItemData() {
  if (!STATE.currentItemId) return;
  
  showLoading(POPUP_IDS.EDIT);
  
  try {
    const response = await fetch(`/get_consumable_info/${STATE.currentItemId}`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
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
async function submitForm(formId, url, method, successCallback) {
  const form = document.getElementById(formId);
  if (!form) return;

  try {
    const formData = new FormData(form);

      // Debug error
      for (let [key, value] of formData.entries()) {
          console.log(`${key}: ${value}`);
      }

    const response = await fetch(url, {
      method,
      headers: {
        'X-CSRFToken': CSRF_TOKEN,
        // 'Content-Type': 'application/json', // Let browser set it automatically
      },
      // body: JSON.stringify(Object.fromEntries(formData)),
        body: formData, // Send forData directly instead of as JSON
    });

    if (!response.ok) {
        throw new Error(`Network response was not ok:
            ${response.status} ${response.statusText}`);
    }
    
    const data = await response.json();
    successCallback(data);
  } catch (error) {
    console.error('Error:', error);
    showNotification(error.message || 'An error occurred. Please try again.', 'error');
  }
}

function handleAddSuccess(data) {
  showNotification('Item added successfully', 'success');
  closeAddPopup();
  if (data.refresh) {
    setTimeout(() => location.reload(), 1000);
  }
}

function handleEditSuccess(data) {
  updateTableRow(STATE.currentItemId, data);
  showNotification('Item updated successfully', 'success');
  closeEditPopup();

    const row = document.querySelector(`tr[data-id="${data.id}"]`);
  if (row) {
    // Update dataset attributes
    row.dataset.name = data.name;
    row.dataset.storageLocation = data.storage_location;
    
    // Update visible cells with truncation
    const nameCell = row.querySelector('td:nth-child(1)');
    nameCell.setAttribute('data-fulltext', data.name);
    nameCell.textContent = truncateText(data.name, 20);
    
    const locationCell = row.querySelector('td:nth-child(7)');
    locationCell.setAttribute('data-fulltext', data.storage_location);
    locationCell.textContent = truncateText(data.storage_location, 15);
  }
}

function handleRetrieveSuccess(data) {
  updateTableRow(STATE.currentItemId, data);
  showNotification('Item retrieved successfully', 'success');
  closeRetrievePopup();
}

function handleReturnSuccess(data) {
  updateTableRow(STATE.currentItemId, data);
  showNotification('Item returned successfully', 'success');
  closeReturnPopup();
}

async function handleDeleteConfirm() {
  if (!STATE.currentItemId || !STATE.currentProject) return;

  showLoading(POPUP_IDS.DELETE);

  try {
    const response = await fetch(`/delete_consumable/${STATE.currentProject}/${STATE.currentItemId}`, {
      method: 'DELETE',
      headers: {
        'X-CSRFToken': CSRF_TOKEN,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) throw new Error('Failed to delete item');
    
    const data = await response.json();
    showNotification('Item deleted successfully', 'success');
    removeTableRow(STATE.currentItemId);
    closeDeletePopup();
  } catch (error) {
    console.error('Delete error:', error);
    showNotification(error.message || 'Failed to delete item', 'error');
  } finally {
    hideLoading();
  }
}

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

function removeTableRow(id) {
  const row = DOM.table?.querySelector(`tr[data-id="${id}"]`);
  if (row) {
    row.classList.add('fade-out');
    setTimeout(() => row.remove(), 300);
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

      const nameCell = row.querySelector('td:nth-child(1)');
    if (nameCell) {
      const fullName = row.dataset.name || '';
      nameCell.setAttribute('data-fulltext', fullName);
      nameCell.textContent = truncateText(fullName, 20); // Truncate to 20 chars
    }

    const locationCell = row.querySelector('td:nth-child(7)');
    if (locationCell) {
      const fullLocation = row.dataset.storageLocation || '';
      locationCell.setAttribute('data-fulltext', fullLocation);
      locationCell.textContent = truncateText(fullLocation, 15);
    }
  });
}

function truncateText(text, maxLength) {
  return text.length > maxLength 
    ? text.substring(0, maxLength - 3) + '...' 
    : text;
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

function resetFilters() {
  // Reset all filter inputs
  Object.values(DOM.filterInputs).forEach(input => {
    if (input) input.value = '';
  });

  // Reset sorting dropdown
  document.getElementById('sortColumnDropdown').value = '0';

  // Reapply filters (which will now show all rows)
  filterTable();
}

function sortTableByColumn() {
  const dropdown = document.getElementById('sortColumnDropdown');
  if (!dropdown) return;

  const columnNum = dropdown.value;
  if (!columnNum || columnNum === '0') {
    resetFilters();
    return;
  }

  const tbody = DOM.table?.querySelector('tbody');
  if (!tbody) return;

  const rows = Array.from(tbody.querySelectorAll('tr[data-id]'));
  if (rows.length === 0) return;

  // Toggle sort direction if clicking same column
  if (STATE.activeSort.column === columnNum) {
    STATE.activeSort.direction = STATE.activeSort.direction === 'asc' ? 'desc' : 'asc';
  } else {
    STATE.activeSort.column = columnNum;
    STATE.activeSort.direction = 'asc';
  }

  rows.sort((a, b) => {
    const aValue = getColumnValue(a, columnNum);
    const bValue = getColumnValue(b, columnNum);

    if (columnNum === '4') { // Quantity column
      return STATE.activeSort.direction === 'asc' 
        ? aValue - bValue 
        : bValue - aValue;
    }
  
    return STATE.activeSort.direction === 'asc' 
      ? aValue.localeCompare(bValue) 
      : bValue.localeCompare(aValue);
  });

  // Reattach sorted rows
  rows.forEach(row => tbody.appendChild(row));
}

function getColumnValue(row, columnNum) {
  const cell = row.querySelector(`td:nth-child(${columnNum})`);
  if (!cell) return '';
  const value = cell.textContent.trim();
  return columnNum === '4' ? parseFloat(value) || 0 : value.toLowerCase();
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

function showLoading(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;

  const loader = document.createElement('div');
  loader.className = 'loading-overlay';
  loader.innerHTML = `
    <div class="spinner"></div>
    <p>Processing...</p>
  `;
  container.appendChild(loader);
  container.style.position = 'relative';
}

function hideLoading() {
  const loaders = document.querySelectorAll('.loading-overlay');
  loaders.forEach(loader => {
    loader.parentNode?.removeChild(loader);
  });
}

function showNotification(message, type = 'success') {
  if (!DOM.notificationContainer) return;

  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  notification.textContent = message;
  DOM.notificationContainer.appendChild(notification);

  setTimeout(() => {
    notification.classList.add('fade-out');
    setTimeout(() => notification.remove(), 500);
  }, 3000);
}

function isDateInRange(dateString, minDateString, maxDateString) {
  if (!dateString) return true;

  try {
    const date = new Date(dateString);
    const minDate = minDateString ? new Date(minDateString) : new Date(0);
    const maxDate = maxDateString ? new Date(maxDateString) : new Date(8640000000000000);
  
    return date >= minDate && date <= maxDate;
  } catch (e) {
    console.error('Date parsing error:', e);
    return true;
  }
}

function initialFilter() {
  // Apply any initial filters if needed
  filterTable();
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initConsumablesManager);
