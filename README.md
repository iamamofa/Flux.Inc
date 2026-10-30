<p align="center">
  <img src="https://img.shields.io/badge/Framework-Django-092e20" alt="Django" />
  <img src="https://img.shields.io/badge/Python-3.11%20recommended-3776ab" alt="Python 3.11 recommended" />
  <img src="https://img.shields.io/badge/Database-SQLite-003b57" alt="SQLite" />
  <img src="https://img.shields.io/badge/License-See%20LICENSE-lightgrey" alt="See LICENSE" />
</p>

<p align="center">
<img src ="./static/images/Logo_Orange.png">
</p>

<p align="center">
  Research inventory management and an integrated administrator portal for laboratory operations.
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#application-routes">Application routes</a> ·
  <a href="ADMIN_PORTAL_README.md">Administrator portal guide</a>
</p>

---

## Overview

**Flux** is a Django application for research inventory and facility administration. It combines the existing research-user application with a dedicated administrator workspace, while preserving the existing projects, inventory, and login.

The application is designed for genomics and bioinformatics laboratories to organize research projects and track reagents, consumables, equipment, and samples. The administrator portal adds user, role, department, notification, audit, settings, and reporting workflows.

## Key features

### Research inventory

- Manage reagents, consumables, equipment, and samples by project.
- Track project teams and access.
- Review inventory dashboards and low-stock alerts.
- Export selected inventory data and manage applicable trash/recovery workflows.
- Upload and manage reagent safety data sheet files.
- Share unused, unopened consumable and reagent packs between project managers through **Borrow & Loan**.

#### Borrow & Loan

Open **Borrow & Loan** in a project manager's workspace. Under **My offers**, publish
spare, unexpired packs that your project can lend. Other enrolled project managers
can search offers by item, category, and project, then request packs with a purpose
and return or replacement date. The lending manager approves or declines each
request before stock moves.

Approval transfers packs into a separate inventory entry in the borrowing project,
preserving item metadata and reagent safety documents. The borrower arranges a
full return or replacement and the lender confirms receipt to close the loan.
Different-expiry replacement stock stays as a separate batch. Requests, decisions,
due dates, and activity history remain stored even when an offer is withdrawn.
Borrowing and lending histories can be exported as CSV. Editors and members cannot
access the exchange, and inventory linked to exchange history is protected from
deletion.

### Administrator portal

- View an operational overview of users, applications, projects, and inventory.
- Search, filter, create, and manage user accounts.
- Configure roles, permissions, departments, and department heads.
- Review database-backed notifications and administrator audit records.
- Export permission-checked CSV reports.
- Configure institutional details and account security workflows.

> **Scope:** Procurement, purchase orders, receiving, accounts/payments, and finance approvals are not implemented. Refer to the [Administrator Portal Guide](ADMIN_PORTAL_README.md) for details on implemented capabilities and limitations.

## Technology

| Component | Technology |
| --- | --- |
| Web framework | Django 4.1.7 |
| Recommended Python version | Python 3.11 |
| Database | SQLite by default |
| Front end | Django templates, HTML, CSS, and JavaScript |
| Static files | WhiteNoise |
| Configuration | Environment variables and optional `.env` file |

## Project structure

```text
Flux/
├── control/                     # Administrator portal
│   ├── migrations/
│   ├── templates/
│   └── tests.py
├── inventory/                   # Research inventory application
│   ├── management/commands/     # Django management commands
│   ├── migrations/
│   ├── templates/
│   └── tests.py
├── inventory_system/            # Django project settings and URL configuration
├── templates/                   # Shared templates and admin customization
├── user_applications/           # User-submitted application uploads
├── .env.example                 # Placeholder environment configuration
├── manage.py
├── requirements-runtime.txt     # Curated application dependencies
└── ADMIN_PORTAL_README.md       # Detailed portal and deployment guide
```

## Requirements

