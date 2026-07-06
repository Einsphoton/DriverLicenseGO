# DriverLicenseGO · 科目一模拟考试

[![Build and Publish Docker Image](https://github.com/Einsphoton/DriverLicenseGO/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/Einsphoton/DriverLicenseGO/actions/workflows/docker-publish.yml)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-blue)](https://github.com/Einsphoton/DriverLicenseGO/pkgs/container/driver-license-go)
[![Platforms](https://img.shields.io/badge/platforms-amd64%20%7C%20arm64-green)](https://github.com/Einsphoton/DriverLicenseGO/pkgs/container/driver-license-go)
[![License](https://img.shields.io/badge/license-MIT-blue)](#license)

基于全国统一驾考题库的 **C1/C2 小型汽车** 科目一模拟考试 Web 应用，支持多架构 Docker 镜像，NAS 一键拉取部署。

## 题库说明

- **适用车型**：C1/C2 小型汽车（已排除大型客车、牵引挂车、城市公交等 A/B 照专属题）
- **来源**：开源项目 [wupeng1221/BrainDrivePass](https://github.com/wupeng1221/BrainDrivePass) 的 SQL 题库（2024-02 更新）
- **题量**：C1/C2 专用 1689 题（判断题 746 + 单选题 943）
- **字段**：题干、选项、正确答案、解析、图片、关键字、难度、错误率
- **说明**：科目一题库全国统一，由公安部交通管理局发布，无地域差异
- **图片题**：782 题带配图（45.4%），含交通标志、手势信号、场景示意等

> 题库为静态数据，应用启动时加载到内存，不依赖数据库。

## 功能

### 两种考试类型

| 类型 | 题量 | 时间 | 每题分值 | 满分 | 及格 | 题库范围 |
|------|------|------|----------|------|------|----------|
| 📝 新考驾照 | 100 题（判断 40 + 单选 60） | 45 分钟 | 1 分 | 100 | 90 | C1/C2 全题库 1689 题 |
| 🔄 恢复驾照 | 50 题（判断 20 + 单选 30） | 30 分钟 | 2 分 | 100 | 90 | C1/C2 法规安全常识 914 题 |

> **恢复驾驶资格考试**：针对驾驶证被注销需恢复驾驶资格的情形。考试以交通法规和安全常识文字题为主，排除标志识别、手势信号等视觉题，题库精简至 914 题。

### 练习模式

| 模式 | 说明 |
|------|------|
| 📖 顺序练习 | 按题库顺序逐题练习，即时显示答案与解析，自动记录进度 |
| ❌ 错题本 | 自动收集做错的题目，支持重做与清空，数据保存在浏览器本地 |
| 🗂️ 分类练习 | 按 24 个高频知识点关键字专项练习 |

其它特性：
- 答题卡快速跳转
- 倒计时自动交卷
- 历史成绩记录（区分考试类型）
- 题目收藏
- 移动端自适应 + 深色模式
- 纯前端状态（localStorage），无需登录

## 🚀 NAS 部署（推荐）

镜像已构建为多架构（`linux/amd64` + `linux/arm64`），群晖、威联通、unraid 等 NAS 可直接拉取。

### 方式一：docker compose（推荐）

把下面的内容存为 `docker-compose.yml`，放到 NAS 任意目录，执行 `docker compose up -d`：

```yaml
services:
  driver-license-go:
    image: ghcr.io/einsphoton/driver-license-go:latest
    container_name: driver-license-go
    ports:
      - "8080:8080"
    restart: unless-stopped
    environment:
      - TZ=Asia/Shanghai
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/stats', timeout=3)"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

访问 `http://<NAS-IP>:8080` 即可使用。

### 方式二：docker run

```bash
docker pull ghcr.io/einsphoton/driver-license-go:latest
docker run -d \
  --name driver-license-go \
  -p 8080:8080 \
  --restart unless-stopped \
  -e TZ=Asia/Shanghai \
  ghcr.io/einsphoton/driver-license-go:latest
```

### 更新到最新版

每次推送到 `main` 分支，GitHub Actions 会自动重新构建并推送 `:latest` 镜像。NAS 上更新：

```bash
docker compose pull && docker compose up -d
# 或
docker pull ghcr.io/einsphoton/driver-license-go:latest
docker rm -f driver-license-go
docker run -d --name driver-license-go ...  # 同上
```

### 关于 GHCR 认证

公开镜像一般无需登录即可拉取。若 NAS 提示需要认证，执行：

```bash
echo <YOUR_GITHUB_PAT> | docker login ghcr.io -u Einsphoton --password-stdin
```

PAT 需要勾选 `read:packages` 权限。生成地址：https://github.com/settings/tokens

## 本地开发

### 方式一：docker compose 本地构建

```bash
git clone https://github.com/Einsphoton/DriverLicenseGO.git
cd DriverLicenseGO
docker compose up -d --build
# 访问 http://localhost:8080
```

> 注意：仓库内的 `docker-compose.yml` 默认从 GHCR 拉取镜像。若要本地构建，把 `image:` 行改成 `build: .` 即可。

### 方式二：直接运行（无 Docker）

```bash
pip install -r requirements.txt
python app.py
# 访问 http://localhost:8080
```

## 目录结构

```
.
├── app.py                       # Flask 后端（题库 API、考试逻辑）
├── requirements.txt             # Python 依赖
├── Dockerfile                   # Docker 构建文件（多架构）
├── docker-compose.yml           # NAS 部署用 compose（拉取 GHCR 镜像）
├── .github/workflows/
│   └── docker-publish.yml       # CI：推送即自动构建多架构镜像到 GHCR
├── data/
│   └── questions.json           # 题库数据（1723 题）
├── static/
│   ├── index.html               # 单页应用入口
│   ├── style.css                # 样式（深色模式自适应）
│   └── app.js                   # 前端应用逻辑
├── scripts/
│   └── convert_sql_to_json.py   # SQL → JSON 转换脚本
└── sql-source/
    └── braindrivepass_practice.sql # 原始 SQL 题库
```

## CI/CD

GitHub Actions workflow（`.github/workflows/docker-publish.yml`）会在以下情况触发：

- 推送到 `main` / `master` 分支
- 打 `v*` tag（如 `v1.0.0`）
- Pull Request（仅构建不推送，用于检查）

构建产物：
- **镜像地址**：`ghcr.io/einsphoton/driver-license-go`
- **多架构**：`linux/amd64` + `linux/arm64`
- **Tag 策略**：
  - `:latest` - 默认分支最新
  - `:v1.0.0` - 语义化版本
  - `:1.0` / `:1` - 主版本
  - `:sha-xxxxxxx` - commit 短哈希
- **缓存**：使用 GitHub Actions cache 加速构建

## API

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/stats` | GET | 题库统计 |
| `/api/questions/all` | GET | 全量题库 |
| `/api/questions/category/<keyword>` | GET | 按关键字分类 |
| `/api/exam/generate` | GET | 生成模拟考试卷 |
| `/api/exam/submit` | POST | 交卷评分 |
| `/api/question/<id>` | GET | 查询单题 |

## 更新题库

题库数据为静态 JSON 文件，如需更新：

1. 替换 `sql-source/braindrivepass_practice.sql`
2. 运行 `python scripts/convert_sql_to_json.py`
3. 提交代码，GitHub Actions 会自动重新构建并推送镜像

## License

MIT License。题库数据遵循原项目 [BrainDrivePass](https://github.com/wupeng1221/BrainDrivePass) 的许可证。
