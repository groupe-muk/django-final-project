# LinguaShift - Project Context File

> **Purpose**: This document provides a complete overview of the LinguaShift Django project. Use it as a reference for an AI coding assistant so it can suggest accurate file paths and understand the codebase without needing the full source code.

---

## 1. PROJECT OVERVIEW

**Name**: LinguaShift Translation Hub  
**Stack**: Django 4.2+ (Python web framework), SQLite (dev), Groq/Whisper API (audio transcription)  
**Purpose**: A web-based translation application with audio transcription support, user authentication, translation history tracking, and a polished dark/light themed UI.

---

## 2. DIRECTORY STRUCTURE (with file paths)

```
django-final-project/
├── .gitignore
├── manage.py                          # Django CLI entry point
├── README.md                          # Project docs & setup instructions
├── requirements.txt                   # Dependencies
├── PROJECT_CONTEXT.md                 # THIS FILE - context for AI assistant
│
├── project/                           # Django project configuration package
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py                    # Global settings (DB, auth, installed apps, etc.)
│   ├── urls.py                        # Root URL routing
│   └── wsgi.py
│
├── core/                              # Main Django app
│   ├── __init__.py
│   ├── admin.py                       # Model admin registrations
│   ├── apps.py                        # App config
│   ├── models.py                      # Language & Translation models
│   ├── tests.py
│   ├── urls.py                        # App-level URL routing
│   ├── views.py                       # View functions (translator, history, audio)
│   ├── migrations/
│   │   └── __init__.py
│   ├── static/
│   │   ├── styles.css                 # Global CSS (currently empty)
│   │   └── audio_handler.js           # Audio recording/upload + transcription JS
│   └── templates/
│       └── core/
│           ├── base.html              # Main styled base template (dark/light theme)
│           ├── translator.html        # Standalone translator page (older version)
│           └── history.html           # History dashboard page
│
├── accounts/                          # User authentication app
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py                      # Empty (uses Django's built-in User model)
│   ├── tests.py
│   ├── urls.py                        # Registration + auth URLs
│   ├── views.py                       # Register view
│   ├── migrations/
│   │   └── __init__.py
│   └── templates/
│       └── registration/
│           ├── login.html             # Login page (extends core/base.html)
│           └── register.html          # Registration page (extends core/base.html)
│
└── templates/
    └── base.html                      # Minimal project-level base template (fallback)
```

---

## 3. SETTINGS (project/settings.py) - KEY CONFIGURATIONS

### File: `project/settings.py`

- **SECRET_KEY**: Read from `DJANGO_SECRET_KEY` env var, fallback `"replace-me-with-secure-key"`
- **DEBUG**: Read from `DJANGO_DEBUG` or `DEBUG` env var (default `True`)
- **ALLOWED_HOSTS**: Comma-separated from `DJANGO_ALLOWED_HOSTS` or `ALLOWED_HOSTS`
- **GROQ_API_KEY**: Read from `GROQ_API_KEY` env var (used for Groq/Whisper API calls)
- **Local env file**: `.env` is loaded through `django-environ`; copy `.env.example`
- **INSTALLED_APPS**: `django.contrib.admin`, `auth`, `contenttypes`, `sessions`, `messages`, `staticfiles`, `core`, `accounts`
- **TEMPLATES**: `DIRS` includes `BASE_DIR / "templates"` (project-level templates), `APP_DIRS` is `True`
- **DATABASES**: SQLite (`db.sqlite3`)
- **STATIC_URL**: `"/static/"`
- **LOGIN_URL**: `"login"` (name of the login URL)
- **LOGIN_REDIRECT_URL**: `"home"` (redirects here after login)
- **LOGOUT_REDIRECT_URL**: `"login"` (redirects here after logout)
- **AUTH_PASSWORD_VALIDATORS**: Empty list (no password complexity rules)

---

## 4. URL ROUTING

### Root URLs (`project/urls.py`)

| Path | Include | Namespace |
|------|---------|-----------|
| `admin/` | `admin.site.urls` | admin |
| `""` (root) | `core.urls` | - |
| `accounts/` | `accounts.urls` | - |

