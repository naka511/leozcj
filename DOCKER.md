# Docker 部署

## 反风控原理

Docker 内不使用 headless 模式。改用 **Xvfb 虚拟显示器** 运行有头 Chrome：

- Cloudflare Turnstile 检测到的是"正常桌面浏览器"，不是 headless
- 安装的是完整 Google Chrome（非 Chromium），指纹更接近真实用户
- 额外注入反自动化检测参数（禁用 `AutomationControlled`、伪装 User-Agent 等）

## 启动

```bash
docker compose up -d --build
```

首次构建会下载 Google Chrome + 依赖，约 3-5 分钟。

访问：

```text
http://服务器IP:8000
```

本机访问：

```text
http://127.0.0.1:8000
```

## 查看日志

```bash
docker compose logs -f
```

## 停止

```bash
docker compose down
```

## 持久化文件

`docker-compose.yml` 会把本地 `./data` 目录挂载到容器的 `/app/data`。

容器内会持久化这些文件：

- `/app/data/config.json`：系统设置
- `/app/data/tasks.json`：任务记录
- `/app/data/cookies/`：注册成功的 Cookie
- `/app/data/screenshots/`：调试截图

如果在面板里部署，只挂载一条硬盘：

```text
硬盘 ID: leo-data
挂载目录: /app/data
```

并添加环境变量：

```text
DATA_DIR=/app/data
DISPLAY=:99
```

## 代理说明

代理检测和注册流量都从容器发起。部署到服务器后，如果代理商开启 IP 白名单，需要把服务器公网 IP 加到代理白名单。

## 架构说明

```
┌─────────────────────────────────────────────┐
│  Docker Container                           │
│                                             │
│  entrypoint.sh                              │
│    └─ Xvfb :99 (虚拟显示器)                 │
│        └─ server.py (FastAPI)               │
│            └─ auto_register_leo.py          │
│                └─ Google Chrome (有头模式)   │
│                    └─ Canva → Leonardo.ai   │
│                                             │
│  关键：Chrome "以为"自己在桌面环境运行       │
│  Cloudflare 看到的是正常浏览器，不是 bot    │
└─────────────────────────────────────────────┘
```
