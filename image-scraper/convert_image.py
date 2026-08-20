#!/usr/bin/env python3
"""
Fast image conversion script using Python PIL/Pillow
Converts images from URLs to PNG format
"""

import sys
import json
import base64
import io
import ssl
import socket
import ipaddress
import time
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, HTTPSHandler
from urllib.error import URLError, HTTPError
from PIL import Image

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)

def _validate_public_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Only absolute HTTP and HTTPS URLs are allowed")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not allowed")

    for result in socket.getaddrinfo(parsed.hostname, parsed.port or 443):
        address = ipaddress.ip_address(result[4][0].split("%", 1)[0])
        if not address.is_global:
            raise ValueError("Private, loopback, and link-local addresses are not allowed")
    return url


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _build_request_profiles(url):
    """
    Build request profiles with browser-like headers.
    Some image CDNs block urllib default headers and return 403.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    referer_host = host
    if host.startswith("static.mobilesentrix."):
        referer_host = host.replace("static.", "www.", 1)
    if not referer_host:
        referer_host = "www.mobilesentrix.ca"

    referer = f"https://{referer_host}/"
    origin = f"https://{referer_host}"

    return [
        {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": referer,
            "Origin": origin,
            "Connection": "keep-alive",
        },
        {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "*/*",
            "Referer": referer,
        },
        {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "*/*",
        },
    ]


def _download_image_data(url, timeout=25):
    _validate_public_url(url)
    profiles = _build_request_profiles(url)
    last_error = None
    deadline = time.monotonic() + max(5, timeout)

    def remaining_timeout():
        return max(3, min(20, deadline - time.monotonic()))

    def is_timeout_error(err):
        if isinstance(err, (TimeoutError, socket.timeout)):
            return True
        reason = getattr(err, "reason", None)
        return isinstance(reason, (TimeoutError, socket.timeout))

    def attempt(context=None):
        nonlocal last_error
        handlers = [_SafeRedirectHandler()]
        if context is not None:
            handlers.append(HTTPSHandler(context=context))
        opener = build_opener(*handlers)
        for headers in profiles:
            if time.monotonic() >= deadline:
                break
            req = Request(url, headers=headers)
            try:
                with opener.open(req, timeout=remaining_timeout()) as response:
                    return response.read()
            except HTTPError as err:
                # Try next profile for common access-block codes.
                last_error = err
                if err.code in (403, 429):
                    continue
                raise
            except (TimeoutError, socket.timeout) as err:
                last_error = err
                break
            except URLError as err:
                last_error = err
                if is_timeout_error(err):
                    break
                continue
        if last_error:
            raise last_error
        raise TimeoutError("Timed out while downloading image")

    try:
        return attempt()
    except URLError as err:
        # Some Python installs miss root certs; fallback to unverified SSL context.
        reason = getattr(err, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError):
            insecure_ctx = ssl._create_unverified_context()
            return attempt(context=insecure_ctx)
        raise


def _is_obvious_non_product_image(img):
    """
    Reject only low-risk junk: tiny assets, very wide bars, or images with a
    tiny amount of non-background content. Real phone/tablet part photos vary a
    lot, so this deliberately avoids clever classification.
    """
    width, height = img.size
    if width < 160 or height < 160:
        return "Image is smaller than minimum product size"

    aspect = width / max(1, height)
    if aspect > 3.2 or aspect < 0.31:
        return "Image aspect ratio looks like a banner/icon"

    sample = img.convert("RGBA")
    sample.thumbnail((160, 160))
    pixels = list(sample.getdata())
    if not pixels:
        return "Empty image"

    content = 0
    for red, green, blue, alpha in pixels:
        if alpha < 12:
            continue
        if red > 246 and green > 246 and blue > 246:
            continue
        content += 1

    content_ratio = content / len(pixels)
    if content_ratio < 0.015:
        return "Image has too little product content"
    return ""


def convert_image_to_png(url, quality=85, timeout=25):
    """
    Download image from URL and convert to PNG format.
    The quality argument is accepted for backwards-compatible CLI calls.
    Returns base64 encoded PNG image data.
    """
    try:
        # Download image with timeout
        image_data = _download_image_data(url, timeout=timeout)

        if not image_data:
            return {'success': False, 'error': 'Empty image payload'}

        # Open image with PIL
        img = Image.open(io.BytesIO(image_data))
        non_product_reason = _is_obvious_non_product_image(img)
        if non_product_reason:
            return {'success': False, 'error': f'Skipped non-product image: {non_product_reason}'}

        # PNG supports alpha, so preserve transparency when present.
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGBA')

        # Convert to PNG.
        output_buffer = io.BytesIO()
        # Avoid optimize=True here: it can turn large WebP images into slow
        # CPU-bound conversions and trigger the Node child-process timeout.
        img.save(output_buffer, format='PNG')
        output_buffer.seek(0)

        # Encode as base64
        png_data = output_buffer.getvalue()
        png_base64 = base64.b64encode(png_data).decode('utf-8')

        return {
            'success': True,
            'data': png_base64,
            'size': len(png_data),
            'format': 'png',
            'quality': quality
        }

    except HTTPError as e:
        return {'success': False, 'error': f'HTTP error {e.code}: {str(e)}'}
    except URLError as e:
        return {'success': False, 'error': f'URL error: {str(e)}'}
    except IOError as e:
        return {'success': False, 'error': f'Image format error: {str(e)}'}
    except Exception as e:
        return {'success': False, 'error': f'Conversion failed: {str(e)}'}

def main():
    """Main entry point for the script"""
    if len(sys.argv) < 2:
        print(json.dumps({'success': False, 'error': 'URL parameter required'}))
        sys.exit(1)

    url = sys.argv[1]
    quality = int(sys.argv[2]) if len(sys.argv) > 2 else 85
    timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 25

    result = convert_image_to_png(url, quality, timeout)
    print(json.dumps(result))

if __name__ == '__main__':
    main()
