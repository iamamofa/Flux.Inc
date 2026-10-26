// equipment.js - Improved Equipment Management Script

function getCSRFToken(form) {
  const formToken = form?.querySelector('[name="csrfmiddlewaretoken"]')?.value
    || document.querySelector('[name="csrfmiddlewaretoken"]')?.value
    || '';
  if (formToken) return formToken.trim();

  const cookie = document.cookie
    .split('; ')
    .find((entry) => entry.startsWith('csrftoken='));
  return cookie ? decodeURIComponent(cookie.slice('csrftoken='.length)) : '';
}

// Constants
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

// Global variables
let currentItemId = null;
let currentProject = null;

// DOM Elements
const elements = {
  table: document.getElementById('equipmentTable'),
  nameFilter: document.getElementById('nameFilterInput'),
  serialNumFilter: document.getElementById('serialNumFilterInput'),
  minQuantityFilter: document.getElementById('minQuantityFilterInput'),
  maxQuantityFilter: document.getElementById('maxQuantityFilterInput'),
  minServiceStartFilter: document.getElementById('minServiceContractStartFilterInput'),
  maxServiceStartFilter: document.getElementById('maxServiceContractStartFilterInput'),
  minServiceEndFilter: document.getElementById('minServiceContractEndFilterInput'),
  maxServiceEndFilter: document.getElementById('maxServiceContractEndFilterInput'),
  storageLocationFilter: document.getElementById('storageLocationFilterInput'),
  sortDropdown: document.getElementById('sortColumnDropdown'),
  resetButton: document.getElementById('resetButton'),
  addItemBtn: document.getElementById('addItemBtn')
};

// Initialize the module
function initEquipmentManager() {
  // Setup popup handlers
  setupPopups();
  
  // Setup event listeners
  setupEventListeners();
  
  // Initial table setup
  filterTable();
}

// Setup all popup handlers
function setupPopups() {
  Object.entries(POPUP_CONTAINERS).forEach(([key, containerClass]) => {
    const popupId = POPUP_IDS[key];
    handlePopup(containerClass, popupId);
  });
}

// Generic popup handler
function handlePopup(containerClass, popupId) {
  const container = document.querySelector(containerClass);
  if (!container) return;

  container.addEventListener("click", (event) => {
    if (event.target === container) {
      setPopupVisibility(popupId, false);
    }
  });
}

