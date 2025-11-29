// reagents.js

// ==============================================
// CONSTANTS AND CONFIGURATION
// ==============================================
const POPUP_IDS = {
  ADD: 'addPopup',
  EDIT: 'editPopup',
  RETRIEVE: 'retrievePopup',
  RETURN: 'returnPopup',
  DELETE: 'deletePopup',
  MSDS: 'msdsPopup'
};

const POPUP_CONTAINERS = {
  ADD: '.popup-container1',
  EDIT: '.popup-container2',
  RETRIEVE: '.popup-container3',
  RETURN: '.popup-container4',
  DELETE: '.popup-container5',
  MSDS: '.popup-container6'
};

// Get CSRF token from meta tag
const CSRF_TOKEN = document.querySelector('meta[name="csrf-token"]')?.content || '';

// Global state
const STATE = {
  currentItemId: null,
  currentProject: null,
  currentReagentId: null,   // For MSDS operations
  activeSort: {
    column: null,
    direction: 'asc'
  }
};

// Global MSDS state
const MSDS_STATE = {
  currentFile: null,
  uploadProgress: 0,
  scanProgress: 0
};

// DOM Elements
const DOM = {
  table: document.getElementById('reagentsTable'),
  forms: {
    add: document.getElementById('reagent-form'),
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
    countryOfOrigin: document.getElementById('countryOfOriginFilterInput'),
    hazardLevel: document.getElementById('hazardLevelFilterInput'),
    thresholdValue: document.getElementById('thresholdValueFilterInput')
  },
  buttons: {
    resetFilters: document.getElementById('resetButton'),
    confirmDelete: document.getElementById('confirmDeleteBtn'),
    addItem: document.getElementById('addItemBtn')
  },
  notificationContainer: document.getElementById('notification-container'),
  msds: {
      popup: document.getElementById('msdsPopup'),
      container: document.getElementById('msdsFilesContainer'),
      uploadBtn: document.getElementById('uploadMsdsBtn'),
      uploadForm: document.getElementById('msdsUploadForm'),
      uploadFormElement: document.getElementById('msdsUploadFormElement'),
      fileInput: document.getElementById('msdsFileInput'),
      uploadStatus: document.getElementById('msdsUploadStatus'),
      progressBar: document.createElement('div'),
      progressText: document.createElement('span')
  }
};