### Core App URLs (`core/urls.py`)

| Path | View Name | URL Name | Method |
|------|-----------|----------|--------|
| `""` (root) | `home` | `"home"` | GET |
| `"transcribe/"` | `transcribe_audio` | `"transcribe_audio"` | POST |
| `"translator/"` | `translator` | `"translator"` | GET |
| `"history/"` | `history` | `"history"` | GET |

### Accounts URLs (`accounts/urls.py`)

| Path | View Name | URL Name | Method |
|------|-----------|----------|--------|
| `"register/"` | `register` | `"register"` | GET/POST |
| `""` (empty) | `django.contrib.auth.urls` | (includes login, logout, password reset, etc.) | - |

Django's built-in auth provides these URLs under `accounts/`:
- `accounts/login/` → name: `"login"`
- `accounts/logout/` → name: `"logout"`
- `accounts/password_change/` → name: `"password_change"`
- `accounts/password_change/done/` → name: `"password_change_done"`
- `accounts/password_reset/` → name: `"password_reset"`
- `accounts/password_reset/done/` → name: `"password_reset_done"`
- `accounts/reset/<uidb64>/<token>/` → name: `"password_reset_confirm"`
- `accounts/reset/done/` → name: `"password_reset_complete"`

---

## 5. DATABASE MODELS

### File: `core/models.py`

#### `Language` model
| Field | Type | Constraints |
|-------|------|-------------|
| `code` | `CharField(max_length=8)` | `null=False`, `unique=True` |
| `name` | `CharField(max_length=64)` | `null=False` |
| `is_active` | `BooleanField` | `default=True`, `null=False` |

#### `Translation` model
| Field | Type | Constraints |
|-------|------|-------------|
| `user_id` | `ForeignKey(User)` | `on_delete=CASCADE`, `related_name="translations"` |
| `source_lang_id` | `ForeignKey(Language)` | `on_delete=RESTRICT`, `related_name="language_source"` |
| `target_lang_id` | `ForeignKey(Language)` | `on_delete=RESTRICT`, `related_name="language_target"` |
| `source_text` | `TextField` | `null=False` |
| `translated_text` | `TextField` | `null=False` |
| `was_detected` | `BooleanField` | `null=False`, `default=False` (True if source lang was auto-detected) |
| `input_mode` | `CharField(max_length=16)` | `null=False`, `default="text"` ('text' or 'voice') |
| `was_successful` | `BooleanField` | `null=False`, `default=True` |
| `latency_ms` | `IntegerField` | - |
| `word_count` | `IntegerField` | `default=0`, `null=False` |
| `created_at` | `DateTimeField` | `null=False`, `default=datetime.now()` |

### Accounts models (`accounts/models.py`)
- **Empty** - Uses Django's built-in `django.contrib.auth.models.User`

---

## 6. VIEWS

### File: `core/views.py`

#### `home(request)` → renders `"core/translator.html"`
- Simple render view, no context data passed.

#### `translator(request)` → renders `"core/translator.html"`
- Simple render view, no context data passed.

#### `history(request)` → renders `"core/history.html"`
- Passes hardcoded `entries` list as context.
- Each entry has: `source`, `target`, `text`, `translation`, `time`.
- NOTE: Currently uses static/mock data, NOT querying the Translation model from the database.

#### `transcribe_audio(request)` → returns `JsonResponse`
- **Method**: POST only
- **Input**: `request.FILES['audio_data']` (audio file)
- **Process**: 
  1. Reads `GROQ_API_KEY` from environment variables
  2. Creates a Groq client
  3. Sends audio to Whisper model (`"whisper-large-v3"`) for transcription
  4. Returns transcribed text as JSON: `{"text": "<transcribed_text>"}`
- **Error handling**: Returns `{"error": "<message>"}` with appropriate status codes (400, 405, 500)

### File: `accounts/views.py`

