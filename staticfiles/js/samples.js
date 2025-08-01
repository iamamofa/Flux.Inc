// samples.js

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
  table: document.getElementById('samplesTable'),
  forms: {
    add: document.getElementById('sample-form'),
    edit: document.getElementById('edit-form'),
    retrieve: document.getElementById('retrieve-form'),
    return: document.getElementById('return-form')
  },
  filterInputs: {
    sampleID: document.getElementById('sampleIDFilterInput'),
    sampleType: document.getElementById('sampleTypeFilterInput'),
    country: document.getElementById('countryFilterInput'),
    minVolume: document.getElementById('minVolumeFilterInput'),
    maxVolume: document.getElementById('maxVolumeFilterInput'),
    minDateCreated: document.getElementById('minDateCreatedFilterInput'),
    maxDateCreated: document.getElementById('maxDateCreatedFilterInput'),
    storageLocation: document.getElementById('storageLocationFilterInput')
  },
  buttons: {
    resetFilters: document.getElementById('resetButton'),
    confirmDelete: document.getElementById('confirmDeleteBtn'),
    addItem: document.getElementById('addItemBtn')
  },
  notificationContainer: document.getElementById('notification-container')
};

// ==============================================
// INITIALIZATION
// ==============================================
function initSamplesManager() {
  setupPopups();
  setupEventListeners();
  initialFilter();
}

