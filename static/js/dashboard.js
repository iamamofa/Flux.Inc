(function () {
    "use strict";
    var popup = document.getElementById("addPopup");
    var form = document.getElementById("add-form");
    var errorContainer = document.getElementById("errorContainer");
    var returnFocus;
    window.showAddPopup = function () {
        returnFocus = document.activeElement;
        popup.style.display = "flex";
        popup.setAttribute("aria-hidden", "false");
        document.getElementById("projectNameInput").focus();
    };
    window.closeAddPopup = function () {
        popup.style.display = "none";
        popup.setAttribute("aria-hidden", "true");
        errorContainer.textContent = "";
        if (returnFocus) returnFocus.focus();
    };
    popup.addEventListener("click", function (event) {
        if (event.target === popup) window.closeAddPopup();
    });
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && popup.getAttribute("aria-hidden") === "false") window.closeAddPopup();
    });
    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        var button = form.querySelector('[type="submit"]');
        if (button.disabled) return;
        button.disabled = true;
        errorContainer.textContent = "";
        try {
            var response = await fetch(form.action, {
                method: "POST",
                body: new FormData(form),
                headers: { "X-Requested-With": "XMLHttpRequest" }
            });
            var data = await response.json();
            if (!response.ok) throw new Error(data.error || "The project could not be created. Please try again.");
            window.location.assign(data.redirect);
        } catch (error) {
            errorContainer.textContent = error.message || "Couldn’t connect. Check your connection and try again.";
            button.disabled = false;
        }
    });
}());
