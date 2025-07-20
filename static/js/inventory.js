// Utility functions
function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

function showLoading(button) {
    button.dataset.originalText = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="spinner">Loading...</span>';
}

function resetLoading(button) {
    button.disabled = false;
    button.innerHTML = button.dataset.originalText;
}

// Table Management
function initTable(tableSelector, options) {
    const table = document.querySelector(tableSelector);
    if (!table) return;

    if (options.sortOptions) {
        initTableSorting(table, options.sortOptions);
    }

    if (options.filterOptions) {
        initTableFiltering(table, options.filterOptions);
    }
}

function initTableSorting(table, sortOptions) {
    const headers = table.querySelectorAll('th[data-sort]');
    
    headers.forEach(header => {
        header.addEventListener('click', () => {
            const sortKey = header.getAttribute('data-sort');
            const sortType = sortOptions[sortKey].type;
            const isAscending = !header.classList.contains('asc');
            
            headers.forEach(h => h.classList.remove('asc', 'desc'));
            header.classList.add(isAscending ? 'asc' : 'desc');
            sortTable(table, sortKey, sortType, isAscending);
        });
    });
}

function sortTable(table, sortKey, sortType, ascending) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    
    rows.sort((a, b) => {
        const aValue = a.getAttribute(`data-${sortKey.replace('_', '-')}`);
        const bValue = b.getAttribute(`data-${sortKey.replace('_', '-')}`);
        
        if (sortType === 'number') {
            return ascending ? 
                parseFloat(aValue) - parseFloat(bValue) : 
                parseFloat(bValue) - parseFloat(aValue);
        } else if (sortType === 'date') {
            return ascending ? 
                new Date(aValue) - new Date(bValue) : 
                new Date(bValue) - new Date(aValue);
        } else {
            return ascending ? 
                aValue.localeCompare(bValue) : 
                bValue.localeCompare(aValue);
        }
    });
    
    rows.forEach(row => tbody.appendChild(row));
}

function initTableFiltering(table, filterOptions) {
    Object.entries(filterOptions).forEach(([key, selector]) => {
        if (typeof selector === 'object') {
            if (selector.min) {
                const input = document.querySelector(selector.min);
                if (input) input.addEventListener('input', () => applyFilters(table, filterOptions));
            }
            if (selector.max) {
                const input = document.querySelector(selector.max);
                if (input) input.addEventListener('input', () => applyFilters(table, filterOptions));
            }
        } else {
            const input = document.querySelector(selector);
            if (input) input.addEventListener('input', () => applyFilters(table, filterOptions));
        }
    });
    
    const resetButton = document.getElementById('resetButton');
    if (resetButton) {
        resetButton.addEventListener('click', () => {
            Object.values(filterOptions).forEach(selector => {
                if (typeof selector === 'object') {
                    if (selector.min) document.querySelector(selector.min).value = '';
                    if (selector.max) document.querySelector(selector.max).value = '';
                } else {
                    const input = document.querySelector(selector);
                    if (input) input.value = '';
                }
            });
            applyFilters(table, filterOptions);
        });
    }
}

function applyFilters(table, filterOptions) {
    const rows = table.querySelectorAll('tbody tr');
    
    rows.forEach(row => {
        let shouldShow = true;
        
        Object.entries(filterOptions).forEach(([key, selector]) => {
            if (typeof selector === 'object') {
                const minInput = selector.min ? document.querySelector(selector.min) : null;
                const maxInput = selector.max ? document.querySelector(selector.max) : null;
                
                const rowValue = parseFloat(row.getAttribute(`data-${key.replace('_', '-')}`)) || 0;
                const minValue = minInput?.value ? parseFloat(minInput.value) : -Infinity;
                const maxValue = maxInput?.value ? parseFloat(maxInput.value) : Infinity;
                    
                if (rowValue < minValue || rowValue > maxValue) {
                    shouldShow = false;
                }
            } else {
                const input = document.querySelector(selector);
                if (!input) return;
                
                const filterValue = input.value.toLowerCase();
                if (!filterValue) return;
                
                const rowValue = row.getAttribute(`data-${key.replace('_', '-')}`)?.toLowerCase() || '';
                
                if (key === 'sample_type' && filterValue === 'all') {
                    return;
                }
                
                if (!rowValue.includes(filterValue)) {
                    shouldShow = false;
                }
            }
        });
        
        row.style.display = shouldShow ? '' : 'none';
    });
}

// Popup Management
function initPopups(config) {
    window.popupConfig = config;
}

