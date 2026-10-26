# Flux.Inc — Integrated Administrator Portal

## What has been implemented

This package is an **in-place extension** of the uploaded Django application. It **does not replace** the original research projects, reagent, equipment, consumables, samples, project teams, or existing research-user login. The original database (`db.sqlite3`) is included **with migrations applied**; the separate original `db.sqlite3.backup` is retained. The new portal uses the existing Django `auth_user`, `auth_group`, `auth_permission`, and `inventory_*` tables.

The administrator workspace is at **`/control/`**. The original research inventory remains at its existing URLs; Django administration remains at **`/admin/`**.

The Django superuser interface at `/admin/` uses Flux branding and a responsive
operations landing page, with searchable/filterable user, project and inventory
lists. Use `/control/` for the full administrator workspace and its user, role,
department, audit, notification and reporting workflows.

| Capability | Implementation |
|---|---|
| Overview | Real ORM counts for existing users, applications, research projects and inventory; recent activity; six-month registration chart |
| Users | Directory, search, filters, pagination, create, edit, details, secure activation/deactivation, staff eligibility changes |
| Roles | Django Group/Permission matrix, role creation and modification, user-group assignment; super-administrator restricted |
| Departments | Create/edit/activate, assign department heads; initial non-destructive import of existing profile department labels |
| Notifications | Database-backed, per-recipient read state; new registration and administrator events; deduplication keys |
| Reports | Permission-checked, live CSV exports for users, research projects, inventory totals and audit logs |
| Audit | Application-level append-only records for portal mutations; legacy project logs also shown on overview |
| Settings | Persisted institutional identity, contact details, currency, display date format |
| Security | Server configuration status, secure password reset email flow, server-side permission checks, CSRF on POST |
| UI | Responsive sidebar, global search, accessible forms, tables, light/dark theme and empty/error states |

**Not part of this release:** requisitions, supplier procurement, purchase orders, quotations, receiving, Accounts/Payments, finance approvals and complete configurable approval workflow engines. No dummy records or pretend procurement links are shown. **Do not characterize these as operational** until their models, workflows, endpoints, tests and authorization rules have been separately implemented.

## Quick start (local development)

1. Install **Python 3.11**. This project uses Django 4.1.7. Create and activate a virtual environment:

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-runtime.txt
   ```

2. Copy `.env.example` to `.env` and configure local environment variables, or set them in your shell:

   ```bash
   cp .env.example .env
   ```

3. From the `Flux.Inc/` folder run:

   ```bash
   python manage.py check
   python manage.py migrate
   python manage.py runserver
   ```

4. Sign in with an **existing authorized super-administrator** at `/admin/login/` and open `/control/`. Standard research users are deliberately blocked. New installations with no accounts can use `python manage.py createsuperuser`.

5. Run automated checks:

   ```bash
   python manage.py test control
   ```

`requirements.txt` is the **unmodified legacy environment export**, containing an invalid `3==0.0.0` dependency and many unrelated data-science/Mac-only packages. Prefer the curated `requirements-runtime.txt` for the Django application. An installed ClamAV service and corresponding Django configuration are still required for the original malware-scanning tasks, if enabled.

## Deployment prerequisites and security

**The uploaded project embedded an application signing secret and email password inside settings and two archived `.txt` snapshots. They have been removed from this deliverable. Rotate those old credentials before deployment.** Secret values are read from environment variables. Django loads a local `.env` file when present; `.env` is excluded from source control. Use `.env.example` as a placeholder-only reference and never put real credentials in it.

For production, configure at least:

- `FLUX_DEBUG=false`, a new random `FLUX_SECRET_KEY`, `FLUX_ALLOWED_HOSTS`, and `FLUX_CSRF_TRUSTED_ORIGINS`.
- `FLUX_EMAIL_USER`, `FLUX_EMAIL_PASSWORD`, `FLUX_FROM_EMAIL` and SMTP settings if password-reset email and existing notification email are needed. No email is claimed sent if it fails.
- An HTTPS reverse proxy, durable user-upload storage, secure backup policy, and production logging.
- A supported database server (PostgreSQL is preferable for multiple concurrent institutional users; this ZIP retains SQLite to preserve the uploaded data).

After backing up the production database, deploy the code, run `python manage.py migrate`, then `python manage.py collectstatic --noinput`; serve with an appropriate WSGI host. Never publicly distribute the included real database, which may contain account and institutional information.

**Security boundary:** The newly added `/control/` routes enforce `is_active`, `is_staff`, and Django permissions on the server. Staff eligibility and group grants can be changed only by super-administrators; staff account details cannot be edited by lesser administrators. A group's permissions are not sufficient alone to log in to the administrator portal without `is_staff`. Sensitive changes use CSRF-protected POSTs. Audit rows cannot be edited or deleted through the model or Django admin; **this is not cryptographically tamper-proof auditing or database-level immutability.**

**Before live institutional deployment:** Upgrade the **legacy Django 4.1.7** and old dependency set to currently supported security releases after compatibility testing. Independently review and penetration-test the **pre-existing** inventory views, particularly project authorization on some legacy URLs, file processing, application approval/self-registration, and session handling. The new administrator portal does not automatically remediate every pre-existing endpoint. Full production load tests, responsive browser testing across devices, SMTP deliverability tests, and external security testing are still required.

## Database and data protection

- New models: `Department`, `AdminAudit`, `AdminNotification`, `PortalSettings` in the `control` app.
- Migrations `0001`, `0002` (non-destructive department import), `0003` (notification uniqueness).
- Original research and inventory schema remain unchanged.
- `db.sqlite3` inside this ZIP already includes new migrations applied against the uploaded data.
- Your separate original `db.sqlite3.backup` is also retained. Keep independent encrypted/off-site backups before migrating your real production deployment.

## Procurement-ready integration plan

Build an `procurement` Django app using the existing `User`, `Group`, `Permission`, `Department`, notifications and audit conventions; add suppliers, requisitions and line items, approval policy versions, quotations, purchase orders, delivery receipts, stores inspections, supplier invoices and payment records **as genuine persisted models**. Require transaction boundaries, unique identifiers/idempotency rules, transition checks, project/department scope controls and separation of duties. Configure approval and financial thresholds with auditable versions. Do not add the procurement navigation group until these routes actually exist and enforce permissions. Procurement was described as a later, separately implemented module in the supplied specification.

## Modified/new files

- `inventory_system/settings.py`, `inventory_system/urls.py`: safer environment-backed settings, new portal routing.
- `inventory/views.py`: repairs duplicate `UserProfile` creation and registration backend selection.
- `inventory/models.py`: ensures registration-image errors can be logged without an undefined `traceback` name.
- `control/`: models, migrations, forms, views, URLs, real-event signals, Django admin registration, tests, templates, styling, and mobile/theme JS.
- `.env.example`, `requirements-runtime.txt`, `ADMIN_PORTAL_README.md`: deployment configuration and documentation.
- `setting_py.txt` and `production_setting.txt`: excluded because they retained historical embedded secrets. Compiled staticfiles, Mac `.venv`, and `.git` are not included; these are regenerated or maintained outside the source archive.

## Validation performed

Django `manage.py check` completed without issues. `control` unit/integration test suite (19 tests) passed for rendering, RBAC, live record handling, user creation/editing, staff access, roles, audit restrictions, departments, notifications, password reset, reports/CSV sanitization, and original project model visibility. The database migration completed, preserving the uploaded user and project rows. **The entire pre-existing inventory application was not end-to-end regression-tested**, and no complete procurement module is present.
