#!/usr/bin/env python3
"""按 sources.json 清单获取所有远程依赖，并回写实际使用的版本 / 下载地址。

清单是唯一的版本与下载源真相：
  - type=git            : git clone --branch <version> 到 <dest>
  - type=github-release : 下载 <assets> 到 <dest>，version 支持 "latest"（解析后回写）
  - type=nixpkgs        : 不下载，由 flake devShell 提供，仅校验版本一致

用法：
  python3 scripts/fetch_sources.py                          # 获取全部
  python3 scripts/fetch_sources.py --only iosevka           # 只获取指定项
  python3 scripts/fetch_sources.py --set iosevka=v34.9.0    # 先改清单版本再获取
  python3 scripts/fetch_sources.py --latest iosevka         # 查询上游最新版本并回写
  python3 scripts/fetch_sources.py --print-latest iosevka   # 只打印上游最新版本
  python3 scripts/fetch_sources.py --print-version iosevka  # 只打印清单中固定版本
  python3 scripts/fetch_sources.py --get build.stable_tag   # 读取清单任意字段
  python3 scripts/fetch_sources.py --record-build v34.9.0   # 记录本次构建（正式）
  python3 scripts/fetch_sources.py --record-build v34.9.0-nf1 --prerelease
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "sources.json"


def now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def load() -> dict:
    return json.loads(MANIFEST.read_text())


def save(data: dict) -> None:
    MANIFEST.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def log(msg: str) -> None:
    print(msg, flush=True)


def in_gha() -> bool:
    return os.environ.get("GITHUB_ACTIONS") == "true"


def group(title: str) -> None:
    if in_gha():
        print(f"::group::{title}", flush=True)


def endgroup() -> None:
    if in_gha():
        print("::endgroup::", flush=True)


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "iosevka-build"})
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"token {token}")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read()
        except Exception:  # noqa: BLE001
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def github_latest_tag(repo: str) -> str:
    payload = json.loads(http_get(f"https://api.github.com/repos/{repo}/releases/latest"))
    tag = payload.get("tag_name")
    if not tag:
        raise SystemExit(f"无法获取 {repo} 的最新 release tag")
    return tag


def download(url: str, dest: pathlib.Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(http_get(url))
    log(f"    ↓ {dest.relative_to(ROOT)} ({dest.stat().st_size} bytes)")


def extract_zip(zip_path: pathlib.Path, target: pathlib.Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(target)
    # 某些包只有单一顶层目录，展平一层便于调用
    entries = list(target.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        inner = entries[0]
        for child in inner.iterdir():
            shutil.move(str(child), target / child.name)
        inner.rmdir()
    log(f"    ⤷ 解压到 {target.relative_to(ROOT)}")


def fetch_git(name: str, entry: dict) -> None:
    dest = ROOT / entry["dest"]
    version = entry["version"]
    if version in ("latest", "", None):
        raise SystemExit(
            f"{name}: 清单中的版本必须明确（当前为 {version!r}），先运行 --latest {name} 解析"
        )
    log(f"==> {name}: git clone {entry['url']} @ {version}")
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", version, entry["url"], str(dest)],
        check=True,
    )
    shutil.rmtree(dest / ".git", ignore_errors=True)


def fetch_github_release(name: str, entry: dict) -> None:
    version = entry["version"]
    if version in ("latest", "", None):
        raise SystemExit(
            f"{name}: 清单中的版本必须明确（当前为 {version!r}），先运行 --latest {name} 解析"
        )

    base_dest = entry.get("dest") or str(pathlib.Path(entry["assets"][0]["extract_to"]).parent)
    (ROOT / base_dest).mkdir(parents=True, exist_ok=True)

    for asset in entry.get("assets", []):
        url = f"https://github.com/{entry['repo']}/releases/download/{version}/{asset['name']}"
        asset["url"] = url
        asset["dest"] = str(pathlib.Path(base_dest) / asset["name"])
        log(f"==> {name}: {asset['name']} @ {version}")
        file_path = ROOT / asset["dest"]
        download(url, file_path)
        if asset.get("extract_to"):
            extract_zip(file_path, ROOT / asset["extract_to"])


def check_nixpkgs(name: str, entry: dict) -> None:
    attr, version = entry["attr"], entry["version"]
    log(f"==> {name}: 由 devShell 提供 ({attr} {version})")
    tool = shutil.which(attr)
    if not tool:
        log(f"    ⚠️  当前 PATH 中没有 {attr}，请在 nix develop 内运行")
        return
    try:
        out = subprocess.run(
            [tool, "--version"], capture_output=True, text=True, check=False
        ).stdout
    except OSError:
        return
    if version not in out:
        log(f"    ⚠️  {attr} 实际版本与清单不一致（清单 {version}）：{out.strip()}")


def github_repo_of(entry: dict) -> str:
    """从 repo 字段或 git url 中解析 owner/repo。"""
    if entry.get("repo"):
        return entry["repo"]
    match = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?$", entry.get("url", ""))
    if not match:
        raise SystemExit(f"{entry.get('url')!r} 不是 GitHub 仓库，无法查询最新版本")
    return f"{match.group(1)}/{match.group(2)}"


def resolve_latest(name: str, entry: dict) -> str:
    """查询上游最新 release tag；git 类型依赖 GitHub Releases。"""
    kind = entry["type"]
    if kind in ("git", "github-release"):
        return github_latest_tag(github_repo_of(entry))
    raise SystemExit(f"{name} 的类型 {kind} 不支持查询最新版本")


def get_field(data: dict, path: str) -> str:
    """读取清单中的点分路径，例如 build.stable_tag；不存在时返回空串。"""
    node: object = data
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return ""
        node = node[part]
    return "" if node is None else str(node)


def record_build(data: dict, tag: str, prerelease: bool = False) -> None:
    commit = subprocess.run(
        ["git", "rev-parse", "--short=7", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    ).stdout.strip()
    build = data.setdefault("build", {})
    build.update(
        {
            "tag": tag,
            "built_at": now(),
            "commit": commit,
            "prerelease": bool(prerelease),
            "sources": {k: v["version"] for k, v in data["sources"].items()},
        }
    )
    if not prerelease:
        # stable_tag 只由正式发布推进，beta 复用的就是它指向的资产
        build["stable_tag"] = tag
    log(f"==> 记录构建版本 {tag}（commit {commit or 'unknown'}，prerelease={prerelease}）")


def main() -> int:
    parser = argparse.ArgumentParser(description="按 sources.json 获取远程依赖")
    parser.add_argument("--only", action="append", default=[], help="只处理指定条目（可重复）")
    parser.add_argument("--set", action="append", default=[], help="改写版本：name=version（可重复）")
    parser.add_argument("--latest", action="append", default=[], help="查询上游最新版本并回写（可重复）")
    parser.add_argument("--record-build", metavar="TAG", help="记录本次构建的版本号")
    parser.add_argument("--list", action="store_true", help="列出清单内容")
    parser.add_argument("--print-latest", metavar="NAME", help="打印指定条目上游最新版本（不下载）")
    parser.add_argument("--print-version", metavar="NAME", help="打印清单中指定条目的固定版本")
    parser.add_argument("--get", metavar="PATH", help="打印清单中的点分路径值，如 build.stable_tag")
    parser.add_argument("--prerelease", action="store_true", help="与 --record-build 配合：标记为 beta")
    parser.add_argument("--no-download", action="store_true", help="只更新清单，不下载文件")
    args = parser.parse_args()

    data = load()
    sources = data["sources"]

    if args.print_latest:
        if args.print_latest not in sources:
            raise SystemExit(f"清单中没有 {args.print_latest}")
        print(resolve_latest(args.print_latest, sources[args.print_latest]))
        return 0

    if args.print_version:
        if args.print_version not in sources:
            raise SystemExit(f"清单中没有 {args.print_version}")
        print(sources[args.print_version]["version"])
        return 0

    if args.get:
        print(get_field(data, args.get))
        return 0

    if args.list:
        for name, entry in sources.items():
            print(f"{name}\t{entry['type']}\t{entry['version']}")
        return 0

    changed = False

    for item in args.set:
        if "=" not in item:
            raise SystemExit(f"--set 需要 name=version 形式：{item}")
        name, version = item.split("=", 1)
        if name not in sources:
            raise SystemExit(f"清单中没有 {name}")
        sources[name]["version"] = version
        changed = True

    for name in args.latest:
        if name not in sources:
            raise SystemExit(f"清单中没有 {name}")
        sources[name]["version"] = resolve_latest(name, sources[name])
        log(f"==> {name}: 上游最新版本 {sources[name]['version']}")
        changed = True

    if args.record_build:
        record_build(data, args.record_build, prerelease=args.prerelease)
        changed = True

    if args.no_download:
        if changed:
            save(data)
            log("==> 清单已更新（未下载）")
        return 0

    targets = args.only or ([] if args.record_build else list(sources))
    unknown = [t for t in targets if t not in sources]
    if unknown:
        raise SystemExit(f"清单中没有：{', '.join(unknown)}")

    # 清单中的版本必须明确，不允许保留 latest
    vague = [f"{n}: {sources[n]['version']!r}" for n in targets if sources[n]["version"] in ("latest", "", None)]
    if vague:
        raise SystemExit(
            "以下条目版本未确定，请用 --latest <name> 或 --set <name>=<version> 固定：\n  "
            + "\n  ".join(vague)
        )

    for name in targets:
        entry = sources[name]
        kind = entry["type"]
        group(f"{name} @ {entry['version']}")
        try:
            if kind == "git":
                fetch_git(name, entry)
            elif kind == "github-release":
                fetch_github_release(name, entry)
            elif kind == "nixpkgs":
                check_nixpkgs(name, entry)
            else:
                raise SystemExit(f"{name}: 未知类型 {kind}")
        finally:
            endgroup()

    if changed:
        save(data)
        log(f"清单已更新：{MANIFEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
