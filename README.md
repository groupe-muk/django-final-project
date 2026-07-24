# Django Base Project

Minimal Django project scaffold.

## Folder Guide

`project/` is the site configuration package. It holds the global Django setup for the whole site, including settings, root URL routing, and the ASGI/WSGI entry points.

`core/` is the main app package. It is where you put feature-specific code such as views, models, app URLs, forms, tests, and backend Python logic.

For front-end files, use Django templates and static files:

- HTML templates usually go in `core/templates/`
- CSS, JavaScript, and images usually go in `core/static/`

Example layout:

```text
core/
	templates/
		core/
			home.html
	static/
		styles.css
```

## Setup

1. Create a virtualenv and activate it:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Run migrations and start server:

```powershell
python manage.py migrate
python manage.py runserver
```

## Stitch Designs

[Designs](https://stitch.withgoogle.com/projects/18083315923321736018)

## Overall Project Structure

```text
DJANGO-FINAL-PROJECT/         # Root repository directory
├── core/                     # Core Django app folder
│   ├── migrations/           # Database migration files
│   ├── static/               # CSS and static assets
│   │   └── styles.css        # Global stylesheet
│   ├── templates/            # HTML templates folder
│   │   └── core/             # Namespaced folder to avoid layout conflicts
│   │       ├── history.html  # Translation history dashboard page
│   │       └── translator.html # Main translation page
│   ├── admin.py
│   ├── apps.py
│   ├── models.py             # Database models configuration
│   ├── tests.py
│   ├── urls.py               # App-level routing
│   └── views.py              # Application logic (API handling & history queries)
├── project/                  # Project configuration folder
│   ├── asgi.py
│   ├── settings.py           # Global project configuration settings
│   ├── urls.py               # Root-level routing
│   └── wsgi.py
├── .gitignore                # Tells Git which local files to ignore
├── manage.py                 # Django command-line utility
├── README.md                 # Project overview and documentation instructions
└── requirements.txt          # Python environment dependencies

```
## Transciption set up

Run this:

```powershell
pip install django-environ
pip install groq
```

## Translation API

The translator currently uses MyMemory through the Django backend. The planned
fallback is a separately hosted FastAPI service backed by Argos Translate.
See [docs/translation-architecture.md](docs/translation-architecture.md) for the
API contract, configuration, test results, and migration plan.

Install the shared dependencies with either tool:

```bash
pip install -r requirements.txt
```

```bash
uv pip install -r requirements.txt
```
