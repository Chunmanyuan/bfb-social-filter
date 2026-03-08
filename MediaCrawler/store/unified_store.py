# -*- coding: utf-8 -*-
# @Desc: Unified SQLite storage for MediaItem across all platforms

import sqlite3
import os
import time
from typing import Dict, Optional

import config
from tools import utils


DB_PATH = os.path.join(
    config.SAVE_DATA_PATH if config.SAVE_DATA_PATH else "data",
    "media_items.db"
)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS media_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id         TEXT NOT NULL,
    platform        TEXT NOT NULL,
    task_id         TEXT,
    content_type    TEXT,
    title           TEXT,
    desc            TEXT,
    publish_time    INTEGER,
    user_id         TEXT,
    nickname        TEXT,
    avatar          TEXT,
    ip_location     TEXT DEFAULT '',
    liked_count     INTEGER DEFAULT 0,
    comment_count   INTEGER DEFAULT 0,
    share_count     INTEGER DEFAULT 0,
    collected_count INTEGER DEFAULT 0,
    play_count      INTEGER DEFAULT 0,
    coin_count      INTEGER DEFAULT 0,
    danmaku_count   INTEGER DEFAULT 0,
    content_url     TEXT,
    cover_url       TEXT,
    image_urls      TEXT,
    video_url       TEXT,
    tag_list        TEXT,
    source_keyword  TEXT,
    initial_passed  INTEGER DEFAULT 1,
    filter_reason   TEXT,
    media_downloaded INTEGER DEFAULT 0,
    local_media_paths TEXT,
    video_screenshots TEXT,
    ocr_text_joined TEXT,
    final_passed    INTEGER DEFAULT NULL,
    matched_keywords TEXT,
    created_at      INTEGER,
    UNIQUE(platform, item_id, task_id)
);
"""


def _ensure_db():
    """Ensure database and table exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(_CREATE_TABLE_SQL)
    conn.commit()
    conn.close()


def insert_media_item(item: Dict) -> None:
    """
    Insert a media item into the unified SQLite table.
    If (platform, item_id, task_id) already exists, update the record.

    Args:
        item: dict with keys matching column names
    """
    _ensure_db()

    item.setdefault("created_at", int(time.time()))

    columns = [
        "item_id", "platform", "task_id", "content_type",
        "title", "desc", "publish_time",
        "user_id", "nickname", "avatar", "ip_location",
        "liked_count", "comment_count", "share_count", "collected_count",
        "play_count", "coin_count", "danmaku_count",
        "content_url", "cover_url", "image_urls", "video_url",
        "tag_list", "source_keyword",
        "initial_passed", "filter_reason",
        "media_downloaded", "local_media_paths",
        "video_screenshots", "ocr_text_joined", "final_passed", "matched_keywords",
        "created_at",
    ]

    values = [item.get(col) for col in columns]
    placeholders = ", ".join(["?"] * len(columns))
    col_names = ", ".join(columns)

    # ON CONFLICT: update interaction counts + initial_passed (only upgrade)
    update_parts = ", ".join([
        f"{col} = excluded.{col}" for col in [
            "liked_count", "comment_count", "share_count", "collected_count",
            "play_count", "coin_count", "danmaku_count",
        ]
    ])

    sql = f"""
        INSERT INTO media_items ({col_names})
        VALUES ({placeholders})
        ON CONFLICT(platform, item_id, task_id) DO UPDATE SET
            {update_parts}
    """

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(sql, values)
        conn.commit()
        utils.logger.info(
            f"[UnifiedStore] Saved {item.get('platform')} item {item.get('item_id')} "
            f"(passed={item.get('initial_passed')}, task={item.get('task_id')})"
        )
    except Exception as e:
        utils.logger.error(f"[UnifiedStore] Failed to save item {item.get('item_id')}: {e}")
    finally:
        conn.close()


def update_media_downloaded(platform: str, item_id: str, task_id: str, local_paths: str) -> None:
    """Mark an item as having its media downloaded."""
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE media_items SET media_downloaded = 1, local_media_paths = ? "
            "WHERE platform = ? AND item_id = ? AND task_id = ?",
            (local_paths, platform, item_id, task_id)
        )
        conn.commit()
    except Exception as e:
        utils.logger.error(f"[UnifiedStore] Failed to update media status for {item_id}: {e}")
    finally:
        conn.close()
