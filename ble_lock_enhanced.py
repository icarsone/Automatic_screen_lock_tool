import bluetooth
import time
import os
import platform
import subprocess
import ctypes
import json
import threading
import sys
import logging
from datetime import datetime

import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import tkinter as tk
from tkinter import messagebox, simpledialog

# 导入发送快捷键和通知所需的库
if platform.system() == "Windows":
    import ctypes
    from ctypes import wintypes
    import win32con
    import win32api
    import win32gui
    try:
        from plyer import notification
        PLYER_AVAILABLE = True
    except ImportError:
        PLYER_AVAILABLE = False
        print("plyer库未安装，将使用系统原生通知")

# 配置文件保存路径和全局变量
CONFIG_FILE = "device_config.json"
LOG_FILE = "bluetooth_monitor.log"
target_device = None  # 格式: (address, name)
running = True       # 控制监控线程退出
current_state = "未知"  # 当前状态（用于托盘菜单动态显示）
previous_state = "未知"  # 前一个状态，用于状态变化检测
tray_icon = None     # 全局托盘图标对象
notification_manager = None  # 通知管理器

# 默认配置
default_config = {
    "absence_threshold": 10,  # 默认10秒
    "scan_interval": 2,
    "enable_notifications": True,
    "enable_countdown": True,
    "log_level": "INFO"
}

# ================= 日志系统 =================

class LogManager:
    def __init__(self, log_file=LOG_FILE, level=logging.INFO):
        self.logger = logging.getLogger('BluetoothMonitor')
        self.logger.setLevel(level)
        
        # 避免重复添加handler
        if not self.logger.handlers:
            # 文件handler
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(level)
            
            # 控制台handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            
            # 格式化器
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def info(self, message):
        self.logger.info(message)
    
    def warning(self, message):
        self.logger.warning(message)
    
    def error(self, message):
        self.logger.error(message)
    
    def debug(self, message):
        self.logger.debug(message)

# 全局日志管理器
log_manager = LogManager()

# ================= 通知系统 =================

class NotificationManager:
    def __init__(self):
        self.system = platform.system()
        self.notifications_enabled = True
        
    def send_notification(self, title, message, level="info", duration=5):
        """发送系统通知"""
        if not self.notifications_enabled:
            return
            
        try:
            if PLYER_AVAILABLE:
                # 使用plyer库发送跨平台通知
                notification.notify(
                    title=title,
                    message=message,
                    app_name="蓝牙智能锁屏助手",
                    timeout=duration
                )
                log_manager.info(f"通知已发送: {title} - {message}")
            else:
                # 使用系统原生通知
                self._send_native_notification(title, message, level)
                
        except Exception as e:
            log_manager.error(f"发送通知失败: {e}")
    
    def _send_native_notification(self, title, message, level):
        """发送原生系统通知"""
        if self.system == "Windows":
            try:
                # Windows 10/11 Toast通知
                script = f'''
                Add-Type -AssemblyName System.Windows.Forms
                $notification = New-Object System.Windows.Forms.NotifyIcon
                $notification.Icon = [System.Drawing.SystemIcons]::Information
                $notification.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info
                $notification.BalloonTipText = "{message}"
                $notification.BalloonTipTitle = "{title}"
                $notification.Visible = $true
                $notification.ShowBalloonTip(5000)
                '''
                subprocess.run(["powershell", "-Command", script], 
                             capture_output=True, check=True)
            except Exception as e:
                log_manager.error(f"Windows通知发送失败: {e}")
                
        elif self.system == "Linux":
            try:
                subprocess.run(["notify-send", title, message], check=True)
            except Exception as e:
                log_manager.error(f"Linux通知发送失败: {e}")
                
        elif self.system == "Darwin":  # macOS
            try:
                script = f'''
                display notification "{message}" with title "{title}"
                '''
                subprocess.run(["osascript", "-e", script], check=True)
            except Exception as e:
                log_manager.error(f"macOS通知发送失败: {e}")
    
    def send_countdown_notification(self, seconds_remaining):
        """发送锁屏倒计时通知"""
        self.send_notification(
            "自动锁屏提醒", 
            f"设备离开，{seconds_remaining}秒后自动锁屏\n可通过托盘菜单取消",
            level="warning",
            duration=3
        )
    
    def send_device_status_notification(self, status, device_name=""):
        """发送设备状态变化通知"""
        if status == "设备在附近":
            self.send_notification(
                "设备已连接", 
                f"检测到设备 {device_name}，自动锁屏已启用",
                level="info"
            )
        elif status == "设备离开":
            self.send_notification(
                "设备已断开", 
                f"设备 {device_name} 已离开范围，开始监控锁屏条件",
                level="warning"
            )
    
    def toggle_notifications(self):
        """切换通知开关"""
        self.notifications_enabled = not self.notifications_enabled
        status = "已启用" if self.notifications_enabled else "已禁用"
        log_manager.info(f"通知功能{status}")
        return self.notifications_enabled

