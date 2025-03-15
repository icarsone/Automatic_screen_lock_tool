import bluetooth
import time
import os
import platform
import subprocess
import ctypes
import json
import threading
import sys

import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import tkinter as tk
from tkinter import messagebox, simpledialog

# 导入发送快捷键所需的库
if platform.system() == "Windows":
    import ctypes
    from ctypes import wintypes
    import win32con
    import win32api
    import win32gui

# 配置文件保存路径和全局变量
CONFIG_FILE = "device_config.json"
target_device = None  # 格式: (address, name)
running = True       # 控制监控线程退出
current_state = "未知"  # 当前状态（用于托盘菜单动态显示）
tray_icon = None     # 全局托盘图标对象
# 默认配置
default_config = {
    "absence_threshold": 10,  # 默认10秒
    "scan_interval": 2
}

# ================= 快捷键相关函数 =================

def send_todesk_shortcut():
    """发送 Ctrl+Shift+Alt+D 快捷键关闭 ToDesk 连接"""
    system = platform.system()
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
        
        print("已发送 Ctrl+Shift+Alt+D 快捷键关闭 ToDesk 连接")
        
        # 方法2: 尝试直接关闭ToDesk窗口
        try:
            # 查找ToDesk窗口
            todesk_hwnd = win32gui.FindWindow(None, "ToDesk")
            if todesk_hwnd != 0:
                # 发送关闭消息
                win32gui.PostMessage(todesk_hwnd, win32con.WM_CLOSE, 0, 0)
                print("已发送关闭消息到ToDesk窗口")
        except Exception as e:
            print(f"尝试关闭ToDesk窗口失败: {e}")
            
    elif system == "Linux":
        try:
            subprocess.run(["xdotool", "key", "ctrl+shift+alt+d"], check=True)
            print("已发送 Ctrl+Shift+Alt+D 快捷键关闭 ToDesk 连接")
        except Exception as e:
            print(f"发送快捷键失败: {e}")
    elif system == "Darwin":  # macOS
        try:
            script = '''
            tell application "System Events"
                keystroke "d" using {control down, shift down, option down}
            end tell
            '''
            subprocess.run(["osascript", "-e", script], check=True)
            print("已发送 Ctrl+Shift+Alt+D 快捷键关闭 ToDesk 连接")
        except Exception as e:
            print(f"发送快捷键失败: {e}")
    else:
        print("当前操作系统不支持发送快捷键")

# ================= 蓝牙相关函数 =================

def lock_screen():
    """直接锁定屏幕，使用系统API而不是快捷键"""
    system = platform.system()
    if system == "Windows":
        # 方法1: 使用Windows API直接锁屏
        try:
            result = ctypes.windll.user32.LockWorkStation()
            if result:
                print("已成功锁定屏幕")
            else:
                print(f"锁屏失败，错误码: {ctypes.get_last_error()}")
                
            # 方法2: 如果API失败，尝试使用rundll32命令
            if not result:
                try:
                    os.system('rundll32.exe user32.dll,LockWorkStation')
                    print("已使用rundll32命令锁定屏幕")
                except Exception as e:
                    print(f"使用rundll32锁屏失败: {e}")
        except Exception as e:
            print(f"锁屏API调用失败: {e}")
    
    elif system == "Linux":
        try:
            # 尝试多种Linux锁屏命令
            commands = [
                ["gnome-screensaver-command", "-l"],
                ["loginctl", "lock-session"],
                ["xdg-screensaver", "lock"]
            ]
            
            for cmd in commands:
                try:
                    subprocess.run(cmd, check=True)
                    print(f"已使用 {' '.join(cmd)} 锁定屏幕")
                    return
                except:
                    continue
                    
            print("所有锁屏命令均失败")
        except Exception as e:
            print(f"锁屏失败: {e}")
            
    elif system == "Darwin":
        os.system('/System/Library/CoreServices/Menu\\ Extras/User.menu/Contents/Resources/CGSession -suspend')
    else:
        print("当前操作系统不受支持。")

def scan_devices(duration=4):
    print("正在扫描蓝牙设备，请稍候...")
    devices = bluetooth.discover_devices(duration=duration, lookup_names=True)
    if not devices:
        print("没有发现蓝牙设备。")
    else:
        print("扫描到以下蓝牙设备：")
        for i, (addr, name) in enumerate(devices):
            print(f"{i}: 名称: {name}, 地址: {addr}")
    return devices