#### `register(request)` → renders `"registration/register.html"` or redirect
- **GET**: Renders registration form using Django's `UserCreationForm`
- **POST**: Validates form, saves user, logs them in automatically, redirects to `"home"`
- **Invalid POST**: Returns `HttpResponse("Invalid form")`

---

## 7. TEMPLATES - DETAILED REFERENCE

### File: `templates/base.html` (Project-level base)
- **Purpose**: Minimal fallback base template
- **Blocks**: `title`, `content`
- **Features**: Simple nav bar with user greeting/logout link or login/register links
- **Extends**: None (top-level)
- **Used by**: Not currently used (superseded by `core/base.html`)

### File: `core/templates/core/base.html` (Main styled base template)
- **Purpose**: Full-featured base template with dark/light theme, sidebar nav, topbar, grid layout
- **Blocks available**:
  - `title` - Page title
  - `extra_head` - Additional head elements (CSS, meta)
  - `body_class` - CSS class on body
  - `topbar` - Top header bar (default provided)
  - `page_heading` - H1 in topbar
  - `page_subtitle` - P in topbar
  - `page_area` - Main content area (default provided with hero + content panel)
  - `hero_title` - Hero section H2
  - `hero_text` - Hero section paragraph
  - `content_title` - Content panel H3
  - `content_subtitle` - Content panel subtitle
  - `content` - Main content block inside content panel
- **Features**: Built-in theme toggle (light/dark), sidebar with navigation, responsive grid layout
- **CSS Variables**: Full dark/light theme support using CSS custom properties on `[data-theme="light"]`
- **JS**: Inline script for theme persistence via `localStorage`

### File: `core/templates/core/translator.html` (Standalone page)
- **Purpose**: The main translator interface page
- **DOES NOT extend** `core/base.html` - it is a fully self-contained HTML page
- **Features**: Two-column card layout (source/target), swap button, translate action button, stats section
- **Has its own**: Full set of CSS variables, inline styles, and structure
- **Key elements**: 
  - Source language card with `.translate-copy`
  - Target language card with `.output-copy`
  - Translate button `.translate-button`
  - Stats cards showing latency, accuracy, today's words

### File: `core/templates/core/history.html` (History dashboard)
- **Purpose**: Displays translation history in a table
- **DOES NOT extend** `core/base.html` - fully self-contained HTML page
- **Features**: Left rail navigation, board layout, table with language pair pills, search box, clear all button
- **Uses Django template engine**: `{% for entry in entries %}` loop to render rows
- **Responsive**: Table collapses to card view on mobile with `data-label` attributes
- **Entries format**: Expects context with `source`, `text`, `translation`, `time` keys

### File: `accounts/templates/registration/login.html`
- **Extends**: `core/base.html`
- **Blocks used**: `title`, `page_heading`, `page_subtitle`, `hero_title`, `hero_text`, `content_title`, `content_subtitle`, `content`
- **Content**: Login form with CSRF token, link to register page

### File: `accounts/templates/registration/register.html`
- **Extends**: `core/base.html`
- **Blocks used**: Same as login.html
- **Content**: Registration form with CSRF token, link to login page

---

## 8. STATIC FILES

### File: `core/static/styles.css`
- **Currently empty** - no CSS rules defined.

### File: `core/static/audio_handler.js`
- **Purpose**: Client-side audio recording and transcription
- **Functions**:
  - `startRecording()` - Initiates microphone recording using `MediaRecorder` API
  - `stopRecording()` - Stops recording and triggers upload
  - `handleFileUpload(event)` - Handles file input for audio upload
  - `sendAudioToDjango(audioFile)` - Sends audio to `/transcribe/` endpoint as `FormData` with CSRF token
  - `getCookie(name)` - Extracts CSRF token from cookies
- **Target input**: Populates `#source-text-input` with transcribed text on success

---

## 9. AUTHENTICATION FLOW