function showPopup(type, itemId = null) {
    const config = window.popupConfig[type];
    if (!config) return;
    
    const popup = document.getElementById('basePopup');
    const popupContent = popup.querySelector('.popup-body');
    
    popup.querySelector('.popup-title').textContent = config.title;
    popupContent.innerHTML = typeof config.template === 'function' 
        ? config.template(itemId) 
        : templates[config.template];

    if (itemId) popup.dataset.itemId = itemId;
    popup.dataset.handler = type;
    popup.style.display = 'flex';

    const firstInput = popupContent.querySelector('input, select, textarea');
    if (firstInput) firstInput.focus();
}

function closePopup(closeButton) {
    const popup = closeButton.closest('.popup-container');
    popup.style.display = 'none';

    const form = popup.querySelector('form');
    if (form) {
        form.reset();
        form.querySelectorAll('.error-message').forEach(el => el.remove());
        form.querySelectorAll('.has-error').forEach(el => el.classList.remove('has-error'));
    }
}

// Specific popup functions
function showAddPopup() {
    showPopup('add');
}

function showEditPopup(itemId) {
    const url = window.location.pathname.includes('reagents') 
        ? `/get_reagent_info/${itemId}`
        : `/get_sample_info/${itemId}`;

    fetch(url)
        .then(response => response.json())
        .then(data => {
            showPopup('edit', itemId);
            const form = document.querySelector('#basePopup form');
            if (form) populateForm(form, data);
        })
        .catch(error => console.error('Error loading item:', error));
}

function populateForm(form, data) {
    Object.entries(data).forEach(([key, value]) => {
        const input = form.querySelector(`[name="${key}"]`);
        if (input) {
            if (input.type === 'checkbox') {
                input.checked = value;
            } else {
                input.value = value || '';
            }
        }
    });
}

function showDeletePopup(projectName, itemId) {
    const popup = document.getElementById('deletePopup');
    popup.dataset.projectName = projectName;
    popup.dataset.itemId = itemId;
    popup.style.display = 'flex';
}

// Form submission handlers
function submitAddForm(form) {
    const submitButton = form.querySelector('button[type="submit"]');
    showLoading(submitButton);
    
    fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(handleResponse)
    .then(data => {
        if (data.success) {
            addNewRowToTable(data.new_item);
            closePopup(form.closest('.popup-container'));
        } else {
            showFormErrors(form, data.errors);
        }
    })
    .catch(handleError)
    .finally(() => resetLoading(submitButton));

    return false;
}

