// consumables.js

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
    storageLocation: document.getElementById('storageLocationFilterInput'),
    storageCondition: document.getElementById('storageConditionFilterInput'),
    vendor: document.getElementById('vendorFilterInput'),
    thresholdValue: document.getElementById('thresholdValueFilterInput')
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
  setupRetrieveReturnForms();
  initialFilter();
  setupTemperatureUnitHandling();
  setupStorageConditionHandling();
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
    submitForm('edit-form', `/edit_consumable/${STATE.currentItemId}`, 'POST', handleEditSuccess);
  });
  
  // Retrieve form
  DOM.forms.retrieve?.addEventListener('submit', (e) => {
    e.preventDefault();
    submitForm('retrieve-form', `/retrieve_consumable/${STATE.currentItemId}`, 'POST', handleRetrieveSuccess);
  });
  
  // Return form
  DOM.forms.return?.addEventListener('submit', (e) => {
    e.preventDefault();
    submitForm('return-form', `/restock_consumable/${STATE.currentItemId}`, 'POST', handleReturnSuccess);
  });
}

function validateTemperatureUnits() {
    const tempInputs = document.querySelectorAll('input[name="oem_temperature"]');
    const tempUnitSelects = document.querySelectorAll('select[name="temperature_unit"]');
    
    let isValid = true;
    
    tempInputs.forEach((input, index) => {
        if (input.value && tempUnitSelects[index]) {
            if (!validateTemperatureValue(input, tempUnitSelects[index].value)) {
                isValid = false;
            }
        }
    });
    
    return isValid;
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
// TEMPERATURE UNIT HANDLING
// ==============================================
function setupTemperatureUnitHandling() {
    // Add change listeners to temperature unit selects
    const tempUnitSelects = document.querySelectorAll('select[name="temperature_unit"]');
    const tempInputs = document.querySelectorAll('input[name="oem_temperature"]');
    
    tempUnitSelects.forEach((select, index) => {
        // Set initial placeholder based on selected unit
        updateTemperaturePlaceholder(select, tempInputs[index]);
        
        select.addEventListener('change', function() {
            updateTemperaturePlaceholder(this, tempInputs[index]);
            validateTemperatureValue(tempInputs[index], this.value);
        });
    });
    
    // Add validation to temperature inputs
    tempInputs.forEach((input, index) => {
        const unitSelect = input.closest('.inputBox').querySelector('select[name="temperature_unit"]');
        input.addEventListener('blur', function() {
            if (unitSelect) {
                validateTemperatureValue(this, unitSelect.value);
            }
        });
    });
}

function updateTemperaturePlaceholder(select, input) {
    const unit = select.value;
    const unitSymbol = unit === 'C' ? '°C' : '°F';
    if (input) {
        input.placeholder = `Temperature in ${unitSymbol}`;
        
        // Update validation constraints
        if (unit === 'C') {
            input.min = -273;
            input.max = 1000;
        } else {
            input.min = -459;
            input.max = 2000;
        }
    }
}

function validateTemperatureValue(input, unit) {
    const value = parseFloat(input.value);
    if (isNaN(value)) return true;
    
    let isValid = true;
    let errorMessage = '';
    
    if (unit === 'C') {
        if (value < -273) {
            isValid = false;
            errorMessage = 'Temperature cannot be below absolute zero (-273°C)';
        } else if (value > 1000) {
            isValid = false;
            errorMessage = 'Temperature seems unusually high for storage';
        }
    } else {
        if (value < -459) {
            isValid = false;
            errorMessage = 'Temperature cannot be below absolute zero (-459°F)';
        } else if (value > 2000) {
            isValid = false;
            errorMessage = 'Temperature seems unusually high for storage';
        }
    }
    
    // Show/hide error message
    let errorElement = input.nextElementSibling;
    if (!errorElement || !errorElement.classList.contains('temperature-error')) {
        errorElement = document.createElement('small');
        errorElement.className = 'temperature-error text-red-500 text-sm mt-1 hidden';
        input.parentNode.appendChild(errorElement);
    }
    
    if (!isValid) {
        errorElement.textContent = errorMessage;
        errorElement.classList.remove('hidden');
        input.classList.add('border-red-500');
    } else {
        errorElement.classList.add('hidden');
        input.classList.remove('border-red-500');
    }
    
    return isValid;
}

// ==============================================
// MODAL FUNCTIONS
// ==============================================
function showModal(id) {
  if (window.showInventoryPopup) {
    window.showInventoryPopup(id);
    document.body.style.overflow = 'hidden';
    return;
  }
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.classList.add('popup-active');
  modal.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
}

function closeModal(id) {
  if (window.hideInventoryPopup) {
    window.hideInventoryPopup(id);
    return;
  }
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.classList.remove('popup-active');
  modal.setAttribute('aria-hidden', 'true');
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
                 'expiry_date', 'storage_location', 'storage_condition',
                 'oem_temperature', 'vendor', 'threshold_value', 'notes'];
  
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

    showLoading(POPUP_IDS.ADD);

  try {
    const formData = new FormData(form);

      // For debugging - log form data
    for (let [key, value] of formData.entries()) {
      console.log(`${key}: ${value}`);
    }
      console.log('Submitting:', Object.fromEntries(formData.entries()));
    const csrfToken = getCSRFToken();
    
    const response = await fetch(url, {
      method,
      headers: {
        'X-CSRFToken': csrfToken,
      },
        body: formData,
        credentials: 'include'
    });
      console.log(method);

      console.log(response)

      // First get response as text to handle both HTML and JSON
      const text = await response.text();

    try{
        // Try to parse as JSON
        const data = JSON.parse(text);
        console.log(data)
    
        if (!response.ok) {
            throw new Error(data.error || `Server responded with status ${response.status}`);
        }
    
        successCallback(data);
    } catch (e) {
        // If not JSON show error page content in console
        console.error('Server returned:', text);
        throw new Error('Server returned an unexpected response. Please check console for details.');
    }
      
  } catch (error) {
    console.error('Error:', error);
    showNotification(error.message || 'An error occurred. Please try again.', 'error');
  } finally {
      hideLoading();
  }
}

