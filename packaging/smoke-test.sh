#!/usr/bin/env bash
# 宿主机冒烟测试：list-devices / 小模型推理 / API
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/build/out/bin/llama-kvmem-server"
LIB="$ROOT/build/out/lib"
MODEL="${MODEL:-$ROOT/build/models/qwen2.5-0.5b-instruct-q8_0.gguf}"
PORT="${PORT:-18999}"
export LD_LIBRARY_PATH="$LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

echo "== ldd 检查 =="
ldd "$BIN" | grep -E "not found|=> /" | grep -vE "/lib/|/lib64/|/usr/lib/" || true
ldd "$BIN" | grep "not found" && { echo "存在缺失库"; exit 1; }

echo "== --list-devices =="
"$BIN" --list-devices 2>&1 | head -15

echo "== 启动服务（小模型）=="
"$BIN" --model "$MODEL" --host 127.0.0.1 --port "$PORT" --ctx-size 4096 \
    --ui-dir "$ROOT/build/out/share/kvmem/ui" > /tmp/kvmem-smoke.log 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null || true' EXIT

ok=0
for i in $(seq 1 120); do
    if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then ok=1; break; fi
    kill -0 $SRV 2>/dev/null || { echo "进程提前退出"; tail -30 /tmp/kvmem-smoke.log; exit 1; }
    sleep 2
done
[ $ok = 1 ] || { echo "端口未就绪"; tail -30 /tmp/kvmem-smoke.log; exit 1; }
echo "服务已就绪（日志尾部）:"
tail -3 /tmp/kvmem-smoke.log

echo "== /props =="
curl -s "http://127.0.0.1:$PORT/props" | head -c 400; echo

echo "== /v1/models =="
curl -s "http://127.0.0.1:$PORT/v1/models" | head -c 300; echo

echo "== 聊天推理 =="
curl -s "http://127.0.0.1:$PORT/v1/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"default","messages":[{"role":"user","content":"用一句话介绍你自己"}],"max_tokens":64,"temperature":0}' | head -c 800
echo

echo "== Web UI =="
curl -s -o /dev/null -w "GET / -> %{http_code} (%{size_download} bytes)\n" "http://127.0.0.1:$PORT/"

echo "SMOKE_OK"
