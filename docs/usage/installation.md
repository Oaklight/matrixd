# 安装

## 从 PyPI 安装

```bash
# 核心（监听器 + CLI，零依赖）
pip install matrixd

# 支持 YAML 配置
pip install matrixd[yaml]

# 支持 MCP 服务器
pip install matrixd[mcp]

# 支持 REST/OpenAPI 服务器
pip install matrixd[api]

# 全部功能
pip install matrixd[full]
```

## 从源码安装

```bash
git clone https://github.com/Oaklight/matrixd.git
cd matrixd
pip install -e ".[dev]"
```

🇨🇳 **中国大陆用户** — 使用 jsdelivr 加速访问：

```
https://cdn.jsdelivr.net/gh/Oaklight/matrixd@master/README_zh.md
```

## 系统要求

- **Python 3.10+**
- **无运行时依赖** — 核心仅使用 Python 标准库 + 内嵌的 [zerodep](https://github.com/Oaklight/zerodep) 模块

## 可选模块

| 模块 | 依赖 | 功能 |
|------|------|------|
| `yaml` | pyyaml | YAML 配置文件支持 |
| `mcp` | mcp SDK | MCP 工具服务器 |
| `api` | fastapi, uvicorn | REST/OpenAPI 服务器 |
| `full` | 以上全部 | 完整功能 |
| `dev` | full + pytest, ruff, ty 等 | 开发工具 |
