# -*- coding: utf-8 -*-
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from services.run_manager import run_manager

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = WORKSPACE_ROOT / "MediaCrawler" / "data" / "media_items.db"


def _connect_db() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(status_code=404, detail=f"Database not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _parse_keywords(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    parts = re.split(r"[,，\n]+", str(raw))
    out: List[str] = []
    seen = set()
    for part in parts:
        token = part.strip()
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _task_rows(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            task_id,
            MIN(created_at) AS started_at,
            MAX(created_at) AS ended_at,
            COUNT(*) AS total_crawled,
            SUM(CASE WHEN initial_passed = 1 THEN 1 ELSE 0 END) AS initial_passed_count
        FROM media_items
        GROUP BY task_id
        ORDER BY started_at DESC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def _build_task_labels(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    minute_totals = Counter()
    for item in tasks:
        minute = datetime.fromtimestamp(item["started_at"]).strftime("%Y-%m-%d %H:%M")
        minute_totals[minute] += 1

    minute_seen = defaultdict(int)
    result = []
    for item in tasks:
        minute = datetime.fromtimestamp(item["started_at"]).strftime("%Y-%m-%d %H:%M")
        minute_seen[minute] += 1
        label = minute
        if minute_totals[minute] > 1:
            label = f"{minute}（第{minute_seen[minute]}次）"
        result.append(
            {
                "task_id": item["task_id"],
                "label": label,
                "started_at": item["started_at"],
                "ended_at": item["ended_at"],
                "started_at_text": datetime.fromtimestamp(item["started_at"]).strftime("%Y-%m-%d %H:%M:%S"),
                "total_crawled": int(item["total_crawled"] or 0),
                "initial_passed_count": int(item["initial_passed_count"] or 0),
            }
        )
    return result


def _field_candidates(row: Dict[str, Any]) -> Dict[str, str]:
    platform = (row.get("platform") or "").lower()
    title = str(row.get("title") or "")
    desc = str(row.get("desc") or "")
    ocr = str(row.get("ocr_text_joined") or "")
    ip_location = str(row.get("ip_location") or "")

    if platform == "bilibili":
        return {
            "标题": title,
            "简介": desc,
            "OCR内容": ocr,
        }
    if platform == "xhs":
        return {
            "标题": title,
            "内容": desc,
            "OCR结果": ocr,
            "发帖IP位置": ip_location,
        }
    return {
        "标题": title,
        "内容": desc,
        "OCR内容": ocr,
        "发帖IP位置": ip_location,
    }


def _match_row(row: Dict[str, Any], keywords: List[str], match_mode: str) -> Dict[str, Any]:
    if not keywords:
        return {"matched": True, "matched_keywords": [], "matched_by": [], "score": 0}

    fields = _field_candidates(row)
    normalized_fields = {k: (v or "").lower() for k, v in fields.items()}
    normalized_keywords = [k.lower() for k in keywords]

    matched_keywords: List[str] = []
    matched_by: List[str] = []

    hit_by_keyword = {}
    for keyword_raw, keyword in zip(keywords, normalized_keywords):
        hit_fields = [field_name for field_name, text in normalized_fields.items() if keyword and keyword in text]
        if hit_fields:
            matched_keywords.append(keyword_raw)
            hit_by_keyword[keyword_raw] = hit_fields
            for field_name in hit_fields:
                if field_name not in matched_by:
                    matched_by.append(field_name)

    if match_mode == "and":
        matched = len(hit_by_keyword) == len(keywords)
    else:
        matched = len(hit_by_keyword) > 0

    score = len(matched_keywords) * 10 + len(matched_by)
    return {
        "matched": matched,
        "matched_keywords": matched_keywords,
        "matched_by": matched_by,
        "score": score,
    }


@router.get("/tasks")
async def list_tasks():
    conn = _connect_db()
    try:
        tasks = _build_task_labels(_task_rows(conn))
        return {"tasks": tasks, "latest_task_id": tasks[0]["task_id"] if tasks else None}
    finally:
        conn.close()


@router.get("/results")
async def get_results(
    task_id: Optional[str] = None,
    keywords: Optional[str] = None,
    match_mode: str = "or",
    limit: int = 200,
):
    match_mode = (match_mode or "or").lower().strip()
    if match_mode not in {"or", "and"}:
        raise HTTPException(status_code=400, detail="match_mode must be 'or' or 'and'")

    if limit <= 0:
        limit = 200
    if limit > 1000:
        limit = 1000

    parsed_keywords = _parse_keywords(keywords)
    conn = _connect_db()
    try:
        task_list = _build_task_labels(_task_rows(conn))
        if not task_list:
            return {
                "task_id": None,
                "task_label": None,
                "keywords": parsed_keywords,
                "stats": {
                    "total_crawled": 0,
                    "initial_passed_count": 0,
                    "matched_count": 0,
                    "returned_count": 0,
                },
                "items": [],
            }

        selected_task_id = task_id or task_list[0]["task_id"]
        selected_task = next((x for x in task_list if x["task_id"] == selected_task_id), None)
        if not selected_task:
            raise HTTPException(status_code=404, detail=f"task_id not found: {selected_task_id}")

        rows = conn.execute(
            """
            SELECT
                platform, item_id, task_id, content_type,
                title, desc, publish_time, nickname, ip_location,
                liked_count, comment_count, share_count, collected_count,
                play_count, coin_count, danmaku_count,
                content_url, local_media_paths, video_screenshots,
                ocr_text_joined, created_at
            FROM media_items
            WHERE task_id = ? AND initial_passed = 1
            ORDER BY publish_time DESC, created_at DESC
            """,
            (selected_task_id,),
        ).fetchall()

        filtered_items = []
        for row in rows:
            item = dict(row)
            match_info = _match_row(item, parsed_keywords, match_mode)
            if not match_info["matched"]:
                continue

            publish_ts = item.get("publish_time")
            publish_time_text = ""
            if isinstance(publish_ts, int) and publish_ts > 0:
                publish_time_text = datetime.fromtimestamp(publish_ts).strftime("%Y-%m-%d %H:%M:%S")

            filtered_items.append(
                {
                    "platform": item.get("platform"),
                    "item_id": item.get("item_id"),
                    "task_id": item.get("task_id"),
                    "content_type": item.get("content_type"),
                    "title": item.get("title") or "",
                    "desc": item.get("desc") or "",
                    "ocr_text_joined": item.get("ocr_text_joined") or "",
                    "ip_location": item.get("ip_location") or "",
                    "nickname": item.get("nickname") or "",
                    "publish_time": publish_ts,
                    "publish_time_text": publish_time_text,
                    "content_url": item.get("content_url") or "",
                    "local_media_paths": item.get("local_media_paths") or "",
                    "video_screenshots": item.get("video_screenshots") or "",
                    "metrics": {
                        "liked_count": item.get("liked_count") or 0,
                        "comment_count": item.get("comment_count") or 0,
                        "share_count": item.get("share_count") or 0,
                        "collected_count": item.get("collected_count") or 0,
                        "play_count": item.get("play_count") or 0,
                        "coin_count": item.get("coin_count") or 0,
                        "danmaku_count": item.get("danmaku_count") or 0,
                    },
                    "matched_keywords": match_info["matched_keywords"],
                    "matched_by": match_info["matched_by"],
                    "score": match_info["score"],
                }
            )

        matched_count = len(filtered_items)
        returned_items = filtered_items[:limit]

        return {
            "task_id": selected_task_id,
            "task_label": selected_task["label"],
            "keywords": parsed_keywords,
            "match_mode": match_mode,
            "stats": {
                "total_crawled": selected_task["total_crawled"],
                "initial_passed_count": selected_task["initial_passed_count"],
                "matched_count": matched_count,
                "returned_count": len(returned_items),
            },
            "items": returned_items,
        }
    finally:
        conn.close()


@router.get("/run-config")
async def get_run_config():
    return {"config": run_manager.load_config(), "run_status": run_manager.get_status()}


@router.post("/run-config")
async def save_run_config(payload: Dict[str, Any]):
    cfg = run_manager.load_config()
    merged = dict(cfg)
    merged.update(payload or {})

    if int(merged.get("hours_back", 24)) <= 0:
        raise HTTPException(status_code=400, detail="hours_back must be > 0")
    if int(merged.get("max_notes", 30)) <= 0:
        raise HTTPException(status_code=400, detail="max_notes must be > 0")
    if int(merged.get("max_video_size_mb", 100)) <= 0:
        raise HTTPException(status_code=400, detail="max_video_size_mb must be > 0")
    if int(merged.get("num_frames", 40)) <= 0:
        raise HTTPException(status_code=400, detail="num_frames must be > 0")
    if int(merged.get("dedup_threshold", 5)) < 0:
        raise HTTPException(status_code=400, detail="dedup_threshold must be >= 0")
    if int(merged.get("ocr_workers", 1)) <= 0:
        raise HTTPException(status_code=400, detail="ocr_workers must be > 0")

    ocr_device = str(merged.get("ocr_device", "auto")).strip().lower()
    if ocr_device not in {"auto", "cpu", "gpu"}:
        raise HTTPException(status_code=400, detail="ocr_device must be one of auto/cpu/gpu")
    merged["ocr_device"] = ocr_device

    daily_time_raw = str(merged.get("daily_time", "09:00")).strip()
    parsed_time = None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            parsed_time = datetime.strptime(daily_time_raw, fmt)
            break
        except ValueError:
            continue
    if parsed_time is None:
        raise HTTPException(status_code=400, detail="daily_time must be HH:MM")
    merged["daily_time"] = parsed_time.strftime("%H:%M")

    merged["hours_back"] = int(merged.get("hours_back", 24))
    merged["max_notes"] = int(merged.get("max_notes", 30))
    merged["max_video_size_mb"] = int(merged.get("max_video_size_mb", 100))
    merged["num_frames"] = int(merged.get("num_frames", 40))
    merged["dedup_threshold"] = int(merged.get("dedup_threshold", 5))
    merged["ocr_workers"] = int(merged.get("ocr_workers", 1))
    merged["headless"] = bool(merged.get("headless", True))
    merged["daily_enabled"] = bool(merged.get("daily_enabled", False))
    merged["keywords"] = str(merged.get("keywords", ""))

    saved = run_manager.save_config(merged)
    return {"status": "ok", "config": saved}


@router.post("/run-once")
async def run_once(payload: Optional[Dict[str, Any]] = None):
    started = await run_manager.start_once(overrides=payload or {}, trigger="manual")
    if not started:
        raise HTTPException(status_code=409, detail="A pipeline run is already in progress")
    return {"status": "ok", "message": "Pipeline run started"}


@router.get("/run-status")
async def run_status():
    return run_manager.get_status()
