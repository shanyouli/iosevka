# Pragma Sevka 构建操作台
#
# 依赖由 sources.json 固定版本，用 python3 scripts/fetch_sources.py 拉取到 vendor/。
# 构建与合并都在 `nix develop` 提供的环境里执行（just devshell）。
#
# 常用流程：
#   just all              # 拉取 → 构建 → 合并 → 元数据 → 发布说明
#   just package          # 已有 vendor/ 时：构建 → 合并 → 元数据 → 发布说明
#   just check            # 纯本地静态检查（无网络）
#   just status           # 查看清单版本 / vendor 状态 / 已有产物

set shell := ["bash", "-euo", "pipefail", "-c"]

repo := justfile_directory()

family := "Pragma Sevka"
family_name := "PragmaSevka-CN"
family_nf := "Pragma Sevka NF CN"
family_nf_name := "PragmaSevka-NF-CN"

# 默认展示所有可用操作
default:
    @just --list

# ---------------------------------------------------------------- 依赖获取

# 按 sources.json 拉取全部依赖（需要联网）
fetch:
    python3 scripts/fetch_sources.py

# 只拉取指定条目，例如 just fetch-only iosevka；需要多个就重复执行
fetch-only name:
    python3 scripts/fetch_sources.py --only {{name}}

# 透传参数给 fetch_sources.py（CI 用，例如 just fetch-args --only iosevka --set iosevka=v34.8.0）
fetch-args *args:
    python3 scripts/fetch_sources.py {{args}}

# 查询上游最新版本并回写 sources.json 后再拉取（需要联网）
fetch-latest:
    python3 scripts/fetch_sources.py --latest iosevka --latest nerd-font-patcher --latest lxgw-wenkai --latest lxgw-wenkai-lite

# 只查询上游最新版本并回写清单，不下载（需要联网）
resolve-latest:
    python3 scripts/fetch_sources.py --no-download --latest iosevka --latest nerd-font-patcher --latest lxgw-wenkai --latest lxgw-wenkai-lite

# 打印清单里固定的版本（离线）
versions:
    python3 scripts/fetch_sources.py --list

# 打印上游最新版本（需要联网，不写清单）
latest:
    @printf '%-18s %s\n' iosevka "$(python3 scripts/fetch_sources.py --print-latest iosevka)"
    @printf '%-18s %s\n' nerd-font-patcher "$(python3 scripts/fetch_sources.py --print-latest nerd-font-patcher)"
    @printf '%-18s %s\n' lxgw-wenkai "$(python3 scripts/fetch_sources.py --print-latest lxgw-wenkai)"
    @printf '%-18s %s\n' lxgw-wenkai-lite "$(python3 scripts/fetch_sources.py --print-latest lxgw-wenkai-lite)"

# ---------------------------------------------------------------- 字体构建

# 全量构建原始 TTF 并打 Nerd 补丁：just build [ttf] [nf]
build ttf="true" nf="true":
    BUILD_TTF={{ttf}} BUILD_NF={{nf}} bash scripts/build.sh

# 只构建原始 TTF，不打补丁
build-ttf:
    BUILD_TTF=true BUILD_NF=false bash scripts/build.sh

# 只打 Nerd 补丁（复用 build/ 中的原始 TTF）
build-nf:
    BUILD_TTF=false BUILD_NF=true bash scripts/build.sh

# 复用外部产物目录（布局同 dist/）补齐 build/，例如 just build-reuse /tmp/restore
build-reuse dir:
    BUILD_TTF=false BUILD_NF=true RESTORE_DIR={{dir}} bash scripts/build.sh

# 合并中文版：just merge [cn] [cn_nf]
merge cn="true" cn_nf="true":
    FAMILY="{{family}}" FAMILY_NAME="{{family_name}}" FAMILY_NF="{{family_nf}}" FAMILY_NF_NAME="{{family_nf_name}}" BUILD_CN={{cn}} BUILD_CN_NF={{cn_nf}} bash scripts/merge.sh

# 只生成中文标准版
merge-cn:
    just merge true false

# 只生成中文 NF 版（需要先跑 build-nf）
merge-cn-nf:
    just merge false true

# 更新合并后字体的 name table（版本号取自 sources.json）
metadata:
    FAMILY="{{family}}" FAMILY_NAME="{{family_name}}" FAMILY_NF="{{family_nf}}" FAMILY_NF_NAME="{{family_nf_name}}" bash scripts/update-metadata.sh

# 生成 release body 到 release-body.md
notes:
    bash scripts/release-notes.sh | tee release-body.md

# ---------------------------------------------------------------- 组合流程

# 已有 vendor/ 时的完整本地流程：构建 → 合并 → 元数据 → 说明
package: build merge metadata notes

# 从零开始的完整流程：拉取 → 构建 → 合并 → 元数据 → 说明
all: fetch package

# 仅做增量（beta）产物：复用已有 TTF，只重跑合并
merge-only: merge metadata notes

# ---------------------------------------------------------------- 发版辅助

# 记录一次构建到清单：just record v34.8.0-nf1 [true]（第二个参数表 beta）
record tag prerelease="false":
    python3 scripts/fetch_sources.py --record-build {{tag}} {{ if prerelease == "true" { "--prerelease" } else { "" } }}

# 查看当前发布状态（离线）
status:
    @bash scripts/status.sh

# ---------------------------------------------------------------- 环境与检查

# 进入构建环境（devShell）
devshell:
    nix develop

# 查看 flake 输出
flake-show:
    nix flake show

# 更新全部 flake inputs（需要联网）：just update-flake [--commit-lock-file]
update-flake *args:
    nix flake update {{args}}

# 只更新指定 input，例如 just update-flake-input nixpkgs（需要联网）
update-flake-input input:
    nix flake update {{input}}

# 校验 flake 输出（不构建）
flake-check:
    nix flake check --no-build

# 纯本地静态检查：脚本语法、Python 编译、workflow YAML、多字节变量名风险
check:
    @bash -n scripts/*.sh
    @python3 -m py_compile scripts/fetch_sources.py
    @ruby -ryaml -e 'Dir.glob(".github/workflows/*").each { |f| YAML.load_file(f) }; puts "workflows: ok"'
    @python3 -c 'import pathlib, re, sys; pat = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)(?=[^\x00-\x7f])"); bad = [(str(f), i, m.group(1)) for f in list(pathlib.Path("scripts").glob("*")) + list(pathlib.Path(".github/workflows").glob("*.y*ml")) if f.is_file() for i, line in enumerate(f.read_text().splitlines(), 1) for m in pat.finditer(line)]; [print(f"{f}:{i}: ${n}") for f, i, n in bad]; print(f"多字节变量名风险: {len(bad)}"); sys.exit(1 if bad else 0)'
    @echo "check: ok"

# 清理构建产物（保留 vendor/）
clean:
    rm -rf build dist output release-body.md

# 清理包括 vendor/ 在内的全部生成物
clean-all:
    rm -rf build dist output release-body.md vendor/iosevka vendor/FontPatcher vendor/lxgw
    mkdir -p vendor/iosevka vendor/FontPatcher vendor/lxgw
    touch vendor/iosevka/.gitkeep vendor/FontPatcher/.gitkeep vendor/lxgw/.gitkeep
