#!/usr/bin/env bash
# 打印当前发布状态：清单版本、最近构建、vendor 与产物情况。全程离线。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

field() {
  python3 scripts/fetch_sources.py --get "$1" 2>/dev/null || true
}

echo "清单版本："
python3 scripts/fetch_sources.py --list | awk -F'\t' '{printf "  %-18s %-16s %s\n", $1, $2, $3}'

echo ""
echo "最近构建："
printf '  tag=%s prerelease=%s stable_tag=%s\n' \
  "$(field build.tag)" "$(field build.prerelease)" "$(field build.stable_tag)"

echo ""
echo "vendor 状态："
if [[ -f vendor/iosevka/package.json ]]; then
  echo "  iosevka: 已就绪"
else
  echo "  iosevka: 缺失（just fetch-only iosevka）"
fi
if [[ -f vendor/FontPatcher/font-patcher ]]; then
  echo "  nerd-font-patcher: 已就绪"
else
  echo "  nerd-font-patcher: 缺失（just fetch-only nerd-font-patcher）"
fi
if [[ -d vendor/lxgw ]]; then
  echo "  lxgw: 已就绪"
else
  echo "  lxgw: 缺失（just fetch-only lxgw-wenkai）"
fi

echo ""
echo "产物："
for dir in build dist output; do
  if [[ -d "$dir" ]] && [[ -n "$(ls -A "$dir" 2>/dev/null)" ]]; then
    ls -1 "$dir" | sed "s|^|  $dir/|"
  else
    echo "  $dir/ 为空"
  fi
done
