import os
from typing import Dict, List, Optional, Tuple


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEDIA_CRAWLER_ROOT = os.path.join(PROJECT_ROOT, "MediaCrawler")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _split_csv_paths(raw_value: Optional[str]) -> List[str]:
    if not raw_value:
        return []
    return [part.strip() for part in str(raw_value).split(",") if part.strip()]


def _to_absolute_path(path_str: str, base_root: str, logger=None) -> str:
    """
    Resolve path by a fixed base root.
    Absolute paths are intentionally rejected to avoid carrying machine-specific history.
    """
    if os.path.isabs(path_str):
        if logger:
            logger.warning(f"Skip absolute path (not allowed): {path_str}")
        return ""
    return os.path.normpath(os.path.join(base_root, path_str))


def collect_image_paths(item: Dict, logger=None) -> List[str]:
    """
    Collect image paths by platform rule:
    - bilibili: only video_screenshots (base: PROJECT_ROOT)
    - xhs: local_media_paths (base: MEDIA_CRAWLER_ROOT) + video_screenshots (base: PROJECT_ROOT)
    """
    platform = (item.get("platform") or "").strip().lower()
    source_paths: List[Tuple[str, str]] = []

    if platform == "bilibili":
        source_paths.extend((p, PROJECT_ROOT) for p in _split_csv_paths(item.get("video_screenshots")))
    elif platform == "xhs":
        source_paths.extend((p, MEDIA_CRAWLER_ROOT) for p in _split_csv_paths(item.get("local_media_paths")))
        source_paths.extend((p, PROJECT_ROOT) for p in _split_csv_paths(item.get("video_screenshots")))
    else:
        source_paths.extend((p, MEDIA_CRAWLER_ROOT) for p in _split_csv_paths(item.get("local_media_paths")))
        source_paths.extend((p, PROJECT_ROOT) for p in _split_csv_paths(item.get("video_screenshots")))

    collected: List[str] = []
    seen = set()

    for raw_path, base_root in source_paths:
        abs_path = _to_absolute_path(raw_path, base_root, logger=logger)
        if not abs_path:
            continue

        _, ext = os.path.splitext(abs_path.lower())
        if ext not in IMAGE_EXTENSIONS:
            if logger:
                logger.warning(f"Skip non-image path: {abs_path}")
            continue
        if not os.path.exists(abs_path):
            if logger:
                logger.warning(f"Skip missing image path: {abs_path}")
            continue
        if abs_path in seen:
            continue

        seen.add(abs_path)
        collected.append(abs_path)

    return collected
