(function () {
    const tour = document.getElementById('fluxProductTour');
    if (!tour) return;

    const steps = [
        { target: 'workspace-navigation', title: 'Your workspace map.', copy: 'This navigation is your lab control room. Move between dashboards, inventory, tools, borrowing, logs and project settings.', placement: 'right' },
        { target: 'dashboard', title: 'Start at a glance.', copy: 'Your dashboard surfaces low stock, expiry pressure and project activity so the next action is always clear.', placement: 'right' },
        { target: 'inventory', title: 'See what is available.', copy: 'Inventory keeps reagents, consumables, samples and equipment searchable, traceable and ready for your next run.', placement: 'right' },
        { target: 'lab-tools', title: 'Your genomics toolkit.', copy: 'Lab tools brings expiry radar, cold-chain checks, plate mapping, labels, imports and shared equipment together.', placement: 'right' },
        { target: 'borrow-loan', title: 'Keep experiments moving.', copy: 'Borrow unused reagents or consumables from another project. Requests, approvals, notifications and receipts stay connected.', placement: 'right' },
        { target: 'logs', title: 'Every action leaves a trail.', copy: 'Project logs and cold-chain audits make it easy to download evidence for reviews, incidents and compliance.', placement: 'right' },
        { target: 'settings', title: 'Make Flux fit your team.', copy: 'Use Settings to manage your project preferences. You can revisit this walkthrough any time from the workspace.', placement: 'right' },
    ];

    let index = 0;
    const title = tour.querySelector('[data-tour-title]');
    const copy = tour.querySelector('[data-tour-copy]');
    const next = tour.querySelector('[data-tour-next]');
    const back = tour.querySelector('[data-tour-back]');
    const progress = tour.querySelector('[data-tour-progress]');
    const card = tour.querySelector('[data-tour-card]');
    const spotlight = tour.querySelector('[data-tour-spotlight]');
    const pointer = tour.querySelector('[data-tour-pointer]');
    const nav = document.querySelector('[data-tour-target="workspace-navigation"]');
    const previousOverflow = document.body.style.overflow;

    function csrfToken() {
        return (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '';
    }

    function finish() {
        document.body.style.overflow = previousOverflow;
        nav?.classList.remove('flux-tour-nav-open');
        window.removeEventListener('resize', position);
        window.removeEventListener('keydown', keyboard);
        fetch(tour.dataset.completeUrl, { method: 'POST', headers: { 'X-CSRFToken': csrfToken() } }).finally(() => tour.remove());
    }

    function keyboard(event) {
        if (event.key === 'Escape') finish();
        if (event.key === 'ArrowRight') advance();
        if (event.key === 'ArrowLeft') retreat();
    }

    function findTarget(step) {
        const element = document.querySelector(`[data-tour-target="${step.target}"]`);
        if (!element) return null;
        if (element.getBoundingClientRect().width === 0 || element.getBoundingClientRect().height === 0) {
            if (step.target === 'workspace-navigation') {
                nav?.classList.add('flux-tour-nav-open');
            }
        }
        return element;
    }

    function clamp(value, min, max) {
        return Math.min(Math.max(value, min), max);
    }

    function position() {
        const step = steps[index];
        const target = findTarget(step);
        const viewportPadding = 16;
        card.classList.remove('flux-tour-card-right', 'flux-tour-card-left', 'flux-tour-card-top', 'flux-tour-card-bottom', 'flux-tour-card-centered');
        tour.classList.toggle('has-spotlight', Boolean(target));

        if (!target) {
            spotlight.hidden = true;
            card.classList.add('flux-tour-card-centered');
            pointer.hidden = true;
            return;
        }

        target.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        const rect = target.getBoundingClientRect();
        const gap = 18;
        const spotlightPadding = 8;
        spotlight.hidden = false;
        spotlight.style.left = `${Math.max(6, rect.left - spotlightPadding)}px`;
        spotlight.style.top = `${Math.max(6, rect.top - spotlightPadding)}px`;
        spotlight.style.width = `${rect.width + spotlightPadding * 2}px`;
        spotlight.style.height = `${rect.height + spotlightPadding * 2}px`;

        const cardRect = card.getBoundingClientRect();
        const cardWidth = cardRect.width || 360;
        const cardHeight = cardRect.height || 250;
        let left;
        let top;
        let placement = 'right';
        if (rect.right + gap + cardWidth <= window.innerWidth - viewportPadding) {
            left = rect.right + gap;
            top = clamp(rect.top + rect.height / 2 - cardHeight / 2, viewportPadding, window.innerHeight - cardHeight - viewportPadding);
        } else if (rect.left - gap - cardWidth >= viewportPadding) {
            placement = 'left';
            left = rect.left - gap - cardWidth;
            top = clamp(rect.top + rect.height / 2 - cardHeight / 2, viewportPadding, window.innerHeight - cardHeight - viewportPadding);
        } else if (rect.bottom + gap + cardHeight <= window.innerHeight - viewportPadding) {
            placement = 'bottom';
            left = clamp(rect.left + rect.width / 2 - cardWidth / 2, viewportPadding, window.innerWidth - cardWidth - viewportPadding);
            top = rect.bottom + gap;
        } else {
            placement = 'top';
            left = clamp(rect.left + rect.width / 2 - cardWidth / 2, viewportPadding, window.innerWidth - cardWidth - viewportPadding);
            top = Math.max(viewportPadding, rect.top - gap - cardHeight);
        }
        card.style.left = `${left}px`;
        card.style.top = `${top}px`;
        card.classList.add(`flux-tour-card-${placement}`);
        pointer.hidden = false;
    }

    function render() {
        const step = steps[index];
        title.textContent = step.title;
        copy.textContent = step.copy;
        progress.textContent = `${index + 1} / ${steps.length}`;
        back.hidden = index === 0;
        next.innerHTML = index === steps.length - 1 ? 'Start exploring <span aria-hidden="true">→</span>' : 'Next feature <span aria-hidden="true">→</span>';
        requestAnimationFrame(position);
        next.focus({ preventScroll: true });
    }

    function advance() {
        if (index === steps.length - 1) finish();
        else { index += 1; render(); }
    }

    function retreat() {
        index = Math.max(0, index - 1);
        render();
    }

    next.addEventListener('click', advance);
    back.addEventListener('click', retreat);
    tour.querySelector('[data-tour-skip]').addEventListener('click', finish);
    document.body.style.overflow = 'hidden';
    window.addEventListener('resize', position);
    window.addEventListener('keydown', keyboard);
    render();
}());
