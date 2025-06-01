#!/bin/bash
# Go Translation Service - Multi-Platform Build Script

set -e

echo "Building Go Translation Service for Multiple Platforms..."
echo "======================================================"

# Check if Go is installed
if ! command -v go &> /dev/null; then
    echo "❌ Go is not installed. Please install Go 1.21+ first."
    echo "Visit: https://golang.org/doc/install"
    exit 1
fi

# Check Go version
GO_VERSION=$(go version | grep -o 'go[0-9]\+\.[0-9]\+' | sed 's/go//')
REQUIRED_VERSION="1.21"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$GO_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Go version $REQUIRED_VERSION or higher is required. Found: $GO_VERSION"
    exit 1
fi

echo "✅ Go version: $GO_VERSION"

# Get current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Initialize Go module if not exists
if [ ! -f "go.mod" ]; then
    echo "Initializing Go module..."
    go mod init translation-service
fi

# Download dependencies
echo "Downloading dependencies..."
go mod tidy

# Build configurations for multiple platforms
declare -A BUILD_TARGETS=(
    # Linux
    ["linux-amd64"]="linux amd64"
    #["linux-arm64"]="linux arm64"
    #["linux-386"]="linux 386"
    
    # Windows
    #["windows-amd64"]="windows amd64 .exe"
    #["windows-arm64"]="windows arm64 .exe"
    #["windows-386"]="windows 386 .exe"
    
    # macOS
    #["darwin-amd64"]="darwin amd64"
    #["darwin-arm64"]="darwin arm64"
)

# Clean previous builds
echo "Cleaning previous builds..."
rm -f translation_service_*
rm -f *.tar.gz *.zip

# Build for all platforms
echo ""
echo "Building static binaries for maximum compatibility..."
echo "=================================================="

for target in "${!BUILD_TARGETS[@]}"; do
    IFS=' ' read -r GOOS GOARCH EXT <<< "${BUILD_TARGETS[$target]}"
    
    echo "Building static binary for ${target} (${GOOS}/${GOARCH})..."
    
    OUTPUT_NAME="translation_service_${target}${EXT}"
    
    # Build static binary with CGO disabled for maximum compatibility
    CGO_ENABLED=0 GOOS=$GOOS GOARCH=$GOARCH go build \
        -a \
        -ldflags="-w -s -extldflags '-static'" \
        -trimpath \
        -tags 'netgo osusergo' \
        -o "$OUTPUT_NAME" \
        translation_service.go
    
    if [ -f "$OUTPUT_NAME" ]; then
        # Get file size
        FILE_SIZE=$(stat -c%s "$OUTPUT_NAME" 2>/dev/null || stat -f%z "$OUTPUT_NAME" 2>/dev/null)
        FILE_SIZE_MB=$((FILE_SIZE / 1024 / 1024))
        
        # Make executable (for Unix-like systems)
        if [[ "$GOOS" != "windows" ]]; then
            chmod +x "$OUTPUT_NAME"
        fi
        
        # Check if binary is static
        if command -v ldd &> /dev/null && [[ "$GOOS" == "linux" ]]; then
            echo "  📋 Checking dependencies..."
            if ldd "$OUTPUT_NAME" | grep -q "not a dynamic"; then
                echo "  ✅ Static binary: $OUTPUT_NAME (${FILE_SIZE_MB}MB) - No GLIBC dependencies"
            else
                echo "  ⚠️  Dynamic binary: $OUTPUT_NAME (${FILE_SIZE_MB}MB)"
                ldd "$OUTPUT_NAME" | head -5
            fi
        else
            echo "  ✅ Built: $OUTPUT_NAME (${FILE_SIZE_MB}MB)"
        fi
    else
        echo "  ❌ Failed to build ${target}"
    fi
done

# Create a symlink for the current platform
CURRENT_OS=$(uname -s | tr '[:upper:]' '[:lower:]')
CURRENT_ARCH=$(uname -m)

case $CURRENT_ARCH in
    x86_64)
        ARCH_NAME="amd64"
        ;;
    aarch64|arm64)
        ARCH_NAME="arm64"
        ;;
    i386|i686)
        ARCH_NAME="386"
        ;;
    *)
        ARCH_NAME="amd64"  # Default fallback
        ;;
esac

CURRENT_TARGET="${CURRENT_OS}-${ARCH_NAME}"
CURRENT_BINARY="translation_service_${CURRENT_TARGET}"

if [[ "$CURRENT_OS" == "mingw"* ]] || [[ "$CURRENT_OS" == "msys"* ]]; then
    CURRENT_TARGET="windows-${ARCH_NAME}"
    CURRENT_BINARY="translation_service_${CURRENT_TARGET}.exe"
fi

if [ -f "$CURRENT_BINARY" ]; then
    if [[ "$CURRENT_OS" == "mingw"* ]] || [[ "$CURRENT_OS" == "msys"* ]]; then
        cp "$CURRENT_BINARY" "translation_service.exe"
        echo "✅ Created copy: translation_service.exe -> $CURRENT_BINARY"
    else
        ln -sf "$CURRENT_BINARY" translation_service
        echo "✅ Created symlink: translation_service -> $CURRENT_BINARY"
    fi
fi

echo ""
echo "✅ Static binary build completed successfully!"
echo ""
echo "Built binaries:"
ls -la translation_service_* 2>/dev/null || true
echo ""
echo "Platform detection on this system:"
echo "  OS: $CURRENT_OS"
echo "  Architecture: $CURRENT_ARCH ($ARCH_NAME)"
echo "  Binary: $CURRENT_BINARY"
echo ""
echo "Quick start:"
echo "  1. Set environment: export DEEPSEEK_API_KEY=\"sk-your-key\""
echo "  2. Run current platform: ./translation_service --help"
echo "  3. Copy binary to target system: scp translation_service_linux-amd64 user@server:/"
echo ""
echo "Static binary features:"
echo "  ✅ No GLIBC dependencies - works on old Linux systems"
echo "  ✅ Self-contained - no external libraries needed"
echo "  ✅ Portable - copy and run anywhere" 