// ==============================================
// INITIALIZATION
// ==============================================
function initReagentsManager() {
  setupPopups();
  setupEventListeners();
  initialFilter();
  setupTemperatureUnitHandling();
  setupStorageConditionHandling();
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

  // MSDS event listeners
  if (DOM.msds.uploadBtn) {
    DOM.msds.uploadBtn.addEventListener('click', showMsdsUploadForm);
  }
  
  if (DOM.msds.uploadFormElement) {
    DOM.msds.uploadFormElement.addEventListener('submit', handleMsdsUpload);
  }
  
  // Close MSDS popup when clicking outside
  if (DOM.msds.popup) {
    DOM.msds.popup.addEventListener('click', (e) => {
      if (e.target === DOM.msds.popup) {
        closeMsdsPopup();
      }
    });
  }
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
  //DOM.forms.add?.addEventListener('submit', (e) => {
  //  e.preventDefault();
  //  submitForm('reagent-form', DOM.forms.add.action, 'POST', handleAddSuccess);
  //});
  
  // Edit form
  DOM.forms.edit?.addEventListener('submit', (e) => {
    if (!validateTemperatureUnits()) {
        e.preventDefault();
        return;
    }
    e.preventDefault();
    submitForm('edit-form', `/edit_reagent/${STATE.currentItemId}`, 'POST', handleEditSuccess);
  });
  
  // Retrieve form
  DOM.forms.retrieve?.addEventListener('submit', (e) => {
    e.preventDefault();
    submitForm('retrieve-form', `/retrieve_reagent/${STATE.currentItemId}`, 'POST', handleRetrieveSuccess);
  });
  
  // Return form
  DOM.forms.return?.addEventListener('submit', (e) => {
    e.preventDefault();
    submitForm('return-form', `/restock_reagent/${STATE.currentItemId}`, 'POST', handleReturnSuccess);
  });

    // Add MSDS file change listener
  if (DOM.msds.fileInput) {
    DOM.msds.fileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        MSDS_STATE.currentFile = e.target.files[0];
        validateMsdsFile(MSDS_STATE.currentFile);
      }
    });
  }
  
  // Update add form submission to use progress version
  DOM.forms.add?.addEventListener('submit', (e) => {
    if (!validateTemperatureUnits()) {
        e.preventDefault();
        return;
    }
    e.preventDefault();
    submitFormWithProgress('reagent-form', DOM.forms.add.action, 'POST', handleAddSuccess);
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

    // Check if click was on MSDS cell
  const msdsCell = e.target.closest('td:nth-child(14)');
  if (msdsCell) {
    showMsdsPopup(STATE.currentItemId);
    return;
  }

  // Action dropdown clicks
  const target = e.target.closest('button');
    if (!target) return;

  if (e.target.closest('.edit-action')) {
    showEditPopup(STATE.currentItemId);
  }
  else if (e.target.closest('.retrieve-action')) {
    showRetrievePopup(STATE.currentItemId);
  }
  else if (e.target.closest('.return-action')) {
    showReturnPopup(STATE.currentItemId);
  }
  else if (e.target.closest('.delete-action')) {
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
    const response = await fetch(`/get_reagent_info/${STATE.currentItemId}`);
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
                 'oem_temperature', 'vendor', 'country_of_origin',
                 'hazard_level', 'threshold_value', 'notes'];
  
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
    const msdsFile = formData.get('msds_file');

    showLoading(formId.includes('add') ? POPUP_IDS.ADD : POPUP_IDS.EDIT);

    const response = await fetch(url, {
      method,
      headers: {
        'X-CSRFToken': CSRF_TOKEN,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(Object.fromEntries(formData)),
    });

    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Network response was not ok');
    }
    
    const data = await response.json();
    successCallback(data);
  } catch (error) {
    console.error('Error:', error);
    showNotification(error.message || 'An error occurred. Please try again.', 'error');

    if (error.message.includes('MSDS')) {
        const statusEl = document.getElementById('msdsUploadStatus');
        if (statusEl) {
            statusEl.classList.remove('hidden');
            statusEl.textContent = error.message;
            statusEl.className = 'text-red-500 text-sm mt-1';
        }
    }
  } finally {
      hideLoading();
  }
}

function handleAddSuccess(data) {
  showNotification('Reagent added successfully', 'success');
  closeAddPopup();
  if (data.refresh) {
    setTimeout(() => location.reload(), 1000);
  }
}

function handleEditSuccess(data) {
  updateTableRow(STATE.currentItemId, data);
  showNotification('Reagent updated successfully', 'success');
  closeEditPopup();
}

function handleRetrieveSuccess(data) {
  updateTableRow(STATE.currentItemId, data);
  showNotification('Reagent retrieved successfully', 'success');
  closeRetrievePopup();
}

function handleReturnSuccess(data) {
  updateTableRow(STATE.currentItemId, data);
  showNotification('Reagent returned successfully', 'success');
  closeReturnPopup();
}

