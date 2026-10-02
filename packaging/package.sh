#!/usr/bin/env bash
# 将 build/out 产物组装进 fnpack 项目并打包为 .fpk
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

APP="packaging/fnos"
OUT="$ROOT/build/out"
DIST="$ROOT/dist"
FNPACK="$ROOT/tools/fnpack"
FNPACK_VERSION="1.2.3"

[ -f "$OUT/bin/llama-kvmem-server" ] || { echo "缺少 $OUT/bin/llama-kvmem-server，先运行 make build" >&2; exit 1; }
[ -d "$OUT/lib" ] || { echo "缺少 $OUT/lib（CUDA 运行时库）" >&2; exit 1; }
[ -d "$OUT/share/kvmem/ui" ] || { echo "缺少 $OUT/share/kvmem/ui（Web UI）" >&2; exit 1; }

# fnpack
if [ ! -x "$FNPACK" ]; then
    echo "==> 下载 fnpack $FNPACK_VERSION"
    mkdir -p tools
    arch="$(uname -m)"
    case "$arch" in
        x86_64)  FNPACK_OS=linux-amd64 ;;
        aarch64) FNPACK_OS=linux-arm64 ;;
        *) echo "不支持的架构: $arch" >&2; exit 1 ;;
    esac
    curl -fsSL "https://static2.fnnas.com/fnpack/fnpack-${FNPACK_VERSION}-${FNPACK_OS}" -o "$FNPACK"
    chmod +x "$FNPACK"
fi

echo "==> 组装 app/（bin/lib/share）"
cp -f "$OUT/bin/llama-kvmem-server" "$APP/app/bin/"
rm -rf "$APP/app/lib"
cp -a "$OUT/lib" "$APP/app/lib"
rm -rf "$APP/app/share"
cp -a "$OUT/share" "$APP/app/share"
chmod 755 "$APP/app/bin/llama-kvmem-server" "$APP/app/bin/kvmem-llama"

echo "==> fnpack 打包"
rm -rf "$DIST"
mkdir -p "$DIST"
( cd "$APP" && "$FNPACK" build )

# 归位到 dist/ 并附 sha256
if ls "$APP"/*.fpk >/dev/null 2>&1; then
    for fpk in "$APP"/*.fpk; do
        cp -f "$fpk" "$DIST/"
        ( cd "$DIST" && sha256sum "$(basename "$fpk")" > "$(basename "$fpk").sha256" )
        rm -f "$fpk"
    done
fi
ls -lh "$DIST"
