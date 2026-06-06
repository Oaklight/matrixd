# Installation

## From PyPI

```bash
# Core (listener + CLI, zero dependencies)
pip install matrixd

# With YAML config support
pip install matrixd[yaml]

# With MCP server
pip install matrixd[mcp]

# With REST/OpenAPI server
pip install matrixd[api]

# Everything
pip install matrixd[full]
```

## From Source

```bash
git clone https://github.com/Oaklight/matrixd.git
cd matrixd
pip install -e ".[dev]"
```

🇨🇳 **China mainland** — use jsdelivr for fast access:

```
https://cdn.jsdelivr.net/gh/Oaklight/matrixd@master/README_en.md
```

## Requirements

- **Python 3.10+**
- **No runtime dependencies** — core uses only Python stdlib + vendored [zerodep](https://github.com/Oaklight/zerodep) modules

## Extras

| Extra | Dependencies | Provides |
|-------|-------------|----------|
| `yaml` | pyyaml | YAML config file support |
| `mcp` | mcp SDK | MCP tool server |
| `api` | fastapi, uvicorn | REST/OpenAPI server |
| `full` | all of the above | Everything |
| `dev` | full + pytest, ruff, ty, etc. | Development tools |
