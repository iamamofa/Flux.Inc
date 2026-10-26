(function () {
    "use strict";

    var densityKey = "flux.density";
    var sidebarKey = "flux.sidebar";
    var root = document.documentElement;
    var preferences = { density: "comfortable", sidebar: "expanded" };
    var storageAvailable = true;

    try {
        var storedDensity = localStorage.getItem(densityKey);
        var storedSidebar = localStorage.getItem(sidebarKey);
        if (storedDensity === "compact") preferences.density = storedDensity;
        if (storedSidebar === "collapsed") preferences.sidebar = storedSidebar;
    } catch (error) {
        storageAvailable = false;
    }

    function applyPreferences() {
        root.dataset.density = preferences.density;
        root.dataset.sidebar = preferences.sidebar;
    }

    function updateControls() {
        document.querySelectorAll("[data-flux-density]").forEach(function (control) {
            control.checked = control.value === preferences.density;
        });
        document.querySelectorAll("[data-flux-sidebar]").forEach(function (control) {
            control.checked = control.value === preferences.sidebar;
        });
    }

    function announce(message) {
        var status = document.querySelector("[data-flux-preference-status]");
        if (status) status.textContent = storageAvailable ? message : "Applied for this page. Enable browser storage to keep your preferences.";
    }

    function savePreference(key, value) {
        preferences[key === densityKey ? "density" : "sidebar"] = value;
        try {
            localStorage.setItem(key, value);
            storageAvailable = true;
        } catch (error) {
            storageAvailable = false;
        }
        applyPreferences();
        updateControls();
        announce("Preferences saved in this browser.");
    }

    applyPreferences();

    document.addEventListener("DOMContentLoaded", function () {
        updateControls();
        if (!storageAvailable) announce("");

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
                preferences.density = "comfortable";
                preferences.sidebar = "expanded";
                try {
                    localStorage.removeItem(densityKey);
                    localStorage.removeItem(sidebarKey);
                    storageAvailable = true;
                } catch (error) {
                    storageAvailable = false;
                }
                applyPreferences();
                updateControls();
                announce("Default preferences restored.");
            });
        }
    });

}());
