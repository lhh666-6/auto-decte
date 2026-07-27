# 竹条生产管理系统 — 本地部署指南

## 环境要求

| 软件 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.11+ | 后端运行环境 |
| Node.js | 18+ | 前端构建与开发服务器 |
| Git | 任意版本 | 拉取代码 |

> 本文档基于 Windows 11 编写。Linux/macOS 仅路径格式不同，其余步骤一致。

---

## 一、拉取代码

```bash
git clone https://github.com/lhh666-6/auto-decte.git
cd auto-decte
git checkout modular-architecture
```

---

## 二、后端部署

### 2.1 创建虚拟环境

```bash
python -m venv .venv
```

### 2.2 激活虚拟环境

**Windows:**
```bash
.venv\Scripts\activate
```

**Linux/macOS:**
```bash
source .venv/bin/activate
```

### 2.3 安装依赖

```bash
pip install -r requirements.txt
```

如果 `requirements.txt` 不存在或缺少依赖，手动安装核心包：

```bash
pip install fastapi uvicorn sqlalchemy alembic pydantic pydantic-settings openpyxl
```

### 2.4 配置环境变量

项目根目录已有 `.env.example`，复制并编辑：

```bash
cp .env.example .env
```

`.env` 内容（按需修改）：

```env
FORM_DEMO_DATA_ROOT=./data
FORM_DEMO_API_HOST=0.0.0.0
FORM_DEMO_AI_ENABLED=false
APP_AUTH_MODE=local_full_access
```

- `FORM_DEMO_API_HOST=0.0.0.0` 表示监听所有网卡，允许局域网访问
- 数据库文件自动创建在 `./data/database/demo.db`

### 2.5 初始化数据库

```bash
# 项目根目录下执行
python -m alembic upgrade head
```

该命令会自动创建 SQLite 数据库文件并执行所有迁移。

### 2.6 启动后端

```bash
python -m uvicorn app.api.main:create_app --factory --host 0.0.0.0 --port 8000
```

验证：

```bash
curl http://127.0.0.1:8000/health/live
# 返回 {"status":"live"} 即成功
```

内网访问：`http://<本机IP>:8000`

---

## 三、前端部署

### 3.1 安装依赖

```bash
cd frontend
npm install
```

### 3.2 开发模式启动

```bash
npm run dev:web
```

默认监听 `0.0.0.0:5173`，局域网可访问。

### 3.3 验证

浏览器打开 `http://localhost:5173`，应看到登录页面。

---

## 四、初始管理员账户

系统首次启动后会自动创建默认账户和业务数据：

| 工号 | 姓名 | 角色 | PIN |
|------|------|------|-----|
| ADMIN001 | 管理员 | 系统管理员 | 1234 |
| GLY001 | 系统管理员 | 系统管理员 | 2468 |

### 4.1 如何创建其他角色账户

1. 浏览器打开 `http://localhost:5173`
2. 用 **ADMIN001 / 1234** 登录
3. 左侧导航 → **工厂与岗位** → 新建工厂（勾选启用 SORTING、DIPPING_DRYING 业务表单）
4. 左侧导航 → **组织与员工** → 点 **+ 新增员工**
5. 选择工厂 → 选择岗位 → 填写姓名 → 设置密码 → 工号自动生成 → 确认创建

### 4.2 工厂预设数据

系统内置两种业务表单：

| 表单 | 名称 | 工序 |
|------|------|------|
| SORTING | 《竹丝装笼跟踪牌》 | 分选 → 主管审核 → 厂长确认 |
| DIPPING_DRYING | 《竹丝浸胶干燥生产记录表》 | 浸胶 → 干燥 → 主管审核 → 厂长确认 |

**分选预设参数**：

| 长度 | 每把重量 |
|------|---------|
| 1.93m | 5 kg |
| 2.1m | 5 kg |
| 2.35m | 6 kg |

---

## 五、生产环境部署（可选）

### 5.1 后端生产运行

```bash
python -m uvicorn app.api.main:create_app --factory --host 0.0.0.0 --port 8000 --workers 4
```

### 5.2 前端生产构建

```bash
cd frontend
npm run build:web
```

构建产物在 `frontend/apps/web/dist/`，部署到 Nginx 或任意静态文件服务器。

Nginx 配置示例：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    root /path/to/frontend/apps/web/dist;
    index index.html;
    try_files $uri /index.html;

    # API 代理到后端
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }
}
```

---

## 六、局域网访问

部署在同一台机器上后，局域网内其他设备通过以下地址访问：

- 前端：`http://<本机IP>:5173`
- 后端 API：`http://<本机IP>:8000`
- API 文档：`http://<本机IP>:8000/docs`

> 查看本机 IP：Windows 执行 `ipconfig`，Linux/macOS 执行 `ifconfig`。

---

## 七、常见问题

### Q: 启动报 "Path doesn't exist: alembic"

在项目根目录执行命令，不要在其他目录启动。

### Q: 数据库损坏

删除 `./data/database/demo.db`，重新执行 `python -m alembic upgrade head`。

### Q: 前端端口被占用

Vite 会自动尝试下一个端口（5174、5175…），按控制台输出的地址访问即可。

### Q: crypto.randomUUID 报错

已修复，当前版本使用降级方案兼容非 HTTPS 环境。

### Q: 如何重置所有数据

删除 `data/` 目录，重新运行初始化命令即可。

---

## 八、技术栈

| 层 | 技术 |
|----|------|
| 后端框架 | FastAPI (Python) |
| 数据库 | SQLite |
| 迁移 | Alembic |
| 前端框架 | React + TypeScript |
| 构建工具 | Vite |
| 测试 | Vitest (前端) / pytest (后端) |
