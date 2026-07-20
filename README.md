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
