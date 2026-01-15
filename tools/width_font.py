#!/usr/bin/env python3

import logging
from fontTools.ttLib import TTFont

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.INFO)


def change_char_width(src_font: str, width: list[int], out_path: str=""):
    """仅用来修改中文宽度，为什么中文是固定宽度？
    不建议动用英文部分 char
    if font_config.cn["narrow"]:
        change_char_width(font, [1200, 1000])
    """
    with TTFont(src_font) as font:
        font["hhea"].advanceWidthMax = width[-1]
        for name in font.getGlyphOrder():
            glyph = font["glyf"][name]
            gwidth, lsb = font["hmtx"][name]

            for i in range(0, len(width), 2):
                if gwidth == width[i]:
                    if glyph.numberOfContours == 0:
                        font["hmtx"][name] = (width[i + 1], lsb)
                    else:
                        font["hhea"].advanceWidthMax = width[i + 1]
                        delta = round((width[i + 1] - width[i]) / 2)
                        try:
                            glyph.coordinates.translate((delta, 0))
                            glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax = (
                                glyph.coordinates.calcIntBounds()
                            )
                            font["hmtx"][name] = (width[i + 1], lsb + delta)
                            logging.info(
                                "--> [%s], width: %s -> %s, lsb: %s -> %s"
                                % (name, gwidth, width[i + 1], lsb, lsb + delta)
                            )
                        except Exception as e:
                            logging.error(e)
        font["hhea"].advanceWidthMax = width[-1]
        if out_path != "":
            font.save(out_path)
        else:
            font.save(src_font)


def fix_width(
    src_file: str, width: int, line_position=0, line_thickness=0, advanceWidthMax=0
):
    """通过修改 AvgCharWidth 和 isFixedPitch，让程序能正确识别字体为 等宽字体，
    并且能以等宽字体来显示。
    推荐如果是合并字体，建议将 line_position, line_thickness, advanceWidthMax
    设置为合并字体前的英文字体属性一致。
    """
    with TTFont(src_file, recalcBBoxes=False) as src_font:
        post = src_font["post"].__dict__

        # 改为 1 后， vimr 等就可以识别该字体了。
        post["isFixedPitch"] = 1

        logging.info(
            "Fix xAvgCharWidth, %d -> %d" % (src_font["OS/2"].xAvgCharWidth, width)
        )
        # 设置为西文字体的宽度，设置后 emacs 就可以中英文对齐了
        src_font["OS/2"].xAvgCharWidth = width
        if advanceWidthMax != 0:
            old_advanceWidthMax = src_font["hhea"].advanceWidthMax
            src_font["hhea"].advanceWidthMax = advanceWidthMax
            logging.info(
                'fi font["hhea"].advabceWudtgMax, %d -> %d'
                % (old_advanceWidthMax, src_font["hhea"].advanceWidthMax)
            )
        if line_position != 0:
            old_position = post["underlinePosition"]
            post["underlinePosition"] = line_position
            logging.info(
                'fix post["underlinePosition"], %d -> %d'
                % (old_position, post["underlinePosition"])
            )

        if line_thickness != 0:
            old_thickness = post["underlineThickness"]
            post["underlineThickness"] = line_thickness
            logging.info(
                'fix post["underlineThickness"] %d -> %d'
                % (old_thickness, post["underlineThickness"])
            )

        src_font.save(src_file)


