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

## Document translation

Upload a PDF, DOCX, TXT, PNG, or JPG from the translator page. LinguaShift:

1. Extracts text locally for TXT/DOCX/digital PDFs (`pypdf`, `python-docx`).
2. Uses the free [OCR.space](https://ocr.space/ocrapi) API for images and scanned PDFs.
3. Chunk-translates through MyMemory (500 UTF-8 byte segments).
4. Lets you download the result as `.docx` or `.txt`.

Free-tier limits to keep in mind:

- OCR.space: about 1 MB per file, 3 PDF pages, and a daily request cap.
- Extracted text is capped at `DOCUMENT_MAX_EXTRACT_BYTES` (default 10 000) before translation.

Set `OCR_SPACE_API_KEY` in `.env` when testing scanned images/PDFs. Born-digital
TXT/DOCX/PDF text extraction works without that key.

Install the shared dependencies with either tool:

```bash
pip install -r requirements.txt
```

```bash
uv pip install -r requirements.txt
```

Create a local environment file:

```bash
cp .env.example .env
```

The example enables local development on `localhost` and `127.0.0.1`. Add
`GROQ_API_KEY` only when testing audio transcription. Add `OCR_SPACE_API_KEY`
when testing scanned document OCR. MyMemory works without an API key for the
initial translation evaluation.

## Deploy to Render with Docker

The repository includes a production Docker image and a Render Blueprint. The
Blueprint provisions:

- a Docker-based Django web service;
- a required `DATABASE_URL` environment variable for an external PostgreSQL
  provider such as Neon;
- a generated Django secret key;
- a `/health/` readiness check.

The container runs database migrations before starting Gunicorn. This supports
Render's free web-service tier, where pre-deploy commands are unavailable.

1. Push this repository to GitHub.
2. In Render, open **Blueprints**, select **New Blueprint Instance**, and connect
   the repository.
3. Render detects `render.yaml`. Review the `linguashift` service, then apply
   the Blueprint.
4. Enter the pooled Neon PostgreSQL URL as `DATABASE_URL`, plus `GROQ_API_KEY`
   and `MYMEMORY_CONTACT_EMAIL`, when Render prompts for environment values.
5. Wait for `/health/` to report HTTP 200, then open the generated
   `onrender.com` URL.

For a custom domain, set `DJANGO_ALLOWED_HOSTS` to its hostname and set
`DJANGO_CSRF_TRUSTED_ORIGINS` to its complete HTTPS origin. Multiple values are
comma-separated. After confirming the domain is HTTPS-only, optionally set
`DJANGO_SECURE_HSTS_SECONDS`; leave it at `0` while initially testing the
deployment.

The Blueprint uses Render's free web-service plan for demonstration. Free web
services sleep after inactivity; change the service `plan` before using this as
a production deployment. Database retention and limits are controlled by the
selected Neon plan.

### Run the production image locally

Build and start the image with a local SQLite database:

```bash
docker build -t linguashift .

docker run --rm --detach \
  --name linguashift-local \
  -p 8000:8000 \
  -e DATABASE_URL=sqlite:////tmp/linguashift.sqlite3 \
  -e DJANGO_SECRET_KEY=local-docker-secret-for-testing-only \
  -e DJANGO_DEBUG=False \
  -e DJANGO_SECURE_SSL_REDIRECT=False \
  -e DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 \
  linguashift
```

Check the running application:

```bash
curl http://localhost:8000/health/
curl --head http://localhost:8000/
curl --head http://localhost:8000/static/styles.css
docker logs linguashift-local
```

Run the Django test suite inside the built image:

```bash
docker run --rm \
  --entrypoint python \
  -e DATABASE_URL=sqlite:////tmp/linguashift-tests.sqlite3 \
  linguashift manage.py test
```

Stop and remove the local container:

```bash
docker stop linguashift-local
```

Set `DATABASE_URL` to a PostgreSQL connection URL to exercise the same database
configuration used on Render. Never put real Neon or Groq credentials in the
Dockerfile, image, or committed files.
