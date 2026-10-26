Implement one useful dashboard feature for Flux this week.

Read README.md, docs/dashboard-roadmap.md, docs/dashboard-upgrade-log.md, and
.github/scripts/dashboard_changes.py before editing. Inspect the existing dashboard
views, templates, charts and tests. Use the current code to determine which roadmap
items already exist; do not duplicate completed capabilities.

Choose the highest-priority unfinished roadmap item that can be completed as one
small, reviewable change using the application's existing data. Implement the feature
end to end, including its user-facing controls, server-side logic when necessary,
empty/error states, and meaningful tests. Improve related usability when it helps
that feature. If every listed item is complete, choose one comparably small dashboard
improvement and add it to the roadmap with a clear user benefit. Do not just update
the roadmap or report without implementing working behavior.

Keep the existing Django templates, plain JavaScript and Chart.js architecture.
Preserve the original full-screen, five-photo home carousel and its newer copy.
Preserve existing page layouts, permissions, stock alerts and inventory workflows.
Keep dashboard calculations based on real project records. Never invent statistics,
claim features that are not implemented, or make records from another project
visible. Include manager/member access and empty-data cases in relevant tests.
Scope new styles and event handlers to the dashboard component they change.

Only edit the paths permitted by dashboard_changes.py. Do not edit the home screen,
account pages, existing automated workflows, this prompt, the scope checker,
dependencies, deployment settings, authentication policies, models or migrations.
Do not read databases, backups, uploaded files, .env files, credentials or secrets.
Do not add paid services, external APIs, new packages, background workers, telemetry,
emails or other external side effects. Do not commit, push, merge, deploy, change
repository settings or call GitHub APIs; the workflow publishes the proposal.

The workflow has already checked the baseline. After implementing the feature:

1. Run python manage.py check and python manage.py test --noinput.
2. Run python manage.py makemigrations --check --dry-run.
3. Run node --check for each changed JavaScript file and git diff --check.
4. Verify the affected dashboards with populated and empty data. Check desktop and
   mobile layouts using an installed browser if available. Do not download a browser
   or claim visual verification when none is available; explain that limit.
5. Mark the implemented roadmap item complete only if its acceptance criteria are
   satisfied. Append an entry to docs/dashboard-upgrade-log.md with today's UTC date,
   the feature, user benefit, files changed, actual validation commands/results and
   any remaining limitations. Never remove earlier log entries.

If the feature cannot be implemented and tested within this run, leave the checkout
unchanged and explain the blocker. Do not disable tests or weaken existing assertions
to get a pass. Do not begin a second feature.

Your final message becomes the pull request description. Lead with the implemented
feature and the observable improvement. Include a short before/after example,
validation actually performed, any unperformed visual checks, and limitations. Never
include secrets, real user data or a full patch in that message.
