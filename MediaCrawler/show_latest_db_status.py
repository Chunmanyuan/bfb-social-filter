from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    module_root = Path(__file__).resolve().parent
    db_path = module_root / "data" / "media_items.db"

    if not db_path.exists():
        print(f"未找到数据库文件：{db_path}")
        return 1

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT * FROM media_items ORDER BY created_at DESC LIMIT 10"
        ).fetchall()

        for row in rows:
            print("\n".join(f"  {key} = {row[key]}" for key in row.keys()))
            print("-" * 50)

        tid_row = cur.execute(
            "SELECT task_id FROM media_items ORDER BY created_at DESC LIMIT 1"
        ).fetchone()

        if not tid_row:
            print("\n>> 当前没有数据")
            return 0

        task_id = tid_row[0]
        total = cur.execute(
            "SELECT count(*) FROM media_items WHERE task_id = ?",
            (task_id,),
        ).fetchone()[0]
        passed = cur.execute(
            "SELECT count(*) FROM media_items WHERE task_id = ? AND initial_passed = 1 AND content_type = 'video'",
            (task_id,),
        ).fetchone()[0]
        screenshots = cur.execute(
            "SELECT count(*) FROM media_items WHERE task_id = ? AND video_screenshots IS NOT NULL AND video_screenshots != ''",
            (task_id,),
        ).fetchone()[0]

        print(f"\n>> 当前最新任务批次号: {task_id}")
        print(f"本批次总抓取条目数: {total}")
        print(f"本批次已通过初筛视频数: {passed}")
        print(f"本批次已完成截图抽取数: {screenshots}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