async function handleDeleteConfirm() {
  if (!STATE.currentItemId || !STATE.currentProject) return;

  showLoading(POPUP_IDS.DELETE);

  try {
    const response = await fetch(`/delete_reagent/${STATE.currentProject}/${STATE.currentItemId}`, {
      method: 'DELETE',
      headers: {
        'X-CSRFToken': CSRF_TOKEN,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) throw new Error('Failed to delete reagent');
    
    const data = await response.json();
    showNotification('Reagent deleted successfully', 'success');
    removeTableRow(STATE.currentItemId);
    closeDeletePopup();
  } catch (error) {
    console.error('Delete error:', error);
    showNotification(error.message || 'Failed to delete reagent', 'error');
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

  // Update MSDS cell
  const msdsCell = row.querySelector('td:nth-child(14)'); // Adjust column index as needed
  if (msdsCell) {
    if (data.has_msds) {
      msdsCell.innerHTML = `
        <button onclick="showMsdsPopup('${id}')" class="text-primary hover:underline">
          View MSDS
        </button>
      `;
    } else {
      msdsCell.innerHTML = `
        <button onclick="showMsdsUploadForm('${id}')" class="text-red-500 hover:underline">
          Upload MSDS
        </button>
      `;
    }
  }
  
  // Highlight update
  row.classList.add('updated');
  setTimeout(() => row.classList.remove('updated'), 1000);

  // Update dataset attributes
  row.dataset.name = data.name;
  row.dataset.productCode = data.product_code;
  row.dataset.itemsPerPack = data.items_per_pack;
  row.dataset.packCount = data.pack_count;
  //row.dataset.dateCreated = data.date_created;
  row.dataset.expiryDate = data.expiry_date;
  row.dataset.storageLocation = data.storage_location;
  row.dataset.coldStorage = data.cold_storage;
  row.dataset.optimalTemp = data.optimal_temp;
  row.dataset.vendor = data.vendor;
  row.dataset.countryOfOrigin = data.country_of_origin;
  row.dataset.hazardLevel = data.hazard_level;
  row.dataset.msds = data.msds;
  row.dataset.thresholdValue = data.threshold_value;
  row.dataset.notes = data.notes;

  // Update cells
  const cells = row.querySelectorAll('td');
  if (cells.length > 7) {
    cells[0].setAttribute('data-fulltext', data.name);
    cells[0].textContent = truncateText(escapeHtml(data.name), 20);
    cells[1].textContent = escapeHtml(data.product_code) || '';
    cells[2].textContent = data.items_left_in_pack || 0;
    cells[3].textContent = data.items_per_pack || 0;
    cells[4].textContent = data.pack_count || 0;
    /cells[5].textContent = data.date_created || '';
    cells[6].textContent = data.expiry_date || '';
    cells[7].setAttribute('data-fulltext', data.storage_location);
    cells[7].textContent = truncateText(escapeHtml(data.storage_location), 20);
    cells[8].textContent = escapeHtml(data.cold_storage) || '';
    cells[9].textContent = data.optimal_temp || 0;
    cells[10].textContent = escapeHtml(data.vendor) || '';
    cells[11].textContent = escapeHtml(data.country_of_origin) || '';
    cells[12].textContent = data.hazard_level || 0;
    cells[13].textContent = data.msds || '';
    cells[14].textContent = data.threshold || 0;
    cells[15].setAttribute('data-fulltext', data.notes);
    cells[15].textContent = truncateText(escapeHtml(data.notes), 20) || '';
  }
}

// Helper function to escape HTML
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
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
    countryOfOrigin: DOM.filterInputs.countryOfOrigin?.value.toLowerCase() || '',
    hazardLevel: DOM.filterInputs.hazardLevel?.value ? parseInt(DOM.filterInputs.hazardLevel.value) : null,
    thresholdValue: DOM.filterInputs.thresholdValue?.value ? parseInt(DOM.filterInputs.thresholdValue.value) : null
  };
  
  const rows = DOM.table?.querySelectorAll('tr[data-id]') || [];
  
  rows.forEach(row => {
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
      countryOfOrigin: (row.dataset.countryOfOrigin || '').toLowerCase(),
      hazardLevel: parseInt(row.dataset.hazardLevel) || 0,
      thresholdValue: parseInt(row.dataset.threshold) || 0
    };
    
    const isVisible = (
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
      rowData.countryOfOrigin.includes(filters.countryOfOrigin) &&
      (filters.hazardLevel === null || rowData.hazardLevel === filters.hazardLevel) &&
      (filters.thresholdValue === null || rowData.thresholdValue === filters.thresholdValue)
    );
    
    row.style.display = isVisible ? '' : 'none';
  });
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
// MSDS FUNCTIONS
// ==============================================

function showMsdsPopup(reagentId) {
  STATE.currentReagentId = reagentId;
  showModal(POPUP_IDS.MSDS);
  loadMsdsFiles(reagentId);
}

function closeMsdsPopup() {
  closeModal(POPUP_IDS.MSDS);
  STATE.currentReagentId = null;
  if (DOM.msds.uploadForm) DOM.msds.uploadForm.classList.add('hidden');
  if (DOM.msds.uploadBtn) DOM.msds.uploadBtn.classList.remove('hidden');
}

function showMsdsUploadForm() {
  if (DOM.msds.uploadForm) DOM.msds.uploadForm.classList.remove('hidden');
  if (DOM.msds.uploadBtn) DOM.msds.uploadBtn.classList.add('hidden');
}

function cancelMsdsUpload() {
  if (DOM.msds.uploadForm) DOM.msds.uploadForm.classList.add('hidden');
  if (DOM.msds.uploadBtn) DOM.msds.uploadBtn.classList.remove('hidden');
  if (DOM.msds.fileInput) DOM.msds.fileInput.value = '';
}

async function loadMsdsFiles(reagentId) {
  if (!DOM.msds.container) return;
  
  showLoading(POPUP_IDS.MSDS);
  DOM.msds.container.innerHTML = '<p class="text-gray-500">Loading MSDS files...</p>';
  
  try {
    const response = await fetch(`/reagents/${reagentId}/msds/`);
    if (!response.ok) throw new Error('Failed to load MSDS files');
    
    const data = await response.json();
    renderMsdsFiles(data.msds_files);
  } catch (error) {
    console.error('Error loading MSDS files:', error);
    DOM.msds.container.innerHTML = '<p class="text-red-500">Error loading MSDS files</p>';
  } finally {
    hideLoading();
  }
}

function renderMsdsFiles(files) {
  if (!DOM.msds.container) return;
  
  if (files.length === 0) {
    DOM.msds.container.innerHTML = '<p class="text-gray-500">No MSDS file uploaded</p>';
    return;
  }
  
  const table = document.createElement('table');
  table.className = 'w-full border-collapse';
  table.innerHTML = `
    <thead>
      <tr class="bg-gray-100">
        <th class="p-2 text-left">Filename</th>
        <th class="p-2 text-left">Uploaded By</>
        <th class="p-2 text-left">Upload Date</th>
        <th class="p-2 text-left">Status</th>
        <th class="p-2 text-left">Actions</th>
      </tr>
    </thead>
    <tbody id="msdsFilesList"></tbody>
  `;
  
  const tbody = table.querySelector('tbody');
  files.forEach(file => {
    const row = document.createElement('tr');
    row.className = 'border-b';
    row.innerHTML = `
      <td class="p-2">
        <a href="${file.download_url}" target="_blank" class="text-primary hover:underline">
          ${file.filename}
        </a>
      </td>
      <td class="p-2">${file.uploaded_by}</td>
      <td class="p-2">${file.upload_date}</td>
      <td class="p-2">
        <span class="status-badge ${file.scan_result === 'clean' ? 'bg-green-100 text-green-800' : 
          file.scan_result === 'infected' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'}">
          ${file.scan_result}
        </span>
      </td>
      <td class="p-2">
        <button onclick="deleteMsdsFile('${file.id}', '${STATE.currentReagentId}')" class="text-red-500 hover:text-red-700">
          Delete
        </button>
      </td>
    `;
    tbody.appendChild(row);
  });
  
  DOM.msds.container.innerHTML = '';
  DOM.msds.container.appendChild(table);
}

async function handleMsdsUpload(e) {
    e.preventDefault();
    if (!STATE.currentReagentId || !DOM.msds.uploadForm) return;
    
    const formData = new FormData(DOM.msds.uploadForm);
    const submitBtn = DOM.msds.uploadForm.querySelector('button[type="submit"]');
    
    // Show progress elements
    const fileInputContainer = DOM.msds.uploadForm.querySelector('.inputBox');
    if (fileInputContainer && !fileInputContainer.contains(DOM.msds.progressBar)) {
        fileInputContainer.appendChild(DOM.msds.progressBar);
        fileInputContainer.appendChild(DOM.msds.progressText);
    }
    
    showMsdsUploadProgress(0, 'Starting upload...');
    submitBtn.disabled = true;

    try {
        const xhr = new XMLHttpRequest();
        
        // Track upload progress
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percent = Math.round((e.loaded / e.total) * 100);
                showMsdsUploadProgress(percent, `Uploading... ${percent}%`);
            }
        });
        
        xhr.addEventListener('load', function() {
            if (xhr.status === 200) {
                const data = JSON.parse(xhr.responseText);
                if (data.success) {
                    showMsdsUploadProgress(100, 'Upload complete!');
                    showNotification('MSDS uploaded successfully', 'success');
                    loadMsdsFiles(STATE.currentReagentId);
                    cancelMsdsUpload();
                } else {
                    showNotification(data.error || 'Error uploading file', 'error');
                }
            } else {
                showNotification('Upload failed', 'error');
            }
        });
        
        xhr.addEventListener('error', function() {
            showNotification('Upload error', 'error');
        });
        
        xhr.open('POST', `/reagents/${STATE.currentProject}/${STATE.currentItemId}/upload-msds/`);
        xhr.setRequestHeader('X-CSRFToken', CSRF_TOKEN);
        xhr.send(formData);

    } catch (error) {
        console.error('Upload error:', error);
        showNotification('Error uploading file', 'error');
    } finally {
        submitBtn.disabled = false;
    }
}