# ================= 图标管理器 =================

class IconManager:
    def __init__(self):
        self.icon_cache = {}
        
    def create_status_icon(self, status="unknown"):
        """根据状态创建不同颜色的托盘图标"""
        if status in self.icon_cache:
            return self.icon_cache[status]
            
        width, height = 64, 64
        image = Image.new('RGBA', (width, height), color=(255, 255, 255, 0))
        dc = ImageDraw.Draw(image)
        
        # 根据状态选择颜色
        color_map = {
            "设备在附近": "#00C851",     # 绿色
            "设备离开": "#FF4444",       # 红色
            "设备未携带": "#FFBB33",     # 黄色
            "未绑定": "#9E9E9E",        # 灰色
            "扫描中": "#2196F3",        # 蓝色
            "unknown": "#9E9E9E"       # 默认灰色
        }
        
        color = color_map.get(status, color_map["unknown"])
        
        # 绘制圆形图标
        dc.ellipse((8, 8, width - 8, height - 8), fill=color)
        
        # 添加状态指示器
        if status == "设备在附近":
            # 绿色图标中心添加白色勾号
            dc.line([(24, 32), (30, 38), (40, 28)], fill="white", width=4)
        elif status == "设备离开":
            # 红色图标中心添加白色X
            dc.line([(24, 24), (40, 40)], fill="white", width=4)
            dc.line([(40, 24), (24, 40)], fill="white", width=4)
        elif status == "扫描中":
            # 蓝色图标添加扫描波纹效果
            for i in range(3):
                radius = 15 + i * 8
                dc.ellipse((32 - radius, 32 - radius, 32 + radius, 32 + radius), 
                          outline="white", width=2)
        
        self.icon_cache[status] = image
        return image

# ================= 错误处理器 =================

class ErrorHandler:
    @staticmethod
    def show_error_dialog(title, message, suggestions=None):
        """显示友好的错误对话框"""
        try:
            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口
            root.attributes('-topmost', True)
            
            full_message = message
            if suggestions:
                full_message += f"\n\n建议解决方案：\n{suggestions}"
            
            messagebox.showerror(title, full_message)
            root.destroy()
        except Exception as e:
            log_manager.error(f"显示错误对话框失败: {e}")
    
    @staticmethod
    def show_warning_dialog(title, message):
        """显示警告对话框"""
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            messagebox.showwarning(title, message)
            root.destroy()
        except Exception as e:
            log_manager.error(f"显示警告对话框失败: {e}")
    
    @staticmethod
    def show_info_dialog(title, message):
        """显示信息对话框"""
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            
            messagebox.showinfo(title, message)
            root.destroy()
        except Exception as e:
            log_manager.error(f"显示信息对话框失败: {e}")

# ================= 快捷键相关函数 =================

