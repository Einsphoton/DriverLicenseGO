FROM python:3.12-slim

LABEL maintainer="subject1-docker-app"
LABEL description="中国驾考科目一模拟考试 Docker 应用"

WORKDIR /app

# 安装依赖（利用缓存层）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码与题库数据
COPY app.py .
COPY static/ ./static/
COPY data/ ./data/

# 暴露端口
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/stats', timeout=3)" || exit 1

# 使用 gunicorn 生产级运行
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
