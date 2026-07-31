# Language Detection & Site Localization (i18n)

## What this feature does

On a visitor's first request, LinguaShift makes a best-effort guess at their
country from their IP address and switches the **site UI** (buttons, labels,
nav, history table, forms — not the translation feature itself) into a
matching language. A visitor from France sees "Se connecter" instead of
"Log In"; a visitor from Saudi Arabia sees the whole page flipped to
right-to-left Arabic.

This is separate from, and does not affect, the actual **text translation**
feature (MyMemory) — that always translates whatever `source_lang` /
`target_lang` the user picks in the dropdowns, regardless of UI language.

## Decision: cookie, not session

Earlier attempts at this feature tried to store the detected language in
`request.session`. That doesn't work on this Django version (4.2): Django
removed session-based storage from `LocaleMiddleware` years ago. The only
persistence mechanisms `LocaleMiddleware` reads are:

1. the `django_language` cookie (`settings.LANGUAGE_COOKIE_NAME`);
2. the `Accept-Language` request header;
3. `settings.LANGUAGE_CODE` as a final fallback.

So detection results are stored in the same cookie Django's own built-in
`django.views.i18n.set_language` view uses. This means the manual language
switcher (see below) and IP auto-detection compose naturally — whichever ran
last wins, and both survive logging in/out since cookies aren't tied to the
Django session.

## How it works, end to end

```text
Request to "/" (core.views.home)
  │
  ├─ django_language cookie already set? ──yes──> do nothing, LocaleMiddleware
  │                                                 already activated it before
  │                                                 the view ran.
  │
  └─ no cookie yet:
       1. get_client_ip(request)            core/utils.py
       2. get_country(ip)                   core/utils.py  (calls ipinfo.io)
       3. COUNTRY_LANGUAGE.get(country, …)  core/views.py  (country -> lang code)
       4. translation.activate(language)    makes {% trans %} tags in THIS
                                             response use the new language
       5. response.set_cookie("django_language", language)
                                             so every later request (any page)
                                             gets it automatically via
                                             LocaleMiddleware, no extra work.
```

Key files:

| File | Responsibility |
|---|---|
| `core/utils.py` | `get_client_ip()`, `get_country()` — IP → country, via [ipinfo.io](https://ipinfo.io). Fully wrapped in try/except with a 3s timeout; **never raises**, returns `None` on any failure (bad IP, network error, rate limit, timeout). |
| `core/views.py` | `COUNTRY_LANGUAGE` dict (country code → language code) and the detection logic in `home()`. |
| `project/settings.py` | `LANGUAGES` (the 6 languages we ship), `LOCALE_PATHS`, `IPINFO_*` settings, `i18n` template context processor. |
| `project/urls.py` | `path("i18n/", include("django.conf.urls.i18n"))` — wires up Django's built-in `set_language` view for the manual switcher. |
| `core/templates/core/base.html` | The `<html lang=… dir=…>` attributes and the manual language `<select>` in the top bar. |
| `locale/<lang>/LC_MESSAGES/django.po` / `.mo` | The actual translated strings (see "Adding/editing translations" below). |

### Why this can't hang or crash the page anymore

The original bug: `get_country()` called `requests.get()` with no timeout and
no exception handling. If ipinfo.io was slow, blocked, or rate-limited, the
whole Django worker thread blocked or raised an unhandled exception — the
page would spin forever or 500. That's what a colleague saw as "the site
couldn't be shown" with nothing in the browser console (the failure was
entirely server-side).

Now `get_country()`:
- returns `None` immediately for local/private IPs (`127.0.0.1`, `10.x`,
  `172.x`, `192.168.x`) without making a network call at all — useful in dev;
- has a hard 3-second timeout (`IPINFO_TIMEOUT_SECONDS`);
- catches every `requests.RequestException` (timeouts, DNS failures,
  connection refused, HTTP errors) and bad JSON, returning `None`;
- `home()` treats `None` the same as "we don't know" and falls back to the
  default language — the page always renders.

## Supported languages & country mapping

`settings.LANGUAGES` (also the choices in the manual switcher):

| Code | Language |
|---|---|
| `en` | English (default) |
| `fr` | Français |
| `de` | Deutsch |
| `ru` | Русский |
| `ar` | العربية (renders right-to-left) |
| `sw` | Kiswahili |

`COUNTRY_LANGUAGE` in `core/views.py` maps ipinfo's two-letter country codes
to one of the above:

| Language | Countries |
|---|---|
| French | FR, BE, CH, CA, SN, CI |
| German | DE, AT, LI |
| Russian | RU, BY, KZ, KG |
| Arabic | SA, AE, EG, MA, DZ, TN, IQ, JO, LB, LY, SY, YE, OM, QA, KW, BH, SD, PS |
| Swahili | KE, TZ |
| English | UG, and anything not listed above |

Any country not in the dict — or a lookup failure — falls back to the
current active language (English by default). Extending this list is safe:
if you add a country that doesn't have a language catalog compiled, Django
just doesn't find any translations for it and silently displays the English
source text, so it can't break the site.

## Testing this locally (no IP spoofing needed)

You do **not** need to fake your IP to test this. Three options, easiest
first:

1. **Manual language switcher** — the dropdown in the top bar next to the
   theme toggle posts to Django's built-in `set_language` view and sets the
   `django_language` cookie directly. Pick any of the 6 languages and every
   page updates immediately.

2. **Set the cookie by hand** (useful for scripting/CI):

   ```bash
   curl -b "django_language=ar" http://127.0.0.1:8000/
   ```

   or in the browser devtools console:

   ```js
   document.cookie = "django_language=ar; path=/";
   location.reload();
   ```

3. **Actually exercise the IP-detection path** by deleting the
   `django_language` cookie and mocking `core.views.get_country` in a test
   (see `core/tests.py::LanguageDetectionTests` for examples), or by running
   against a real `IPINFO_TOKEN` from a network where `ipinfo.io` is
   reachable and your public IP resolves to a country you care about.

## Adding or editing translated strings

Strings are marked for translation in templates with `{% trans "..." %}` /
`{% blocktrans %}` and in Python with `gettext`/`gettext_lazy` (imported as
`_`). To add a new user-facing string:

1. Wrap it: `{% trans "New label" %}` in a template, or
   `messages.success(request, _("Saved."))` in a view.
2. Regenerate the catalogs:

   ```bash
   python manage.py makemessages -l fr -l de -l ru -l ar -l sw
   ```

3. Open `locale/<lang>/LC_MESSAGES/django.po` and fill in the new
   `msgstr ""` entries for each of the 5 languages.
4. Compile:

   ```bash
   python manage.py compilemessages
   ```

5. Commit both the `.po` (source, human-editable) and `.mo` (compiled binary
   Django actually reads) files.

`.mo` files are binary — if a merge conflict ever touches one, just delete
it and rerun `compilemessages`; never hand-edit it.

## Adding a new language

1. Add it to `LANGUAGES` in `project/settings.py`.
2. Add the relevant country codes to `COUNTRY_LANGUAGE` in `core/views.py`.
3. `python manage.py makemessages -l <code>` and translate the new
   `locale/<code>/LC_MESSAGES/django.po`.
4. `python manage.py compilemessages`.
5. If the language reads right-to-left (like Arabic), no extra work is
   needed — `core/templates/core/base.html` already sets
   `dir="{% if LANGUAGE_BIDI %}rtl{% else %}ltr{% endif %}"` automatically
   based on Django's built-in list of RTL languages.

## Configuration

Copy `.env.example` to `.env`; these are all optional (the feature degrades
to "always English" if unset, never breaks):

```text
IPINFO_TOKEN=
IPINFO_TIMEOUT_SECONDS=3
```

Get a free token at [ipinfo.io](https://ipinfo.io) (their unauthenticated
tier also works, just with a lower rate limit). Never commit a real token —
`IPINFO_TOKEN` stays in `.env`, which is git-ignored.

## Known limitations

- **Static `.js` files are not translated.** `core/static/audio_handler.js`,
  `output_actions.js`, and `document_handler.js` are plain static assets, not
  Django templates, so `{% trans %}` doesn't work inside them. Their few
  runtime strings (e.g. button tooltips) stay in English. The inline
  `<script>` block in `translator.html` *is* translated, since that file is
  template-rendered.
- **RTL support is attribute-level, not a full mirrored layout.** Arabic
  gets `dir="rtl"` (so text reads correctly and the browser reflows most
  flex layouts), but no custom CSS mirroring pass has been done for the more
  bespoke components (cards, stat grid, etc.). Flag any visually broken RTL
  spots for a follow-up CSS pass.
- **ipinfo.io's free/unauthenticated tier is rate-limited.** Under heavy
  traffic without a token, detection will start failing (safely — falling
  back to English) more often. Get a free token for anything beyond local
  testing.