def send_todesk_shortcut():
    """发送 Ctrl+Shift+Alt+D 快捷键关闭 ToDesk 连接"""
    system = platform.system()
    try:
        if system == "Windows":
            # 方法1: 使用keybd_event (更可靠的实现)
            user32 = ctypes.WinDLL('user32', use_last_error=True)
            
            # 确保没有其他按键被按下
            time.sleep(0.1)
            
            # 按下按键
            user32.keybd_event(win32con.VK_CONTROL, 0, 0, 0)  # Ctrl
            time.sleep(0.05)
            user32.keybd_event(win32con.VK_SHIFT, 0, 0, 0)    # Shift
            time.sleep(0.05)
            user32.keybd_event(win32con.VK_MENU, 0, 0, 0)     # Alt
            time.sleep(0.05)
            user32.keybd_event(0x44, 0, 0, 0)                 # D
            time.sleep(0.1)
            
            # 释放按键
            user32.keybd_event(0x44, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.05)
            user32.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.05)
            user32.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
            time.sleep(0.05)
            user32.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
            
            log_manager.info("已发送 Ctrl+Shift+Alt+D 快捷键关闭 ToDesk 连接")
            
            # 方法2: 尝试直接关闭ToDesk窗口
            try:
                todesk_hwnd = win32gui.FindWindow(None, "ToDesk")
                if todesk_hwnd != 0:
                    win32gui.PostMessage(todesk_hwnd, win32con.WM_CLOSE, 0, 0)
                    log_manager.info("已发送关闭消息到ToDesk窗口")
            except Exception as e:
                log_manager.warning(f"尝试关闭ToDesk窗口失败: {e}")
                
        elif system == "Linux":
            subprocess.run(["xdotool", "key", "ctrl+shift+alt+d"], check=True)
            log_manager.info("已发送 Ctrl+Shift+Alt+D 快捷键关闭 ToDesk 连接")
        elif system == "Darwin":  # macOS
            script = '''
            tell application "System Events"
                keystroke "d" using {control down, shift down, option down}
            end tell
            '''
            subprocess.run(["osascript", "-e", script], check=True)
            log_manager.info("已发送 Ctrl+Shift+Alt+D 快捷键关闭 ToDesk 连接")
            
    except Exception as e:
        log_manager.error(f"发送ToDesk快捷键失败: {e}")
        ErrorHandler.show_error_dialog(
            "快捷键发送失败",
            f"无法发送关闭ToDesk的快捷键: {e}",
            "请检查ToDesk是否正在运行，或手动关闭ToDesk连接"
        )

# ================= 蓝牙相关函数 =================

def lock_screen():
    """直接锁定屏幕，使用系统API而不是快捷键"""
    system = platform.system()
    try:
        if system == "Windows":
            # 方法1: 使用Windows API直接锁屏
            result = ctypes.windll.user32.LockWorkStation()
            if result:
                log_manager.info("已成功锁定屏幕")
                if notification_manager:
                    notification_manager.send_notification(
                        "屏幕已锁定",
                        "由于蓝牙设备离开，系统已自动锁屏"
                    )
            else:
                log_manager.error(f"锁屏失败，错误码: {ctypes.get_last_error()}")
                # 方法2: 如果API失败，尝试使用rundll32命令
                os.system('rundll32.exe user32.dll,LockWorkStation')
                log_manager.info("已使用rundll32命令锁定屏幕")
        
        elif system == "Linux":
            # 尝试多种Linux锁屏命令
            commands = [
                ["gnome-screensaver-command", "-l"],
                ["loginctl", "lock-session"],
                ["xdg-screensaver", "lock"]
            ]
            
            success = False
            for cmd in commands:
                try:
                    subprocess.run(cmd, check=True)
                    log_manager.info(f"已使用 {' '.join(cmd)} 锁定屏幕")
                    success = True
                    break
                except:
                    continue
                    
            if not success:
                raise Exception("所有锁屏命令均失败")
                
        elif system == "Darwin":
            os.system('/System/Library/CoreServices/Menu\\ Extras/User.menu/Contents/Resources/CGSession -suspend')
            log_manager.info("已在macOS上锁定屏幕")
            
    except Exception as e:
        log_manager.error(f"锁屏失败: {e}")
        ErrorHandler.show_error_dialog(
            "锁屏失败",
            f"无法锁定屏幕: {e}",
            "请检查系统权限设置，或手动锁定屏幕"
        )

