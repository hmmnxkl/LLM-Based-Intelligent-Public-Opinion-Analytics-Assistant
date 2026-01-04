# 使用 Ubuntu 基础镜像，优先使用官方源
FROM ubuntu:22.04

WORKDIR /app

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 先尝试使用官方源，失败时使用备用镜像源
RUN echo "=== 配置 Ubuntu 软件源 ===" && \
    # 备份原始源列表
    cp /etc/apt/sources.list /etc/apt/sources.list.bak && \
    # 尝试使用官方源更新，如果失败则使用镜像源
    apt-get update || ( \
        echo "官方源更新失败，尝试使用镜像源..." && \
        sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list && \
        sed -i 's/security.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list && \
        apt-get update \
    ) || ( \
        echo "阿里云镜像失败，尝试华为云镜像..." && \
        sed -i 's/mirrors.aliyun.com/mirrors.huaweicloud.com/g' /etc/apt/sources.list && \
        apt-get update \
    ) || ( \
        echo "华为云镜像失败，尝试清华镜像..." && \
        sed -i 's/mirrors.huaweicloud.com/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list && \
        apt-get update \
    ) || ( \
        echo "所有镜像源尝试失败，恢复官方源并继续..." && \
        cp /etc/apt/sources.list.bak /etc/apt/sources.list && \
        apt-get update \
    )

