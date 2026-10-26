(function () {
    "use strict";

    document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
        button.addEventListener("click", function () {
            var input = document.getElementById(button.dataset.passwordToggle);
            var visible = input.type === "password";
            input.type = visible ? "text" : "password";
            button.textContent = visible ? "Hide" : "Show";
            button.setAttribute("aria-pressed", String(visible));
            var label = document.querySelector('label[for="' + input.id + '"]');
            button.setAttribute("aria-label", (visible ? "Hide " : "Show ") + label.textContent.trim().toLowerCase());
        });
    });

    document.querySelectorAll(".flux-form-field").forEach(function (field) {
        var input = field.querySelector("input, select, textarea");
        if (!input) return;
        var descriptions = [];
        field.querySelectorAll(".flux-field-help, .flux-field-error").forEach(function (description) {
            descriptions.push(description.id);
        });
        if (descriptions.length) input.setAttribute("aria-describedby", descriptions.join(" "));
        if (field.classList.contains("flux-form-field-invalid")) input.setAttribute("aria-invalid", "true");
        if (input.name === "email") input.autocomplete = "email";
        if (input.name === "first_name") input.autocomplete = "given-name";
        if (input.name === "last_name") input.autocomplete = "family-name";
        if (input.name === "password") input.autocomplete = "current-password";
    });

    document.querySelectorAll("[data-table-search]").forEach(function (input) {
        var table = document.querySelector(input.dataset.tableSearch);
        if (!table) return;
        var body = table.querySelector("tbody") || table;
        var rows = Array.from(body.querySelectorAll("tr[data-id], tr[data-search-row]"));
        if (!rows.length) {
            input.disabled = true;
            input.placeholder = "No records yet";
            return;
        }
        var searchableRows = rows.map(function (row) {
            return row.textContent + " " + Object.values(row.dataset).join(" ");
        });
        var status = document.querySelector("[data-table-search-status]");
        var empty = document.createElement("tr");
        empty.className = "flux-search-empty";
        empty.hidden = true;
        var cell = document.createElement("td");
        cell.colSpan = table.querySelectorAll("thead th").length || 10;
        cell.textContent = "No matching records on this page. Try another search or clear your filters.";
        empty.appendChild(cell);
        body.appendChild(empty);
        input.addEventListener("input", function () {
            var query = input.value.toLocaleLowerCase().trim();
            var matches = 0;
            rows.forEach(function (row, index) {
                row.hidden = !searchableRows[index].toLocaleLowerCase().includes(query);
                if (!row.hidden && row.style.display !== "none") matches++;
            });
            empty.hidden = !query || matches > 0;
            if (status) status.textContent = query ? matches + " matching record" + (matches === 1 ? "" : "s") + " on this page" : "";
        });
    });

    document.addEventListener("click", function (event) {
        document.querySelectorAll(".flux-project-switcher[open]").forEach(function (details) {
            if (!details.contains(event.target)) details.open = false;
        });
    });
    document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") return;
        document.querySelectorAll(".flux-project-switcher[open]").forEach(function (details) {
            details.open = false;
            details.querySelector("summary").focus();
        });
    });
}());