// Helper function to get CSRF token
function getCSRFToken() {
  // Try to get from meta tag
  const metaTag = document.querySelector('meta[name="csrf-token"]');
  if (metaTag) return metaTag.content;
  
  // Try to get from cookie as fallback
  const cookieValue = document.cookie
    .split('; ')
    .find(row => row.startsWith('csrftoken='))
    ?.split('=')[1];
    
  if (!cookieValue) {
    console.error('CSRF token not found');
    showNotification('Security token missing. Please refresh the page.', 'error');
    throw new Error('CSRF token not found');
  }
  
  return cookieValue;
}

function handleAddSuccess(data) {
  showNotification('Item added successfully', 'success');
  showLowStockAlert(data);
  closeAddPopup();
  if (data.refresh) {
    setTimeout(() => location.reload(), 1000);
  }
}

function handleEditSuccess(data) {
  updateTableRow(STATE.currentItemId, data);
  showNotification(data.message, 'success');
  showLowStockAlert(data);
  closeEditPopup();

    //const row = document.querySelector(`tr[data-id="${data.id}"]`);
  //if (row) {
    // Update dataset attributes
    //row.dataset.name = data.name;
    //row.dataset.storageLocation = data.storage_location;
    
    // Update visible cells with truncation
    //const nameCell = row.querySelector('td:nth-child(1)');
    //nameCell.setAttribute('data-fulltext', data.name);
    //nameCell.textContent = truncateText(data.name, 20);
    
    //const locationCell = row.querySelector('td:nth-child(7)');
    //locationCell.setAttribute('data-fulltext', data.storage_location);
    //locationCell.textContent = truncateText(data.storage_location, 15);
  //}
}

function handleRetrieveSuccess(data) {
  updateTableRow(STATE.currentItemId, data);
  showNotification('Item retrieved successfully', 'success');
  showLowStockAlert(data);
  closeRetrievePopup();
}

function handleReturnSuccess(data) {
  updateTableRow(STATE.currentItemId, data);
    console.log(data);
  showNotification(data.message, 'success');
  closeReturnPopup();
}

