#!/usr/bin/env python3

from fontTools.ttLib import TTFont
import os


def get_font_info(src_file: str, is_verbose: bool):
    """检查每个 char 的 width， 同时获取字体某些信息
    """
    with TTFont(src_file) as font:
        result = dict()
        # 获取每个字全角的 单位数，常用的有 1000, 1024, 2048
        result['em'] = font['head'].unitsPerEm
        print("[head].unitsPerEm      = %d" % result['em'])

        # 行高相关参数
        result['winAscent'] = font["OS/2"].usWinAscent # windows 系统的上升部
        result['winDescent'] = font["OS/2"].usWinDescent # windows 系统的下降部
        result['ascent'] = font['hhea'].ascent # 水平排头的上升部
        result['descent'] = font['hhea'].descent # 水平排版头的下降部
        result['sTypoAscender'] = font['OS/2'].sTypoAscender # 拼写上部分
        result['sTypoDescender'] = font['OS/2'].sTypoDescender # 拼写下降部
        result['sTypoLineGap'] = font["OS/2"].sTypoLineGap # 拼写行间距
        result['lineGap'] = font['hhea'].lineGap # 默认行间距
        print("[OS/2].usWinAscent     = %d" % result['winAscent'])
        print("[OS/2].usWinDescent    = %d" % result['winDescent'])
        print("[hhea].ascent          = %d" % result['ascent'])
        print("[hhea].descent         = %d" % result['descent'])
        print("[OS/2].sTypoAscender   = %d" % result['sTypoAscender'])
        print("[OS/2].sTypoDescender  = %d" % result['sTypoDescender'])
        print("[OS/2].sTypoLineGap    = %d" % result['sTypoLineGap'])
        print("[hhea].lineGap         = %d" % result['lineGap'])

        # 水平相关参数
        result['advanceWidthMax'] = font['hhea'].advanceWidthMax # 字体中最大的字符宽度
        result['xAvgCharWidth'] = font['OS/2'].xAvgCharWidth # 所有字符的平均宽度
        result['underlinePosition'] = font['post'].underlinePosition # 下划线垂直位置
        result['underlineThickness'] = font['post'].underlineThickness # 下划线粗细
        result['isFixedPitch'] = font['post'].isFixedPitch # 等宽字体表示
        print("[hhea].advanceWidthMax = %d" % result['advanceWidthMax'])
        print("[OS/2].xAvgCharWidth   = %d" % result['xAvgCharWidth'])
        print("[post].underlinePosition  = %d" % result['underlinePosition'])
        print("[post].underlineThickness = %d" % result['underlineThickness'])
        print("[post].isFixedPitch    = %d" % result['isFixedPitch'])

        count = 0
        chars = {}
        for name in font.getGlyphOrder(): # 遍历字体的每个字形
            # glyph = font['glyf'][name] # 获取字形数据
            width, lsb = font['hmtx'][name] # 获取预进宽度(width)和左侧侧轴(lsb)

            chars[str(width)] = chars.get(str(width), 0) + 1
            count += 1
            if is_verbose:
                print("[%s], width: %s, lsp: %s" % (name, width, lsb)) # 打印每个字符的数据

        # 排序从少到多输出
        sorted_value = sorted(chars.items(), key=lambda x: x[1])
        result['chars'] = sorted_value
        result['count'] = count
        print("counts:     %d" % count)
        print("[char width]   [count]")
        for key, value in sorted_value:
            print("    %8s   %7s" % (key, value)) # 打印宽度和对应的字符数量
        return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("font_path", help="font path")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    if os.path.exists(args.font_path):
        get_font_info(args.font_path,args.verbose)
    else:
        print(f"{args.font_path} not exists.")
