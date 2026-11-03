"""Safe, asynchronous thumbnail cache for public Rebrickable set images."""

from __future__ import annotations

import os
import queue
import re
import tkinter as tk
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parent.parent
IMAGE_CACHE_PATH = ROOT / "data" / "image-cache"
BUNDLED_IMAGE_PATH = ROOT / "assets" / "set-images"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
THUMBNAIL_SIZE = (250, 155)
ALLOWED_IMAGE_HOSTS = {"cdn.rebrickable.com"}


class SetImageCache:
    """Download public set art in the background and reuse it from local storage."""

    def __init__(self, master: tk.Misc) -> None:
        self.master = master
        self.cache_path = IMAGE_CACHE_PATH
        self.cache_path.mkdir(parents=True, exist_ok=True)
        self._pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="brick-images")
        self._results: queue.Queue[tuple[str, Image.Image | None]] = queue.Queue()
        self._memory: dict[str, Image.Image] = {}
        self._pending: dict[str, list[Callable[[Image.Image | None], None]]] = {}
        self._closed = False
        self.master.after(75, self._drain_results)

    def request(self, set_number: str, image_url: str, callback: Callable[[Image.Image | None], None]) -> None:
        if self._closed:
            return
        key = _safe_name(set_number)
        if key in self._memory:
            callback(self._memory[key])
            return
        if key in self._pending:
            self._pending[key].append(callback)
            return
        self._pending[key] = [callback]
        future = self._pool.submit(self._load, set_number, image_url)
        future.add_done_callback(lambda completed, image_key=key: self._deliver(completed, image_key))

    def close(self) -> None:
        self._closed = True
        self._pool.shutdown(wait=False, cancel_futures=True)

    def _deliver(self, future: Future[Image.Image | None], key: str) -> None:
        try:
            image = future.result()
        except Exception:
            image = None
        if self._closed:
            return
        self._results.put((key, image))

    def _drain_results(self) -> None:
        if self._closed:
            return
        try:
            processed = 0
            while processed < 1:
                key, image = self._results.get_nowait()
                callbacks = self._pending.pop(key, [])
                if image is not None:
                    self._memory[key] = image
                for callback in callbacks:
                    callback(image)
                processed += 1
        except queue.Empty:
            pass
        except tk.TclError:
            return
        self.master.after(80, self._drain_results)

    def _load(self, set_number: str, image_url: str) -> Image.Image | None:
        safe_name = _safe_name(set_number)
        for suffix in (".png", ".webp", ".jpg", ".jpeg"):
            bundled_file = BUNDLED_IMAGE_PATH / f"{safe_name}{suffix}"
            if bundled_file.exists():
                try:
                    with Image.open(bundled_file) as bundled:
                        return _transparent_thumbnail(bundled)
                except (OSError, ValueError):
                    continue
        source_file = self.cache_path / f"{safe_name}.source"
        processed_file = self.cache_path / f"{safe_name}.png"
        legacy_file = self.cache_path / f"{safe_name}.img"
        if processed_file.exists():
            try:
                with Image.open(processed_file) as processed:
                    return processed.convert("RGBA")
            except (OSError, ValueError):
                processed_file.unlink(missing_ok=True)
        if not source_file.exists() and legacy_file.exists():
            source_file = legacy_file
        if not source_file.exists() and not self._download(image_url, source_file):
            return None
        try:
            with Image.open(source_file) as source:
                thumbnail = _transparent_thumbnail(source)
            thumbnail.save(processed_file, format="PNG", optimize=True)
            return thumbnail
        except (OSError, ValueError):
            try:
                processed_file.unlink(missing_ok=True)
            except OSError:
                pass
            return None

    @staticmethod
    def _download(image_url: str, destination: Path) -> bool:
        parsed = urlparse(image_url)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_IMAGE_HOSTS:
            return False
        temporary = destination.with_suffix(".tmp")
        request = urllib.request.Request(image_url, headers={"User-Agent": "BrickLedger/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                content_type = response.headers.get_content_type()
                if not content_type.startswith("image/"):
                    return False
                data = response.read(MAX_IMAGE_BYTES + 1)
                if len(data) > MAX_IMAGE_BYTES:
                    return False
            temporary.write_bytes(data)
            os.replace(temporary, destination)
            return True
        except (OSError, ValueError):
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            return False


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)[:100] or "unknown"


def _transparent_thumbnail(source: Image.Image) -> Image.Image:
    """Remove only light backdrop pixels connected to the image boundary."""
    rgba = source.convert("RGBA")
    work = source.convert("RGB")
    marker = (1, 2, 3)
    width, height = work.size
    step = max(min(width, height) // 24, 1)
    border_points = (
        [(x, 0) for x in range(0, width, step)]
        + [(x, height - 1) for x in range(0, width, step)]
        + [(0, y) for y in range(0, height, step)]
        + [(width - 1, y) for y in range(0, height, step)]
    )
    for point in border_points:
        pixel = work.getpixel(point)
        if min(pixel) >= 210 and max(pixel) - min(pixel) <= 45:
            ImageDraw.floodfill(work, point, marker, thresh=42)

    difference = ImageChops.difference(work, Image.new("RGB", work.size, marker))
    cutout_alpha = difference.convert("L").point([0] + [255] * 255)
    cutout_alpha = cutout_alpha.filter(ImageFilter.GaussianBlur(0.65))
    alpha = ImageChops.multiply(rgba.getchannel("A"), cutout_alpha)
    rgba.putalpha(alpha)

    bounds = alpha.getbbox()
    if bounds:
        rgba = rgba.crop(bounds)
    artwork = ImageOps.contain(rgba, (238, 143), Image.Resampling.LANCZOS)
    thumbnail = Image.new("RGBA", THUMBNAIL_SIZE, (0, 0, 0, 0))
    position = ((THUMBNAIL_SIZE[0] - artwork.width) // 2, (THUMBNAIL_SIZE[1] - artwork.height) // 2)
    thumbnail.alpha_composite(artwork, position)
    return thumbnail