def scan_devices(duration=4):
    """扫描蓝牙设备，增加错误处理和日志记录"""
    log_manager.info("开始扫描蓝牙设备...")
    try:
        devices = bluetooth.discover_devices(duration=duration, lookup_names=True)
        if not devices:
            log_manager.warning("没有发现蓝牙设备")
            return []
        else:
            log_manager.info(f"扫描到 {len(devices)} 个蓝牙设备")
            for i, (addr, name) in enumerate(devices):
                log_manager.debug(f"设备 {i}: 名称: {name}, 地址: {addr}")
        return devices
    except Exception as e:
        log_manager.error(f"蓝牙扫描失败: {e}")
        ErrorHandler.show_error_dialog(
            "蓝牙扫描失败",
            f"无法扫描蓝牙设备: {e}",
            "请检查：\n1. 蓝牙是否已开启\n2. 蓝牙驱动是否正常\n3. 是否有其他程序占用蓝牙"
        )
        return []

def save_config(device, config=None):
    if config is None:
        config = default_config.copy()
    
    config.update({
        "address": device[0],
        "name": device[1]
    })
    
    try:
        with open(CONFIG_FILE, "w", encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        log_manager.info(f"设备配置已保存: {device[1]} ({device[0]})")
    except Exception as e:
        log_manager.error(f"保存配置失败: {e}")
        ErrorHandler.show_error_dialog(
            "配置保存失败",
            f"无法保存设备配置: {e}",
            "请检查文件权限"
        )

def load_config():
    if not os.path.exists(CONFIG_FILE):
        log_manager.info("未找到配置文件，使用默认配置")
        return None, default_config
    
    try:
        with open(CONFIG_FILE, "r", encoding='utf-8') as f:
            config = json.load(f)
        
        # 提取设备信息
        device = (config.get("address"), config.get("name"))
        
        # 提取配置信息，如果不存在则使用默认值
        settings = default_config.copy()
        for key in settings:
            if key in config:
                settings[key] = config[key]
        
        log_manager.info(f"配置加载成功: {device[1]} ({device[0]})")
        return device, settings
        
    except Exception as e:
        log_manager.error(f"加载配置失败: {e}")
        ErrorHandler.show_error_dialog(
            "配置加载失败",
            f"无法加载设备配置: {e}",
            "将使用默认配置"
        )
        return None, default_config

def scan_for_target(target_addr, duration=4):
    """扫描指定目标设备"""
    try:
        devices = bluetooth.discover_devices(duration=duration, lookup_names=True)
        for addr, name in devices:
            if addr == target_addr:
                return True
        return False
    except Exception as e:
        log_manager.error(f"目标设备扫描失败: {e}")
        return False

# ================= 监控线程 =================

def monitor_device(absence_threshold=10, scan_interval=2):
    """
    增强的设备监控逻辑，包含通知和日志记录
    """
    global target_device, running, current_state, previous_state, notification_manager
    device_was_seen = False
    absence_time = 0
    screen_locked = False
    countdown_sent = False  # 倒计时通知是否已发送
    
    while running:
        if target_device is None:
            current_state = "未绑定"
            time.sleep(scan_interval)
            continue

        current_target = target_device
        log_manager.debug(f"扫描目标设备：{current_target[1]} ({current_target[0]})")
        
        # 更新托盘图标为扫描状态
        previous_state = current_state
        current_state = "扫描中"
        
        found = scan_for_target(current_target[0], duration=4)
        
        if found:
            # 设备在附近
            device_was_seen = True
            if absence_time > 0:
                log_manager.info(f"设备 {current_target[1]} 重新回到附近，重置计时器")
                screen_locked = False
                countdown_sent = False
            
            absence_time = 0
            current_state = "设备在附近"
            
            # 发送状态变化通知
            if previous_state != current_state and notification_manager:
                notification_manager.send_device_status_notification(
                    current_state, current_target[1]
                )
                
        else:
            # 设备不在附近
            if device_was_seen:
                absence_time += scan_interval
                current_state = "设备离开"
                log_manager.debug(f"设备暂时未检测到，累计缺失时间: {absence_time}秒")
                
                # 发送状态变化通知（仅在状态刚改变时）
                if previous_state != current_state and notification_manager:
                    notification_manager.send_device_status_notification(
                        current_state, current_target[1]
                    )
                
                # 倒计时通知（在阈值前5秒发送）
                if (absence_time >= absence_threshold - 5 and 
                    absence_time < absence_threshold and 
                    not countdown_sent and 
                    notification_manager):
                    remaining = absence_threshold - absence_time
                    notification_manager.send_countdown_notification(int(remaining))
                    countdown_sent = True
                
                # 锁屏条件检查
                if absence_time >= absence_threshold and not screen_locked:
                    log_manager.warning(f"设备 {current_target[1]} 长期缺失，执行锁屏操作")
                    
                    # 先发送快捷键关闭ToDesk连接
                    send_todesk_shortcut()
                    time.sleep(1)
                    
                    # 然后锁屏
                    lock_screen()
                    screen_locked = True
                    countdown_sent = False  # 重置倒计时标志
                    
            else:
                current_state = "设备未携带"
                if previous_state != current_state:
                    log_manager.info("设备未携带")
                
        time.sleep(scan_interval)
    
    log_manager.info("监控线程退出")

# ================= GUI 绑定界面增强 =================

def gui_binding_process():
    """
    增强的GUI绑定界面，添加了更好的错误处理和用户反馈
    """
    devices = []
    _, current_settings = load_config()

    def scan_and_update():
        nonlocal devices
        try:
            scan_button.config(text="扫描中...", state="disabled")
            root.update()
            
            devices = scan_devices(duration=4)
            listbox.delete(0, tk.END)
            
            if not devices:
                ErrorHandler.show_warning_dialog(
                    "未发现设备", 
                    "没有发现蓝牙设备，请检查：\n1. 蓝牙是否已开启\n2. 目标设备是否可被发现\n3. 距离是否过远"
                )
                listbox.insert(tk.END, "没有发现设备 - 请检查蓝牙状态")
            else:
                for i, (addr, name) in enumerate(devices):
                    listbox.insert(tk.END, f"{i}: 名称: {name}, 地址: {addr}")
                    
        except Exception as e:
            log_manager.error(f"设备扫描过程出错: {e}")
            ErrorHandler.show_error_dialog(
                "扫描错误",
                f"设备扫描过程中出现错误: {e}",
                "请尝试重新扫描或检查蓝牙设置"
            )
        finally:
            scan_button.config(text="重新扫描", state="normal")

    def confirm_selection():
        try:
            selection = listbox.curselection()
            if not selection:
                ErrorHandler.show_warning_dialog("提示", "请先选择一个设备")
                return
            
            if not devices:
                ErrorHandler.show_warning_dialog("提示", "没有可用设备，请先扫描")
                return
                
            index = selection[0]
            if index >= len(devices):
                ErrorHandler.show_error_dialog("错误", "选择的设备索引无效")
                return
                
            selected = devices[index]
            save_config(selected, current_settings)
            
            ErrorHandler.show_info_dialog(
                "绑定成功", 
                f"已成功绑定设备：\n名称: {selected[1]}\n地址: {selected[0]}"
            )
            
            global target_device
            target_device = selected
            log_manager.info(f"用户绑定了新设备: {selected[1]} ({selected[0]})")
            root.destroy()
            
        except Exception as e:
            log_manager.error(f"设备绑定过程出错: {e}")
            ErrorHandler.show_error_dialog(
                "绑定失败",
                f"设备绑定过程中出现错误: {e}",
                "请重试或联系技术支持"
            )

    try:
        root = tk.Tk()
        root.title("蓝牙设备绑定 - 智能锁屏助手")
        root.geometry("600x400")
        root.resizable(True, True)
        
        # 主标签
        title_label = tk.Label(root, text="选择要绑定的蓝牙设备", 
                              font=("Arial", 12, "bold"))
        title_label.pack(pady=10)
        
        # 设备列表
        list_frame = tk.Frame(root)
        list_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        
        listbox = tk.Listbox(list_frame, font=("Arial", 10))
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=listbox.yview)
        
        # 按钮框架
        button_frame = tk.Frame(root)
        button_frame.pack(pady=10)
        
        scan_button = tk.Button(button_frame, text="开始扫描", 
                               command=scan_and_update, width=12)
        scan_button.pack(side=tk.LEFT, padx=5)
        
        confirm_button = tk.Button(button_frame, text="确认绑定", 
                                  command=confirm_selection, width=12)
        confirm_button.pack(side=tk.LEFT, padx=5)
        
        cancel_button = tk.Button(button_frame, text="取消", 
                                 command=root.destroy, width=12)
        cancel_button.pack(side=tk.LEFT, padx=5)
        
        # 帮助信息
        help_label = tk.Label(root, 
                             text="提示：请确保目标设备蓝牙已开启且可被发现",
                             font=("Arial", 9), fg="gray")
        help_label.pack(pady=5)
        
        # 自动开始扫描
        scan_and_update()
        
        root.mainloop()
        
    except Exception as e:
        log_manager.error(f"GUI界面创建失败: {e}")
        ErrorHandler.show_error_dialog(
            "界面错误",
            f"无法创建绑定界面: {e}",
            "请检查系统图形界面支持"
        )

