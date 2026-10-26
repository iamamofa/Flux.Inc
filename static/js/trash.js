(function () {
    "use strict";
    var dialog = document.getElementById("trashDialog");
    var form = document.getElementById("trashActionForm");
    var confirm = document.getElementById("trashConfirm");
    var error = document.getElementById("trashActionError");
    var trigger;
    document.querySelectorAll("[data-trash-url]").forEach(function (button) {
        button.addEventListener("click", function () {
            trigger = button;
            form.action = button.dataset.trashUrl;
            error.textContent = "";
            var restore = button.dataset.trashAction === "restore";
            var empty = button.dataset.trashAction === "empty";
            document.getElementById("trashDialogTitle").textContent = restore ? "Restore this record?" : empty ? "Empty this category?" : "Permanently delete this record?";
            document.getElementById("trashDialogDescription").textContent = restore ? button.dataset.trashName + " will return to your inventory." : empty ? "All archived records in this category will be permanently removed. This cannot be undone." : button.dataset.trashName + " will be permanently removed. This cannot be undone.";
            confirm.textContent = restore ? "Restore record" : "Delete permanently";
            dialog.showModal();
        });
    });
    document.querySelector("[data-close-trash]").addEventListener("click", function () { dialog.close(); });
    dialog.addEventListener("close", function () { if (trigger) trigger.focus(); });
    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        if (confirm.disabled) return;
        confirm.disabled = true;
        error.textContent = "";
        try {
            var response = await fetch(form.action, { method: "POST", body: new FormData(form), headers: { "X-Requested-With": "XMLHttpRequest" } });
            var data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.error || "The record could not be updated.");
            window.location.reload();
        } catch (failure) {
            error.textContent = failure.message || "Couldn’t connect. Please try again.";
            confirm.disabled = false;
        }
    });
}());
