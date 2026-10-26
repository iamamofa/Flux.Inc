(function () {
    "use strict";

    var densityKey = "flux.density";
    var sidebarKey = "flux.sidebar";
    var root = document.documentElement;

    function applyPreferences() {
        root.dataset.density = localStorage.getItem(densityKey) || "comfortable";
        root.dataset.sidebar = localStorage.getItem(sidebarKey) || "expanded";
    }

    function updateControls() {
        var density = localStorage.getItem(densityKey) || "comfortable";
        var sidebar = localStorage.getItem(sidebarKey) || "expanded";

        document.querySelectorAll("[data-flux-density]").forEach(function (control) {
            control.checked = control.value === density;
        });
        document.querySelectorAll("[data-flux-sidebar]").forEach(function (control) {
            control.checked = control.value === sidebar;
        });
    }

    function savePreference(key, value) {
        localStorage.setItem(key, value);
        applyPreferences();
        updateControls();
    }

    applyPreferences();

    document.addEventListener("DOMContentLoaded", function () {
        updateControls();

        document.querySelectorAll("[data-flux-density]").forEach(function (control) {
            control.addEventListener("change", function () {
                if (control.checked) {
                    savePreference(densityKey, control.value);
                }
            });
        });
        document.querySelectorAll("[data-flux-sidebar]").forEach(function (control) {
            control.addEventListener("change", function () {
                if (control.checked) {
                    savePreference(sidebarKey, control.value);
                }
            });
        });

        var reset = document.querySelector("[data-flux-reset-preferences]");
        if (reset) {
            reset.addEventListener("click", function () {
                localStorage.removeItem(densityKey);
                localStorage.removeItem(sidebarKey);
                applyPreferences();
                updateControls();
            });
        }
    });

}());