# ================= 系统托盘图标与菜单增强 =================

icon_manager = IconManager()

def get_current_state(_):
    """获取当前状态用于托盘菜单显示"""
    return f"当前状态: {current_state}"

def on_rebind(icon, item):
    """重新绑定设备"""
    log_manager.info("用户触发重新绑定设备")
    threading.Thread(target=gui_binding_process, daemon=True).start()

def on_exit(icon, item):
    """退出程序"""
    global running
    log_manager.info("用户退出程序")
    running = False
    icon.stop()
    sys.exit(0)

def on_toggle_notifications(icon, item):
    """切换通知开关"""
    global notification_manager
    if notification_manager:
        enabled = notification_manager.toggle_notifications()
        status = "启用" if enabled else "禁用"
        ErrorHandler.show_info_dialog("通知设置", f"通知功能已{status}")

def on_set_threshold(icon, item):
    """设置检测设备离开多久后锁屏的时间阈值"""
    global target_device
    _, current_settings = load_config()
    current_threshold = current_settings.get("absence_threshold", default_config["absence_threshold"])
    
    def show_dialog():
        try:
            dialog_root = tk.Tk()
            dialog_root.title("设置时间阈值")
            dialog_root.geometry("350x200")
            dialog_root.resizable(False, False)
            dialog_root.attributes('-topmost', True)
            
            # 主标签
            tk.Label(dialog_root, text="设置检测不到设备多久后锁屏", 
                    font=("Arial", 12, "bold")).pack(pady=10)
            
            # 输入框架
            input_frame = tk.Frame(dialog_root)
            input_frame.pack(pady=10)
            
            tk.Label(input_frame, text="时间（秒）:").pack(side=tk.LEFT)
            threshold_var = tk.StringVar(value=str(current_threshold))
            entry = tk.Entry(input_frame, textvariable=threshold_var, width=10)
            entry.pack(side=tk.LEFT, padx=5)
            entry.select_range(0, tk.END)
            entry.focus()
            
            # 提示信息
            tk.Label(dialog_root, text="建议设置范围：5-60秒", 
                    font=("Arial", 9), fg="gray").pack(pady=5)
            
            def on_confirm():
                try:
                    new_threshold = int(threshold_var.get())
                    if new_threshold < 1:
                        ErrorHandler.show_warning_dialog("警告", "时间阈值必须大于0秒")
                        return
                    if new_threshold > 300:
                        ErrorHandler.show_warning_dialog("警告", "时间阈值不能超过300秒")
                        return
                    
                    if new_threshold != current_threshold:
                        current_settings["absence_threshold"] = new_threshold
                        if target_device:
                            save_config(target_device, current_settings)
                            ErrorHandler.show_info_dialog(
                                "设置成功", 
                                f"时间阈值已更新为 {new_threshold} 秒"
                            )
                            log_manager.info(f"用户更新时间阈值为 {new_threshold} 秒")
                        else:
                            ErrorHandler.show_warning_dialog(
                                "提示", 
                                "请先绑定设备后再设置时间阈值"
                            )
                    dialog_root.destroy()
                except ValueError:
                    ErrorHandler.show_warning_dialog("警告", "请输入有效的数字")
            
            def on_cancel():
                dialog_root.destroy()
            
            # 按钮框架
            btn_frame = tk.Frame(dialog_root)
            btn_frame.pack(pady=15)
            
            tk.Button(btn_frame, text="确认", command=on_confirm, width=10).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="取消", command=on_cancel, width=10).pack(side=tk.LEFT, padx=5)
            
            dialog_root.bind('<Return>', lambda event: on_confirm())
            dialog_root.mainloop()
            
        except Exception as e:
            log_manager.error(f"阈值设置对话框错误: {e}")
            ErrorHandler.show_error_dialog("设置错误", f"无法打开设置对话框: {e}")
    
    threading.Thread(target=show_dialog, daemon=True).start()

