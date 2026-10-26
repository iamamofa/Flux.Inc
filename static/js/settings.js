(function () {
    "use strict";

    var content = document.querySelector("[data-settings-content]");
    if (!content) return;

    var sections = Array.from(content.querySelectorAll(".flux-settings-section"));
    var links = Array.from(document.querySelectorAll(".flux-settings-overview a"));

    function showSection(id, moveFocus) {
        var selected = sections.find(function (section) { return section.id === id; });
        if (!selected) return false;

        sections.forEach(function (section) { section.hidden = section !== selected; });
        links.forEach(function (link) {
            if (link.hash === "#" + id) link.setAttribute("aria-current", "location");
            else link.removeAttribute("aria-current");
        });

        if (moveFocus) {
            var heading = selected.querySelector("h2");
            heading.setAttribute("tabindex", "-1");
            heading.focus({ preventScroll: true });
            selected.scrollIntoView({ block: "start" });
        }
        return true;
    }

    function readLocation() {
        if (!showSection(window.location.hash.slice(1), false)) showSection("profile", false);
    }

    // Links still reach every section when JavaScript is unavailable.
    document.querySelector(".flux-settings").addEventListener("click", function (event) {
        var link = event.target.closest('a[href^="#"]');
        if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
        if (showSection(link.hash.slice(1), true)) {
            event.preventDefault();
            if (window.location.hash !== link.hash) window.history.pushState(null, "", link.hash);
        }
    });

    window.addEventListener("hashchange", readLocation);
    window.addEventListener("popstate", readLocation);
    if (content.hasAttribute("data-profile-errors")) showSection("profile", false);
    else readLocation();
}());
