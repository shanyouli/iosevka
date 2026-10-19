#!/usr/bin/env bash
# 把 LXGW WenKai 的中文字形合并进 Iosevka 构建产物。
#
# 环境变量：
#   BUILD_CN=true|false        是否生成中文标准版（默认 true）
#   BUILD_CN_NF=true|false     是否生成中文 NF 版（默认 true）
#   BASE_TTF=<path>            原始 TTF，默认 build/pragma-sevka-mono/TTF/*upright*.ttf
#   BASE_NF_TTF=<path>         已打 NF 补丁的 TTF，默认 build/pragma-sevka-mono-NF/TTF/*Regular.ttf
#   FAMILY / FAMILY_NAME / FAMILY_NF / FAMILY_NF_NAME  由工作流提供
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./gha.sh
source "$SCRIPT_DIR/gha.sh"

REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

: "${FAMILY:?}" "${FAMILY_NAME:?}" "${FAMILY_NF:?}" "${FAMILY_NF_NAME:?}"

BUILD_CN="${BUILD_CN:-true}"
BUILD_CN_NF="${BUILD_CN_NF:-true}"

asset_dest() {
  python3 - "$1" <<'PY'
import json, sys
data = json.load(open("sources.json", encoding="utf-8"))
print(data["sources"][sys.argv[1]]["assets"][0]["dest"])
PY
}

if [[ -z "${BASE_TTF:-}" ]]; then
  BASE_TTF="$(find "$REPO_ROOT/build/pragma-sevka-mono/TTF" -name '*upright*.ttf' 2>/dev/null | head -1 || true)"
  BASE_TTF="${BASE_TTF:-$REPO_ROOT/build/pragma-sevka-mono/TTF/pragma-sevka-mono-normalregularupright.ttf}"
fi
if [[ -z "${BASE_NF_TTF:-}" ]]; then
  BASE_NF_TTF="$(find "$REPO_ROOT/build/pragma-sevka-mono-NF/TTF" -name '*Regular.ttf' 2>/dev/null | head -1 || true)"
fi

LXGW_MAIN="$(asset_dest lxgw-wenkai)"
LXGW_LITE="$(asset_dest lxgw-wenkai-lite)"

require_lxgw() {
  [[ -f "$LXGW_MAIN" ]] || { echo "缺少 ${LXGW_MAIN}，先运行 scripts/fetch_sources.py" >&2; exit 1; }
  [[ -f "$LXGW_LITE" ]] || { echo "缺少 ${LXGW_LITE}，先运行 scripts/fetch_sources.py" >&2; exit 1; }
}

mkdir -p output

if [[ "$BUILD_CN" == "true" ]]; then
  require_lxgw
  [[ -f "$BASE_TTF" ]] || { echo "缺少 $BASE_TTF" >&2; exit 1; }
  gha_group "合并中文标准版 $FAMILY_NAME"
  echo "==> 合并中文标准版 -> output/$FAMILY_NAME-Regular.ttf"
  # 标准版：不做 hint，避免字体数据翻倍
  python tools/run.py \
    -b "$BASE_TTF" \
    -z "$LXGW_MAIN" "$LXGW_LITE" \
    -f "$FAMILY" -s "Regular" -o "output/$FAMILY_NAME-Regular.ttf" \
    -w 500 525 1000 1050 -x 525 -l -50 -t 50 -a 1050
  gha_endgroup
else
  echo "==> 跳过中文标准版"
fi

if [[ "$BUILD_CN_NF" == "true" ]]; then
  require_lxgw
  [[ -f "$BASE_NF_TTF" ]] || { echo "缺少 Nerd Font 构建产物（build/pragma-sevka-mono-NF/TTF）" >&2; exit 1; }
  gha_group "合并中文 NF 版 $FAMILY_NF_NAME"
  echo "==> 合并中文 NF 版 -> output/$FAMILY_NF_NAME-Regular.ttf"
  python tools/run.py \
    -b "$BASE_NF_TTF" \
    -z "$LXGW_MAIN" "$LXGW_LITE" \
    -f "$FAMILY_NF" -s "Regular" -o "output/$FAMILY_NF_NAME-Regular.ttf" \
    -w 500 525 1000 1050 -x 525 -l -50 -t 50 -a 1050
  gha_endgroup
else
  echo "==> 跳过中文 NF 版"
fi