def update_metadata(
    src_font: str,
    family: str,
    style: str = "Regular",
    zfamily: str = "",
    out_path: str = "",
):
    style_dict = {
        "Regular": "常规",
        "Bold": "粗体",
        "Light": "细体",
        "Medium": "中等",
        "Italic": "斜体",
    }
    # 1. full name
    full_name = f"{family} {style}"
    ps_name = f"{family.replace(' ', '_')}-{style}"
    zfamily = zfamily or family
    full_name_zh = f"{zfamily} {style_dict[style]}"
    records = [
        # 英文
        (1, 0x409, family),
        (2, 0x409, style),
        (4, 0x409, full_name),
        (6, 0x409, ps_name),
        (16, 0x409, family),
        (17, 0x409, style),
        # 中文
        (1, 0x804, zfamily),
        (2, 0x804, style_dict[style]),
        (4, 0x804, full_name_zh),
        (16, 0x804, zfamily),
        (17, 0x804, style_dict[style]),
    ]
    with TTFont(src_font) as font:
        name_table = font["name"]
        # 清除旧记录并写入新记录
        # 注意：Windows 平台需要 PlatformID=3, EncodingID=1
        for name_id, lang_id, string in records:
            logging.info(
                f"为平台 3, id为1 设置字体 family: {string}, lang_id: {lang_id}, name_id: {name_id}"
            )
            name_table.setName(string, name_id, 3, 1, lang_id)
        # 设置 uniqueID
        version_text = None
        for record in name_table.names:
            if record.nameID == 5:
                # decode('utf-16-be') 处理 Windows 平台记录，或使用 toUnicode()
                version_text = record.toUnicode()
            if record.langID == 0x409: # 优先取英文
                break
            # 准备写入的数据 (NameID, PlatformID, EncodingID, LanguageID, String)
            # 0x409 为英语（美国）
        wws_records = [
            (21, 3, 1, 0x409, family),
            (22, 3, 1, 0x409, style)
        ]
        # 1. 如果需要中文兼容性，也可以添加 0x804 记录
        # wws_records.append((21, 3, 1, 0x804, "中文家族名"))
        # wws_records.append((22, 3, 1, 0x804, "中文样式名"))
        logging.info(f"WWS 属性更新为 {family} {style}")
        for name_id, plat_id, enc_id, lang_id, string in wws_records:
            name_table.setName(string, name_id, plat_id, enc_id, lang_id)
    
        # 3. 写入新的 UniqueID (覆盖现有记录)
        # 平台 3, 编码 1, 语言 0x409 (英语) 是最通用的
        logging.info("Change family uniqueID...")
        name_table.setName(f"{full_name} {version_text.split()[-1] if version_text else "0"}", 3, 3, 1, 0x409)
        
        # 3 . 同步 OS/2 表
        if "OS/2" in font:
            weight_map = {"Regular": 400, "Bold": 700, "Light": 300, "Medium": 500}
            font["OS/2"].usWeightClass = weight_map.get(style, 400)

            # 处理 Bold/Italic 标志位
            if style.lower() == "bold":
                font["OS/2"].fsSelection |= 1 << 5  # BOLD bit
                font["OS/2"].fsSelection &= ~(1 << 6)  # 取消 REGULAR bit
            elif style.lower() == "regular":
                font["OS/2"].fsSelection |= 1 << 6  # REGULAR bit
                font["OS/2"].fsSelection &= ~(1 << 5)

            # Bit 8 (0x100) 表示字体符合 WWS 命名规范
            # 根据规范，如果设置了 WWS 属性，建议在 OS/2 表中开启 Bit 8 (WWS bit)
            font['OS/2'].fsSelection |= (1 << 8)

        # 4. 同步 head 表 (macStyle)
        if "head" in font:
            if style.lower() == "bold":
                font["head"].macStyle |= 1 << 0
            else:
                font["head"].macStyle &= ~(1 << 0)

        r = out_path if out_path != "" else src_font
        font.save(r)
        logging.info(f"保存到 {r}...")

if __name__ == "__main__":
    import argparse
    import sys
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--font", help="Filename of a ttf font file.")
    parser.add_argument("-w", "--width", help="modify char width", nargs="+", type=int)
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

    parser.add_argument(
        "-s",
        "--style",
        default="Regular",
        type=str,
        help="Font style",
        choices=["Regular", "Bold", "Light", "Medium", "Italic"],
    )
    parser.add_argument("-n", "--name", type=str, help="Font family")
    parser.add_argument("-z", "--namezh", type=str, help="ZH Font family",default="")
    parser.add_argument("-o", "--outpath", type=str, help="out put path.", default="")

    args = parser.parse_args()
    if args.font is None or (not os.path.exists(os.path.expanduser(args.font))):
        logging.error("font %s is not exists." % args.font)
        sys.exit(-1)

    if args.width:
        len_width = len(args.width)
        if len_width == 1:
            fix_width(
                args.font,
                args.width[0],
                args.line_position,
                args.line_thickness,
                args.advanceWidthMax,
            )
        elif len_width % 2 == 0:
            change_char_width(args.font, args.width)
        else:
            logging.error("The length of the widht must be a multiple of 1 or 2.")
            sys.exit(-1)
    if args.name:
        update_metadata(args.font, args.name, args.style,args.namezh, args.outpath)