function showLowStockAlert(data) {
  if (data.low_stock_alert) {
    showNotification(
      `Low stock: ${data.name || 'Inventory item'} has ${data.pack_count} packs remaining.`,
      'warning'
    );
  }
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
  setLowStockAppearance(row, data.low_stock);
  
    // Highlight update
    row.classList.add('updated');
    setTimeout(() => row.classList.remove('updated'), 1000);

    // Update dataset attributes
  row.dataset.name = data.name;
  row.dataset.productCode = data.product_code;
  row.dataset.itemsLeftInPack = data.items_left_in_pack;
  row.dataset.itemsPerPack = data.items_per_pack;
  row.dataset.packCount = data.pack_count;
  //row.dataset.dateCreated = data.date_created;
  row.dataset.expiryDate = data.expiry_date;
  row.dataset.storageLocation = data.storage_location;
  row.dataset.coldStorage = data.cold_storage;
  row.dataset.optimalTemp = data.optimal_temp;
  row.dataset.vendor = data.vendor;
  row.dataset.thresholdValue = data.threshold_value;
  row.dataset.notes = data.notes;

  // Update visible cells
  const cells = row.querySelectorAll('td');
  if (cells.length > 7) {
    cells[0].textContent = escapeHtml(data.name) || '';
    cells[1].textContent = escapeHtml(data.product_code) || '';
    cells[2].textContent = data.items_left_in_pack || 0;
    cells[3].textContent = data.items_per_pack || 0;
    cells[4].textContent = data.pack_count || 0;
    //cells[5].textContent = data.date_created || '';
    cells[6].textContent = data.expiry_date || '';
    cells[7].textContent = escapeHtml(data.storage_location) || '';
    cells[8].textContent = escapeHtml(data.cold_storage) || '';
    cells[9].textContent = data.optimal_temp || 0;
    cells[10].textContent = escapeHtml(data.vendor) || '';
    cells[11].textContent = data.threshold || 0;
    cells[12].textContent = escapeHtml(data.notes) || '';
  }
}

function setLowStockAppearance(row, isLowStock) {
  row.classList.toggle('low-stock-row', Boolean(isLowStock));
  const cells = row.querySelectorAll('td');
  cells[0]?.classList.toggle('low-stock-indicator', Boolean(isLowStock));
  cells[4]?.classList.toggle('low-stock-indicator', Boolean(isLowStock));
}

