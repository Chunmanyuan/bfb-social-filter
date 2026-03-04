import os
import sqlite3
from typing import Dict, List, Optional


DB_HELPER_DIR = os.path.dirname(os.path.abspath(__file__))
OCR_ROOT = os.path.dirname(DB_HELPER_DIR)
PROJECT_ROOT = os.path.dirname(OCR_ROOT)
DB_PATH = os.path.join(PROJECT_ROOT, "MediaCrawler", "data", "media_items.db")


def get_pending_items(
    task_id: Optional[str] = None,
    item_ids: Optional[List[str]] = None,
    force: bool = False,
) -> List[Dict]:
    if not os.path.exists(DB_PATH):
        return []

    base_query = """
        SELECT platform, item_id, task_id, content_type, local_media_paths, video_screenshots, ocr_text_joined
        FROM media_items
        WHERE initial_passed = 1
          AND media_downloaded = 1
          AND (
                (platform = 'bilibili' AND video_screenshots IS NOT NULL AND video_screenshots != '')
             OR (platform = 'xhs' AND (
                    (local_media_paths IS NOT NULL AND local_media_paths != '')
                 OR (video_screenshots IS NOT NULL AND video_screenshots != '')
                ))
          )
    """
    params: List[str] = []

    if not force:
        base_query += " AND (ocr_text_joined IS NULL OR ocr_text_joined = '')"

    if task_id:
        base_query += " AND task_id = ?"
        params.append(task_id)

    if item_ids:
        placeholders = ",".join(["?"] * len(item_ids))
        base_query += f" AND item_id IN ({placeholders})"
        params.extend(item_ids)

    base_query += " ORDER BY id ASC"

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(base_query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def save_ocr_text(platform: str, item_id: str, task_id: str, ocr_text: str) -> bool:
    if not os.path.exists(DB_PATH):
        return False

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(
            """
            UPDATE media_items
            SET ocr_text_joined = ?
            WHERE platform = ? AND item_id = ? AND task_id = ?
            """,
            (ocr_text, platform, item_id, task_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
