import html
import json
import logging
import os
import re
import tempfile
import time
import urllib.request
from http.client import HTTPResponse
from typing import Any
from urllib.parse import urljoin, urlparse

# sites block Python's User-Agent or send an "unsupported browser" page, Meta also wants Sec-Fetch-Mode
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Sec-Fetch-Mode": "navigate",
}


def _open(url: str, timeout: float) -> HTTPResponse:
    return urllib.request.urlopen(urllib.request.Request(url, headers=_HEADERS), timeout=timeout)


def get_web_icon(url: str) -> tuple[str | None, str | None]:
    """Website icon from its web app manifest, saved as a temp PNG, and the page title."""
    try:
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        manifest_url = None
        page_title = None
        try:
            with _open(url, 3) as resp:
                page = resp.read().decode("utf-8", errors="ignore")
            title_match = re.search(r"<title\b[^>]*>(.*?)</title>", page, re.IGNORECASE | re.DOTALL)

            if title_match:
                page_title = html.unescape(title_match.group(1)).strip()
                if len(page_title) > 30:
                    page_title = page_title[:30] + "..."
            match = re.search(r'<link[^>]+rel=["\']manifest["\'][^>]*href=["\']([^"\']+)["\']', page, re.IGNORECASE)
            if match:
                manifest_url = urljoin(base_url, match.group(1))
        except Exception:
            manifest_url = None

        # many sites don't link their manifest but still have one here
        manifest_urls: list[str] = []
        if manifest_url:
            manifest_urls.append(manifest_url)
        manifest_urls += [
            urljoin(base_url, "manifest.webmanifest"),
            urljoin(base_url, "manifest.json"),
        ]

        manifest = None
        manifest_base_url = None
        for m_url in manifest_urls:
            try:
                with _open(m_url, 2) as resp:
                    if resp.status == 200:
                        manifest = json.loads(resp.read().decode("utf-8"))
                        manifest_base_url = m_url
                        break
            except Exception:
                continue
        if not manifest or "icons" not in manifest:
            return None, page_title

        # first icon of 192 px or more, else the largest
        icons = manifest["icons"]
        best_icon: dict[str, Any] | None = None
        fallback_icon: dict[str, Any] | None = None
        best_size = 0
        for icon in icons:
            purpose = icon.get("purpose", "").strip().lower()
            if purpose == "monochrome":
                continue
            sizes = icon.get("sizes", "")
            if not sizes:
                continue
            for size in sizes.split():
                try:
                    w, h = map(int, size.lower().split("x"))
                    if w >= 192 and h >= 192:
                        best_icon = icon
                        break
                    if w * h > best_size:
                        fallback_icon = icon
                        best_size = w * h
                except Exception:
                    continue
            if best_icon:
                break

        if not best_icon and fallback_icon is not None:
            best_icon = fallback_icon
        if not best_icon:
            return None, page_title

        icon_src = best_icon.get("src")
        if not icon_src:
            return None, page_title

        # icon paths are relative to the manifest
        icon_url = urljoin(manifest_base_url, icon_src) if manifest_base_url else urljoin(base_url, icon_src)
        try:
            with _open(icon_url, 5) as icon_resp:
                if icon_resp.status != 200:
                    return None, page_title
                icon_data = icon_resp.read()
        except Exception:
            return None, page_title

        temp_dir = tempfile.gettempdir()
        temp_png = os.path.join(temp_dir, f"{int(time.time() * 1000)}.png")
        with open(temp_png, "wb") as f:
            f.write(icon_data)
        return temp_png, page_title
    except Exception as e:
        logging.error("Failed to extract icon from url %s: %s", url, e)
        return None, None
