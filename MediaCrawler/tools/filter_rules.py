import config
from tools import utils


class ItemFilter:
    """
    初筛规则集合。当前已实现：
    - check_publish_time: 时间窗口过滤
    - check_video_size: 视频大小拦截

    后续可扩展方向（直接在此类中新增 @staticmethod 方法即可）：
    - 标题/描述关键词黑白名单
    - 标签(tag)匹配过滤
    - 博主ID/昵称黑白名单
    - 互动数据阈值(最低点赞数等)
    """
    @staticmethod
    def check_publish_time(timestamp_s: int) -> int:
        """
        Check if the item's publish time is within the configured range.
        :param timestamp_s: Publish time timestamp in seconds
        :return: 
            1: Item is within the valid time range (or filtering is disabled).
            -1: Item is strictly OLDER than the start boundary (trigger cutoff).
            0: Item is NEWER than the end boundary (skip this item, but keep crawling).
        """
        if not config.FILTER_TIME_RANGE.get("enable", False):
            return 1
            
        start_ts = config.FILTER_TIME_RANGE.get("start_timestamp_s", 0)
        end_ts = config.FILTER_TIME_RANGE.get("end_timestamp_s", 0)
        
        # If both are 0, it means it's not configured properly, skip filtering
        if start_ts == 0 and end_ts == 0:
            return 1
            
        if timestamp_s < start_ts:
            return -1
        elif timestamp_s > end_ts:
            return 0
            
        return 1

    @staticmethod
    def check_video_size(content_length_bytes: int) -> bool:
        """
        Check if the video size is within the allowed limit.
        :param content_length_bytes: Size of the video in bytes.
        :return: True if allowed or no limit, False if too large.
        """
        max_mb = config.MAX_VIDEO_SIZE_MB
        if max_mb <= 0:
            return True
            
        max_bytes = max_mb * 1024 * 1024
        if content_length_bytes > max_bytes:
            utils.logger.warning(
                f"[ItemFilter.check_video_size] Video size {content_length_bytes / 1024 / 1024:.2f} MB "
                f"exceeds the limit of {max_mb} MB. Dropping download."
            )
            return False
            
        return True
