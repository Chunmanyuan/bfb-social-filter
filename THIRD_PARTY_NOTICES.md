# 第三方项目说明

本文档用于说明本仓库中涉及的主要第三方项目、使用方式和注意事项。

## 1. MediaCrawler

### 基本情况

- 项目名称：MediaCrawler
- 上游地址：<https://github.com/NanmiCoder/MediaCrawler>
- 本仓库中的位置：`MediaCrawler/`
- 使用方式：本仓库直接包含了该项目的部分源码，并在此基础上做了本地修改

### 本项目中的实际情况

- `MediaCrawler/` 不是单纯的外部依赖引用
- 它已经作为本仓库的一部分被放入并参与运行
- 本项目为了适配当前业务流程，对其中部分文件进行了修改

### 许可证情况

- 本地许可证文件：`MediaCrawler/LICENSE`
- 根据该许可证文本，相关代码主要限于非商业学习用途

### 使用提醒

- 如果你只是用于学习、研究、交流，一般应同时保留原许可证和版权说明
- 如果你计划将相关代码用于商业用途、正式产品或对外收费服务，建议先联系原作者确认授权
- 请不要移除 `MediaCrawler/LICENSE`

## 2. PaddleOCR

### 基本情况

- 项目名称：PaddleOCR
- 上游地址：<https://github.com/PaddlePaddle/PaddleOCR>
- 使用方式：本项目通过 Python 依赖方式使用 `paddleocr`
- 本仓库中的相关封装目录：`PaddleOCRProcessor/`

### 本项目中的实际情况

- `PaddleOCRProcessor/` 是本项目自己的调用封装层
- 该目录不是 PaddleOCR 官方完整源码仓库
- 主要功能是组织 OCR 调用流程、日志、数据库写入和路径处理

### 许可证情况

- PaddleOCR 官方许可证为 Apache License 2.0
- 在再次分发或修改相关功能时，建议保留对上游项目的引用说明

## 3. 建议的分享方式

如果你要把本项目上传到 GitHub 或分享给其他人，建议至少同时保留以下内容：

- 本文件 `THIRD_PARTY_NOTICES.md`
- `MediaCrawler/LICENSE`
- `README.md`
- `免责声明.md`

## 4. 当前仓库的使用定位

当前仓库更适合以下用途：

- 学习研究
- 本地测试
- 小范围交流分享

当前仓库不建议在未确认授权前直接用于以下用途：

- 商业项目
- 收费交付
- 面向客户的大规模正式分发
