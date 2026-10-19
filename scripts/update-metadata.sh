#!/usr/bin/env bash
# 用 gftools 更新合并后字体的 name table 元数据。版本号取自 sources.json。
# 只处理 output/ 下实际存在的字体（beta 发布可能只生成其中一个）。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./gha.sh
source "$SCRIPT_DIR/gha.sh"

REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

: "${FAMILY:?}" "${FAMILY_NAME:?}" "${FAMILY_NF_NAME:?}"

read_version() {
  python3 - "$1" <<'PY'
import json, sys
print(json.load(open("sources.json", encoding="utf-8"))["sources"][sys.argv[1]]["version"])
PY
}

IOSEVKA_VERSION="$(read_version iosevka)"
LXGW_VERSION="$(read_version lxgw-wenkai)"
NF_VERSION="$(read_version nerd-font-patcher)"
NOW="v$(TZ='Asia/Shanghai' date +'%Y%m%d.%H%M%S')"

for font_path in "output/$FAMILY_NAME-Regular.ttf" "output/$FAMILY_NF_NAME-Regular.ttf"; do
  [[ -f "$font_path" ]] || { echo "==> 跳过（未生成）：$font_path"; continue; }
  is_nf=""
  [[ "$font_path" == *"-NF-"* ]] && is_nf=" NF"

  gha_group "更新元数据 $(basename "$font_path")"
  gftools update-nameids "$font_path" \
    --uniqueid "$FAMILY$is_nf Regular $NOW" \
    --designer "$FUSION_DEVELOPER" \
    --manufacturer "$FUSION_DEVELOPER" \
    --version "$NOW; Iosevka $IOSEVKA_VERSION; LXGW_WenKai $LXGW_VERSION; NerdFonts $NF_VERSION" \
    --copyright "$(printf "%s\n%s\n%s" "$IOSEVKA_COPYRIGHT" "$LXGW_COPYRIGHT" "$FUSION_COPYRIGHT")" \
    --license "$FUSION_LICENSE"
  mv "$font_path.fix" "$font_path"
  gha_endgroup
done
