(function () {
    "use strict";

    // Keep panels in their rows so existing table action handlers still receive clicks.
    // Popovers render in the top layer, outside the scroll container's clipping area.
    const supportsPopover = typeof HTMLElement.prototype.showPopover === "function";
    const menus = [];
    let activeMenu = null;

    function resetMenu(menu) {
        menu.dropdown.classList.remove("active");
        menu.trigger.setAttribute("aria-expanded", "false");
        if (activeMenu === menu) activeMenu = null;
    }

    function closeMenu(restoreFocus = false) {
        if (!activeMenu) return;
        const menu = activeMenu;
        if (supportsPopover && menu.panel.matches(":popover-open")) {
            menu.panel.hidePopover();
        }
        resetMenu(menu);
        if (restoreFocus) menu.trigger.focus({ preventScroll: true });
    }

    function positionMenu(menu) {
        const anchor = menu.trigger.getBoundingClientRect();
        const panel = menu.panel;
        const gutter = 12;
        const gap = 8;
        const viewportWidth = document.documentElement.clientWidth;
        const viewportHeight = document.documentElement.clientHeight;
        panel.style.maxHeight = `${Math.max(0, viewportHeight - gutter * 2)}px`;

        const width = panel.offsetWidth;
        const height = panel.offsetHeight;
        const roomBelow = viewportHeight - anchor.bottom - gap - gutter;
        const roomAbove = anchor.top - gap - gutter;
        const openAbove = height > roomBelow && roomAbove > roomBelow;
        const top = openAbove ? anchor.top - gap - height : anchor.bottom + gap;

        panel.style.left = `${Math.max(gutter, Math.min(anchor.right - width, viewportWidth - width - gutter))}px`;
        panel.style.top = `${Math.max(gutter, Math.min(top, viewportHeight - height - gutter))}px`;
        panel.dataset.placement = openAbove ? "above" : "below";
    }

    function openMenu(menu, focusFirst = false) {
        closeMenu();
        activeMenu = menu;
        menu.dropdown.classList.add("active");
        menu.trigger.setAttribute("aria-expanded", "true");
        if (supportsPopover) menu.panel.showPopover();
        positionMenu(menu);
        if (focusFirst) menu.panel.querySelector("button:not(:disabled)")?.focus();
    }

    document.querySelectorAll(".flux-inventory-layout .wide-inventory-table .dropdown-trigger").forEach((trigger, index) => {
        const dropdown = trigger.closest(".dropdown");
        const panel = dropdown.querySelector(".dropdown-actions");
        if (!panel) return;

        const menu = { trigger, dropdown, panel };
        menus.push(menu);
        panel.id = panel.id || `inventory-actions-${index}`;
        panel.setAttribute("role", "group");
        panel.setAttribute("aria-label", trigger.getAttribute("aria-label") || "Item actions");
        trigger.type = "button";
        trigger.setAttribute("aria-controls", panel.id);
        trigger.setAttribute("aria-expanded", "false");

        if (supportsPopover) {
            // Own dismissal here to avoid native light-dismiss racing a different row's click.
            panel.setAttribute("popover", "manual");
            panel.addEventListener("toggle", () => {
                if (!panel.matches(":popover-open")) resetMenu(menu);
            });
        }

        trigger.addEventListener("click", (event) => {
            // Let clicks on actions bubble through the table; only the trigger is handled here.
            event.stopPropagation();
            if (activeMenu === menu) closeMenu();
            else openMenu(menu);
        });
        trigger.addEventListener("keydown", (event) => {
            if (event.key !== "ArrowDown") return;
            event.preventDefault();
            openMenu(menu, true);
        });
    });

    if (!menus.length) return;

    document.addEventListener("click", (event) => {
        if (!activeMenu) return;
        // This runs after the table's action handler, preserving the selected item.
        if (activeMenu.panel.contains(event.target)) {
            if (event.target.closest("button")) closeMenu();
        } else if (!activeMenu.trigger.contains(event.target)) {
            closeMenu();
        }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && activeMenu) {
            event.preventDefault();
            closeMenu(true);
        }
    });
    document.addEventListener("focusin", (event) => {
        if (activeMenu && !activeMenu.dropdown.contains(event.target)) closeMenu();
    });
    // Follow visible rows while scrolling, including the browser's scroll-to-focus.
    document.addEventListener("scroll", (event) => {
        if (!activeMenu || activeMenu.panel.contains(event.target)) return;
        const anchor = activeMenu.trigger.getBoundingClientRect();
        const bounds = activeMenu.trigger.closest(".table-container").getBoundingClientRect();
        if (anchor.bottom <= Math.max(0, bounds.top) ||
            anchor.top >= Math.min(innerHeight, bounds.bottom) ||
            anchor.right <= Math.max(0, bounds.left) ||
            anchor.left >= Math.min(innerWidth, bounds.right)) {
            closeMenu();
        } else {
            positionMenu(activeMenu);
        }
    }, true);
    window.addEventListener("resize", () => closeMenu());
}());
