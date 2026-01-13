#!/usr/bin/env python3

from ast import arguments
import sys
import argparse

try:
    import fontforge
except ImportError:
    print(f"请安装 fontforge")
    sys.exits(1)

def get_font_stats_fontforge(font_path):
    try:
        font = fontforge.open(font_path)
        # 1. 获取字体中定义字形槽位总数
        total_glyphs = font.glyphs
        print(len(font))

        # 2. 获取所有字形的有效 Unicode 数
        all_count = 0
        encoded_count = 0
        for glyph in font.glyphs():
            all_count +=1
            if glyph.unicode > 0:
                encoded_count += 1

        print(f"字体名称: {font.fontname}")
        print(f"-----------")
        print(f"总字形数： {all_count}")
        print(f"有效字形数：  {encoded_count}")
        return encoded_count
    except Exception as e:
        print(f"读取失败: {e}")
if __name__ == '__main__':
    params = argparse.ArgumentParser()
    params.add_argument("font_path", help="use font path")
    args = params.parse_args()
    print(args.font_path)
    get_font_stats_fontforge(args.font_path)