// ==============================================
// EVENT HANDLERS SETUP
// ==============================================
function setupEventListeners() {
  // Modal triggers
  DOM.buttons.addItem?.addEventListener('click', showAddPopup);
  
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
    submitForm('sample-form', DOM.forms.add.action, 'POST', handleAddSuccess);
  });
  
  // Edit form
  DOM.forms.edit?.addEventListener('submit', (e) => {
    e.preventDefault();
    submitForm('edit-form', `/edit_sample/${STATE.currentItemId}`, 'PUT', handleEditSuccess);
  });
  
  // Retrieve form
  DOM.forms.retrieve?.addEventListener('submit', (e) => {
    e.preventDefault();
    submitForm('retrieve-form', `/retrieve_sample/${STATE.currentItemId}`, 'PUT', handleRetrieveSuccess);
  });
  
  // Return form
  DOM.forms.return?.addEventListener('submit', (e) => {
    e.preventDefault();
    submitForm('return-form', `/return_sample/${STATE.currentItemId}`, 'PUT', handleReturnSuccess);
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
    const response = await fetch(`/get_sample_info/${STATE.currentItemId}`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    const data = await response.json();
    populateEditForm(data);
  } catch (error) {
    console.error('Error loading sample data:', error);
    showNotification('Failed to load sample data', 'error');
  } finally {
    hideLoading();
  }
}

function populateEditForm(data) {
  if (!DOM.forms.edit) return;
  
  const fields = ['sample_id', 'sample_type', 'description', 'country', 
                 'volume', 'well_id', 'storage_location', 'threshold_value'];
  
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
    const response = await fetch(url, {
      method,
      headers: {
        'X-CSRFToken': CSRF_TOKEN,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(Object.fromEntries(formData)),
    });

    if (!response.ok) throw new Error('Network response was not ok');
    
    const data = await response.json();
    successCallback(data);
  } catch (error) {
    console.error('Error:', error);
    showNotification(error.message || 'An error occurred. Please try again.', 'error');
  }
}

function handleAddSuccess(data) {
  showNotification('Sample added successfully', 'success');
  closeAddPopup();
  if (data.refresh) {
    setTimeout(() => location.reload(), 1000);
  }
}

function handleEditSuccess(data) {
  updateTableRow(STATE.currentItemId, data);
  showNotification('Sample updated successfully', 'success');
  closeEditPopup();
}

function handleRetrieveSuccess(data) {
  updateTableRow(STATE.currentItemId, data);
  showNotification('Sample retrieved successfully', 'success');
  closeRetrievePopup();
}

function handleReturnSuccess(data) {
  updateTableRow(STATE.currentItemId, data);
  showNotification('Sample returned successfully', 'success');
  closeReturnPopup();
}

async function handleDeleteConfirm() {
  if (!STATE.currentItemId || !STATE.currentProject) return;

  showLoading(POPUP_IDS.DELETE);

  try {
    const response = await fetch(`/delete_sample/${STATE.currentProject}/${STATE.currentItemId}`, {
      method: 'DELETE',
      headers: {
        'X-CSRFToken': CSRF_TOKEN,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) throw new Error('Failed to delete sample');
    
    const data = await response.json();
    showNotification('Sample deleted successfully', 'success');
    removeTableRow(STATE.currentItemId);
    closeDeletePopup();
  } catch (error) {
    console.error('Delete error:', error);
    showNotification(error.message || 'Failed to delete sample', 'error');
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
  if (cells.length >= 8) {
    cells[0].textContent = data.sample_id || '';
    cells[1].setAttribute('data-fulltext', data.sample_type);
    cells[1].textContent = truncateText(data.sample_type, 15);
    cells[2].setAttribute('data-fulltext', data.description);
    cells[2].textContent = truncateText(data.description, 20);
    cells[3].textContent = data.country || '';
    cells[4].textContent = data.volume || '';
    cells[6].textContent = data.well_id || '';
    cells[7].setAttribute('data-fulltext', data.storage_location);
    cells[7].textContent = truncateText(data.storage_location, 15);
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
    sampleID: DOM.filterInputs.sampleID?.value.toLowerCase() || '',
    sampleType: DOM.filterInputs.sampleType?.value.toLowerCase() === 'all' ? '' : DOM.filterInputs.sampleType?.value?.toLowerCase(),
    country: DOM.filterInputs.country?.value.toLowerCase() || '',
    minVolume: DOM.filterInputs.minVolume?.value ? parseFloat(DOM.filterInputs.minVolume.value) : 0,
    maxVolume: DOM.filterInputs.maxVolume?.value ? parseFloat(DOM.filterInputs.maxVolume.value) : Infinity,
    minDateCreated: DOM.filterInputs.minDateCreated?.value || '',
    maxDateCreated: DOM.filterInputs.maxDateCreated?.value || '',
    storageLocation: DOM.filterInputs.storageLocation?.value.toLowerCase() || ''
  };
  
  const rows = DOM.table?.querySelectorAll('tr[data-id]') || [];
  
  rows.forEach(row => {
    const rowData = {
      sampleID: (row.dataset.sampleId || '').toLowerCase(),
      sampleType: (row.dataset.sampleType || '').toLowerCase(),
      country: (row.dataset.country || '').toLowerCase(),
      volume: parseFloat(row.dataset.volume) || 0,
      dateCreated: row.dataset.dateCreated || '',
      storageLocation: (row.dataset.storageLocation || '').toLowerCase()
    };
    
    const isVisible = (
      rowData.sampleID.includes(filters.sampleID) &&
      rowData.sampleType.includes(filters.sampleType) &&
      rowData.country.includes(filters.country) &&
      rowData.volume >= filters.minVolume &&
      rowData.volume <= filters.maxVolume &&
      isDateInRange(rowData.dateCreated, filters.minDateCreated, filters.maxDateCreated) &&
      rowData.storageLocation.includes(filters.storageLocation)
    );
    
    row.style.display = isVisible ? '' : 'none';
  });
}

function resetFilters() {
  // Reset all filter inputs
  Object.values(DOM.filterInputs).forEach(input => {
    if (input) input.value = input.tagName === 'SELECT' ? 'all' : '';
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

    if (columnNum === '5') { // Volume column
      return STATE.activeSort.direction === 'asc' 
        ? aValue - bValue 
        : bValue - aValue;
    }
    
    if (columnNum === '6') { // Date column
      return STATE.activeSort.direction === 'asc' 
        ? new Date(aValue) - new Date(bValue)
        : new Date(bValue) - new Date(aValue);
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
  
  if (columnNum === '5') return parseFloat(value) || 0; // Volume
  if (columnNum === '6') return value; // Date
  
  return value.toLowerCase();
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

function truncateText(text, maxLength) {
  return text.length > maxLength 
    ? text.substring(0, maxLength - 3) + '...' 
    : text;
}

function initialFilter() {
  filterTable();
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initSamplesManager);
