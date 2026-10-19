#!/usr/bin/env python3
"""输出 release body：发布标识 + 下载链接 + 可折叠的字体参数 / 依赖信息。

冗余信息（依赖版本、构建 commit、中间产物明细）不删除，而是用 <details> 折叠，
需要的人点开即可。

环境变量：
  TAG / BETA / BASE_TAG / CHANGED   发布标识相关，缺省从 sources.json 的 build 段推断
  BUILD_TTF / BUILD_NF / BUILD_CN / BUILD_CN_NF
                                    决定列出哪些可下载资产，缺省视为 true（便于本地预览）
  FAMILY_NAME / FAMILY_NF_NAME      中文产物文件名，缺省 PragmaSevka-CN / PragmaSevka-NF-CN
  GITHUB_SERVER_URL / GITHUB_REPOSITORY
                                    拼下载直链用；缺失时回退 git remote
"""

from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def env_flag(name: str) -> bool:
    return os.environ.get(name, "true").strip().lower() != "false"


def git_remote_repo() -> str:
    """从 origin 的 URL 里取 owner/repo（支持 https 与 scp 风格）。"""
    out = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?/?$", out)
    return m.group(1) if m else ""


def main() -> int:
    os.chdir(REPO_ROOT)
    data = json.load(open("sources.json", encoding="utf-8"))
    build = data.get("build", {})
    sources = data["sources"]

    tag = os.environ.get("TAG") or build.get("tag") or "unknown"
    beta = os.environ.get("BETA", "false") == "true"
    changed = os.environ.get("CHANGED", "").strip()
    base_tag = os.environ.get("BASE_TAG") or build.get("stable_tag") or "unknown"

    # 发布资产与 release.yaml 的筛选逻辑保持一致：beta 只列本次重建的产物
    assets: list[tuple[str, str]] = []
    if env_flag("BUILD_TTF"):
        assets += [(p, "原始 TTF") for p in sorted(glob.glob("dist/*.zip")) if not p.endswith("-NF.zip")]
    if env_flag("BUILD_NF"):
        assets += [(p, "Nerd Font 补丁") for p in sorted(glob.glob("dist/*-NF.zip"))]
    cn = os.environ.get("FAMILY_NAME") or "PragmaSevka-CN"
    cn_nf = os.environ.get("FAMILY_NF_NAME") or "PragmaSevka-NF-CN"
    if env_flag("BUILD_CN") and os.path.isfile(f"output/{cn}-Regular.ttf"):
        assets.append((f"output/{cn}-Regular.ttf", "中文合并"))
    if env_flag("BUILD_CN_NF") and os.path.isfile(f"output/{cn_nf}-Regular.ttf"):
        assets.append((f"output/{cn_nf}-Regular.ttf", "中文合并 + Nerd Font"))

    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip() or git_remote_repo()

    def release_url(filename: str) -> str:
        """拼接 release 资产的下载地址；信息不全时退回文件名，避免输出坏链接。"""
        if not repo or tag == "unknown":
            return filename
        return f"{server}/{repo}/releases/download/{tag}/{filename}"

    kind = "beta（仅增量发布）" if beta else "正式发布"
    print(f"release: {tag} - {kind}")
    print(f"基于稳定版: {base_tag}")
    if changed:
        print(f"本次变更: {changed}")
    print("")

    if assets:
        print("### 下载")
        print("")
        print("| 文件 | 说明 |")
        print("| --- | --- |")
        for path, note in assets:
            name = os.path.basename(path)
            print(f"| [{name}]({release_url(name)}) | {note} |")
        print("")

    fonts = sorted(glob.glob("build/*/TTF/*.ttf")) + sorted(glob.glob("output/*.ttf"))
    if fonts:
        print("### 字体参数")
        print("")
        for f in fonts:
            info = subprocess.run(
                [sys.executable, "tools/infos_font.py", f], capture_output=True, text=True
            )
            body = (info.stdout or "").strip() or (info.stderr or "").strip() or "（读取失败）"
            print("<details>")
            print(f"<summary>{os.path.basename(f)}</summary>")
            print("")
            print("```text")
            print(body)
            print("```")
            print("")
            print("</details>")
            print("")

    print("<details>")
    print("<summary>依赖与构建信息</summary>")
    print("")
    for name, entry in sources.items():
        print(f"- {name}: {entry['version']}")
        if entry["type"] == "git":
            print(f"  - git: {entry['url']} @ {entry['version']} -> {entry['dest']}")
        for asset in entry.get("assets", []):
            print(f"  - {asset['name']}: {asset['url']}")
    print(f"- build commit: {build.get('commit') or 'unknown'}")
    print("")
    print("</details>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
