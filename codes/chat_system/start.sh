#!/bin/bash

# 聊天系统启动脚本
# 适用于单机和集群环境
# 加载.env文件中的环境变量
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
    info "已加载.env文件中的环境变量"
fi
# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # 恢复默认颜色

# 输出函数
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 进程ID文件
PID_FILE="/tmp/chat_system_pids.txt"
# 创建PID文件目录
PID_DIR=$(dirname "$PID_FILE")
if [ ! -d "$PID_DIR" ]; then
    mkdir -p "$PID_DIR"
fi

# 清空PID文件
cat /dev/null > "$PID_FILE"

# 设置更详细的调试模式
if [ "$DEBUG" = "true" ]; then
    set -x
    # 使用更详细的日志级别
    export LOG_LEVEL="DEBUG"
    info "启用详细调试模式"
fi

# 确保进程监控器可执行
chmod +x shutdown_monitor.py

# 信号处理函数
cleanup() {
    info "接收到终止信号，正在关闭所有服务..."
    
    # 标记自己正在处理信号，避免递归
    local HANDLING_SIGNAL=true
    
    # 不通过监控器清理，而是直接终止主应用进程
    if [ -n "$APP_PID" ] && ps -p "$APP_PID" > /dev/null; then
        info "终止主应用进程 $APP_PID"
        kill -15 "$APP_PID" 2>/dev/null || true
        
        # 等待3秒，如果还没终止就强制终止
        sleep 3
        if ps -p "$APP_PID" > /dev/null; then
            warn "应用进程未响应，强制终止"
            kill -9 "$APP_PID" 2>/dev/null || true
        fi
    fi
    
    # 最后再使用监控器清理剩余进程
    info "使用进程监控器清理残留进程..."
    python3 -c "
import sys
import os
import time
import signal

# 直接调用系统命令，避免加载整个模块
os.system('python3 shutdown_monitor.py')

# 延迟退出，给清理进程一些时间
time.sleep(1)
sys.exit(0)
" &
    
    info "清理完成，退出脚本"
    exit 0
}

# 注册信号处理
trap cleanup SIGINT SIGTERM SIGHUP

# 启动参数
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8000}
WORKERS=${WORKERS:-2}
MAX_CONNECTIONS=${MAX_CONNECTIONS:-10000}

# 判断操作系统类型
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS_TYPE="MacOS"
    info "检测到MacOS系统环境"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS_TYPE="Linux"
    info "检测到Linux系统环境"
else
    OS_TYPE="Other"
    info "未知操作系统类型: $OSTYPE"
fi

# 检查Python版本并特别处理Python 3.12+版本
if [ "$(python3 -c 'import sys; print(sys.version_info >= (3, 12))')" = "True" ]; then
    echo "[WARN] 检测到Python 3.12或更高版本，某些模块需要特定版本"
    echo "[WARN] 将安装Python 3.12兼容的依赖版本"
    echo "[INFO] 安装兼容Python 3.12的依赖集"
    
    # 创建临时requirements文件
    cat > /tmp/requirements_py312.txt << EOF
# Python 3.12兼容版本集
fastapi==0.103.1
uvicorn==0.23.2
pydantic>=2.4.0  # 支持Python 3.12的Pydantic 2.x版本
starlette==0.27.0
websockets==11.0.3
jinja2==3.1.2
python-dotenv==1.0.0
redis==3.5.3  # 固定版本以兼容redis-py-cluster
redis-py-cluster==2.1.3  # 集群支持(如果可用)
httpx==0.24.1
ujson==5.8.0
psutil==5.9.5
gunicorn==21.2.0
EOF
else
    # 检查依赖
    info "检查依赖..."
    python3 -m pip install -r requirements.txt || {
        error "安装依赖失败，尝试使用最小安装模式"
        
        TMP_REQUIREMENTS="/tmp/requirements_minimal.txt"
        cat > $TMP_REQUIREMENTS << EOF
# 最小依赖集
fastapi==0.95.2
uvicorn==0.22.0
redis==3.5.3  # 降级到与redis-py-cluster兼容的版本
jinja2==3.1.2
python-dotenv==1.0.0
pydantic==1.10.8
EOF
        
        python3 -m pip install -r $TMP_REQUIREMENTS || {
            error "最小依赖安装失败，无法继续"
            exit 1
        }
        warn "已安装最小依赖集，部分功能可能不可用"
    }
fi

# 必须安装psutil用于进程管理
python3 -m pip install psutil || {
    error "安装psutil失败，无法继续"
    exit 1
}

# 设置环境变量
export MAX_CONNECTIONS=$MAX_CONNECTIONS

# 如果是Python 3.12，则显式禁用uvloop和其他不兼容模块
if [ "$(python3 -c 'import sys; print(sys.version_info >= (3, 12))')" = "True" ]; then
    export DISABLE_UVLOOP=1
    export MINIMAL_DEPS=1
fi

# 判断是否使用单机模式
if [ -z "$REDIS_URL" ]; then
    warn "未设置 REDIS_URL 环境变量，将使用单机模式"
    MODE="single"
