# kvmem-llamacpp-cuda → 飞牛 fnOS 安装包

将 [kvmem/kvmem-llama.cpp](https://github.com/kvmem/kvmem-llama.cpp)（v0.17.0，CUDA）编译为
x86_64 多架构 fat binary，连同 CUDA 13.0 运行时库与 Web UI 一起，打包为飞牛 fnOS 应用
安装包（`.fpk`），可用应用中心或 `appcenter-cli` 安装。

## 目标运行环境（已实测确认）

| 项 | 值 |
| --- | --- |
| 系统 | 飞牛 fnOS（Debian 12 bookworm，glibc 2.36，x86_64，内核 6.18） |
| GPU | NVIDIA GeForce RTX 4080（sm_89） |
| 驱动 | NVIDIA 580.142（`Nvidia-Driver-580` 应用），最高支持 CUDA 13.0 |
| `/dev/nvidia*` | root:root 0666（任意用户可访问 GPU） |

**关键约束：驱动 580 只支持到 CUDA 13.0，因此必须用 CUDA 13.0 工具链编译**
（上游 README 的验证基线是 CUDA 13.2.86；13.2 二进制在 580 驱动上无法运行。
Q8/BF16 模型不受影响，IQ3/IQ4 量化模型未在上游 13.0 工具链上验证过，请自行确认）。

## 仓库结构

```
├── Makefile                    # 入口：make icons / build / package
├── kvmem-llama.cpp/            # git submodule，固定在 tag v0.17.0
│   └── llama.cpp/              # 二级 submodule（ggml-org/llama.cpp @ b81c99b47）
├── packaging/
│   ├── Dockerfile              # nvidia/cuda:13.0.3-devel-ubuntu22.04 构建镜像
│   ├── build-in-docker.sh      # docker 构建 + 产物提取到 build/out
│   ├── stage_libs.py           # 按 ldd 闭包收集 CUDA 运行时库
│   ├── package.sh              # 组装 app/ 并 fnpack build → dist/*.fpk
│   ├── make_icons.py           # 生成包图标/入口图标（PIL）
│   └── fnos/                   # fnpack 项目（静态部分，全部入库）
│       ├── manifest            # 应用元数据
│       ├── ICON.PNG / ICON_256.PNG
│       ├── cmd/                # 生命周期脚本（main/install_*/upgrade_*/uninstall_*/config_*）
│       ├── config/privilege    # 包用户 + join-groups: render,video
│       ├── config/resource     # 共享目录 kvmemllamacpp/models + /usr/local/bin/kvmem-llama
│       ├── wizard/             # install/config/upgrade/uninstall 向导
│       └── app/
│           ├── ui/config       # 桌面入口（iframe → ${wizard_port}）
│           ├── ui/images/      # 入口图标 icon_64/icon_256
│           └── bin/kvmem-llama # 系统 PATH 下的 CLI 包装脚本（静态）
├── build/                      # docker 构建产物（gitignore）
│   └── out/{bin,lib,share/kvmem/ui,share/kvmem/ui-lightweight}
└── dist/                       # 最终 .fpk + sha256（gitignore）
```

## 构建

要求：Docker（可访问 Docker Hub）、Python3 + Pillow（图标）、curl。

```bash
make all            # = icons + build + package
# 或分步：
make icons          # 生成图标
make build          # docker 内编译（CUDA 13.0，fat binary），产物在 build/out
make package        # 组装 + fnpack build，输出 dist/kvmemllamacpp-*.fpk
```

只针对特定 GPU 编译（更快、更小）：

```bash
CUDA_ARCHS="89-real" make build      # 仅 RTX 40 系
CUDA_ARCHS="75-real;89-real" make build
```

默认架构集：`75-real;80-virtual;86-real;89-real;90-virtual;120a-real;121a-real`
（Turing/Ampere/Ada/Hopper/Blackwell；-real 为原生 cubin，-virtual 为 PTX JIT。
CUDA 13.0 工具链不再支持 compute_70/Volta，故不含 V100）。

构建镜像：`nvidia/cuda:13.0.3-devel-ubuntu22.04`（glibc 2.35 ≤ fnOS 2.36，前向兼容）。
镜像内额外安装 pip 版 CMake ≥3.31（Ubuntu 22.04 自带 3.22 无法识别 sm_120/121）
与 Node.js 22（构建 Web UI）。

上游构建命令等价于：

```bash
scripts/apply-patches.sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CUDA_ARCHITECTURES="..." \
    -DGGML_CUDA=ON -DGGML_CUDA_FA_ALL_QUANTS=ON \
    -DKVMEM_BUILD_LLAMA=ON -DLLAMA_KVMEM=ON -DLLAMA_KVMEM_ROOT=.
cmake --build build -j$(nproc)
python3 scripts/build-webui.py --full-ui --output build/share/kvmem/ui
python3 scripts/build-webui.py --output build/share/kvmem/ui-lightweight
```

## 应用行为（安装后）

- 安装位置 `/var/apps/kvmemllamacpp`，包用户 `kvmemllamacpp_user`（加入 render/video 组）。
- 服务端口默认 `18200`（安装/设置向导可改），桌面入口为 iframe 打开 Web UI。
  服务进程以 `LD_LIBRARY_PATH=<app>/lib` 启动，使用包内 CUDA 13.0 运行时，
  与 NAS 上已装的 CUDA 12.8（Nvidia-Driver-580 附带）互不干扰。
- 模型：向导可填固定 GGUF 路径；留空则自动选择共享目录 `kvmemllamacpp/models`
  中**唯一**的 `.gguf`（多个时需在设置中指定）。启动前找不到模型会给出明确报错。
- 视觉映射（mmproj）：向导可填 vision projector 的 `.mmproj/.gguf` 路径，
  启动时追加 `--mmproj`；纯文本模型留空。设置了但文件不可读会启动失败并明确报错。
- API Key：向导可填（password 字段），支持逗号分隔多个 key，启动时追加 `--api-key`。
  设置后所有 API 请求须携带 `Authorization: Bearer <key>`，否则 401
  （实测：无 key 401 / 错 key 401 / 正确 key 200）。留空则不启用鉴权。
  **开启局域网访问时强烈建议设置**。key 明文存于 `etc/config.conf`（权限 600，
  仅包用户与 root 可读），日志中不出现明文（记为 `api_key=***`）。

### 启动参数（默认值对齐上游 IQ3 配方 `scripts/start-iq3.sh`）

| 向导字段 | 服务器参数 | 默认（IQ3 配方） | 说明 |
|---|---|---|---|
| 主模型路径 | `--model` | 自动/必填 | 见上 |
| 视觉映射 | `--mmproj` | 空 | 多模态 projector |
| 视觉编码器位置 | `--no-mmproj-offload` / `--mmproj-offload` | cpu | IQ3 配方视觉走 CPU |
| KV 缓存类型 | `--kv-dtype` | q8_0 | f16/f32 精度更高更费显存 |
| 上下文长度 | `--ctx-size` | 262144 | 256K；超出 GPU 工作集由 KVMem 主机内存检索 |
| KVMem GPU 工作集 | `--kvmem-budget` | 36864 | 0 = 取上下文长度（不检索） |
| KVMem 生成预留 | `--kvmem-gen-reserve` | 16384 | 解码预留 GPU 空间 |
| 默认最大生成 | `--n-predict` | 16384 | -1 = 不额外限制 |
| 图片最大 tokens | `--image-max-tokens` | 512 | 单图上限 |
| MTP 投机解码 | `--spec-type` | draft-mtp | **模型不含 MTP 层时自动回退 none**（启动期检测，日志有记录） |
| 思考模式 | `--enable-thinking` | on | ⚠ 非 Thinking 模型（模板无思考标记）须关闭，否则所有请求报错 |
| 思考 token 预算 | `--reasoning-budget` | 4096 | -1 不限；思考关闭时忽略 |

对应关系：`start-server.py --recipe iq3` 的 argv（`-c 262144 -n 16384
--kvmem-budget 36864 --kvmem-gen-reserve 16384 --kv-dtype q8_0
--spec-type draft-mtp --enable-thinking --reasoning-budget 4096
--no-mmproj-offload --image-max-tokens 512`）。服务器内部默认值
（`kvmem-mtp-state=replay`、`kvmem-query-replay=auto`、`kvmem-query-policy=user`、
`spec-draft-n-max=3`、`spec-kv-dtype=f16`、`kvmem-block-tokens=128`）与配方一致，
未单独暴露；如需调整可用 `/usr/local/bin/kvmem-llama` 直接命令行启动。
- 启动流程：先加载模型（大模型可能数分钟）后绑定端口；`cmd/main` 等待端口最多 300s，
  超时但进程存活视为“加载中”并成功返回，由系统 checkport 跟踪状态。
- 局域网访问默认关闭（绑定 127.0.0.1）；向导开启后绑定 0.0.0.0。
- 日志：`/var/apps/kvmemllamacpp/var/server.log`。
- 卸载保留共享目录中的模型与日志。
- 命令行：`/usr/local/bin/kvmem-llama --help`（包装脚本自动设置库路径）。

## 安装到 NAS

```bash
# 将 dist/kvmemllamacpp.fpk 上传到 NAS（scp/文件管理器均可），然后：
sudo appcenter-cli install-fpk /path/to/kvmemllamacpp.fpk
# 向导值可通过环境变量文件传入（config.env，每行 key=value）：
#   wizard_port=18200
#   wizard_model_path=/vol1/@appdata.../kvmemllamacpp/models/model.gguf
#   wizard_mmproj_path=/vol1/.../mmproj.gguf      # 视觉映射，可选
#   wizard_api_key=sk-xxx                         # API Key，可选（多 key 逗号分隔）
#   wizard_ctx_size=32768
#   wizard_lan_access=no
sudo appcenter-cli install-fpk kvmemllamacpp.fpk --env config.env
sudo appcenter-cli start kvmemllamacpp
```

或在 fnOS 应用中心界面手动上传安装。

## 验证记录（2026-10-02）

- 编译：nvidia/cuda:13.0.3-devel-ubuntu22.04，nvcc 13.0.88 / GCC 11.4 /
  CMake 4.4（pip），fat binary 架构 75/80/86/89/90/120a/121a。
- 随包运行时库（ldd 闭包，14 个）：项目库 libllama/libllama-common/libmtmd/
  libggml/libggml-base/libggml-cuda/libggml-cpu + CUDA 13.0 的
  libcudart/libcublas/libcublasLt/libnccl + libstdc++/libgcc_s/libgomp。
  RUNPATH 已 patchelf 为 `$ORIGIN:$ORIGIN/../lib`，无 LD_LIBRARY_PATH 亦可运行。
- 宿主机冒烟测试（RTX 2060 SUPER / 驱动 615 / `packaging/smoke-test.sh`）：
  - `--list-devices` 正常识别 sm_75 设备
  - Qwen2.5-0.5B-Instruct Q8_0 启动成功：KVMem 启用（method=retrieval），
    4096 ctx，端口绑定正常
  - `/props`、`/v1/models`、`/v1/chat/completions` 全部正常（185 tok/s 生成连贯回答）
  - 内置完整 Web UI：`GET /` → 200
- `cmd/main` 生命周期脚本已在 /tmp 沙盒完整模拟：自动/指定模型、端口冲突、
  幂等 start、stop/status 退出码（0/3）、无模型/无 mmproj 时的用户可见报错、
  全量 IQ3 参数透传、API key 往返（含逗号）、**MTP 自动回退**（draft-mtp 启动失败
  → 检测日志特征 → none 重启成功）。
- 完整 IQ3 配方 argv 在真实服务器上验证：非 MTP 模型下 `--spec-type draft-mtp`
  启动即失败（日志 `model doesn't contain MTP layers`），去掉后
  `n_ctx=262144 budget=36864 reserve=16384 think=1 rbudget=4096 qmax=512`
  全部生效，推理正常；思考模式组合矩阵已测（仅 `think=on + 预算>0 + 模板无标记`
  报错，其余组合正常）。
- 产物：`dist/kvmemllamacpp.fpk`（773MB，gzip tar，22 个条目 + app.tgz 122 条目）。
- 待目标 NAS 复核：`appcenter-cli start kvmemllamacpp` 后
  `curl 127.0.0.1:18200/props`（驱动 580/CUDA 13.0 兼容性与实际吞吐）。

## 更新上游版本

```bash
cd kvmem-llama.cpp
git fetch --tags && git checkout vX.Y.Z
git submodule update --init
cd .. && make build package
```

注意同步更新 `packaging/fnos/manifest` 的 `version` 与 `changelog`。
