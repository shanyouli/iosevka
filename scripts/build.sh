#!/usr/bin/env bash
# 在 nix develop 提供的环境中构建 build plan 产物。
#
# 环境变量：
#   BUILD_TTF=true|false   是否用 npm 构建原始 TTF（默认 true）
#   BUILD_NF=true|false    是否打 Nerd Font 补丁（默认 true）
#   RESTORE_DIR=<dir>      BUILD_TTF=false 时，先把该目录内容并入 build/（布局同 dist/）
#
# 产物索引写入 build/manifest.txt，供发布说明等下游步骤读取。
#
# 依赖须先由 python3 scripts/fetch_sources.py 按 sources.json 放好。
# 依赖版本一律以 sources.json 为准；nerd-font-patcher 的自报版本只做提示，不阻断构建。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./gha.sh
source "$SCRIPT_DIR/gha.sh"

REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC_DIR="$REPO_ROOT/vendor/iosevka"
OUT_DIR="$REPO_ROOT/build"
DIST_DIR="$REPO_ROOT/dist"
PATCHER_DIR="$REPO_ROOT/vendor/FontPatcher"

BUILD_TTF="${BUILD_TTF:-true}"
BUILD_NF="${BUILD_NF:-true}"

RESTORE_DIR="${RESTORE_DIR:-}"

mkdir -p "$OUT_DIR"
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

MANIFEST="$OUT_DIR/manifest.txt"
: > "$MANIFEST"
record() {
  printf '%s\t%s\n' "$1" "$2" >> "$MANIFEST"
}

read_plan() {
  python3 - "$1" <<'PY'
import sys, tomllib
with open(sys.argv[1], "rb") as f:
    plans = tomllib.load(f)["buildPlans"]
name = next(iter(plans))
print(name, plans[name].get("spacing", "normal"))
PY
}

if [[ "$BUILD_NF" == "true" ]]; then
  # nerd-font-patcher 由清单下载到 vendor/FontPatcher（版本必须明确）
  EXPECTED_PATCHER="$(python3 -c 'import json;print(json.load(open("sources.json"))["sources"]["nerd-font-patcher"]["version"].lstrip("v"))')"
  if [[ ! -f "$PATCHER_DIR/font-patcher" ]]; then
    echo "vendor/FontPatcher 中没有 font-patcher，先执行 python3 scripts/fetch_sources.py" >&2
    exit 1
  fi
  # font-patcher 依赖 python 的 fontforge 模块（nixpkgs 中同为 build input）
  if ! python3 -c 'import fontforge' 2>/dev/null; then
    echo "当前 python 环境缺少 fontforge 模块，请在 nix develop 内运行（devShell 已包含 python3Packages.fontforge）" >&2
    exit 1
  fi
  # 版本自检只提示不阻断：上游 `--version` 的输出格式不稳定（例如 3.5.x 在
  # vendor/FontPatcher 位于 git 工作区内时会夹带 `git describe` 得到的 x.y.z 串，
  # 被这里的 grep 抢到），把版本判定交给 sources.json + 发版探测步骤。
  PATCHER_OUT="$(cd "$PATCHER_DIR" && python3 font-patcher --version 2>&1 || true)"
  ACTUAL_PATCHER="$(printf '%s\n' "$PATCHER_OUT" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
  if [[ -n "$ACTUAL_PATCHER" && "$ACTUAL_PATCHER" != "$EXPECTED_PATCHER" ]]; then
    echo "⚠️  nerd-font-patcher 自报版本 $ACTUAL_PATCHER 与清单 $EXPECTED_PATCHER 不一致（不阻断，版本以 sources.json 为准）" >&2
    printf '%s\n' "$PATCHER_OUT" | sed 's/^/    /' >&2
  fi
fi

if [[ "$BUILD_TTF" != "true" && -n "$RESTORE_DIR" ]]; then
  echo "==> 从 $RESTORE_DIR 复用已有产物"
  cp -RL "$RESTORE_DIR/." "$OUT_DIR/"
fi

if [[ "$BUILD_TTF" == "true" ]]; then
  if [[ ! -f "$SRC_DIR/package.json" ]]; then
    echo "vendor/iosevka 中没有源码，先执行 python3 scripts/fetch_sources.py" >&2
    exit 1
  fi
  gha_group "npm ci"
  echo "==> 安装依赖 (npm ci)"
  ( cd "$SRC_DIR" && npm ci --no-audit --no-fund )
  gha_endgroup
else
  echo "==> 跳过 npm 构建，复用 build/ 中已有的原始 TTF"
fi

for plan_file in "$REPO_ROOT"/src/*.toml; do
  base="$(basename "$plan_file")"
  [[ "$base" == "private-build-plans.toml" ]] && continue

  read -r pname spacing <<<"$(read_plan "$plan_file")"

  if [[ "$BUILD_TTF" == "true" ]]; then
    gha_group "构建 $pname (spacing=$spacing)"
    echo "==> 构建 $pname (spacing=$spacing)"
    cp -v "$plan_file" "$SRC_DIR/private-build-plans.toml"
    rm -rf "$SRC_DIR/dist/$pname"
    ( cd "$SRC_DIR" && npm run build --no-update-notifier --targets "ttf::$pname" )

    rm -rf "$OUT_DIR/$pname"
    mkdir -p "$OUT_DIR/$pname"
    cp -RL "$SRC_DIR/dist/$pname/." "$OUT_DIR/$pname/"

    # 打包原始字体
    ( cd "$OUT_DIR/$pname" && zip -qr "$DIST_DIR/$pname.zip" . )
    record "$pname" "dist/$pname.zip"
    gha_endgroup
  else
    if [[ ! -d "$OUT_DIR/$pname/TTF" ]]; then
      if [[ "$spacing" == "term" ]]; then
        echo "build/$pname/TTF 不存在，无法复用；请改用 BUILD_TTF=true" >&2
        exit 1
      fi
      echo "==> 跳过 ${pname}（未复用且不在本次发布范围）"
      continue
    fi
    echo "==> 复用 $pname 的原始 TTF"
    rm -f "$DIST_DIR/$pname.zip"
  fi

  if [[ "$spacing" == "term" && "$BUILD_NF" == "true" ]]; then
    gha_group "Nerd Font 补丁 $pname"
    echo "==> Nerd Font 补丁 $pname"
    rm -rf "$OUT_DIR/$pname-NF"
    mkdir -p "$OUT_DIR/$pname-NF"
    for f in "$OUT_DIR/$pname"/TTF/*.ttf; do
      ( cd "$PATCHER_DIR" && python3 font-patcher \
          --mono --careful --complete --no-progressbars --quiet \
          --adjust-line-height --makegroups 6 \
          --outputdir "$OUT_DIR/$pname-NF" "$f" )
    done
    mkdir -p "$OUT_DIR/$pname-NF/TTF"
    mv "$OUT_DIR/$pname-NF"/*.ttf "$OUT_DIR/$pname-NF/TTF/"
    ( cd "$OUT_DIR/$pname-NF" && zip -qr "$DIST_DIR/$pname-NF.zip" . )
    record "$pname-NF" "dist/$pname-NF.zip"
    gha_endgroup
  fi
done

gha_group "产物索引"
echo "==> 产物："
ls -lh "$DIST_DIR"
echo "==> 索引：$MANIFEST"
cat "$MANIFEST"
gha_endgroup