- Python 3.11 recommended
- `pip`
- Git

The project uses Django 4.1.7, a legacy release. Review the [security and deployment notes](#security-and-deployment) before exposing an installation to users.

## Quick start

### 1. Get the project

```bash
git clone https://github.com/iamamofa/flux.git
cd flux
```

### 2. Create and activate a virtual environment

macOS/Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements-runtime.txt
```

Use `requirements-runtime.txt` for the application. `requirements.txt` is a legacy environment export and is not the recommended installation file.

### 4. Configure and initialize

For a local development setup, Django defaults to debug mode when `FLUX_DEBUG` is not set. You can run locally without creating a `.env` file, or copy `.env.example` to `.env` and set development values there. Do not use the example placeholder values in a production deployment.

```bash
python manage.py check
python manage.py migrate
```

Create an administrator account if this is a new installation without existing accounts:

```bash
python manage.py createsuperuser
```

### 5. Start the development server

```bash
python manage.py runserver
```

The application is available at:

- Research application: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Django administration: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
- Administrator portal: [http://127.0.0.1:8000/control/](http://127.0.0.1:8000/control/)

Sign in with an authorized super-administrator account to access the administrator portal. Standard research accounts do not automatically receive portal access.

## Application routes

| Area | Route | Description |
| --- | --- | --- |
| Research application | `/` | Existing research-user application |
| Sign in | `/login/` | Research application login |
| Password reset | `/forgot-password/` | Email-based password reset and secure confirmation |
| Registration | `/registration/` | User registration |
| Project workspace | Project-specific routes | Project team, settings, logs, and inventory |
| Borrow & Loan | `/borrow-loan/<project_name>/` | Manager-only stock exchange and borrowing history |
| Django administration | `/admin/` | Django administrative interface |
| Portal overview | `/control/` | Administrator workspace |
| Users and roles | `/control/users/`, `/control/roles/` | User and role management |
| Departments | `/control/departments/` | Department administration |
| Reports and audit | `/control/reports/`, `/control/audit/` | Portal reports and audit records |
| Portal settings | `/control/settings/` | Institutional and portal settings |

Inventory and project routes are defined in the application and may require an authenticated user with access to the relevant project.

## Useful commands

Run Django configuration checks:

```bash
python manage.py check
```

Apply database migrations:

```bash
python manage.py migrate
```

Run portal tests:

```bash
python manage.py test control
```

Collect static files for deployment:

```bash
python manage.py collectstatic --noinput
```

Send scheduled low-stock email summaries:

```bash
python manage.py send_scheduled_low_stock_alerts
```

The low-stock command must be scheduled externally, typically once per minute, and requires the application email environment variables. See the [Administrator Portal Guide](ADMIN_PORTAL_README.md) for scheduling and delivery behavior.

## Weekly AI bug-fix proposals

The `Weekly AI bug fixes` GitHub Actions workflow runs every Monday and can also
be started manually from the Actions tab. It uses OpenAI Codex to run the Django
checks and tests, investigate concrete bugs, and open or update a pull request
with focused fixes. Changes are not merged automatically.

To enable it, add an `OPENAI_API_KEY` Actions secret in the repository settings
and allow GitHub Actions to create pull requests under **Settings → Actions →
General → Workflow permissions**. The workflow requires the project
dependencies listed in `requirements-runtime.txt` and runs on Python 3.11.

## Weekly AI dashboard upgrades

The separate **Weekly AI dashboard upgrades** workflow runs each Monday at
**10:43 UTC / Accra time**, or manually through the repository's Actions tab. It
uses the [Codex GitHub Action](https://learn.chatgpt.com/docs/github-action) to
implement one dashboard feature from the
[feature roadmap](docs/dashboard-roadmap.md) and record the work in the
[upgrade log](docs/dashboard-upgrade-log.md).

The first priorities are accessible chart data, chart controls, attention
summaries, summary exports and saved display preferences. The agent checks what
already exists before selecting the next feature. It preserves the original
five-photo home screen and its updated copy.

Each proposal is tested on a fresh runner before a pull request is created on
`codex/weekly-dashboard-upgrades`. Validation includes the full Django suite,
migration drift, JavaScript syntax and a production static-file build. The AI job
has read-only repository permissions; a separate publishing job receives the
permissions to open the pull request. A scope checker rejects changes to the home
screen, dependencies, stored application data, migrations and automation files.
The next run waits while a dashboard proposal is still open. Review and merge
the pull request to release the feature; upgrades are never merged or deployed
automatically.

To enable the workflow, configure the repository's `OPENAI_API_KEY` Actions
secret and allow GitHub Actions to create pull requests under **Settings →
Actions → General → Workflow permissions**, as for the existing bug-fix agent.
Runs use the configured OpenAI API account. Missing credentials produce a clear
setup error without generating a proposal. After setup, choose **Actions →
Weekly AI dashboard upgrades → Run workflow** to start the first upgrade.

## Configuration

Flux reads configuration from environment variables and loads a local `.env` file when present. See [.env.example](.env.example) for the available variable names and placeholder values.

Important settings include:

| Variable | Purpose |
| --- | --- |
| `FLUX_DEBUG` | Enables or disables Django debug mode |
| `FLUX_SECRET_KEY` | Django signing key; required when debug mode is disabled |
| `FLUX_ALLOWED_HOSTS` | Comma-separated allowed host names |
| `FLUX_CSRF_TRUSTED_ORIGINS` | Comma-separated trusted origins |
| `FLUX_SITE_URL` | Base site URL used by application links |
| `FLUX_EMAIL_HOST`, `FLUX_EMAIL_PORT` | SMTP server connection |
| `FLUX_EMAIL_USER`, `FLUX_EMAIL_PASSWORD` | SMTP credentials |
| `FLUX_FROM_EMAIL` | Sender address for application email |

Never commit real credentials or secrets. The `.env` file is excluded from Git; `.env.example` is intended for placeholders only.

## Security and deployment

**Do not deploy this project publicly using development defaults.** Before a live deployment:

- Set `FLUX_DEBUG=false` and configure a new, randomly generated `FLUX_SECRET_KEY`.
- Set correct allowed hosts, trusted origins, and HTTPS settings for the deployment.
- Upgrade legacy Django and dependencies to supported security releases after compatibility testing.
- Use a supported production database for multi-user institutional deployments; the default configuration uses SQLite.
- Configure an HTTPS reverse proxy, durable upload storage, protected backups, and production logging.
- Review existing research-application endpoints and file handling separately; the administrator portal does not remediate all legacy application behavior.
- Protect the included database and any uploaded user data. Do not publish databases containing account or institutional information.

For full deployment prerequisites, security boundaries, database notes, and known limitations, read [ADMIN_PORTAL_README.md](ADMIN_PORTAL_README.md).

## Troubleshooting

### Django reports that `FLUX_SECRET_KEY` is required

When `FLUX_DEBUG=false`, set `FLUX_SECRET_KEY` to a new, secure value before starting the application.

### Administrator portal access is denied

The portal requires an authorized staff administrator. Sign in at `/admin/login/` with an authorized super-administrator, then open `/control/`. A research account alone does not grant portal access.

### Scheduled low-stock emails are not sent

Confirm that SMTP configuration is present, then configure an external scheduler to run `python manage.py send_scheduled_low_stock_alerts` once per minute. The command reports configuration or delivery failures.

## License

See [LICENSE](LICENSE) for the project's usage terms. Review those terms before copying, modifying, or distributing Flux.

## Documentation

- [Administrator Portal Guide](ADMIN_PORTAL_README.md): implementation details, quick start, security, deployment, and limitations.
- [.env.example](.env.example): placeholder environment configuration.
