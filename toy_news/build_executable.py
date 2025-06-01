#!/usr/bin/env python3
"""
构建可执行文件的脚本
使用PyInstaller将translation_service.py打包成独立的可执行文件
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def build_executable():
    """构建可执行文件"""
    
    # 确保在正确的目录
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # 源文件路径
    source_script = "scripts/translation_service.py"
    
    if not os.path.exists(source_script):
        print(f"Error: Source script {source_script} not found!")
        return False
    
    print("Building translation service executable...")
    print(f"Source: {source_script}")
    
    # 获取项目根路径的toy_news模块
    toy_news_path = os.path.join(os.getcwd(), "toy_news")
    
    # PyInstaller命令
    cmd = [
        "pyinstaller",
        "--onefile",  # 打包成单个可执行文件
        "--name=translation_service",  # 可执行文件名称
        "--distpath=dist",  # 输出目录
        "--workpath=build",  # 临时文件目录
        "--specpath=build",  # spec文件目录
        "--console",  # 控制台应用
        f"--add-data={toy_news_path}{os.pathsep}toy_news",  # 包含toy_news模块
        "--hidden-import=toy_news.translators.deepseek_translator",  # 确保翻译器模块被包含
        "--hidden-import=pymongo",  # 确保pymongo被包含
        "--hidden-import=requests",  # 确保requests被包含
        "--hidden-import=openai",  # 确保openai被包含
        "--paths=.",  # 添加当前目录到路径
        "--clean",  # 清理临时文件
        source_script
    ]
    
    try:
        # 执行PyInstaller
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Build successful!")
        print(result.stdout)
        
        # 检查生成的文件
        executable_path = "dist/translation_service"
        if os.path.exists(executable_path):
            file_size = os.path.getsize(executable_path)
            print(f"\nExecutable created: {executable_path}")
            print(f"File size: {file_size / (1024*1024):.1f} MB")
            
            # 给可执行文件添加执行权限
            os.chmod(executable_path, 0o755)
            print("Execute permission set.")
            
            return True
        else:
            print("Error: Executable file not found!")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False


def create_run_script():
    """创建运行脚本"""
    
    run_script_content = '''#!/bin/bash
# Translation Service 运行脚本

# 默认配置 - 使用统一翻译架构
DEFAULT_INTERVAL=10
DEFAULT_MONGO_URI="mongodb://localhost:27017/"
DEFAULT_MONGO_DB="scrapy_items"

# 显示帮助
show_help() {
    echo "Unified Translation Service 可执行文件运行脚本"
    echo ""
    echo "用法:"
    echo "  $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -i, --interval SECONDS   检查间隔秒数 (默认: 10)"
    echo "  -u, --mongo-uri URI      MongoDB URI (默认: mongodb://localhost:27017/)"
    echo "  -d, --mongo-db DB        MongoDB 数据库名 (默认: scrapy_items)"
    echo "  --show-stats             显示统计信息并退出"
    echo "  -h, --help               显示此帮助信息"
    echo ""
    echo "说明:"
    echo "  统一翻译服务处理 translation_pending 队列中的数据"
    echo "  翻译结果直接更新到 toys_normalized 集合"
    echo "  翻译字段: name, description"
    echo ""
    echo "示例:"
    echo "  $0                        # 使用默认配置运行"
    echo "  $0 -i 30                  # 30秒检查间隔"
    echo "  $0 --show-stats           # 显示统计信息"
}

# 解析参数
INTERVAL="$DEFAULT_INTERVAL" 
MONGO_URI="$DEFAULT_MONGO_URI"
MONGO_DB="$DEFAULT_MONGO_DB"
SHOW_STATS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--interval)
            INTERVAL="$2"
            shift 2
            ;;
        -u|--mongo-uri)
            MONGO_URI="$2"
            shift 2
            ;;
        -d|--mongo-db)
            MONGO_DB="$2"
            shift 2
            ;;
        --show-stats)
            SHOW_STATS=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
done

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXECUTABLE="$SCRIPT_DIR/translation_service"

# 检查可执行文件是否存在
if [ ! -f "$EXECUTABLE" ]; then
    echo "错误: 可执行文件 $EXECUTABLE 不存在!"
    echo "请先运行构建脚本生成可执行文件。"
    exit 1
fi

# 构建命令参数
ARGS=(
    "--mongo-uri" "$MONGO_URI"
    "--mongo-db" "$MONGO_DB"
)

if [ "$SHOW_STATS" = true ]; then
    ARGS+=("--show-stats")
else
    ARGS+=("--interval" "$INTERVAL")
fi

# 显示配置信息
echo "===== Unified Translation Service ====="
echo "可执行文件: $EXECUTABLE"
echo "MongoDB URI: $MONGO_URI"
echo "MongoDB DB: $MONGO_DB"
if [ "$SHOW_STATS" = false ]; then
    echo "检查间隔: ${INTERVAL}秒"
    echo "处理队列: translation_pending"
    echo "更新集合: toys_normalized"
    echo "翻译字段: name, description"
fi
echo "========================================"
echo ""

# 运行可执行文件
exec "$EXECUTABLE" "${ARGS[@]}"
'''
    
    with open("dist/run_translation_service.sh", "w") as f:
        f.write(run_script_content)
    
    # 给脚本添加执行权限
    os.chmod("dist/run_translation_service.sh", 0o755)
    print("Run script created: dist/run_translation_service.sh")


def main():
    """主函数"""
    print("Translation Service Executable Builder")
    print("=====================================")
    
    # 构建可执行文件
    if build_executable():
        print("\n" + "="*50)
        create_run_script()
        
        print("\n" + "="*50)
        print("构建完成!")
        print("")
        print("生成的文件:")
        print("  - dist/translation_service (可执行文件)")
        print("  - dist/run_translation_service.sh (运行脚本)")
        print("")
        print("使用方法:")
        print("  1. 直接运行: ./dist/translation_service --help")
        print("  2. 使用脚本: ./dist/run_translation_service.sh --help")
        print("")
        print("示例:")
        print("  ./dist/run_translation_service.sh")
        print("  ./dist/run_translation_service.sh --show-stats")
        print("  ./dist/run_translation_service.sh -i 30")
        
    else:
        print("构建失败!")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 