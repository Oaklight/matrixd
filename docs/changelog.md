# 更新日志

本项目的所有重要变更记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.1.0] - 2026-06-06

### 新增

- Matrix Client-Server API 封装（`MatrixClient`）
- `/sync` 监听器，支持自动重连和指数退避
- 策略引擎，4 个级别：lurk（静默）、mention-only（仅提及）、important（重要）、all（全部）
- 反回声过滤（忽略 bot 自身消息）
- 可插拔分发后端：stdout、webhook、exec
- CLI：`matrixd whoami`、`send`、`rooms`、`listen`、`serve`、`version`
- JSONC 配置，支持环境变量插值
- 内嵌 zerodep 模块：`httpclient`（HTTP 客户端）、`jsonc`（配置解析器）
- 零运行时依赖 — 纯标准库 + 内嵌模块
- Pre-commit CI：ruff、ty、complexipy（排除 `_vendor/`）
- GitHub Actions CI，Python 3.10–3.13 测试矩阵

[0.1.0]: https://github.com/Oaklight/matrixd/releases/tag/v0.1.0
