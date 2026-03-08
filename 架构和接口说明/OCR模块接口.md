# OCR提取模块 (PaddleOCRProcessor) — 交接文档

> 本文档面向后续开发者，说明 OCR 模块的功能、接口定义、数据库读写规则和联调方式。

---

## 1. 模块功能

OCR 模块负责读取已落盘媒体资源中的图片，调用 PaddleOCR 提取文本，并将结果回写到统一数据库字段 `ocr_text_joined`。

核心能力：
- 统一入口 `run(...)`，支持按批次和按条目处理
- 平台差异化取图规则（B站仅截图，小红书图片+截图）
- 幂等处理（默认不重复跑已有 OCR 的条目）
- 支持 `dry_run`（仅统计不落库）和 `force`（覆盖重跑）
- 支持动态关闭 MKLDNN（`enable_mkldnn=False`），解决 Windows 下特定 Paddle 版本的崩溃问题
- 支持实验性并行参数 `workers`，默认关闭（`workers=1`）

---

## 2. 启动方式

### 方式 A：函数调用（推荐给调度脚本/上层模块）

入口文件：`PaddleOCRProcessor/ocr_module.py`

```python
from PaddleOCRProcessor.ocr_module import run

result = run(
    task_id="E2E-202603021634",  # 可选：只处理指定 task
    item_ids=None,               # 可选：只处理指定 item_id 列表
    device="auto",              # auto/cpu/gpu
    dry_run=False,               # True=只跑识别，不写数据库
    force=False,                 # True=忽略幂等，强制覆盖重跑
    lang="ch",                  # OCR 语言，默认中文
    workers=1,                   # 实验性并行参数，默认 1（不开并行）
    enable_mkldnn=False,         # True=开启 CPU MKLDNN 加速（在部分 Windows 上可能导致内存崩溃，默认 False）
)
```

### 方式 B：命令行调用（适合单模块调试）

```bash
cd PaddleOCRProcessor
python ocr_module.py --task_id E2E-202603021634 --device auto --workers 1
```

常用参数：
- `--task_id`：只处理某一批次
- `--item_ids a,b,c`：只处理指定条目
- `--dry_run`：只跑不写库
- `--force`：覆盖重跑已有 OCR 结果
- `--workers`：实验性并行 worker 数，默认 `1`
- `--enable_mkldnn`：启用 CPU MKLDNN 加速（在部分较新的 Paddle 版本的 Windows 环境下可能导致 C++ `Unimplemented` 崩溃，建议保留默认关闭状态）

---

## 3. 接口定义

### 3.1 `run(...)` 参数契约

```python
run(
    task_id: Optional[str] = None,
    item_ids: Optional[List[str]] = None,
    device: str = "auto",
    dry_run: bool = False,
    force: bool = False,
    lang: str = "ch",
    workers: int = 1,
    enable_mkldnn: bool = False,
) -> Dict
```

参数说明：
- `task_id`：批次过滤键，建议流水线始终传入
- `item_ids`：指定条目重试名单
- `device`：`auto/cpu/gpu`，macOS 下 `auto` 默认走 CPU
- `dry_run`：识别执行但不写回数据库
- `force`：是否忽略 `ocr_text_joined` 非空条件并重跑
- `lang`：传给 PaddleOCR 的语言参数
- `workers`：并行进程数，`<=1` 按串行执行；`>1` 走多进程并行（实验性）
- `enable_mkldnn`：是否启用 MKLDNN C++ 引擎级加速（默认 `False` 安全模式）

### 3.2 返回值契约

常规返回：

```python
{
  "total": 39,
  "processed": 39,
  "updated": 39,
  "skipped": 0,
  "failed": 0,
  "dry_run": False,
  "device": "cpu",
  "workers": 1
}
```

无待处理项时返回：

```python
{
  "total": 0,
  "processed": 0,
  "updated": 0,
  "skipped": 0,
  "failed": 0,
  "dry_run": False
}
```

---

## 4. 平台取图规则

由 `core/path_parser.py` 实现，规则如下：
- `bilibili`：仅读取 `video_screenshots`
- `xhs`：读取 `local_media_paths` + `video_screenshots`

路径支持：
- 逗号分隔多路径
- 绝对路径
- 相对路径（自动按 `MediaCrawler` 根目录补绝对路径）

过滤策略：
- 非图片扩展名直接跳过（`.jpg/.jpeg/.png/.bmp/.webp`）
- 文件不存在跳过
- 重复路径去重

---

## 5. 数据库契约

数据库位置：
`MediaCrawler/data/media_items.db`

### 5.1 读取条件（待 OCR 队列）

基础条件：
- `initial_passed = 1`
- `media_downloaded = 1`
- 平台资源可用：
  - B站：`video_screenshots != ''`
  - 小红书：`local_media_paths != '' OR video_screenshots != ''`

幂等条件：
- 默认：`ocr_text_joined IS NULL OR ocr_text_joined = ''`
- `force=True`：跳过该限制，允许覆盖重跑

附加过滤：
- `task_id = ?`
- `item_id IN (...)`

### 5.2 写回规则

仅更新一个字段：
- `ocr_text_joined`

更新定位键：
- `WHERE platform = ? AND item_id = ? AND task_id = ?`

特殊值：
- 若识别流程正常但无文本，写入 `[OCR_EMPTY]` 防止重复进入待处理队列

---

## 6. 并行策略说明（workers）

- `workers=1`：默认串行模式，稳定性优先
- `workers>1`：多进程并行模式（`ProcessPoolExecutor + spawn`），用于加速批量 OCR
- 当前项目默认策略：生产/常规联调使用 `workers=1`
- `测试模块连贯运行.py` 已显式固定 OCR 步骤为 `--workers 1`

说明：
- 并行模式依赖运行环境对多进程信号量等系统资源权限支持
- 如环境受限，优先回退串行而不是强开并行

---

## 7. 日志规范

日志文件：
`PaddleOCRProcessor/logs/ocr_processor.log`

日志格式：
`[时间] [task_id] [PaddleOCRProcessor] [INFO/WARNING/ERROR] - 消息`

日志策略：
- 按天滚动
- 保留最近 7 天
- 可按 `task_id` 跨模块排障

---

## 8. 关键代码文件

| 文件 | 职责 |
|------|------|
| `PaddleOCRProcessor/ocr_module.py` | 模块入口、串并行编排、统计返回、CLI 参数 |
| `PaddleOCRProcessor/core/ocr_engine.py` | PaddleOCR 封装、设备策略、单图识别调用 |
| `PaddleOCRProcessor/core/path_parser.py` | 平台取图规则、相对路径补全、路径过滤 |
| `PaddleOCRProcessor/store/db_helper.py` | 查询待处理条目、按三元组键写回 OCR |

---

## 9. 与流水线衔接

当前连贯测试脚本步骤：
- `[1/4]` B站爬虫
- `[2/4]` 小红书爬虫
- `[3/4]` 视频截图
- `[4/4]` OCR

OCR 步骤默认传参：
- `--task_id <本轮task_id>`
- `--device auto`
- `--workers 1`
- 不带 `--dry_run`
- 不带 `--force`

---

## 10. 已知边界

- 当前仅回写拼接文本，不保存逐图坐标框和置信度
- OCR 质量受原图清晰度、字幕样式、截图参数影响
- 并行模式已可用但定位为实验能力，默认不作为常规路径
