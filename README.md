# 蓝牙自动锁屏工具

## 项目简介

蓝牙自动锁屏工具是一个基于蓝牙设备检测的自动锁屏应用程序。当您携带绑定的蓝牙设备（如手机）离开电脑一定距离后，系统将自动锁定屏幕，保护您的隐私和数据安全。

## 功能特点

- **自动检测**：持续监控指定蓝牙设备的存在状态
- **智能锁屏**：当绑定设备离开一段时间后自动锁定电脑屏幕（仅锁屏一次）
- **智能恢复**：当设备重新回到附近时，重置锁屏状态，允许下次离开时再次锁屏
- **跨平台支持**：支持 Windows、Linux 和 macOS 系统
- **系统托盘图标**：提供直观的状态显示和操作界面
- **设备绑定**：简单的图形界面用于选择和绑定蓝牙设备
- **ToDesk断开**：在锁屏前自动发送快捷键关闭ToDesk远程连接
- **可配置时间**：可自定义设备离开多久后触发锁屏，默认为10秒

## 使用方法

### 安装依赖

```bash
pip install bluetooth pystray pillow pywin32
```

### 运行程序

```bash
python ble_lock.py
```

### 首次使用

1. 首次运行时，程序会自动打开设备绑定界面
2. 点击"重新扫描"按钮搜索附近的蓝牙设备
3. 从列表中选择您想要绑定的设备（通常是您的手机）
4. 点击"确认"按钮完成绑定

### 日常使用

- 程序启动后会在系统托盘显示一个蓝色图标
- 托盘菜单显示当前设备状态（设备在附近/设备离开/设备未携带）
- 当您携带绑定的设备离开电脑超过预设时间（默认10秒）后，系统将自动关闭ToDesk连接并锁屏
- 您可以通过托盘菜单随时重新绑定设备、设置时间阈值或退出程序

### 设置时间阈值

1. 右键点击系统托盘中的蓝色图标
2. 选择"设置时间阈值"选项
3. 在弹出的对话框中输入新的时间值（单位：秒）
4. 点击"确定"保存设置

## 技术实现

### 核心技术

- **蓝牙通信**：使用 Python 的 `bluetooth` 库实现设备扫描和检测
- **多线程处理**：采用线程分离监控逻辑和用户界面，确保程序响应性
- **系统集成**：根据不同操作系统调用相应的锁屏API
- **状态管理**：实时监控和更新设备状态，智能判断锁屏时机
- **配置持久化**：使用JSON文件保存设备配置信息和时间阈值设置
- **快捷键模拟**：使用系统API模拟键盘快捷键操作，关闭ToDesk连接

### 工作原理

1. **设备绑定**：用户选择并绑定一个蓝牙设备，配置信息保存到本地
2. **持续监控**：程序定期扫描周围蓝牙设备，检查绑定设备是否在范围内
3. **状态判断**：
   - 如果检测到设备，状态设为"设备在附近"
   - 如果曾检测到但随后未检测到，状态设为"设备离开"，并开始计时
   - 如果一直未检测到，状态显示为"设备未携带"
4. **自动锁屏**：当设备离开状态持续超过阈值时间（默认10秒），自动执行以下操作：
   - 发送Ctrl+Shift+Alt+D快捷键关闭ToDesk连接
   - 执行系统锁屏操作
   - 在设备重新回到附近前不会重复锁屏
5. **智能恢复**：当设备重新回到附近时，重置锁屏状态，允许下次离开时再次触发锁屏

### 系统架构

- **监控线程**：负责蓝牙设备扫描和状态判断
- **GUI模块**：提供设备绑定和时间阈值设置的图形界面
- **系统托盘**：显示程序状态和提供用户操作入口
- **锁屏模块**：根据不同操作系统实现屏幕锁定功能
- **快捷键模块**：根据不同操作系统实现键盘快捷键模拟

## 配置选项

程序支持以下配置选项，可通过系统托盘菜单或修改配置文件进行调整：

- `absence_threshold`：设备离开多长时间后锁屏（默认10秒）
- `scan_interval`：蓝牙扫描间隔时间（默认2秒）

配置文件保存在程序同目录下的 `device_config.json` 文件中。

## 常见问题

1. **无法检测到蓝牙设备**
   - 确保您的电脑蓝牙已开启
   - 确保目标设备蓝牙已开启且可被发现
   - 尝试重启蓝牙服务

2. **锁屏功能不工作**
   - 确保程序有足够的系统权限
   - 检查操作系统的锁屏策略设置

3. **ToDesk快捷键不起作用**
   - 确认ToDesk的快捷键设置是否为默认值（Ctrl+Shift+Alt+D）
   - 尝试手动测试快捷键是否有效

4. **程序占用资源过高**
   - 尝试增加扫描间隔时间减少资源占用

## 系统要求

- Python 3.6+
- 支持蓝牙功能的电脑
- Windows 10/11, macOS 10.14+, 或主流Linux发行版
- 对于Windows系统，需要安装pywin32库

## 许可证

MIT License

## 贡献指南

欢迎提交问题报告和功能建议。如果您想贡献代码，请先创建issue讨论您的想法。

## 未来计划

- 添加更多自定义配置选项
- 优化蓝牙扫描性能
- 添加多设备绑定支持
- 实现更智能的存在检测算法
- 支持自定义快捷键设置 