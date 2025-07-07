#!/usr/bin/env python3
"""
蓝牙智能锁屏助手 - 启动脚本
自动检查依赖并启动增强版程序
"""

import sys
import os
import subprocess

def check_dependencies():
    """检查必要的依赖库是否已安装"""
    required_modules = [
        'bluetooth',
        'pystray', 
        'PIL',
        'plyer'
    ]
    
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    return missing_modules

def main():
    """主启动流程"""
    print("🔧 蓝牙智能锁屏助手 - 启动检查")
    print("=" * 50)
    
    # 检查依赖
    missing = check_dependencies()
    
    if missing:
        print(f"❌ 缺少以下依赖库: {', '.join(missing)}")
        print("\n🔧 自动安装依赖...")
        
        # 运行依赖安装脚本
        try:
            subprocess.run([sys.executable, "install_dependencies.py"], check=True)
            print("\n✅ 依赖安装完成，重新检查...")
            
            # 重新检查
            missing = check_dependencies()
            if missing:
                print(f"❌ 仍有依赖缺失: {', '.join(missing)}")
                print("请手动安装缺失的库")
                return False
        except subprocess.CalledProcessError:
            print("❌ 自动安装失败，请手动安装依赖")
            return False
        except FileNotFoundError:
            print("❌ 找不到安装脚本，请手动安装依赖:")
            print("   pip install -r requirements.txt")
            return False
    
    print("✅ 所有依赖检查通过")
    print("\n🚀 启动蓝牙智能锁屏助手...")
    
    # 启动增强版程序
    try:
        import ble_lock_enhanced
        ble_lock_enhanced.main()
    except ImportError:
        print("❌ 找不到增强版程序文件")
        return False
    except Exception as e:
        print(f"❌ 程序启动失败: {e}")
        return False
    
    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 程序被用户中断")
    except Exception as e:
        print(f"\n❌ 启动过程中出现错误: {e}")
        sys.exit(1)