async function deleteMsdsFile(msdsId, reagentId) {
  if (!confirm('Are you sure you want to delete this MSDS file?')) return;
  
  showLoading(POPUP_IDS.MSDS);
  
  try {
    const response = await fetch(`/msds/${msdsId}/delete/`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': CSRF_TOKEN,
        'Content-Type': 'application/json'
      }
    });
    
    const data = await response.json();
    
    if (data.success) {
      showNotification('MSDS deleted successfully', 'success');
      loadMsdsFiles(reagentId); // Refresh the list
    } else {
      showNotification(data.error || 'Error deleting file', 'error');
    }
  } catch (error) {
    console.error('Delete error:', error);
    showNotification('Error deleting file', 'error');
  } finally {
    hideLoading();
  }
}

// Initialize MSDS progress indicators
function initMsdsProgress() {
  DOM.msds.progressBar = document.createElement('div');
  DOM.msds.progressBar.className = 'w-full bg-gray-200 rounded-full h-2.5 mt-2';
  DOM.msds.progressBar.innerHTML = `
    <div id="msdsProgressBar" class="bg-primary h-2.5 rounded-full transition-all duration-300" style="width: 0%"></div>
  `;
  
  DOM.msds.progressText = document.createElement('span');
  DOM.msds.progressText.className = 'text-xs text-gray-500 mt-1';
  DOM.msds.progressText.id = 'msdsProgressText';
}

