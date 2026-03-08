import os
import logging
import logging.handlers
from typing import List
from store.db_helper import get_pending_videos, save_video_screenshots
from core.screencap import extract_and_deduplicate_frames

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Setup standardized logging
log_format = '[%(asctime)s] [%(task_id)s] [%(name)s] [%(levelname)s] - %(message)s'
formatter = logging.Formatter(log_format)

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Daily Rotating File Handler
log_file = os.path.join(LOG_DIR, "screenshotter.log")
file_handler = logging.handlers.TimedRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=7, encoding='utf-8')
file_handler.setFormatter(formatter)

logger = logging.getLogger("VideoScreenshotter")
logger.setLevel(logging.INFO)
# Clear existing handlers to avoid duplicates if run multiple times
if logger.hasHandlers():
    logger.handlers.clear()
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Custom extra dict to inject task_id into formatter
class TaskFilter(logging.Filter):
    def __init__(self, task_id="GLOBAL_TASK"):
        super().__init__()
        self.task_id = task_id
        
    def filter(self, record):
        record.task_id = self.task_id
        return True

task_filter = TaskFilter()
logger.addFilter(task_filter)

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data", "screenshots")

def run(task_id: str = None, item_ids: List[str] = None, num_frames: int = 40, dedup_threshold: int = 5, debug: bool = False) -> int:
    """
    Main entry point for the Video Screenshot Module.
    
    Args:
        task_id: Process all pending videos for this specific task
        item_ids: Alternatively, process specific video item IDs
        num_frames: Total number of frames to uniformly sample from the video (default: 40)
        dedup_threshold: The acceptable Hamming distance for aHash comparison. 
                         Lower means stricter deduplication. (default: 5)
                         
    Returns:
        Number of videos successfully processed.
    """
    # Set task_id for logger
    global task_filter
    task_filter.task_id = task_id if task_id else "GLOBAL_TASK"

    logger.info(f"Starting Video Screenshotter: task_id={task_id}, item_ids={item_ids}, "
                f"num_frames={num_frames}, dedup_threshold={dedup_threshold}, debug={debug}")
                
    videos_to_process = get_pending_videos(task_id=task_id, item_ids=item_ids)
    
    if not videos_to_process:
        logger.info("No videos found awaiting screenshots.")
        return 0
        
    logger.info(f"Found {len(videos_to_process)} videos to process.")
    success_count = 0
    
    for platform, item_id, row_task_id, local_media_paths in videos_to_process:
        logger.info(f"Processing video item_id: {item_id} (Platform: {platform})")
        
        # 1. Parse local media paths 
        # local_media_paths is stored as a relative path string like "data/bili/videos/xxx/video.mp4"
        # We need to construct the absolute path to the MediaCrawler directory
        media_crawler_root = os.path.join(os.path.dirname(PROJECT_ROOT), "MediaCrawler")
        
        video_paths = [p.strip() for p in local_media_paths.split(',') if p.strip()]
        if not video_paths:
            logger.warning(f"No valid local media path found for {item_id}. Skipping.")
            continue
            
        video_rel_path = video_paths[0] 
        video_abs_path = os.path.join(media_crawler_root, video_rel_path)
        
        if not os.path.exists(video_abs_path):
            logger.error(f"Video file missing at disk: {video_abs_path}")
            continue
            
        # 2. Extract and Deduplicate
        item_output_dir = os.path.join(OUTPUT_DIR, platform, item_id)
        
        try:
            retained_frames = extract_and_deduplicate_frames(
                video_path=video_abs_path,
                output_dir=item_output_dir,
                num_frames=num_frames,
                dedup_threshold=dedup_threshold,
                debug_mode=debug
            )
            
            # 3. Save to database
            if save_video_screenshots(platform, item_id, retained_frames, task_id=row_task_id):
                logger.info(f"Successfully processed and saved {len(retained_frames)} screenshots for {item_id}.")
                success_count += 1
            else:
                logger.error(f"Failed to update database for {item_id}.")
                
        except Exception as e:
            logger.error(f"Error during extraction for {item_id}: {e}")
            
    logger.info(f"Finished processing. Success: {success_count}/{len(videos_to_process)}")
    return success_count

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run Video Screenshotting")
    parser.add_argument("--task_id", type=str, help="Process specific task_id")
    parser.add_argument("--item_ids", type=str, help="Comma separated item_ids")
    parser.add_argument("--num_frames", type=int, default=40, help="Number of frames to sample")
    parser.add_argument("--threshold", type=int, default=5, help="aHash deduplication threshold")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode to save original frames separately")
    
    args = parser.parse_args()
    
    item_ids_list = [i.strip() for i in args.item_ids.split(',')] if args.item_ids else None
    
    run(task_id=args.task_id, item_ids=item_ids_list, num_frames=args.num_frames, dedup_threshold=args.threshold, debug=args.debug)
