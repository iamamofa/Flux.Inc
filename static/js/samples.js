// samples.js - Improved JavaScript for samples management

// Utility Functions
function getCSRFToken() {
    const cookieValue = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];
    return cookieValue;
}

async function makeRequest(url, method, data) {
    try {
        const response = await fetch(url, {
            method,
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Request failed:', error);
        showToast('Operation failed. Please try again.', false);
        throw error;
    }
}

function showToast(message, isSuccess = true) {
    const toast = document.createElement('div');
    toast.className = `toast ${isSuccess ? 'success' : 'error'}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// DOM Elements
const domElements = {
    popups: {
        add: document.getElementById('addPopup'),
        edit: document.getElementById('editPopup'),
        retrieve: document.getElementById('retrievePopup'),
        return: document.getElementById('returnPopup'),
        delete: document.getElementById('deletePopup'),
    },
    forms: {
        add: document.getElementById('sample-form'),
        edit: document.getElementById('edit-form'),
        retrieve: document.getElementById('retrieve-form'),
        return: document.getElementById('return-form'),
    },
    filters: {
        sampleID: document.getElementById('sampleIDFilterInput'),
        sampleType: document.getElementById('sampleTypeFilterInput'),
        country: document.getElementById('countryFilterInput'),
        minVolume: document.getElementById('minVolumeFilterInput'),
        maxVolume: document.getElementById('maxVolumeFilterInput'),
        minDate: document.getElementById('minDateCreatedFilterInput'),
        maxDate: document.getElementById('maxDateCreatedFilterInput'),
        storageLocation: document.getElementById('storageLocationFilterInput'),
        sortColumn: document.getElementById('sortColumnDropdown'),
    },
    buttons: {
        reset: document.getElementById('resetButton'),
        addItem: document.getElementById('addItemBtn'),
    },
    table: document.getElementById('samplesTable'),
};

// State Management
let currentState = {
    currentItemId: null,
    currentProject: null,
    sortDirection: 'asc',
    currentSortColumn: null,
};

// Popup Management
function setupPopup(containerClass, popupId, openFunc, closeFunc) {
    const container = document.querySelector(containerClass);
    const popup = document.getElementById(popupId);
    
    container?.addEventListener("click", (e) => {
        if (e.target === container) closeFunc();
    });
    
    return { open: openFunc, close: closeFunc };
}

const popups = {
    add: setupPopup('.popup-container1', 'addPopup', showAddPopup, closeAddPopup),
    edit: setupPopup('.popup-container2', 'editPopup', showEditPopup, closeEditPopup),
    retrieve: setupPopup('.popup-container3', 'retrievePopup', showRetrievePopup, closeRetrievePopup),
    return: setupPopup('.popup-container4', 'returnPopup', showReturnPopup, closeReturnPopup),
};

// Sample CRUD Operations
function showAddPopup() {
    domElements.popups.add.style.display = 'flex';
}

function closeAddPopup() {
    domElements.popups.add.style.display = 'none';
    domElements.forms.add.reset();
}

function showEditPopup(id) {
    currentState.currentItemId = id;
    domElements.popups.edit.style.display = 'flex';
    getItemInfo();
}

function closeEditPopup() {
    domElements.popups.edit.style.display = 'none';
    domElements.forms.edit.reset();
}

function showRetrievePopup(id) {
    currentState.currentItemId = id;
    domElements.popups.retrieve.style.display = 'flex';
}

function closeRetrievePopup() {
    domElements.popups.retrieve.style.display = 'none';
    domElements.forms.retrieve.reset();
}

function showReturnPopup(id) {
    currentState.currentItemId = id;
    domElements.popups.return.style.display = 'flex';
}

function closeReturnPopup() {
    domElements.popups.return.style.display = 'none';
    domElements.forms.return.reset();
}

function showDeletePopup(projectName, id) {
    currentState.currentItemId = id;
    currentState.currentProject = projectName;
    domElements.popups.delete.style.display = 'flex';
}

function closeDeletePopup() {
    domElements.popups.delete.style.display = 'none';
}

// Update the getItemInfo function to fill the edit form
async function getItemInfo() {
    try {
        const data = await makeRequest(`/get_sample_info/${currentState.currentItemId}`, 'GET');
        
        // Fill the edit form with the retrieved data
        document.getElementById('edit_sample_id').value = data.sample_id;
        document.getElementById('edit_sample_type').value = data.sample_type;
        document.getElementById('edit_description').value = data.description;
        document.getElementById('edit_country').value = data.country;
        document.getElementById('edit_volume').value = data.volume;
        document.getElementById('edit_well_id').value = data.well_id;
        document.getElementById('edit_storage_location').value = data.storage_location;
        document.getElementById('edit_threshold_value').value = data.threshold_value;
    } catch (error) {
        console.error('Error retrieving sample information:', error);
        showToast('Failed to load sample data', false);
    }
}

async function deleteItem() {
    try {
        await makeRequest(
            `/delete_sample/${currentState.currentProject}/${currentState.currentItemId}`, 
            'DELETE'
        );
        removeTableRow(currentState.currentItemId);
        showToast('Sample deleted successfully');
        closeDeletePopup();
    } catch (error) {
        console.error('Error deleting sample:', error);
    }
}

function removeTableRow(id) {
    const row = domElements.table.querySelector(`tr[data-id="${id}"]`);
    if (row) row.remove();
}

// Form Handlers
function setupFormHandler(formElement, endpoint, method, successCallback) {
    formElement.addEventListener('submit', async (event) => {
        event.preventDefault();
        
        const formData = new FormData(formElement);
        const jsonData = {};
        formData.forEach((value, key) => {
            jsonData[key] = value;
        });

        try {
            const data = await makeRequest(
                `${endpoint}/${currentState.currentItemId}`, 
                method, 
                jsonData
            );
            
            if (successCallback) successCallback(data);
            showToast('Operation completed successfully');
        } catch (error) {
            console.error('Form submission error:', error);
        }
    });
}

// Table Operations
function refreshTableRow(id, data) {
    const row = domElements.table.querySelector(`tr[data-id="${id}"]`);
    if (!row) return;

    // Update data attributes
    row.dataset.sampleId = data.sample_id;
    row.dataset.sampleType = data.sample_type;
    row.dataset.description = data.description;
    row.dataset.country = data.country;
    row.dataset.volume = data.volume;
    row.dataset.wellId = data.well_id;
    row.dataset.storageLocation = data.storage_location;

    // Update visible cells
    const cells = row.querySelectorAll('td');
    cells[0].textContent = data.sample_id;
    cells[1].textContent = data.sample_type;
    cells[2].textContent = data.description;
    cells[3].textContent = data.country;
    cells[4].textContent = data.volume;
    cells[6].textContent = data.well_id;
    cells[7].textContent = data.storage_location;
}

function filterTable() {
    const filters = {
        sampleID: domElements.filters.sampleID.value.toLowerCase(),
        sampleType: domElements.filters.sampleType.value.toLowerCase() === 'all' ? '' : domElements.filters.sampleType.value.toLowerCase(),
        country: domElements.filters.country.value.toLowerCase(),
        minVolume: domElements.filters.minVolume.value !== '' ? parseFloat(domElements.filters.minVolume.value) : 0,
        maxVolume: domElements.filters.maxVolume.value !== '' ? parseFloat(domElements.filters.maxVolume.value) : Infinity,
        minDate: domElements.filters.minDate.value || '1900-01-01',
        maxDate: domElements.filters.maxDate.value || '9999-12-31',
        storageLocation: domElements.filters.storageLocation.value.toLowerCase(),
    };

    const rows = domElements.table.querySelectorAll('tr');
    
    rows.forEach((row) => {
        if (!row.dataset.id) return; // Skip header row
        
        const rowData = {
            sampleID: row.dataset.sampleId.toLowerCase(),
            sampleType: row.dataset.sampleType.toLowerCase(),
            country: row.dataset.country.toLowerCase(),
            volume: parseFloat(row.dataset.volume),
            dateRecorded: row.dataset.dateRecorded,
            storageLocation: row.dataset.storageLocation.toLowerCase(),
        };

        const isVisible = (
            rowData.sampleID.includes(filters.sampleID) &&
            rowData.sampleType.includes(filters.sampleType) &&
            rowData.country.includes(filters.country) &&
            rowData.volume >= filters.minVolume &&
            rowData.volume <= filters.maxVolume &&
            isDateInRange(rowData.dateRecorded, filters.minDate, filters.maxDate) &&
            rowData.storageLocation.includes(filters.storageLocation)
        );

        row.style.display = isVisible ? '' : 'none';
    });
}

function isDateInRange(date, minDate, maxDate) {
    if (!date || !minDate || !maxDate) return true;
    
    const currentDate = new Date(date);
    const min = new Date(minDate);
    const max = new Date(maxDate);

    return currentDate >= min && currentDate <= max;
}

function sortTable() {
    const columnIndex = domElements.filters.sortColumn.value;
    if (columnIndex === '0') return; // "None" selected
    
    const rows = Array.from(domElements.table.querySelectorAll('tr:not(:first-child)'));
    
    // Toggle sort direction if clicking the same column
    if (currentState.currentSortColumn === columnIndex) {
        currentState.sortDirection = currentState.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        currentState.currentSortColumn = columnIndex;
        currentState.sortDirection = 'asc';
    }
    
    rows.sort((a, b) => {
        const valA = getCellValue(a, columnIndex);
        const valB = getCellValue(b, columnIndex);
        
        return currentState.sortDirection === 'asc' 
            ? compareValues(valA, valB)
            : compareValues(valB, valA);
    });
    
    // Reattach sorted rows
    rows.forEach(row => domElements.table.appendChild(row));
}

function getCellValue(row, columnIndex) {
    const column = row.querySelector(`td:nth-child(${columnIndex})`);
    if (!column) return '';
    
    const value = column.textContent.trim();
    
    // Special handling for numeric columns
    if (columnIndex === '5') { // Volume column
        return parseFloat(value) || 0;
    }
    
    // Special handling for date columns
    if (columnIndex === '6') { // Date Recorded column
        return new Date(value).getTime();
    }
    
    return value.toLowerCase();
}

function compareValues(a, b) {
    if (typeof a === 'number' && typeof b === 'number') {
        return a - b;
    }
    return String(a).localeCompare(String(b));
}

function resetFilters() {
    // Clear all filter inputs
    Object.values(domElements.filters).forEach(filter => {
        if (filter.tagName === 'SELECT') {
            filter.value = filter.querySelector('option[value="0"]') ? '0' : 'All';
        } else {
            filter.value = '';
        }
    });
    
    // Reset sort state
    currentState.sortDirection = 'asc';
    currentState.currentSortColumn = null;
    
    // Show all rows
    const rows = domElements.table.querySelectorAll('tr');
    rows.forEach(row => row.style.display = '');
}

// Event Listeners
function initializeEventListeners() {
    // Filter events
    domElements.filters.sampleID.addEventListener('input', debounce(filterTable, 300));
    domElements.filters.sampleType.addEventListener('input', debounce(filterTable, 300));
    domElements.filters.country.addEventListener('input', debounce(filterTable, 300));
    domElements.filters.minVolume.addEventListener('input', debounce(filterTable, 300));
    domElements.filters.maxVolume.addEventListener('input', debounce(filterTable, 300));
    domElements.filters.minDate.addEventListener('change', debounce(filterTable, 300));
    domElements.filters.maxDate.addEventListener('change', debounce(filterTable, 300));
    domElements.filters.storageLocation.addEventListener('input', debounce(filterTable, 300));
    domElements.filters.sortColumn.addEventListener('change', sortTable);
    
    // Button events
    domElements.buttons.reset.addEventListener('click', resetFilters);
    domElements.buttons.addItem.addEventListener('click', showAddPopup);
    
    // Form submissions
    setupFormHandler(
        domElements.forms.edit, 
        '/edit_sample', 
        'PUT', 
        (data) => {
            refreshTableRow(currentState.currentItemId, data);
            closeEditPopup();
        }
    );
    
    setupFormHandler(
        domElements.forms.retrieve, 
        '/retrieve_sample', 
        'PUT', 
        (data) => {
            refreshTableRow(currentState.currentItemId, data);
            closeRetrievePopup();
            domElements.filters.retrieveFilterInput.value = '';
        }
    );
    
    setupFormHandler(
        domElements.forms.return, 
        '/return_sample', 
        'PUT', 
        (data) => {
            refreshTableRow(currentState.currentItemId, data);
            closeReturnPopup();
            domElements.filters.returnFilterInput.value = '';
        }
    );
    
    // Add form needs special handling since it creates a new item
    domElements.forms.add.addEventListener('submit', async (event) => {
        event.preventDefault();
        
        const formData = new FormData(domElements.forms.add);
        const jsonData = {};
        formData.forEach((value, key) => {
            jsonData[key] = value;
        });

        try {
            const data = await makeRequest(
                domElements.forms.add.action, 
                'POST', 
                jsonData
            );
            
            // Add new row to table
            addNewRowToTable(data);
            showToast('Sample added successfully');
            closeAddPopup();
        } catch (error) {
            console.error('Error adding sample:', error);
        }
    });
}

function addNewRowToTable(sampleData) {
    const newRow = document.createElement('tr');
    newRow.dataset.id = sampleData.id;
    newRow.dataset.sampleId = sampleData.sample_id;
    newRow.dataset.sampleType = sampleData.sample_type;
    newRow.dataset.description = sampleData.description;
    newRow.dataset.country = sampleData.country;
    newRow.dataset.volume = sampleData.volume;
    newRow.dataset.dateRecorded = sampleData.date_recorded;
    newRow.dataset.wellId = sampleData.well_id;
    newRow.dataset.storageLocation = sampleData.storage_location;

    newRow.innerHTML = `
        <td>${sampleData.sample_id}</td>
        <td>${sampleData.sample_type}</td>
        <td>${sampleData.description}</td>
        <td>${sampleData.country}</td>
        <td>${sampleData.volume}</td>
        <td>${sampleData.date_recorded}</td>
        <td>${sampleData.well_id}</td>
        <td>${sampleData.storage_location}</td>
        <td>
            <!-- Action buttons would go here -->
        </td>
    `;

    domElements.table.appendChild(newRow);
}

// Utility function to debounce rapid events
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();

    Object.values(domElements.popups).forEach(popup => {
        if (popup) popup.style.display = 'none';
    });
    
    // Make functions available globally if needed
    window.showEditPopup = showEditPopup;
    window.showRetrievePopup = showRetrievePopup;
    window.showReturnPopup = showReturnPopup;
    window.showDeletePopup = showDeletePopup;
    window.deleteItem = deleteItem;
    window.closeDeletePopup = closeDeletePopup;
});