function showMsdsUploadProgress(percent, message = '') {
    const progressBar = document.getElementById('msdsProgressBar');
    const progressText = document.getElementById('msdsProgressText');
    
    if (progressBar) {
        progressBar.style.width = `${percent}%`;
    }
    
    if (progressText) {
        progressText.textContent = message || `Uploading... ${percent}%`;
    }
}

// Client-side validation
function validateMsdsFile(file) {
  // File type validation
  if (file.type !== 'application/pdf') {
    showMsdsStatus('Only PDF files are allowed', 'error');
    return false;
  }
  
  // File size validation (5MB limit)
  if (file.size > 5 * 1024 * 1024) {
    showMsdsStatus('File size exceeds 5MB limit', 'error');
    return false;
  }
  
  return true;
}

function showMsdsStatus(message, type = 'info') {
  DOM.msds.uploadStatus.textContent = message;
  DOM.msds.uploadStatus.className = `text-sm mt-1 ${
    type === 'error' ? 'text-red-500' : 
    type === 'success' ? 'text-green-500' : 'text-gray-500'
  }`;
  DOM.msds.uploadStatus.classList.remove('hidden');
}

// Update progress indicators
function updateMsdsProgress(uploadPercent, scanPercent = 0) {
  const totalPercent = Math.floor(uploadPercent * 0.7 + scanPercent * 0.3);
  document.getElementById('msdsProgressBar').style.width = `${totalPercent}%`;
  
  DOM.msds.progressText.textContent = 
    `Uploading: ${uploadPercent}% | Scanning: ${scanPercent}%`;
}

