// equipment.js - Improved Equipment Management Script

// Get CSRF token from meta tag (NEW: More reliable than template variable)
const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';

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
      document.getElementById(popupId).style.display = 'none';
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
    const formData = new FormData(form);
    const response = await fetch(url, {
      method,
      headers: {
        'X-CSRFToken': csrfToken,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(Object.fromEntries(formData)),
    });

    if (!response.ok) throw new Error('Network response was not ok');
    
    const data = await response.json();
    successCallback(data);
  } catch (error) {
    console.error('Error:', error);
    showNotification('An error occurred. Please try again.', 'error');
  }
}

// Show notification to user
function showNotification(message, type = 'success') {
  // Implement your notification system here
  console.log(`${type}: ${message}`);
  // Example: toastr[type](message);
}

// Popup functions
function showAddPopup() {
  document.getElementById(POPUP_IDS.ADD).style.display = 'flex';
}

function closeAddPopup() {
  document.getElementById(POPUP_IDS.ADD).style.display = 'none';
}

function showEditPopup(id) {
  currentItemId = id;
  document.getElementById(POPUP_IDS.EDIT).style.display = 'flex';
  getItemInfo();
}

function closeEditPopup() {
  document.getElementById(POPUP_IDS.EDIT).style.display = 'none';
}

function showRetrievePopup(id) {
  currentItemId = id;
  document.getElementById(POPUP_IDS.RETRIEVE).style.display = 'flex';
}

function closeRetrievePopup() {
  document.getElementById(POPUP_IDS.RETRIEVE).style.display = 'none';
}

function showReturnPopup(id) {
  currentItemId = id;
  document.getElementById(POPUP_IDS.RETURN).style.display = 'flex';
}

function closeReturnPopup() {
  document.getElementById(POPUP_IDS.RETURN).style.display = 'none';
}

function showDeletePopup(projectName, id) {
  currentItemId = id;
  currentProject = projectName;
  document.getElementById(POPUP_IDS.DELETE).style.display = 'flex';
}

function closeDeletePopup() {
  document.getElementById(POPUP_IDS.DELETE).style.display = 'none';
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
    const response = await fetch(`/delete_equipment/${currentProject}/${currentItemId}`, {
      method: 'DELETE',
      headers: {
        'X-CSRFToken': csrfToken,
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

  const tableRows = elements.table.querySelectorAll('tbody tr');

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

  const rows = Array.from(elements.table.querySelectorAll('tr'));
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
