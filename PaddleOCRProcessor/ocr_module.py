import os
import argparse
import multiprocessing as mp
import logging
import logging.handlers
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Optional

# Ensure writable runtime cache paths before importing PaddleOCR internals.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("MPLCONFIGDIR", os.path.join(PROJECT_ROOT, ".mplconfig"))
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

from core.ocr_engine import PaddleOCREngine
from core.path_parser import collect_image_paths
from store.db_helper import get_pending_items, save_ocr_text


LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)


log_format = "[%(asctime)s] [%(task_id)s] [%(name)s] [%(levelname)s] - %(message)s"
formatter = logging.Formatter(log_format)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

file_handler = logging.handlers.TimedRotatingFileHandler(
    os.path.join(LOG_DIR, "ocr_processor.log"),
    when="midnight",
    interval=1,
    backupCount=7,
    encoding="utf-8",
)
file_handler.setFormatter(formatter)

logger = logging.getLogger("PaddleOCRProcessor")
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()
logger.addHandler(console_handler)
logger.addHandler(file_handler)


class TaskFilter(logging.Filter):
    def __init__(self, task_id: str = "GLOBAL_TASK"):
        super().__init__()
        self.task_id = task_id

    def filter(self, record):
        record.task_id = self.task_id
        return True


task_filter = TaskFilter()
logger.addFilter(task_filter)

_WORKER_ENGINE = None
_WORKER_DEVICE = "cpu"