// Modified form submission with progress tracking
async function submitFormWithProgress(formId, url, method, successCallback) {
  const form = document.getElementById(formId);
  if (!form) return;

  const formData = new FormData(form);
  const msdsFile = formData.get('msds_file');
  
  // Client-side validation
  if (msdsFile && !validateMsdsFile(msdsFile)) {
    return;
  }

  // Add progress elements if they don't exist
  if (!document.getElementById('msdsProgressBar')) {
    form.querySelector('.inputBox').appendChild(DOM.msds.progressBar);
    form.querySelector('.inputBox').appendChild(DOM.msds.progressText);
  }

  try {
    const xhr = new XMLHttpRequest();
    
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const percent = Math.round((e.loaded / e.total) * 100);
        MSDS_STATE.uploadProgress = percent;
        updateMsdsProgress(percent, MSDS_STATE.scanProgress);
      }
    });

    // Simulate scan progress (in real app, this would come from server events)
    const scanInterval = setInterval(() => {
      if (MSDS_STATE.scanProgress < 100) {
        MSDS_STATE.scanProgress += 10;
        updateMsdsProgress(MSDS_STATE.uploadProgress, MSDS_STATE.scanProgress);
      }
    }, 300);

    xhr.onreadystatechange = function() {
      if (xhr.readyState === 4) {
        clearInterval(scanInterval);
        
        if (xhr.status === 200) {
          const data = JSON.parse(xhr.responseText);
          successCallback(data);
        } else {
          const error = JSON.parse(xhr.responseText).error || 'Upload failed';
          showMsdsStatus(error, 'error');
        }
      }
    };

    xhr.open(method, url);
    xhr.setRequestHeader('X-CSRFToken', CSRF_TOKEN);
    xhr.send(formData);

  } catch (error) {
    console.error('Upload error:', error);
    showMsdsStatus('Upload failed', 'error');
  }
}


// ==============================================
// BULK ACTIONS IMPLEMENTATION
// ==============================================
function setupBulkActions() {
    // Add bulk action checkboxes to table headers
    const tableHead = DOM.table?.querySelector('thead tr');
    if (tableHead) {
        const selectAllTh = document.createElement('th');
        selectAllTh.innerHTML = `
            <input type="checkbox" id="selectAllReagents" 
                   class="bulk-select-checkbox" style="width: 16px; height: 16px;">
        `;
        selectAllTh.style.width = '30px';
        tableHead.insertBefore(selectAllTh, tableHead.firstChild);
        
        // Select all functionality
        document.getElementById('selectAllReagents')?.addEventListener('change', function() {
            const checkboxes = document.querySelectorAll('.reagent-checkbox');
            checkboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
            toggleBulkActions();
        });
    }
    
    // Add checkboxes to each row
    const rows = DOM.table?.querySelectorAll('tbody tr[data-id]');
    rows.forEach(row => {
        const checkboxTd = document.createElement('td');
        checkboxTd.innerHTML = `
            <input type="checkbox" class="reagent-checkbox" 
                   data-id="${row.dataset.id}" style="width: 16px; height: 16px;">
        `;
        checkboxTd.style.width = '30px';
        row.insertBefore(checkboxTd, row.firstChild);
        
        // Row checkbox functionality
        const checkbox = checkboxTd.querySelector('.reagent-checkbox');
        checkbox.addEventListener('change', toggleBulkActions);
    });
    
    // Add bulk actions toolbar
    addBulkActionsToolbar();
}

