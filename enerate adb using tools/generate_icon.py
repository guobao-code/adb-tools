#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADB工具图标生成器
自动生成适用于ADB工具的图标文件
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_adb_icon(icon_path="adb_icon.ico"):
    """
    创建ADB工具图标
    
    Args:
        icon_path: 图标保存路径
    """
    print(f"正在生成图标: {icon_path}")
    
    # 定义不同的图标尺寸（Windows图标需要多个尺寸）
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    
    # 创建图标图像列表
    icon_images = []
    
    for size in sizes:
        width, height = size
        
        # 创建新图像
        image = Image.new('RGBA', (width, height), (33, 150, 243, 255))  # 蓝色背景
        draw = ImageDraw.Draw(image)
        
        # 绘制圆角矩形背景
        draw.rounded_rectangle(
            [2, 2, width-2, height-2], 
            radius=width//8,
            fill=(25, 118, 210, 255)  # 深蓝色
        )
        
        try:
            # 尝试使用系统字体
            if width >= 32:
                font_size = width // 4
                try:
                    # Windows系统字体
                    font = ImageFont.truetype("C:\\Windows\\Fonts\\msyh.ttc", font_size)
                except:
                    try:
                        # 备选字体
                        font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", font_size)
                    except:
                        # 默认字体
                        font = ImageFont.load_default()
                
                # 绘制文字
                text = "ADB" if width >= 48 else "A"
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x = (width - text_width) // 2
                y = (height - text_height) // 2
                
                draw.text(
                    (x, y),
                    text,
                    fill=(255, 255, 255, 255),  # 白色文字
                    font=font
                )
            else:
                # 小图标上绘制简单的USB图标
                draw.line([width//4, height//2, width*3//4, height//2], 
                         fill=(255, 255, 255, 255), width=width//8)
                draw.rectangle([width//4, height//3, width//2, height*2//3], 
                              fill=(255, 193, 7, 255))
                draw.rectangle([width//2, height//3, width*3//4, height*2//3], 
                              fill=(76, 175, 80, 255))
                
        except Exception as e:
            print(f"绘制图标时出错 (尺寸 {size}): {e}")
            # 简单备选：绘制圆形
            center_x, center_y = width // 2, height // 2
            radius = width // 4
            draw.ellipse(
                [center_x - radius, center_y - radius, 
                 center_x + radius, center_y + radius],
                fill=(255, 193, 7, 255)  # 黄色
            )
        
        icon_images.append(image)
    
    # 保存为ICO格式
    if icon_images:
        # 保存主要尺寸的图标
        icon_images[0].save(
            icon_path,
            format='ICO',
            sizes=sizes,
            append_images=icon_images[1:] if len(icon_images) > 1 else None
        )
        print(f"✅ 图标已生成: {icon_path}")
        print(f"   尺寸: {sizes}")
        
        # 同时保存为PNG格式用于预览
        png_path = icon_path.replace('.ico', '_256.png')
        icon_images[-1].save(png_path, format='PNG')
        print(f"   预览: {png_path}")
    else:
        print("❌ 图标生成失败")

def check_icon_exists(icon_path="adb_icon.ico"):
    """检查图标文件是否存在"""
    return os.path.exists(icon_path)

def main():
    """主函数"""
    print("=" * 50)
    print("ADB工具图标生成器")
    print("=" * 50)
    
    icon_path = "adb_icon.ico"
    
    if check_icon_exists(icon_path):
        print(f"已存在图标文件: {icon_path}")
        response = input("是否重新生成? (y/n): ").strip().lower()
        if response != 'y':
            print("使用现有图标")
            return
    
    try:
        # 尝试导入PIL
        create_adb_icon(icon_path)
        
        # 显示图标信息
        print("\n图标信息:")
        print(f"文件路径: {os.path.abspath(icon_path)}")
        print(f"文件大小: {os.path.getsize(icon_path) / 1024:.1f} KB")
        
    except ImportError as e:
        print(f"\n❌ 缺少依赖库: {e}")
        print("\n安装依赖:")
        print("pip install pillow")
        
        # 创建简单的备选图标（不使用PIL）
        print("\n使用简单方法创建图标...")
        try:
            # 如果PIL不可用，创建一个简单的图标文件头
            # 注意：这不是真正的ICO文件，但可以让PyInstaller不报错
            with open(icon_path, 'wb') as f:
                # 写入一个最小的ICO文件头
                f.write(b'\x00\x00')  # 保留字
                f.write(b'\x01\x00')  # 图标类型
                f.write(b'\x01\x00')  # 图标数量
                f.write(b'\x10\x10')  # 16x16
                f.write(b'\x00')      # 颜色数
                f.write(b'\x00')      # 保留
                f.write(b'\x01\x00')  # 颜色平面
                f.write(b'\x20\x00')  # 每像素位数
                f.write(b'\x00\x00\x00\x00')  # 图像数据大小
                f.write(b'\x16\x00\x00\x00')  # 图像数据偏移量
                # 简单的16x16单色图像数据
                f.write(b'\x28\x00\x00\x00')  # 信息头大小
                f.write(b'\x10\x00\x00\x00')  # 宽度
                f.write(b'\x20\x00\x00\x00')  # 高度（包含掩码）
                f.write(b'\x01\x00')          # 平面数
                f.write(b'\x01\x00')          # 每像素位数
                f.write(b'\x00\x00\x00\x00')  # 压缩方式
                f.write(b'\x00\x00\x00\x00')  # 图像大小
                f.write(b'\x00\x00\x00\x00')  # 水平分辨率
                f.write(b'\x00\x00\x00\x00')  # 垂直分辨率
                f.write(b'\x00\x00\x00\x00')  # 颜色数
                f.write(b'\x00\x00\x00\x00')  # 重要颜色数
                # XOR掩码（蓝色方块）
                for _ in range(16):
                    f.write(b'\x55\xAA')  # 蓝白相间
                # AND掩码
                f.write(b'\xFF\xFF' * 16)  # 全透明
                
            print(f"✅ 已创建基础图标文件: {icon_path}")
            print("   注意：这是一个简单图标，如需更好效果请安装PIL")
            print("   运行: pip install pillow")
            
        except Exception as e2:
            print(f"创建基础图标失败: {e2}")
            print("\n解决方案:")
            print("1. 手动安装图标库: pip install pillow")
            print("2. 或手动创建图标文件，命名为 adb_icon.ico")
            print("3. 或从网上下载ADB相关的图标")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    main()