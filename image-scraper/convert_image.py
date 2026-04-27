#!/usr/bin/env python3
"""
Fast image conversion script using Python PIL/Pillow
Converts images from URLs to JPG format with optimized compression
"""

import sys
import json
import base64
import io
import ssl
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from PIL import Image

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
)


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
    profiles = _build_request_profiles(url)
    last_error = None

    def attempt(context=None):
        nonlocal last_error
        for headers in profiles:
            req = Request(url, headers=headers)
            try:
                with urlopen(req, timeout=timeout, context=context) as response:
                    return response.read()
            except HTTPError as err:
                # Try next profile for common access-block codes.
                last_error = err
                if err.code in (403, 429):
                    continue
                raise
            except URLError as err:
                last_error = err
                continue
        if last_error:
            raise last_error
        raise URLError("Unknown download error")

    try:
        return attempt()
    except URLError as err:
        # Some Python installs miss root certs; fallback to unverified SSL context.
        reason = getattr(err, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError):
            insecure_ctx = ssl._create_unverified_context()
            return attempt(context=insecure_ctx)
        raise


def convert_image_to_jpg(url, quality=85, timeout=25):
    """
    Download image from URL and convert to JPG format
    Returns base64 encoded JPG image data
    """
    try:
        # Download image with timeout
        image_data = _download_image_data(url, timeout=timeout)
        
        if not image_data:
            return {'success': False, 'error': 'Empty image payload'}
        
        # Open image with PIL
        img = Image.open(io.BytesIO(image_data))
        
        # Convert RGBA to RGB (flatten transparency)
        if img.mode in ('RGBA', 'LA', 'P'):
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = rgb_img
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Convert to JPG with specified quality
        output_buffer = io.BytesIO()
        img.save(output_buffer, format='JPEG', quality=quality, optimize=True)
        output_buffer.seek(0)
        
        # Encode as base64
        jpg_data = output_buffer.getvalue()
        jpg_base64 = base64.b64encode(jpg_data).decode('utf-8')
        
        return {
            'success': True,
            'data': jpg_base64,
            'size': len(jpg_data),
            'format': 'jpeg',
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
    
    result = convert_image_to_jpg(url, quality, timeout)
    print(json.dumps(result))

if __name__ == '__main__':
    main()
