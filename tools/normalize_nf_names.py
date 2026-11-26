#!/usr/bin/env python3
"""把 nerd-font-patcher 的产物名归一到 "<Family> NF" 口径。

font-patcher 的组名来自 PostScript 名（空格被吞），`--makegroups 6` 时还会额外产出
"NF Propo" / "NF Mono" 两组，于是 family 会变成 `PragmaSevkaMono NFM` 这种样子。
本脚本只保留 NF 组，并把 name 表与文件名改成与其它产物一致的口径，例如：

    family = "Pragma Sevka Mono"
    -> family (nameID 1/16)  = "Pragma Sevka Mono NF"
    -> full   (nameID 4)     = "Pragma Sevka Mono NF Regular"
    -> PS     (nameID 6)     = "PragmaSevka-Mono-NF-Regular"
    -> 文件名                = "PragmaSevka-Mono-NF-Regular.ttf"

用法：
    python3 tools/normalize_nf_names.py \
        --dir build/pragma-sevka-mono-NF/TTF --family "Pragma Sevka Mono"

幂等：重复运行结果不变（head.modified 不重写），便于复用旧产物后再跑一次。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

# patcher 各组在 Preferred Family 上的后缀（长的在前，避免前缀误匹配）
GROUP_SUFFIXES = (
    (" Nerd Font Propo", "propo"),
    (" Nerd Font Mono", "mono"),
    (" Nerd Font", "nf"),
)


def group_of(name16: str) -> str:
    """按 Preferred Family 判断 patcher 的命名组。"""
    for suffix, group in GROUP_SUFFIXES:
        if name16.endswith(suffix):
            return group
    # 已经被本脚本归一过的文件（幂等）
    if name16.endswith(" NF"):
        return "nf"
    return "unknown"


def read_name(font: TTFont, name_id: int) -> str:
    return font["name"].getDebugName(name_id) or ""


def set_name(font: TTFont, name_id: int, value: str) -> None:
    """同时写 Windows(3,1,0x409) 与 Mac(1,0,0) 两条记录。"""
    table = font["name"]
    table.removeNames(nameID=name_id)
    table.setName(value, name_id, 3, 1, 0x409)
    table.setName(value, name_id, 1, 0, 0)


def style_of(font: TTFont, path: Path) -> str:
    """取子族名（Regular / Italic / Bold / Bold Italic），取不到时退回文件名。"""
    style = read_name(font, 2).strip()
    if style:
        return style
    stem = path.stem
    for candidate in ("BoldItalic", "Bold Italic", "Bold", "Italic", "Regular"):
        if candidate.replace(" ", "") in stem:
            return candidate
    return "Regular"


def font_stem(family: str, base: str) -> str:
    """把 "Pragma Sevka Mono" + base "PragmaSevka" 变成 "PragmaSevka-Mono"。"""
    packed = family.replace(" ", "")
    if base and packed.startswith(base):
        feature = packed[len(base) :]
        return f"{base}-{feature}" if feature else base
    return packed


def normalize(path: Path, family: str, base: str) -> Path:
    """就地归一一个 ttf，返回新路径（不移动目录）。"""
    with TTFont(path, recalcTimestamp=False) as font:
        style = style_of(font, path)
        style_token = style.replace(" ", "")
        stem = font_stem(family, base)
        full_name = f"{family} NF {style}"
        ps_name = f"{stem}-NF-{style_token}"
        version = read_name(font, 5)

        set_name(font, 1, f"{family} NF")
        set_name(font, 2, style)
        if version:
            set_name(font, 3, f"{full_name};{version}")
        set_name(font, 4, full_name)
        set_name(font, 6, ps_name)
        set_name(font, 16, f"{family} NF")
        set_name(font, 17, style)

        target = path.with_name(f"{ps_name}.ttf")
        font.save(target)

    if target != path:
        path.unlink()
    print(f"  {path.name} -> {target.name}（family={family} NF）")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="归一 nerd-font-patcher 产物名到 <Family> NF")
    parser.add_argument("--dir", required=True, help="打补丁后的 TTF 目录")
    parser.add_argument("--family", required=True, help='build plan 的 family，例如 "Pragma Sevka Mono"')
    parser.add_argument("--base", default="PragmaSevka", help="文件名前缀，默认 PragmaSevka")
    args = parser.parse_args()

    ttf_dir = Path(args.dir)
    if not ttf_dir.is_dir():
        print(f"目录不存在：{ttf_dir}", file=sys.stderr)
        return 1

    fonts = sorted(ttf_dir.glob("*.ttf"))
    if not fonts:
        print(f"{ttf_dir} 下没有 ttf，nerd-font-patcher 可能没有产出", file=sys.stderr)
        return 1

    kept: list[Path] = []
    dropped: list[Path] = []
    for path in fonts:
        with TTFont(path, recalcTimestamp=False) as font:
            name16 = read_name(font, 16)
        group = group_of(name16)
        if group in ("nf", "unknown"):
            if group == "unknown":
                print(f"⚠️  无法识别命名组，按 NF 保留：{path.name}（{name16!r}）", file=sys.stderr)
            kept.append(path)
        else:
            dropped.append(path)

    if not kept:
        print("没有可用的 NF 组产物，检查 font-patcher 的 --makegroups 参数", file=sys.stderr)
        return 1

    for path in dropped:
        print(f"  删除非 NF 组：{path.name}")
        path.unlink()

    print(f"==> 归一 {len(kept)} 个 NF 产物（{args.family} NF）")
    for path in kept:
        normalize(path, args.family, args.base)

    return 0


if __name__ == "__main__":
    sys.exit(main())