def _worker_init(device: str, lang: str, enable_mkldnn: bool):
    """
    Initialize one OCR engine per worker process.
    """
    global _WORKER_ENGINE, _WORKER_DEVICE

    worker_cache_dir = os.path.join(PROJECT_ROOT, ".mplconfig_workers", str(os.getpid()))
    os.makedirs(worker_cache_dir, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = worker_cache_dir
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

    _WORKER_ENGINE = PaddleOCREngine(device=device, lang=lang, enable_mkldnn=enable_mkldnn, logger=None)
    _WORKER_DEVICE = _WORKER_ENGINE.device


def _worker_process_item(item: Dict) -> Dict:
    """
    Worker-side OCR for one DB item.
    """
    global _WORKER_ENGINE, _WORKER_DEVICE

    platform = item["platform"]
    item_id = item["item_id"]
    item_task_id = item["task_id"]
    label = f"{platform}:{item_id}:{item_task_id}"

    try:
        image_paths = collect_image_paths(item, logger=None)
        if not image_paths:
            return {
                "status": "skipped",
                "label": label,
                "platform": platform,
                "item_id": item_id,
                "task_id": item_task_id,
                "images": 0,
                "device": _WORKER_DEVICE,
            }

        texts = _WORKER_ENGINE.extract_text(image_paths)
        text_joined = " ".join(texts).strip() or "[OCR_EMPTY]"
        return {
            "status": "processed",
            "label": label,
            "platform": platform,
            "item_id": item_id,
            "task_id": item_task_id,
            "images": len(image_paths),
            "ocr_text": text_joined,
            "chars": len(text_joined),
            "device": _WORKER_DEVICE,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "label": label,
            "platform": platform,
            "item_id": item_id,
            "task_id": item_task_id,
            "error": str(exc),
            "device": _WORKER_DEVICE,
        }


def run(
    task_id: Optional[str] = None,
    item_ids: Optional[List[str]] = None,
    device: str = "auto",
    dry_run: bool = False,
    force: bool = False,
    lang: str = "ch",
    workers: int = 1,
    enable_mkldnn: bool = False,
) -> Dict:
    """
    OCR module entry point.
    """
    global task_filter
    task_filter.task_id = task_id if task_id else "GLOBAL_TASK"

    logger.info(
        "Starting OCR Processor: task_id=%s, item_ids=%s, device=%s, dry_run=%s, force=%s, lang=%s, workers=%s, enable_mkldnn=%s",
        task_id,
        item_ids,
        device,
        dry_run,
        force,
        lang,
        workers,
        enable_mkldnn,
    )

    pending = get_pending_items(task_id=task_id, item_ids=item_ids, force=force)
    if not pending:
        logger.info("No pending items found for OCR.")
        return {
            "total": 0,
            "processed": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "dry_run": dry_run,
        }

    total = len(pending)
    processed = 0
    updated = 0
    skipped = 0
    failed = 0
    workers = max(1, int(workers))
    effective_device = "cpu"

    if workers == 1:
        engine = PaddleOCREngine(device=device, lang=lang, enable_mkldnn=enable_mkldnn, logger=logger)
        effective_device = engine.device

        for item in pending:
            platform = item["platform"]
            item_id = item["item_id"]
            item_task_id = item["task_id"]
            label = f"{platform}:{item_id}:{item_task_id}"

            image_paths = collect_image_paths(item, logger=logger)
            if not image_paths:
                logger.warning("No valid image paths for %s, skip.", label)
                skipped += 1
                continue

            texts = engine.extract_text(image_paths)
            text_joined = " ".join(texts).strip() or "[OCR_EMPTY]"
            processed += 1

            if dry_run:
                logger.info("Dry-run item=%s, images=%s, chars=%s", label, len(image_paths), len(text_joined))
                continue

            ok = save_ocr_text(
                platform=platform,
                item_id=item_id,
                task_id=item_task_id,
                ocr_text=text_joined,
            )
            if ok:
                updated += 1
                logger.info("Updated OCR text for %s (chars=%s)", label, len(text_joined))
            else:
                failed += 1
                logger.error("Failed to update OCR text for %s", label)
    else:
        logger.info("Parallel OCR enabled with workers=%s", workers)
        with ProcessPoolExecutor(
            max_workers=workers,
            mp_context=mp.get_context("spawn"),
            initializer=_worker_init,
            initargs=(device, lang, enable_mkldnn),
        ) as executor:
            futures = [executor.submit(_worker_process_item, item) for item in pending]
            for future in as_completed(futures):
                result_item = future.result()
                status = result_item["status"]
                effective_device = result_item.get("device", effective_device)
                label = result_item["label"]

                if status == "skipped":
                    skipped += 1
                    logger.warning("No valid image paths for %s, skip.", label)
                    continue

                if status == "failed":
                    failed += 1
                    logger.error("OCR worker failed for %s: %s", label, result_item.get("error"))
                    continue

                processed += 1
                text_joined = result_item["ocr_text"]
                image_count = result_item["images"]
                char_count = result_item["chars"]

                if dry_run:
                    logger.info("Dry-run item=%s, images=%s, chars=%s", label, image_count, char_count)
                    continue

                ok = save_ocr_text(
                    platform=result_item["platform"],
                    item_id=result_item["item_id"],
                    task_id=result_item["task_id"],
                    ocr_text=text_joined,
                )
                if ok:
                    updated += 1
                    logger.info("Updated OCR text for %s (chars=%s)", label, char_count)
                else:
                    failed += 1
                    logger.error("Failed to update OCR text for %s", label)

    result = {
        "total": total,
        "processed": processed,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
        "dry_run": dry_run,
        "device": effective_device,
        "workers": workers,
    }
    logger.info("OCR Processor finished: %s", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Paddle OCR Processor")
    parser.add_argument("--task_id", type=str, help="Process specific task id")
    parser.add_argument("--item_ids", type=str, help="Comma separated item ids")
    parser.add_argument("--device", type=str, default="auto", help="auto/cpu/gpu")
    parser.add_argument("--dry_run", action="store_true", help="Do not write to database")
    parser.add_argument("--force", action="store_true", help="Re-run OCR even if existing text is present")
    parser.add_argument("--lang", type=str, default="ch", help="OCR language, default ch")
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Experimental parallel worker count. Default 1 (parallel disabled).",
    )
    parser.add_argument(
        "--enable_mkldnn",
        action="store_true",
        help="Enable MKLDNN acceleration for CPU inference (may cause crashes on newer Paddle versions on Windows). Default is False.",
    )
    args = parser.parse_args()

    parsed_item_ids = [x.strip() for x in args.item_ids.split(",")] if args.item_ids else None
    run(
        task_id=args.task_id,
        item_ids=parsed_item_ids,
        device=args.device,
        dry_run=args.dry_run,
        force=args.force,
        lang=args.lang,
        workers=args.workers,
        enable_mkldnn=args.enable_mkldnn,
    )
