#!/usr/bin/env python3
import logging
import sys
import subprocess
import os
import shutil
from fontTools.ttLib import TTFont
parent_dir = os.path.dirname(__file__)
sys.path.append(parent_dir)
from width_font import change_char_width, fix_width, update_metadata # noqa: E402

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.INFO)

def count_glyphs(font_path: str) -> int:
    """获取字体的 glyph 数量"""
    with TTFont(font_path) as font:
        # 获取所有字符 （Glyph）
        glyph_count = len(font.getGlyphOrder())
        # 获取实际映射了 Unicode 编码的字符数量
        bestCmap = font.getBestCmap()

        unicode_count = len(bestCmap.items()) if bestCmap else 0

        logging.info(f"{font_path}总 Glyph 数量：{glyph_count}")
        logging.info(f"{font_path}带有 Unicode 编码的字符数量：{unicode_count}")
        return glyph_count

def merge_font(base_font: str, zh_fonts: list[str], family: str, style: str, output_path: str):
    base_font_count = count_glyphs(base_font)
    zh_font = None
    for i in zh_fonts:
        if count_glyphs(i) + base_font_count < 65534:
            zh_font = i
            break
    else:
        logging.error(f"{base_font} and {zh_fonts} 的字符数超过 65534, 建议不要合并")
        sys.exit(-1)
    try:
        logging.info(f"merge {base_font} and {zh_font}")
        if sys.platform == "darwin":
            try:
                subprocess.run([
                    "/Applications/FontForge.app/Contents/MacOS/FFPython",
                    os.path.join(parent_dir, "fuse_font.py"),
                    zh_font,
                    base_font,
                    family,
                    style,
                    output_path
                ], check=True)
            except subprocess.SubprocessError as e:
                logging.error(e)
                sys.exit(-1)
        else:
            from fuse_font import fuse_fonts
            fuse_fonts(zh_font,base_font, family, style, output_path)
    except Exception as e:
        logging.error(e)
        sys.exit(-1)

def run_ttfautohint(input_path: str, output_path: str=""):
    """使用 ttfautohint 命令将字体进行 autohint 化"""
    if not shutil.which("ttfautohint"):
        logging.error("Please install ttfautohint")
        sys.exit(-1)
    try:
        output_path = (input_path + "-temp.ttf") if output_path == "" else output_path
        subprocess.run(["ttfautohint", "-i" "-s","-c","-n", "-f" "latn", input_path, output_path], check=True)
        if output_path.endswith("temp.ttf"):
            os.rename(output_path, input_path)
    except subprocess.SubprocessError as e:
        logging.error(e)
        sys.exit(-1)

if __name__ == "__main__":
    # 使用方法：
    # py run.py -b base-font -z
    # python run.py -b base-font -z zfont1 zfont2 \
    #   -w 500 525 1000 1025 -x 525  -l -50 -t 50 -a 1050 \
    #   -f mytest -s Regular -o output.ttf --hint
    
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--basefont", help="基础英文字体")
    parser.add_argument("-z", "--zhfonts", help="中文字体", nargs="+")

    parser.add_argument("-o", "--outpath", help="merge 字体路径")

    parser.add_argument("-f", "--family", help="合成后字体名称")
    parser.add_argument(
        "-s",
        "--style",
        default="Regular",
        type=str,
        help="Font style",
        choices=["Regular", "Bold", "Light", "Medium", "Italic"],
    )
    parser.add_argument("-w", "--width", help="modify char width", nargs="+", type=int)

    # fix
    parser.add_argument('-x', '--avgwidth', type=int, help='Fix ["OS/2"].xAvgCharWidth')
    parser.add_argument(
        "-l",
        "--line-position",
        default=0,
        type=int,
        help='Fix ["OS/2"].underlinePosition, default is 0, underlinePosition is not modified.',
    )
    parser.add_argument(
        "-t",
        "--line-thickness",
        default=0,
        type=int,
        help='Fix ["OS/2"].underlineThickness, default is 0, underlineThickness is not modified.',
    )
    parser.add_argument(
        "-a",
        "--advanceWidthMax",
        default=0,
        type=int,
        help='Fix ["hhea"].advanceWidthMax, default is 0, advanceWidthMax is not modified.',
    )

    parser.add_argument("-n","--zh-family", type=str, help="ZH Font family",default="")

    parser.add_argument("--hint",help="auto hint", action="store_true")

    args = parser.parse_args()

    if args.basefont is None and args.zhfonts is None:
        if args.outpath and os.path.exists(os.path.expanduser(args.outpath)):
            pass
        else:
            logging.error("如果你需要合并字体，请确保basefont 和zhfonts 存在，否则确保outpath 存在。")
            sys.exit(-1)
    else:
        if not os.path.exists(os.path.expanduser(args.basefont)):
            logging.error("font %s is not exists." % args.font)
            sys.exit(-1)

        for i in args.zhfonts:
            if os.path.exists(os.path.expanduser(i)):
                continue
            else:
                logging.error("font %s is not exists." % i)
                sys.exit(-1)
        logging.info("[+] 开始合成字体......")
        merge_font(args.basefont, args.zhfonts, args.family, args.style, args.outpath)

    if args.width and len(args.width) % 2 == 0:
        logging.info("[+] 开始修改字体宽度......")
        change_char_width(args.outpath, args.width)

    if args.avgwidth:
        logging.info("[+] 开始修正让字体等宽......")
        fix_width(args.outpath, args.avgwidth, args.line_position, args.line_thickness, args.advanceWidthMax)

    if args.family:
        logging.info("update font meta")
        update_metadata(args.outpath, args.family, args.style, args.zh_family)
    if args.hint:
        logging.info("%s auto hint." % args.outpath)
        run_ttfautohint(args.outpath)
