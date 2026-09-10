import contextlib
import html
import os
import re
import urllib.parse

import requests
from werkzeug.utils import secure_filename

# Matches the ceiling the upload form applies, so an import cannot slip past it.
MAX_ARTWORK_BYTES = int(os.environ.get("MAX_UPLOAD_SIZE_BYTES", str(20 * 1024 * 1024)))


def extract_cdn_url(html_content):
    html_content = html.unescape(html_content)
    
    cleaned_html = html_content.replace(r'\/', '/')

    cdn_pattern = r'https://cdn\.reframed\.gallery/(?:cdn-cgi/image/[^/]+/)?(originals/[^\s"\'<>]+?\.(?:jpg|jpeg|png|webp))'
    matches = re.findall(cdn_pattern, cleaned_html, re.IGNORECASE)

    if matches:
        return f"https://cdn.reframed.gallery/{matches[0]}"

    return None

def get_image_from_reframed_gallery(gallery_url, location=None):
    """Download the first artwork from a Reframed gallery page.

    Returns the downloaded filename. Errors are raised so an API caller can return
    an appropriate response instead of treating a failed download as a success.
    """
    if not isinstance(gallery_url, str) or not gallery_url.strip():
        raise ValueError("A Reframed gallery URL is required")

    # The address is typed in by hand and this app has no login, so the fetch is kept
    # on Reframed rather than pointed at anything the server itself can reach.
    parsed = urllib.parse.urlsplit(gallery_url.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not (
        host == "reframed.gallery" or host.endswith(".reframed.gallery")
    ):
        raise ValueError("That is not a Reframed gallery address")

    response = requests.get(gallery_url.strip(), timeout=15)
    response.raise_for_status()
    cdn_url = extract_cdn_url(response.text)
    if not cdn_url:
        raise ValueError("Could not find artwork in the Reframed gallery page")

    raw_filename = urllib.parse.unquote(urllib.parse.urlsplit(cdn_url).path.rsplit("/", 1)[-1])
    filename = secure_filename(raw_filename)
    if not filename:
        raise ValueError("The artwork has an invalid filename")

    save_directory = location or os.getcwd()
    os.makedirs(save_directory, exist_ok=True)
    save_path = os.path.join(save_directory, filename)

    img_response = requests.get(cdn_url, stream=True, timeout=30)
    img_response.raise_for_status()
    written = 0
    try:
        with open(save_path, "wb") as file_handle:
            for chunk in img_response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                written += len(chunk)
                if written > MAX_ARTWORK_BYTES:
                    raise ValueError("The artwork is larger than this app accepts")
                file_handle.write(chunk)
    except Exception:
        # A partial file is worse than none: the gallery would list something that
        # no viewer can open, and the TV would refuse it.
        with contextlib.suppress(OSError):
            os.remove(save_path)
        raise

    return filename

if __name__ == "__main__":
    url_input = input("Enter Reframed URL:\n> ")
    if url_input.strip():
        get_image_from_reframed_gallery(url_input)