// Setup all event listeners
function setupEventListeners() {
  // Filter inputs
  elements.nameFilter.addEventListener('input', filterTable);
  elements.serialNumFilter.addEventListener('input', filterTable);
  elements.minQuantityFilter.addEventListener('input', filterTable);
  elements.maxQuantityFilter.addEventListener('input', filterTable);
  elements.minServiceStartFilter.addEventListener('change', filterTableByDate);
  elements.maxServiceStartFilter.addEventListener('change', filterTableByDate);
  elements.minServiceEndFilter.addEventListener('change', filterTableByDate);
  elements.maxServiceEndFilter.addEventListener('change', filterTableByDate);
  elements.storageLocationFilter.addEventListener('input', filterTable);
  
  // Sort dropdown
  elements.sortDropdown.addEventListener('change', sortTableByColumn);
  
  // Reset button
  elements.resetButton.addEventListener('click', resetFilters);
  
  // Add item button
  if (elements.addItemBtn) {
    elements.addItemBtn.addEventListener('click', showAddPopup);
  }
  
  // Form submissions
  setupFormSubmissions();

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

// Setup form submissions
function setupFormSubmissions() {
  // Add form
  const addForm = document.getElementById('equipment-form');
  if (addForm) {
    addForm.addEventListener('submit', (event) => {
      event.preventDefault();
      submitForm('equipment-form', addForm.action, 'POST', handleAddSuccess);
    });
  }
  
  // Edit form
  const editForm = document.getElementById('edit-form');
  if (editForm) {
    editForm.addEventListener('submit', (event) => {
      event.preventDefault();
      submitForm('edit-form', `/edit_equipment/${currentItemId}`, 'PUT', handleEditSuccess);
    });
  }
  
  // Retrieve form
  const retrieveForm = document.getElementById('retrieve-form');
  if (retrieveForm) {
    retrieveForm.addEventListener('submit', (event) => {
      event.preventDefault();
      submitForm('retrieve-form', `/retrieve_equipment/${currentItemId}`, 'PUT', handleRetrieveSuccess);
    });
  }
  
  // Return form
  const returnForm = document.getElementById('return-form');
  if (returnForm) {
    returnForm.addEventListener('submit', (event) => {
      event.preventDefault();
      submitForm('return-form', `/return_equipment/${currentItemId}`, 'PUT', handleReturnSuccess);
    });
  }
}

// Generic form submission handler
async function submitForm(formId, url, method, successCallback) {
  const form = document.getElementById(formId);
  if (!form) return;

  try {
    const csrfToken = getCSRFToken(form);
    if (!csrfToken) {
      throw new Error('CSRF token is missing. Reload the equipment page and try again.');
    }
    const formData = new FormData(form);
    const isFormPost = method.toUpperCase() === 'POST';
    const response = await fetch(url, {
      method,
      headers: {
        'X-CSRFToken': csrfToken,
        ...(isFormPost ? {} : { 'Content-Type': 'application/json' }),
      },
      body: isFormPost
        ? formData
        : JSON.stringify(Object.fromEntries(formData)),
    });

    const responseText = await response.text();
    let data = {};
    if (responseText) {
      try {
        data = JSON.parse(responseText);
      } catch {
        data = { error: responseText };
      }
    }
    if (!response.ok) {
      const formErrors = Object.entries(data.errors || {})
        .flatMap(([field, errors]) => errors.map((error) => (
          `${field.replace(/_/g, ' ')}: ${error.message}`
        )));
      throw new Error(
        formErrors.join(' ') || data.error || `Request failed (${response.status}).`
      );
    }

    successCallback(data);
  } catch (error) {
    console.error('Error:', error);
    showNotification(error.message || 'An error occurred. Please try again.', 'error');
  }
}

// Show notification to user
function showNotification(message, type = 'success') {
  const container = document.getElementById('notification-container');
  if (!container) {
    window.alert(message);
    return;
  }

  const notification = document.createElement('div');
  notification.className = `notification ${type} show`;
  notification.setAttribute('role', type === 'error' ? 'alert' : 'status');
  notification.textContent = message;
  container.appendChild(notification);
  window.setTimeout(() => notification.remove(), 7000);
}

// Popup functions
function setPopupVisibility(id, isVisible) {
  const popupHandler = isVisible ? window.showInventoryPopup : window.hideInventoryPopup;
  if (popupHandler) {
    popupHandler(id);
    return;
  }
  const popup = document.getElementById(id);
  if (!popup) return;
  popup.classList.toggle('popup-active', isVisible);
  popup.setAttribute('aria-hidden', String(!isVisible));
  document.body.style.overflow = isVisible ? 'hidden' : '';
}

function showAddPopup() {
  setPopupVisibility(POPUP_IDS.ADD, true);
}

function closeAddPopup() {
  setPopupVisibility(POPUP_IDS.ADD, false);
}

function showEditPopup(id) {
  currentItemId = id;
  setPopupVisibility(POPUP_IDS.EDIT, true);
  getItemInfo();
}

function closeEditPopup() {
  setPopupVisibility(POPUP_IDS.EDIT, false);
}

function showRetrievePopup(id) {
  currentItemId = id;
  setPopupVisibility(POPUP_IDS.RETRIEVE, true);
}

function closeRetrievePopup() {
  setPopupVisibility(POPUP_IDS.RETRIEVE, false);
}

function showReturnPopup(id) {
  currentItemId = id;
  setPopupVisibility(POPUP_IDS.RETURN, true);
}

function closeReturnPopup() {
  setPopupVisibility(POPUP_IDS.RETURN, false);
}

function showDeletePopup(projectName, id) {
  currentItemId = id;
  currentProject = projectName;
  setPopupVisibility(POPUP_IDS.DELETE, true);
}

function closeDeletePopup() {
  setPopupVisibility(POPUP_IDS.DELETE, false);
}

// Get item information for editing
async function getItemInfo() {
  try {
    const response = await fetch(`/get_equipment_info/${currentItemId}`, {
      method: 'GET',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    });

    if (!response.ok) throw new Error('Network response was not ok');
    
    const data = await response.json();
    const form = document.getElementById('edit-form');

    // Update form fields
    form.elements.name.value = data.name;
    form.elements.equip_id.value = data.equip_id;
    form.elements.serial_num.value = data.serial_num;
    form.elements.quantity.value = data.quantity;
    form.elements.status.value = data.status;
    form.elements.service_contract_start.value = data.service_contract_start;
    form.elements.service_contract_end.value = data.service_contract_end;
    form.elements.donated_by.value = data.donated_by;
    form.elements.storage_location.value = data.storage_location;
  } catch (error) {
    console.error('Error retrieving equipment information:', error);
    showNotification('Failed to load equipment details', 'error');
  }
}

// Delete item
async function deleteItem() {
  try {
    const csrfToken = getCSRFToken(document.getElementById('delete-form'));
    if (!csrfToken) {
      throw new Error('CSRF token is missing. Reload the equipment page and try again.');
    }
    const response = await fetch(`/delete_equipment/${currentProject}/${currentItemId}`, {
      method: 'DELETE',
      headers: {
        'X-CSRFToken': getCSRFToken(document.getElementById('delete-form')),
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) throw new Error('Network response was not ok');
    
    removeTableRow(currentItemId);
    showNotification('Equipment deleted successfully', 'success');
    closeDeletePopup();
  } catch (error) {
    console.error('Error deleting equipment:', error);
    showNotification('Failed to delete equipment', 'error');
    closeDeletePopup();
  }
}

// Remove table row
function removeTableRow(id) {
  const row = elements.table.querySelector(`tr[data-id="${id}"]`);
  if (row) row.remove();
}

// Refresh table row with new data
function refreshTableRow(id, data) {
  const row = elements.table.querySelector(`tr[data-id="${id}"]`);
  if (!row) return;

  const cells = row.querySelectorAll('td');
  if (cells.length < 10) return;

  cells[0].setAttribute('data-fulltext', data.name);
  cells[0].textContent = truncateText(data.name, 20);
  cells[1].textContent = data.equip_id;
  cells[2].textContent = data.serial_num;
  cells[3].textContent = data.quantity;
  cells[4].setAttribute('data-fulltext', data.status);
  cells[4].textContent = data.status;
  cells[5].textContent = data.service_contract_start;
  cells[6].textContent = data.service_contract_end;
  cells[8].setAttribute('data-fulltext', data.donated_by);
  cells[8].textContent = data.donated_by;
  cells[9].setAttribute('data-fulltext', data.storage_location);
  cells[9].textContent = truncateText(data.storage_location, 15);
}

function truncateText(text, maxLength) {
  return text.length > maxLength 
    ? text.substring(0, maxLength - 3) + '...' 
    : text;
}

// Success handlers
function handleAddSuccess(data) {
  showNotification('Equipment added successfully', 'success');
  closeAddPopup();
  // Optionally refresh the entire table or add the new row
  location.reload(); // Simple solution - consider a better approach
}

function handleEditSuccess(data) {
  showNotification('Equipment updated successfully', 'success');
  refreshTableRow(currentItemId, data);
  closeEditPopup();
}

function handleRetrieveSuccess(data) {
  showNotification('Equipment retrieved successfully', 'success');
  refreshTableRow(currentItemId, data);
  closeRetrievePopup();
  document.getElementById('retrieveFilterInput').value = '';
}

function handleReturnSuccess(data) {
  showNotification('Equipment returned successfully', 'success');
  refreshTableRow(currentItemId, data);
  closeReturnPopup();
  document.getElementById('returnFilterInput').value = '';
}

// Filter functions
function filterTable() {
  const nameFilterValue = elements.nameFilter.value.toLowerCase();
  const serialNumFilterValue = elements.serialNumFilter.value.toLowerCase();
  const minQuantityFilterValue = elements.minQuantityFilter.value !== '' ? parseInt(elements.minQuantityFilter.value) : 0;
  const maxQuantityFilterValue = elements.maxQuantityFilter.value !== '' ? parseInt(elements.maxQuantityFilter.value) : Infinity;
  const minServiceStartFilterValue = elements.minServiceStartFilter.value || '1900-01-01';
  const maxServiceStartFilterValue = elements.maxServiceStartFilter.value || '9999-12-31';
  const minServiceEndFilterValue = elements.minServiceEndFilter.value || '1900-01-01';
  const maxServiceEndFilterValue = elements.maxServiceEndFilter.value || '9999-12-31';
  const storageLocationFilterValue = elements.storageLocationFilter.value.toLowerCase();

  const tableRows = elements.table.querySelectorAll('tbody tr[data-id]');

  tableRows.forEach((row) => {
      const cells = row.querySelectorAll('td');

      // Skip if not enough cells
      if (cells.length < 10) {
          console.warn('Row missing required cells:', row);
          row.style.display = 'none';
          return;
      }

      // Now access cells by their correct positions
      const name = cells[0].textContent.toLowerCase();
      const serialNum = cells[2].textContent.toLowerCase(); // 3rd column (index 2)
        const quantity = parseInt(cells[3].textContent) || 0; // 4th column (index 3)
        const startDate = cells[5].textContent; // 6th column (index 5)
        const endDate = cells[6].textContent;   // 7th column (index 6)
        const storageLocation = cells[9].textContent.toLowerCase(); // 10th column (index 9)

        const matchesFilters = (
            name.includes(nameFilterValue) &&
            serialNum.includes(serialNumFilterValue) &&
            quantity >= minQuantityFilterValue &&
            quantity <= maxQuantityFilterValue &&
            isDateInRange(startDate, minServiceStartFilterValue, maxServiceStartFilterValue) &&
            isDateInRange(endDate, minServiceEndFilterValue, maxServiceEndFilterValue) &&
            storageLocation.includes(storageLocationFilterValue)
        );

        row.style.display = matchesFilters ? '' : 'none';
    });
}
function filterTableByDate() {
  filterTable();
}

function isDateInRange(date, minDate, maxDate) {
  if (!date || !minDate || !maxDate) return true;

  const currentDate = new Date(date);
  const min = new Date(minDate);
  const max = new Date(maxDate);

  return currentDate >= min && currentDate <= max;
}

// Reset filters
function resetFilters() {
  elements.nameFilter.value = '';
  elements.serialNumFilter.value = '';
  elements.minQuantityFilter.value = '';
  elements.maxQuantityFilter.value = '';
  elements.minServiceStartFilter.value = '';
  elements.maxServiceStartFilter.value = '';
  elements.minServiceEndFilter.value = '';
  elements.maxServiceEndFilter.value = '';
  elements.storageLocationFilter.value = '';

  filterTable();
}

// Sort table
function sortTableByColumn() {
  const columnNum = elements.sortDropdown.value;
  if (columnNum === '0') {
    location.reload();
    return;
  }

  const rows = Array.from(elements.table.querySelectorAll('tbody tr[data-id]'));
  const tbody = elements.table.querySelector('tbody');
  
  rows.sort((row1, row2) => {
    const value1 = getColumnValue(row1, columnNum);
    const value2 = getColumnValue(row2, columnNum);

    if (columnNum === '4') {
      return value1 - value2;
    }

    return value1.localeCompare(value2);
  });

  // Reorder the rows in the table
  rows.forEach(row => tbody.appendChild(row));
}

function getColumnValue(row, columnNum) {
  const column = row.querySelector(`td:nth-child(${columnNum})`);
  if (!column) return '';

  const value = column.textContent.trim();
  return columnNum === '4' ? parseFloat(value) : value.toLowerCase();
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initEquipmentManager);
