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
from tkinter import messagebox

# 配置文件保存路径和全局变量
CONFIG_FILE = "device_config.json"
target_device = None  # 格式: (address, name)
running = True       # 控制监控线程退出
current_state = "未知"  # 当前状态（用于托盘菜单动态显示）
tray_icon = None     # 全局托盘图标对象

# ================= 蓝牙相关函数 =================

def lock_screen():
    system = platform.system()
    if system == "Windows":
        result = ctypes.windll.user32.LockWorkStation()
        if not result:
            print("锁屏失败，请确保权限足够。")
    elif system == "Linux":
        try:
            subprocess.run(["gnome-screensaver-command", "-l"], check=True)
        except Exception:
            try:
                subprocess.run(["loginctl", "lock-session"], check=True)
            except Exception:
                print("未能锁定屏幕，请检查系统支持的锁屏方式。")
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

def save_config(device):
    config = {
        "address": device[0],
        "name": device[1]
    }
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
        print("设备配置已保存。")
    except Exception as e:
        print("保存配置出错：", e)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        return (config.get("address"), config.get("name"))
    except Exception as e:
        print("加载配置出错：", e)
        return None

def scan_for_target(target_addr, duration=4):
    devices = bluetooth.discover_devices(duration=duration, lookup_names=True)
    for addr, name in devices:
        if addr == target_addr:
            return True
    return False

# ================= 监控线程 =================

def monitor_device(absence_threshold=30, scan_interval=2):
    """
    监控逻辑：
      - 如果扫描中检测到目标设备，状态设为"设备在附近"；
      - 如果曾检测到设备但随后未检测到，则状态设为"设备离开"，并累计缺失时间，
        超过阈值后执行锁屏，并标记为已锁屏；
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
                    print("设备长期缺失，执行锁屏操作")
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
        save_config(selected)
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
        item("退出", on_exit)
    )
    tray_icon = pystray.Icon("BluetoothMonitor", create_image(), "蓝牙监控", menu)
    # 开启一个线程定时刷新托盘菜单
    threading.Thread(target=update_tray_menu, daemon=True).start()
    tray_icon.run()

# ================= 主程序 =================

def main():
    global target_device
    target_device = load_config()
    if target_device:
        print(f"加载到已绑定设备：名称: {target_device[1]}, 地址: {target_device[0]}")
    else:
        print("没有找到绑定设备，启动绑定流程")
        gui_binding_process()
    # 启动蓝牙监控线程
    monitor_thread = threading.Thread(target=monitor_device, daemon=True)
    monitor_thread.start()
    # 启动系统托盘图标
    setup_tray()

if __name__ == "__main__":
    main()
