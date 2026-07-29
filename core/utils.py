import requests
from django.conf import settings

# IPs that never resolve to a useful country (local dev, private networks).
_LOCAL_IPS = {"127.0.0.1", "::1", "localhost"}


def get_country(ip):
    """Best-effort country lookup for `ip`.

    Network failures, timeouts, and bad responses are swallowed and return
    None so callers can fall back to a default language instead of the
    whole request blowing up.
    """
    if not ip or ip in _LOCAL_IPS or ip.startswith(("10.", "192.168.", "172.")):
        return None

    url = f"{settings.IPINFO_BASE_URL}/{ip}/json"
    params = {"token": settings.IPINFO_TOKEN} if settings.IPINFO_TOKEN else {}

    try:
        response = requests.get(url, params=params, timeout=settings.IPINFO_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None

    return data.get("country")


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")

    return ip
