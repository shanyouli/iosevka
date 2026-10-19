# AGENTS.md

本文件记录在此仓库中工作的 AI/自动化代理必须遵守的约定。

## 网络与验证

- **任何需要网络下载的操作，未经用户当轮明确确认，一律不得执行**。包括但不限于：
  - `nix flake update` / `nix build` / `nix develop` 等可能触发 fetch 的命令
  - `nix eval` 触发 tarball 下载（首次求值新 input 时）
  - `git clone` / `git ls-remote` / `git fetch`
  - `python3 scripts/fetch_sources.py`（会下载 Iosevka、FontPatcher.zip、LXGW 字体）
  - `npm ci` / `npm install`
  - `curl` / `wget` / `gh api` 等一切外部请求
- 只读的本地操作（读文件、`bash -n`、`python3 -m py_compile`、`nix eval` 仅求值已缓存输入）可以直接执行。
- 若某项验证必须联网，先说明「要执行什么、会下载什么、大致耗时/体积」，等待用户确认后再执行；用户未确认则跳过，并在结论中标注为「未验证」。

## 发版流程

- 发版决策（是否构建、构建哪些产物、是否 beta、tag 名、复用哪个稳定版资产）**只由 `release.yaml` 中「🔍 探测组件版本」步骤产出的环境变量决定**；后续步骤只能读 `BUILD_*` / `BETA` / `TAG` / `BASE_TAG`，不得内联版本比较。
- 变更矩阵：iosevka 变化 → 全量 + 正式发布；仅 nf → 重建 nf 与 cn-nf；仅 lxgw → 重建 cn 与 cn-nf；nf 与 lxgw 同时变化 → 重建 nf、cn、cn-nf 后 beta 发布。
- beta 发布只上传本次变动产生的产物，未变动资产不复制、不上传。
- 复用资产只能是「未打补丁 / 未合并」的中间产物（`dist/<plan>.zip`、`dist/<plan>-NF.zip`），禁止用已合并的 `PragmaSevka-*.ttf` 再加工。
- 步骤顺序固定为「构建 → 合并 → 元数据 → 说明 → 记录并提交 `sources.json` → 创建 release」。`gh release create` 把 tag 打在远端默认分支 HEAD 上，所以必须先提交再发布，tag 才会指向带本次构建记录的 commit。
- 因此发布步骤失败时，`sources.json` 里可能已留下一个远端不存在的 tag：手动触发 workflow 并勾选 `use_manifest`（跳过上游探测、按清单固定版本全量重建）即可重发，该 tag 会被复用。`build.stable_tag` 只由正式发布推进，beta 不覆盖它。

## 命名规范

参考 maple-font（`documentation/choose.md`）的组合顺序：`<BaseName>-<feature/width>-<format marker>-<locale>-<Style>`。

- 文件名：`PragmaSevka-Regular.ttf`、`PragmaSevka-NF-Regular.ttf`、`PragmaSevka-CN-Regular.ttf`、`PragmaSevka-NF-CN-Regular.ttf`
- family：`Pragma Sevka`、`Pragma Sevka NF`、`Pragma Sevka CN`、`Pragma Sevka NF CN`
- 发布包：`<plan>.zip` / `<plan>-NF.zip`（`NF` 替代旧写法 `nerd`）
- hint 标记（`-AutoHint` / `-unhinted`）只用于发布包/目录名，不进入 family 名

## 操作入口

- 日常操作与 CI 统一走 `justfile`（`just --list`）：CI 用 `nix develop --command just <recipe>`；只有版本探测 / 清单改写这类带动态参数的步骤直接调用 `python3 scripts/fetch_sources.py`。
- 新增/修改脚本时同步更新：`justfile` 对应 recipe、`readme.org` 的本地构建段落、本文件的约定。
- 需要联网的 recipe 已在注释里标注「需要联网」，不要在没有授权时执行。

## 日志分组

Actions 日志用 group 折叠，避免长步骤刷屏：

- shell：`source scripts/gha.sh` 后用 `gha_group "标题"` / `gha_endgroup`（本地运行为空操作）。
- Python：`scripts/fetch_sources.py` 的 `group()` / `endgroup()`，仅在 `GITHUB_ACTIONS=true` 时输出。
- workflow 内联片段：直接 `echo "::group::..."` / `echo "::endgroup::"`。
- 分组标题要能说明"在构建什么"，例如 `构建 pragma-sevka-mono (spacing=term)`，便于定位失败步骤。

## 依赖与版本

- 远程依赖（Iosevka 源码、nerd-font-patcher、LXGW WenKai）统一由仓库根目录 `sources.json` 管理：版本号、下载地址、落地路径都写在该文件里。
- `sources.json` 中每个条目的 `version` 必须是明确版本号，禁止写 `latest`；升级时用 `python3 scripts/fetch_sources.py --latest <name>` 解析后写回具体版本。
- `scripts/build.sh` 对 nerd-font-patcher 的版本自检只做提示、不阻断构建：上游 `--version` 的输出会夹带 `git describe` 之类的额外 `x.y.z` 串（`vendor/FontPatcher` 位于 git 工作区内时尤甚）。版本准入由 `sources.json` + 「🔍 探测组件版本」负责，不要在构建脚本里再次硬断言。
- Nix 只提供构建环境（devShell），不得在 `flake.nix` 中抓取源码或构建字体产物。
- `nixpkgs` 固定为 stable 分支（当前 `nixos-26.05`），不跟随 unstable。
