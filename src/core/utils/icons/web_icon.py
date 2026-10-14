import json
import logging
import os
import re
import tempfile
import time
import urllib.request
from typing import Any
from urllib.parse import urljoin, urlparse


class UrlExtractorUtil:
    """
    Extract the icon and title from URL and save as PNG in the icons dir.
    Falls back to extracting from the manifest.json or manifest.webmanifest.
    Returns the PNG path and page title or None if not found.
    """

    @staticmethod
    def extract_from_url(url: str, icons_dir: str | None) -> tuple[str | None, str | None]:
        try:
            parsed = urlparse(url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"

            manifest_url = None
            page_title = None
            try:
                with urllib.request.urlopen(url, timeout=3) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                title_match = re.search(r"<title\b[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)

                if title_match:
                    page_title = title_match.group(1).strip()
                    if len(page_title) > 30:
                        page_title = page_title[:30] + "..."
                match = re.search(r'<link[^>]+rel=["\']manifest["\'][^>]*href=["\']([^"\']+)["\']', html, re.IGNORECASE)
                if match:
                    manifest_url = urljoin(base_url, match.group(1))
            except Exception:
                manifest_url = None

            # Fallback to default manifest locations if not found in HTML
            # This is useful for sites that don't explicitly link to a manifest
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
                    with urllib.request.urlopen(m_url, timeout=2) as resp:
                        if resp.status == 200:
                            manifest = json.loads(resp.read().decode("utf-8"))
                            manifest_base_url = m_url
                            break
                except Exception:
                    continue
            if not manifest or "icons" not in manifest:
                return None, page_title

            # Find the largest icon >=192x192
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

            # Use the manifest's URL as the base for relative icon URLs
            icon_url = urljoin(manifest_base_url, icon_src) if manifest_base_url else urljoin(base_url, icon_src)
            try:
                with urllib.request.urlopen(icon_url, timeout=5) as icon_resp:
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
