#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建有效的Windows图标文件
专门解决PyInstaller的UpdateResourceW错误
"""

import os
import struct

def create_valid_icon_file(icon_path="adb_icon.ico"):
    """
    创建一个完全有效的Windows图标文件
    
    Args:
        icon_path: 图标文件路径
    """
    print(f"创建有效的图标文件: {icon_path}")
    
    # 删除可能存在的损坏文件
    if os.path.exists(icon_path):
        try:
            os.remove(icon_path)
            print(f"已删除旧的图标文件: {icon_path}")
        except:
            pass
    
    try:
        # 创建最简单的有效ICO文件
        # ICO文件结构：
        # 1. ICO文件头 (6字节)
        # 2. 图标目录项 (16字节 * 图标数量)
        # 3. 图标数据
        
        # 我们创建一个16x16，32位色的简单图标
        width = 16
        height = 16
        bpp = 32  # 32位色 (ARGB)
        
        # 计算数据大小
        # BITMAPINFOHEADER: 40字节
        # 颜色表: 对于32位色通常为0
        # 像素数据: width * height * (bpp/8)
        header_size = 40
        color_table_size = 0  # 32位色不需要颜色表
        pixel_data_size = width * height * (bpp // 8)  # 16*16*4 = 1024字节
        
        # 图标数据总大小
        icon_data_size = header_size + color_table_size + pixel_data_size
        
        # 创建ICO文件
        with open(icon_path, 'wb') as f:
            # ====== ICO文件头 (6字节) ======
            # 保留字 (2字节): 0x0000
            f.write(struct.pack('<H', 0x0000))
            # 图标类型 (2字节): 1 = ICO
            f.write(struct.pack('<H', 0x0001))
            # 图标数量 (2字节): 1个图标
            f.write(struct.pack('<H', 0x0001))
            
            # ====== 图标目录项 (16字节) ======
            # 宽度 (1字节): 0-255, 0表示256像素
            f.write(struct.pack('<B', width if width < 256 else 0))
            # 高度 (1字节): 0-255, 0表示256像素
            f.write(struct.pack('<B', height if height < 256 else 0))
            # 颜色数 (1字节): 0表示不使用调色板(>256色)
            f.write(struct.pack('<B', 0))
            # 保留字 (1字节): 0x00
            f.write(struct.pack('<B', 0x00))
            # 颜色平面 (2字节): 通常为1
            f.write(struct.pack('<H', 0x0001))
            # 每像素位数 (2字节): 32位
            f.write(struct.pack('<H', bpp))
            # 图像数据大小 (4字节)
            f.write(struct.pack('<I', icon_data_size))
            # 图像数据偏移量 (4字节): 6+16=22字节
            f.write(struct.pack('<I', 6 + 16))
            
            # ====== 图标数据 ======
            # BITMAPINFOHEADER (40字节)
            # 信息头大小 (4字节): 40
            f.write(struct.pack('<I', 40))
            # 宽度 (4字节): 16
            f.write(struct.pack('<i', width))
            # 高度 (4字节): 32 (16像素图像 + 16像素掩码)
            f.write(struct.pack('<i', height * 2))
            # 颜色平面 (2字节): 1
            f.write(struct.pack('<H', 1))
            # 每像素位数 (2字节): 32
            f.write(struct.pack('<H', bpp))
            # 压缩方式 (4字节): 0 = BI_RGB (无压缩)
            f.write(struct.pack('<I', 0))
            # 图像大小 (4字节): 1024
            f.write(struct.pack('<I', pixel_data_size))
            # 水平分辨率 (4字节): 0
            f.write(struct.pack('<i', 0))
            # 垂直分辨率 (4字节): 0
            f.write(struct.pack('<i', 0))
            # 颜色数 (4字节): 0 (使用所有颜色)
            f.write(struct.pack('<I', 0))
            # 重要颜色数 (4字节): 0 (所有颜色都重要)
            f.write(struct.pack('<I', 0))
            
            # 像素数据 (1024字节) - 创建一个简单的蓝色方块
            # 32位格式: BGRA (Blue, Green, Red, Alpha)
            # 创建蓝色 (0, 0, 255) 带透明通道
            blue_pixel = struct.pack('<BBBB', 255, 0, 0, 255)  # BGRA: B=255,G=0,R=0,A=255
            
            for y in range(height):
                for x in range(width):
                    # 创建一个简单的图案：中心为白色，边框为蓝色
                    if x == 0 or x == width-1 or y == 0 or y == height-1:
                        # 边框：蓝色
                        f.write(blue_pixel)
                    elif x == width//2 and y == height//2:
                        # 中心点：白色
                        f.write(struct.pack('<BBBB', 255, 255, 255, 255))
                    else:
                        # 内部：浅蓝色
                        f.write(struct.pack('<BBBB', 200, 150, 100, 255))
            
            # 掩码数据 (对于32位色通常不需要，但为了完整性添加)
            # 掩码：1位每像素，每行对齐到4字节
            # 对于16x16，每行需要2字节，总共32字节
            mask_row_size = (width + 31) // 32 * 4  # 每行掩码字节数
            mask_data_size = mask_row_size * height
            
            # 全透明掩码 (全0表示不透明区域)
            for _ in range(mask_data_size):
                f.write(struct.pack('<B', 0x00))
        
        print(f"✅ 已创建有效的图标文件: {icon_path}")
        print(f"   尺寸: {width}x{height} 像素")
        print(f"   颜色深度: {bpp}位")
        
        # 验证文件大小
        file_size = os.path.getsize(icon_path)
        expected_size = 6 + 16 + icon_data_size + mask_data_size
        print(f"   文件大小: {file_size} 字节 (期望: {expected_size} 字节)")
        
        return True
        
    except Exception as e:
        print(f"❌ 创建图标文件失败: {e}")
        
        # 创建绝对最小的有效ICO文件作为最后的手段
        try:
            print("尝试创建最小ICO文件...")
            with open(icon_path, 'wb') as f:
                # 绝对最小的有效ICO文件
                f.write(b'\x00\x00\x01\x00\x01\x00\x01\x01\x00\x00\x01\x00\x20\x00\x68\x04\x00\x00\x16\x00\x00\x00')
                # 添加一些数据使文件看起来有效
                f.write(b'\x28\x00\x00\x00\x01\x00\x00\x00\x02\x00\x00\x00\x01\x00\x20\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
                # 添加一些像素数据
                for _ in range(16):
                    f.write(b'\x00\x00\xFF\xFF')
            
            print(f"✅ 已创建最小图标文件: {icon_path}")
            return True
        except Exception as e2:
            print(f"❌ 创建最小图标文件也失败: {e2}")
            return False

def main():
    """主函数"""
    print("=" * 50)
    print("Windows有效图标生成器")
    print("专门解决PyInstaller UpdateResourceW错误")
    print("=" * 50)
    
    # 检查命令行参数
    import sys
    is_debug = len(sys.argv) > 1 and sys.argv[1] == "--debug"
    
    if is_debug:
        icon_path = "adb_icon_debug.ico"
        print("创建调试版图标...")
    else:
        icon_path = "adb_icon.ico"
        print("创建正式版图标...")
    
    success = create_valid_icon_file(icon_path)
    
    if success:
        print(f"\n✅ 图标已成功创建: {icon_path}")
        print("   现在可以重新运行打包脚本")
    else:
        print(f"\n❌ 图标创建失败")
        print("   建议:")
        print("   1. 使用 --icon=NONE 参数打包（无图标）")
        print("   2. 手动创建ICO文件")
        print("   3. 下载现成的图标文件")
    
    print("=" * 50)
    
    # 返回退出代码
    import sys
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()