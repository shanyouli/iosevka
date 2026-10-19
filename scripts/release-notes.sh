#!/usr/bin/env bash
# 输出 release body（字体信息汇总）。版本信息全部来自 sources.json。
# 可选环境变量：CHANGED（本次变更的组件，逗号分隔）、BETA（true/false）、BASE_TAG。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

python3 - <<'PY'
import json
import os

data = json.load(open("sources.json", encoding="utf-8"))
build = data.get("build", {})
sources = data["sources"]

tag = os.environ.get("TAG") or build.get("tag") or "unknown"
beta = os.environ.get("BETA", "false") == "true"
changed = os.environ.get("CHANGED", "").strip()
base_tag = os.environ.get("BASE_TAG") or build.get("stable_tag") or "unknown"

kind = "beta（仅增量发布）" if beta else "正式发布"
print(f"release: {tag}（{kind}）")
print(f"build commit: {build.get('commit') or 'unknown'}")
print(f"基于稳定版: {base_tag}")
if changed:
    print(f"本次变更: {changed}")
print("")

for name, entry in sources.items():
    print(f"- {name}: {entry['version']}")
    if entry["type"] == "git":
        print(f"  git: {entry['url']} @ {entry['version']} -> {entry['dest']}")
    for asset in entry.get("assets", []):
        print(f"  {asset['name']}: {asset['url']}")
PY

echo ""
if [ -f build/manifest.txt ] && [ -s build/manifest.txt ]; then
  echo "本次生成的发布包："
  while IFS="$(printf '\t')" read -r kind path; do
    [ -n "$kind" ] && echo "- $kind: $path"
  done < build/manifest.txt
  echo ""
fi

for f in build/*/TTF/*.ttf output/*.ttf; do
  [ -f "$f" ] || continue
  echo "* $(basename "$f")"
  python tools/infos_font.py "$f"
  echo ""
done
