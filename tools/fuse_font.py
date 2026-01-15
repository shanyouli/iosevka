#!/usr/bin/env python

import logging
import sys
import os
import argparse
import shutil
# import subprocess

logger = logging.getLogger(__name__)

try:
    import fontforge
except ImportError:
    logger.error("Please install fontforge modules.")
    sys.exit(-1)

def which(cmd: str) -> bool:
    return shutil.which(cmd) is not None

def run_ttfautohint(input_path, output_path):
    """调用系统命令 ttfautohint"""
    try:
        logger.info(f"[+] Running ttfautohint on {input_path}...")
        # subprocess.run(["ttfautohint", "-i", input_path, output_path], check-True)
        return (os.system(f"ttfautohint -i '{input_path}', '{output_path}'") == 0)
    except Exception as e:
        logger.error(f"[-] ttfautohint failed: {e}")
        return False

def fuse_fonts(merge_path, base_path,  family_name,  subfamily, output_path, hint=False):
    if not os.path.exists(merge_path):
        logger.error(f"merge font {merge_path} not exists.")
        sys.exit(-1)
    if not os.path.exists(path=base_path):
        logger.error(f"base font {base_path} not exists.")
        sys.exit(-1)

    logger.info(f"[+]Open {base_path}")
    font = fontforge.open(base_path)

    logger.info(f"[+]Merge fonts {merge_path}")
    font.mergeFonts(merge_path)

    # 1. 完善元数据：增加中文 LangID (0x804) 兼容性
    for langid in [0x409, 0x804]:
        logger.info(f"[+] {langid}: Set Prefereed Family: {family_name}")
        font.appendSFNTName(langid, 16, family_name) # Preferred Family
        logger.info(f"[+] {langid}: Set preferred subfamily: {subfamily}")
        font.appendSFNTName(langid, 17, subfamily)   # Preferred Subfamily

    # 设置核心名字
    font.fontname = f"{family_name.replace(" ", "_")}-{subfamily}"
    font.familyname = family_name
    font.fullname = f"{family_name} {subfamily}"
    font.weight = subfamily

       # 2. 核心数值同步 (解决你查看时属性不变的问题)
    weight_map = {"Regular": 400, "Bold": 700, "Light": 300, "Medium": 500}
    font.os2_weight = weight_map.get(subfamily, 400)
    # 3. 确保所有 SFNT 名称 ID 均被重写
    for langid in [0x409, 0x804]:
        font.appendSFNTName(langid, 1, family_name)
        font.appendSFNTName(langid, 2, subfamily)
        font.appendSFNTName(langid, 16, family_name)
        font.appendSFNTName(langid, 17, subfamily)

    # 标准化和优化, # 对应 SetFontOrder(2)
    logger.info("[+]Setting font order (Even-Odd)")
    if not font.is_quadratic:
        font.layers[font.activeLayer].is_quadratic = True
        font.is_quadratic = True

    font.selection.all()
    use_ttfhint = which("ttfautohint")
    # 由于在 autoIntStr 之前执行 round 会让生成字体体积增大。
    if hint and (not use_ttfhint):
        logger.info("[+] Step 0: auto hint")
        font.autoHint()
        font.autoInstr()

    logger.info("[+] Step 1: Canonical processing...")
    font.canonicalContours()
    font.canonicalStart()
    logger.info("[+] Step 2: Simplifying...")
    # 使用默认参数，或者显式指定 flags 避免 TypeError
    font.simplify()
    
    logger.info("[+] Step 3: Rounding to Int (Crucial for geometry math)")
    font.round()

    logger.info("[+] Step 4: Adding Extrema...")
    font.addExtrema()

    # logger.info("[+] Step 5: Remove Overlap (With Exception Handling)...")
    try:
        # 这个操作最吃内存和 CPU
        font.removeOverlap()
    except Exception as e:
        logger.warning(f"[-] RemoveOverlap failed for some glyphs: {e}")
    # 4. 微调 (最后进行)
    logger.info("[+] Step 6: Hinting...")
    font.autoHint()
    # font.autoInstr()

    logger.info(f"[+] Generating {output_path}...")
    if use_ttfhint and hint:
        temp_output = output_path + ".tmp.ttf"
        font.generate(temp_output)
        font.close()
        logger.info(f"Running ttfautohint ...")
        if run_ttfautohint(temp_output, output_path):
            logger.info(f"[+]清理临时文件 {temp_output}...")
            os.remove(temp_output)
        else:
            logger.error("[-] External hinting failed.")
            sys.exit(-1)
        
    else:
        font.generate(output_path)
        font.close()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    parse = argparse.ArgumentParser()
    parse.add_argument("merge_path", help="merge cn font")
    parse.add_argument("base_path", help="base font[en]")
    parse.add_argument("family_name", help="family name")
    parse.add_argument("subfamily", help="subfamily, Regular")
    parse.add_argument("output_path", help="output font path")
    parse.add_argument("--hint", help="use hint.", default=False, action="store_true")
    args = parse.parse_args()
    fuse_fonts(args.merge_path, args.base_path, args.family_name, args.subfamily, args.output_path)