# 安装系统依赖（包含运行Chromium所需的库）
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 python3-pip wget curl unzip xz-utils xvfb dos2unix jq \
    libnss3 libxss1 libasound2 libatk-bridge2.0-0 libgtk-3-0 libdbus-1-3 \
    libgbm-dev libxshmfence1 libdrm2 libx11-6 libxcb1 libxcomposite1 \
    libxdamage1 libxext6 libxfixes3 libxrandr2 fonts-liberation \
    netcat-openbsd ca-certificates software-properties-common \
    chromium-browser chromium-chromedriver \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/* && \
    ln -sf /usr/bin/python3 /usr/bin/python

# 配置 pip，优先使用官方源，失败时使用镜像
RUN echo "=== 配置 pip ===" && \
    # 先尝试直接使用 pip（官方源）
    pip3 install --no-cache-dir --upgrade pip setuptools wheel || ( \
        echo "pip官方源失败，配置使用阿里云镜像..." && \
        mkdir -p /root/.pip && \
        echo "[global]" > /root/.pip/pip.conf && \
        echo "index-url = https://mirrors.aliyun.com/pypi/simple/" >> /root/.pip/pip.conf && \
        echo "trusted-host = mirrors.aliyun.com" >> /root/.pip/pip.conf && \
        echo "timeout = 120" >> /root/.pip/pip.conf && \
        pip3 install --no-cache-dir --upgrade pip setuptools wheel \
    ) || ( \
        echo "阿里云镜像失败，尝试华为云镜像..." && \
        sed -i 's/mirrors.aliyun.com/repo.huaweicloud.com/g' /root/.pip/pip.conf && \
        sed -i 's/mirrors.aliyun.com/repo.huaweicloud.com/g' /root/.pip/pip.conf && \
        pip3 install --no-cache-dir --upgrade pip setuptools wheel \
    ) || ( \
        echo "所有镜像失败，移除pip配置，使用官方源重试..." && \
        rm -f /root/.pip/pip.conf && \
        pip3 install --no-cache-dir --upgrade pip setuptools wheel \
    )

# 安装最新版 Chrome/Chromium 和 ChromeDriver（多源尝试）
RUN echo "=== 尝试从多个源安装 Chrome/Chromium 和 ChromeDriver ===" && \
    # 方法1: 尝试安装 Google Chrome（官方源）
    if ! command -v google-chrome-stable &> /dev/null; then \
        echo "尝试从官方源安装 Google Chrome..." && \
        wget -q --timeout=30 --tries=2 -O /tmp/google-chrome-stable_current_amd64.deb \
        https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb || \
        (echo "官方源下载失败，尝试镜像源..." && \
        wget -q --timeout=30 -O /tmp/google-chrome-stable_current_amd64.deb \
        https://mirrors.huaweicloud.com/google-chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_current_amd64.deb) || \
        (echo "华为云镜像失败，尝试阿里云镜像..." && \
        wget -q --timeout=30 -O /tmp/google-chrome-stable_current_amd64.deb \
        https://mirrors.aliyun.com/google-chrome/deb/pool/main/g/google-chrome-stable/google-chrome-stable_current_amd64.deb); \
        if [ -f /tmp/google-chrome-stable_current_amd64.deb ]; then \
            apt-get update && \
            apt-get install -y /tmp/google-chrome-stable_current_amd64.deb --no-install-recommends && \
            rm /tmp/google-chrome-stable_current_amd64.deb && \
            echo "Google Chrome 安装成功"; \
        else \
            echo "Google Chrome 下载失败，继续尝试其他方法"; \
        fi; \
    fi && \
    # 方法2: 确保 Chromium 已安装
    if ! command -v chromium-browser &> /dev/null && ! command -v google-chrome-stable &> /dev/null; then \
        echo "安装 Chromium..." && \
        apt-get update && \
        apt-get install -y chromium-browser --no-install-recommends && \
        echo "Chromium 安装成功"; \
    fi && \
    # 确定浏览器二进制路径
    if command -v google-chrome-stable &> /dev/null; then \
        echo "使用 Google Chrome 作为浏览器" && \
        ln -sf /usr/bin/google-chrome-stable /usr/bin/chromium; \
    elif command -v chromium-browser &> /dev/null; then \
        echo "使用 Chromium 作为浏览器" && \
        ln -sf /usr/bin/chromium-browser /usr/bin/chromium; \
    else \
        echo "未找到浏览器，将安装 Chromium" && \
        apt-get update && \
        apt-get install -y chromium-browser --no-install-recommends && \
        ln -sf /usr/bin/chromium-browser /usr/bin/chromium; \
    fi && \
    # 安装/更新 ChromeDriver（多源尝试）
    echo "安装 ChromeDriver..." && \
    if command -v google-chrome-stable &> /dev/null; then \
        CHROME_VERSION=$(google-chrome-stable --version | grep -oP '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | head -1); \
        echo "Google Chrome 版本: $CHROME_VERSION"; \
    elif command -v chromium-browser &> /dev/null; then \
        CHROME_VERSION=$(chromium-browser --version | grep -oP '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | head -1); \
        echo "Chromium 版本: $CHROME_VERSION"; \
    else \
        CHROME_VERSION="114.0.5735.90"; \
        echo "未检测到浏览器版本，使用默认版本: $CHROME_VERSION"; \
    fi && \
    # 提取主版本号
    CHROME_MAJOR_VERSION=$(echo $CHROME_VERSION | cut -d'.' -f1) && \
    echo "Chrome 主版本: $CHROME_MAJOR_VERSION" && \
    # 方法1: 尝试从官方源下载对应版本的 ChromeDriver
    echo "尝试从官方源下载 ChromeDriver v$CHROME_MAJOR_VERSION..." && \
    wget -q --timeout=30 --tries=2 -O /tmp/chromedriver.zip \
    https://storage.googleapis.com/chrome-for-testing-public/$CHROME_MAJOR_VERSION.0.0/linux64/chromedriver-linux64.zip || \
    (echo "官方源下载失败，尝试华为云镜像..." && \
    wget -q --timeout=30 -O /tmp/chromedriver.zip \
    https://mirrors.huaweicloud.com/chromedriver/$CHROME_MAJOR_VERSION.0.0/chromedriver_linux64.zip) || \
    (echo "华为云镜像失败，尝试阿里云镜像..." && \
    wget -q --timeout=30 -O /tmp/chromedriver.zip \
    https://mirrors.aliyun.com/chromedriver/$CHROME_MAJOR_VERSION.0.0/chromedriver_linux64.zip) || \
    (echo "阿里云镜像失败，尝试淘宝镜像..." && \
    wget -q --timeout=30 -O /tmp/chromedriver.zip \
    https://npm.taobao.org/mirrors/chromedriver/$CHROME_MAJOR_VERSION.0.0/chromedriver_linux64.zip) || \
    # 方法5: 尝试下载最新版本
    (echo "特定版本失败，尝试下载最新版本..." && \
    LATEST_VERSION=$(curl -sS --max-time 30 https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_MAJOR_VERSION 2>/dev/null || echo "") && \
    if [ -n "$LATEST_VERSION" ]; then \
        wget -q --timeout=30 -O /tmp/chromedriver.zip \
        https://chromedriver.storage.googleapis.com/$LATEST_VERSION/chromedriver_linux64.zip || \
        wget -q --timeout=30 -O /tmp/chromedriver.zip \
        https://mirrors.aliyun.com/chromedriver/$LATEST_VERSION/chromedriver_linux64.zip; \
    fi) && \
    # 如果所有方法都失败，使用备用的较新版本
    if [ ! -f /tmp/chromedriver.zip ]; then \
        echo "所有下载方法失败，使用备用版本 (115.0.5790.102)..." && \
        wget -q --timeout=30 -O /tmp/chromedriver.zip \
        https://chromedriver.storage.googleapis.com/115.0.5790.102/chromedriver_linux64.zip || \
        wget -q --timeout=30 -O /tmp/chromedriver.zip \
        https://mirrors.aliyun.com/chromedriver/115.0.5790.102/chromedriver_linux64.zip; \
    fi && \
    # 解压并安装 ChromeDriver
    if [ -f /tmp/chromedriver.zip ]; then \
        echo "解压 ChromeDriver..." && \
        unzip -o /tmp/chromedriver.zip -d /tmp/ && \
        # 查找 chromedriver 文件（新版本可能在子目录中）
        if [ -f /tmp/chromedriver-linux64/chromedriver ]; then \
            mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver; \
        elif [ -f /tmp/chromedriver ]; then \
            mv /tmp/chromedriver /usr/local/bin/chromedriver; \
        else \
            find /tmp -name "chromedriver" -type f -exec mv {} /usr/local/bin/chromedriver \; 2>/dev/null || true; \
        fi && \
        chmod +x /usr/local/bin/chromedriver && \
        rm -rf /tmp/chromedriver* && \
        echo "ChromeDriver 安装成功"; \
    else \
        echo "警告: 无法下载 ChromeDriver，将尝试使用系统自带的 chromedriver"; \
        if command -v chromedriver &> /dev/null; then \
            echo "使用系统自带的 chromedriver"; \
        else \
            echo "尝试安装 chromium-chromedriver 包"; \
            apt-get update && \
            apt-get install -y chromium-chromedriver --no-install-recommends && \
            ln -sf /usr/lib/chromium-browser/chromedriver /usr/local/bin/chromedriver; \
        fi; \
    fi && \
    # 验证安装
    echo "=== 验证安装 ===" && \
    if command -v chromium &> /dev/null; then \
        echo "浏览器路径: $(which chromium)"; \
        chromium --version || true; \
    fi && \
    if command -v chromedriver &> /dev/null; then \
        echo "ChromeDriver 路径: $(which chromedriver)"; \
        chromedriver --version || true; \
    fi && \
    echo "=== 安装完成 ==="

# 复制项目文件
COPY . .

# 确保脚本文件使用 Unix 换行符
RUN find . -name "*.sh" -type f -exec dos2unix {} \; && \
    find . -name "*.py" -type f -exec dos2unix {} \;

# 安装Python依赖（先尝试官方源，失败则使用镜像）
RUN echo "=== 安装 Python 依赖 ===" && \
    # 先尝试使用官方源安装
    pip install --no-cache-dir --ignore-installed -r requirements.txt || ( \
        echo "pip官方源安装失败，配置使用镜像源..." && \
        if [ ! -f /root/.pip/pip.conf ]; then \
            mkdir -p /root/.pip && \
            echo "[global]" > /root/.pip/pip.conf && \
            echo "index-url = https://mirrors.aliyun.com/pypi/simple/" >> /root/.pip/pip.conf && \
            echo "trusted-host = mirrors.aliyun.com" >> /root/.pip/pip.conf && \
            echo "timeout = 120" >> /root/.pip/pip.conf; \
        fi && \
        pip install --no-cache-dir --ignore-installed -r requirements.txt \
    ) || ( \
        echo "所有安装方法失败，清理缓存后重试..." && \
        pip cache purge && \
        pip install --no-cache-dir --ignore-installed -r requirements.txt \
    )

# 创建必要的目录并设置权限
RUN mkdir -p logs vector_db data temp reports && \
    chmod 777 logs vector_db data temp reports

# 确保所有文件可读
RUN chmod -R a+r /app

# 设置 Python 文件可执行
RUN find /app -name "*.py" -exec chmod +x {} \;

# 暴露端口
EXPOSE 5000

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
# 以下环境变量对于无头浏览器在Docker中运行至关重要
ENV DISPLAY=:99
# 设置浏览器驱动路径
ENV BROWSER_BIN=/usr/bin/chromium
ENV BROWSER_DRIVER=/usr/local/bin/chromedriver
ENV CHROMIUM_FLAGS="--no-sandbox --disable-dev-shm-usage --headless --disable-gpu --remote-debugging-port=9222 --disable-setuid-sandbox --disable-blink-features=AutomationControlled"

# 设置执行权限并指定启动命令
RUN chmod +x docker-entrypoint.sh
CMD ["sh", "docker-entrypoint.sh"]