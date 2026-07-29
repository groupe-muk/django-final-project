import requests

TOKEN = "1df2e02bb1b428"

def get_country(ip):
    url = f"https://ipinfo.io/{ip}/json?token={TOKEN}"

    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        return data.get("country")

    return None


def get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded:
        ip = forwarded.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")

    return ip