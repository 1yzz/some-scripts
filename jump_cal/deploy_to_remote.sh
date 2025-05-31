#!/bin/bash
# 部署到远程主机脚本

set -e

# 配置参数
REMOTE_HOST="192.168.5.122"
REMOTE_USER="root"  # 根据需要修改用户名
REMOTE_PATH="/opt/translation_service"
LOCAL_DIST_DIR="dist"
PACKAGE_NAME="translation_service_$(date +%Y%m%d_%H%M%S)"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===== Translation Service 远程部署脚本 =====${NC}"
echo -e "${YELLOW}目标主机: ${REMOTE_HOST}${NC}"
echo -e "${YELLOW}远程路径: ${REMOTE_PATH}${NC}"
echo ""

# 检查参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--host)
            REMOTE_HOST="$2"
            shift 2
            ;;
        -u|--user)
            REMOTE_USER="$2"
            shift 2
            ;;
        -p|--path)
            REMOTE_PATH="$2"
            shift 2
            ;;
        --help)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  -h, --host HOST    远程主机 (默认: 192.168.5.122)"
            echo "  -u, --user USER    远程用户 (默认: root)"
            echo "  -p, --path PATH    远程路径 (默认: /opt/translation_service)"
            echo "  --help             显示帮助信息"
            echo ""
            echo "示例:"
            echo "  $0"
            echo "  $0 -h 192.168.1.100 -u ubuntu -p /home/ubuntu/translation_service"
            exit 0
            ;;
        *)
            echo -e "${RED}未知选项: $1${NC}"
            exit 1
            ;;
    esac
done

# 检查本地文件
if [ ! -d "$LOCAL_DIST_DIR" ]; then
    echo -e "${RED}错误: $LOCAL_DIST_DIR 目录不存在!${NC}"
    echo "请先运行构建脚本: python build_executable.py"
    exit 1
fi

if [ ! -f "$LOCAL_DIST_DIR/translation_service" ]; then
    echo -e "${RED}错误: 可执行文件 $LOCAL_DIST_DIR/translation_service 不存在!${NC}"
    echo "请先运行构建脚本: python build_executable.py"
    exit 1
fi

# 测试SSH连接
echo -e "${BLUE}测试SSH连接...${NC}"
if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "${REMOTE_USER}@${REMOTE_HOST}" "echo 'SSH连接成功'" 2>/dev/null; then
    echo -e "${RED}SSH连接失败!${NC}"
    echo "请确保:"
    echo "1. 远程主机 ${REMOTE_HOST} 可达"
    echo "2. SSH密钥已配置或准备输入密码"
    echo "3. 用户 ${REMOTE_USER} 有访问权限"
    exit 1
fi

# 创建临时压缩包
echo -e "${BLUE}创建压缩包...${NC}"
TEMP_PACKAGE="/tmp/${PACKAGE_NAME}.tar.gz"
tar -czf "$TEMP_PACKAGE" -C . "$LOCAL_DIST_DIR"
PACKAGE_SIZE=$(du -h "$TEMP_PACKAGE" | cut -f1)
echo -e "${GREEN}压缩包创建完成: $TEMP_PACKAGE (${PACKAGE_SIZE})${NC}"

# 上传文件
echo -e "${BLUE}上传文件到远程主机...${NC}"
scp "$TEMP_PACKAGE" "${REMOTE_USER}@${REMOTE_HOST}:/tmp/"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}文件上传成功${NC}"
else
    echo -e "${RED}文件上传失败${NC}"
    rm -f "$TEMP_PACKAGE"
    exit 1
fi

# 在远程主机上部署
echo -e "${BLUE}在远程主机上部署...${NC}"
ssh "${REMOTE_USER}@${REMOTE_HOST}" << EOF
set -e

echo "=== 远程主机部署开始 ==="

# 创建目标目录
echo "创建目标目录: ${REMOTE_PATH}"
mkdir -p "${REMOTE_PATH}"

# 备份现有文件
if [ -f "${REMOTE_PATH}/translation_service" ]; then
    echo "备份现有文件..."
    BACKUP_DIR="${REMOTE_PATH}/backup_\$(date +%Y%m%d_%H%M%S)"
    mkdir -p "\$BACKUP_DIR"
    cp -r "${REMOTE_PATH}"/* "\$BACKUP_DIR/" 2>/dev/null || true
    echo "备份保存到: \$BACKUP_DIR"
fi

# 解压新文件
echo "解压新文件..."
cd /tmp
tar -xzf "${PACKAGE_NAME}.tar.gz"

# 复制文件到目标目录
echo "部署文件到: ${REMOTE_PATH}"
cp -r ${LOCAL_DIST_DIR}/* "${REMOTE_PATH}/"

# 设置权限
chmod +x "${REMOTE_PATH}/translation_service"
chmod +x "${REMOTE_PATH}/run_translation_service.sh"

# 清理临时文件
rm -f "/tmp/${PACKAGE_NAME}.tar.gz"
rm -rf "/tmp/${LOCAL_DIST_DIR}"

echo "=== 远程主机部署完成 ==="
echo ""
echo "部署信息:"
echo "  部署路径: ${REMOTE_PATH}"
echo "  文件列表:"
ls -la "${REMOTE_PATH}/"
echo ""
echo "使用方法:"
echo "  cd ${REMOTE_PATH}"
echo "  ./run_translation_service.sh --help"
echo "  ./run_translation_service.sh"
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}远程部署成功!${NC}"
else
    echo -e "${RED}远程部署失败!${NC}"
    rm -f "$TEMP_PACKAGE"
    exit 1
fi

# 清理本地临时文件
rm -f "$TEMP_PACKAGE"

echo ""
echo -e "${GREEN}===== 部署完成 =====${NC}"
echo -e "${YELLOW}远程主机: ${REMOTE_USER}@${REMOTE_HOST}${NC}"
echo -e "${YELLOW}部署路径: ${REMOTE_PATH}${NC}"
echo ""
echo -e "${BLUE}下一步操作:${NC}"
echo "1. 连接到远程主机:"
echo "   ssh ${REMOTE_USER}@${REMOTE_HOST}"
echo ""
echo "2. 进入部署目录:"
echo "   cd ${REMOTE_PATH}"
echo ""
echo "3. 查看帮助:"
echo "   ./run_translation_service.sh --help"
echo ""
echo "4. 启动服务:"
echo "   ./run_translation_service.sh"
echo ""
echo "5. 后台运行:"
echo "   nohup ./run_translation_service.sh > translation.log 2>&1 &" 