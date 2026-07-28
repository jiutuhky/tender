#!/usr/bin/env bash
set -euo pipefail

# 假设 server 已在 8000 端口跑起来；env 里有可选 HAGENT_API_KEY
BASE=${HAGENT_BASE:-http://localhost:8000}
KEY=${HAGENT_API_KEY:-}

curl_auth() {
    if [[ -n "$KEY" ]]; then
        curl -sS -H "Authorization: Bearer $KEY" "$@"
    else
        curl -sS "$@"
    fi
}

echo "==> /healthz"
curl_auth "$BASE/healthz" | jq .

echo "==> POST /projects"
PID=$(curl_auth -X POST "$BASE/projects" -H 'Content-Type: application/json' -d '{"name": "冒烟项目"}' | jq -r .id)
echo "project_id=$PID"

echo "==> POST /sessions"
SID=$(curl_auth -X POST "$BASE/sessions" -H 'Content-Type: application/json' -d "{\"project_id\": \"$PID\"}" | jq -r .session_id)
echo "session_id=$SID"

echo "==> POST /projects/$PID/files (upload,票6:上传归属 project)"
echo "hello, hagent" > /tmp/hagent_curl_upload.txt
curl_auth -X POST "$BASE/projects/$PID/files" \
    -F "file=@/tmp/hagent_curl_upload.txt" \
    -F "path=sources/greeting.txt" | jq .

echo "==> GET /projects/$PID/workspace/files"
curl_auth "$BASE/projects/$PID/workspace/files" | jq .

echo "==> GET /projects/$PID/workspace/files/sources/greeting.txt"
curl_auth "$BASE/projects/$PID/workspace/files/sources/greeting.txt"
echo

echo "==> GET /projects/$PID/workspace/history"
curl_auth "$BASE/projects/$PID/workspace/history" | jq .

echo "==> POST /sessions/$SID/messages (SSE)"
curl_auth -N -X POST "$BASE/sessions/$SID/messages" \
    -H 'Content-Type: application/json' \
    -d '{"content": "say hi"}'

echo "==> smolvm 段(可用性探测,缺环境跳过)"
if [[ -r /dev/kvm && -w /dev/kvm ]]; then
    SM_PID=$(curl_auth -X POST "$BASE/projects" -H 'Content-Type: application/json' \
        -d '{"name": "冒烟项目-smolvm"}' | jq -r .id)
    SM_SID=$(curl_auth -X POST "$BASE/sessions" -H 'Content-Type: application/json' \
        -d "{\"project_id\": \"$SM_PID\", \"sandbox_kind\": \"smolvm\"}" | jq -r '.session_id // empty')
    if [[ -z "$SM_SID" ]]; then
        echo "skip: smolvm session 创建失败(server 未启用 smolvm 或容量不足)"
    else
        echo "smolvm session_id=$SM_SID"
        echo "hello from smolvm smoke" > /tmp/hagent_smolvm_upload.txt
        curl_auth -X POST "$BASE/projects/$SM_PID/files" \
            -F "file=@/tmp/hagent_smolvm_upload.txt" \
            -F "path=sources/probe.txt" | jq .
        echo "==> POST /sessions/$SM_SID/messages(首个消息触发租约 + 物化注入)"
        curl_auth -N -X POST "$BASE/sessions/$SM_SID/messages" \
            -H 'Content-Type: application/json' \
            -d '{"content": "列出 sources 目录"}'
        echo "==> GET /sessions/$SM_SID/files(容器内列目录,走 vsock)"
        curl_auth "$BASE/sessions/$SM_SID/files?path=sources" | jq .
        echo "==> GET /sessions/$SM_SID/files/sources/probe.txt(下载回读)"
        curl_auth "$BASE/sessions/$SM_SID/files/sources/probe.txt"
        echo
        echo "==> DELETE /sessions/$SM_SID"
        curl_auth -X DELETE "$BASE/sessions/$SM_SID" | jq .
        echo "==> DELETE /projects/$SM_PID"
        curl_auth -X DELETE "$BASE/projects/$SM_PID" | jq .
    fi
else
    echo "skip: /dev/kvm 不可读写(WSL2 重启后需重授权,见 docs)"
fi

echo "==> GET /projects"
curl_auth "$BASE/projects" | jq .

echo "==> DELETE /sessions/$SID"
curl_auth -X DELETE "$BASE/sessions/$SID" | jq .

echo "==> DELETE /projects/$PID"
curl_auth -X DELETE "$BASE/projects/$PID" | jq .
