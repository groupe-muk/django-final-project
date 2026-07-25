# Translation Architecture

## Decision

LinguaShift will integrate translation providers in two stages:

1. Start with the hosted MyMemory REST API and evaluate its quality and limits.
2. If MyMemory is too constrained, replace it with a self-hosted FastAPI service
   backed by Argos Translate.

The browser always talks to Django. Django owns validation, provider credentials,
error handling, and translation history. It then calls the configured translation
provider over HTTP.

```text
Browser -> Django -> MyMemory API
                   -> Future FastAPI/Argos API
```

This keeps provider details out of the browser and gives the Django application a
stable interface even if the provider changes.

## Stage 1: MyMemory

Endpoint:

```text
GET https://api.mymemory.translated.net/get
```

Parameters:

- `q`: UTF-8 source segment, limited by MyMemory to 500 bytes.
- `langpair`: source and target codes separated by `|`.
- `mt=1`: allow machine-translation results.
- `de`: optional contact email configured on the server.
- `key`: optional MyMemory key configured on the server.

The Django endpoint is:

```text
POST /api/translate/
```

Example request:

```json
{
  "source_text": "Hello world",
  "source_lang": "en",
  "target_lang": "fr"
}
```

Example response:

```json
{
  "translated_text": "Bonjour tout le monde",
  "match": 1,
  "latency_ms": 420,
  "word_count": 2,
  "provider": "mymemory"
}
```

Configuration:

```text
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
GROQ_API_KEY=
MYMEMORY_BASE_URL=https://api.mymemory.translated.net
MYMEMORY_CONTACT_EMAIL=
MYMEMORY_API_KEY=
MYMEMORY_TIMEOUT_SECONDS=10
```

Copy `.env.example` to `.env` for local development. Django loads this file
through `django-environ`. Existing deployments using `DJANGO_DEBUG` and
`DJANGO_ALLOWED_HOSTS` remain supported and take precedence over the shorter
local variable names.

### Evaluation criteria

Before moving to Argos, test MyMemory for:

- translation quality across the language pairs required by the class;
- the practical impact of the 500-byte segment limit;
- daily quota reliability;
- latency and service availability;
- correct handling of non-Latin UTF-8 input.

### Initial smoke test

On 2026-07-24, three requests were sent through the complete Django endpoint:

| Pair | Source | Result | Match | Latency |
| --- | --- | --- | ---: | ---: |
| EN → FR | Good morning, how are you? | Bonjour comment allez vous | 97% | 1673 ms |
| EN → SW | Welcome to our translation application. | Karibu kwenye programu yetu ya kutafsiri. | 85% | 1000 ms |
| EN → ES | Django makes web development faster. | Django hace que el desarrollo web sea más rápido. | 85% | 1036 ms |

All returned HTTP 200 responses. This is enough to continue evaluating MyMemory,
but not enough to establish its daily quota reliability or quality on longer and
more technical inputs.

## Stage 2: FastAPI and Argos Translate

If MyMemory is not sufficient, deploy a separate service:

```text
Django -> HTTPS -> FastAPI -> Argos Translate models
```

Proposed API:

- `POST /translate` translates one request.
- `GET /languages` lists installed language pairs.
- `GET /health` reports whether the service and models are ready.

The service should:

- install models during image build or deployment, never during a user request;
- begin with only the required language pairs;
- use persistent model storage;
- run one worker initially to avoid duplicating model memory;
- require an API key and HTTPS;
- return a stable JSON response matching the Django provider interface.

The FastAPI service should have its own dependency file so Django contributors do
not need to install the machine-learning runtime:

```text
fastapi
uvicorn[standard]
argostranslate
```

Django will replace only its provider client; the browser-facing endpoint and UI
will remain unchanged.