def save_config(device, config=None):
    if config is None:
        config = default_config.copy()
    
    config.update({
        "address": device[0],
        "name": device[1]
    })
    
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
        print("设备配置已保存。")
    except Exception as e:
        print("保存配置出错：", e)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return None, default_config
    
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        
        # 提取设备信息
        device = (config.get("address"), config.get("name"))
        
        # 提取配置信息，如果不存在则使用默认值
        settings = default_config.copy()
        if "absence_threshold" in config:
            settings["absence_threshold"] = config["absence_threshold"]
        if "scan_interval" in config:
            settings["scan_interval"] = config["scan_interval"]
            
        return device, settings
    except Exception as e:
        print("加载配置出错：", e)
        return None, default_config

def scan_for_target(target_addr, duration=4):
    devices = bluetooth.discover_devices(duration=duration, lookup_names=True)
    for addr, name in devices:
        if addr == target_addr:
            return True
    return False

# ================= 监控线程 =================

def monitor_device(absence_threshold=10, scan_interval=2):
    """
    监控逻辑：
      - 如果扫描中检测到目标设备，状态设为"设备在附近"；
      - 如果曾检测到设备但随后未检测到，则状态设为"设备离开"，并累计缺失时间，
        超过阈值后先发送快捷键关闭ToDesk连接，然后执行锁屏，并标记为已锁屏；
      - 当设备重新回到附近时，重置锁屏标记，允许下次离开时再次锁屏；
      - 如果一直未检测到设备，则状态显示"设备未携带"。
    """
    global target_device, running, current_state
    device_was_seen = False
    absence_time = 0
    screen_locked = False  # 新增标记，记录当前离开周期是否已锁屏
    
    while running:
        if target_device is None:
            current_state = "未绑定"
            time.sleep(scan_interval)
            continue

        current_target = target_device
        print(f"扫描目标设备：{current_target[1]} ({current_target[0]})")
        found = scan_for_target(current_target[0], duration=4)
        
        if found:
            # 设备在附近
            device_was_seen = True
            if absence_time > 0:
                # 设备重新回到附近，重置锁屏标记
                print("设备重新回到附近，重置计时器")
                screen_locked = False  # 重置锁屏标记
            
            absence_time = 0
            current_state = "设备在附近"
            print("设备在附近")
        else:
            # 设备不在附近
            if device_was_seen:
                absence_time += scan_interval
                current_state = "设备离开"
                print(f"设备暂时未检测到，累计缺失时间: {absence_time}秒")
                
                # 只有当超过阈值且尚未锁屏时，才执行锁屏
                if absence_time >= absence_threshold and not screen_locked:
                    print("设备长期缺失，执行关闭ToDesk连接和锁屏操作")
                    # 先发送快捷键关闭ToDesk连接
                    send_todesk_shortcut()
                    # 等待一小段时间确保ToDesk关闭
                    time.sleep(1)
                    # 然后锁屏
                    lock_screen()
                    screen_locked = True  # 标记为已锁屏
                    # 不重置absence_time，继续累计离开时间
            else:
                current_state = "设备未携带"
                print("设备未携带")
                
        time.sleep(scan_interval)
    print("监控线程退出。")

# ================= GUI 绑定界面 =================

def gui_binding_process():
    """
    弹出 Tkinter 窗口，显示扫描到的蓝牙设备列表，
    允许点击"重新扫描"刷新列表，选中设备后点击"确认"完成绑定。
    """
    devices = []
    _, current_settings = load_config()

    def scan_and_update():
        nonlocal devices
        devices = scan_devices(duration=4)
        listbox.delete(0, tk.END)
        if not devices:
            messagebox.showinfo("提示", "没有发现蓝牙设备，请检查蓝牙状态！")
        else:
            for i, (addr, name) in enumerate(devices):
                listbox.insert(tk.END, f"{i}: 名称: {name}, 地址: {addr}")

    def confirm_selection():
        selection = listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个设备")
            return
        index = selection[0]
        selected = devices[index]
        save_config(selected, current_settings)
        messagebox.showinfo("提示", f"已选定设备：名称: {selected[1]}, 地址: {selected[0]}")
        global target_device
        target_device = selected
        root.destroy()

    root = tk.Tk()
    root.title("重新绑定蓝牙设备")
    listbox = tk.Listbox(root, width=60, height=10)
    listbox.pack(padx=10, pady=10)
    frame = tk.Frame(root)
    frame.pack(pady=5)
    btn_scan = tk.Button(frame, text="重新扫描", command=scan_and_update)
    btn_scan.pack(side=tk.LEFT, padx=5)
    btn_confirm = tk.Button(frame, text="确认", command=confirm_selection)
    btn_confirm.pack(side=tk.LEFT, padx=5)
    scan_and_update()
    root.mainloop()

# ================= 系统托盘图标与菜单 =================

