# KVMem LLaMA 构建镜像
# 基于 nvidia/cuda 13.0（匹配目标 NAS 驱动 580 / CUDA 13.0），Debian 兼容（glibc 2.35 <= fnOS 2.36）
FROM nvidia/cuda:13.0.3-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

# 基础工具 + 新版 CMake（Ubuntu 22.04 自带 3.22，无法识别 sm_120/121 架构，
# ggml 的 120a-real/121a-real 需要 CMake >= 3.31/4.0 的校验规则）
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl xz-utils git python3 python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir "cmake>=3.31"

# Node.js 22（Web UI 构建需要）
ARG NODE_VERSION=v22.14.0
RUN curl -fsSL "https://nodejs.org/dist/${NODE_VERSION}/node-${NODE_VERSION}-linux-x64.tar.xz" -o /tmp/node.tar.xz \
    && tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 \
    && rm /tmp/node.tar.xz \
    && node --version && npm --version

WORKDIR /src
COPY kvmem-llama.cpp/ /src/

# 目标 GPU 架构（fat binary）。注意：CUDA 13.0 工具链已不支持 compute_70（Volta）。
#   75-real Turing(RTX 20/16) / 80-virtual A100 /
#   86-real RTX 30 系 / 89-real RTX 40 系 / 90-virtual Hopper /
#   120a-real,121a-real Blackwell(RTX 50 系)
ARG CUDA_ARCHS="75-real;80-virtual;86-real;89-real;90-virtual;120a-real;121a-real"
RUN set -eux \
    && scripts/apply-patches.sh \
    && cmake -S . -B build \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_CUDA_ARCHITECTURES="${CUDA_ARCHS}" \
        -DGGML_CUDA=ON \
        -DGGML_CUDA_FA_ALL_QUANTS=ON \
        -DKVMEM_BUILD_LLAMA=ON \
        -DLLAMA_KVMEM=ON \
        -DLLAMA_KVMEM_ROOT=/src \
    && cmake --build build -j"$(nproc)" \
    && ls -lh build/bin/llama-kvmem-server

# Web UI：完整版（share/kvmem/ui，服务器默认目录）+ 轻量版（share/kvmem/ui-lightweight）
RUN set -eux \
    && python3 scripts/build-webui.py --build-dir /uiwork --output /src/build/share/kvmem/ui --full-ui \
    && python3 scripts/build-webui.py --build-dir /uiwork --output /src/build/share/kvmem/ui-lightweight \
    && ls /src/build/share/kvmem/ui | head

# 打包产物：二进制 + 运行时库闭包 + Web UI
# patchelf 用于把构建期绝对 RUNPATH 重写为 $ORIGIN（跨机器可用）
RUN apt-get update \
    && apt-get install -y --no-install-recommends patchelf \
    && rm -rf /var/lib/apt/lists/*

COPY packaging/stage_libs.py /usr/local/bin/stage_libs.py
RUN set -eux \
    && mkdir -p /out/bin /out/lib /out/share/kvmem \
    && cp -L build/bin/llama-kvmem-server /out/bin/ \
    && python3 /usr/local/bin/stage_libs.py /out/bin/llama-kvmem-server /out/lib \
    && cp -r build/share/kvmem/ui /out/share/kvmem/ \
    && cp -r build/share/kvmem/ui-lightweight /out/share/kvmem/ \
    # patchelf 0.14（Debian 12 系）没有 --set-runpath；--set-rpath 在已有
    # DT_RUNPATH 的对象上会更新 RUNPATH（已验证）
    && patchelf --set-rpath '$ORIGIN:$ORIGIN/../lib' /out/bin/llama-kvmem-server \
    && for f in /out/lib/*.so*; do patchelf --set-rpath '$ORIGIN' "$f"; done \
    && readelf -d /out/bin/llama-kvmem-server | grep -E 'RUNPATH|RPATH' \
    && echo '--- final ldd (clean env, 仅允许 libcuda 由驱动提供) ---' \
    && { env -u LD_LIBRARY_PATH ldd /out/bin/llama-kvmem-server || true; }
