// samples.js - Optimized JavaScript for samples management

// ==============================================
// UTILITY FUNCTIONS
// ==============================================

function getCSRFToken() {
    return document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];
}

async function makeRequest(url, method, data = null) {
    try {
        const options = {
            method,
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'Content-Type': 'application/json',
            }
        };
        
        if (data) options.body = JSON.stringify(data);
        
        const response = await fetch(url, options);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
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

function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

function isDateInRange(date, minDate, maxDate) {
    if (!date) return true;
    const currentDate = new Date(date);
    const min = new Date(minDate);
    const max = new Date(maxDate);
    return currentDate >= min && currentDate <= max;
}

// ==============================================
// DOM ELEMENTS & STATE MANAGEMENT
// ==============================================

const dom = {
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

const state = {
    currentItemId: null,
    currentProject: null,
    sortDirection: 'asc',
    currentSortColumn: null,
};

// ==============================================
// POPUP MANAGEMENT
// ==============================================

function setupPopup(containerClass, popupId) {
    const container = document.querySelector(containerClass);
    const popup = document.getElementById(popupId);
    
    if (!container || !popup) return;
    
    container.addEventListener("click", (e) => {
        if (e.target === container) hidePopup(popupId);
    });
}

function showPopup(popupId) {
    if (dom.popups[popupId]) {
        dom.popups[popupId].style.display = 'flex';
    }
}

function hidePopup(popupId) {
    if (dom.popups[popupId]) {
        dom.popups[popupId].style.display = 'none';
        if (dom.forms[popupId]) dom.forms[popupId].reset();
    }
}

// ==============================================
// SAMPLE CRUD OPERATIONS
// ==============================================

async function getItemInfo() {
    try {
        const data = await makeRequest(`/get_sample_info/${state.currentItemId}`, 'GET');
        
        // Fill the edit form with the retrieved data
        const form = document.getElementById('edit-form');
        if (!form) return;
        
        form.elements.sample_id.value = data.sample_id;
        form.elements.sample_type.value = data.sample_type;
        form.elements.description.value = data.description;
        form.elements.country.value = data.country;
        form.elements.volume.value = data.volume;
        form.elements.well_id.value = data.well_id;
        form.elements.storage_location.value = data.storage_location;
        form.elements.threshold_value.value = data.threshold_value;
    } catch (error) {
        console.error('Error retrieving sample information:', error);
        showToast('Failed to load sample data', false);
    }
}

async function deleteItem() {
    try {
        await makeRequest(
            `/delete_sample/${state.currentProject}/${state.currentItemId}`, 
            'DELETE'
        );
        removeTableRow(state.currentItemId);
        showToast('Sample deleted successfully');
        hidePopup('delete');
    } catch (error) {
        console.error('Error deleting sample:', error);
    }
}

// ==============================================
// TABLE OPERATIONS
// ==============================================

function removeTableRow(id) {
    const row = dom.table.querySelector(`tr[data-id="${id}"]`);
    if (row) row.remove();
}

function refreshTableRow(id, data) {
    const row = dom.table.querySelector(`tr[data-id="${id}"]`);
    if (!row) return;

    row.dataset.sampleId = data.sample_id;
    row.dataset.sampleType = data.sample_type;
    row.dataset.description = data.description;
    row.dataset.country = data.country;
    row.dataset.volume = data.volume;
    row.dataset.wellId = data.well_id;
    row.dataset.storageLocation = data.storage_location;

    const cells = row.querySelectorAll('td');
    cells[0].textContent = data.sample_id;
    cells[1].setAttribute('data-fulltext', data.sample_type);
    cells[1].textContent = truncateText(data.sample_type, 15);
    cells[2].setAttribute('data-fulltext', data.description);
    cells[2].textContent = truncateText(data.description, 20);
    cells[3].textContent = data.country;
    cells[4].textContent = data.volume;
    cells[6].textContent = data.well_id;
    cells[7].setAttribute('data-fulltext', data.storage_location);
    cells[7].textContent = truncateText(data.storage_location, 15);
}

function truncateText(text, maxLength) {
  return text.length > maxLength 
    ? text.substring(0, maxLength - 3) + '...' 
    : text;
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
        <td class="actions">
            <button onclick="showEditPopup('${sampleData.id}')">Edit</button>
            <button onclick="showDeletePopup('${sampleData.project}', '${sampleData.id}')">Delete</button>
        </td>
    `;

    dom.table.appendChild(newRow);
}

// ==============================================
// FILTERING & SORTING
// ==============================================

function filterTable() {
    const filters = {
        sampleID: dom.filters.sampleID.value.toLowerCase(),
        sampleType: dom.filters.sampleType.value.toLowerCase() === 'all' ? '' : dom.filters.sampleType.value.toLowerCase(),
        country: dom.filters.country.value.toLowerCase(),
        minVolume: dom.filters.minVolume.value ? parseFloat(dom.filters.minVolume.value) : 0,
        maxVolume: dom.filters.maxVolume.value ? parseFloat(dom.filters.maxVolume.value) : Infinity,
        minDate: dom.filters.minDate.value || '1900-01-01',
        maxDate: dom.filters.maxDate.value || '9999-12-31',
        storageLocation: dom.filters.storageLocation.value.toLowerCase(),
    };

    const rows = dom.table.querySelectorAll('tr');
    
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

function sortTable() {
    const columnIndex = dom.filters.sortColumn.value;
    if (columnIndex === '0') return; // "None" selected
    
    const rows = Array.from(dom.table.querySelectorAll('tr:not(:first-child)'));
    
    // Toggle sort direction if same column
    if (state.currentSortColumn === columnIndex) {
        state.sortDirection = state.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        state.currentSortColumn = columnIndex;
        state.sortDirection = 'asc';
    }
    
    rows.sort((a, b) => {
        const valA = getCellValue(a, columnIndex);
        const valB = getCellValue(b, columnIndex);
        
        return state.sortDirection === 'asc' 
            ? compareValues(valA, valB)
            : compareValues(valB, valA);
    });
    
    // Reattach sorted rows
    rows.forEach(row => dom.table.appendChild(row));
}

function getCellValue(row, columnIndex) {
    const column = row.querySelector(`td:nth-child(${columnIndex})`);
    if (!column) return '';
    
    const value = column.textContent.trim();
    
    // Numeric columns
    if (columnIndex === '5') return parseFloat(value) || 0;
    
    // Date columns
    if (columnIndex === '6') return new Date(value).getTime();
    
    return value.toLowerCase();
}

function compareValues(a, b) {
    if (typeof a === 'number' && typeof b === 'number') return a - b;
    return String(a).localeCompare(String(b));
}

function resetFilters() {
    // Clear all filter inputs
    Object.values(dom.filters).forEach(filter => {
        if (filter) filter.value = filter.tagName === 'SELECT' ? '0' : '';
    });
    
    // Reset sort state
    state.sortDirection = 'asc';
    state.currentSortColumn = null;
    
    // Show all rows
    const rows = dom.table.querySelectorAll('tr');
    rows.forEach(row => row.style.display = '');
}

// ==============================================
// FORM HANDLERS
// ==============================================

function setupFormHandler(form, endpoint, method, onSuccess) {
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = new FormData(form);
        const jsonData = Object.fromEntries(formData.entries());

        try {
            const url = typeof endpoint === 'function' 
                ? endpoint(state.currentItemId) 
                : endpoint;
            
            const data = await makeRequest(url, method, jsonData);
            if (onSuccess) onSuccess(data);
            showToast('Operation completed successfully');
        } catch (error) {
            console.error('Form submission error:', error);
        }
    });
}

// ==============================================
// DROPDOWN FUNCTIONS (NEW SECTION)
// ==============================================

function setupDropdowns() {
  // Toggle dropdowns when clicking triggers
  document.querySelectorAll('.dropdown-trigger').forEach(trigger => {
    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      trigger.closest('.dropdown').classList.toggle('active');
    });
  });

  // Close all dropdowns when clicking outside
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.dropdown')) {
      document.querySelectorAll('.dropdown').forEach(dropdown => {
        dropdown.classList.remove('active');
      });
    }
  });
}

// ==============================================
// INITIALIZATION
// ==============================================

function initialize() {
    // Setup popups
    setupPopup('.popup-container1', 'add');
    setupPopup('.popup-container2', 'edit');
    setupPopup('.popup-container3', 'retrieve');
    setupPopup('.popup-container4', 'return');
    setupPopup('.popup-container5', 'delete');

    // Setup dropdowns
    setupDropdowns();

    // Form handlers
    setupFormHandler(dom.forms.edit, id => `/edit_sample/${id}`, 'PUT', (data) => {
        refreshTableRow(state.currentItemId, data);
        hidePopup('edit');
    });
    
    setupFormHandler(dom.forms.retrieve, id => `/retrieve_sample/${id}`, 'PUT', (data) => {
        refreshTableRow(state.currentItemId, data);
        hidePopup('retrieve');
    });
    
    setupFormHandler(dom.forms.return, id => `/return_sample/${id}`, 'PUT', (data) => {
        refreshTableRow(state.currentItemId, data);
        hidePopup('return');
    });

    // Add form (special case)
    if (dom.forms.add) {
        dom.forms.add.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = new FormData(dom.forms.add);
            const jsonData = Object.fromEntries(formData.entries());

            try {
                const data = await makeRequest(dom.forms.add.action, 'POST', jsonData);
                addNewRowToTable(data);
                showToast('Sample added successfully');
                hidePopup('add');
            } catch (error) {
                console.error('Error adding sample:', error);
            }
        });
    }

    // Filter events
    const filterInputs = [
        dom.filters.sampleID,
        dom.filters.sampleType,
        dom.filters.country,
        dom.filters.minVolume,
        dom.filters.maxVolume,
        dom.filters.storageLocation
    ];
    
    filterInputs.forEach(input => {
        if (input) input.addEventListener('input', debounce(filterTable, 300));
    });

    // Date filter events
    if (dom.filters.minDate) dom.filters.minDate.addEventListener('change', filterTable);
    if (dom.filters.maxDate) dom.filters.maxDate.addEventListener('change', filterTable);

    // Sort event
    if (dom.filters.sortColumn) {
        dom.filters.sortColumn.addEventListener('change', sortTable);
    }

    // Button events
    if (dom.buttons.reset) dom.buttons.reset.addEventListener('click', resetFilters);
    if (dom.buttons.addItem) dom.buttons.addItem.addEventListener('click', () => showPopup('add'));

    // Hide all popups on load
    Object.values(dom.popups).forEach(popup => {
        if (popup) popup.style.display = 'none';
    });
}

// Make functions available globally
window.showEditPopup = (id) => {
    state.currentItemId = id;
    showPopup('edit');
    getItemInfo();
};

window.showRetrievePopup = (id) => {
    state.currentItemId = id;
    showPopup('retrieve');
};

window.showReturnPopup = (id) => {
    state.currentItemId = id;
    showPopup('return');
};

window.showDeletePopup = (projectName, id) => {
    state.currentItemId = id;
    state.currentProject = projectName;
    showPopup('delete');
};

window.deleteItem = deleteItem;
window.closeDeletePopup = () => hidePopup('delete');

// Initialize the application
document.addEventListener('DOMContentLoaded', initialize);