// Helper function to escape HTML
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Improved truncate function
function truncateText(text, maxLength) {
  if (!text) return '';
  return text.length > maxLength 
    ? text.substring(0, maxLength - 3) + '...' 
    : text;
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
    storageLocation: DOM.filterInputs.storageLocation?.value.toLowerCase() || '',
    storageCondition: DOM.filterInputs.storageCondition?.value.toLowerCase() || '',
    optimalTemperature: DOM.filterInputs.optimalTemperature?.value ? parseInt(DOM.filterInputs.optimalTemperature.value) : null,
    temperatureUnit: document.getElementById('temperatureUnitFilter')?.value || '',
    vendor: DOM.filterInputs.vendor?.value.toLowerCase() || '',
    thresholdValue: DOM.filterInputs.thresholdValue?.value ? parseInt(DOM.filterInputs.thresholdValue.value) : null
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
    quantity: parseInt(row.dataset.packCount) || 0,
    dateCreated: row.dataset.dateCreated || '',
    expiryDate: row.dataset.expiryDate || '',
    storageLocation: (row.dataset.storageLocation || '').toLowerCase(),
    storageCondition: (row.dataset.coldStorage || '').toLowerCase(),
    optimalTemperature: parseInt(row.dataset.optimalTemp) || 0,
    temperatureUnit: row.dataset.temperatureUnit || 'C',
    vendor: (row.dataset.vendor || '').toLowerCase(),
    thresholdValue: parseInt(row.dataset.threshold) || 0
  };
  
  return (
    rowData.name.includes(filters.name) &&
    rowData.productCode.includes(filters.productCode) &&
    rowData.quantity >= filters.minQuantity &&
    rowData.quantity <= filters.maxQuantity &&
    isDateInRange(rowData.dateCreated, filters.minDateCreated, filters.maxDateCreated) &&
    isDateInRange(rowData.expiryDate, filters.minDateExpired, filters.maxDateExpired) &&
    rowData.storageLocation.includes(filters.storageLocation) &&
    (filters.storageCondition === '' || rowData.storageCondition.includes(filters.storageCondition)) &&
    (filters.optimalTemperature === null || rowData.optimalTemperature === filters.optimalTemperature) &&
    (filters.temperatureUnit === '' || rowData.temperatureUnit === filters.temperatureUnit) &&
    rowData.vendor.includes(filters.vendor) &&
    (filters.thresholdValue === null || rowData.thresholdValue === filters.thresholdValue)
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

    if (columnNum === '5') { // Quantity column
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
  return columnNum === '5' ? parseFloat(value) || 0 : value.toLowerCase();
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
  const options = {
    text: message,
    duration: 5000,
    close: true,
    gravity: "top", // top or bottom
    position: "right", // left, center or right
    stopOnFocus: true, // Prevents dismissing when window is focused
    className: `custom-toast ${type}-toast`,
  };

  Toastify(options).showToast();
}

function validateExpiryDate(input) {
  const errorElement = document.getElementById('date-error');
  const selectedDate = new Date(input.value);
  const today = new Date();
  today.setHours(0, 0, 0, 0); // Reset time part for accurate comparison

  if (selectedDate < today) {
    errorElement.classList.remove('hidden');
    input.setCustomValidity('Expiry date must be in the future');
  } else {
    errorElement.classList.add('hidden');
    input.setCustomValidity('');
  }
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

// Validate positive integer input
function validatePositiveInteger(input) {
  // Remove any non-digit characters
  input.value = input.value.replace(/[^0-9]/g, '');
  
  // Ensure minimum value of 1
  if (input.value && parseInt(input.value) < 1) {
    input.value = '1';
  }
  
  // Remove leading zeros
  if (input.value.length > 1 && input.value.startsWith('0')) {
    input.value = input.value.replace(/^0+/, '');
  }
}

// Add event listeners to forms
function setupRetrieveReturnForms() {
  const editPackSizeInput = document.getElementById('pack_size');
  const editQuantityInput = document.getElementById('quantity');
  const editThresholdInput = document.getElementById('threshold_value');
  const retrieveInput = document.getElementById('retrieveFilterInput');
  const returnInput = document.getElementById('returnFilterInput');


  if (editPackSizeInput) {
    editPackSizeInput.addEventListener('change', function() {
      if (!this.value || parseInt(this.value) < 1) {
        this.value = '1';
      }
    });
  }

  if (editQuantityInput) {
    editQuantityInput.addEventListener('change', function() {
      if (!this.value || parseInt(this.value) < 1) {
        this.value = '1';
      }
    });
  }
  if (editThresholdInput) {
    editThresholdInput.addEventListener('change', function() {
      if (!this.value || parseInt(this.value) < 1) {
        this.value = '1';
      }
    });
  }

  if (retrieveInput) {
    retrieveInput.addEventListener('change', function() {
      if (!this.value || parseInt(this.value) < 1) {
        this.value = '1';
      }
    });
  }
  
  if (returnInput) {
    returnInput.addEventListener('change', function() {
      if (!this.value || parseInt(this.value) < 1) {
        this.value = '1';
      }
    });
  }
}

function setupStorageConditionHandling() {
    const storageConditionSelects = document.querySelectorAll('select[name="storageConditionOptions"]');
    
    storageConditionSelects.forEach(select => {
        select.addEventListener('change', function() {
            const otherField = this.closest('.inputBox').querySelector('#otherField');
            if (otherField) {
                otherField.style.display = this.value === 'other' ? 'block' : 'none';
            }
        });
        
        // Trigger change on page load
        select.dispatchEvent(new Event('change'));
    });
}

function initialFilter() {
  // Apply any initial filters if needed
  filterTable();
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initConsumablesManager);
