#!/usr/bin/env python3
"""
蓝牙智能锁屏助手 - 功能测试脚本
测试新增的高优先级功能
"""

import sys
import time
import os

def test_notification_system():
    """测试通知系统"""
    print("🔔 测试通知系统...")
    
    try:
        # 导入增强版本的通知管理器
        sys.path.append('.')
        from ble_lock_enhanced import NotificationManager
        
        notification_manager = NotificationManager()
        
        # 测试基本通知
        notification_manager.send_notification(
            "测试通知", 
            "这是一个测试通知消息",
            level="info"
        )
        
        time.sleep(2)
        
        # 测试设备状态通知
        notification_manager.send_device_status_notification("设备在附近", "测试设备")
        
        time.sleep(2)
        
        # 测试倒计时通知
        notification_manager.send_countdown_notification(5)
        
        print("✅ 通知系统测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 通知系统测试失败: {e}")
        return False

def test_icon_manager():
    """测试图标管理器"""
    print("🎨 测试图标管理器...")
    
    try:
        from ble_lock_enhanced import IconManager
        
        icon_manager = IconManager()
        
        # 测试不同状态的图标生成
        statuses = ["设备在附近", "设备离开", "设备未携带", "扫描中", "未绑定"]
        
        for status in statuses:
            icon = icon_manager.create_status_icon(status)
            if icon:
                print(f"✅ {status} 图标生成成功")
            else:
                print(f"❌ {status} 图标生成失败")
        
        print("✅ 图标管理器测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 图标管理器测试失败: {e}")
        return False

def test_log_manager():
    """测试日志管理器"""
    print("📝 测试日志管理器...")
    
    try:
        from ble_lock_enhanced import LogManager
        
        # 创建测试日志管理器
        test_log = LogManager("test_bluetooth_monitor.log")
        
        # 测试不同级别的日志
        test_log.info("这是一个信息级别的测试日志")
        test_log.warning("这是一个警告级别的测试日志")
        test_log.error("这是一个错误级别的测试日志")
        test_log.debug("这是一个调试级别的测试日志")
        
        # 检查日志文件是否创建
        if os.path.exists("test_bluetooth_monitor.log"):
            print("✅ 日志文件创建成功")
            with open("test_bluetooth_monitor.log", "r", encoding="utf-8") as f:
                content = f.read()
                if "测试日志" in content:
                    print("✅ 日志内容写入成功")
                else:
                    print("❌ 日志内容写入失败")
            
            # 清理测试文件
            os.remove("test_bluetooth_monitor.log")
        else:
            print("❌ 日志文件创建失败")
            return False
        
        print("✅ 日志管理器测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 日志管理器测试失败: {e}")
        return False

def test_error_handler():
    """测试错误处理器"""
    print("💬 测试错误处理器...")
    
    try:
        from ble_lock_enhanced import ErrorHandler
        
        print("⚠️  即将弹出测试对话框，请关闭它们以继续测试...")
        time.sleep(2)
        
        # 测试信息对话框
        ErrorHandler.show_info_dialog("测试信息", "这是一个测试信息对话框")
        
        time.sleep(1)
        
        # 测试警告对话框
        ErrorHandler.show_warning_dialog("测试警告", "这是一个测试警告对话框")
        
        time.sleep(1)
        
        # 测试错误对话框
        ErrorHandler.show_error_dialog(
            "测试错误", 
            "这是一个测试错误对话框",
            "这是解决方案建议"
        )
        
        print("✅ 错误处理器测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 错误处理器测试失败: {e}")
        return False

def test_config_functions():
    """测试配置功能"""
    print("⚙️ 测试配置功能...")
    
    try:
        from ble_lock_enhanced import save_config, load_config
        
        # 测试保存配置
        test_device = ("AA:BB:CC:DD:EE:FF", "测试设备")
        test_config = {
            "absence_threshold": 15,
            "scan_interval": 3,
            "enable_notifications": True,
            "enable_countdown": True,
            "log_level": "DEBUG"
        }
        
        save_config(test_device, test_config)
        
        # 测试加载配置
        loaded_device, loaded_config = load_config()
        
        if loaded_device == test_device:
            print("✅ 设备配置保存/加载成功")
        else:
            print("❌ 设备配置保存/加载失败")
            return False
        
        if loaded_config["absence_threshold"] == 15:
            print("✅ 配置参数保存/加载成功")
        else:
            print("❌ 配置参数保存/加载失败")
            return False
        
        print("✅ 配置功能测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 配置功能测试失败: {e}")
        return False

def main():
    """主测试流程"""
    print("🧪 蓝牙智能锁屏助手 - 功能测试")
    print("=" * 60)
    print("正在测试新增的高优先级功能...\n")
    
    test_results = []
    
    # 执行各项测试
    test_results.append(("通知系统", test_notification_system()))
    test_results.append(("图标管理器", test_icon_manager()))
    test_results.append(("日志管理器", test_log_manager()))
    test_results.append(("错误处理器", test_error_handler()))
    test_results.append(("配置功能", test_config_functions()))
    
    # 测试结果汇总
    print("\n" + "=" * 60)
    print("📊 测试结果汇总:")
    print("-" * 60)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:<15} {status}")
        if result:
            passed += 1
    
    print("-" * 60)
    print(f"总测试数: {total}")
    print(f"通过数量: {passed}")
    print(f"失败数量: {total - passed}")
    print(f"通过率: {passed/total*100:.1f}%")
    
    if passed == total:
        print("\n🎉 所有功能测试通过！")
        print("✅ 高优先级功能实现成功，可以正常使用增强版程序")
    else:
        print("\n⚠️  部分功能测试失败")
        print("❗ 请检查依赖安装和系统环境")
    
    print("\n💡 提示: 运行 `python start.py` 启动完整程序")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        sys.exit(1)