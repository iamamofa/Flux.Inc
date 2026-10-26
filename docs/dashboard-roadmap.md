# Dashboard feature roadmap

The weekly agent completes one item per proposal, in order. Verify the current code
before starting: some items may already have been implemented manually. Completed
items stay here and are recorded in [the upgrade log](dashboard-upgrade-log.md).

- [ ] **Accessible chart data.** Add a keyboard-accessible way to inspect the values
  behind each dashboard chart as a labeled table, with an understandable empty state.
  Keep charts available and show the correct units and threshold values.
- [ ] **Chart display controls.** Let users change the number of stock/sample items
  shown and sort the primary chart by name, amount or threshold status. Controls must
  update the actual chart and accessible values without changing stored inventory.
- [ ] **Actionable attention summaries.** Show project-specific low stock, upcoming
  expiry or calibration reminders with working links to the relevant inventory.
  Use each category's actual fields and preserve project access checks.
- [ ] **Download chart summaries.** Offer CSV downloads of the displayed chart data,
  including units and thresholds. Keep the export scoped to the current project and
  prevent spreadsheet formula injection in text cells.
- [ ] **Remember display preferences.** Remember dashboard chart/display choices in
  this browser, provide a reset, and handle unavailable browser storage gracefully.
- [ ] **Administrator dashboard navigation.** Make overview metrics lead to useful
  existing filtered views, with accurate accessible labels and permission checks.
- [ ] **Clear dashboard empty states.** Add useful next actions when a category has
  no records or a chart has no applicable data; keep zero distinct from unavailable.

Each feature must work with empty and populated data, fit narrow screens, use
existing application data and pass the automated checks. Changes needing a schema
migration, new package, external service or a broader product decision are deferred
for a separately requested change. Keep the original home screen and account flows.
