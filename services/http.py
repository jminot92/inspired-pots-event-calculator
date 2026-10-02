"""Small JSON HTTP client. Never put credentials in URLs or error messages."""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def post_json(url, payload, headers):
    request = Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        raise ValueError(f"Integration returned HTTP {error.code}. Check credentials, permissions and billing.") from None
    except (URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise ValueError("Integration could not be reached or returned an invalid response. Check connectivity and try again.") from None
