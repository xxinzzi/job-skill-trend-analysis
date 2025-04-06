from urllib.parse import urlparse, parse_qs, unquote

def extract_real_image_url(image_url):
    parsed = urlparse(image_url)
    query = parse_qs(parsed.query)
    ext_url = query.get("ext", [None])[0]
    if ext_url:
        return unquote(ext_url)
    return image_url