- **Login URL**: `accounts/login/` (URL name: `"login"`)
- **Logout URL**: `accounts/logout/` (URL name: `"logout"`)
- **Registration URL**: `accounts/register/` (URL name: `"register"`)
- **Login redirect**: `"home"` (translator page)
- **Logout redirect**: `"login"` (login page)
- **Auth check**: `{% if user.is_authenticated %}` in templates
- **Nav behavior**: Shows username + logout button when authenticated, login/register links when not

---

## 10. EXISTING ISSUES / IMPROVEMENT OPPORTUNITIES

1. **`core/templates/core/translator.html`** and **`core/templates/core/history.html`** are self-contained pages with duplicate CSS - they do NOT extend `core/base.html`. Consider refactoring to use the base template.
2. **`history` view** uses hardcoded mock data instead of querying the `Translation` model from the database.
3. **No migration files** exist yet for the `Language` and `Translation` models - migrations need to be created and applied.
4. **`transcribe_audio` view** does not save transcriptions to the database.
5. **`styles.css`** is empty - all styling is inline in HTML templates.
6. **No translation API endpoint** is wired up yet - the translate button doesn't perform actual translations.
7. **`accounts/models.py`** and **`core/admin.py`** are empty - no models registered in admin.

---

## 11. DEPENDENCIES (requirements.txt)

```
Django>=4.2,<5
djangorestframework
psycopg2-binary
```

Additional deps from README:
```
django-environ
groq
```

---

## 12. COMMON TASKS - FILE CHANGE GUIDE

When making changes, here's which files to modify based on the task:

| Task | File(s) to modify |
|------|-------------------|
| Add a new page/view | `core/views.py`, `core/urls.py`, create new template in `core/templates/core/` |
| Change UI layout/design | `core/templates/core/base.html` (global), or individual page templates |
| Add a new model field | `core/models.py` + create migration |
| Change auth behavior | `project/settings.py` (redirect URLs), `accounts/views.py` |
| Add new route | `core/urls.py` or `project/urls.py` + corresponding view |
| Modify translation logic | `core/views.py` (the view functions) |
| Change audio transcription | `core/views.py` (backend) and/or `core/static/audio_handler.js` (frontend) |
| Modify login/register forms | `accounts/templates/registration/login.html` or `register.html` |
| Add CSS styling | `core/static/styles.css` or inline `<style>` in templates |
| Add JavaScript | `core/static/audio_handler.js` or inline `<script>` in templates |
| Change database | `project/settings.py` (DATABASES section) |
| Add environment variable | `project/settings.py` (read the env var) |
| Change theme/colors | `core/templates/core/base.html` (CSS variables in `:root` and `body[data-theme="light"]`) |
| Add admin functionality | `core/admin.py` (register models) |
| Save translations to DB | `core/views.py` (modify `transcribe_audio` or add new translate view using `Translation` model) |
| Add password validators | `project/settings.py` (`AUTH_PASSWORD_VALIDATORS`) |
| Deploy to production | `project/settings.py` (DEBUG, ALLOWED_HOSTS, SECRET_KEY, database) |

---

## 13. HOW EXTENDS/INCLUDE CHAIN WORKS

```
Template Inheritance Chain (Auth pages):
  core/templates/core/base.html (main base with theme/sidebar/grid)
    └── accounts/templates/registration/login.html  (extends, fills blocks)
    └── accounts/templates/registration/register.html (extends, fills blocks)

Self-Contained Pages (NO extends):
  core/templates/core/translator.html (standalone HTML)
  core/templates/core/history.html (standalone HTML with Django template tags)

Fallback Base (not actively used):
  templates/base.html (project-level, minimal)
```

---

## 14. KEY NAMING CONVENTIONS

- **App name**: `core` (main), `accounts` (auth)
- **Template namespacing**: Templates in `core/templates/core/` (prevents conflicts)
- **URL names**: `home`, `translator`, `history`, `transcribe_audio`, `register`, `login`, `logout`
- **CSS classes**: Use `kebab-case` (e.g., `app-shell`, `nav-link`, `theme-toggle`)
- **JS functions**: Use `camelCase` (e.g., `startRecording`, `sendAudioToDjango`)

---

*Generated from full codebase analysis. Update this file when project structure changes.*