else
    # 解析Redis URL (支持密码格式：redis://[:password@]host[:port])
    if [[ $REDIS_URL =~ redis://([^:@]+@)?([^:@]+)(:([0-9]+))? ]]; then
        # 提取密码（如果有）
        if [[ $REDIS_URL =~ redis://([^:@]+):([^@]+)@([^:]+)(:([0-9]+))? ]]; then
            REDIS_USER=${BASH_REMATCH[1]}
            REDIS_PASSWORD=${BASH_REMATCH[2]}
            REDIS_HOST=${BASH_REMATCH[3]}
            REDIS_PORT=${BASH_REMATCH[5]:-6379}
            info "检测到Redis用户名和密码"
        elif [[ $REDIS_URL =~ redis://([^@]+)@([^:]+)(:([0-9]+))? ]]; then
            REDIS_PASSWORD=${BASH_REMATCH[1]}
            REDIS_HOST=${BASH_REMATCH[2]}
            REDIS_PORT=${BASH_REMATCH[4]:-6379}
            info "检测到Redis密码"
        else
            REDIS_HOST=${BASH_REMATCH[2]}
            REDIS_PORT=${BASH_REMATCH[4]:-6379}
        fi
        
        # 检查Redis连接
        info "检查 Redis 连接: $REDIS_HOST:$REDIS_PORT"
        
        # 组装Redis连接参数
        REDIS_PARAMS="host='$REDIS_HOST', port=$REDIS_PORT, socket_connect_timeout=2"
        if [ ! -z "$REDIS_PASSWORD" ]; then
            REDIS_PARAMS="$REDIS_PARAMS, password='$REDIS_PASSWORD'"
        fi
        if [ ! -z "$REDIS_USER" ]; then
            REDIS_PARAMS="$REDIS_PARAMS, username='$REDIS_USER'"
        fi
        
        # 使用Python检查Redis连接
        REDIS_CHECK=$(python3 -c "
import sys
try:
    import redis
    r = redis.Redis($REDIS_PARAMS)
    r.ping()
    print('ok')
except Exception as e:
    print(f'error: {e}')
    sys.exit(1)
" 2>&1)
        
        if [[ $REDIS_CHECK == "ok" ]]; then
            info "Redis连接成功: $REDIS_URL"
            MODE="distributed"
        else
            warn "Redis连接失败: $REDIS_CHECK"
            warn "将使用单机模式运行，Redis功能不可用"
            MODE="single"
        fi
    else
        warn "无效的 REDIS_URL 格式: $REDIS_URL"
        warn "将使用单机模式运行"
        MODE="single"
    fi
fi

# 启动过程监控
if [ "$MONITOR_ENABLED" = "true" ]; then
    info "启动进程监控..."
    python3 shutdown_monitor.py "$PPID" "$PID_FILE" &
    MONITOR_PID=$!
    echo $MONITOR_PID >> "$PID_FILE"
    info "进程监控已启动 (PID: $MONITOR_PID)"
fi

# 启动聊天系统
info "启动聊天系统..."
info "模式: $MODE"
info "主机: $HOST 端口: $PORT"

if [ "$MODE" == "single" ]; then
    info "单机模式，不使用 Redis"
    
    # 在MacOS上使用Uvicorn，因为gunicorn在MacOS上可能有问题
    if [ "$OS_TYPE" == "MacOS" ]; then
        info "在MacOS上使用Uvicorn启动单进程模式..."
        info "使用日志级别: info"
        
        # 启动服务，添加-v参数增加详细度
        python3 -m uvicorn main:app --host $HOST --port $PORT --log-level info --reload &
        APP_PID=$!
        echo $APP_PID >> "$PID_FILE"
        info "服务已启动 (PID: $APP_PID)"
        
        # 等待服务退出
        wait $APP_PID || true
    else
        # Linux环境使用多进程
        info "在Linux上使用Gunicorn多进程模式..."
        info "工作进程: $WORKERS"
        
        # 启动服务
        gunicorn main:app --bind $HOST:$PORT --workers $WORKERS \
            --worker-class uvicorn.workers.UvicornWorker \
            --timeout 120 \
            --graceful-timeout 30 \
            --keep-alive 5 &
        APP_PID=$!
        echo $APP_PID >> "$PID_FILE"
        info "服务已启动 (PID: $APP_PID)"
        
        # 等待服务退出
        wait $APP_PID || true
    fi
else
    # 分布式模式
    info "分布式模式，使用Redis: $REDIS_URL"
    
    if [ "$OS_TYPE" == "MacOS" ]; then
        info "在MacOS上使用Uvicorn启动单进程模式..."
        
        # 启动服务
        python3 -m uvicorn main:app --host $HOST --port $PORT --log-level info --reload &
        APP_PID=$!
        echo $APP_PID >> "$PID_FILE"
        info "服务已启动 (PID: $APP_PID)"
        
        # 等待服务退出
        wait $APP_PID || true
    else
        # Linux环境使用多进程
        info "在Linux上使用Gunicorn多进程集群模式..."
        info "工作进程: $WORKERS"
        
        # 启动服务
        gunicorn main:app --bind $HOST:$PORT --workers $WORKERS \
            --worker-class uvicorn.workers.UvicornWorker \
            --timeout 120 \
            --graceful-timeout 30 \
            --keep-alive 5 &
        APP_PID=$!
        echo $APP_PID >> "$PID_FILE"
        info "服务已启动 (PID: $APP_PID)"
        
        # 等待服务退出
        wait $APP_PID || true
    fi
fi

# 如果到达这里，说明服务已停止
info "服务已停止"

# 确保清理所有进程
cleanup 