function addBulkActionsToolbar() {
    const bulkActionsToolbar = document.createElement('div');
    bulkActionsToolbar.id = 'bulkActionsToolbar';
    bulkActionsToolbar.className = 'fixed bottom-4 left-1/2 transform -translate-x-1/2 bg-white shadow-lg rounded-lg p-3 hidden';
    bulkActionsToolbar.innerHTML = `
        <div class="flex items-center space-x-3">
            <span id="selectedCount" class="text-sm font-medium">0 selected</span>
            <button onclick="bulkDeleteReagents()" class="btn btn-danger btn-sm">Delete Selected</button>
            <button onclick="bulkExportReagents()" class="btn btn-secondary btn-sm">Export Selected</button>
            <button onclick="clearBulkSelection()" class="btn btn-secondary btn-sm">Cancel</button>
        </div>
    `;
    
    document.body.appendChild(bulkActionsToolbar);
}

function toggleBulkActions() {
    const selectedCount = document.querySelectorAll('.reagent-checkbox:checked').length;
    const toolbar = document.getElementById('bulkActionsToolbar');
    const selectedCountElement = document.getElementById('selectedCount');
    
    if (selectedCount > 0) {
        toolbar.classList.remove('hidden');
        selectedCountElement.textContent = `${selectedCount} selected`;
    } else {
        toolbar.classList.add('hidden');
    }
}

function clearBulkSelection() {
    const checkboxes = document.querySelectorAll('.reagent-checkbox:checked');
    checkboxes.forEach(checkbox => {
        checkbox.checked = false;
    });
    toggleBulkActions();
}

async function bulkDeleteReagents() {
    const selectedIds = Array.from(document.querySelectorAll('.reagent-checkbox:checked'))
        .map(checkbox => checkbox.dataset.id);
    
    if (selectedIds.length === 0) return;
    
    if (!confirm(`Are you sure you want to delete ${selectedIds.length} reagent(s)? This action cannot be undone.`)) {
        return;
    }
    
    showLoading('bulkActionsToolbar');
    
    try {
        const formData = new FormData();
        selectedIds.forEach(id => formData.append('reagent_ids', id));
        
        const response = await fetch(`/reagents/${STATE.currentProject}/bulk-delete/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': CSRF_TOKEN,
            },
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`Successfully deleted ${data.deleted_count} reagents`, 'success');
            // Refresh the table after a short delay
            setTimeout(() => location.reload(), 1000);
        } else {
            showNotification(data.error || 'Error during bulk deletion', 'error');
        }
        
    } catch (error) {
        console.error('Bulk delete error:', error);
        showNotification('Error during bulk deletion', 'error');
    } finally {
        hideLoading();
        clearBulkSelection();
    }
}

async function bulkExportReagents() {
    const selectedIds = Array.from(document.querySelectorAll('.reagent-checkbox:checked'))
        .map(checkbox => checkbox.dataset.id);
    
    if (selectedIds.length === 0) return;
    
    showNotification(`Preparing export of ${selectedIds.length} reagents...`, 'info');
    
    // Create query string for selected IDs
    const queryString = selectedIds.map(id => `ids=${id}`).join('&');
    
    // Open the export in a new tab - this calls the dedicated bulk export endpoint
    window.open(`/reagents/${STATE.currentProject}/bulk-export/?${queryString}`, '_blank');
    
    // Close bulk actions
    clearBulkSelection();
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

function truncateText(text, maxLength) {
  if (!text) return '';
  return text.length > maxLength 
    ? text.substring(0, maxLength - 3) + '...' 
    : text;
}

function initialFilter() {
  filterTable();
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

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initReagentsManager();
    initMsdsProgress();
});

// Make functions available globally for inline handlers
window.showMsdsPopup = showMsdsPopup;
window.closeMsdsPopup = closeMsdsPopup;
window.cancelMsdsUpload = cancelMsdsUpload;
window.deleteMsdsFile = deleteMsdsFile;