def update_tray_icon():
    """更新托盘图标状态"""
    global tray_icon, current_state
    while running:
        if tray_icon is not None:
            try:
                # 更新图标
                new_icon = icon_manager.create_status_icon(current_state)
                tray_icon.icon = new_icon
                
                # 更新菜单
                tray_icon.update_menu()
            except Exception as e:
                log_manager.error(f"更新托盘图标失败: {e}")
        time.sleep(1)

def setup_tray():
    """设置增强的系统托盘"""
    global tray_icon, notification_manager
    
    # 初始化通知管理器
    notification_manager = NotificationManager()
    
    try:
        menu = (
            item(get_current_state, None, enabled=False),
            item("重新绑定设备", on_rebind),
            item("设置时间阈值", on_set_threshold),
            item("切换通知", on_toggle_notifications),
            item("退出", on_exit)
        )
        
        initial_icon = icon_manager.create_status_icon("unknown")
        tray_icon = pystray.Icon("BluetoothMonitor", initial_icon, "蓝牙智能锁屏助手", menu)
        
        # 启动图标更新线程
        threading.Thread(target=update_tray_icon, daemon=True).start()
        
        log_manager.info("系统托盘已启动")
        tray_icon.run()
        
    except Exception as e:
        log_manager.error(f"系统托盘启动失败: {e}")
        ErrorHandler.show_error_dialog(
            "托盘启动失败",
            f"无法启动系统托盘: {e}",
            "程序将以控制台模式运行"
        )

