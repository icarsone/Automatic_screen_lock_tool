#!/usr/bin/env python3
"""
蓝牙智能锁屏助手 - 依赖安装脚本
自动检测并安装所需的Python库
"""

import subprocess
import sys
import os
import platform

def run_command(cmd):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 6):
        print("❌ 错误: 需要Python 3.6或更高版本")
        print(f"   当前版本: {version.major}.{version.minor}.{version.micro}")
        return False
    else:
        print(f"✅ Python版本检查通过: {version.major}.{version.minor}.{version.micro}")
        return True

def install_package(package_name, description=""):
    """安装单个包"""
    print(f"📦 正在安装 {package_name}...")
    if description:
        print(f"   {description}")
    
    cmd = [sys.executable, "-m", "pip", "install", package_name]
    success, output = run_command(cmd)
    
    if success:
        print(f"✅ {package_name} 安装成功")
        return True
    else:
        print(f"❌ {package_name} 安装失败: {output}")
        return False

def check_bluetooth_support():
    """检查蓝牙支持"""
    try:
        # 动态导入以避免linter错误
        __import__('bluetooth')
        print("✅ 蓝牙库可用")
        return True
    except ImportError:
        print("❌ 蓝牙库不可用，尝试安装...")
        
        system = platform.system().lower()
        if system == "linux":
            print("💡 在Linux上，可能需要安装系统级蓝牙开发包:")
            print("   Ubuntu/Debian: sudo apt-get install libbluetooth-dev")
            print("   CentOS/RHEL: sudo yum install bluez-libs-devel")
            print("   Fedora: sudo dnf install bluez-libs-devel")
        elif system == "windows":
            print("💡 在Windows上，确保蓝牙服务已启用")
        
        return install_package("bluetooth")

def main():
    """主安装流程"""
    print("=" * 60)
    print("🔧 蓝牙智能锁屏助手 - 依赖安装向导")
    print("=" * 60)
    
    # 检查Python版本
    if not check_python_version():
        return False
    
    print("\n📋 开始安装依赖包...")
    
    # 定义要安装的包
    packages = [
        ("pystray>=0.19.4", "系统托盘图标支持"),
        ("Pillow>=8.0.0", "图像处理库"),
        ("plyer>=2.0", "跨平台通知支持")
    ]
    
    # Windows特定包
    if platform.system().lower() == "windows":
        packages.append(("pywin32>=227", "Windows API支持"))
    
    # 安装包
    failed_packages = []
    for package, description in packages:
        if not install_package(package, description):
            failed_packages.append(package)
    
    # 检查蓝牙支持
    print("\n🔵 检查蓝牙支持...")
    if not check_bluetooth_support():
        failed_packages.append("bluetooth")
    
    # 总结
    print("\n" + "=" * 60)
    if failed_packages:
        print("⚠️  安装完成，但有些包安装失败:")
        for package in failed_packages:
            print(f"   ❌ {package}")
        print("\n💡 请手动安装失败的包或检查系统环境")
        return False
    else:
        print("🎉 所有依赖安装成功！")
        print("\n🚀 现在可以运行程序:")
        print("   python ble_lock_enhanced.py")
        return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n❌ 安装被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 安装过程中出现错误: {e}")
        sys.exit(1)