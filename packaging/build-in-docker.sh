#!/usr/bin/env bash
# 在 Docker 中编译 kvmem-llama.cpp（CUDA 13.0，Ubuntu 22.04 / glibc 2.35，
# 产物兼容 fnOS Debian 12 / glibc 2.36），并提取产物到 build/out。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

IMAGE="${IMAGE:-kvmem-llamacpp-builder:$(git rev-parse --short HEAD 2>/dev/null || echo dev)}"
# 覆盖方式：CUDA_ARCHS="75-real;89-real" make build（CUDA 13.0 不支持 70-Volta）
ARCHS="${CUDA_ARCHS:-75-real;80-virtual;86-real;89-real;90-virtual;120a-real;121a-real}"
OUT="$ROOT/build/out"

echo "==> 构建镜像 $IMAGE (CUDA_ARCHS=$ARCHS)"
docker build -f packaging/Dockerfile --build-arg CUDA_ARCHS="$ARCHS" -t "$IMAGE" "$ROOT"

echo "==> 提取产物（容器内 root 清理 + chown 回宿主用户）"
mkdir -p "$OUT"
docker run --rm \
    -v "$OUT":/extract \
    -e HOST_UID="$(id -u)" -e HOST_GID="$(id -g)" \
    "$IMAGE" sh -c 'find /extract -mindepth 1 -delete && cp -a /out/. /extract/ && chown -R "$HOST_UID:$HOST_GID" /extract'

echo "==> 产物列表"
find "$OUT" -maxdepth 3 -type f | head -30
du -sh "$OUT"