def create_image():
    """
    创建一个简单的托盘图标（蓝色圆形）
    """
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), color="white")
    dc = ImageDraw.Draw(image)
    dc.ellipse((8, 8, width - 8, height - 8), fill="blue")
    return image

def on_rebind(icon, item):
    threading.Thread(target=gui_binding_process, daemon=True).start()

def on_exit(icon, item):
    global running
    running = False
    icon.stop()
    sys.exit(0)

def on_set_threshold(icon, item):
    """设置检测设备离开多久后锁屏的时间阈值"""
    global target_device
    _, current_settings = load_config()
    current_threshold = current_settings.get("absence_threshold", default_config["absence_threshold"])
    
    # 创建一个独立的对话框窗口
    def show_dialog():
        dialog_root = tk.Tk()
        dialog_root.title("设置时间阈值")
        dialog_root.geometry("300x150")
        dialog_root.resizable(False, False)
        
        # 确保窗口在最前面
        dialog_root.attributes('-topmost', True)
        
        # 创建标签和输入框
        tk.Label(dialog_root, text="请输入检测不到设备多久后锁屏（秒）：", pady=10).pack()
        
        # 创建一个StringVar来存储输入值
        threshold_var = tk.StringVar(value=str(current_threshold))
        entry = tk.Entry(dialog_root, textvariable=threshold_var, width=10)
        entry.pack(pady=5)
        entry.select_range(0, tk.END)
        entry.focus()
        
        # 创建按钮框架
        btn_frame = tk.Frame(dialog_root)
        btn_frame.pack(pady=10)
        
        # 确认按钮的回调函数
        def on_confirm():
            try:
                new_threshold = int(threshold_var.get())
                if new_threshold < 1:
                    messagebox.showwarning("警告", "时间阈值必须大于0秒")
                    return
                if new_threshold > 300:
                    messagebox.showwarning("警告", "时间阈值不能超过300秒")
                    return
                
                # 更新配置
                if new_threshold != current_threshold:
                    current_settings["absence_threshold"] = new_threshold
                    if target_device:
                        save_config(target_device, current_settings)
                        messagebox.showinfo("提示", f"时间阈值已更新为 {new_threshold} 秒")
                    else:
                        messagebox.showwarning("提示", "请先绑定设备后再设置时间阈值")
                dialog_root.destroy()
            except ValueError:
                messagebox.showwarning("警告", "请输入有效的数字")
        
        # 取消按钮的回调函数
        def on_cancel():
            dialog_root.destroy()
        
        # 添加确认和取消按钮
        tk.Button(btn_frame, text="确认", command=on_confirm, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", command=on_cancel, width=10).pack(side=tk.LEFT, padx=5)
        
        # 绑定回车键到确认按钮
        dialog_root.bind('<Return>', lambda event: on_confirm())
        
        # 显示对话框并等待
        dialog_root.mainloop()
    
    # 在新线程中显示对话框，避免阻塞托盘图标线程
    threading.Thread(target=show_dialog, daemon=True).start()

def get_current_state(_):
    # 接收参数 _ 以符合 pystray 的调用要求
    return "当前状态: " + current_state

def update_tray_menu():
    global tray_icon
    while running:
        if tray_icon is not None:
            tray_icon.update_menu()  # 强制刷新菜单项
        time.sleep(2)

def setup_tray():
    global tray_icon
    menu = (
        item(get_current_state, None, enabled=False),
        item("重新绑定蓝牙设备", on_rebind),
        item("设置时间阈值", on_set_threshold),
        item("退出", on_exit)
    )
    tray_icon = pystray.Icon("BluetoothMonitor", create_image(), "蓝牙监控", menu)
    # 开启一个线程定时刷新托盘菜单
    threading.Thread(target=update_tray_menu, daemon=True).start()
    tray_icon.run()

# ================= 主程序 =================

def main():
    global target_device
    target_device, settings = load_config()
    if target_device:
        print(f"加载到已绑定设备：名称: {target_device[1]}, 地址: {target_device[0]}")
        print(f"当前设置：检测不到设备 {settings['absence_threshold']} 秒后锁屏")
    else:
        print("没有找到绑定设备，启动绑定流程")
        gui_binding_process()
        # 重新加载配置
        target_device, settings = load_config()
    
    # 启动蓝牙监控线程，使用配置中的参数
    monitor_thread = threading.Thread(
        target=monitor_device, 
        args=(settings["absence_threshold"], settings["scan_interval"]),
        daemon=True
    )
    monitor_thread.start()
    
    # 启动系统托盘图标
    setup_tray()

if __name__ == "__main__":
    main()
