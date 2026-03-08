import sqlite3
import os
import logging
from typing import List, Tuple

# We will read DB_PATH from the parent project structure or configure it here.
# Assuming standard layout where MediaCrawler is adjacent to VideoScreenshotter
# Moving two levels up from VideoScreenshotter/store/db_helper.py gives us the VideoScreenshotter root
# Moving three levels up gives us the overall project root where MediaCrawler is
DB_HELPER_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_SCREENSHOTTER_ROOT = os.path.dirname(DB_HELPER_DIR)
PROJECT_ROOT = os.path.dirname(VIDEO_SCREENSHOTTER_ROOT)
DB_PATH = os.path.join(PROJECT_ROOT, "MediaCrawler", "data", "media_items.db")

logger = logging.getLogger("VideoScreenshotter.db")

def get_pending_videos(task_id: str = None, item_ids: List[str] = None) -> List[Tuple[str, str, str, str]]:
    """
    Fetch videos that need screenshotting.
    Returns: List of (platform, item_id, task_id, local_media_paths)
    """
    if not os.path.exists(DB_PATH):
        logger.error(f"Database not found at {DB_PATH}")
        return []

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = """
        SELECT platform, item_id, task_id, local_media_paths 
        FROM media_items 
        WHERE content_type = 'video' 
          AND initial_passed = 1 
          AND media_downloaded = 1 
          AND (video_screenshots IS NULL OR video_screenshots = '')
    """
    params = []
    
    if task_id:
        query += " AND task_id = ?"
        params.append(task_id)
        
    if item_ids and len(item_ids) > 0:
        placeholders = ','.join(['?'] * len(item_ids))
        query += f" AND item_id IN ({placeholders})"
        params.extend(item_ids)

    try:
        cursor.execute(query, params)
        results = cursor.fetchall()
        return results
    except Exception as e:
        logger.error(f"Error quering pending videos: {e}")
        return []
    finally:
        conn.close()

def save_video_screenshots(platform: str, item_id: str, screenshots_paths: List[str], task_id: str = None) -> bool:
    """
    Update the video_screenshots column for a specific item.
    """
    if not os.path.exists(DB_PATH):
         return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    paths_str = ",".join(screenshots_paths)
    
    try:
        if task_id:
            cursor.execute(
                "UPDATE media_items SET video_screenshots = ? WHERE platform = ? AND item_id = ? AND task_id = ?",
                (paths_str, platform, item_id, task_id)
            )
        else:
            # Backward compatibility for legacy callers that do not pass task_id.
            cursor.execute(
                "UPDATE media_items SET video_screenshots = ? WHERE platform = ? AND item_id = ?",
                (paths_str, platform, item_id)
            )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error saving screenshots for {item_id}: {e}")
        return False
    finally:
         conn.close()
