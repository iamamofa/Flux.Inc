// For consumables and equipment
// Shared utility functions (used by all inventory pages)
const InventoryUtils = {
    // Show/hide popups
    showPopup: function(popupId) {
        const popup = document.getElementById(popupId);
        if (popup) popup.style.display = 'flex';
    },

    closePopup: function(popupId) {
        const popup = document.getElementById(popupId);
        if (popup) popup.style.display = 'none';
    },

    // Date comparison helper
    isDateInRange: function(date, minDate, maxDate) {
        if (!date || !minDate || !maxDate) return true;
        const currentDate = new Date(date);
        const min = new Date(minDate);
        const max = new Date(maxDate);
        return currentDate >= min && currentDate <= max;
    },

    // AJAX helper
    makeRequest: function(url, method, data, successCallback) {
        return fetch(url, {
            method: method,
            headers: {
                'X-CSRFToken': this.getCSRFToken(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
        .then(response => {
            if (!response.ok) throw new Error('Network response was not ok');
            return response.json();
        })
        .then(successCallback)
        .catch(error => {
            console.error('Error:', error);
            alert('Operation failed. Please try again.');
        });
    },

    getCSRFToken: function() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }
};

// Base initialization (runs on all pages)
document.addEventListener('DOMContentLoaded', function() {
    // Close popups when clicking outside
    document.querySelectorAll('.popup-container').forEach(container => {
        container.addEventListener('click', function(e) {
            if (e.target === this) {
                this.style.display = 'none';
            }
        });
    });

    // Reset button handling
    document.getElementById('resetButton')?.addEventListener('click', function() {
        document.querySelectorAll('.filters-container input, .filters-container select').forEach(input => {
            if (input.type !== 'submit' && input.type !== 'button') {
                input.value = '';
            }
        });
        if (typeof window.filterTable === 'function') {
            window.filterTable();
        }
    });

    // Make utility functions globally available
    window.InventoryUtils = InventoryUtils;
});
