#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版图标生成器
用于在批处理文件中安全地生成图标
"""

import os
import sys

def create_simple_icon(icon_path="adb_icon.ico", is_debug=False):
    """创建简单的图标文件
    
    Args:
        icon_path: 图标保存路径
        is_debug: 是否为调试版图标
    """
    debug_suffix = "调试版" if is_debug else "正式版"
    print(f"正在创建{debug_suffix}图标: {icon_path}")
    
    try:
        # 尝试导入PIL库
        try:
            from PIL import Image, ImageDraw, ImageFont
            HAS_PIL = True
        except ImportError:
            HAS_PIL = False
            print("警告: PIL库未安装，创建基础图标")
        
        if HAS_PIL:
            # 使用PIL创建高质量图标
            sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
            icon_images = []
            
            for width, height in sizes:
                # 根据是否为调试版选择颜色
                if is_debug:
                    # 调试版：绿色主题
                    bg_color = (76, 175, 80, 255)      # 绿色背景
                    rect_color = (56, 142, 60, 255)    # 深绿色矩形
                    text = 'ADB-D' if width >= 48 else 'D'
                else:
                    # 正式版：蓝色主题
                    bg_color = (33, 150, 243, 255)     # 蓝色背景
                    rect_color = (25, 118, 210, 255)   # 深蓝色矩形
                    text = 'ADB' if width >= 48 else 'A'
                
                image = Image.new('RGBA', (width, height), bg_color)
                draw = ImageDraw.Draw(image)
                
                # 绘制圆角矩形或矩形
                if hasattr(draw, 'rounded_rectangle'):
                    draw.rounded_rectangle([2, 2, width-2, height-2], radius=width//8, fill=rect_color)
                else:
                    # 旧版PIL不支持rounded_rectangle
                    draw.rectangle([2, 2, width-2, height-2], fill=rect_color)
                
                # 添加文字
                if width >= 32:
                    try:
                        font_size = width // 4
                        try:
                            font = ImageFont.truetype('C:\\Windows\\Fonts\\msyh.ttc', font_size)
                        except:
                            try:
                                font = ImageFont.truetype('C:\\Windows\\Fonts\\arial.ttf', font_size)
                            except:
                                font = ImageFont.load_default()
                        
                        # 使用textsize而不是textbbox以兼容旧版PIL
                        try:
                            bbox = draw.textbbox((0, 0), text, font=font)
                            text_width = bbox[2] - bbox[0]
                            text_height = bbox[3] - bbox[1]
                        except:
                            # 旧版PIL兼容
                            text_width, text_height = draw.textsize(text, font=font)
                        
                        x = (width - text_width) // 2
                        y = (height - text_height) // 2
                        
                        draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)
                    except Exception as e:
                        print(f"绘制文字失败: {e}")
                        # 简单备选
                        center_x, center_y = width // 2, height // 2
                        radius = width // 4
                        draw.ellipse([center_x-radius, center_y-radius, center_x+radius, center_y+radius], fill=(255, 255, 255, 255))
                
                icon_images.append(image)
            
            # 保存为ICO文件
            if icon_images:
                icon_images[0].save(
                    icon_path,
                    format='ICO',
                    sizes=sizes,
                    append_images=icon_images[1:] if len(icon_images) > 1 else None
                )
                print(f"✅ 高质量{debug_suffix}图标已生成: {icon_path}")
                return True
            else:
                print(f"❌ {debug_suffix}图标生成失败，使用基础图标")
                HAS_PIL = False  # 降级使用基础图标
        
        # 如果没有PIL或PIL生成失败，创建基础ICO文件
        if not HAS_PIL:
            # 根据是否为调试版选择基础图标的颜色模式
            if is_debug:
                # 调试版：绿色相间
                color_pattern1 = 0x5A  # 绿色模式1
                color_pattern2 = 0xA5  # 绿色模式2
            else:
                # 正式版：蓝色相间
                color_pattern1 = 0x55  # 蓝色模式1
                color_pattern2 = 0xAA  # 蓝色模式2
            
            # 创建最简单的最小ICO文件
            ico_data = bytes([
                # ICO文件头
                0x00, 0x00,  # 保留字
                0x01, 0x00,  # 图标类型
                0x01, 0x00,  # 图标数量
                # 图标目录项
                0x10, 0x10,  # 16x16
                0x00,        # 颜色数
                0x00,        # 保留
                0x01, 0x00,  # 颜色平面
                0x20, 0x00,  # 每像素位数
                0x00, 0x00, 0x00, 0x00,  # 图像数据大小
                0x16, 0x00, 0x00, 0x00,  # 图像数据偏移量
                # 图像数据 (16x16 单色简单图像)
                # BITMAPINFOHEADER
                0x28, 0x00, 0x00, 0x00,  # 信息头大小
                0x10, 0x00, 0x00, 0x00,  # 宽度
                0x20, 0x00, 0x00, 0x00,  # 高度 (包含掩码)
                0x01, 0x00,              # 平面数
                0x01, 0x00,              # 每像素位数
                0x00, 0x00, 0x00, 0x00,  # 压缩方式
                0x00, 0x00, 0x00, 0x00,  # 图像大小
                0x00, 0x00, 0x00, 0x00,  # 水平分辨率
                0x00, 0x00, 0x00, 0x00,  # 垂直分辨率
                0x00, 0x00, 0x00, 0x00,  # 颜色数
                0x00, 0x00, 0x00, 0x00,  # 重要颜色数
            ])
            
            # 添加一些简单的像素数据（根据模式选择颜色）
            # XOR掩码 (16行，每行16像素)
            for i in range(16):
                if i % 2 == 0:
                    ico_data += bytes([color_pattern1, color_pattern2])
                else:
                    ico_data += bytes([color_pattern2, color_pattern1])
            
            # AND掩码 (全透明)
            for i in range(16):
                ico_data += bytes([0xFF, 0xFF])
            
            with open(icon_path, 'wb') as f:
                f.write(ico_data)
            
            print(f"✅ 基础{debug_suffix}图标已生成: {icon_path}")
            return True
            
    except Exception as e:
        print(f"❌ {debug_suffix}图标生成失败: {e}")
        # 创建空文件作为占位符
        try:
            with open(icon_path, 'wb') as f:
                f.write(b'\x00\x00\x01\x00\x01\x00\x10\x10\x00\x00\x00\x00\x00\x00\x16\x00\x00\x00')
            print(f"⚠️ 已创建{debug_suffix}占位图标: {icon_path}")
            return True
        except:
            print(f"❌ 无法创建{debug_suffix}图标文件")
            return False
    
    return False

def main():
    """主函数"""
    print("=" * 40)
    print("ADB工具图标生成器 (简化版)")
    print("=" * 40)
    
    # 判断是否为调试版
    is_debug = len(sys.argv) > 1 and sys.argv[1] == "--debug"
    
    if is_debug:
        icon_path = "adb_icon_debug.ico"
        print("生成调试版图标...")
    else:
        icon_path = "adb_icon.ico"
        print("生成正式版图标...")
    
    success = create_simple_icon(icon_path, is_debug)
    
    if success:
        # 显示图标信息
        try:
            file_size = os.path.getsize(icon_path)
            print(f"图标大小: {file_size} 字节")
        except:
            pass
    
    print("=" * 40)
    
    # 返回退出代码
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()