# ================= 主程序 =================

def main():
    """增强的主程序入口"""
    global target_device
    
    try:
        log_manager.info("=" * 50)
        log_manager.info("蓝牙智能锁屏助手启动")
        log_manager.info(f"系统平台: {platform.system()}")
        log_manager.info(f"Python版本: {sys.version}")
        
        # 加载配置
        target_device, settings = load_config()
        
        if target_device and target_device[0]:
            log_manager.info(f"已加载绑定设备: {target_device[1]} ({target_device[0]})")
            log_manager.info(f"当前设置: 检测不到设备 {settings['absence_threshold']} 秒后锁屏")
        else:
            log_manager.info("未找到绑定设备，启动设备绑定流程")
            gui_binding_process()
            # 重新加载配置
            target_device, settings = load_config()
            
            if not target_device or not target_device[0]:
                log_manager.warning("用户未完成设备绑定，程序退出")
                return
        
        # 启动设备监控线程
        log_manager.info("启动设备监控线程")
        monitor_thread = threading.Thread(
            target=monitor_device, 
            args=(settings["absence_threshold"], settings["scan_interval"]),
            daemon=True
        )
        monitor_thread.start()
        
        # 启动系统托盘
        log_manager.info("启动系统托盘界面")
        setup_tray()
        
    except KeyboardInterrupt:
        log_manager.info("用户中断程序")
    except Exception as e:
        log_manager.error(f"程序启动失败: {e}")
        ErrorHandler.show_error_dialog(
            "启动失败",
            f"程序启动过程中出现错误: {e}",
            "请检查系统环境和依赖库"
        )
    finally:
        global running
        running = False
        log_manager.info("程序退出")

if __name__ == "__main__":
    main()