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

// Global state for storage creation
const STORAGE_STATE = {
    currentShelf: null,
    currentRack: null,
    currentBox: null
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

 // Load storage options if we're on a project page
  if (STATE.currentProject) {
    loadStorageOptions();
  }
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

// Load storage options when the page loads
async function loadStorageOptions() {
  try {
    const response = await fetch(`/api/storage-options/${STATE.currentProject}`);
    if (!response.ok) throw new Error('Failed to load storage options');
    
    const data = await response.json();
    populateShelves(data.shelves);
    // Pre-populate racks and boxes too for better UX
    populateRacks(data.racks);
    populateBoxes(data.boxes);
  } catch (error) {
    console.error('Error loading storage options:', error);
    showNotification('Failed to load storage options', 'error');
  }
}

// Populate shelves dropdown
function populateShelves(shelves) {
  const shelfSelect = document.getElementById('shelfSelect');
  if (!shelfSelect) return;
  
  // Clear existing options except the first two
  while (shelfSelect.options.length > 2) {
    shelfSelect.remove(2);
  }
  
  // Add new options with project info
  shelves.forEach(shelf => {
    const option = document.createElement('option');
    option.value = shelf.id;
    option.textContent = `${shelf.name} (${shelf.location_code}) - ${shelf.project__name}`;
    option.setAttribute('data-project', shelf.project__name);
    shelfSelect.appendChild(option);
  });
}

// Populate racks dropdown
function populateRacks(racks) {
  const rackSelect = document.getElementById('rackSelect');
  if (!rackSelect) return;
  
  // Clear existing options except the first two
  while (rackSelect.options.length > 2) {
    rackSelect.remove(2);
  }
  
  // Add new options with project and shelf info
  racks.forEach(rack => {
    const option = document.createElement('option');
    option.value = rack.id;
    option.textContent = `${rack.name} (${rack.location_code}) - ${rack.project__name}`;
    option.setAttribute('data-shelf', rack.shelf_id);
    option.setAttribute('data-project', rack.project__name);
    rackSelect.appendChild(option);
  });
}

// Populate boxes dropdown
function populateBoxes(boxes) {
  const boxSelect = document.getElementById('boxSelect');
  if (!boxSelect) return;
  
  // Clear existing options except the first two
  while (boxSelect.options.length > 2) {
    boxSelect.remove(2);
  }
  
  // Add new options with project and rack info
  boxes.forEach(box => {
    const option = document.createElement('option');
    option.value = box.id;
    option.textContent = `${box.name} (${box.location_code}) - ${box.project__name}`;
    option.setAttribute('data-rack', box.rack_id);
    option.setAttribute('data-project', box.project__name);
    boxSelect.appendChild(option);
  });
}

// Handle shelf selection change
function handleShelfChange(shelfId) {
  const rackSelect = document.getElementById('rackSelect');
  const newShelfForm = document.getElementById('newShelfForm');
  
  if (shelfId === 'new') {
    // Show new shelf form
    newShelfForm.style.display = 'block';
    rackSelect.disabled = true;
    STORAGE_STATE.currentShelf = null;
  } else if (shelfId) {
    // Hide new shelf form and filter racks
    newShelfForm.style.display = 'none';
    STORAGE_STATE.currentShelf = shelfId;
    filterRacksByShelf(shelfId);
    rackSelect.disabled = false;
  } else {
    // No shelf selected
    newShelfForm.style.display = 'none';
    rackSelect.disabled = true;
    STORAGE_STATE.currentShelf = null;
  }
  
  // Reset downstream selections
  disableSelect('boxSelect');
  STORAGE_STATE.currentRack = null;
  STORAGE_STATE.currentBox = null;
}

// Handle rack selection change
function handleRackChange(rackId) {
  const boxSelect = document.getElementById('boxSelect');
  const newRackForm = document.getElementById('newRackForm');
  
  if (rackId === 'new') {
    // Show new rack form
    newRackForm.style.display = 'block';
    boxSelect.disabled = true;
    STORAGE_STATE.currentRack = null;
  } else if (rackId) {
    // Hide new rack form and filter boxes
    newRackForm.style.display = 'none';
    STORAGE_STATE.currentRack = rackId;
    filterBoxesByRack(rackId);
    boxSelect.disabled = false;
  } else {
    // No rack selected
    newRackForm.style.display = 'none';
    boxSelect.disabled = true;
    STORAGE_STATE.currentRack = null;
  }
  
  // Reset downstream selection
  STORAGE_STATE.currentBox = null;
}

// Handle box selection change
function handleBoxChange(boxId) {
  const newBoxForm = document.getElementById('newBoxForm');
  
  if (boxId === 'new') {
    // Show new box form
    newBoxForm.style.display = 'block';
    STORAGE_STATE.currentBox = null;
  } else if (boxId) {
    // Hide new box form
    newBoxForm.style.display = 'none';
    STORAGE_STATE.currentBox = boxId;
  } else {
    // No box selected
    newBoxForm.style.display = 'none';
    STORAGE_STATE.currentBox = null;
  }
}

// Filter racks by selected shelf
function filterRacksByShelf(shelfId) {
  const rackSelect = document.getElementById('rackSelect');
  if (!rackSelect) return;
  
  // Enable all options first
  Array.from(rackSelect.options).forEach(option => {
    option.style.display = '';
  });
  
  // Hide options that don't belong to the selected shelf
  if (shelfId && shelfId !== 'new') {
    Array.from(rackSelect.options).forEach(option => {
      if (option.value && option.value !== 'new' && option.getAttribute('data-shelf') !== shelfId) {
        option.style.display = 'none';
      }
    });
  }
}

// Filter boxes by selected rack
function filterBoxesByRack(rackId) {
  const boxSelect = document.getElementById('boxSelect');
  if (!boxSelect) return;
  
  // Enable all options first
  Array.from(boxSelect.options).forEach(option => {
    option.style.display = '';
  });
  
  // Hide options that don't belong to the selected rack
  if (rackId && rackId !== 'new') {
    Array.from(boxSelect.options).forEach(option => {
      if (option.value && option.value !== 'new' && option.getAttribute('data-rack') !== rackId) {
        option.style.display = 'none';
      }
    });
  }
}

// Disable a select dropdown
function disableSelect(selectId) {
  const select = document.getElementById(selectId);
  if (!select) return;
  
  // Clear options except the first one
  while (select.options.length > 1) {
    select.remove(1);
  }
  
  // Reset to default and disable
  select.selectedIndex = 0;
  select.disabled = true;
}

// Create new shelf
async function createNewShelf() {
  const name = document.getElementById('newShelfName').value;
  const code = document.getElementById('newShelfCode').value;
  
  if (!name || !code) {
    showNotification('Please provide both name and location code', 'error');
    return;
  }
  
  try {
    const response = await fetch(`/api/create-shelf/${STATE.currentProject}`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': CSRF_TOKEN,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name, location_code: code })
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to create shelf');
    }
    
    const data = await response.json();
    
    // Add the new shelf to the dropdown and select it
    const shelfSelect = document.getElementById('shelfSelect');
    const option = document.createElement('option');
    option.value = data.id;
    option.textContent = `${data.name} (${data.location_code}) - ${data.project__name || STATE.currentProject}`;
    option.setAttribute('data-project', data.project__name || STATE.currentProject);
    shelfSelect.appendChild(option);
    shelfSelect.value = data.id;
    
    // Hide the form and trigger change
    document.getElementById('newShelfForm').style.display = 'none';
    handleShelfChange(data.id);
    
    showNotification('Shelf created successfully', 'success');
    
  } catch (error) {
    showNotification(error.message, 'error');
  }
}

// Cancel new shelf creation
function cancelNewShelf() {
  document.getElementById('newShelfForm').style.display = 'none';
  document.getElementById('shelfSelect').value = '';
  document.getElementById('newShelfName').value = '';
  document.getElementById('newShelfCode').value = '';
}

// Create new rack
async function createNewRack() {
  if (!STORAGE_STATE.currentShelf) {
    showNotification('Please select a shelf first', 'error');
    return;
  }
  
  const name = document.getElementById('newRackName').value;
  const code = document.getElementById('newRackCode').value;
  
  if (!name || !code) {
    showNotification('Please provide both name and location code', 'error');
    return;
  }
  
  try {
    const response = await fetch(`/api/create-rack/${STORAGE_STATE.currentShelf}`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': CSRF_TOKEN,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name, location_code: code })
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to create rack');
    }
    
    const data = await response.json();
    
    // Add the new rack to the dropdown and select it
    const rackSelect = document.getElementById('rackSelect');
    const option = document.createElement('option');
    option.value = data.id;
    option.textContent = `${data.name} (${data.location_code}) - ${data.project__name}`;
    option.setAttribute('data-shelf', data.shelf_id);
    option.setAttribute('data-project', data.project__name);
    rackSelect.appendChild(option);
    rackSelect.value = data.id;
    
    // Hide the form and trigger change
    document.getElementById('newRackForm').style.display = 'none';
    handleRackChange(data.id);
    
    showNotification('Rack created successfully', 'success');
    
  } catch (error) {
    showNotification(error.message, 'error');
  }
}

// Cancel new rack creation
function cancelNewRack() {
  document.getElementById('newRackForm').style.display = 'none';
  document.getElementById('rackSelect').value = '';
  document.getElementById('newRackName').value = '';
  document.getElementById('newRackCode').value = '';
}

// Create new box
async function createNewBox() {
  if (!STORAGE_STATE.currentRack) {
    showNotification('Please select a rack first', 'error');
    return;
  }
  
  const name = document.getElementById('newBoxName').value;
  const code = document.getElementById('newBoxCode').value;
  
  if (!name || !code) {
    showNotification('Please provide both name and location code', 'error');
    return;
  }
  
  try {
    const response = await fetch(`/api/create-box/${STORAGE_STATE.currentRack}`, {
      method: 'POST',
      headers: {
        'X-CSRFToken': CSRF_TOKEN,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name, location_code: code })
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to create box');
    }
    
    const data = await response.json();
    
    // Add the new box to the dropdown and select it
    const boxSelect = document.getElementById('boxSelect');
    const option = document.createElement('option');
    option.value = data.id;
    option.textContent = `${data.name} (${data.location_code}) - ${data.project__name}`;
    option.setAttribute('data-rack', data.rack_id);
    option.setAttribute('data-project', data.project__name);
    boxSelect.appendChild(option);
    boxSelect.value = data.id;
    
    // Hide the form
    document.getElementById('newBoxForm').style.display = 'none';
    
    showNotification('Box created successfully', 'success');
    
  } catch (error) {
    showNotification(error.message, 'error');
  }
}

// Cancel new box creation
function cancelNewBox() {
  document.getElementById('newBoxForm').style.display = 'none';
  document.getElementById('boxSelect').value = '';
  document.getElementById('newBoxName').value = '';
  document.getElementById('newBoxCode').value = '';
}

// Prepare storage data for form submission
function prepareStorageData(formData) {
  // Handle shelf
  const shelfSelect = document.getElementById('shelfSelect');
  if (shelfSelect.value === 'new') {
    formData.append('new_shelf_name', document.getElementById('newShelfName').value);
    formData.append('new_shelf_code', document.getElementById('newShelfCode').value);
  } else {
    formData.append('shelf', shelfSelect.value);
  }
  
  // Handle rack
  const rackSelect = document.getElementById('rackSelect');
  if (rackSelect.value === 'new') {
    formData.append('new_rack_name', document.getElementById('newRackName').value);
    formData.append('new_rack_code', document.getElementById('newRackCode').value);
  } else {
    formData.append('rack', rackSelect.value);
  }
  
  // Handle box
  const boxSelect = document.getElementById('boxSelect');
  if (boxSelect.value === 'new') {
    formData.append('new_box_name', document.getElementById('newBoxName').value);
    formData.append('new_box_code', document.getElementById('newBoxCode').value);
  } else {
    formData.append('box', boxSelect.value);
  }
  
  return formData;
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initSamplesManager);
