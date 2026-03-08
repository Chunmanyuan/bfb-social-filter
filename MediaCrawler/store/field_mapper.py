# -*- coding: utf-8 -*-
# @Desc: Field mappers to convert platform-specific data to unified MediaItem schema

import time
from typing import Dict, List

from var import source_keyword_var


def _safe_int(val, default=0) -> int:
    """Safely convert a value to int."""
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def map_xhs_to_media_item(note_detail: Dict, task_id: str = None) -> Dict:
    """
    Convert XHS note_detail (raw API response) to unified MediaItem dict.

    Args:
        note_detail: raw note detail from XHS API
        task_id: current task batch ID

    Returns:
        dict ready for insert_media_item()
    """
    user_info = note_detail.get("user", {})
    interact_info = note_detail.get("interact_info", {})
    image_list: List[Dict] = note_detail.get("image_list", [])
    tag_list: List[Dict] = note_detail.get("tag_list", [])

    # Process image URLs
    for img in image_list:
        if img.get("url_default", "") != "":
            img["url"] = img.get("url_default")

    image_urls = ",".join([img.get("url", "") for img in image_list])
    cover_url = image_list[0].get("url", "") if image_list else ""

    # Process video URL
    from store.xhs import get_video_url_arr
    video_url = ",".join(get_video_url_arr(note_detail))

    # Process tags
    tags = ",".join([
        tag.get("name", "") for tag in tag_list
        if tag.get("type") == "topic"
    ])

    # Process publish time (XHS uses milliseconds)
    raw_time = note_detail.get("time", 0)
    publish_time = int(raw_time) // 1000 if int(raw_time) > 1e12 else int(raw_time)

    note_id = note_detail.get("note_id", "")
    xsec_token = note_detail.get("xsec_token", "")

    return {
        "item_id": note_id,
        "platform": "xhs",
        "task_id": task_id,
        "content_type": note_detail.get("type", "normal"),
        "title": note_detail.get("title") or note_detail.get("desc", "")[:255],
        "desc": note_detail.get("desc", ""),
        "publish_time": publish_time,
        "user_id": user_info.get("user_id", ""),
        "nickname": user_info.get("nickname", ""),
        "avatar": user_info.get("avatar", ""),
        "ip_location": note_detail.get("ip_location", ""),
        "liked_count": _safe_int(interact_info.get("liked_count")),
        "comment_count": _safe_int(interact_info.get("comment_count")),
        "share_count": _safe_int(interact_info.get("share_count")),
        "collected_count": _safe_int(interact_info.get("collected_count")),
        "play_count": 0,
        "coin_count": 0,
        "danmaku_count": 0,
        "content_url": f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=pc_search",
        "cover_url": cover_url,
        "image_urls": image_urls,
        "video_url": video_url,
        "tag_list": tags,
        "source_keyword": source_keyword_var.get(),
        "created_at": int(time.time()),
    }


def map_bilibili_to_media_item(video_item: Dict, task_id: str = None) -> Dict:
    """
    Convert Bilibili video_item (from get_video_info_task) to unified MediaItem dict.

    Args:
        video_item: raw video item containing "View" and "Card" keys
        task_id: current task batch ID

    Returns:
        dict ready for insert_media_item()
    """
    view = video_item.get("View", {})
    stat = view.get("stat", {})
    owner = view.get("owner", {})

    video_id = str(view.get("aid", ""))

    return {
        "item_id": video_id,
        "platform": "bilibili",
        "task_id": task_id,
        "content_type": "video",
        "title": view.get("title", "")[:500],
        "desc": view.get("desc", "")[:500],
        "publish_time": view.get("pubdate", 0),
        "user_id": str(owner.get("mid", "")),
        "nickname": owner.get("name", ""),
        "avatar": owner.get("face", ""),
        "ip_location": "",
        "liked_count": _safe_int(stat.get("like")),
        "comment_count": _safe_int(stat.get("reply")),
        "share_count": _safe_int(stat.get("share")),
        "collected_count": _safe_int(stat.get("favorite")),
        "play_count": _safe_int(stat.get("view")),
        "coin_count": _safe_int(stat.get("coin")),
        "danmaku_count": _safe_int(stat.get("danmaku")),
        "content_url": f"https://www.bilibili.com/video/av{video_id}",
        "cover_url": view.get("pic", ""),
        "image_urls": "",
        "video_url": "",
        "tag_list": "",
        "source_keyword": source_keyword_var.get(),
        "created_at": int(time.time()),
    }
