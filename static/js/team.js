// team.js
document.addEventListener('DOMContentLoaded', function() {
    // State management
    const state = {
        currentItemId: null,
        currentProject: null,
        isLoading: false
    };

    // DOM Elements
    const elements = {
        addPopup: document.getElementById('addPopup'),
        editPopup: document.getElementById('editPopup'),
        removePopup: document.getElementById('removePopup'),
        memberForm: document.getElementById('member-form'),
        editForm: document.getElementById('edit-form'),
        teamTable: document.getElementById('teamTable')
    };

    // Event Listeners
    if (elements.addPopup) {
        elements.addPopup.addEventListener('click', (event) => {
            if (event.target === elements.addPopup) {
                closeAddPopup();
            }
        });
    }

    if (elements.editPopup) {
        elements.editPopup.addEventListener('click', (event) => {
            if (event.target === elements.editPopup) {
                closeEditPopup();
            }
        });
    }

    if (elements.removePopup) {
        elements.removePopup.addEventListener('click', (event) => {
            if (event.target === elements.removePopup) {
                closeRemovePopup();
            }
        });
    }

    if (elements.memberForm) {
        elements.memberForm.addEventListener('submit', handleMemberFormSubmit);
    }

    if (elements.editForm) {
        elements.editForm.addEventListener('submit', handleEditFormSubmit);
    }

    // Functions
    function showAddPopup() {
        elements.addPopup.style.display = 'flex';
        elements.addPopup.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
    }

    function closeAddPopup() {
        elements.addPopup.style.display = 'none';
        elements.addPopup.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
    }

    function showEditPopup(projectName, id) {
        state.currentItemId = id;
        state.currentProject = projectName;
        
        // Set current access level in the form
        const row = elements.teamTable.querySelector(`tr[data-id="${id}"]`);
        if (row) {
            const accessLevel = row.querySelector('td:nth-child(3)').textContent.trim();
            const select = elements.editForm.querySelector('#edit-role');
            select.value = accessLevel;
        }
        
        elements.editPopup.style.display = 'flex';
        elements.editPopup.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
    }

    function closeEditPopup() {
        elements.editPopup.style.display = 'none';
        elements.editPopup.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
    }

    function showRemovePopup(projectName, id) {
        state.currentItemId = id;
        state.currentProject = projectName;
        elements.removePopup.style.display = 'flex';
        elements.removePopup.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
    }

    function closeRemovePopup() {
        elements.removePopup.style.display = 'none';
        elements.removePopup.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
    }

    async function handleMemberFormSubmit(event) {
        event.preventDefault();
        if (state.isLoading) return;
        
        state.isLoading = true;
        const form = event.target;
        const submitButton = form.querySelector('button[type="submit"]');
        const originalButtonText = submitButton.textContent;
        
        try {
            submitButton.disabled = true;
            submitButton.innerHTML = 'Adding...';
            
            const response = await fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value
                }
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // Handle successful addition
                if (data.success) {
                    // Refresh the page or update the table dynamically
                    window.location.reload();
                } else {
                    showError(data.message || 'Failed to add team member');
                }
            } else {
                showError(data.message || 'Server error occurred');
            }
        } catch (error) {
            console.error('Error:', error);
            showError('Network error occurred');
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = originalButtonText;
            state.isLoading = false;
        }
    }

    async function handleEditFormSubmit(event) {
        event.preventDefault();
        if (state.isLoading) return;
        
        state.isLoading = true;
        const form = event.target;
        const submitButton = form.querySelector('button[type="submit"]');
        const originalButtonText = submitButton.textContent;
        
        try {
            submitButton.disabled = true;
            submitButton.innerHTML = 'Updating...';
            
            const response = await fetch(`/edit_user_access/${state.currentProject}/${state.currentItemId}/`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify({
                    role: form.querySelector('#edit-role').value
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                if (data.success) {
                    // Update the table row
                    const row = elements.teamTable.querySelector(`tr[data-id="${state.currentItemId}"]`);
                    if (row) {
                        row.querySelector('td:nth-child(3)').textContent = form.querySelector('#edit-role').value;
                    }
                    closeEditPopup();
                } else {
                    showError(data.message || 'Failed to update access');
                }
            } else {
                showError(data.message || 'Server error occurred');
            }
        } catch (error) {
            console.error('Error:', error);
            showError('Network error occurred');
        } finally {
            submitButton.disabled = false;
            submitButton.textContent = originalButtonText;
            state.isLoading = false;
        }
    }

    async function removeItem() {
        if (state.isLoading) return;
        
        state.isLoading = true;
        const confirmButton = document.querySelector('#removePopup .delete-bg-primary');
        const originalButtonText = confirmButton.textContent;
        
        try {
            confirmButton.disabled = true;
            confirmButton.innerHTML = 'Removing...';
            
            const response = await fetch(`/remove_user/${state.currentProject}/${state.currentItemId}`, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            });
            
            const data = await response.json();
            
            if (response.ok) {
                if (data.success) {
                    // Remove the row from the table
                    const row = elements.teamTable.querySelector(`tr[data-id="${state.currentItemId}"]`);
                    if (row) {
                        row.remove();
                    }
                    closeRemovePopup();
                } else {
                    showError(data.message || 'Failed to remove user');
                }
            } else {
                showError(data.message || 'Server error occurred');
            }
        } catch (error) {
            console.error('Error:', error);
            showError('Network error occurred');
        } finally {
            confirmButton.disabled = false;
            confirmButton.textContent = originalButtonText;
            state.isLoading = false;
        }
    }


    // Notification System
    function showNotification({ type = 'info', title = '', message = '', duration = 5000 }) {
        const container = document.getElementById('notification-container');
        const template = document.getElementById('notification-template');
        const clone = template.content.cloneNode(true);
        const notification = clone.querySelector('.notification');
        const icon = clone.querySelector('.notification-icon');
        const titleEl = clone.querySelector('.notification-title');
        const messageEl = clone.querySelector('.notification-message');
        const closeBtn = clone.querySelector('.notification-close');

        // Set notification content and style
        notification.classList.add(type);
        titleEl.textContent = title;
        messageEl.textContent = message;
    
        // Set icon based on type
        const icons = {
            success: '✓',
            error: '⚠',
            warning: '⚠',
            info: 'i'
        };
        icon.textContent = icons[type] || 'i';

        // Close button handler
        closeBtn.addEventListener('click', () => {
            notification.classList.add('notification-exit');
            setTimeout(() => notification.remove(), 300);
        });

        // Auto-dismiss after duration
        if (duration > 0) {
            setTimeout(() => {
                notification.classList.add('notification-exit');
                setTimeout(() => notification.remove(), 300);
            }, duration);
        }

        // Add to DOM
        container.appendChild(clone);
    }

    // Updated error handling function
    function showError(message, title = 'Error') {
        showNotification({
            type: 'error',
            title: title,
            message: message,
            duration: 8000
        });
    }

    // Success notification
    function showSuccess(message, title = 'Success') {
        showNotification({
            type: 'success',
            title: title,
            message: message,
            duration: 5000
        });
    }

    // Info notification
    function showInfo(message, title = 'Info') {
        showNotification({
            type: 'info',
            title: title,
            message: message,
            duration: 5000
        });
    }

    // Warning notification
    function showWarning(message, title = 'Warning') {
        showNotification({
            type: 'warning',
            title: title,
            message: message,
            duration: 6000
        });
    }

    // Make functions available globally
    window.showAddPopup = showAddPopup;
    window.closeAddPopup = closeAddPopup;
    window.showEditPopup = showEditPopup;
    window.closeEditPopup = closeEditPopup;
    window.showRemovePopup = showRemovePopup;
    window.closeRemovePopup = closeRemovePopup;
    window.removeItem = removeItem;
});