function submitEditForm(form) {
    const submitButton = form.querySelector('button[type="submit"]');
    showLoading(submitButton);
    const itemId = form.closest('.popup-container').dataset.itemId;
    
    const url = window.location.pathname.includes('reagents')
        ? `/edit_reagent/${itemId}`
        : `/edit_sample/${itemId}`;
    
    fetch(url, {
        method: 'PUT',
        body: new FormData(form),
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(handleResponse)
    .then(data => {
        if (data.success) {
            updateTableRow(itemId, data.updated_item);
            closePopup(form.closest('.popup-container'));
        } else {
            showFormErrors(form, data.errors);
        }
    })
    .catch(handleError)
    .finally(() => resetLoading(submitButton));

    return false;
}

function submitRetrieveForm(form) {
    const submitButton = form.querySelector('button[type="submit"]');
    showLoading(submitButton);
    
    const isReagent = window.location.pathname.includes('reagents');
    const itemId = form.closest('.popup-container').dataset.itemId;
    const url = isReagent 
        ? `/retrieve_reagent/${itemId}`
        : `/retrieve_sample/${itemId}`;

    fetch(url, {
        method: 'POST',
        body: new FormData(form),
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(handleResponse)
    .then(data => {
        if (data.success) {
            updateTableRow(itemId, data.updated_item);
            closePopup(form.closest('.popup-container'));
        } else {
            showFormErrors(form, data.errors);
        }
    })
    .catch(handleError)
    .finally(() => resetLoading(submitButton));

    return false;
}

function submitReturnForm(form) {
    const submitButton = form.querySelector('button[type="submit"]');
    showLoading(submitButton);
    
    const isReagent = window.location.pathname.includes('reagents');
    const itemId = form.closest('.popup-container').dataset.itemId;
    const url = isReagent 
        ? `/return_reagent/${itemId}`
        : `/return_sample/${itemId}`;

    fetch(url, {
        method: 'POST',
        body: new FormData(form),
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(handleResponse)
    .then(data => {
        if (data.success) {
            updateTableRow(itemId, data.updated_item);
            closePopup(form.closest('.popup-container'));
        } else {
            showFormErrors(form, data.errors);
        }
    })
    .catch(handleError)
    .finally(() => resetLoading(submitButton));

    return false;
}

function deleteItem() {
    const popup = document.getElementById('deletePopup');
    const submitButton = popup.querySelector('.btn-danger');
    showLoading(submitButton);
    const { projectName, itemId } = popup.dataset;

    const url = window.location.pathname.includes('reagents')
        ? `/delete_reagent/${projectName}/${itemId}`
        : `/delete_sample/${projectName}/${itemId}`;

    fetch(url, {
        method: 'DELETE',
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'Content-Type': 'application/json',
        }
    })
    .then(handleResponse)
    .then(data => {
        if (data.success) {
            document.querySelector(`tr[data-id="${itemId}"]`)?.remove();
            closePopup(popup.querySelector('.popup-close'));
        }
    })
    .catch(handleError)
    .finally(() => resetLoading(submitButton));
}

function addNewRowToTable(itemData) {
    const isReagent = window.location.pathname.includes('reagents');
    const table = document.querySelector(isReagent ? '#reagentsTable tbody' : '#samplesTable tbody');
    if (!table) return;

    const newRow = document.createElement('tr');
    newRow.dataset.id = itemData.id;
    Object.entries(itemData).forEach(([key, value]) => {
        newRow.dataset[key.replace('_', '-')] = value;
    });

    if (isReagent) {
        newRow.innerHTML = `
            <td>${itemData.name}</td>
            <td>${itemData.product_code}</td>
            <td>${itemData.pack_size_rem} / ${itemData.pack_size}</td>
            <td>${itemData.quantity}</td>
            <td>${itemData.date_recorded}</td>
            <td>${itemData.expiry_date}</td>
            <td>${itemData.storage_location}</td>
            <td>${buildActionButtons(itemData.id)}</td>
        `;
    } else {
        newRow.innerHTML = `
            <td>${itemData.sample_id}</td>
            <td>${itemData.sample_type}</td>
            <td>${itemData.description}</td>
            <td>${itemData.country}</td>
            <td>${itemData.volume}</td>
            <td>${itemData.date_recorded}</td>
            <td>${itemData.well_id}</td>
            <td>${itemData.storage_location}</td>
            <td>${buildActionButtons(itemData.id)}</td>
        `;
    }

    table.appendChild(newRow);
}

function buildActionButtons(itemId) {
    const isReagent = window.location.pathname.includes('reagents');
    return `
        <div class="dropdown">
            <button class="btn btn-icon">. . .</button>
            <div class="dropdown-content">
                <a href="#" onclick="showRetrievePopup('${itemId}')">Retrieve</a>
                <a href="#" onclick="showReturnPopup('${itemId}')">Return</a>
                {% if user == project.project_manager or user in project.project_editors.all %}
                <hr>
                <a href="#" onclick="showEditPopup('${itemId}')">Edit</a>
                <a href="#" onclick="showDeletePopup('{{ project.name }}','${itemId}')">Delete</a>
                {% endif %}
            </div>
        </div>
    `;
}

function updateTableRow(itemId, itemData) {
    const row = document.querySelector(`tr[data-id="${itemId}"]`);
    if (!row) return;

    Object.entries(itemData).forEach(([key, value]) => {
        row.dataset[key.replace('_', '-')] = value;
    });

    const isReagent = window.location.pathname.includes('reagents');
    if (isReagent) {
        row.cells[0].textContent = itemData.name;
        row.cells[1].textContent = itemData.product_code;
        row.cells[2].textContent = `${itemData.pack_size_rem} / ${itemData.pack_size}`;
        row.cells[3].textContent = itemData.quantity;
        row.cells[4].textContent = itemData.date_recorded;
        row.cells[5].textContent = itemData.expiry_date;
        row.cells[6].textContent = itemData.storage_location;
    } else {
        row.cells[0].textContent = itemData.sample_id;
        row.cells[1].textContent = itemData.sample_type;
        row.cells[2].textContent = itemData.description;
        row.cells[3].textContent = itemData.country;
        row.cells[4].textContent = itemData.volume;
        row.cells[5].textContent = itemData.date_recorded;
        row.cells[6].textContent = itemData.well_id;
        row.cells[7].textContent = itemData.storage_location;
    }
}

// Error Handling
function showFormErrors(form, errors) {
    form.querySelectorAll('.error-message').forEach(el => el.remove());
    form.querySelectorAll('.has-error').forEach(el => el.classList.remove('has-error'));

    if (!errors) {
        showGenericError(form);
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

function showGenericError(form) {
    const errorEl = document.createElement('div');
    errorEl.className = 'error-message mb-4';
    errorEl.textContent = 'An unexpected error occurred';
    form.prepend(errorEl);
}

function handleResponse(response) {
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
}

function handleError(error) {
    console.error('Error:', error);
    alert('An error occurred. Please try again.');
}

// Templates
const templates = {
    // Sample Forms
    addSampleForm: `
        <form id="sample-form" method="POST" action="{% url 'add_sample' project_name=project.name %}">
            {% csrf_token %}
            <div class="form-group">
                <label for="sample_id">Sample ID</label>
                <input type="text" name="sample_id" id="sample_id" required>
            </div>
            <div class="form-group">
                <label for="edit-sample_type">Type</label>
                <select name="sample_type" id="edit-sample_type" required class="filter-input">
                    <option value="Bacteria">Bacteria</option>
                    <option value="Fungi">Fungi</option>
                    <option value="Parasite">Parasite</option>
                    <option value="Virus">Virus</option>
                </select>
            </div>
            <div class="form-group">
                <label for="description">Description</label>
                <textarea name="description" id="description" rows="3" class="filter-input"></textarea>
            </div>
            <div class="form-group">
                <label for="country">Country</label>
                <input type="text" name="country" id="country" required class="filter-input">
            </div>
            <div class="form-group">
                <label for="volume">Volume (ml)</label>
                <input type="number" name="volume" id="volume" required min="0" step="0.1" class="filter-input">
            </div>
            <div class="form-group">
                <label for="well_id">Well ID</label>
                <input type="text" name="well_id" id="well_id" required class="filter-input">
            </div>
            <div class="form-group">
                <label for="storage_location">Storage Location</label>
                <input type="text" name="storage_location" id="storage_location" required class="filter-input">
            </div>
            <div class="form-group">
                <label for="threshold_value">Threshold Volume (ml)</label>
                <input type="number" name="threshold_value" id="threshold_value" required min="0" step="0.1" class="filter-input">
            </div>
            <div class="form-actions">
                <button type="submit" class="btn btn-primary">Add</button>
            </div>
        </form>
    `,
    editSampleForm: `
        <form id="edit-form" method="POST">
            {% csrf_token %}
            <div class="form-group">
                <label for="edit-sample_id">Sample ID</label>
                <input type="text" name="sample_id" id="edit-sample_id" required class="filter-input">
            </div>
            <div class="form-group">
                <label for="edit-sample_type">Type</label>
                <select name="sample_type" id="edit-sample_type" required class="filter-input">
                    <option value="Bacteria">Bacteria</option>
                    <option value="Fungi">Fungi</option>
                    <option value="Parasite">Parasite</option>
                    <option value="Virus">Virus</option>
                </select>
            </div>
            <div class="form-group">
                <label for="description">Description</label>
                <textarea name="description" id="description" rows="3" class="filter-input"></textarea>
            </div>
            <div class="form-group">
                <label for="country">Country</label>
                <input type="text" name="country" id="country" required class="filter-input">
            </div>
            <div class="form-group">
                <label for="volume">Volume (ml)</label>
                <input type="number" name="volume" id="volume" required min="0" step="0.1" class="filter-input">
            </div>
            <div class="form-group">
                <label for="well_id">Well ID</label>
                <input type="text" name="well_id" id="well_id" required class="filter-input">
            </div>
            <div class="form-group">
                <label for="storage_location">Storage Location</label>
                <input type="text" name="storage_location" id="storage_location" required class="filter-input">
            </div>
            <div class="form-group">
                <label for="threshold_value">Threshold Volume (ml)</label>
                <input type="number" name="threshold_value" id="threshold_value" required min="0" step="0.1" class="filter-input">
            </div>
            <div class="form-actions">
                <button type="submit" class="btn btn-primary">Save Changes</button>
            </div>
        </form>
    `,
    retrieveSampleForm: `
        <form id="retrieve-sample-form">
            {% csrf_token %}
            <div class="form-group">
                <label for="retrieve-volume">Volume (ml)</label>
                <input type="number" name="amount" id="retrieve-volume" required min="0" step="0.1" class="filter-input">
            </div>
            <div class="form-actions">
                <button type="submit" class="btn btn-primary">Retrieve</button>
            </div>
        </form>
    `,
    returnSampleForm: `
        <form id="return-sample-form">
            {% csrf_token %}
            <div class="form-group">
                <label for="return-volume">Volume (ml)</label>
                <input type="number" name="amount" id="return-volume" required min="0" step="0.1" class="filter-input">
            </div>
            <div class="form-actions">
                <button type="submit" class="btn btn-primary">Return</button>
            </div>
        </form>
    `,
    
    // Reagent Forms
    addReagentForm: `
        <form id="reagent-form" method="POST" action="{% url 'add_reagent' project_name=project.name %}">
            {% csrf_token %}
            <div class="form-group">
                <label for="name">Name</label>
                <input type="text" name="name" id="name" required>
            </div>
            <div class="form-group">
                <label for="product_code">Product Code</label>
                <input type="text" name="product_code" id="product_code" required>
            </div>
            <div class="form-group">
                <label for="pack_size">Pack Size</label>
                <input type="text" name="pack_size" id="pack_size" required>
            </div>
            <div class="form-group">
                <label for="quantity">Quantity</label>
                <input type="number" name="quantity" id="quantity" required min="0" step="0.01">
            </div>
            <div class="form-group">
                <label for="expiry_date">Expiry Date</label>
                <input type="date" name="expiry_date" id="expiry_date" required>
            </div>
            <div class="form-group">
                <label for="storage_location">Storage Location</label>
                <input type="text" name="storage_location" id="storage_location" required>
            </div>
            <div class="form-group">
                <label for="threshold_value">Threshold Value</label>
                <input type="number" name="threshold_value" id="threshold_value" required min="0">
            </div>
            <div class="form-actions">
                <button type="submit" class="btn btn-primary">Add</button>
            </div>
        </form>
    `,
    editReagentForm: `
        <form id="edit-form" method="POST">
            {% csrf_token %}
            <div class="form-group">
                <label for="edit-name">Name</label>
                <input type="text" name="name" id="edit-name" required>
            </div>
            <div class="form-group">
                <label for="edit-product_code">Product Code</label>
                <input type="text" name="product_code" id="edit-product_code" required>
            </div>
            <div class="form-group">
                <label for="edit-pack_size">Pack Size</label>
                <input type="text" name="pack_size" id="edit-pack_size" required>
            </div>
            <div class="form-group">
                <label for="edit-quantity">Quantity</label>
                <input type="number" name="quantity" id="edit-quantity" required min="0" step="0.01">
            </div>
            <div class="form-group">
                <label for="edit-expiry_date">Expiry Date</label>
                <input type="date" name="expiry_date" id="edit-expiry_date" required>
            </div>
            <div class="form-group">
                <label for="edit-storage_location">Storage Location</label>
                <input type="text" name="storage_location" id="edit-storage_location" required>
            </div>
            <div class="form-group">
                <label for="edit-threshold_value">Threshold Value</label>
                <input type="number" name="threshold_value" id="edit-threshold_value" required min="0">
            </div>
            <div class="form-actions">
                <button type="submit" class="btn btn-primary">Save Changes</button>
            </div>
        </form>
    `,
    retrieveReagentForm: `
        <form id="retrieve-reagent-form">
            {% csrf_token %}
            <div class="form-group">
                <label for="retrieve-by">Retrieve By</label>
                <select class="filter-input" id="retrieve-by" name="retrieve_by" required>
                    <option value="Pack size">Pack size</option>
                    <option value="Quantity">Quantity</option>
                </select>
            </div>
            <div class="form-group">
                <label for="retrieve-amount">Amount</label>
                <input type="number" name="amount" id="retrieve-amount" required min="0" step="0.01" class="filter-input">
            </div>
            <div class="form-actions">
                <button type="submit" class="btn btn-primary">Retrieve</button>
            </div>
        </form>
    `,
    returnReagentForm: `
        <form id="return-reagent-form">
            {% csrf_token %}
            <div class="form-group">
                <label for="return-by">Return By</label>
                <select class="filter-input" id="return-by" name="return_by" required>
                    <option value="Pack size">Pack size</option>
                    <option value="Quantity">Quantity</option>
                </select>
            </div>
            <div class="form-group">
                <label for="return-amount">Amount</label>
                <input type="number" name="amount" id="return-amount" required min="0" step="0.01" class="filter-input">
            </div>
            <div class="form-actions">
                <button type="submit" class="btn btn-primary">Return</button>
            </div>
        </form>
    `
};

// Initialization
function setupEventListeners() {
    document.addEventListener('submit', function(e) {
        if (e.target.matches('#add-form, #edit-form, #sample-form, #reagent-form')) {
            e.preventDefault();
            const handlerType = e.target.closest('.popup-container').dataset.handler;
            if (window.popupConfig?.[handlerType]?.submitHandler) {
                window.popupConfig[handlerType].submitHandler(e.target);
            }
        }
    });

    const today = new Date().toISOString().split('T')[0];
    document.getElementById('minDateCreatedFilterInput')?.value = today;
    document.getElementById('maxDateCreatedFilterInput')?.value = today;
}

document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
});
