import cv2
import os
import logging
from typing import List
from .image_algo import ahash, hamming_distance

logger = logging.getLogger("VideoScreenshotter")

def extract_and_deduplicate_frames(
    video_path: str,
    output_dir: str,
    num_frames: int = 40,
    dedup_threshold: int = 5,
    debug_mode: bool = False
) -> List[str]:
    """
    Extract frames from a video uniformly, deduplicate them based on aHash, 
    save the retained frames to output_dir, and return their absolute paths.
    """
    if not debug_mode:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
    else:
        all_frames_dir = os.path.join(output_dir, "原始截图")
        dedup_dir = os.path.join(output_dir, "去重后图片")
        os.makedirs(all_frames_dir, exist_ok=True)
        os.makedirs(dedup_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"Failed to open video file: {video_path}")
        return []

    total_frames_in_video = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = total_frames_in_video / fps if fps > 0 else 0
    
    if total_frames_in_video == 0:
        logger.warning(f"Video {video_path} has 0 frames.")
        cap.release()
        return []

    # Calculate frame indices to extract uniformly
    if total_frames_in_video <= num_frames:
        frame_indices = list(range(total_frames_in_video))
    else:
        # Uniformly distribute num_frames across total_frames_in_video
        step = total_frames_in_video / num_frames
        frame_indices = [int(i * step) for i in range(num_frames)]
        
    retained_paths = []
    last_hash = ""
    
    logger.debug(f"Targeting {len(frame_indices)} frames from {video_path} (Duration: {duration:.2f}s)")

    for idx, frame_idx in enumerate(frame_indices):
        # Set frame position
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        
        if not ret or frame is None:
            logger.warning(f"Failed to read frame at index {frame_idx}")
            continue
            
        file_name = f"frame_{idx:03d}.jpg"
        
        # In debug mode, unconditionally save to '原始截图'
        if debug_mode:
            all_path = os.path.join(all_frames_dir, file_name)
            cv2.imwrite(all_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            
        # Calculate Hash
        current_hash = ahash(frame)
        if not current_hash:
            continue
            
        # Deduplication logic
        is_duplicate = False
        if last_hash != "":
            dist = hamming_distance(last_hash, current_hash)
            if dist <= dedup_threshold:
                is_duplicate = True
                
        if not is_duplicate:
            # Save frame to final destination
            if debug_mode:
                save_path = os.path.join(dedup_dir, file_name)
            else:
                save_path = os.path.join(output_dir, file_name)
            
            # Use OpenCV to save the image (jpeg quality 90)
            cv2.imwrite(save_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            retained_paths.append(os.path.abspath(save_path))
            
            # Update last hash only if we keep the frame
            last_hash = current_hash
            
    cap.release()
    logger.info(f"Extracted {len(frame_indices)} frames, retained {len(retained_paths)} after deduplication")
    
    return retained_paths
