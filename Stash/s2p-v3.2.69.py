# -*- coding: utf-8 -*-
"""
S-View - Integrates 'Display Mode' with Normal / Max modes.
Author: Arthur Gu
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.ticker import MaxNLocator, MultipleLocator, AutoMinorLocator, ScalarFormatter
import os
import re
import ctypes
from ctypes import wintypes
import sys # 确保导入 sys
from tkinter import colorchooser
import platform
from scipy.signal import find_peaks
import matplotlib.font_manager as fm
import warnings
from PIL import Image, ImageTk
import io
# FIX 1: 导入 collections 模块
import matplotlib.collections as mcollections
import matplotlib.lines as lines
import matplotlib.text as text
# --------------------------
import datetime

# --- [新增激活机制所需的库] ---
import uuid
import base64
import json
# 需要安装：pip install cryptography
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature
# -------------------------------
warnings.filterwarnings("ignore", category=UserWarning)

# 支持 Smith 图 - 已移除 skrf 依赖
SMITH_AVAILABLE = False # 显式设置为 False

#Update log
#2.46.16 移除整个 def _draw_max_plot(self)
#2.46.18 移除整个 Normal模式切换为新显示形式
#2.46.19 修复Normal模式下的bug
#2.46.20 增加启动程序但未加载文件光标坐标区显示 "X: ---, Y: ---"
#2.46.50 移除自定义ID颜色
#2.46.51 修复Normal模式下Marker标记拖拽的bug
#2.46.52 修复Normal模式下第一次添加Marker是出现重复Marker的bug
#2.46.53 修复Normal模式下拖动图表出现残影的bug
#2.46.54 修复disable_refresh拖动Marker Legend图表恢复大小的bug
#2.46.55 修复拖动Marker Legend图表闪烁2下的bug
#2.46.56 增加自定义Marker Legend颜色自定义功能
#2.47 添加Peak Marker Search功能
#2.47.1 修复Limits & Marks标签页的bug
#2.47.2 添加Marker超出范围显示Out of Freq Range提示
#2.47.3 修复添加Marker标签后再次加载文件无法识别新文件Ref ID的bug
#2.47.4 添加无文件时禁止添加Marker和Limit Line
#2.47.5 优化Peak Marker Search功能
#2.47.6 修复Normal模式下无法删除Peak Search Marker标签的bug
#2.47.7 优化Max模式下未加载文件时的显示
#2.47.8 优化Limits & Marks输入框大小
#2.47.9 更改Limits & Marks组内的Markers名称为Regular Marker
#2.47.10 修复Add Limit line Start Frequency的bug
#2.47.11 Normal优化X轴的刻度更好的支持只显示1个，2个，3个S参数
#2.47.12 修复Normal模式下Zoom后保持图片不一致的bug
#2.47.13 修复Reset App无法清除Marker Legend背景颜色的bug
#2.47.14 优化Loaded File Informaiton标签页内的名称
#2.47.15 优化Loaded File Informaiton标签页内的显示，隐藏ID, File Path等信息
#2.47.16 Loaded S2P File List增加文件隐藏开关并修复Normal模式报告Title消失的bug
#2.47.17 修复Max模式下截图、保存文件顶部序列号重影的bug
#2.47.18 删除重复的draw_marker_search_config_frame函数
#2.47.19 Peak Marker Search频率单位改为下拉菜单选择MHz、GHz
#2.47.20 Normal模式的Peak Search增加First Match和Last Match功能
#2.47.21 Max模式的Peak Search增加First Match和Last Match功能
#2.47.22 FirsMatch和Last Match频率精确到3位小数
#2.47.23 移动Marker Legend Position位置到Loaded File Information标签页
#2.47.24 修改XY轴标签页修改字体大小
#2.47.25 优化Loaded File Informaiton标签页内S11,S21,S12,S22标签的显示
#2.47.26 修复Normal模式下只能拖动一次的bug
#2.47.27 修复Normal模式下Disable Refresh在拖拽时失效的bug
#2.47.28 修复Max模式下Disable Refresh在拖拽时失效的bug
#2.47.29 修复Max模式下多次切换后显示多Marker的bug
#2.47.30 初始化def __init__添加Max模式事件管理初始化
#2.47.31 优化Lower Limit的显示
#2.47.32 优化Loaded S2P File List和Axis Control显示
#2.47.33 优化Axis Control的按钮大小
#2.47.34 优化Limits & Marks的按钮大小
#2.47.35 更改Clear Names名称为Rest Name并更改按钮大小
#3.0 无bug,最终发行版.
#3.1 添加只能DPI功能
#3.2 添加Auto Font Color功能

# ----------------------------------------------------
# [新增] PyInstaller 资源路径解析函数 (修复 onefile 模式路径问题)
# ----------------------------------------------------
def resource_path(relative_path):
    """
    获取资源文件的绝对路径。
    在开发模式下，返回相对路径。
    在 PyInstaller 打包模式下，返回临时解压路径 (_MEIPASS)。
    """
    try:
        # PyInstaller 打包后的临时目录
        base_path = sys._MEIPASS
    except Exception:
        # 开发模式下的当前脚本目录
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)
# ----------------------------------------------------


# ----------------------------------------------------
# 激活机制配置和核心工具函数
# ----------------------------------------------------

# --- 激活机制配置 ---
LICENSE_FILE = "license.json"
PUBLIC_KEY_FILE = "public_key.pem"
# --- 激活机制配置结束 ---

def get_machine_id():
    """生成一个稳定的机器唯一标识符 (基于 MAC 地址)。"""
    try:
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff) for i in range(0, 8 * 6, 8)][::-1])
        if mac == '00:00:00:00:00:00':
             return f"{platform.node()}-{platform.system()}-{platform.machine()}".upper()
        return mac.upper()
    except Exception:
        return f"{platform.node()}-{platform.system()}-{platform.machine()}".upper()

def load_public_key():
    """加载公钥用于验证签名和机器码加密。"""
    
    # ***** 核心修复：使用 resource_path 来解析打包后的文件路径 *****
    public_key_full_path = resource_path(PUBLIC_KEY_FILE)
    # ************************************************************
    
    if not os.path.exists(public_key_full_path):
        raise FileNotFoundError(f"Public key file {PUBLIC_KEY_FILE} does not exist.\nFailed to locate the program at the path {public_key_full_path}.Please make sure that key_utils.py has been executed.")
    with open(public_key_full_path, "rb") as f:
        public_key = serialization.load_pem_public_key(
            f.read(),
            backend=default_backend()
        )
    return public_key

def encrypt_machine_id(machine_id):
    """使用公钥加密机器码，用于发送给许可证生成者。"""
    try:
        public_key = load_public_key()
        cipher_text = public_key.encrypt(
            machine_id.encode('utf-8'),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return base64.urlsafe_b64encode(cipher_text).decode('utf-8')
    except Exception as e:
        raise Exception(f"Machine code encryption failed: {e}")

def verify_license(machine_id, activation_code):
    """使用公钥验证激活码的有效性，并返回到期日期。"""
    try:
        public_key = load_public_key()
        parts = activation_code.split('|')
        if len(parts) != 2:
            return False, "Activation code format is incorrect."
            
        expiry_date_b64, signature_b64 = parts
        expiry_date_str = base64.urlsafe_b64decode(expiry_date_b64).decode('utf-8')
        expiry_date = datetime.datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
        data_to_verify = f"{machine_id}|{expiry_date_str}".encode('utf-8')
        signature = base64.urlsafe_b64decode(signature_b64)

        public_key.verify(
            signature,
            data_to_verify,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )

        if expiry_date < datetime.date.today():
            return False, f"The activation code has expired ({expiry_date_str})"
            
        return True, expiry_date

    except InvalidSignature:
        return False, "Activation code signature verification failed (Invalid activation code)"
    except Exception as e:
        return False, f"An error occurred during the activation code verification process: {e}"

# ----------------------------------------------------
# 许可证管理和激活对话框 (已移除错误的缩进)
# ----------------------------------------------------

class ActivationDialog(simpledialog.Dialog):
    """
    激活对话框，显示机器码并提供激活码输入框。
    """
    def __init__(self, parent, machine_id, encrypted_machine_id):
        self.machine_id = machine_id
        self.encrypted_machine_id = encrypted_machine_id
        self.activation_code = None
        self.result = False # 默认失败
        super().__init__(parent, title="Software Activation")
        
    def body(self, master):
        
        # 机器码显示区域
        tk.Label(master, text="Step 1: Please send the machine code below to the software provider to obtain your activation code.", font=('Helvetica', 10, 'bold')).pack(pady=(10, 5), padx=20, anchor='w')
        
        # 加密机器码
        tk.Label(master, text="Machine Code:", font=('Helvetica', 9)).pack(pady=(0, 2), padx=20, anchor='w')
        # 使用 scrolledtext 确保长机器码可滚动
        self.machine_code_display = scrolledtext.ScrolledText(master, height=5, width=50, wrap=tk.WORD, bd=2, relief=tk.FLAT)
        self.machine_code_display.insert(tk.END, self.encrypted_machine_id)
        self.machine_code_display.config(state=tk.DISABLED) 
        self.machine_code_display.pack(pady=5, padx=20)
        
        # 复制按钮
        copy_button = tk.Button(master, text="Copy Machine Code", command=self.copy_machine_code)
        copy_button.pack(pady=(0, 10))

        # 激活码输入区域
        tk.Label(master, text="Step 2: Please enter the activation code:", font=('Helvetica', 10, 'bold')).pack(pady=(10, 5), padx=20, anchor='w')
        self.activation_entry = scrolledtext.ScrolledText(master, height=5, width=50, wrap=tk.WORD, bd=2, relief=tk.SUNKEN)
        self.activation_entry.pack(pady=5, padx=20)
        
        return self.activation_entry
        
    def copy_machine_code(self):
        """复制加密机器码到剪贴板"""
        try:
            self.parent.clipboard_clear()
            self.machine_code_display.config(state=tk.NORMAL)
            code_to_copy = self.machine_code_display.get(1.0, tk.END).strip()
            self.machine_code_display.config(state=tk.DISABLED)
            
            self.parent.clipboard_append(code_to_copy)
            messagebox.showinfo("Copied Successfully", "The machine code has been copied to the clipboard.")
        except Exception as e:
            messagebox.showerror("Copy Failed", f"Unable to access clipboard: {e}")

    def buttonbox(self):
        box = tk.Frame(self)
        w = tk.Button(box, text="Activate", width=10, command=self.ok, default=tk.ACTIVE)
        w.pack(side=tk.LEFT, padx=5, pady=5)
        # 确保按回车也能触发确认
        self.bind("<Return>", self.ok)
        box.pack()

    def apply(self):
        """点击确认激活按钮时调用，进行验证和保存"""
        import traceback # 导入用于打印堆栈信息的模块
        
        try:
            self.activation_code = self.activation_entry.get(1.0, tk.END).strip()
            if not self.activation_code:
                messagebox.showerror("Activation failed", "Activation code cannot be empty.")
                self.result = False
                return 

            # 验证激活码
            is_valid, result = verify_license(self.machine_id, self.activation_code)
            
            if is_valid:
                expiry_date = result
                # 激活成功，保存许可证
                license_data = {
                    "machine_id": self.machine_id,
                    "activation_code": self.activation_code,
                    "expiry_date": expiry_date.strftime('%Y-%m-%d')
                }
                try:
                    with open(LICENSE_FILE, 'w') as f:
                        json.dump(license_data, f, indent=4)
                    
                    messagebox.showinfo("Activation successful.", f"The software has been successfully activated and is valid until {expiry_date}.")
                    self.result = True
                except Exception as e:
                    messagebox.showerror("Activation failed", f"Failed to write license file. Please check file permissions.\nError details: {e}")
                    self.result = False
                    return 
            else:
                messagebox.showerror("Activation failed", f"Invalid activation code.\nError details: {result}")
                self.result = False
                return 
        
        except Exception as general_e:
            # 捕获所有未预期的错误，并报告
            error_details = traceback.format_exc()
            messagebox.showerror("An unknown error occurred during activation", f"An unexpected error was caught during activation. Please check the console output.\nError details: {general_e}")
            print("--- Activation Dialog apply() Unexpected Error ---")
            print(error_details)
            print("---------------------------------")
            self.result = False
            return 
            

def check_license(root):
    """
    检查许可证文件，如果不存在或过期，则弹出激活对话框。
    返回 True 表示许可证有效，可以启动主程序；False 表示未激活或程序已退出。
    """
    machine_id = get_machine_id()
    
    is_licensed = False
    
    # 尝试加载许可证
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, 'r') as f:
                license_data = json.load(f)
                
            stored_machine_id = license_data.get('machine_id')
            activation_code = license_data.get('activation_code')
            
            # 1. 检查机器码是否匹配
            if stored_machine_id != machine_id:
                messagebox.showwarning("License Error", "Machine code change detected. Please reactivate the software.")
            elif activation_code:
                # 2. 验证激活码的有效性
                is_valid, result = verify_license(machine_id, activation_code)
                
                if is_valid:
                    is_licensed = True
                else:
                    messagebox.showwarning("License expired or invalid", f"License verification failed or expired.\nDetails: {result}")

        except Exception as e:
            print(f"License file failed to load or parse.: {e}")
            messagebox.showwarning("License Error", "The license file is corrupted or unreadable and needs to be reactivated.")
    
    # 3. 如果未授权，则弹出激活对话框
    if not is_licensed:
        # 生成加密机器码
        try:
            encrypted_machine_id = encrypt_machine_id(machine_id)
        except Exception as e:
            messagebox.showerror("Fatal error", f"Unable to generate machine code, possibly missing public_key.pem.\nError details: {e}")
            root.destroy()
            return False

        # 弹出激活对话框 (此调用会阻塞直到对话框关闭)
        dialog = ActivationDialog(root, machine_id, encrypted_machine_id)
        
        # 对话框关闭后，检查结果
        if not dialog.result:
            messagebox.showerror("Startup failed", "Startup failed: software is not activated or activation failed.")
            # 只有在未激活时才退出
            root.destroy()
            return False
        else:
            return True
            
    else:
        return True

# ----------------------------------------------------
# Marker Legend 排序辅助函数和常量
# ----------------------------------------------------

# S 参数的排序优先级映射：S11 -> 0, S21 -> 1, S12 -> 2, S22 -> 3
S_PARAM_ORDER = {'S11': 0, 'S21': 1, 'S12': 2, 'S22': 3}

def get_marker_id_number(marker_id_str):
    """
    从 Marker ID 字符串（如 'M1', 'M10'）中提取数字部分。
    """
    import re
    # 查找字符串中第一个连续的数字序列
    match = re.search(r'\d+', marker_id_str)
    # 如果找到数字，返回整数；否则返回一个很大的数，确保它排在最后
    return int(match.group()) if match else 9999

# 自动选择中文字体
def get_chinese_font():
    fonts = ["Microsoft YaHei", "SimHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC", "DejaVu Sans"]
    available = [f.name for f in fm.fontManager.ttflist]
    for f in fonts:
        if f in available:
            return f
    return "sans-serif"

# ----------------------------------------------------
# [新增] DPI 自适应计算函数
# ----------------------------------------------------
def get_scaling_factor():
    """尝试获取系统的缩放因子 (用于高DPI屏幕)"""
    try:
        # 创建一个临时的 Tk 实例来获取 DPI
        temp_root = tk.Tk()
        # winfo_fpixels('1i') 返回一英寸内的像素数，即物理 DPI
        screen_dpi = temp_root.winfo_fpixels('1i')
        temp_root.destroy()
        
        # Matplotlib 默认 DPI (通常为 100)
        base_mpl_dpi = 100 
        
        # 计算缩放因子，并取整 (例如 150% 缩放返回 2, 200% 缩放返回 2)
        scaling_factor = max(1, round(screen_dpi / base_mpl_dpi))
        return scaling_factor
    except Exception:
        # 异常情况或非标准环境返回 1 (无缩放)
        return 1
# ----------------------------------------------------


# ----------------------------------------------------
# 【全局常量】Peak Marker Search 类型选项
# ----------------------------------------------------
MARKER_SEARCH_TYPES = ["Max Value", "Min Value", "Custom Search"]
MATCH_TYPES = ["First Match", "Last Match"]  # 新增：First/Last Match 选项

CHINESE_FONT = get_chinese_font()
plt.rcParams['font.sans-serif'] = [CHINESE_FONT]
plt.rcParams['axes.unicode_minus'] = False

# 颜色循环
#1f77b4 (#经典蓝), #ff7f0e (#经典橙), #2ca02c (#经典绿), #d62728 (#经典红), #9467bd (#经典紫), #8c564b (#棕褐色), #17becf (#青蓝色), #bcbd22 (#黄绿色), #e377c2 (#玫瑰粉), #7f7f7f (#中灰色),#e41a1c (#哈佛红),#377eb8 (#亮宝蓝), #4daf4a (#鲜草绿), #984ea3 (#明亮紫), #ff7f00 (#亮橙色), #ffff33 (#明黄色), #a65628 (#深棕色), #f781bf (#樱花粉), #999999 (#浅灰色), #66c2a5 (#薄荷绿)

#COLOR_CYCLE = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#bcbd22', '#17becf', '#7f7f7f', '#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33', '#a65628', '#f781bf', '#999999', '#66c2a5']

COLOR_CYCLE = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#17becf', '#bcbd22', '#e377c2', '#7f7f7f', '#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00', '#ffff33', '#a65628', '#f781bf', '#999999', '#66c2a5']

# 暗主题配色（高亮度版本，适合黑底）
COLOR_CYCLE_DARK = ['#a5cee3', '#fdbf6f', '#b2df8a', '#fb9a99', '#cab2d6', '#ffff99', '#b15928', '#ffffff', '#bdbdbd', '#6a3d9a', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf', '#ffbb78']


# 剪贴板复制 (Windows 支持)
def copy_image_to_clipboard(img):
    system = platform.system()
    if system == "Windows":
        clipboard_opened = False
        try:
            import win32clipboard
            from io import BytesIO
            output = BytesIO()
            img.convert("RGB").save(output, format="BMP")
            data = output.getvalue()[14:]
            output.close()
            win32clipboard.OpenClipboard()
            clipboard_opened = True
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            return True
        except Exception as e:
            print("Clipboard copy failed:", e)
            return False
        finally:
            if clipboard_opened:
                try:
                    win32clipboard.CloseClipboard()
                except:
                    pass
    return False

class SViewGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("S-View Created By Arthur Gu | V3.3")
        self.root.geometry("1450x980")
        self.root.resizable(True, True)
        self.root.minsize(1150, 780)
        self.root.configure(bg="#f0f2f5")

        # ====== [新增 DPI 自适应逻辑] 高DPI 屏幕自适应核心代码======
        self.scaling_factor = get_scaling_factor()
        self.actual_dpi = 100 * self.scaling_factor
        plt.rcParams['figure.dpi'] = self.actual_dpi       # 画图清晰
        plt.rcParams['savefig.dpi'] = 300           # 导出超清
        # =================================================================

        # 用户自定义颜色存储
        # Normal模式:  { dataset_id: "#RRGGBB" }
        self.custom_id_colors = {}
        # Max模式: { dataset_id: { "S11": "#", "S21": "#", ... } }
        self.custom_sparam_colors = {}

        self.params = ["S11", "S21", "S12", "S22"]
        # S 参数显示状态变量 (默认全部显示)
        self.show_param_vars = {p: tk.BooleanVar(value=True) for p in self.params}
        # 允许 Center
        self.MARKER_POSITIONS = ["Top Left", "Top Right", "Bottom Left", "Bottom Right", "Center", "Custom"] 
        self.plot_configs = {}
        self.limit_tabs = {}

        # === Report Logo 添加 ===
        self.report_logo_path = None
        self.report_logo_width = tk.StringVar(value="150")   # 默认 150 像素
        self.report_logo_height = tk.StringVar(value="60")  # 默认 60 像素

        self.max_fig = None
        self.max_canvas = None
        # 初始化一个保底值，以防读取失败
        self.max_fig_default_height_px = 850 
        # ⚠️ 确保在 Figure 被 Tkinter 放置并绘制一次后捕获尺寸
        if self.max_fig and self.max_canvas:
            self.root.update_idletasks() # 确保 Tkinter 已布局
            self.max_fig.canvas.draw()
            # 捕获默认尺寸下的 Figure 像素高度作为参考
            self.max_fig_default_height_px = self.max_fig.bbox.height

        # --- Max 模式事件管理初始化---
        # 用于存储 Max 模式中除 _cursor_move_cid 外的其他事件连接 ID
        self.max_cids = {}
         # 用于存储鼠标移动事件的连接 ID
        self._cursor_move_cid = None

        # --- 新增：拖拽平移状态追踪 ---
        self.pan_drag_active = False
        self.pan_start_x = None
        self.pan_start_y = None
        self.left_button_pressed = False
        self.right_button_pressed = False
        self.pan_ax = None
        self.pan_param = None
                
        # 【核心新增/修复】：用于 Blitting 机制，缓存 Axes 背景
        self.pan_ax_bg = None

        # 【新增修复】：Marker 点击处理锁，防止首次点击时事件双重触发
        self.is_processing_marker_click = False

        # 新增：Marker 鼠标操作控制
        self.marker_click_enabled = tk.BooleanVar(value=False) # 默认设置为关闭
        
        # [新增功能] 新增：Disable Refresh 控制变量 (默认未勾选，即默认刷新功能是开启的)
        self.disable_refresh_var = tk.BooleanVar(value=False)

        # [新增功能] Limits Check 控制变量 (默认为关闭)
        self.limits_check_enabled = tk.BooleanVar(value=False) # <--- NEW: Limits Check

        # 【新增】：Marker Legend颜色
        self.auto_font_color_enabled = tk.BooleanVar(value=False)

        # [NEW]: Add trace for auto font color functionality
        self.auto_font_color_enabled.trace_add("write", self._on_auto_font_color_change) # <--- 新增此行  

        # 【关键修复】: 确保 self.marker_legend_ui_refs 在被使用前被初始化
        self.marker_legend_ui_refs = {}
 
        # --- Marker Dragging State (NEW) ---
        self.dragging_marker_legend = False
        
        # 【必须新增】：用于 Blitting 机制，缓存需要快速重绘的前景 Artists (数据线、Marker等)
        self.pan_artists = []
        
        # --- Max模式下的Marker辅助函数 ---
        self.max_marker_artists = []

        # 初始化核心状态
        self._initialize_state()
        self.custom_id_names = {}

        # 必须初始化为 None，便于后续管理
        self.cid_max_drag_press = None
        self.cid_max_drag_release = None
        self.cid_max_drag_motion = None

        # 核心修复：添加 trace，当变量值写入时调用回调函数
        self.marker_click_enabled.trace_add("write", self._on_marker_click_setting_changed)

        # ------------------------------------
        # --- 💥 在这里添加设置图标的代码 ---
        icon_path = os.path.join(os.path.dirname(__file__), "StoreLogo.ico")
        
        # 1. 检查文件是否存在，防止打包后找不到文件
        if not os.path.exists(icon_path):
            # 兼容 pyinstaller 打包后的路径（它会将文件放入临时目录）
            # pyinstaller 在运行时会设置一个特殊的 _MEIPASS 属性
            if hasattr(sys, '_MEIPASS'):
                 icon_path = os.path.join(sys._MEIPASS, "StoreLogo.ico")
            
        try:
            # 使用 iconbitmap() 方法加载 .ico 文件
            self.root.iconbitmap(icon_path)
            
        except tk.TclError:
            # 如果加载失败（例如路径不正确或文件损坏），这里可以捕获错误
            print(f"Warning: Failed to load window icon from {icon_path}")
            pass # 软件继续运行，但使用默认图标
        # ------------------------------------

        # 创建 UI
        # 假设这里有一个 self.setup_ui() 方法
        # self.setup_ui()
        # self.plot_type.trace_add("write", self.on_plot_type_change)
        # self.display_mode.trace_add("write", self.on_display_mode_change)
        #----------------------------------------------------------

    def _initialize_state(self):
        self.datasets = []
        self.next_dataset_id = 1
        self.current_img = None
        self.maximized_param = None

        self.title_var = tk.StringVar(value="SN-001")
        self.plot_type = tk.StringVar(value="Magnitude (dB)")
        self.display_mode = tk.StringVar(value="Normal") # 新增：Normal / Max

        SUPPORTED_PLOT_TYPES = ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"]
        
        self.drag_start_point_axes = None # 拖动起始点的归一化坐标 (0-1)
        self.drag_ax = None # 正在拖动的 Axes 对象
        self.drag_x_var = None # 绑定的 Custom X 变量引用 (tk.StringVar)
        self.drag_y_var = None # 绑定的 Custom Y 变量引用 (tk.StringVar)
        self.drag_mode_var = None # 绑定的 Position Mode 变量引用 (tk.StringVar)
        self.drag_canvas = None # 正在拖动的 Canvas 对象
        # 【新增优化】用于拖动Marker性能优化的变量
        self._drag_update_id = None      # 存储 Tkinter.after 的 ID
        self.DRAG_UPDATE_INTERVAL = 50     # 更新间隔 (毫秒)。推荐 30-60ms
 
        # 存储 Marker Legend 的 Matplotlib Text Artist 对象，用于点击检测
        self.normal_marker_legend_artists = {p: None for p in self.params} 
        self.max_marker_legend_artists = {}
 
        # 初始化 Marker 位置配置
        self.marker_pos_configs = {}
        for pt in SUPPORTED_PLOT_TYPES:
            self.marker_pos_configs[pt] = {}
            for p in self.params:
                self.marker_pos_configs[pt][p] = {
                    "mode_var": tk.StringVar(value="Top Right"),
                    "x_var": tk.StringVar(value="0.5"),
                    "y_var": tk.StringVar(value="0.5")
                }

        # 新增：Max 模式 Marker 位置配置（per plot_type，共享）
        self.max_marker_pos_configs = {}
        for pt in SUPPORTED_PLOT_TYPES:
            self.max_marker_pos_configs[pt] = {
                "mode_var": tk.StringVar(value="Top Right"),
                "x_var": tk.StringVar(value="0.5"),
                "y_var": tk.StringVar(value="0.5")
            }
        
        self.data = {
            "Magnitude (dB)": {
                "limit_lines": {p: [] for p in self.params},
                "marks": {p: [] for p in self.params},
                "ui_refs": {p: {} for p in self.params}
            },
            "Phase (deg)": {
                "limit_lines": {p: [] for p in self.params},
                "marks": {p: [] for p in self.params},
                "ui_refs": {p: {} for p in self.params}
            },
            "Group Delay (ns)": {
                "limit_lines": {p: [] for p in self.params},
                "marks": {p: [] for p in self.params},
                "ui_refs": {p: {} for p in self.params}
            }
        }

        # Max 模式显示控制（复选框）
        self.show_param_vars = {p: tk.BooleanVar(value=True) for p in self.params}

        # Max 模式的图形对象引用
        self.max_frame = None
        self.max_fig = None
        self.max_ax = None
        self.max_canvas = None
        self.max_toolbar = None
        self.max_cids = {}

        # 新增：Axis 配置
        self.axis_configs = {
            "x_mode": tk.StringVar(value="Default"),
            "x_start": tk.StringVar(value="800"),
            "x_stop": tk.StringVar(value="1000"),
            "x_unit": tk.StringVar(value="MHz"),
            # === 新增 Max 模式统一 Y 轴控制变量 ===
            "unified_y_mode": tk.StringVar(value="Default"),
            "unified_y_min": tk.StringVar(value="-50"), 
            "unified_y_max": tk.StringVar(value="0")    
            # ==================================
        }
        self.y_configs = {}
        
        y_defaults = {
            "Magnitude (dB)": {"min": "-50", "max": "0"},
            "Phase (deg)": {"min": "-180", "max": "180"},
            "Group Delay (ns)": {"min": "0", "max": "10"}
        }
        for pt in SUPPORTED_PLOT_TYPES:
            self.y_configs[pt] = {}
            for p in self.params:
                default_min = y_defaults[pt]["min"]
                default_max = y_defaults[pt]["max"]
                self.y_configs[pt][p] = {
                    "mode": tk.StringVar(value="Default"),
                    "min": tk.StringVar(value=default_min),
                    "max": tk.StringVar(value=default_max)
                }
    
        # --- 新增：Marker Legend BBox 自定义配置 ---
        self.marker_legend_configs = {
            "boxstyle_var": tk.StringVar(value="Default"),
            "facecolor_var": tk.StringVar(value="Default"),
            "alpha_var": tk.StringVar(value="Default")
        }

        # 【新增】Marker Legend Position 统一刷新回调（用于 Custom 坐标框显示隐藏 + 重绘）
        self.normal_position_controls = {}
        self.max_position_controls = None
        self.normal_position_notebook = None
        self.max_position_frame = None
        
        # 为所有 plot_type 的 mode_var 添加统一 trace（避免重复添加）
        for pt in ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"]:
            for p in self.params:
                self.marker_pos_configs[pt][p]["mode_var"].trace_add("write", self._on_any_legend_mode_change)
            self.max_marker_pos_configs[pt]["mode_var"].trace_add("write", self._on_any_legend_mode_change)
            
        # 内部选项，用于 UI ComboBox
        # 注意：boxstyle 选项不包含 pad=0.3
        self.MARKER_LEGEND_BOXSTYLE_OPTIONS = ["round", "larrow", "rarrow", "darrow", "square", "round4", "sawtooth", "roundtooth"]
        # 边框样式(BoxStyle): round:标准圆角, round4:小圆角, square:直角矩形, larrow:左箭头, rarrow:右箭头, darrow:双箭头, roundtooth:圆锯齿, sawtooth:尖锯齿
        # 常用颜色
        self.MARKER_LEGEND_FACECOLOR_OPTIONS = ["red", "cyan", "blue", "none", "white", "black", "green", "brown", "yellow", "magenta", "lightgray"]
        # 景颜色(Facecolor): yellow: 亮黄色, cyan: 青色/蓝绿色, magenta: 洋红色/品红色, white: 白色, lightgray: 浅灰色/亮灰, blue: 标准蓝色, red: 标准红色, green: 标准绿色, brown: 棕色/咖啡色, black: 黑色明)
        # 常用透明度
        self.MARKER_LEGEND_ALPHA_OPTIONS = ["0.0", "0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9", "1.0"]
        #透明度(Alpha):0.0 表示完全透明, 1.0 表示完全不透明      
        # ----------------------------------------------------

    def _on_auto_font_color_change(self, *args):
        is_enabled = self.auto_font_color_enabled.get()

        facecolor_var = self.marker_legend_configs["facecolor_var"]
        alpha_var     = self.marker_legend_configs["alpha_var"]
        boxstyle_var  = self.marker_legend_configs["boxstyle_var"]

        if is_enabled:
            facecolor_var.set("none")
            alpha_var.set("0.0")
            boxstyle_var.set("round")           # 你选项里有 round
            state = "disabled"
        else:
            facecolor_var.set("Default")
            alpha_var.set("Default")
            boxstyle_var.set("Default")         # 现在你有 "Default" 了，完美！
            state = "readonly"

        # 三个下拉框全部同步禁用/启用
        for key in ('facecolor_combo', 'alpha_combo', 'boxstyle_combo'):
            combo = self.marker_legend_ui_refs.get(key)
            if combo:
                combo.config(state=state)

        self.update_plots()

    # ----------------------------------------------------
    def _safe_refresh_markers(self, reset_limits=True):
        """
        根据 reset_limits 标志执行图表刷新。
        如果 reset_limits=False (即 Disable Refresh 勾选)，则保存并恢复 Axes Limits，
        从而在刷新 Marker 标记的同时保持图表的缩放/平移状态，并修复 X/Y 轴刻度不协调的问题，
        同时统一应用细线网格。
        """
        # 1. 如果不需要重置 Limits，则临时保存当前所有图表的 Limits
        current_limits = {}
        if not reset_limits:
            try:
                if self.display_mode.get() == "Normal":
                    # 正常模式：保存四个子图的 Limits
                    for p in self.params:
                        if p in self.plot_configs and self.plot_configs[p]["ax"]:
                            ax = self.plot_configs[p]["ax"]
                            # 保存 (x_min, x_max, y_min, y_max)
                            current_limits[p] = ax.get_xlim() + ax.get_ylim()
                else:
                    # Max 模式：保存单一图表的 Limits
                    if self.max_ax:
                        current_limits["max"] = self.max_ax.get_xlim() + self.max_ax.get_ylim()
            except Exception as e:
                print(f"Error saving limits: {e}")
                
        # 2. 执行完整的绘制逻辑 (它会清除并重新绘制所有内容，包括 Marker)
        self.update_plots()

        # 3. 如果不需要重置，且 Limits 成功保存，则恢复 Limits 并修复刻度、添加细线
        if not reset_limits:
            try:
                if self.display_mode.get() == "Normal":
                    for p, limits in current_limits.items():
                        if p in self.plot_configs:
                            ax = self.plot_configs[p]["ax"]
                            ax.set_xlim(limits[0], limits[1])
                            ax.set_ylim(limits[2], limits[3])
                            
                            # ------------------------------------------------------------------
                            # --- [优化 1: 刻度修复] --- 恢复 Limits 后，强制使用 MaxNLocator 重新计算合理的刻度
                            ax.xaxis.set_major_locator(MaxNLocator(nbins=10, prune='both'))
                            ax.yaxis.set_major_locator(MaxNLocator(nbins=10, prune='both'))
                            
                            # --- [优化 2: 添加细线网格] ---
                            # AutoMinorLocator(2) 意味着主刻度之间加入一根细线
                            ax.xaxis.set_minor_locator(AutoMinorLocator(2))
                            ax.yaxis.set_minor_locator(AutoMinorLocator(2))
                            # 启用次网格线 (细线)
                            ax.grid(which='minor', linestyle=':', linewidth=0.5, color='gray', alpha=0.5)
                            # ------------------------------------------------------------------
                            
                            self.plot_configs[p]["canvas"].draw_idle()
                else:
                    if self.max_ax and "max" in current_limits:
                        limits = current_limits["max"]
                        self.max_ax.set_xlim(limits[0], limits[1])
                        self.max_ax.set_ylim(limits[2], limits[3])
                        
                        # ------------------------------------------------------------------
                        # --- [优化 1: 刻度修复] ---
                        # Max 模式使用 nbins=15 (与 on_scroll_zoom_combined 保持一致)
                        self.max_ax.xaxis.set_major_locator(MaxNLocator(nbins=15, prune='both'))
                        self.max_ax.yaxis.set_major_locator(MaxNLocator(nbins=15, prune='both'))
                        
                        # --- [优化 2: 添加细线网格] ---
                        self.max_ax.xaxis.set_minor_locator(AutoMinorLocator(2))
                        self.max_ax.yaxis.set_minor_locator(AutoMinorLocator(2))
                        # 启用次网格线 (细线)
                        self.max_ax.grid(which='minor', linestyle=':', linewidth=0.5, color='gray', alpha=0.5)
                        # ------------------------------------------------------------------
                        
                        self.max_canvas.draw_idle()
            except Exception as e:
                print(f"Error restoring limits: {e}")

    #def _on_any_legend_mode_change(self, *args):
    #    """统一处理 Normal 和 Max 模式的 mode_var 变化（显示/隐藏 Custom 输入框 + 刷新图表）"""
    #    self.update_marker_position_ui()  # 更新自定义坐标框显示状态
    #    if self.display_mode.get() == "Normal":
    #        self.update_plots()
    #    else:
    #        self.plot_combined()  # Max 模式刷新用 plot_combined

    def _on_any_legend_mode_change(self, *args):
        """统一处理 Normal 和 Max 模式的 mode_var 变化（显示/隐藏 Custom 输入框 + 刷新图表）"""
        self.update_marker_position_ui()  # 更新自定义坐标框显示状态
        
        # 【终极修复】：
        # 无论 Normal 还是 Max 模式，都统一调用 update_plots()。
        # 严禁在此处直接调用 plot_combined()！
        # 因为 update_plots() 内部拥有 "is_dragging + Disable Refresh" 的熔断保护机制。
        # 这样当拖拽开始自动切换为 "Custom" 模式时，图表不会被强制重绘，从而完美保留 Zoom。
        self.update_plots()
 
    # [新增功能] Limits Check 辅助方法
    def _check_dataset_limits(self, dataset, plot_type, param):
        """
        检查单个数据集是否违反给定参数的任何 Limit Line。
        
        Args:
            dataset (dict): 单个数据集，包含 's_data' 和 'freq'。
            plot_type (str): 当前的绘图类型 (如 "Magnitude (dB)")。
            param (str): S-参数名称 (如 "S11")。
            
        Returns:
            tuple: (is_pass: bool, has_freq_overlap: bool)
            is_pass: True if PASS, False if FAIL.
            has_freq_overlap: True if there was any frequency overlap 
                              between data and limit lines, False otherwise.
        """
        import numpy as np # 确保 numpy 可用

        limit_lines = self.data.get(plot_type, {}).get("limit_lines", {}).get(param, [])
        
        # 【新增】追踪是否有有效的频率重叠
        has_freq_overlap = False 
        
        if not limit_lines:
            # 无限制线，返回 (PASS, 无有效检查)
            return True, False 
            
        s_data = dataset['s_data'].get(param.lower())
        if s_data is None or len(s_data) < 2:
            # 无效或空数据，返回 (PASS, 无有效检查)
            return True, False 
            
        # 1. 准备 Y 轴数据和频率
        freq_hz = dataset['freq']
        y_data = None
        freq_mhz = None
        
        if plot_type == "Magnitude (dB)":
            y_data = 20 * np.log10(np.abs(s_data) + 1e-20)
            freq_mhz = freq_hz / 1e6
        elif plot_type == "Phase (deg)":
            y_data = np.unwrap(np.angle(s_data)) * 180 / np.pi
            freq_mhz = freq_hz / 1e6
        elif plot_type == "Group Delay (ns)":
            try:
                # 假设您已定义 calculate_group_delay，并且它返回 (y_data, freq_mhz)
                y_data, freq_mhz = self.calculate_group_delay(freq_hz, s_data)
            except AttributeError:
                # 无法计算群延迟，返回 (PASS, 无有效检查)
                return True, False
        else:
            return True, False # 未知绘图类型

        if y_data is None or len(y_data) == 0:
             return True, False # 无效数据，默认通过

        # 2. 检查限制线
        for line in limit_lines:
            try:
                # 从 Tkinter 变量中获取值
                lower = float(line["lower"].get())
                upper = float(line["upper"].get())
                ltype = line["type"].get()
                
                start_val = float(line["start"].get())
                start_unit = line["start_unit"].get() 
                stop_val = float(line["stop"].get())
                stop_unit = line["stop_unit"].get()
                
                # 统一转换到 MHz
                start_mhz = start_val * 1000 if start_unit == "GHz" else start_val
                stop_mhz = stop_val * 1000 if stop_unit == "GHz" else stop_val
                
                f_min = min(start_mhz, stop_mhz)
                f_max = max(start_mhz, stop_mhz)
                
                # 确定在限制线频率范围内的有效数据
                freq_mask = (freq_mhz >= f_min) & (freq_mhz <= f_max)
                
                if not np.any(freq_mask):
                    continue # 此限制线与数据无频率重叠，跳过此行
                
                # 【核心修复】: 只要有一条限制线与数据有频率重叠，就标记为 True
                has_freq_overlap = True
                
                y_data_masked = y_data[freq_mask]
                check_freq_mhz = freq_mhz[freq_mask] # 获取需要检查的频率点
                
                # ----------------------------------------------------
                # 【FIX: Limits Check 线性插值】
                # ----------------------------------------------------
                if abs(stop_mhz - start_mhz) < 1e-6:
                    # 频率相同，无法计算斜率，使用 lower/upper 作为恒定 Y 值
                    # 此时假设 Lower 和 Upper 必须相等，否则 Limit 定义不合理
                    if abs(lower - upper) > 1e-6:
                        continue # 频率范围为零，但 Y 值不同，跳过
                    
                    limit_y_array = np.full_like(check_freq_mhz, upper)
                else:
                    # 计算斜率 m，并对所有 check_freq_mhz 点进行线性插值
                    m = (upper - lower) / (stop_mhz - start_mhz)
                    # Y_limit(f) = lower + m * (f - start_mhz)
                    limit_y_array = lower + m * (check_freq_mhz - start_mhz)
                
                # --- 检查违规 ---
                violation = False
                
                if ltype in ["Max", "Band", "Upper Only", "Upper/Lower", "Upper Limit"]:
                    # FIX: 用 limit_y_array 替换标量 upper
                    if np.any(y_data_masked > limit_y_array):
                        violation = True

                if ltype in ["Min", "Band", "Lower Only", "Upper/Lower", "Lower Limit"]:
                    # FIX: 用 limit_y_array 替换标量 lower
                    if np.any(y_data_masked < limit_y_array):
                        violation = True
                        
                if violation:
                    # 发现任何违规，立即返回 (FAIL, 有效检查)
                    return False, True 

            except ValueError:
                # 忽略无效的限制线输入值
                continue
                
        # 所有限制线都检查通过，返回 (PASS, has_freq_overlap)。
        # 如果 has_freq_overlap 为 False，调用者将判为 N/A_NoOverlap。
        return True, has_freq_overlap

    # [新增功能] Limits Check status 辅助方法
    def _draw_limit_check_status(self, ax, check_results):
        """
        在 Matplotlib Axes 的右下角绘制 Limits Check 状态。

        Args:
            ax (Axes): Matplotlib Axes 对象。
            check_results (list): 包含 {'name': str, 'status': 'PASS'|'FAIL'|'N/A_NoLimits'|'N/A_NoData'|'N/A_NoOverlap'} 的列表。
        """
        
        # 提取需要显示的行
        txt_lines = []
        is_fail_overall = False
        # 追踪是否有需要显示的多行结果，包括 PASS/FAIL/N/A_NoData/N/A_NoOverlap
        has_limit_check_results = False 
        
        for res in check_results:
            name = res['name']
            status = res['status']
            
            if status == 'FAIL':
                line = f"{name} (FAIL)"
                is_fail_overall = True
                has_limit_check_results = True
            elif status == 'PASS':
                line = f"{name} (PASS)"
                has_limit_check_results = True
            elif status == 'N/A_NoData':
                line = f"{name} N/A (No Data)" # 优化显示文本
                has_limit_check_results = True
            elif status == 'N/A_NoOverlap': # 【新增处理：无频率重叠】
                line = f"{name} N/A (No Freq Overlap)"
                has_limit_check_results = True
            # N/A_NoLimits (整个图表没有限制线) 不会在多行显示中出现，而是单独判断
            
            if status != 'N/A_NoLimits':
                txt_lines.append(line)


        # 1. 判断最终显示状态 (N/A 优先级最高)
        na_statuses = ['N/A_NoLimits', 'N/A_NoData', 'N/A_NoOverlap'] # 新增 'N/A_NoOverlap'
        if not self.datasets or all(res['status'] in na_statuses for res in check_results) or not has_limit_check_results:
            # 如果没有数据集，或者所有文件状态都是 N/A (包括 NoOverlap)，或者整个图表没有限制线
            status_text = "N/A"
            color = 'gray'
            has_limit_check = False
        else:
            # 2. 显示多行结果
            status_text = "\n".join(txt_lines)
            color = 'red' if is_fail_overall else 'green'
            has_limit_check = True


        # 坐标: (0.98, 0.05) 是 Axes 坐标系的归一化位置 (右下角)
        ax.text(0.98, 0.05, status_text,
                transform=ax.transAxes,
                fontsize=9, 
                fontweight='bold',
                color='black', # 文本颜色设置为黑色，背景框颜色表示状态
                ha='right', # 文本框右对齐到 0.98
                va='bottom',
                multialignment='left', # 文本内容左对齐
                bbox=dict(facecolor='white' if not has_limit_check else '#fcfdbe', # N/A/无数据用白色
                          alpha=0.8, 
                          edgecolor=color if has_limit_check else 'gray', 
                          boxstyle="round,pad=0.3"),
                zorder=10)


    def _update_max_marker_display(self, redraw_points=True):
        """
        仅更新 Max 模式下的 Marker 点和 Marker Legend (黄色信息框)。
        在 Auto Refresh Disabled 时被调用。
        """
        if not self.max_ax or not self.max_canvas:
            return

        ax = self.max_ax
        plot_type = self.plot_type.get()
        visible_params = [p for p in self.params if self.show_param_vars[p].get()]

        # ----------------------------------------------------
        # 1. 清除旧的 Marker Legend Text Artist
        # ----------------------------------------------------
        if hasattr(self, 'max_marker_legend_artists') and plot_type in self.max_marker_legend_artists and self.max_marker_legend_artists[plot_type]:
            try:
                self.max_marker_legend_artists[plot_type].remove()
                self.max_marker_legend_artists[plot_type] = None
            except:
                pass
        
        # ----------------------------------------------------
        # 2. 清除旧的 Marker 点和 Annotation Artists (关键!)
        # ----------------------------------------------------
        if hasattr(self, 'max_marker_artists'):
            for artist in self.max_marker_artists:
                try:
                    artist.remove()
                except:
                    pass
            self.max_marker_artists = []
            
        # ----------------------------------------------------
        # 3. 重新获取 X/Y 轴限制和 Y 轴单位
        # ----------------------------------------------------
        try:
            # 当前图表显示的频率范围 (MHz)
            x_min_mhz, x_max_mhz = ax.get_xlim()
        except Exception:
            return
            
        y_unit = ""
        if plot_type == "Magnitude (dB)": y_unit = "dB"
        elif plot_type == "Phase (deg)": y_unit = "deg"
        elif plot_type == "Group Delay (ns)": y_unit = "ns"
        
        marker_info_list = []

        # ----------------------------------------------------
        # 4. 重新执行 plot_combined 中的 Marker 绘制逻辑 (步骤 9)
        # ----------------------------------------------------
        if plot_type in self.data:
            for p in visible_params:
                for mark in self.data[plot_type]["marks"].get(p, []):
                    try:
                        target_freq_hz = self._get_marker_freq_hz(mark)
                        f_str = mark["freq"].get()
                        unit = mark["unit"].get()
                        x_display = f"{f_str} {unit}"
                        mark_id = mark['id']
                        selected_data_id = mark["data_id"].get()
                        
                        dataset = next((d for d in self.datasets if str(d['id']) == selected_data_id), None)
                        if not dataset or dataset['s_data'].get(p.lower()) is None:
                            continue
                            
                        s_data = dataset['s_data'][p.lower()]
                        freq = dataset['freq']
                        
                        data_array = None
                        if plot_type == "Magnitude (dB)":
                            data_array = 20 * np.log10(np.abs(s_data) + 1e-20)
                        elif plot_type == "Phase (deg)":
                            data_array = np.unwrap(np.angle(s_data)) * 180 / np.pi
                        elif plot_type == "Group Delay (ns)":
                            data_array, _ = self.calculate_group_delay(freq, s_data)
        
                        if data_array is None or len(freq) < 2:
                            continue
                            
                        # --------------------- 【优化 1: 频率范围检查和插值】 ---------------------
                        min_f_hz = freq[0]
                        max_f_hz = freq[-1]
                        # Marker 是否在 S2P 文件的频率范围内
                        marker_is_in_data_range = (target_freq_hz >= min_f_hz) and (target_freq_hz <= max_f_hz)
                        
                        val = None
                        if marker_is_in_data_range:
                            # 仅在 S2P 数据范围内时尝试插值
                            val = self.safe_interp(target_freq_hz, freq, data_array)
                            
                        # --------------------- 【优化 2: 准备 Legend Y 值】 ---------------------
                        color = self.get_max_mode_color(dataset['id'], p)
                        custom_name = self.custom_id_names.get(selected_data_id, f"ID {selected_data_id}")	
                        
                        # Legend 文本 Y 值
                        y_str = ""
                        if val is not None and marker_is_in_data_range:
                            y_str = f"{val:.3f} {y_unit}"
                        else:
                            # 如果不在数据范围内或插值失败，Legend 上显示 N/A
                            y_str = "Out of Freq Range"
                            
                        # --------------------- 【优化 3: 收集 Legend 信息】 ---------------------
                        full_legend_text = f"{mark['id']} ({p} {custom_name}) @{x_display}, {y_str}"
                        marker_info_list.append((mark['id'], p, full_legend_text, selected_data_id))
                        
                        # --------------------- 【优化 4: 绘制跳过逻辑 V2.0 - 严格模式】 ---------------------
                        
                        # 必须满足：1. 在 S2P 数据范围内 (marker_is_in_data_range)
                        #         2. 插值成功 (val is not None)
                        if not marker_is_in_data_range or val is None: 
                            continue 
                            
                        x_pt_original = target_freq_hz / 1e6 # 转换成 MHz
                        
                        # 必须满足：3. 在图表当前的 X 轴显示范围内 (x_min_mhz to x_max_mhz)
                        marker_is_in_plot_range = (x_pt_original >= x_min_mhz) and (x_pt_original <= x_max_mhz)
                        
                        if not marker_is_in_plot_range:
                            # 严格跳过：即使在数据范围内，如果超出图表显示范围，也不绘制点和标注
                            continue 
                            
                        # --------------------- 【优化 5: 绘制 Marker 点和标注 (仅在数据和显示范围内)】 ---------------------
                        y_pt = val 
                        x_pt_plot = x_pt_original # 此时 x_pt_original 已经在可见范围内，无需钳位
                        
                        # Draw marker (使用 ax=self.max_ax)
                        marker_line = ax.plot(x_pt_plot, y_pt, '.', markerfacecolor='none', markeredgecolor=color,	
                                               markersize=4, markeredgewidth=2, zorder=5)
                        marker_text = ax.annotate(mark['id'], xy=(x_pt_plot, y_pt), xytext=(5, 5),
                                                   textcoords='offset points', fontsize=9, color=color,
                                                   zorder=6)

                        # 添加到 Artist 列表以便下次清除
                        if not hasattr(self, 'max_marker_artists'):
                            self.max_marker_artists = []
                        self.max_marker_artists.extend(marker_line)
                        self.max_marker_artists.append(marker_text)
                            
                    except Exception:
                        pass
        
        # ----------------------------------------------------
        # 5. 重新执行 plot_combined 中的 Marker Legend 逻辑 (步骤 11 & 12)
        # ----------------------------------------------------
        if marker_info_list:
            
            PARAM_ORDER = {'S11': 0, 'S21': 1, 'S12': 2, 'S22': 3}
            
            def max_mode_sort_key(info):
                param_str = info[1]
                data_id_str = info[3]
                
                try: data_id_number = int(data_id_str)
                except ValueError: data_id_number = 9999
                        
                param_index = PARAM_ORDER.get(param_str, 99)
                return (data_id_number, param_index)

            sorted_markers = sorted(marker_info_list, key=max_mode_sort_key)
            marker_legend_text = [info[2] for info in sorted_markers]
            txt = "\n".join(marker_legend_text)
            
            # 绘制 Marker Legend 文本框
            pos_config = self.max_marker_pos_configs[plot_type]
            mode = pos_config["mode_var"].get()
            x_val, y_val, h_align, v_align = 0.98, 0.98, 'right', 'top'	

            if mode == "Top Left": x_val, y_val, h_align, v_align = 0.02, 0.98, 'left', 'top'
            elif mode == "Top Right": x_val, y_val, h_align, v_align = 0.98, 0.98, 'right', 'top'
            elif mode == "Bottom Left": x_val, y_val, h_align, v_align = 0.02, 0.02, 'left', 'bottom'
            elif mode == "Bottom Right": x_val, y_val, h_align, v_align = 0.98, 0.02, 'right', 'bottom'
            elif mode == "Center": x_val, y_val, h_align, v_align = 0.5, 0.5, 'center', 'center'
            elif mode == "Custom":
                try:
                    x_val = float(pos_config["x_var"].get())
                    y_val = float(pos_config["y_var"].get())
                    h_align = 'left' if x_val < 0.5 else 'right'
                    v_align = 'bottom' if y_val < 0.5 else 'top'
                    if x_val == 0.5: h_align = 'center'
                    if y_val == 0.5: v_align = 'center'
                except:
                    pass	
                    
            # 获取自定义 Marker Legend BBox 参数 (新增)
            bbox_params = self._get_marker_legend_bbox_params()
            
            txt_artist = ax.text(x_val, y_val, txt, transform=ax.transAxes, fontsize=9,
                                 verticalalignment=v_align, horizontalalignment=h_align,
                                 multialignment='left',
                                 bbox=bbox_params, zorder=7) # 使用自定义参数
            #---------------------------------------------------	 	
        
        # 6. 更新 Marker Artist 引用
        if not hasattr(self, 'max_marker_legend_artists'):
            self.max_marker_legend_artists = {}	
            
        # 7. 刷新画布
        self.max_canvas.draw()
    #------------------------------------------   
 
    #获取date information
    def _generate_filename(self):
        """
        根据 Plot Title 和当前时间日期生成一个安全的文件名。
        格式: Plot_Title_YYYYMMDD_HHMMSS
        """
        import datetime # 确保函数内也能访问 datetime
        import re       # 确保函数内也能访问 re
        
        # 1. 获取 Plot Title
        plot_title = self.title_var.get()
        
        # 2. 清理 Plot Title，移除不安全字符，替换非安全字符为下划线
        # \w 匹配字母、数字、下划线。\u4e00-\u9fa5 匹配中文。
        safe_title = re.sub(r'[^\w\u4e00-\u9fa5\-\_]', '_', plot_title).strip('_')
        # 如果 title 为空或全是非法字符，使用默认名称
        if not safe_title:
             safe_title = "Plot" 
        
        # 3. 获取当前时间日期
        now = datetime.datetime.now()
        datetime_str = now.strftime("%Y%m%d_%H%M%S")
        
        # 4. 组合文件名 (例如: SN-001_20251111_123456)
        filename = f"{safe_title}_{datetime_str}"
        
        return filename
 
    def setup_ui(self):
        main_frame = tk.Frame(self.root, bg="#f0f2f5")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        content_frame = tk.Frame(main_frame, bg="#f0f2f5")
        content_frame.pack(fill="both", expand=True)

        content_frame.grid_columnconfigure(0, weight=1)
        content_frame.grid_columnconfigure(1, weight=0)
        content_frame.grid_rowconfigure(0, weight=1)

        # Notebook (左侧)
        self.notebook = ttk.Notebook(content_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self.chart_tab = tk.Frame(self.notebook, bg="#f0f2f5")
        self.notebook.add(self.chart_tab, text=" S-Parameter Plots ")
        self.setup_chart_tab()

        self.create_data_information_tab()
        self.create_axis_control_tab()
        self.create_limit_mark_tab(self.plot_type.get())

        # 右侧垂直控制区
        vertical_control_frame = tk.Frame(content_frame, bg="#f0f2f5", width=300)
        vertical_control_frame.grid(row=0, column=1, sticky="ns")

        control_stack_frame = tk.Frame(vertical_control_frame, bg="#f0f2f5")
        # 移除原代码中的冗余 pack，仅保留此处的 pack
        control_stack_frame.pack(fill="x", side="top", padx=5, pady=5)
        
        # --------------------------------------------------------------------------
        # 【注意】原代码中调用了 self._setup_s_param_display_controls(control_stack_frame) 
        # 但紧接着又在 display_mode_group 中手动创建了 self.cb_frame 及其内容。
        # 最佳实践是仅保留其中一种方式，这里将手动创建的 UI 逻辑优化并保留。
        # --------------------------------------------------------------------------

        # Serial Number改为Plot Title
        sn_group = tk.LabelFrame(control_stack_frame, text="Plot Title:", 
                                 font=("sans-serif", 10, "bold"), 
                                 bg="#f0f2f5")
        sn_group.pack(fill="x", padx=5, pady=2)
        
        left_margin = 20
        
        tk.Entry(sn_group, textvariable=self.title_var, font=("Arial", 10), width=18).pack(fill="x", padx=5, pady=(0, 5))

        # File Operations
        file_ops_group = tk.LabelFrame(control_stack_frame, text="File Operations", font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        file_ops_group.pack(fill="x", padx=5, pady=2)
        tk.Button(file_ops_group, text="Load S2P File", font=("sans-serif", 10, "bold"),
                      bg="#4CAF50", fg="white", relief="flat", anchor="w",
                      padx=left_margin, pady=6, command=self.load_s2p)\
                .pack(fill="x", padx=5, pady=2)

        # 新增 Frame 用于放置 Clear Data 和 Reset App 按钮 (放在同一行)
        clear_reset_frame = tk.Frame(file_ops_group, bg="#f0f2f5")
        clear_reset_frame.pack(fill="x", padx=5, pady=2)  

        # Clear Data 按钮
        tk.Button(clear_reset_frame, text="Clear Data", font=("sans-serif", 9, "bold"), bg="#e74c3c", fg="white", relief="flat", padx=1, pady=6, command=self.clear_all_datasets)\
        .pack(side="left", fill="x", expand=True, padx=(0, 2), pady=0)  

        # Reset App 按钮
        tk.Button(clear_reset_frame, text="Reset App", font=("sans-serif", 9, "bold"), bg="#3F51B5", fg="white", relief="flat", padx=1, pady=6, command=self.reset_application)\
        .pack(side="left", fill="x", expand=True, padx=(2, 0), pady=0)

        # Plot Type
        plot_type_group = tk.LabelFrame(control_stack_frame, text="Plot Type", font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        plot_type_group.pack(fill="x", padx=5, pady=2)
        plot_values = ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"]
        plot_combo = ttk.Combobox(plot_type_group, textvariable=self.plot_type, values=plot_values, state="readonly")
        plot_combo.pack(fill="x", padx=5, pady=2)

        # Display Mode (新增)
        display_mode_group = tk.LabelFrame(control_stack_frame, text="Display Mode", font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        display_mode_group.pack(fill="x", padx=5, pady=2)
        display_combo = ttk.Combobox(display_mode_group, textvariable=self.display_mode, values=["Normal", "Max"], state="readonly")
        display_combo.pack(fill="x", padx=5, pady=(8, 5))

        # Show Params (Normal Mode)
        # 【优化】将 Show Params 作为一个 LabelFrame 容器
        self.cb_frame = tk.LabelFrame(display_mode_group, text="Show Params", 
                                      font=("sans-serif", 10, "bold"), bg="#f0f2f5") 
        self.cb_frame.pack_forget() # 默认隐藏
        
        inner_param_frame = tk.Frame(self.cb_frame, bg="#f0f2f5")
        inner_param_frame.pack(fill="x", padx=5, pady=2)

        # 两行两列布局
        param_grid = [["S11", "S21"], ["S12", "S22"]]
        for r, row_params in enumerate(param_grid):
            for c, p in enumerate(row_params):
                # 【修改点】：移除 command=self.on_show_param_change
                chk = tk.Checkbutton(inner_param_frame, text=p, variable=self.show_param_vars[p], 
                                     bg="#f0f2f5", anchor="w")
                chk.grid(row=r, column=c, sticky="w", padx=(5, 15))
        
        # 确保 grid 容器能扩展
        inner_param_frame.grid_columnconfigure(0, weight=1)
        inner_param_frame.grid_columnconfigure(1, weight=1)

        # Refresh
        # [MODIFICATION] 使用 lambda 包装 command，使其在刷新时重置 Disable Refresh 状态
        def refresh_plots_and_reset_flag():
            """执行刷新操作，并重置 'Disable Refresh' 状态为 False。"""
            self.disable_refresh_var.set(False)
            self.update_plots()
            
        # Refresh Plots
        refresh_ops_group = tk.LabelFrame(control_stack_frame, text="Refresh", font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        refresh_ops_group.pack(fill="x", padx=5, pady=2)
        tk.Button(refresh_ops_group, text="Refresh Plots", font=("sans-serif", 10, "bold"),
                      bg="#FF9800", fg="white", relief="flat", anchor="w",
                      padx=left_margin, pady=6, command=refresh_plots_and_reset_flag)\
                .pack(fill="x", padx=5, pady=2)
            

        # 将原有的三个独立控制组合并到“一区功能区” (Feature Controls)
        combined_feature_group = tk.LabelFrame(control_stack_frame, text="Feature Controls",
                                                    font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        combined_feature_group.pack(fill="x", padx=5, pady=2)

        # 使用一个内部Frame来容纳所有Checkbutton
        inner_combined_frame = tk.Frame(combined_feature_group, bg="#f0f2f5")
        inner_combined_frame.pack(anchor='w', fill='x', padx=5, pady=2)

        # 1. Add Tag Control: Enable Add Tag
        tk.Checkbutton(inner_combined_frame,
                                  text="Enable Add Tag",
                                  variable=self.marker_click_enabled,
                                  bg="#f0f2f5",
                                  anchor='w', 
                                  justify='left').pack(anchor='w', padx=(5, 0), pady=0)  

        # 2. Auto Refresh: Disable Refresh
        tk.Checkbutton(inner_combined_frame,
                                  text="Disable Refresh",
                                  variable=self.disable_refresh_var,
                                  bg="#f0f2f5",
                                  anchor='w', 
                                  justify='left').pack(anchor='w', padx=(5, 0), pady=0)

        # 3. Limits Check: Enable Limits Check
        tk.Checkbutton(inner_combined_frame,
                                  # 为了清晰，将 " Enable Check" 改为 "Enable Limits Check"
                                  text="Enable Limits Check", 
                                  variable=self.limits_check_enabled,
                                  bg="#f0f2f5",
                                  anchor='w',
                                  justify='left',
                                  command=self.update_plots).pack(anchor='w', padx=(5, 0), pady=0)

        # 4. Auto Font Color: Enable Marker Auto Font Color
        tk.Checkbutton(inner_combined_frame,
                                text="Sync Marker Color",
                                variable=self.auto_font_color_enabled,
                                bg="#f0f2f5",
                                anchor='w',
                                justify='left',
                                command=self._on_auto_font_color_change).pack(anchor='w', padx=(5, 0), pady=0)
                                
        # Chart ops
        chart_ops_group = tk.LabelFrame(control_stack_frame, text="Chart Output", font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        chart_ops_group.pack(fill="x", padx=5, pady=2)

        # 新增 Frame 用于放置 Copy Plots 和 Save Image 按钮 (放在同一行)
        copy_save_frame = tk.Frame(chart_ops_group, bg="#f0f2f5")
        copy_save_frame.pack(fill="x", padx=5, pady=2)
        # Copy Plots 按钮
        tk.Button(copy_save_frame, text="Copy Plots", font=("sans-serif", 9, "bold"), bg="#FF5722", fg="white", relief="flat", padx=1, pady=6, command=self.copy_all_charts)\
        .pack(side="left", fill="x", expand=True, padx=(0, 2), pady=0)
        # Save Image 按钮
        tk.Button(copy_save_frame, text="Save Image", font=("sans-serif", 9, "bold"), bg="#9C27B0", fg="white", relief="flat", padx=1, pady=6, command=self.save_chart)\
        .pack(side="left", fill="x", expand=True, padx=(2, 0), pady=0)

        # --- Legend frame ---
        self.legend_frame = tk.LabelFrame(vertical_control_frame, text="Legend (Data ID)",
                                             font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        self.legend_content = tk.Frame(self.legend_frame, bg="#f0f2f5")
        self.legend_content.pack(fill="x", padx=5, pady=5)

        # --- Cursor Coordinates frame ---
        self.cursor_frame = tk.LabelFrame(vertical_control_frame, text="Cursor Coordinates",
                                             font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        self.cursor_content = tk.Label(self.cursor_frame, text="X: ---, Y: ---",
                                           font=("sans-serif", 9), bg="#f0f2f5", anchor="w", fg="#333333")
        self.cursor_content.pack(fill="x", padx=5, pady=5)

        # 默认显示顺序：Legend 在上，Cursor Coordinates 在下
        self.cursor_frame.pack(fill="x", padx=5, pady=(5, 0), side="bottom")
        self.legend_frame.pack(fill="x", padx=5, pady=(5, 0), side="bottom")

        # Status bar
        self.status_var = tk.StringVar(value="Please load S2P file(s)...")
        tk.Label(main_frame, textvariable=self.status_var, font=("sans-serif", 10),
                     bg="#e0e0e0", anchor="w", relief="sunken").pack(side="bottom", fill="x", pady=(10, 0))
        tk.Label(main_frame, text="© 2025 S-View | Created By Arthur Gu", font=("sans-serif", 9),
                     bg="#f0f2f5", fg="gray").pack(side="bottom", pady=10, anchor="center")

        # 【修复 Bug 1】 
        # 将 on_display_mode_change 移至 self.status_var 初始化之后，
        # 避免启动时调用 update_plots 找不到 self.status_var 的错误。
        self.on_display_mode_change()

    def create_axis_control_tab(self):
        if hasattr(self, 'axis_control_tab'):
            return
        self.axis_control_tab = tk.Frame(self.notebook, bg="#f0f2f5")
        # 插入到 Data Information Tab 后面 (index 1 的下一个位置)
        try:
            data_index = self.notebook.index(self.data_information_tab)
            self.notebook.insert(data_index + 1, self.axis_control_tab, text="Axis Control")
        except tk.TclError:
            self.notebook.add(self.axis_control_tab, text=" Axis Control ")

        # X Axis 控制
        x_frame = tk.LabelFrame(self.axis_control_tab, text="X Axis Control", font=("sans-serif", 10), bg="#f0f2f5")
        x_frame.pack(fill="x", padx=15, pady=10)

        x_mode_var = self.axis_configs["x_mode"]

        # --- 1. 模式选择 Frame ---
        x_mode_frame = tk.Frame(x_frame, bg="#f0f2f5")
        #修改X Axis Control容器显示高度
        #x_mode_frame.pack(fill="x", padx=10, pady=(5, 0))
        x_mode_frame.pack(pady=12, padx=10, anchor="w")        
        

        tk.Label(x_mode_frame, text="Mode:", bg="#f0f2f5", 
                 font=("sans-serif", 10)).pack(side="left", padx=(0, 5))
        
        # X 轴模式选择：Default / Custom
        x_mode_combo = ttk.Combobox(x_mode_frame, textvariable=x_mode_var, 
                                     values=["Default", "Custom"], state="readonly", width=10)
        x_mode_combo.pack(side="left", padx=5)

        # --- 2. 自定义 X 轴 Start/Stop 输入框和 Apply 按钮 Frame ---
        custom_x_frame = tk.Frame(x_frame, bg="#f0f2f5")
        # 初始状态由回调函数控制

        # Start频率
        tk.Label(custom_x_frame, text="Start:", bg="#f0f2f5").pack(side="left", padx=(0, 5))
        tk.Entry(custom_x_frame, textvariable=self.axis_configs["x_start"], width=9).pack(side="left", padx=5)

        # Stop频率
        tk.Label(custom_x_frame, text="Stop:", bg="#f0f2f5").pack(side="left", padx=(20, 5))
        tk.Entry(custom_x_frame, textvariable=self.axis_configs["x_stop"], width=9).pack(side="left", padx=5)
        
        # 频率单位选择
        ttk.Combobox(custom_x_frame, textvariable=self.axis_configs["x_unit"], 
                     values=["MHz", "GHz"], state="readonly", width=6).pack(side="left", padx=5)
        
        # Apply Button (同步到绘图函数)
        tk.Button(custom_x_frame, text="Apply",
                  command=self.update_plots, width=10).pack(side="left", padx=(20, 5))

        # --- 3. 动态显示/隐藏逻辑 ---
        def on_x_mode_change(*args):
            current_mode = x_mode_var.get()
            if current_mode == "Custom":
                custom_x_frame.pack(fill="x", padx=9, pady=(0, 10))
            else:
                custom_x_frame.pack_forget()
        
        # 绑定回调函数到模式变量
        x_mode_var.trace_add("write", on_x_mode_change)
        
        # 初始调用以设置正确的可见性
        on_x_mode_change()

        # Y Axis 控制 主容器 (用于Normal/Max模式切换)
        y_control_container = tk.Frame(self.axis_control_tab, bg="#f0f2f5")
        y_control_container.pack(fill="both", expand=True, padx=15, pady=10)
        
        # --- 1. Normal 模式的四个独立 Y 轴控制 ---
        self.normal_y_control_frame = tk.LabelFrame(y_control_container, 
                                                text="Y Axis Control (per Plot Type & Parameter)", 
                                                font=("sans-serif", 10), bg="#f0f2f5")
        # 默认显示 Normal 模式
        self.normal_y_control_frame.pack(fill="both", expand=True) 
        
        # 沿用原有的子 Notebook，但父容器指向新的 frame
        self.y_sub_notebook = ttk.Notebook(self.normal_y_control_frame)
        self.y_sub_notebook.pack(fill="both", expand=True)
        
        # --- 绑定事件以禁用手动切换 ---
        self.y_sub_notebook.bind("<<NotebookTabChanged>>", self._prevent_y_axis_notebook_switch)
        # ------------------------------------

        # --- 2. Max 模式的统一 Y 轴控制 (新增) ---
        self.unified_y_control_frame = tk.LabelFrame(y_control_container, 
                                                    text="Unified Y Axis Control (Max Mode)", 
                                                    font=("sans-serif", 10), bg="#f0f2f5")
        # 调用新增方法创建统一控制 UI
        self._setup_unified_y_control_ui(self.unified_y_control_frame)
        # 注意: 默认 pack_forget()，由 on_display_mode_change 控制显示/隐藏
        # self.unified_y_control_frame.pack_forget() 
        # ------------------------------------
        SUPPORTED_PLOT_TYPES = ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"]
        for pt in SUPPORTED_PLOT_TYPES:
            pt_tab = tk.Frame(self.y_sub_notebook, bg="#f0f2f5")
            self.y_sub_notebook.add(pt_tab, text=pt)

            # Per param frames
            for p in self.params:
                # 每个参数配置的 LabelFrame
                p_y_frame = tk.LabelFrame(pt_tab, text=f"{p} Y Limits", font=("sans-serif", 10), bg="#f0f2f5")
                p_y_frame.pack(fill="x", padx=10, pady=5)

                # 获取该 S 参数的配置字典
                config = self.y_configs[pt][p]
                
                # --- 1. 模式选择 Frame (统一风格) ---
                mode_frame = tk.Frame(p_y_frame, bg="#f0f2f5")
                #修改Y Axis Control容器显示高度
                #mode_frame.pack(fill="x", padx=10, pady=(5, 0))
                mode_frame.pack(pady=12, padx=10, anchor="w")

                tk.Label(mode_frame, text=f"{p} Mode:", bg="#f0f2f5", 
                         font=("sans-serif", 10)).pack(side="left", padx=(0, 5))
                
                # Y 轴模式选择：Default / Custom
                mode_combo = ttk.Combobox(mode_frame, textvariable=config["mode"], 
                                          values=["Default", "Custom"], state="readonly", width=10)
                mode_combo.pack(side="left", padx=5)


                # --- 2. 自定义 Y 轴 Min/Max 输入框 和 Apply 按钮 Frame ---
                custom_y_frame = tk.Frame(p_y_frame, bg="#f0f2f5")
                # custom_y_frame.pack(fill="x", padx=10, pady=(0, 10)) # 初始状态由回调函数决定
                
                # Y_Min (注意这里 Min 和 Max 的位置与您原代码中的顺序，我们保持 Min-Max 顺序以匹配 Max 模式风格)
                tk.Label(custom_y_frame, text="Max:", bg="#f0f2f5").pack(side="left", padx=(0, 5))
                tk.Entry(custom_y_frame, textvariable=config["max"], width=10).pack(side="left", padx=5)

                # Y_Max
                tk.Label(custom_y_frame, text="Min:", bg="#f0f2f5").pack(side="left", padx=(20, 5))
                tk.Entry(custom_y_frame, textvariable=config["min"], width=10).pack(side="left", padx=5)

                # Apply Button (同步到绘图函数)
                tk.Button(custom_y_frame, text="Apply",
                          command=self.update_plots, width=10).pack(side="left", padx=(20, 5))


                # --- 3. 动态显示/隐藏逻辑 ---
                # 定义并立即绑定到模式变量
                def on_y_mode_change(*args, frame_to_toggle=custom_y_frame, mode_var=config["mode"]):
                    current_mode = mode_var.get()
                    if current_mode == "Custom":
                        frame_to_toggle.pack(fill="x", padx=10, pady=(0, 10))
                    else:
                        frame_to_toggle.pack_forget()

                config["mode"].trace_add("write", on_y_mode_change)
                
                # 确保初始状态正确（调用一次）
                on_y_mode_change() 
                
        # ------------------------------------
        
        # 绑定变化事件 (保留原代码中的 on_axis_change 绑定)
        self.axis_configs["x_mode"].trace_add("write", self.on_axis_change)
        for pt in SUPPORTED_PLOT_TYPES:
            for p in self.params:
                # 注意：这里我们移除了对 mode 的重复绑定，因为我们已经在循环中使用了 trace_add
                # 但是为了兼容您原代码的 on_axis_change，如果它有其他用途，我们可以保留
                # 如果 on_axis_change 只用于触发 update_plots，则保留原代码：
                if pt in self.y_configs and p in self.y_configs[pt]:
                     self.y_configs[pt][p]["mode"].trace_add("write", self.on_axis_change)

        # 绑定变化事件
        self.axis_configs["x_mode"].trace_add("write", self.on_axis_change)
        for pt in SUPPORTED_PLOT_TYPES:
            for p in self.params:
                self.y_configs[pt][p]["mode"].trace_add("write", self.on_axis_change)

    def on_axis_change(self, *args):
        self.update_plots()

    def _prevent_y_axis_notebook_switch(self, event):
        """
        阻止用户手动切换 Y Axis Control 子 Notebook 的标签页，
        强制其始终与当前 Plot Type 保持一致。
        """
        # 获取当前选择的标签页索引
        current_selection = self.y_sub_notebook.index(self.y_sub_notebook.select())
        
        # 获取所有标签页的标题
        tab_titles = [self.y_sub_notebook.tab(i, "text").strip() for i in self.y_sub_notebook.tabs()]
        
        plot_type = self.plot_type.get()
        
        try:
            # 找到正确标签页的索引
            correct_index = tab_titles.index(plot_type)
        except ValueError:
            # 如果 Plot Type 不在标签中（理论上不应该发生），则退出
            return
            
        # 如果当前选择的不是正确的标签页
        if current_selection != correct_index:
            # 强制切换回正确的标签页
            # 使用 self.root.after(0, ...) 确保在 Notebook 完成其默认的切换操作后，
            # 立即执行强制切换，从而覆盖用户的点击效果。
            self.root.after(1, lambda: self.y_sub_notebook.select(correct_index))
            
            # 弹出提示（可选，用于用户反馈）
            # messagebox.showinfo("提示", f"Y Axis Control 标签页已锁定为 '{plot_type}'，请通过 Plot Type 切换。")

# 文件: s2p-test1.py (在 SViewGUI 类内，替换 _setup_unified_y_control_ui 方法)

    def _setup_unified_y_control_ui(self, parent_frame):
        """
        设置 Max 模式下的统一 Y 轴控制 UI，仅在 Custom 模式下显示 Min/Max 输入框和 Apply 按钮。
        """
        mode_var = self.axis_configs["unified_y_mode"]
        
        # ------------------------------------
        # 1. 模式选择 Frame
        # ------------------------------------
        mode_frame = tk.Frame(parent_frame, bg="#f0f2f5")
        #修改X Axis Control容器显示高度(Max)
        #mode_frame.pack(fill="x", padx=10, pady=(5, 0))
        mode_frame.pack(pady=12, padx=10, anchor="w")        

        tk.Label(mode_frame, text="Mode:", bg="#f0f2f5", 
                 font=("sans-serif", 10)).pack(side="left", padx=(0, 5))
        
        # Y 轴模式选择：Default / Custom
        mode_combo = ttk.Combobox(mode_frame, textvariable=mode_var, 
                                  values=["Default", "Custom"], state="readonly", width=10)
        mode_combo.pack(side="left", padx=5)
        
        # ------------------------------------
        # 2. Custom Y 轴输入和 Apply 按钮 Frame
        # ------------------------------------
        custom_y_frame = tk.Frame(parent_frame, bg="#f0f2f5")
        # custom_y_frame 的显示/隐藏将由下面的 trace 函数控制
        
        # Y_Min
        tk.Label(custom_y_frame, text="Max:", bg="#f0f2f5").pack(side="left", padx=(0, 5))
        tk.Entry(custom_y_frame, textvariable=self.axis_configs["unified_y_max"], width=10).pack(side="left", padx=5)

        # Y_Max
        tk.Label(custom_y_frame, text="Min:", bg="#f0f2f5").pack(side="left", padx=(20, 5))
        tk.Entry(custom_y_frame, textvariable=self.axis_configs["unified_y_min"], width=10).pack(side="left", padx=5)

        # 刷新按钮 (Apply button)
        tk.Button(custom_y_frame, text="Apply",
                  command=self.update_plots, width=10).pack(side="left", padx=(20, 5))

        # ------------------------------------
        # 3. 动态显示/隐藏逻辑
        # ------------------------------------
        def on_unified_y_mode_change(*args):
            current_mode = mode_var.get()
            # 只有在 Custom 模式下才显示 Min/Max 输入框和 Apply 按钮
            if current_mode == "Custom":
                custom_y_frame.pack(fill="x", padx=10, pady=(0, 10))
            else:
                custom_y_frame.pack_forget()

        # 绑定回调函数到模式变量
        mode_var.trace_add("write", on_unified_y_mode_change)
        
        # 初始调用以设置正确的可见性
        on_unified_y_mode_change()


    def setup_chart_tab(self):
        # 1. 创建 charts_frame 容器
        charts_frame = tk.Frame(self.chart_tab, bg="#f0f2f5")
        charts_frame.pack(fill="both", expand=True)
        self.charts_frame = charts_frame

        # 2. 确保 charts_frame 的 2x2 grid 权重已设置
        for i in range(2):
            charts_frame.grid_rowconfigure(i, weight=1)
            charts_frame.grid_columnconfigure(i, weight=1)
            
        # 3. 初始化 Max 模式框架（安全创建）
        
        # 检查是否需要重新创建 Max 模式的 frame
        needs_recreation = False
        
        # 情况 1: 属性不存在，或者属性值为 None (修复 NoneType 错误)
        if not hasattr(self, 'max_frame') or self.max_frame is None:
            needs_recreation = True
        # 情况 2: 属性存在且非 None，但其对应的 Tk 窗口已经被销毁
        elif not self.max_frame.winfo_exists():
            needs_recreation = True
            
        if needs_recreation:
            self.max_frame = tk.Frame(self.charts_frame, bg="#f0f2f5") 

        # 4. 初始化/清空 plot_configs 字典
        self.plot_configs = {} 

        # 5. 初始化 Max 模式的图表引用（安全措施）
        self.max_fig = None
        self.max_ax = None
        self.max_canvas = None

    # ---------- Utility plotting / interaction helpers ----------
    def _format_coords(self, x, y):
        if x is None or y is None:
            return ""
        x_str = f"{x:.2f}"
        plot_type = self.plot_type.get()
        if plot_type == "Magnitude (dB)":
            y_str = f"{y:.2f} dB"
        elif plot_type == "Phase (deg)":
            y_str = f"{y:.2f} deg"
        elif plot_type == "Group Delay (ns)":
            y_str = f"{y:.2f} ns"
        else:
            y_str = f"{y:.2f}"
        return f"X: {x_str} MHz, Y: {y_str}"

    def safe_interp(self, target, x, y):
        """Safe linear interpolation with boundary clamping."""
        if len(x) < 2 or len(y) == 0:
            return y[0] if len(y) > 0 else None
        # Assume x is sorted ascending
        if target <= x[0]:
            return y[0]
        elif target >= x[-1]:
            return y[-1]
        else:
            return np.interp(target, x, y)

    def get_marker_id_number(self, marker_id_str):
        """
        从 Marker ID 字符串中提取数字部分，用于 Marker 的数字排序。
        例如: 'M1' -> 1, 'M10' -> 10。
        """
        import re 
        match = re.search(r'\d+', marker_id_str)
        if match:
            try:
                return int(match.group(0))
            except ValueError:
                pass
        
        return float('inf')

    def _on_mouse_move_custom(self, event, param_or_combined):
        # param_or_combined: 'COMBINED' or specific param (S11/S21/S12/S22)

        # ▼ NEW: 若尚未加载文件，则不更新任何光标坐标显示
        if not hasattr(self, "datasets") or not self.datasets:
            if hasattr(self, "cursor_content") and param_or_combined == "COMBINED":
                self.cursor_content.config(text="X: ---, Y: ---")
            return

        # 找到对应的 toolbar
        tb = None
        if param_or_combined == 'COMBINED':
            tb = self.max_toolbar
        elif param_or_combined in self.plot_configs:
            tb = self.plot_configs[param_or_combined]["toolbar"]

        # ───────────────────────────────────────────────
        # 鼠标在坐标轴内 → 显示坐标
        # ───────────────────────────────────────────────
        if event.inaxes and event.xdata is not None and event.ydata is not None:

            # Toolbar 文本
            msg = self._format_coords(event.xdata, event.ydata)
            if tb:
                try:
                    tb.set_message(msg)
                except:
                    pass

            # Max 模式光标显示
            if param_or_combined == 'COMBINED' and hasattr(self, "cursor_content"):
                self.cursor_content.config(text=f"X: {event.xdata:.3f}, Y: {event.ydata:.3f}")

        else:
            # ───────────────────────────────────────────────
            # 鼠标不在图内 → Toolbar 恢复默认提示
            # ───────────────────────────────────────────────
            if tb:
                try:
                    if tb.mode == '':
                        default_msg = (
                            "Zoom & Pan enabled (Combined)"
                            if param_or_combined == "COMBINED"
                            else f"Zoom & Pan enabled for {param_or_combined}"
                        )
                        tb.set_message(default_msg)
                except:
                    pass

            # Max 模式光标显示（鼠标离开图区域）
            if param_or_combined == 'COMBINED' and hasattr(self, "cursor_content"):
                self.cursor_content.config(text="X: ---, Y: ---")


    #Normal模式zoom操作
    def on_scroll_zoom_normal(self, mpl_event, param):
        """Handle mouse scroll for zooming on individual plots in Normal mode."""
        if mpl_event.inaxes is None:
            return

        config = self.plot_configs.get(param)
        if not config:
            return
            
        ax = config["ax"]
        canvas = config["canvas"]
        
        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()
        xdata = mpl_event.xdata
        ydata = mpl_event.ydata
        
        if xdata is None or ydata is None:
            return
            
        scale_factor = 1.25
        # 'up' is zoom in (scale < 1), 'down' is zoom out (scale > 1)
        scale = 1 / scale_factor if mpl_event.button == 'up' else scale_factor
        
        # New limits calculation (与 Max 模式逻辑一致)
        new_xlim = [
            xdata - (xdata - cur_xlim[0]) * scale,
            xdata + (cur_xlim[1] - xdata) * scale
        ]
        new_ylim = [
            ydata - (ydata - cur_ylim[0]) * scale,
            ydata + (cur_ylim[1] - ydata) * scale
        ]
        
        # Apply limits
        ax.set_xlim(new_xlim)
        ax.set_ylim(new_ylim)
        
        # ------------------------------------------------------------------
        # --- [优化 1: 统一刻度优化，解决缩放不协调问题] ---
        # 强制重新计算刻度以保持缩放协调 (X/Y 轴)，prune='both' 移除边界刻度以防重叠
        ax.xaxis.set_major_locator(MaxNLocator(nbins=10, prune='both')) 
        ax.yaxis.set_major_locator(MaxNLocator(nbins=10, prune='both'))
        
        # --- [优化 2: 添加细线网格] ---
        # AutoMinorLocator(2) 意味着每两个主刻度之间有一个次刻度（即中间一条细线）
        ax.xaxis.set_minor_locator(AutoMinorLocator(2))
        ax.yaxis.set_minor_locator(AutoMinorLocator(2))
        # 启用次网格线 (细线)
        ax.grid(which='minor', linestyle=':', linewidth=0.5, color='gray', alpha=0.5)
        # ------------------------------------------------------------------
        
        # 重新优化刻度标签（调用现有方法）
        self._optimize_tick_labels_output(ax, config["fig"])
        
        canvas.draw()

    #Max模式zoom操作
    def on_scroll_zoom_combined(self, mpl_event):
        if mpl_event.inaxes is None:
            return
        ax = self.max_ax
        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()
        xdata = mpl_event.xdata
        ydata = mpl_event.ydata
        if xdata is None or ydata is None:
            return
        scale_factor = 1.25
        scale = 1/scale_factor if mpl_event.button == 'up' else scale_factor
        new_xlim = [xdata - (xdata - cur_xlim[0]) * scale, xdata + (cur_xlim[1] - xdata) * scale]
        new_ylim = [ydata - (ydata - cur_ylim[0]) * scale, ydata + (cur_ylim[1] - ydata) * scale]
        ax.set_xlim(new_xlim)
        ax.set_ylim(new_ylim)

        # ------------------------------------------------------------------
        # --- [优化 1: 统一刻度优化，解决缩放不协调问题] ---
        # 确保 X/Y 轴刻度协调，nbins=15 (Max模式下刻度更多)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=15, prune='both')) 
        ax.yaxis.set_major_locator(MaxNLocator(nbins=15, prune='both'))
        
        # --- [优化 2: 添加细线网格] ---
        # AutoMinorLocator(2) 意味着每两个主刻度之间有一个次刻度（即中间一条细线）
        ax.xaxis.set_minor_locator(AutoMinorLocator(2))
        ax.yaxis.set_minor_locator(AutoMinorLocator(2))
        # 启用次网格线 (细线)
        # 注意：Max 模式下主网格线通常是开启的，这里只添加次网格线的显示。
        ax.grid(which='minor', linestyle=':', linewidth=0.5, color='gray', alpha=0.5)
        # ------------------------------------------------------------------

        # 重新优化刻度标签（调用现有方法）
        self._optimize_tick_labels_output(ax, self.max_fig)
        
        self.max_canvas.draw()

    def _on_mouse_move_cursor_normal(self, event):
        """
        在所有模式下实时显示鼠标坐标。
        鼠标移动到任意图表区域内时，更新右下角的 Cursor Coordinates。
        (此函数现已绑定到 Normal 和 Max 模式下的 Canvas)
        """
        # --- 核心优化：移除模式检查，让数据检查逻辑控制显示 ---

        # 1. 检查数据是否加载 (处理静止/清空状态)
        if not hasattr(self, "datasets") or not self.datasets:
            self.cursor_content.config(text="X: ---, Y: ---")
            return

        # 2. 判断鼠标是否在坐标轴内
        if event.inaxes and event.xdata is not None and event.ydata is not None:
            # 显示到小数点后三位
            self.cursor_content.config(text=f"X: {event.xdata:.3f}, Y: {event.ydata:.3f}")
        else:
            # 鼠标不在图内时清空显示
            self.cursor_content.config(text="X: ---, Y: ---")


    def _update_mouse_button_state(self, mpl_event):
        """更新鼠标按键的按下/释放状态。"""
        if mpl_event.button == 1:  # 左键
            self.left_button_pressed = (mpl_event.name == 'button_press_event')
        elif mpl_event.button == 3:  # 右键
            self.right_button_pressed = (mpl_event.name == 'button_press_event')

        # 任何按键释放时，都停止平移（安全释放）
        if mpl_event.name == 'button_release_event':
            self.pan_drag_active = False

    def on_dual_button_pan_press(self, mpl_event, p=None):
        """处理鼠标按下事件，用于启动组合键平移（精简版，不使用 Blitting）。"""
        self._update_mouse_button_state(mpl_event)

        if self.marker_click_enabled.get():
            return
        
        is_left_press_with_right_down = (mpl_event.button == 1 and self.right_button_pressed)
        is_right_press_with_left_down = (mpl_event.button == 3 and self.left_button_pressed)

        if (is_left_press_with_right_down or is_right_press_with_left_down) and mpl_event.inaxes:
            if self.pan_drag_active:
                return
            
            if not self.dragging_marker_legend:
                self.pan_drag_active = True
                
                self.pan_start_x = mpl_event.xdata
                self.pan_start_y = mpl_event.ydata
                self.pan_ax = mpl_event.inaxes
                self.pan_param = p if self.display_mode.get() == "Normal" else None
                
                # 【移除 Blitting 相关的代码】
                # canvas = self.pan_ax.figure.canvas
                # canvas.draw() # 移除强制绘制
                # self.pan_artists = [] # 移除 Artists 收集
                # self.pan_ax_bg = None # 移除背景缓存
                
                # 设置 Axes 为 interactive 模式
                self.pan_ax.set_autoscale_on(False)


    def on_dual_button_pan_motion(self, mpl_event):
        """处理鼠标移动事件，执行 X/Y 轴的平移（恢复：使用完整重绘）。"""
        if not self.pan_drag_active or not mpl_event.inaxes or mpl_event.inaxes != self.pan_ax:
            return

        # 再次检查条件：必须满足组合键和平移状态
        if not self.marker_click_enabled.get() and self.left_button_pressed and self.right_button_pressed:
            current_x = mpl_event.xdata
            current_y = mpl_event.ydata

            if current_x is None or current_y is None or self.pan_start_x is None or self.pan_start_y is None:
                return

            # 核心平移逻辑
            dx = current_x - self.pan_start_x
            dy = current_y - self.pan_start_y
            
            # 获取并应用新的轴限制
            xlim = self.pan_ax.get_xlim()
            ylim = self.pan_ax.get_ylim()
            
            new_xlim = (xlim[0] - dx, xlim[1] - dx)
            new_ylim = (ylim[0] - dy, ylim[1] - dy)

            self.pan_ax.set_xlim(new_xlim)
            self.pan_ax.set_ylim(new_ylim)
            
            # 【核心修复】：使用 draw_idle() 触发完整重绘，代替 Blitting 序列。
            self.pan_ax.figure.canvas.draw_idle()
            
            # 重置起始点，实现连续拖拽
            self.pan_start_x = current_x
            self.pan_start_y = current_y
        
    def on_dual_button_pan_release(self, mpl_event):
        """处理鼠标释放事件，停止平移（精简版，不使用 Blitting 清理）。"""
        self._update_mouse_button_state(mpl_event)

        # 检查是否应该结束平移
        if self.pan_drag_active and not self.left_button_pressed and not self.right_button_pressed:
            if self.pan_ax:
                # 恢复 Autoscale 状态
                self.pan_ax.set_autoscale_on(True) 
                # 触发一次最终的重绘（可选，但推荐保留）
                self.pan_ax.figure.canvas.draw_idle()
            
            # 清理状态变量
            self.pan_drag_active = False
            self.pan_ax = None
            self.pan_param = None
        #------------------------------------

    def _manage_max_mode_drag_bindings(self, enable_drag):
        """
        根据 enable_drag 状态，绑定或解除 Max 模式下的 Marker Legend 拖拽事件。
        """
        # 检查 Max 模式的画布是否存在
        # BUG 修复：将 self.fig_max 更改为正确的 self.max_fig
        if not hasattr(self, 'max_fig') or not self.max_fig: 
            return

        # BUG 修复：将 self.fig_max 更改为正确的 self.max_fig
        canvas = self.max_fig.canvas 
        
        # 1. 无论如何，先解除现有的绑定以避免重复和冲突
        if self.cid_max_drag_press is not None:
            canvas.mpl_disconnect(self.cid_max_drag_press)
            self.cid_max_drag_press = None
            canvas.mpl_disconnect(self.cid_max_drag_release)
            self.cid_max_drag_release = None
            canvas.mpl_disconnect(self.cid_max_drag_motion)
            self.cid_max_drag_motion = None

        # 2. 如果允许拖拽 (Marker Click 关闭)，则绑定事件
        if enable_drag:
            # 重新绑定 Max 模式下的拖拽事件
            # 注意：这里我们使用 self.on_marker_legend_press/motion/release，
            # 假设这些函数能够处理 Max 模式和 Normal 模式的事件。
            self.cid_max_drag_press = canvas.mpl_connect('button_press_event', self.on_marker_legend_press)
            self.cid_max_drag_release = canvas.mpl_connect('button_release_event', self.on_marker_legend_release)
            self.cid_max_drag_motion = canvas.mpl_connect('motion_notify_event', self.on_marker_legend_motion)
            
        # 强制刷新 canvas
        canvas.draw_idle()


    def _on_marker_click_setting_changed(self, *args):
        """
        marker_click_enabled 变量值改变时触发的回调。
        如果当前处于 Max 模式，则更新 Max 模式的拖拽事件绑定。
        """
        # 只有在 Max 模式下，并且 Max 模式的 UI 元素已创建时才需要动态更新
        if self.display_mode.get() == "Max" and self.max_frame:
            new_click_value = self.marker_click_enabled.get()
            # 拖拽功能与 Marker Click 状态相反 (False 允许拖拽)
            enable_drag = not new_click_value
            self._manage_max_mode_drag_bindings(enable_drag)

    # Max mode添加Marker信息
    def add_marker_on_click_combined(self, mpl_event):
        """
        在 Combined 图中点击添加 Marker：为每个被选中的 param 创建 marker
        """
        
        if not self.marker_click_enabled.get(): # <--- 检查 Marker 点击功能是否开启
            return
        if not self.datasets: return
        
        # 基础检查：确保点击事件有效、左键、且在坐标轴内
        if mpl_event.inaxes is None or mpl_event.button != 1 or mpl_event.xdata is None or mpl_event.ydata is None:
            return
            
        x_mhz = mpl_event.xdata
        # 直接使用点击的精确频率 (Hz)
        click_hz = x_mhz * 1e6
        plot_type = self.plot_type.get()
        y_click_value = mpl_event.ydata
        
        markers_added_count = 0 

        # For each param shown, add marker at exact frequency
        for param in self.params:
            if not self.show_param_vars[param].get():
                continue

            # 寻找最接近点击位置的 Dataset ID (类似于 Normal 模式)
            closest_data_id = None
            min_y_diff = float('inf')

            for dataset in self.datasets:
                data_id = dataset['id']
                freq = dataset['freq']
                
                # 确保 S 参数数据存在
                if param.lower() not in dataset['s_data']:
                    continue
                    
                s_data = dataset['s_data'][param.lower()]

                # 转换为绘图所需的 Y 轴数据 (与 plot_parameter_output 逻辑一致)
                data_array = None
                if plot_type == "Magnitude (dB)":
                    data_array = 20 * np.log10(np.abs(s_data) + 1e-20)
                elif plot_type == "Phase (deg)":
                    data_array = np.unwrap(np.angle(s_data)) * 180 / np.pi
                elif plot_type == "Group Delay (ns)":
                    try:
                        # 假设 calculate_group_delay 存在并返回 (data_array, _)
                        data_array, _ = self.calculate_group_delay(freq, s_data)
                    except:
                        continue # 无法计算群延时则跳过

                if data_array is not None and len(freq) > 1:
                    # 使用 safe_interp 进行插值，找到该数据集在点击频率处的 Y 值
                    y_interpolated = self.safe_interp(click_hz, freq, data_array)
                    
                    if y_interpolated is not None:
                        # 计算 Y 轴差值
                        y_diff = abs(y_click_value - y_interpolated)
                        
                        # 寻找最小差值对应的 Dataset ID
                        if y_diff < min_y_diff:
                            min_y_diff = y_diff
                            closest_data_id = str(data_id)

            # 确定用于 Marker 的 Data ID
            if closest_data_id is None:
                # 如果没有找到任何合适的曲线，则默认使用第一个数据集
                data_id_options = [str(d['id']) for d in self.datasets]
                target_data_id = data_id_options[0] if data_id_options else "1"
            else:
                target_data_id = closest_data_id

            # --- 核心修复 1: 生成 Marker ID (M1, M2...) ---
            # 确保 data 结构存在
            if plot_type not in self.data:
                self.data[plot_type] = {"marks": {}}
            if "marks" not in self.data[plot_type]:
                self.data[plot_type]["marks"] = {}
            if param not in self.data[plot_type]["marks"]:
                self.data[plot_type]["marks"][param] = []
                
            current_marks = self.data[plot_type]["marks"][param]
            next_id_number = len(current_marks) + 1
            mark_id = f"M{next_id_number}"
            # ------------------------------------------------

            # UI stores in MHz by default
            f_val = x_mhz
            f_unit = "MHz"
            new_mark = {
                "id": mark_id, # <-- FIX: 使用正确的 ID
                "freq": tk.StringVar(value=f"{f_val:g}"),
                "unit": tk.StringVar(value=f_unit),
                "data_id": tk.StringVar(value=target_data_id),
                # --- 核心修复 2: 解决 KeyError: 'display_status' ---
                "display_status": tk.StringVar(value="Display") 
            }
            
            self.data[plot_type]["marks"][param].append(new_mark)
            markers_added_count += 1
            
            # reindex and refresh UI
            self._reindex_markers_and_refresh_ui(plot_type, param)
            
        if markers_added_count == 0:
            self.status_var.set("Warning: No visible S-parameters found to add marker.")
            return
            
        # -------------------------- 刷新逻辑修复 --------------------------
        # 检查 'Auto Refresh' 状态。
        if not self.disable_refresh_var.get():
            # Auto Refresh 处于 Enable 状态，执行完整刷新 (可能重置 Limits)
            self.update_plots()
            self.status_var.set(f"Added {markers_added_count} marker(s) at {x_mhz:.3f} MHz on combined view.")
        else:
            # Auto Refresh 处于 Disable 状态。
            try:
                # 【FIX Bug 2: Max模式下禁用自动刷新添加Marker时仍自动刷新】
                # 使用 _safe_refresh_markers(reset_limits=False) 来安全刷新 Marker，同时保持缩放状态。
                # 替换 self.plot_combined(redraw_full=True)
                self._safe_refresh_markers(reset_limits=False)
                self.status_var.set(f"Added {markers_added_count} marker(s). Auto Refresh is DISABLED. Zoom state preserved.")
            except Exception as e:
                self.status_var.set(f"Marker added, but manual plot update failed: {e}. Auto Refresh is DISABLED.")
        # -------------------------- 刷新逻辑修复结束 --------------------------

    def plot_normal(self):
        """ 
        Normal 模式下的绘图逻辑。
        [修复 Bug 2]: 确保父容器权重设置和图表容器的正确 grid/grid_forget 操作。
        """
        
        # 1. 【修复 Bug 2 关键】强制配置父容器 self.charts_frame 的权重
        # 确保子图容器 grid 时可以占据空间并扩展 (2x2 布局)
        if hasattr(self, 'charts_frame'):
            self.charts_frame.grid_columnconfigure(0, weight=1)
            self.charts_frame.grid_columnconfigure(1, weight=1)
            self.charts_frame.grid_rowconfigure(0, weight=1)
            self.charts_frame.grid_rowconfigure(1, weight=1)

        # 2. 隐藏所有 S 参数图表的 Tkinter 容器 Frame
        for p in self.params: 
            if p in self.plot_configs and "frame" in self.plot_configs[p]:
                # 假设 config["frame"] 是包含 Matplotlib Canvas 的 Tkinter.Frame
                self.plot_configs[p]["frame"].grid_forget()

        # 3. 重新排列和显示可见的图表
        row_idx, col_idx = 0, 0
        
        for p in self.params:
            if self.show_param_vars[p].get(): # 检查是否勾选了该参数 (True = 显示)
                config = self.plot_configs[p]
                
                # 重新将 frame 放入 grid 布局，实现显示
                # 假设 config["frame"] 是包含 Canvas 的 Tkinter.Frame
                # 注意：如果 config["frame"] 存储的是 CanvasTkAgg 对象，则需要调用 get_tk_widget().grid(...)
                # 这里假设 config["frame"] 是 Tkinter Frame 容器：
                config["frame"].grid(
                    row=row_idx, column=col_idx, sticky="nsew", padx=5, pady=5
                )

                # 4. 绘制 S 参数内容 (这部分逻辑不变)
                self.plot_parameter_output(
                    ax=config["ax"], 
                    fig=config["fig"], 
                    param=p, 
                    plot_type=self.plot_type.get()
                )
                
                # 更新下一个位置 (2x2 布局)
                col_idx += 1
                if col_idx > 1:
                    col_idx = 0
                    row_idx += 1
        
        # 注意：最终的 self.update_plots() 调用会负责 Matplotlib Canvas 的 draw() 刷新。

    # Normal mode添加/删除 Marker，并处理 Pan 委托
    def add_marker_on_click_normal(self, event, param):
        """
        Normal 模式下：鼠标点击添加 Marker，右键删除（支持普通 + Search Marker）
        """
        # --- 1. 禁用 Marker 点击 → 交给 Pan 处理 ---
        if not self.marker_click_enabled.get():
            self.on_dual_button_pan_press(event, param)
            return

        # --- 2. 基本检查 ---
        if not event.inaxes or event.xdata is None or event.ydata is None or not self.datasets:
            return

        # --- 3. 防止重复触发（互斥锁）---
        if getattr(self, 'is_processing_marker_click', False):
            return
        self.is_processing_marker_click = True
        self.root.after(100, lambda: setattr(self, 'is_processing_marker_click', False))

        # --- 4. 获取点击信息 ---
        plot_type = self.plot_type.get()
        x_click_mhz = event.xdata
        x_click_hz = x_click_mhz * 1e6
        y_click_value = event.ydata

        # --- 5. 右键删除 Marker（支持普通 + Search）---
        if event.button == 3:  # 右键
            # 最简单且稳健的做法：把删除任务交给统一的删除处理函数（使用基于实际绘图点的反推算法）
            # 假定类中有实现 delete_marker_on_right_click(event, param)
            try:
                self.delete_marker_on_right_click(event, param)
            except Exception as e:
                # 容错：若统一删除函数不存在或出错，记录状态并继续（不影响添加逻辑）
                self.status_var.set(f"Delete marker failed: {e}")
            return

        # --- 6. 左键添加普通 Marker ---
        if event.button != 1:
            return

        # --- 智能选择最近的曲线 ---
        closest_data_id = None
        min_y_diff = float('inf')

        for dataset in self.datasets:
            data_id = dataset['id']
            freq = dataset['freq']
            s_data = dataset['s_data'].get(param.lower())
            if s_data is None or len(freq) < 2:
                continue

            # 计算 Y 数据
            if plot_type == "Magnitude (dB)":
                y_data = 20 * np.log10(np.abs(s_data) + 1e-20)
            elif plot_type == "Phase (deg)":
                y_data = np.unwrap(np.angle(s_data)) * 180 / np.pi
            elif plot_type == "Group Delay (ns)":
                y_data, _ = self.calculate_group_delay(freq, s_data)
            else:
                continue

            y_interp = self.safe_interp(x_click_hz, freq, y_data)
            if y_interp is None:
                continue

            y_diff = abs(y_click_value - y_interp)
            if y_diff < min_y_diff:
                min_y_diff = y_diff
                closest_data_id = str(data_id)

        # --- 默认 Data ID ---
        target_data_id = closest_data_id or (str(self.datasets[0]['id']) if self.datasets else "1")

        # --- 频率格式 ---
        f_val = x_click_hz / 1e9 if x_click_hz >= 3e9 else x_click_hz / 1e6
        f_unit = "GHz" if x_click_hz >= 3e9 else "MHz"

        # --- 创建新 Marker ---
        marks = self.data[plot_type]["marks"].setdefault(param, [])
        new_mark = {
            "id": f"M{len(marks) + 1}",
            "freq": tk.StringVar(value=f"{f_val:g}"),
            "unit": tk.StringVar(value=f_unit),
            "data_id": tk.StringVar(value=target_data_id),
            "display_status": tk.StringVar(value="Display"),
            "is_search": False
        }
        marks.append(new_mark)

        # --- 刷新 UI ---
        self._reindex_markers_and_refresh_ui(plot_type, param)

        # --- 更新图表 ---
        if not self.disable_refresh_var.get():
            self.update_plots()
            self.status_var.set(f"Marker {new_mark['id']} added at {f_val:g} {f_unit} on {param} (ID {target_data_id}).")
        else:
            self._safe_refresh_markers(reset_limits=False)
            self.status_var.set(f"Marker {new_mark['id']} added. Zoom preserved.")


    def _clear_marker_click_flag(self):
        """清除防止 Marker 点击时事件双重触发的标志。"""
        self.is_processing_marker_click = False
                        
    def _is_artist_hit(self, artist, mpl_event):
        """检查鼠标事件是否击中了 Matplotlib Text Artist 的边界框。"""
        if artist is None or mpl_event.inaxes is None or mpl_event.x is None or mpl_event.y is None:
            return False
        
        # 使用 Matplotlib 的 contains 方法检查点击是否在艺术家范围内
        contains, _ = artist.contains(mpl_event)
        
        if contains:
            # 进一步检查是否在紧密边界框内 (使用 bbox 确保点击的是黄色框体)
            renderer = mpl_event.canvas.get_renderer()
            if renderer:
                bbox = artist.get_window_extent(renderer=renderer)
                return bbox.contains(mpl_event.x, mpl_event.y)
        return False


    def on_marker_legend_press(self, mpl_event):
        """
        处理鼠标左键按下事件：检测并启动 Marker Legend 拖动（支持旧 Text 和新 AnnotationBbox）
        """
        if mpl_event.button != 1 or not mpl_event.inaxes:
            return
        if self.pan_drag_active:
            return
        if self.marker_click_enabled.get():
            return

        is_max_mode = (self.display_mode.get() == "Max")
        plot_type = self.plot_type.get()
        hit_artist = None
        hit_pos_config = None
        hit_param = None  # 新增：记录是哪个 param（Normal 模式需要）

        current_click_axes = mpl_event.inaxes.transAxes.inverted().transform((mpl_event.x, mpl_event.y))

        # --- 1. Max Mode 检测（保持不变）---
        if is_max_mode:
            artist = self.max_marker_legend_artists.get(plot_type)
            if artist:
                try:
                    if artist.get_window_extent().contains(mpl_event.x, mpl_event.y):
                        hit_artist = artist
                        hit_pos_config = self.max_marker_pos_configs[plot_type]
                        self.drag_ax = self.max_ax
                        self.drag_canvas = self.max_canvas
                except:
                    if artist.contains(mpl_event)[0]:
                        hit_artist = artist
                        hit_pos_config = self.max_marker_pos_configs[plot_type]
                        self.drag_ax = self.max_ax
                        self.drag_canvas = self.max_canvas

        # --- 2. Normal Mode 检测（关键兼容 AnnotationBbox）---
        else:
            for p, artist in self.normal_marker_legend_artists.items():
                if not artist or artist.axes != mpl_event.inaxes:
                    continue
                contains, _ = artist.contains(mpl_event)
                if contains:
                    hit_artist = artist
                    hit_pos_config = self.marker_pos_configs[plot_type][p]
                    hit_param = p
                    self.drag_ax = mpl_event.inaxes
                    self.drag_canvas = self.plot_configs[p]["canvas"]
                    break

        # --- 3. 命中后启动拖动 ---
        if hit_artist:
            self.dragging_marker_legend = hit_artist  # 直接存 artist（新版支持！）
            self.drag_param = hit_param  # Normal 模式需要知道是哪个 param

            # 存储配置变量
            self.drag_x_var = hit_pos_config["x_var"]
            self.drag_y_var = hit_pos_config["y_var"]
            self.drag_mode_var = hit_pos_config["mode_var"]

            # 【核心】计算当前图例的归一化坐标（支持 xy 和 get_position）
            try:
                if hasattr(hit_artist, 'xy'):
                    legend_x = hit_artist.xy[0]
                    legend_y = hit_artist.xy[1]
                else:
                    legend_x, legend_y = hit_artist.get_position()
            except:
                legend_x = float(self.drag_x_var.get())
                legend_y = float(self.drag_y_var.get())

            # 计算偏移量（鼠标点击点相对于图例左上角/锚点的偏移）
            self.drag_offset_x = legend_x - current_click_axes[0]
            self.drag_offset_y = legend_y - current_click_axes[1]

            # 强制切换到 Custom 模式
            self.drag_mode_var.set("Custom")

            # 更新 Custom 坐标框（实时显示）
            self.drag_x_var.set(f"{legend_x:.4f}")
            self.drag_y_var.set(f"{legend_y:.4f}")

            self.status_var.set("Dragging Marker Legend...")
            self._drag_update_id = None

            # 释放可能的 Pan/Zoom 冲突
            toolbar = getattr(mpl_event.canvas, 'toolbar', None)
            if toolbar and toolbar._active:
                toolbar._active = None

            return
        #-------------------------------------------------    

    #鼠标Marker拖拽
    def on_marker_legend_motion(self, mpl_event):
        if not getattr(self, 'dragging_marker_legend', False) or mpl_event.canvas != self.drag_canvas:
            return
        if mpl_event.inaxes is None or mpl_event.x is None or mpl_event.y is None:
            return

        point = mpl_event.inaxes.transAxes.inverted().transform((mpl_event.x, mpl_event.y))
        x_new = max(0.0, min(1.0, point[0] + self.drag_offset_x))
        y_new = max(0.0, min(1.0, point[1] + self.drag_offset_y))

        artist = self.dragging_marker_legend

        # 实时移动（超快）
        if hasattr(artist, 'set_position'):
            artist.set_position((x_new, y_new))
        else:
            artist.xy = (x_new, y_new)

        # 实时更新坐标框
        if self.drag_x_var and self.drag_y_var:
            self.drag_x_var.set(f"{x_new:.4f}")
            self.drag_y_var.set(f"{y_new:.4f}")

        # 节流刷新画布（只重绘图例，不触发 update_plots）
        if self._drag_update_id:
            self.root.after_cancel(self._drag_update_id)

        def light_draw():
            mpl_event.canvas.draw_idle()  # 轻量、丝滑、不卡顿

        self._drag_update_id = self.root.after(self.DRAG_UPDATE_INTERVAL, light_draw)
    #---------------------------------------

    # Marker拖拽的辅助函数
    def _throttled_update_plots(self):
        """
        辅助函数，用于在拖动时节流地调用图表更新，并根据 'Disable Refresh' 状态决定是否保留 Limits。
        """
        # 清除 pending ID，表示更新已执行
        self._drag_update_id = None 

        # 根据 'Disable Refresh' 状态决定更新方式
        if self.disable_refresh_var.get():
            # 禁用刷新: 调用安全刷新以保持当前缩放 (reset_limits=False)
            self._safe_refresh_markers(reset_limits=False) 
        else:
            # 启用刷新: 执行完整的重绘
            self.update_plots()

        # 更新状态栏以提供反馈
        if self.dragging_marker_legend:
            self.status_var.set(f"Marker Legend dragging: ({self.drag_x_var.get()}, {self.drag_y_var.get()})")
    #---------------------------------------

    # Marker拖拽释放
    def on_marker_legend_release(self, mpl_event):
        """处理鼠标左键释放事件，停止拖动 Marker Legend（终极丝滑版）"""
       
        # 1. 检查和处理 Marker Legend 拖动结束
        if self.dragging_marker_legend:
           
            # 取消任何待处理的节流更新（我们现在用的是轻量 draw_idle）
            if self._drag_update_id:
                self.root.after_cancel(self._drag_update_id)
                self._drag_update_id = None

            # 标记拖动状态结束
            self.dragging_marker_legend = False
           
            # 清除所有拖动相关的临时引用（你原来写得完美，保留）
            self.drag_start_point_axes = None
            self.drag_ax = None
            self.drag_x_var = None
            self.drag_y_var = None
            self.drag_mode_var = None
            self.drag_offset_x = None
            self.drag_offset_y = None
            self.drag_canvas = None  # 顺手清理

            # 强制释放 Max Toolbar 的 Pan/Zoom（你原来的保险，保留）
            if self.display_mode.get() == "Max" and self.max_toolbar:
                self.max_toolbar.release_pan(mpl_event)
                self.max_toolbar._active = None
               
            # 【终极优化】松开后只调用一次 update_plots，确保位置永久保存
            # 完全不需要判断 update_needed —— 因为我们拖动时只用了 draw_idle，从未触发过重绘
            # 所以松开后必须主动调用一次 update_plots 来“落盘”位置
            self.root.after_idle(lambda: self._final_drag_update())

            self.status_var.set("Marker Legend drag finished. Position saved.")
            return
           
        # 3. 非拖动情况下的 Max Toolbar 保险（保留你原来的逻辑）
        if self.display_mode.get() == "Max" and self.max_toolbar:
            if self.max_toolbar._active:
                self.max_toolbar.release_pan(mpl_event)
                self.max_toolbar._active = None
        #------------------------------------

    # 【新增】拖动结束后的最终落盘函数（推荐单独抽出，清晰优雅）
    def _final_drag_update(self):
        """拖动结束后执行一次最终刷新，确保位置永久保存"""
        if self.disable_refresh_var.get():
            # 禁用刷新：只更新 Marker 位置，不重置缩放
            self._safe_refresh_markers(reset_limits=False)
        else:
            # 正常刷新：完整重绘（会保存 Custom 坐标）
            self.update_plots()

    def _get_marker_freq_hz(self, mark):
            """Helper to convert marker frequency back to Hz from its Tkinter variables."""
            try:
                freq_val = float(mark["freq"].get())
                freq_unit = mark["unit"].get()
            except ValueError:
                return 0.0 # Return 0 or handle error

            if freq_unit == "GHz":
                return freq_val * 1e9
            elif freq_unit == "MHz":
                return freq_val * 1e6
            elif freq_unit == "KHz":
                return freq_val * 1e3
            return freq_val

    #删除Marker容忍度调整
    # ----------------------------------------------------
    # 【终极修复】右键删除 P1 —— 使用 Matplotlib 绘图点反推
    # ----------------------------------------------------
    def delete_marker_on_right_click(self, mpl_event, param=None):
        """
        右键点击删除最近的 Marker。
        - 优先检测 Normal 模式下的 Marker Legend Box 点击，删除对应参数的最新 Marker。
        - 否则，通过距离计算删除最接近点击位置的 Marker（普通 + Search）。
        """
        if not self.marker_click_enabled.get():
            return
        if not mpl_event.inaxes or mpl_event.button != 3:
            return

        plot_type = self.plot_type.get()
        ax = mpl_event.inaxes
        
        # ------------------------------------------------------------------
        # 【新增逻辑】1. 优先处理 Normal 模式下点击 Marker Legend Box 的删除请求
        # ------------------------------------------------------------------
        if self.display_mode.get() == "Normal": 
            # 确定要检查的参数范围
            params_to_check_legend = [param] if param else [p for p in self.params if self.show_param_vars[p].get()]
            
            for p_legend in params_to_check_legend:
                # 获取图例 artist (AnnotationBbox 或 Text)
                artist = self.normal_marker_legend_artists.get(p_legend)
                
                # 检查 artist 是否存在、是否在当前 Axes 上，并检查点击是否命中
                if artist and artist.axes == ax and artist.contains(mpl_event)[0]:
                    # 命中图例框，删除该参数 p_legend 的最后一个（最新）Marker
                    marks_list = self.data[plot_type]["marks"].get(p_legend, [])
                    if marks_list:
                        # 找到最后一个 Marker
                        marker_to_delete = marks_list[-1]
                        marker_id = marker_to_delete.get('id', 'Unknown')
                        
                        # 执行删除
                        marks_list.remove(marker_to_delete)
                        
                        # 调用刷新逻辑
                        if marker_to_delete.get("is_search", False):
                            self._refresh_search_markers_ui(plot_type, p_legend)
                        else:
                            self._reindex_markers_and_refresh_ui(plot_type, p_legend)
                            
                        # 更新绘图和状态
                        if not self.disable_refresh_var.get():
                            self.update_plots()
                            self.status_var.set(f"Marker {marker_id} deleted via Legend Box click on {p_legend}.")
                        else:
                            self._safe_refresh_markers(reset_limits=False)
                            self.status_var.set(f"Marker {marker_id} deleted. Zoom preserved.")
                        
                        return # 成功处理，退出函数，不执行后续距离计算
        # ------------------------------------------------------------------


        # ------------------------------------------------------------------
        # 【原有逻辑】2. 基于距离计算的删除（如果未命中图例框，则继续执行）
        # ------------------------------------------------------------------
        
        # 确保 Matplotlib 事件有数据点，否则无法计算距离
        if mpl_event.xdata is None or mpl_event.ydata is None:
            if self.display_mode.get() != "Normal": # Max 模式下点击空白区，图例检测逻辑已返回 None，所以在这里添加状态提示
                 self.status_var.set("No data point clicked.")
            return
        if not self.datasets:
            return

        click_mhz = mpl_event.xdata
        click_value = mpl_event.ydata
        trans = ax.transData

        # 参数列表 (用于距离计算)
        params_to_check = [param] if param else [p for p in self.params if self.show_param_vars[p].get()]

        # --- 容忍度计算 (保留不变) ---
        TOLERANCE_MULTIPLIER = 10.0
        MIN_ABSOLUTE_TOLERANCE_MHZ = 0.5
        if self.datasets and any(len(d['freq']) > 1 for d in self.datasets):
            try:
                # 尝试计算最小频率间隔
                min_delta_hz = min(np.min(np.diff(d['freq'])) for d in self.datasets if len(d['freq']) > 1 and d['freq'] is not None and len(d['freq']) > 1)
            except ValueError:
                # 如果所有数据集的长度都不大于1，则使用默认值
                min_delta_hz = 1e6 # 1 MHz in Hz
            
            tolerance_mhz = max((min_delta_hz / 1e6) * TOLERANCE_MULTIPLIER, MIN_ABSOLUTE_TOLERANCE_MHZ)
        else:
            tolerance_mhz = MIN_ABSOLUTE_TOLERANCE_MHZ

        Y_TOLERANCE_BASE = {"Magnitude (dB)": 0.5, "Phase (deg)": 15.0, "Group Delay (ns)": 5.0}.get(plot_type, 1.0)
        try:
            y_range = ax.get_ylim()[1] - ax.get_ylim()[0]
            tolerance_value = max(Y_TOLERANCE_BASE, y_range * 0.005)
        except:
            tolerance_value = Y_TOLERANCE_BASE

        # --- 查找最佳 Marker (保留不变) ---
        best_marker = None
        best_param = None
        best_dist = float('inf')

        for p in params_to_check:
            marks_list = self.data[plot_type]["marks"].get(p, [])
            for mark in marks_list:
                try:
                    data_id = int(mark["data_id"].get())
                    dataset = next((d for d in self.datasets if d['id'] == data_id), None)
                    if not dataset:
                        continue
                    freq = dataset['freq']
                    s_data = dataset['s_data'][p.lower()]
                    freq_mhz = freq / 1e6

                    if plot_type == "Magnitude (dB)":
                        y_data = 20 * np.log10(np.abs(s_data) + 1e-20)
                    elif plot_type == "Phase (deg)":
                        y_data = np.unwrap(np.angle(s_data)) * 180 / np.pi
                    elif plot_type == "Group Delay (ns)":
                        y_data, _ = self.calculate_group_delay(freq, s_data)
                    else:
                        continue

                    if mark.get("is_search", False):
                        start_val = float(mark["start"].get())
                        stop_val = float(mark["stop"].get())
                        unit = mark["unit"].get()
                        start_mhz = start_val * 1000 if unit == "GHz" else start_val
                        stop_mhz = stop_val * 1000 if unit == "GHz" else stop_val
                        f_min, f_max = min(start_mhz, stop_mhz), max(start_mhz, stop_mhz)
                        mask = (freq_mhz >= f_min) & (freq_mhz <= f_max)
                        if not np.any(mask):
                            continue
                        y_masked = y_data[mask]
                        freq_masked = freq_mhz[mask]
                        idx = np.argmax(y_masked) if mark["search_type"].get() == "Max Value" else np.argmin(y_masked)
                        x_actual = freq_masked[idx]
                        y_actual = y_masked[idx]
                    else:
                        freq_val = float(mark["freq"].get())
                        unit = mark["unit"].get()
                        x_actual = freq_val * 1000 if unit == "GHz" else freq_val
                        y_actual = self.safe_interp(x_actual * 1e6, freq, y_data)
                        if y_actual is None:
                            continue

                    x_min, x_max = ax.get_xlim()
                    # 仅将 x_actual 裁剪到当前视图范围用于距离计算
                    x_plot = np.clip(x_actual, x_min, x_max) 
                    
                    # 尝试通过 display 坐标反算出数据坐标，确保 y_plot 与 x_plot 属于同一视图范围
                    try:
                        x_display, y_display = trans.transform((x_plot, y_actual))
                        x_inv, y_inv = trans.inverted().transform((x_display, y_display))
                        y_plot = y_inv
                    except:
                        y_plot = y_actual

                    # 距离计算
                    dist_x = abs(click_mhz - x_plot)
                    dist_y = abs(click_value - y_plot)
                    dist = (dist_x ** 2 + dist_y ** 2) ** 0.5

                    if dist_x <= tolerance_mhz and dist_y <= tolerance_value and dist < best_dist:
                        best_dist = dist
                        best_marker = mark
                        best_param = p
                except Exception:
                    # 忽略处理 Marker 时的异常
                    continue
            if best_marker:
                break

        # --- 执行删除 (保留不变) ---
        if best_marker:
            marker_id = best_marker.get('id', 'Unknown')
            self.data[plot_type]["marks"][best_param].remove(best_marker)
            if best_marker.get("is_search", False):
                self._refresh_search_markers_ui(plot_type, best_param)
            else:
                self._reindex_markers_and_refresh_ui(plot_type, best_param)
            if not self.disable_refresh_var.get():
                self.update_plots()
                self.status_var.set(f"Marker {marker_id} deleted on {best_param}.")
            else:
                self._safe_refresh_markers(reset_limits=False)
                self.status_var.set(f"Marker {marker_id} deleted. Zoom preserved.")
        else:
            self.status_var.set(f"No marker found near {click_mhz:.3f} MHz.")
    # ----------------------------------------------------

    def format_freq_display_value(self, f_hz):
        """格式化频率值，用于 Marker Legend 显示。"""
        if f_hz is None:
            return "---"
        if f_hz >= 1e9:
            return f"{f_hz / 1e9:.3f} GHz"
        elif f_hz >= 1e6:
            return f"{f_hz / 1e6:.3f} MHz"
        elif f_hz >= 1e3:
            return f"{f_hz / 1e3:.3f} KHz"
        else:
            return f"{f_hz:.3f} Hz"

    def _get_marker_search_params(self, search_data):
        """Helper to get Peak Marker Search parameters in Hz and string format."""
        
        start_hz = 0.0
        stop_hz = 0.0
        
        try:
            start_val = float(search_data["start_freq"].get())
            stop_val = float(search_data["stop_freq"].get())
            freq_unit = search_data["unit"].get()
            
            if freq_unit == "GHz":
                factor = 1e9
            elif freq_unit == "MHz":
                factor = 1e6
            elif freq_unit == "KHz":
                factor = 1e3
            else:
                factor = 1.0 # Hz
                
            start_hz = start_val * factor
            stop_hz = stop_val * factor
            
            # 确保 Start < Stop (统一处理)
            if start_hz > stop_hz:
                start_hz, stop_hz = stop_hz, start_hz
                start_val_str = f"{stop_val:g}" # 交换显示值
                stop_val_str = f"{start_val:g}"
            else:
                start_val_str = f"{start_val:g}"
                stop_val_str = f"{stop_val:g}"
                
            ref_id = search_data["data_id"].get()
            search_type = search_data["type"].get()
            display_status = search_data["display_status"].get()
            
            # Format display string
            x_display = f"Start:{start_val_str} Stop:{stop_val_str} {freq_unit}"

            return {
                "start_hz": start_hz,
                "stop_hz": stop_hz,
                "ref_id": ref_id,
                "search_type": search_type,
                "display_status": display_status,
                "x_display": x_display
            }
            
        except ValueError:
            self.status_var.set("Peak Marker Search: Invalid frequency input.")
            return None
        except Exception as e:
            print(f"Error in _get_marker_search_params: {e}")
            return None


    def _run_marker_search(self, search_data, plot_type, param):
        """
        在指定范围和数据集中搜索 Max/Min Value，并返回结果 (freq_hz, value)。
        """
        params = self._get_marker_search_params(search_data)
        if not params:
            return None, None
            
        ref_id = params["ref_id"]
        start_hz = params["start_hz"]
        stop_hz = params["stop_hz"]
        search_type = params["search_type"]
        
        if not self.datasets:
            self.status_var.set("Peak Marker Search: No datasets loaded.")
            return None, None
            
        target_dataset = next((d for d in self.datasets if str(d['id']) == ref_id), None)
        if not target_dataset:
            # 允许 Ref ID 为空，此时搜索所有数据集的 Max/Min
            if ref_id.strip() == "":
                datasets_to_search = self.datasets
            else:
                self.status_var.set(f"Peak Marker Search: Reference ID {ref_id} not found.")
                return None, None
        else:
            datasets_to_search = [target_dataset]
            
        best_freq_hz = None
        best_value = None
        current_best_data_id = None
        
        # Max/Min 搜索的初始值
        if search_type == "Max Value":
            best_value = -float('inf') 
        elif search_type == "Min Value":
            best_value = float('inf')
        else:
            return None, None

        for dataset in datasets_to_search:
            data_id = dataset['id']
            if param.lower() not in dataset['s_data']:
                continue 

            freq_hz = dataset['freq']
            s_data = dataset['s_data'][param.lower()]
            
            # 转换为绘图所需的 Y 轴数据
            data_array = None
            if plot_type == "Magnitude (dB)":
                data_array = 20 * np.log10(np.abs(s_data) + 1e-20)
            elif plot_type == "Phase (deg)":
                data_array = np.unwrap(np.angle(s_data)) * 180 / np.pi
            elif plot_type == "Group Delay (ns)":
                try:
                    data_array, _ = self.calculate_group_delay(freq_hz, s_data)
                except:
                    continue
                    
            if data_array is None or len(data_array) < 2:
                continue

            # 找到搜索频率范围对应的索引
            start_index = np.searchsorted(freq_hz, start_hz, side='left')
            stop_index = np.searchsorted(freq_hz, stop_hz, side='right')

            if start_index >= stop_index:
                continue

            search_freq = freq_hz[start_index:stop_index]
            search_data_array = data_array[start_index:stop_index]
            
            if len(search_freq) == 0:
                continue

            # 在当前数据集上执行 Max/Min 搜索
            if search_type == "Max Value":
                max_index_in_search = np.argmax(search_data_array)
                current_value = search_data_array[max_index_in_search]
                current_freq_hz = search_freq[max_index_in_search]
                
                if current_value > best_value:
                    best_value = current_value
                    best_freq_hz = current_freq_hz
                    current_best_data_id = data_id
                    
            elif search_type == "Min Value":
                min_index_in_search = np.argmin(search_data_array)
                current_value = search_data_array[min_index_in_search]
                current_freq_hz = search_freq[min_index_in_search]
                
                if current_value < best_value:
                    best_value = current_value
                    best_freq_hz = current_freq_hz
                    current_best_data_id = data_id

        # 如果搜索成功，更新 search_data 中的 Ref ID 为找到结果的数据 ID (如果 Ref ID 原本是空白)
        if best_freq_hz is not None and ref_id.strip() == "":
            search_data["data_id"].set(str(current_best_data_id))
            
        return best_freq_hz, best_value


    def _reindex_marker_searches_and_refresh_ui(self, plot_type, param):
        """
        重新索引 Peak Marker Search 列表并刷新 UI。
        """
        searches = self.data[plot_type].get("marker_searches", {}).get(param, [])
        ui_refs = self.data[plot_type]["ui_refs"].get(param, {})
        search_list_frame = ui_refs.get("marker_search_list_frame") 
        canvas = ui_refs.get("marker_search_canvas") # 使用专用的 canvas 引用

        if not search_list_frame or not canvas:
            return 
            
        for widget in search_list_frame.winfo_children():
            widget.destroy()

        for i, search_data in enumerate(searches):
            new_id = f"P{i + 1}"
            search_data["id"] = new_id
            self._draw_search_marker_frame(self, mark_data, container, plot_type, param)
            
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))


    def add_marker_search(self, plot_type, param):
        """
        新增一个 Peak Marker Search 配置项。
        """
        searches = self.data[plot_type]["marker_searches"][param]
        ui_refs = self.data[plot_type]["ui_refs"].get(param, {})
        search_list_frame = ui_refs.get("marker_search_list_frame")
        canvas = ui_refs.get("marker_search_canvas")

        if not search_list_frame or not canvas:
            messagebox.showerror("Error", "Internal error: Marker search UI not initialized.")
            return

        next_id_number = len(searches) + 1
        new_id = f"P{next_id_number}"
        
        # 获取默认频率单位和范围
        default_unit = self.axis_configs["x_unit"].get()
        default_start = self.axis_configs["x_start"].get()
        default_stop = self.axis_configs["x_stop"].get()

        # 找到第一个数据集 ID 作为默认 Ref ID
        default_data_id = str(self.datasets[0]['id']) if self.datasets else "" # 默认 Ref ID 留空，允许搜索所有数据集

        new_search_data = {
            "id": new_id,
            "start_freq": tk.StringVar(value=default_start),
            "stop_freq": tk.StringVar(value=default_stop),
            "unit": tk.StringVar(value=default_unit),
            "data_id": tk.StringVar(value=default_data_id),
            "type": tk.StringVar(value="Max Value"),
            "display_status": tk.StringVar(value="Display"),
            "result_freq_hz": None, 
            "result_value": None,
            "frame": None
        }

        searches.append(new_search_data)
        self._draw_search_marker_frame(self, mark_data, container, plot_type, param)

        # 立即执行搜索并刷新图表以显示结果
        if not self.disable_refresh_var.get():
            self.update_plots()
        else:
            self._safe_refresh_markers(reset_limits=False)
            
        self.status_var.set(f"Peak Marker Search {new_id} added and executed.")
    
    def on_show_param_change(self, *args):
        """
        当 S 参数显示复选框状态改变时，触发图表刷新以更新 Normal 模式下的图表可见性，
        或 Max 模式下的曲线可见性。
        """
        # 无论 'Auto Refresh' 是否禁用，图表结构的改变（显示/隐藏子图）都需要立即刷新
        self.update_plots()


    def _setup_s_param_display_controls(self, parent_frame):
        """
        创建 S 参数显示控制组（即用户要求的 'Show Params' 选项区域）。
        该方法将创建 self.cb_frame。
        """
        # [修改点3] S-Parameter Display Control Group (使用 self.cb_frame)
        self.cb_frame = tk.LabelFrame(parent_frame, text="Show Params", 
                                      font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        
        # 注意：此处不 pack/grid，其可见性由 on_display_mode_change 统一控制。

        inner_param_frame = tk.Frame(self.cb_frame, bg="#f0f2f5")
        inner_param_frame.pack(anchor='w', padx=5, pady=2)
        
        # S11, S21, S12, S22 Checkboxes
        for p in self.params:
            var = self.show_param_vars[p]
            # 绑定 command 到 on_show_param_change
            tk.Checkbutton(inner_param_frame, text=p, variable=var, 
                           bg="#f0f2f5", anchor='w', justify='left', 
                           command=self.on_show_param_change).pack(side="left", padx=5, pady=0)


    # ---------- Layout switchers (Normal <-> Max) ----------
    def on_display_mode_change(self, *args):
        mode = self.display_mode.get()  # "Normal" 或 "Max"

        # ----------------------------------------------------
        # 1. Legend (Data ID) 显示控制
        # ----------------------------------------------------
        if hasattr(self, "legend_frame"):
            if mode == "Max":
                self.legend_frame.pack_forget()
            else:
                self.legend_frame.pack(fill="x", padx=5, pady=(5, 0), side="bottom")

        # ----------------------------------------------------
        # 2. Cursor Coordinates 始终显示（两种模式都需要）
        # ----------------------------------------------------
        if hasattr(self, "cursor_frame"):
            self.cursor_frame.pack(fill="x", padx=5, pady=(5, 0), side="bottom")

        # ----------------------------------------------------
        # 3. Show Params 复选框区域（现在两种模式都显示）
        # ----------------------------------------------------
        if hasattr(self, "cb_frame"):
            self.cb_frame.pack(fill="x", padx=5, pady=(2, 8))

        # ----------------------------------------------------
        # 4. 旧的 Marker 控件可见性（Limits & Marks 页面的控件，已被迁移，可保留兼容）
        # ----------------------------------------------------
        self.update_marker_controls_visibility()

        # ----------------------------------------------------
        # 5. Y 轴控制界面切换（原逻辑保持不变）
        # ----------------------------------------------------
        if mode == "Max":
            # Max 模式：显示统一 Y 轴控制
            if hasattr(self, 'normal_y_control_frame'):
                self.normal_y_control_frame.pack_forget()
            if hasattr(self, 'unified_y_control_frame'):
                self.unified_y_control_frame.pack(fill="both", expand=True)
            self.enter_max_mode()
        else:
            # Normal 模式：显示四个独立 Y 轴控制
            if hasattr(self, 'unified_y_control_frame'):
                self.unified_y_control_frame.pack_forget()
            if hasattr(self, 'normal_y_control_frame'):
                self.normal_y_control_frame.pack(fill="both", expand=True)
            self.exit_max_mode()

        # ----------------------------------------------------
        # 6. 【关键新增】Marker Legend Position 控件切换显示
        #     - Normal 模式 → 显示 4 个 S 参数标签页
        #     - Max 模式   → 只显示一个全局控件
        # ----------------------------------------------------
        if hasattr(self, 'update_marker_position_visibility'):
            self.update_marker_position_visibility()

        if hasattr(self, 'update_marker_position_ui'):
            # 确保控件绑定的是当前 Plot Type 对应的配置
            self.update_marker_position_ui()

        # ----------------------------------------------------
        # 7. 最终刷新图表（放在最后，确保所有 UI 状态已切换完毕）
        # ----------------------------------------------------
        if mode == "Normal":
            self.update_plots()
        else:
            self.plot_combined()
        #-------------------------------------    


    def update_marker_controls_visibility(self):
        mode = self.display_mode.get()
        for plot_type in ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"]:
            if plot_type not in self.data:
                continue
            for param in self.params:
                ui_refs = self.data[plot_type]["ui_refs"].get(param, {})
                if "legend_controls" not in ui_refs or "max_controls" not in ui_refs:
                    continue

                legend_label = ui_refs["legend_controls"]["label"]
                legend_combo = ui_refs["legend_controls"]["combo"]
                legend_custom = ui_refs["legend_controls"]["custom_frame"]

                max_label = ui_refs["max_controls"]["label"]
                max_combo = ui_refs["max_controls"]["combo"]
                max_custom = ui_refs["max_controls"]["custom_frame"]

                if mode == "Normal":
                    # 显示 Legend Pos，隐藏 Max Marker Config
                    legend_label.pack(side="left", padx=(10, 5))
                    legend_combo.pack(side="left", padx=5)
                    # 触发 legend custom 显示逻辑
                    self.marker_pos_configs[plot_type][param]["mode_var"].trace_add("write", lambda *a: self.on_legend_mode_change(plot_type, param))
                    self.on_legend_mode_change(plot_type, param)  # 立即更新 custom

                    max_label.pack_forget()
                    max_combo.pack_forget()
                    max_custom.pack_forget()
                else:  # Max
                    # 隐藏 Legend Pos，显示 Max Marker Config
                    legend_label.pack_forget()
                    legend_combo.pack_forget()
                    legend_custom.pack_forget()

                    max_label.pack(side="left", padx=(10, 5))
                    max_combo.pack(side="left", padx=5)
                    # 触发 max custom 显示逻辑
                    self.max_marker_pos_configs[plot_type]["mode_var"].trace_add("write", lambda *a: self.on_max_mode_change(plot_type))
                    self.on_max_mode_change(plot_type)  # 立即更新 custom

    def on_legend_mode_change(self, plot_type, param):
        # FIX: 检查 'legend_controls' 是否存在，以防止 Reset App 时的 KeyError。
        ui_refs = self.data[plot_type]["ui_refs"][param]
        if "legend_controls" not in ui_refs:
            return
            
        pos_config = self.marker_pos_configs[plot_type][param]
        mode = pos_config["mode_var"].get()
        custom_frame = ui_refs["legend_controls"]["custom_frame"]
        if mode == "Custom":
            custom_frame.pack(side="left", padx=(10, 5))
        else:
            custom_frame.pack_forget()

    def on_max_mode_change(self, plot_type):
        # FIX: 从 Max Marker 自己的配置中获取模式变量
        max_pos_config = self.max_marker_pos_configs[plot_type]
        mode = max_pos_config["mode_var"].get() 
        
        for param in self.params:
            if plot_type in self.data and param in self.data[plot_type]["ui_refs"]:
                # 检查 'max_controls' 是否存在 (保留上次的修复)
                ui_refs_param = self.data[plot_type]["ui_refs"][param]
                if "max_controls" not in ui_refs_param:
                    continue

                custom_frame = ui_refs_param["max_controls"]["custom_frame"]
                
                # --- 以下是重点修复区域 ---
                # 确保 custom_frame.pack(...) 是在 if 语句下正确缩进
                if mode == "Custom": # <-- 这是报错提示的第 878 行 (或附近)
                    custom_frame.pack(side="left", padx=(10, 5)) # <-- 这是报错提示的第 879 行 (或附近)
                else:
                    custom_frame.pack_forget()

    def _bind_max_mode_mpl_events(self):
        """
        Binds all necessary Matplotlib events (click, scroll, motion, pan)
        to the max_fig canvas. Called after self.max_canvas is created.
        Ensures events are bound exactly once (or rebound safely when needed).
        """
        # If figure or canvas not ready, do nothing
        if not self.max_fig or not hasattr(self.max_fig, 'canvas'):
            return

        # If we already have stored CIDs and they are non-empty, assume bound.
        # However, allow re-binding if dict is empty (fresh start) or if forced.
        if hasattr(self, 'max_cids') and self.max_cids:
            return

        canvas = self.max_fig.canvas

        # 1. 基础事件
        cid_click = canvas.mpl_connect('button_press_event', lambda e: self.add_marker_on_click_combined(e))
        cid_rclick = canvas.mpl_connect('button_press_event', lambda e: self.delete_marker_on_right_click(e))
        cid_scroll = canvas.mpl_connect('scroll_event', lambda e: self.on_scroll_zoom_combined(e))
        cid_motion = canvas.mpl_connect('motion_notify_event', lambda e: self._on_mouse_move_custom(e, 'COMBINED'))

        # 2. Dual-Button Pan 事件
        cid_pan_press = canvas.mpl_connect('button_press_event', lambda e: self.on_dual_button_pan_press(e))
        cid_pan_release = canvas.mpl_connect('button_release_event', self.on_dual_button_pan_release)
        cid_pan_motion = canvas.mpl_connect('motion_notify_event', self.on_dual_button_pan_motion)

        # 3. 统一存储所有 CIDs
        self.max_cids = {
            'click': cid_click,
            'rclick': cid_rclick,
            'scroll': cid_scroll,
            'motion': cid_motion,
            'pan_press': cid_pan_press,
            'pan_release': cid_pan_release,
            'pan_motion': cid_pan_motion
        }

        # 保存鼠标移动事件 ID 用作后续解绑
        self._cursor_move_cid = cid_motion


    def enter_max_mode(self):
        """
        Enter Max mode: create or show the combined chart area,
        ensure a valid canvas exists, rebind events, and trigger drawing.
        """
        # Hide individual param frames
        for p, cfg in self.plot_configs.items():
            try:
                cfg["frame"].grid_forget()
            except Exception:
                pass
        created = False
        # Create frame + figure + canvas if missing
        if not getattr(self, "max_frame", None):
            created = True
            self.max_frame = tk.LabelFrame(self.charts_frame, text="",
                                           font=("sans-serif", 12, "bold"), bg="#f0f2f5")
            self.max_frame.grid(row=0, column=0, rowspan=2, columnspan=2, sticky="nsew", padx=8, pady=8)
            # create figure and axes
            #self.max_fig = plt.Figure(figsize=(10, 7), dpi=120)
            #自适应DPI
            self.max_fig = plt.Figure(figsize=(10, 7), dpi=self.actual_dpi)
            self.max_ax = self.max_fig.add_subplot(111)
            # create a new FigureCanvasTkAgg and attach
            try:
                self.max_canvas = FigureCanvasTkAgg(self.max_fig, master=self.max_frame)
                self.max_canvas_widget = self.max_canvas.get_tk_widget()
                self.max_canvas_widget.pack(fill="both", expand=True)
            except Exception as e:
                self.max_canvas = None
                self.max_canvas_widget = None
            # toolbar (optional)
            try:
                toolbar_frame = tk.Frame(self.max_frame)
                self.max_toolbar = NavigationToolbar2Tk(self.max_canvas, toolbar_frame)
                self.max_toolbar.update()
                # disable default pan/zoom if needed
                try:
                    self._disable_mpl_default_pan_zoom(self.max_toolbar)
                except Exception:
                    pass
            except Exception as e:
                self.max_toolbar = None
        else:
            # Existing frame: ensure it is visible and that we have axes/canvas
            try:
                self.max_frame.grid(row=0, column=0, rowspan=2, columnspan=2, sticky="nsew", padx=8, pady=8)
            except Exception:
                pass
            # Ensure figure & axes exist
            if getattr(self, "max_fig", None) is None:
                try:
                    #self.max_fig = plt.Figure(figsize=(10, 7), dpi=120)
                    #自适应DIP
                    self.max_fig = plt.Figure(figsize=(10, 7), dpi=self.actual_dpi)
                    self.max_ax = self.max_fig.add_subplot(111)
                except Exception as e:
                    pass
            else:
                if not getattr(self.max_fig, "axes", None):
                    try:
                        self.max_ax = self.max_fig.add_subplot(111)
                    except Exception as e:
                        pass
                else:
                    try:
                        self.max_ax = self.max_fig.axes[0]
                    except Exception:
                        pass
            # If max_canvas missing or invalid, try to recreate it
            if not getattr(self, "max_canvas", None):
                try:
                    self.max_canvas = FigureCanvasTkAgg(self.max_fig, master=self.max_frame)
                    self.max_canvas_widget = self.max_canvas.get_tk_widget()
                    self.max_canvas_widget.pack(fill="both", expand=True)
                except Exception as e:
                    self.max_canvas = None
                    self.max_canvas_widget = None
            # Ensure toolbar present
            if not getattr(self, "max_toolbar", None):
                try:
                    toolbar_frame = tk.Frame(self.max_frame)
                    self.max_toolbar = NavigationToolbar2Tk(self.max_canvas, toolbar_frame)
                    self.max_toolbar.update()
                    try:
                        self._disable_mpl_default_pan_zoom(self.max_toolbar)
                    except Exception:
                        pass
                except Exception:
                    self.max_toolbar = None
            else:
                # try disable defaults again
                try:
                    self._disable_mpl_default_pan_zoom(self.max_toolbar)
                except Exception:
                    pass
        # At this point we either have a FigureCanvasTkAgg or not.
        # If we have one, call draw() to ensure figure.canvas gets attached.
        canvas_obj = getattr(self, "max_canvas", None)
        if canvas_obj:
            try:
                canvas_obj.draw() # ensure backend attaches canvas to figure
            except Exception as e:
                pass
        # Determine concrete object to bind mpl events on (prefer FigureCanvasTkAgg)
        bind_target = None
        if getattr(self, "max_canvas", None):
            bind_target = self.max_canvas
        else:
            # fallback: if Figure got a canvas attribute (rare until draw), use it
            if getattr(self, "max_fig", None) and getattr(self.max_fig, "canvas", None):
                bind_target = self.max_fig.canvas
        # If still no bind_target, attempt to (re)create a canvas once more
        if bind_target is None:
            try:
                self.max_canvas = FigureCanvasTkAgg(self.max_fig, master=self.max_frame)
                self.max_canvas_widget = self.max_canvas.get_tk_widget()
                self.max_canvas_widget.pack(fill="both", expand=True)
                self.max_canvas.draw()
                bind_target = self.max_canvas
            except Exception as e:
                bind_target = None
        # Now bind events robustly to the concrete bind_target
        if bind_target is not None:
            try:
                # --- 修复 1: 在重新连接之前，强制断开所有已存储的 Max 模式 CID ---
                # 清理 self.max_cids 中存储的所有事件连接
                for name, cid in list(getattr(self, "max_cids", {}).items()):
                    if cid is not None:
                        try:
                            bind_target.mpl_disconnect(cid)
                        except Exception:
                            pass
                self.max_cids = {} # 清空字典

                # 清理 _cursor_move_cid (原代码中尝试清理，但逻辑分散，在此集中清理更安全)
                if hasattr(self, "_cursor_move_cid") and self._cursor_move_cid is not None:
                    try:
                        bind_target.mpl_disconnect(self._cursor_move_cid)
                    except Exception:
                        pass
                    finally:
                        self._cursor_move_cid = None

                # ------------------- 修复 1 结束 -------------------
                
                # helper wrapper for cursor movement (保持原逻辑)
                def _on_mouse_move_cursor(event):
                    try:
                        if hasattr(self, "_on_mouse_move_custom"):
                            self._on_mouse_move_custom(event, "COMBINED")
                    except Exception:
                        pass
                        
                cid = None
                try:
                    # 重新连接鼠标移动事件
                    cid = bind_target.mpl_connect("motion_notify_event", _on_mouse_move_cursor)
                    self._cursor_move_cid = cid # 存储 CID
                except Exception as e:
                    pass
                    
                # --- 修复 2: 重新连接其他事件，并存储所有 CID 到 self.max_cids ---
                try:
                    # Marker (左键点击)
                    self.max_cids['click_marker'] = bind_target.mpl_connect('button_press_event', 
                                                                           lambda e: self.add_marker_on_click_combined(e))
                    # Marker 删除 (右键点击)
                    self.max_cids['click_delete'] = bind_target.mpl_connect('button_press_event', 
                                                                           lambda e: self.delete_marker_on_right_click(e))
                    # Zoom (滚轮)
                    self.max_cids['scroll_zoom'] = bind_target.mpl_connect('scroll_event', 
                                                                          lambda e: self.on_scroll_zoom_combined(e))
                    # Pan (双键拖拽 - 按下)
                    self.max_cids['pan_press'] = bind_target.mpl_connect('button_press_event', 
                                                                        lambda e: self.on_dual_button_pan_press(e))
                    # Pan (双键拖拽 - 释放)
                    self.max_cids['pan_release'] = bind_target.mpl_connect('button_release_event', 
                                                                          self.on_dual_button_pan_release)
                    # Pan (双键拖拽 - 移动)
                    self.max_cids['pan_motion'] = bind_target.mpl_connect('motion_notify_event', 
                                                                         self.on_dual_button_pan_motion)
                except Exception:
                    pass
                # ------------------- 修复 2 结束 -------------------
                    
            except Exception as e:
                pass
        else:
            pass

        # Manage drag-binding if needed
        try:
            enable_drag = not self.marker_click_enabled.get()
            if getattr(self, "max_canvas", None):
                self._manage_max_mode_drag_bindings(enable_drag)
        except Exception as e:
            pass
        # Force immediate draw + idle + tk update to force refresh
        try:
            if getattr(self, "max_canvas", None):
                try:
                    self.max_canvas.draw_idle()
                except Exception:
                    pass
                try:
                    self.max_canvas.draw()
                except Exception:
                    pass
            elif getattr(self, "max_fig", None) and getattr(self.max_fig, "canvas", None):
                try:
                    self.max_fig.canvas.draw_idle()
                except Exception:
                    pass
                try:
                    self.max_fig.canvas.draw()
                except Exception:
                    pass
        except Exception as e:
            pass
        # Ensure cursor frame visible
        try:
            self.cursor_frame.pack(fill="x", padx=5, pady=(5, 0), side="bottom")
        except Exception:
            pass
        self.max_mode_active = True
        # Finally, explicitly call update_plots and plot_combined to ensure drawing
        try:
            self.update_plots()
            # also try calling plot_combined directly if available
            if hasattr(self, "plot_combined"):
                try:
                    self.plot_combined(redraw_full=True)
                except Exception as e:
                    pass
        except Exception as e:
            pass
        #------------------------------------    


    def _disable_mpl_default_pan_zoom(self, toolbar):
        """解除 Matplotlib NavigationToolbar 的默认鼠标事件绑定。"""
        # Matplotlib Pan (平移) 默认绑定在左键 (Button 1)
        # Matplotlib Zoom (缩放) 默认绑定在右键 (Button 3)
        
        # 释放默认的 Pan 和 Zoom 模式 (如果有)
        toolbar.release_pan(None)
        toolbar.release_zoom(None)
        
        # 查找并解除与左键 (Button 1) 和右键 (Button 3) 相关的默认 press/release/motion 绑定
        
        # 导航工具栏在初始化时会连接一些默认事件。
        # 最直接的方法是重写或禁用其内部函数。
        
        # 禁用 press_pan 和 press_zoom 的默认行为
        # Matplotlib 内部使用 press_event 来启动拖拽
        if hasattr(toolbar, 'press_event'):
            # 解除 press_event 的绑定（这是最关键的绑定）
            # 注意：这可能会影响其他依赖 press_event 的功能，但能解决冲突
            toolbar.canvas.mpl_disconnect(toolbar._id_press)
            # 重新连接一个空函数或只调用自定义逻辑的函数（这里选择只断开）
            
            # 或者，更简单和安全的方法：直接重写 Pan 和 Zoom 按钮的行为，
            # 确保工具栏不处于任何活动模式。
            toolbar.pan() # 再次调用 pan() 会取消 pan 模式
            toolbar.zoom() # 再次调用 zoom() 会取消 zoom 模式

        # 最终确保没有任何模式处于激活状态
        toolbar._active = None

    # 注意：如果上述 Matplotlib 内部方法（如 _id_press）不可用，
    # 一个更强力但不太优雅的解决方案是直接覆盖 press_pan 和 press_zoom 方法为空操作。
    # toolbar.press_pan = lambda self, event: None 
    # toolbar.press_zoom = lambda self, event: None

    def exit_max_mode(self):
        # destroy or hide combined frame and restore individual frames
        if self.max_frame:
            # 1. 断开所有事件
            try:
                if self.max_fig and self.max_cids:
                    for k, cid in self.max_cids.items():
                        self.max_fig.canvas.mpl_disconnect(cid)
            except Exception:
                # 忽略断开失败的错误
                pass
            self.max_cids = {}
            
            # --- 【核心修复 1】: 断开 Max 模式下 Marker 拖拽相关的 CIDs ---
            try:
                canvas = self.max_fig.canvas
                if self.cid_max_drag_press is not None:
                    canvas.mpl_disconnect(self.cid_max_drag_press)
                    self.cid_max_drag_press = None
                if self.cid_max_drag_release is not None:
                    canvas.mpl_disconnect(self.cid_max_drag_release)
                    self.cid_max_drag_release = None
                if self.cid_max_drag_motion is not None:
                    canvas.mpl_disconnect(self.cid_max_drag_motion)
                    self.cid_max_drag_motion = None
            except Exception:
                pass
            # -------------------------------------------------------------
            
            # 2. 隐藏 Max 模式的 Frame
            self.max_frame.grid_forget()

            # --- 断开 Max 模式下的鼠标移动事件 ---
            try:
                if hasattr(self, "_cursor_move_cid"):
                    self.max_canvas.mpl_disconnect(self._cursor_move_cid)
                    self._cursor_move_cid = None
            except Exception:
                pass

            # 3. 清除 Figure，确保下次进入 Max 模式时是全新的画布
            if self.max_fig:
                self.max_fig.clear()
                # 重新设置 max_ax 为 None，强制 update_plots 重新创建 Axes
                self.max_ax = None

            # 4. 恢复 Normal 模式布局（Legend 在上，Cursor Coordinates 在下）
            try:
                if hasattr(self, "legend_frame"):
                    self.legend_frame.pack(fill="x", padx=5, pady=(5, 0), side="bottom")
                if hasattr(self, "cursor_frame"):
                    self.cursor_frame.pack(fill="x", padx=5, pady=(5, 0), side="bottom")
            except Exception:
                pass

            # 5. 恢复各图表布局
            self.restore_plots_layout()
        #---------------------------------    


    def restore_plots_layout(self):
        """
        退出 Max 模式或加载数据后，将 Normal 模式图表恢复到其动态网格位置，并显示工具栏。
        """
        
        # 1. 获取当前的动态布局配置
        layout_config = self._determine_normal_layout()
        
        # 2. 遍历当前所有在 self.plot_configs 中的图表
        # 注意：在 update_plots 中，self.plot_configs 已经被清空并只包含选中的图表配置
        for param, config in self.plot_configs.items():
            
            # 确保当前参数在布局配置中（即仍然处于被选中状态）
            if param in layout_config:
                
                # 获取动态布局配置
                grid_config = layout_config[param]
                
                # 将图表的 LabelFrame 重新 grid 回去，并应用动态布局
                config["frame"].grid(
                    row=grid_config['row'], 
                    column=grid_config['col'], 
                    rowspan=grid_config['rowspan'], 
                    columnspan=grid_config['colspan'], 
                    padx=8, pady=8, sticky="nsew"
                )
                
                # 恢复 Canvas Widget 的 pack 状态
                # 确保 'canvas_widget' 存在 (假设您已在 update_plots 中将其加入 config)
                if 'canvas_widget' in config and config['canvas_widget']:
                    config["canvas_widget"].pack(side=tk.TOP, fill="both", expand=True)

                # 恢复显示工具栏
                # 之前 'toolbar_frame' 报错，这里确保它存在且被 pack 恢复显示
                if 'toolbar_frame' in config and config['toolbar_frame']:
                    # 注意：如果之前在 exit_max_mode 中调用了 pack_forget()，这里需要 pack() 恢复
                    # 否则，如果 Max 模式中工具栏是隐藏的，这里应是 pack()
                    # 由于 Max 模式不显示 Normal 模式的工具栏，我们假设这里需要重新 pack
                    # 确保 toolbar_frame 的显示 (修复 KeyError 后，这里是逻辑恢复)
                    config["toolbar_frame"].pack(side=tk.BOTTOM, fill=tk.X, padx=2, pady=2)
                
                # --- 断开并重新绑定 Matplotlib 事件 ---
                # disconnect any per-plot custom cids
                for key in ('cid_click', 'cid_scroll', 'cid_mouse_move', 'cid_rclick', 'cid_drag_press', 'cid_drag_motion', 'cid_drag_release'):
                    if key in config and config[key] is not None:
                        try:
                            # 尝试断开连接，如果连接不存在则跳过
                            config["fig"].canvas.mpl_disconnect(config[key])
                        except:
                            pass
                        config.pop(key, None)
                        
                # 重新绑定事件
                # Marker Dragging Bindings
                if not self.marker_click_enabled.get():
                    cid_press = config["fig"].canvas.mpl_connect('button_press_event', self.on_marker_legend_press)
                    cid_motion = config["fig"].canvas.mpl_connect('motion_notify_event', self.on_marker_legend_motion)
                    cid_release = config["fig"].canvas.mpl_connect('button_release_event', self.on_marker_legend_release)
                    config['cid_drag_press'] = cid_press
                    config['cid_drag_motion'] = cid_motion
                    config['cid_drag_release'] = cid_release

                # 绑定左键点击添加 Marker 事件 (button=1)
                cid_click = config["fig"].canvas.mpl_connect('button_press_event', lambda e, pp=param: self.add_marker_on_click_normal(e, pp))
                config['cid_click'] = cid_click
                
                # 绑定右键点击删除 Marker 事件 (button=3)
                cid_rclick = config["fig"].canvas.mpl_connect('button_press_event', lambda e, pp=param: self.delete_marker_on_right_click(e, pp))
                config['cid_rclick'] = cid_rclick

            else:
                # 理论上不会发生，因为 update_plots 已经清空了未选中的参数
                # 但作为安全措施，确保未选中的图表被移除
                if 'frame' in config:
                    config['frame'].grid_forget()

        # 确保 Max 模式相关组件被隐藏
        if self.max_canvas and self.max_canvas.get_tk_widget().winfo_ismapped():
            self.max_canvas.get_tk_widget().pack_forget()

        self.charts_frame.update_idletasks()
        self.max_mode_active = False # 假设 restore_plots_layout 意味着退出 Max 模式
        
        # 再次调用 update_plots 确保图表内容和轴限制被正确同步和绘制
        # 这一步是必要的，因为布局改变后可能需要重新绘制数据
        # 【移除】: 必须移除或注释掉此行，否则会导致第三次重绘和闪烁
        #self.update_plots()

    def get_max_mode_color(self, data_id, param):
        """
        Max 模式颜色获取逻辑：
        1. 如果用户为该ID的该S参数自定义了颜色 → 使用用户颜色
        2. 否则 → 使用你原来的颜色计算公式
        """

        # -------- ① 用户自定义颜色优先 --------
        if hasattr(self, 'custom_sparam_colors'):
            if data_id in self.custom_sparam_colors:
                if param in self.custom_sparam_colors[data_id]:
                    return self.custom_sparam_colors[data_id][param]

        # -------- ② 没有用户颜色 → 用原来的默认颜色逻辑 --------
        param_index = self.params.index(param)
        color_index = ((data_id - 1) * len(self.params) + param_index) % len(COLOR_CYCLE)
        return COLOR_CYCLE[color_index]


    #新增回调函数
    def on_s_param_change(self, *args):
        """
        S 参数显示状态改变时的回调函数，触发图表刷新。
        """
        # 只有在 Normal 模式下，S 参数的勾选/取消才影响布局
        if self.display_mode.get() == "Normal":
            self.update_plots()

    #Normal模式显示逻辑计算函数
    def _determine_normal_layout(self):
        """
        根据 self.show_param_vars 的状态，决定 Normal 模式下的图表布局。
        返回一个字典，键为 S 参数 (str)，值为其 grid 配置 (dict: row, col, rowspan, colspan)。
        """
        selected_params = [p for p in self.params if self.show_param_vars[p].get()]
        layout = {}
        num_selected = len(selected_params)
        
        if num_selected == 4:
            # ✅ 2x2 标准布局
            layout = {
                "S11": {'row': 0, 'col': 0, 'rowspan': 1, 'colspan': 1},
                "S21": {'row': 0, 'col': 1, 'rowspan': 1, 'colspan': 1},
                "S12": {'row': 1, 'col': 0, 'rowspan': 1, 'colspan': 1},
                "S22": {'row': 1, 'col': 1, 'rowspan': 1, 'colspan': 1},
            }
            
        elif num_selected == 1:
            # ✅ 2x2 独占布局
            p = selected_params[0]
            layout[p] = {'row': 0, 'col': 0, 'rowspan': 2, 'colspan': 2}
            
        elif num_selected == 3:
            # 3个选中 (只取消了1个)
            unselected = [p for p in self.params if not self.show_param_vars[p].get()][0]
            
            if unselected in ["S11", "S22"]:
                # ✅ 只取消 S11 或 S22 (S21, S12 上部1x1; S22/S11 下部1x2)
                p_lower_full = "S22" if unselected == "S11" else "S11"
                
                layout["S21"] = {'row': 0, 'col': 0, 'rowspan': 1, 'colspan': 1}
                layout["S12"] = {'row': 0, 'col': 1, 'rowspan': 1, 'colspan': 1}
                layout[p_lower_full] = {'row': 1, 'col': 0, 'rowspan': 1, 'colspan': 2}
                
            elif unselected in ["S21", "S12"]:
                # ✅ 只取消 S21 或 S12 (S11, S22 上部1x1; S12/S21 下部1x2)
                p_lower_full = "S12" if unselected == "S21" else "S21"
                
                layout["S11"] = {'row': 0, 'col': 0, 'rowspan': 1, 'colspan': 1}
                layout["S22"] = {'row': 0, 'col': 1, 'rowspan': 1, 'colspan': 1}
                layout[p_lower_full] = {'row': 1, 'col': 0, 'rowspan': 1, 'colspan': 2}
                
        elif num_selected == 2:
            # ✅ 取消两个参数 (上部1x2 + 下部1x2，按优先级 S11 > S21 > S12 > S22)
            priority_map = {'S11': 0, 'S21': 1, 'S12': 2, 'S22': 3}
            # 按照优先级升序排列 (0最高)
            selected_with_priority = sorted(
                [(p, priority_map[p]) for p in selected_params], 
                key=lambda x: x[1]
            )
            
            p_upper_full = selected_with_priority[0][0] # 优先级最高的占上部
            p_lower_full = selected_with_priority[1][0] # 优先级次高的占下部
            
            layout[p_upper_full] = {'row': 0, 'col': 0, 'rowspan': 1, 'colspan': 2}
            layout[p_lower_full] = {'row': 1, 'col': 0, 'rowspan': 1, 'colspan': 2}

        return layout
  

    # 更新plots---------- Plot / draw logic ----------
    def update_plots(self):
        # 防止拖动时被误触发
        if getattr(self, 'dragging_marker_legend', False):
            return
        self.status_var.set("Refreshing plots... Please wait")

        # --- 变量初始化 ---
        layout_config = {}
        selected_params = []
        mode = self.display_mode.get()
        plot_type = self.plot_type.get()
        displayed_datasets = [d for d in self.datasets if d.get('is_displayed', True)]
        num_displayed = len(displayed_datasets)

        original_datasets = self.datasets
        self.datasets = displayed_datasets

        has_data = bool(self.datasets)
        DEFAULT_MIN_FREQ, DEFAULT_MAX_FREQ = 1e6, 10e9
        DEFAULT_MIN_Y, DEFAULT_MAX_Y = -40.0, 0.0
        try:
            min_f = self.min_freq.get()
            max_f = self.max_freq.get()
        except AttributeError:
            min_f, max_f = DEFAULT_MIN_FREQ, DEFAULT_MAX_FREQ

        # ------------------ 更新图例面板 ------------------
        for widget in self.legend_content.winfo_children():
            widget.destroy()

        legend_items = {}
        if self.datasets:
            for dataset in self.datasets:
                data_id = dataset['id']
                if data_id in self.custom_id_colors:
                    color = self.custom_id_colors[data_id]  # 用户自定义颜色
                else:
                    color = COLOR_CYCLE[(data_id - 1) % len(COLOR_CYCLE)]
                points = dataset['points']
                name = self.custom_id_names.get(str(data_id), f"ID {data_id}")
                legend_items[data_id] = {'label': f"({name}) : {points} points", 'color': color}

        if legend_items:
            for data_id, item in legend_items.items():
                row = tk.Frame(self.legend_content, bg="#f0f2f5")
                row.pack(fill="x", pady=1)
                tk.Label(row, bg=item['color'], width=2, height=1, relief="solid", bd=1).pack(side="left", padx=(5, 5))
                tk.Label(row, text=item['label'], font=("sans-serif", 9), bg="#f0f2f5", anchor="w", fg="#333333").pack(side="left", fill="x", expand=True)

        # ------------------ 状态检测 ------------------
        is_dragging = getattr(self, "dragging_marker_legend", False)
        is_refresh_disabled = getattr(self, 'disable_refresh_var', None).get() if hasattr(self, 'disable_refresh_var') else False

        # ==================================================
        # Normal 模式
        # ==================================================
        if mode == "Normal":
            can_reuse = is_dragging and bool(self.plot_configs)

            if not can_reuse:
                for widget in self.charts_frame.winfo_children():
                    if hasattr(self, 'max_frame') and widget is self.max_frame:
                        if widget.winfo_ismapped():
                            widget.grid_forget()
                            widget.pack_forget()
                        continue
                    widget.destroy()
                self.plot_configs = {}

                for i in range(2):
                    self.charts_frame.grid_columnconfigure(i, weight=1)
                    self.charts_frame.grid_rowconfigure(i, weight=1)

            layout_config = self._determine_normal_layout()
            selected_params = list(layout_config.keys())

            for param in selected_params:
                config = layout_config[param]

                # 【关键】拖拽时跳过重绘，保留 Zoom 和图例位置
                if is_dragging and can_reuse and param in self.plot_configs:
                    canvas = self.plot_configs[param]['canvas']
                    if canvas:
                        canvas.draw_idle()
                    continue

                # 常规重绘流程
                fig = plt.Figure(figsize=(4, 3), dpi=self.actual_dpi)
                ax = fig.add_subplot(111)
                fig.tight_layout(pad=1.0)

                frame = tk.LabelFrame(
                    self.charts_frame,
                    text=" ",
                    font=("sans-serif", 11, "bold"),
                    bg="#f0f2f5",
                    fg={"S11": "blue", "S21": "green", "S12": "red", "S22": "purple"}.get(param, "black")
                )
                frame.grid(row=config['row'], column=config['col'],
                           rowspan=config['rowspan'], columnspan=config['colspan'],
                           padx=8, pady=8, sticky="nsew")

                canvas = FigureCanvasTkAgg(fig, master=frame)
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=1)

                self.plot_configs[param] = {
                    'fig': fig, 'ax': ax, 'canvas': canvas, 'frame': frame
                }

                # 事件绑定
                canvas.mpl_connect('scroll_event', lambda e, p=param: self.on_scroll_zoom_normal(e, p))
                canvas.mpl_connect('motion_notify_event', lambda e: self._on_mouse_move_cursor_normal(e))
                canvas.mpl_connect('button_release_event', self.on_dual_button_pan_release)
                canvas.mpl_connect('motion_notify_event', self.on_dual_button_pan_motion)
                canvas.mpl_connect('button_press_event', lambda e, p=param: self.add_marker_on_click_normal(e, p))
                canvas.mpl_connect("button_press_event", self.on_marker_legend_press)
                canvas.mpl_connect("motion_notify_event", self.on_marker_legend_motion)
                canvas.mpl_connect("button_release_event", self.on_marker_legend_release)

                if has_data:
                    self.plot_parameter(ax, fig, canvas, param, plot_type)
                else:
                    ax.clear()
                    ax.set_title(param)
                    ax.set_xlim(min_f, max_f)
                    ax.set_ylim(DEFAULT_MIN_Y, DEFAULT_MAX_Y)
                    ax.text(0.5, 0.5, "No Data Loaded", transform=ax.transAxes,
                            ha='center', va='center', fontsize=12, color='gray')
                canvas.draw()

            # 清理未使用的 param
            if not can_reuse:
                for p in set(self.plot_configs.keys()) - set(selected_params):
                    del self.plot_configs[p]

        # ==================================================
        # Max 模式
        # ==================================================
        elif mode == "Max":
            if is_dragging and has_data:
                # 【拖拽快速通道】仅更新图例位置，不重绘
                artist = getattr(self, 'max_marker_legend_artists', {}).get(plot_type)
                if artist:
                    pos_config = self.max_marker_pos_configs[plot_type]
                    mode_val = pos_config["mode_var"].get()
                    x_val, y_val = 0.98, 0.98
                    h_align, v_align = 'right', 'top'

                    if mode_val == "Top Left": x_val, y_val, h_align, v_align = 0.02, 0.98, 'left', 'top'
                    elif mode_val == "Top Right": x_val, y_val, h_align, v_align = 0.98, 0.98, 'right', 'top'
                    elif mode_val == "Bottom Left": x_val, y_val, h_align, v_align = 0.02, 0.02, 'left', 'bottom'
                    elif mode_val == "Bottom Right": x_val, y_val, h_align, v_align = 0.98, 0.02, 'right', 'bottom'
                    elif mode_val == "Center": x_val, y_val, h_align, v_align = 0.5, 0.5, 'center', 'center'
                    elif mode_val == "Custom":
                        try:
                            x_val = float(pos_config["x_var"].get())
                            y_val = float(pos_config["y_var"].get())
                            h_align = 'left' if x_val < 0.5 else 'right'
                            v_align = 'bottom' if y_val < 0.5 else 'top'
                            if x_val == 0.5: h_align = 'center'
                            if y_val == 0.5: v_align = 'center'
                        except: pass

                    # 万能移动 + 对齐（支持 AnnotationBbox）
                    if hasattr(artist, 'set_position'):
                        artist.set_position((x_val, y_val))
                    else:
                        artist.xy = (x_val, y_val)
                        h_map = {'left': 0.0, 'center': 0.5, 'right': 1.0}
                        v_map = {'bottom': 0.0, 'center': 0.5, 'top': 1.0}
                        artist.box_alignment = (h_map.get(h_align, 0.5), v_map.get(v_align, 0.5))

                    if self.max_canvas:
                        self.max_canvas.get_tk_widget().delete("all")
                        self.max_canvas.draw_idle()

                self.datasets = original_datasets
                return  # 必须 return！防止重绘破坏 Zoom

            # 常规 Max 模式重绘
            if has_data:
                self.plot_combined()
                if self.max_ax and not is_refresh_disabled:
                    self.max_ax.autoscale_view(True, True, True)
                if self.max_canvas:
                    self.max_canvas.draw()
            else:
                if hasattr(self, 'max_ax') and self.max_ax:
                    self.max_ax.clear()
                    self.max_ax.set_title("")
                    self.max_ax.set_xlim(min_f, max_f)
                    self.max_ax.set_ylim(DEFAULT_MIN_Y, DEFAULT_MAX_Y)
                    self.max_ax.text(0.5, 0.5, "No Data Loaded", transform=self.max_ax.transAxes,
                                    ha='center', va='center', fontsize=12, color='gray')
                    if self.max_canvas:
                        self.max_canvas.draw()

        # ------------------ 恢复原始数据 ------------------
        self.datasets = original_datasets
        self.charts_frame.update_idletasks()
        self.root.update_idletasks()

        self.status_var.set(f"Plots refreshed: {num_displayed} visible dataset(s), {self.plot_type.get()}")   

  
    # Max模式配置（支持 Custom Search 的 First/Last Match）
    def plot_combined(self, redraw_full=True):
        # 1. 确保绘图环境可用
        if not getattr(self, "max_ax", None) or not getattr(self, "max_canvas", None):
            return
        ax = self.max_ax
        ax.clear()
        if not self.datasets:
            ax.text(0.5, 0.5, "No Data Loaded", transform=ax.transAxes, ha='center', va='center', fontsize=14, color='gray')
            self.max_canvas.draw()
            return
        # 2. 清理旧的 Figure 标题/SN 文本
        if self.max_fig:
            texts_to_remove = [t for t in self.max_fig.texts if t.get_position()[1] > 0.85]
            for t in texts_to_remove:
                t.remove()
        # 3. 初始化变量
        plot_type = self.plot_type.get()
        plot_title_info = self.title_var.get()
        all_y_values = []
        all_freq_values = []
        is_limit_check_enabled = self.limits_check_enabled.get()
        import numpy as np
        import tkinter as tk
        from matplotlib.ticker import MaxNLocator, MultipleLocator, AutoMinorLocator
        # 4. 绘制数据曲线
        # ==================== 终极修正：图例顺序改为 “先文件后参数” ====================
        visible_params = [p for p in self.params if self.show_param_vars[p].get()]

        # 关键修改：先遍历 dataset，再遍历参数 → 图例顺序完美！
        for dataset in self.datasets:
            data_id = dataset['id']
            custom_name = self.custom_id_names.get(str(data_id), f"ID {data_id}")
            
            for p in visible_params:
                limit_lines = self.data.get(plot_type, {}).get("limit_lines", {}).get(p, [])
                freq = dataset['freq']
                s = dataset['s_data'].get(p.lower())
                if s is None or len(s) == 0:
                    continue

                color = self.get_max_mode_color(data_id, p)
                freq_mhz = freq / 1e6
                y_data = None
                
                if plot_type == "Magnitude (dB)":
                    y_data = 20 * np.log10(np.abs(s) + 1e-20)
                elif plot_type == "Phase (deg)":
                    y_data = np.unwrap(np.angle(s)) * 180 / np.pi
                elif plot_type == "Group Delay (ns)":
                    y_data, temp_freq_mhz = self.calculate_group_delay(freq, s)
                    if temp_freq_mhz is not None:
                        freq_mhz = temp_freq_mhz

                if y_data is None:
                    continue

                pass_fail_suffix = ""
                if is_limit_check_enabled and limit_lines:
                    is_pass, has_overlap = self._check_dataset_limits(dataset, plot_type, p)
                    if not has_overlap:
                        pass_fail_suffix = "(N/A)"
                    elif is_pass:
                        pass_fail_suffix = " (PASS)"
                    else:
                        pass_fail_suffix = " (FAIL)"

                label_text = f"{p} {custom_name}{pass_fail_suffix}"
                ax.plot(freq_mhz, y_data, color=color, linewidth=1.0, label=label_text)
                
                all_y_values.extend(y_data)
                all_freq_values.extend(freq_mhz)
        # 5. 轴标签和网格
        ax.set_xlabel("Frequency (MHz)")
        y_unit = {"Magnitude (dB)": "dB", "Phase (deg)": "deg", "Group Delay (ns)": "ns"}.get(plot_type, "")
        ax.set_ylabel(f"{plot_type.split('(')[0].strip()} ({y_unit})")
        ax.grid(True, which='major', alpha=0.3)
        # 6. Y 轴范围（统一控制）
        unified_y_mode = self.axis_configs["unified_y_mode"].get()
        is_custom_y = False
        if unified_y_mode == "Custom":
            try:
                y_min_custom = float(self.axis_configs["unified_y_min"].get())
                y_max_custom = float(self.axis_configs["unified_y_max"].get())
                ax.set_ylim(y_min_custom, y_max_custom)
                ax.yaxis.set_major_locator(MaxNLocator(12))
                is_custom_y = True
                ax.yaxis.set_minor_locator(AutoMinorLocator(2))
                ax.grid(True, which='minor', linestyle=':', linewidth=0.5, color='gray', alpha=0.5)
            except ValueError:
                pass
        if not is_custom_y and all_y_values:
            valid_y = np.array([v for v in all_y_values if np.isfinite(v)])
            if valid_y.size > 0:
                y_min_data, y_max_data = np.min(valid_y), np.max(valid_y)
                y_min, y_max, y_step = self._calculate_friendly_y_limits(y_min_data, y_max_data)
                ax.set_ylim(y_min, y_max)
                ax.yaxis.set_major_locator(MultipleLocator(y_step))
                ax.yaxis.set_minor_locator(MultipleLocator(y_step / 2))
                ax.grid(True, which='minor', linestyle=':', linewidth=0.5, color='gray', alpha=0.5)
        # 7. X 轴设置
        ax.xaxis.set_major_locator(MaxNLocator(15))
        if self.axis_configs["x_mode"].get() == "Custom":
            try:
                start_val = float(self.axis_configs["x_start"].get())
                stop_val = float(self.axis_configs["x_stop"].get())
                unit = self.axis_configs["x_unit"].get()
                x_start_mhz = start_val * 1000 if unit == "GHz" else start_val
                x_stop_mhz = stop_val * 1000 if unit == "GHz" else stop_val
                ax.set_xlim(x_start_mhz, x_stop_mhz)
            except ValueError:
                pass
        x_min_mhz, x_max_mhz = ax.get_xlim()
        ax.xaxis.set_minor_locator(AutoMinorLocator(2))
        ax.grid(True, which='minor', linestyle=':', linewidth=0.5, color='gray', alpha=0.5)
        # 8. Limit Lines
        if plot_type in self.data and self.datasets:
            for p in visible_params:
                for line in self.data[plot_type]["limit_lines"].get(p, []):
                    try:
                        start_val = float(line["start"].get())
                        start_unit = line["start_unit"].get()
                        stop_val = float(line["stop"].get())
                        stop_unit = line["stop_unit"].get()
                        
                        # 频率转换成 MHz
                        start_mhz = start_val * 1000 if start_unit == "GHz" else start_val
                        stop_mhz = stop_val * 1000 if stop_unit == "GHz" else stop_val
                        
                        # Y 轴值
                        lower = float(line["lower"].get())
                        upper = float(line["upper"].get())
                        
                        ltype = line["type"].get()

                        # 限制线绘制的 X 轴范围
                        x_min_mhz, x_max_mhz = ax.get_xlim()
                        min_f = max(x_min_mhz, min(start_mhz, stop_mhz))
                        max_f = min(x_max_mhz, max(start_mhz, stop_mhz))
                        
                        if min_f < max_f:
                            # 关键：计算绘制范围内的 Y 轴插值
                            # 限制线是一条从 (start_mhz, lower) 到 (stop_mhz, upper) 的直线
                            
                            # X 坐标轴上的起点和终点
                            x_line_start = min_f 
                            x_line_stop = max_f
                            
                            # Y 坐标轴上的起点和终点 (线性插值)
                            # 如果 start_mhz == stop_mhz，则为水平线，y_line_start = y_line_stop = (lower + upper) / 2
                            if abs(start_mhz - stop_mhz) < 1e-6: # 检查是否为水平线（频率相同）
                                y_line_start = lower
                                y_line_stop = upper # 实际上此时 lower 和 upper 相同没关系，但为了逻辑统一，我们不插值
                                # 考虑到您的需求是斜线，如果频率相同，则它们应该是水平的，但用户输入的 lower/upper 仍可能不同。
                                # 由于 UI 设计是 (Start Freq, Lower) 到 (Stop Freq, Upper)，如果 Start=Stop，则它应该只是一条垂直的线，但我们只画水平/斜线。
                                # 假设 Start != Stop
                                
                            else:
                                # 斜率 m = (upper - lower) / (stop_mhz - start_mhz)
                                # Y(x) = lower + m * (x - start_mhz)
                                m = (upper - lower) / (stop_mhz - start_mhz)
                                y_line_start = lower + m * (x_line_start - start_mhz)
                                y_line_stop = lower + m * (x_line_stop - start_mhz)

                            # --- Upper Limit Line 绘制 ---
                            if ltype in ["Max", "Band", "Upper Only", "Upper/Lower", "Upper Limit"]:
                                ax.plot(
                                    [x_line_start, x_line_stop], 
                                    [y_line_start, y_line_stop], # FIX: 使用插值后的 Y 值
                                    color='blue', 
                                    linestyle='-', 
                                    linewidth=1.0, 
                                    zorder=4
                                )
                            
                            # --- Lower Limit Line 绘制 ---
                            if ltype in ["Min", "Band", "Lower Only", "Upper/Lower", "Lower Limit"]:
                                ax.plot(
                                    [x_line_start, x_line_stop], 
                                    [y_line_start, y_line_stop], # FIX: 使用插值后的 Y 值
                                    color='blue', # 假设 Lower Limit 用蓝色虚线，如果需要绿色，请改成 'green'
                                    linestyle='--', 
                                    linewidth=1.0, 
                                    zorder=4
                                )
                    except Exception:
                        pass
        # 9. 初始化 Marker Artists 列表
        if not hasattr(self, 'max_marker_artists'):
            self.max_marker_artists = []
        else:
            for artist in self.max_marker_artists:
                try:
                    artist.remove()
                except:
                    pass
            self.max_marker_artists = []
        visible_marker_info_list = []
        # --- 获取当前 X 轴范围 ---
        x_min_mhz, x_max_mhz = ax.get_xlim()
        # --- 9.1 绘制普通 Marker 和 Search Marker（统一逻辑）---
        if plot_type in self.data:
            for p in visible_params:
                # 普通 Marker
                for mark in self.data[plot_type]["marks"].get(p, []):
                    try:
                        if mark.get("display_status", tk.StringVar(value="Display")).get() != "Display":
                            continue
                        selected_data_id = mark["data_id"].get()
                        dataset = next((d for d in self.datasets if str(d['id']) == selected_data_id), None)
                        if not dataset:
                            continue
                        freq = dataset['freq']
                        s_data = dataset['s_data'][p.lower()]
                        color = self.get_max_mode_color(dataset['id'], p)
                        mark_id = mark["id"]
                       
                        y_pt = None # 最终的 Y 值 (数值)
                        x_pt_original = None # 原始 X 坐标 (MHz)
                        y_str = "N/A" # Legend 中显示的 Y 字符串
                        x_display = "" # Legend 中显示的 X 字符串
                        plot_marker_point = False
                       
                        # 1. 计算 Y 数据
                        if plot_type == "Magnitude (dB)":
                            data_array = 20 * np.log10(np.abs(s_data) + 1e-20)
                        elif plot_type == "Phase (deg)":
                            data_array = np.unwrap(np.angle(s_data)) * 180 / np.pi
                        elif plot_type == "Group Delay (ns)":
                            data_array, _ = self.calculate_group_delay(freq, s_data)
                        else:
                            continue
                       
                        if data_array is None or len(freq) < 2:
                             y_str = "N/A (No S-data)"
                        
                        # S2P 文件数据范围 (Hz)
                        min_f_hz = freq[0]
                        max_f_hz = freq[-1]
                        # ==================== 【Search Marker】 ====================
                        if mark.get("is_search", False):
                            # 确保在局部作用域内可以使用 tk (如果 tk 不在文件头部导入的话，需要加上)
                            try:
                                import tkinter as tk
                            except ImportError:
                                # 假设 tkinter 已经在类或文件头部导入
                                pass
                            start_str = mark["start"].get()
                            stop_str = mark["stop"].get()
                            unit = mark["unit"].get()
                           
                            # 初始化 x_display
                            x_display = f"@{start_str}-{stop_str}{unit}"
                           
                            # 频率单位转换
                            try:
                                start_val = float(start_str)
                                stop_val = float(stop_str)
                            except ValueError:
                                y_str = "Invalid Freq Value"
                                continue
                            unit_multiplier = 1e9 if unit == "GHz" else 1e6 if unit == "MHz" else 1e3 if unit == "KHz" else 1
                            start_hz = start_val * unit_multiplier
                            stop_hz = stop_val * unit_multiplier
                            f_min_hz, f_max_hz = min(start_hz, stop_hz), max(start_hz, stop_hz)
                           
                            range_no_overlap = (f_max_hz < min_f_hz) or (f_min_hz > max_f_hz)
                           
                            if range_no_overlap:
                                # **超范围**
                                y_str = "Out of Freq Range"
                                x_display = f"{start_str}-{stop_str}{unit}"
                            else:
                                mask = (freq >= f_min_hz) & (freq <= f_max_hz)
                               
                                if np.any(mask):
                                    y_masked = data_array[mask]
                                    freq_masked = freq[mask]
                                    search_type = mark["search_type"].get()
                                   
                                    # --- 逻辑：确定目标值和匹配索引 ---
                                    if search_type == "Max Value":
                                        idx = np.argmax(y_masked)
                                        precise_f_hz = float(freq_masked[idx])
                                        y_pt = float(y_masked[idx])
                                    elif search_type == "Min Value":
                                        idx = np.argmin(y_masked)
                                        precise_f_hz = float(freq_masked[idx])
                                        y_pt = float(y_masked[idx])
                                    elif search_type == "Custom Search":
                                        # Read custom value & match type with improved robustness (与 Normal 一致)
                                        custom_val = 0.0  # Default fallback
                                        try:
                                            custom_val_str = mark.get("custom_value", tk.StringVar(value="0.0"))
                                            if isinstance(custom_val_str, tk.StringVar):
                                                custom_val = float(custom_val_str.get().strip())
                                            else:
                                                custom_val = float(str(custom_val_str).strip())
                                        except (ValueError, TypeError, AttributeError):
                                            custom_val = 0.0  # Specific exceptions for better debugging
                                       
                                        match_type = "First Match"  # Unified default
                                        allowed_match_types = ["First Match", "Last Match"]
                                        try:
                                            cm = mark.get("match_type", tk.StringVar(value="First Match"))  # Correct key: "match_type" from source code
                                            if isinstance(cm, tk.StringVar):
                                                candidate = cm.get().strip()
                                            else:
                                                candidate = str(cm).strip()
                                           
                                            # Validate and set
                                            if candidate in allowed_match_types:
                                                match_type = candidate
                                            else:
                                                match_type = "First Match"  # Fallback to default if invalid
                                        except (ValueError, TypeError, AttributeError, KeyError):
                                            match_type = "First Match"
                                       
                                        # Optional: Log invalid values for debugging (comment out in production)
                                        # print(f"Warning: Invalid match_type '{candidate}' fallback to '{match_type}'")
                                        # call helper (expects freq in Hz and array)
                                        precise = self._find_custom_match_freq_hz(custom_val, freq_masked, y_masked, match_type)
                                        if precise is None:
                                            # fallback: nearest
                                            idx_close = np.argmin(np.abs(y_masked - custom_val))
                                            precise = float(freq_masked[idx_close])
                                            y_pt = float(y_masked[idx_close])
                                        else:
                                            # get y at that precise freq by interpolation (linear)
                                            # use safe_interp with Hz input if available
                                            val_interp = self.safe_interp(precise, freq, data_array)
                                            y_pt = float(val_interp) if val_interp is not None else float(y_masked[np.argmin(np.abs(freq_masked - precise))])
                                        precise_f_hz = float(precise)
                                    else:
                                        # unsupported type -> skip
                                        continue
                                    precise_f_mhz = precise_f_hz / 1e6
                                    # format display
                                    precise_f_str = f"{precise_f_mhz:.3f}".rstrip("0").rstrip(".")
                                    x_display = f"{start_str}-{stop_str}{unit}, {precise_f_str} MHz"
                                    # 修正后的代码
                                    y_str = f"{y_pt:.3f} ns" if plot_type == "Group Delay (ns)" else f"{y_pt:.3f} {y_unit}"
                                    #y_str = f"{y_pt:.3f}" if plot_type == "Group Delay (ns)" else f"{y_pt:.3f} {y_unit}"
                                    x_pt_original = precise_f_mhz
                                    plot_marker_point = True
                                else:
                                    # 搜索范围在数据范围内，但无数据点命中
                                    y_str = "N/A (No data in range)"
                                    x_display = f"{start_str}-{stop_str}{unit} (No Data)"
                        # ==================== 【普通 Marker】 ====================
                        else:
                            target_freq_hz = self._get_marker_freq_hz(mark)
                            f_str = mark["freq"].get()
                            unit = mark["unit"].get()
                            x_display = f"{f_str} {unit}"
                           
                            # 1. 检查 S2P 文件数据范围
                            marker_is_in_data_range = (target_freq_hz >= min_f_hz) and (target_freq_hz <= max_f_hz)
                            val = None
                            if marker_is_in_data_range:
                                # 2. 仅在 S2P 数据范围内时尝试插值
                                val = self.safe_interp(target_freq_hz, freq, data_array)
                           
                            if val is not None and marker_is_in_data_range:
                                x_pt_original = target_freq_hz / 1e6 # 转换为 MHz
                                y_pt = val
                                y_str = f"{y_pt:.3f} {y_unit}"
                                plot_marker_point = True
                            else:
                                # 3. 超范围 / 插值失败
                                y_str = "Out of Freq Range" if not marker_is_in_data_range else "N/A (Interp Failed)"
                        # --------------------- 【统一绘图和 Legend 生成】 ---------------------
                       
                        # 绘制
                        if plot_marker_point:
                            # 必须满足：在图表当前的 X 轴显示范围内
                            marker_is_in_plot_range = (x_pt_original >= x_min_mhz) and (x_pt_original <= x_max_mhz)
                           
                            if marker_is_in_plot_range:
                                x_pt_plot = x_pt_original # 严格模式，如果超出绘图范围则不绘制
                               
                                line = ax.plot(x_pt_plot, y_pt, '.', markerfacecolor='none',
                                                markeredgecolor=color, markersize=4, markeredgewidth=2, zorder=5)
                                text = ax.annotate(mark_id, xy=(x_pt_plot, y_pt), xytext=(5, 5),
                                                     textcoords='offset points', fontsize=9, color=color, zorder=6)
                                self.max_marker_artists.extend(line)
                                self.max_marker_artists.append(text)
                            # else: 超出图表显示范围，跳过绘制点和标注
                        # Legend 信息
                        custom_name = self.custom_id_names.get(selected_data_id, f"ID {selected_data_id}")
                        # 使用 y_str, 它包含了数值或状态信息
                        full_legend = f"{mark_id} ({p} {custom_name}) @{x_display}, {y_str}"
                        visible_marker_info_list.append((mark_id, p, full_legend, selected_data_id))
                    except Exception as e:
                        # 捕获任何意外错误，并确保不会崩溃
                        continue
        # 10. 数据线图例
        ax.legend(loc='best', fontsize=9, framealpha=0.7)
        # 11. Marker Legend 绘制（Max 模式终极版：文字颜色 = Trace 实际颜色 + 可拖动背景框）
        if visible_marker_info_list:
            import matplotlib.offsetbox as moffsetbox

            if not hasattr(self, 'max_marker_legend_artists'):
                self.max_marker_legend_artists = {}

            # 清理旧图例
            old_ab = self.max_marker_legend_artists.get(plot_type)
            if old_ab:
                try: old_ab.remove()
                except: pass

            # ==================== Marker Legend 完美排序（你想要的终极顺序）====================
            PARAM_ORDER = {'S11': 0, 'S21': 1, 'S12': 2, 'S22': 3}

            def sort_key(info):
                mark_id, param, full_legend, data_id_str = info
                try:
                    data_id = int(data_id_str)
                except:
                    data_id = 999999

                # 获取该 marker 所属的 dataset（用于读取自定义名称排序更准）
                dataset = next((d for d in self.datasets if d['id'] == data_id), None)
                sort_id = dataset['sort_index'] if dataset and 'sort_index' in dataset else data_id

                param_idx = PARAM_ORDER.get(param, 99)

                # 如果有 get_marker_id_number 函数，用它排 marker 序号（M1 < M2 < M3）
                marker_num = 0
                if hasattr(self, 'get_marker_id_number'):
                    try:
                        marker_num = self.get_marker_id_number(mark_id)
                    except:
                        marker_num = 0

                # 终极排序键：先按 ID（加载顺序），再按参数顺序（S11→S21→S12→S22），再按 Marker 编号
                return (sort_id, param_idx, marker_num)

            sorted_info = sorted(visible_marker_info_list, key=sort_key)

            # 位置
            pos_config = self.max_marker_pos_configs[plot_type]
            mode = pos_config["mode_var"].get()
            x_val, y_val = 0.98, 0.98
            h_align, v_align = 'right', 'top'

            # --- 原始位置确定 ---
            if mode == "Top Left":       x_val, y_val, h_align, v_align = 0.02, 0.98, 'left',   'top'
            elif mode == "Top Right":    x_val, y_val, h_align, v_align = 0.98, 0.98, 'right',  'top'
            elif mode == "Bottom Left":  x_val, y_val, h_align, v_align = 0.02, 0.02, 'left',   'bottom'
            elif mode == "Bottom Right": x_val, y_val, h_align, v_align = 0.98, 0.02, 'right',  'bottom'
            elif mode == "Center":       x_val, y_val, h_align, v_align = 0.5,  0.5,  'center', 'center'
            
            # --- 【新增：自动避让 S-参数标签逻辑】 ---
            # 仅在非 Custom 模式下，且位置在四角时才进行垂直调整
            if mode != "Custom":
                # 偏移量：0.13 的归一化坐标，用于将图例推离角落
                #OFFSET从0.13改为0.01
                OFFSET = 0.01 
                if mode in ["Top Left", "Top Right"]:
                    # 位于顶部角落，向下推
                    y_val = 0.98 - OFFSET # 0.98 -> 0.85
                elif mode in ["Bottom Left", "Bottom Right"]:
                    # 位于底部角落，向上推
                    y_val = 0.02 + OFFSET # 0.02 -> 0.15
            
            # --- Custom 模式逻辑（保持不变） ---
            elif mode == "Custom":
                try:
                    x_val = float(pos_config["x_var"].get())
                    y_val = float(pos_config["y_var"].get())
                    # 保持 Custom 模式下的对齐逻辑
                    h_align = 'left' if x_val < 0.5 else 'right'
                    v_align = 'bottom' if y_val < 0.5 else 'top'
                    if x_val == 0.5: h_align = 'center'
                    if y_val == 0.5: v_align = 'center'
                except: pass
            # ----------------------------------------
            # 文字颜色 = Trace 真实颜色
            text_areas = []
            auto_font_color_enabled = hasattr(self, 'auto_font_color_enabled') and self.auto_font_color_enabled.get()

            for mark_id, param, full_text, data_id_str in sorted_info:
                trace_color = self.get_max_mode_color(int(data_id_str), param)
                color = trace_color if auto_font_color_enabled else 'black'
                ta = moffsetbox.TextArea(full_text, textprops=dict(color=color, fontsize=9, ha=h_align, va='center'))
                text_areas.append(ta)

            #vp = moffsetbox.VPacker(children=text_areas, align='left' if h_align=='left' else 'right' if h_align=='right' else 'center', pad=0, sep=3)
            # 强制左对齐，无论图例在左中右，文字永远从左边开始排列
            vp = moffsetbox.VPacker(children=text_areas, align='left', pad=0, sep=3)
            box_align_x = 1.0 if h_align == 'right' else 0.0 if h_align == 'left' else 0.5
            box_align_y = 1.0 if v_align == 'top' else 0.0 if v_align == 'bottom' else 0.5
            bbox_params = self._get_marker_legend_bbox_params()

            ab = moffsetbox.AnnotationBbox(
                vp, (x_val, y_val),
                xycoords='axes fraction',
                boxcoords='axes fraction',
                box_alignment=(box_align_x, box_align_y),
                frameon=True,
                pad=0.45,
                bboxprops=dict(
                    boxstyle=bbox_params.get('boxstyle', 'round,pad=0.4'),
                    facecolor=bbox_params.get('facecolor', '#ffffff'),
                    edgecolor='none',
                    alpha=bbox_params.get('alpha', 0.9),
                    linewidth=0
                ),
                zorder=10
            )
            ax.add_artist(ab)

            # 关键：只存 ab，绝不提 txt_artist！
            self.max_marker_legend_artists[plot_type] = ab

        else:
            # 无 marker 清理
            old = self.max_marker_legend_artists.get(plot_type)
            if old:
                try: old.remove()
                except: pass
            self.max_marker_legend_artists[plot_type] = None
        # 12. 更新引用
        if not hasattr(self, 'max_marker_legend_artists'):
            self.max_marker_legend_artists = {}
        # 13. 标题和布局
        if self.max_fig:
            #取消顶部SN显示
            #sn_text = f"{plot_title_info}"
            sn_text = f""
            self.max_fig.text(0.5, 0.97, sn_text, fontsize=14, ha='center', va='top', fontweight='bold')
            self.max_fig.subplots_adjust(top=0.92, bottom=0.08, left=0.10, right=0.95)
        if redraw_full:
            self.max_canvas.draw()
        #------------------------------
   

    def _get_y_data_for_limit_calc(self, dataset, param, plot_type):
        """Helper to get calculated Y data array for a specific dataset and parameter."""
        # 确保 S 参数数据存在
        if param.lower() not in dataset['s_data']:
            return np.array([])
            
        s = dataset['s_data'][param.lower()]
        freq = dataset['freq']
        
        if len(s) == 0:
            return np.array([])
            
        # Apply data transformation based on plot_type
        y_data = np.array([])
        if plot_type == "Magnitude (dB)":
            # 使用 1e-20 确保对数运算不会因为 0 报错
            y_data = 20 * np.log10(np.abs(s) + 1e-20) 
        elif plot_type == "Phase (deg)":
            y_data = np.unwrap(np.angle(s)) * 180 / np.pi
        elif plot_type == "Group Delay (ns)":
            # 假设 self.calculate_group_delay 是可用的群延时计算方法
            try:
                # Group delay calculation expects freq in Hz and s_data
                y_data, _ = self.calculate_group_delay(freq, s) 
            except Exception:
                return np.array([])
        
        return y_data

    def _calculate_friendly_y_limits(self, y_min_data, y_max_data, target_steps=8, param_name=None):
        """
        计算友好的 Y 轴限制和步长。
        根据 param_name 优先选择 5 或 10 的倍数作为主步长。
        顶部刻度优化：确保 y_max 比 y_max_data 至少高 2.0 个单位。
        """
        # --- 边界情况处理 ---
        if y_min_data == y_max_data:
            # ... (代码不变)
            y_min = y_min_data - 5.0
            y_max = y_min_data + 5.0
            step = 2.0
            if abs(y_min_data) < 1.0:
                 y_min = -2.0
                 y_max = 2.0
            return y_min, y_max, step

        data_range = y_max_data - y_min_data
        
        # 尝试计算一个基础步长 (base_step)
        base_step = data_range / target_steps
        if base_step <= 0: base_step = 1.0 

        # 确定友好的步长 (Friendly Step)
        exponent = np.floor(np.log10(base_step))
        power_of_10 = 10**exponent
        
        # --- 根据 S-参数类型定制候选步长 ---
        if param_name and param_name.upper() in ["S11", "S22"]:
            # S11, S22 (反射系数): 优先使用 5 的倍数作为美观步长
            # 候选步长：5*10^n, 2*10^n, 1*10^n (略去 10*10^n，除非 base_step 很大)
            candidates = [5 * power_of_10, 2 * power_of_10, 1 * power_of_10]
            # 补充一个 10*power_of_10，以防数据范围太大
            if 10 * power_of_10 > candidates[0]:
                 candidates.insert(0, 10 * power_of_10)
                 
        elif param_name and param_name.upper() in ["S21", "S12"]:
            # S21, S12 (传输系数): 优先使用 10 的倍数作为美观步长
            # 候选步长：10*10^n, 5*10^n, 2*10^n, 1*10^n
            candidates = [10 * power_of_10, 5 * power_of_10, 2 * power_of_10, 1 * power_of_10]
        else:
            # 默认或 Group Delay/Phase: 标准友好步长
            candidates = [10 * power_of_10, 5 * power_of_10, 2 * power_of_10, 1 * power_of_10]
        # --- 定制结束 ---
        
        friendly_step = candidates[0]
        for c in candidates:
             if c >= base_step:
                 friendly_step = c
             else:
                 break

        step = friendly_step
        
        # --- 核心优化逻辑：确定 Y 轴范围（与之前保持一致的美观和缓冲逻辑） ---
        
        BUFFER_DISTANCE = 2.0 
        target_max = y_max_data + BUFFER_DISTANCE
        
        y_min = np.floor(y_min_data / step) * step
        
        if y_max_data >= 0:
            y_max = np.ceil(target_max / step) * step
            
        else: # y_max_data < 0，数据为负，例如 dB 图
            if target_max <= 0.0:
                y_max = 0.0
            else:
                # 初始上限：将 target_max 向上取整到步长的倍数
                y_max_coarse = np.ceil(target_max / step) * step
                
                # 限制 y_max 避免在数据靠近 0dB 时，上限跳到 10 或更高
                if target_max <= 2.0:
                    y_max = 2.0
                elif target_max <= 5.0:
                    y_max = 5.0
                elif target_max <= 10.0:
                    # 如果 target_max 在 5 到 10 之间，用 5 的倍数取整
                    y_max = np.ceil(target_max / 5.0) * 5.0
                else:
                    y_max = y_max_coarse
                    
        # 确保 Y 轴范围至少有一个步长
        if y_max <= y_min:
            y_max = y_min + step

        return y_min, y_max, step

    # 新增：用于输出图像的纯Matplotlib绘图方法（不依赖Tk Canvas）

    #Normal模式配置
    def plot_parameter_output(self, ax, fig, param, plot_type):
        # Normal 模式单参数绘制（支持 Custom Search）
        if not self.show_param_vars[param].get():
            ax.clear()
            ax.set_title("")
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_xlabel("")
            ax.set_ylabel("")
            ax.grid(False)
            ax.text(0.5, 0.5, f"{param} Hidden", transform=ax.transAxes,
                    ha='center', va='center', fontsize=14, color='gray')
            if param in self.normal_marker_legend_artists:
                self.normal_marker_legend_artists[param] = None
            return

        ax.clear()
        ax.set_title(param, fontsize=12, fontweight='bold')
        is_smith_chart = False
        ax.set_aspect('equal' if is_smith_chart else 'auto')

        # marker legend 内容收集
        visible_marker_info_list = []
        all_y_values = []
        all_freq_values = []

        # 确定 y 单位与标签
        y_unit = ""
        if plot_type == "Magnitude (dB)":
            y_unit = "dB"
            ax.set_ylabel("Magnitude (dB)")
        elif plot_type == "Phase (deg)":
            y_unit = "deg"
            ax.set_ylabel("Phase (deg)")
        elif plot_type == "Group Delay (ns)":
            y_unit = "ns"
            ax.set_ylabel("Group Delay (ns)")

        import numpy as np
        from matplotlib.ticker import MultipleLocator, AutoMinorLocator, MaxNLocator

        # --- 绘制主曲线 ---
        for dataset in self.datasets:
            data_id = dataset['id']
            freq = dataset['freq']   # Hz
            s = dataset['s_data'][param.lower()]
            if data_id in self.custom_id_colors:
                color = self.custom_id_colors[data_id]  # 用户自定义颜色
            else:            
                color = COLOR_CYCLE[(int(data_id) - 1) % len(COLOR_CYCLE)]

            if len(s) == 0:
                continue
            freq_mhz = freq / 1e6
            all_freq_values.extend(freq_mhz)

            label = f"ID {data_id}"
            if plot_type == "Magnitude (dB)":
                y_data = 20 * np.log10(np.abs(s) + 1e-20)
                ax.plot(freq_mhz, y_data, color=color, linewidth=1.0, label=label)
                all_y_values.extend(y_data)
                ax.set_xlabel("Frequency (MHz)")
            elif plot_type == "Phase (deg)":
                y_data = np.unwrap(np.angle(s)) * 180 / np.pi
                ax.plot(freq_mhz, y_data, color=color, linewidth=1.0, label=label)
                all_y_values.extend(y_data)
                ax.set_xlabel("Frequency (MHz)")
            elif plot_type == "Group Delay (ns)":
                y_data, freq_mhz_gd = self.calculate_group_delay(freq, s)
                ax.plot(freq_mhz_gd, y_data, color=color, linewidth=1.0, label=label)
                all_y_values.extend(y_data)
                ax.set_xlabel("Frequency (MHz)")

        ax.grid(True, which='major', alpha=0.3)

        # X 轴自定义范围（若设置了 Custom）
        if self.axis_configs["x_mode"].get() == "Custom":
            try:
                start_val = float(self.axis_configs["x_start"].get())
                stop_val = float(self.axis_configs["x_stop"].get())
                unit = self.axis_configs["x_unit"].get()
                x_start_mhz = start_val * 1000 if unit == "GHz" else start_val
                x_stop_mhz = stop_val * 1000 if unit == "GHz" else stop_val
                ax.set_xlim(x_start_mhz, x_stop_mhz)
            except Exception:
                pass

        # Y 轴自动/自定义
        y_mode = self.y_configs[plot_type][param]["mode"].get()
        if y_mode != "Custom" and all_y_values:
            # 聚合组：S11/S22 作为一组，S21/S12 作为一组
            s_param_index = self.params.index(param)
            if s_param_index in [0, 3]:
                group_params = ["S11", "S22"]
            elif s_param_index in [1, 2]:
                group_params = ["S21", "S12"]
            else:
                group_params = [param]

            grouped_y_values = []
            for dataset in self.datasets:
                for p in group_params:
                    y_data = self._get_y_data_for_limit_calc(dataset, p, plot_type)
                    if len(y_data) > 0:
                        grouped_y_values.append(y_data)
            if grouped_y_values:
                y_all = np.concatenate(grouped_y_values)
                y_min_data, y_max_data = np.min(y_all), np.max(y_all)
                y_min, y_max, y_step = self._calculate_friendly_y_limits(y_min_data, y_max_data)
                ax.set_ylim(y_min, y_max)
                ax.yaxis.set_major_locator(MultipleLocator(y_step))
                ax.yaxis.set_minor_locator(MultipleLocator(y_step / 2))
                ax.grid(True, which='minor', linestyle=':', linewidth=0.5, color='gray', alpha=0.5)
        elif y_mode == "Custom":
            try:
                y_min_custom = float(self.y_configs[plot_type][param]["min"].get())
                y_max_custom = float(self.y_configs[plot_type][param]["max"].get())
                ax.set_ylim(y_min_custom, y_max_custom)
                ax.yaxis.set_minor_locator(AutoMinorLocator(2))
                ax.grid(True, which='minor', linestyle=':', linewidth=0.5, color='gray', alpha=0.5)
            except Exception:
                pass

        # Limit lines
        if plot_type in self.data and self.datasets and all_freq_values:
            # 这里的 x 轴范围应该基于当前图表的显示范围，而不是所有数据点的范围
            # 使用 ax.get_xlim() 来获取当前的 X 轴显示范围，与 Max Mode 保持一致。
            x_min_mhz, x_max_mhz = ax.get_xlim() 
            
            for line in self.data[plot_type]["limit_lines"][param]:
                try:
                    start_val = float(line["start"].get())
                    start_unit = line["start_unit"].get()
                    stop_val = float(line["stop"].get())
                    stop_unit = line["stop_unit"].get()
                    
                    # 频率转换成 MHz
                    start_mhz = start_val * 1000 if start_unit == "GHz" else start_val
                    stop_mhz = stop_val * 1000 if stop_unit == "GHz" else stop_val
                    
                    # Y 轴值
                    lower = float(line["lower"].get())
                    upper = float(line["upper"].get())
                    
                    ltype = line["type"].get()

                    # 限制线绘制的 X 轴范围：取 Limit Line 范围与当前图表显示范围的交集
                    min_f = max(x_min_mhz, min(start_mhz, stop_mhz))
                    max_f = min(x_max_mhz, max(start_mhz, stop_mhz))

                    if min_f >= max_f:
                        continue
                        
                    # ------------------- 核心修复逻辑 -------------------
                    
                    # X 坐标轴上的起点和终点
                    x_line_start = min_f 
                    x_line_stop = max_f
                    
                    # 如果 Limit Line 定义的频率范围是一个点 (start_mhz == stop_mhz)，则无法计算斜率
                    if abs(start_mhz - stop_mhz) < 1e-6:
                        # 此时 Limit Line 应该是一条水平线 (如果 Lower=Upper)，但由于无法插值，我们只绘制 Upper/Lower
                        y_line_start = lower
                        y_line_stop = upper 
                        
                        # 为了避免绘制错误的斜线，我们在这里使用一个合理的水平值
                        # 如果 Start Freq 和 Stop Freq 相同，我们假设用户是想画一条水平线
                        # 并且取 Lower 和 Upper 的平均值作为水平线的高度，但这违背了斜线的初衷。
                        # 更合理的方式是：如果频率相同，并且 Lower != Upper，则 Limit Line 范围无效，跳过绘制。
                        if abs(lower - upper) > 1e-6:
                            # 频率相同，但 Y 值不同：无法绘制有效的水平或斜线，跳过
                            continue
                        # 如果频率和 Y 值都相同：绘制水平线
                        
                    else:
                        # 斜率 m = (upper - lower) / (stop_mhz - start_mhz)
                        # Y(x) = lower + m * (x - start_mhz)
                        m = (upper - lower) / (stop_mhz - start_mhz)
                        y_line_start = lower + m * (x_line_start - start_mhz)
                        y_line_stop = lower + m * (x_line_stop - start_mhz)

                    # --- Upper Limit Line 绘制 (使用 ax.plot) ---
                    if ltype in ["Max", "Band", "Upper Only", "Upper/Lower", "Upper Limit"]:
                        ax.plot(
                            [x_line_start, x_line_stop], 
                            [y_line_start, y_line_stop], # FIX: 使用插值后的 Y 值
                            color='blue', 
                            linestyle='-', 
                            linewidth=1.0, 
                            zorder=4,
                            # 存储 artist 引用以备后用 (可选)
                            # label=f"Limit Upper {p}" 
                        )
                    
                    # --- Lower Limit Line 绘制 (使用 ax.plot) ---
                    if ltype in ["Min", "Band", "Lower Only", "Upper/Lower", "Lower Limit"]:
                        ax.plot(
                            [x_line_start, x_line_stop], 
                            [y_line_start, y_line_stop], # FIX: 使用插值后的 Y 值
                            color='blue', # 请根据您的规范调整 Lower Limit 的颜色和线型
                            linestyle='--', 
                            linewidth=1.0, 
                            zorder=4,
                            # 存储 artist 引用以备后用 (可选)
                            # label=f"Limit Lower {p}"
                        )
                    # ----------------------------------------------------
                except Exception:
                    # print(f"Error drawing limit line: {e}")
                    pass

        # x limits for clipping
        x_min_mhz, x_max_mhz = ax.get_xlim()

        # --- 绘制 Markers（普通 + Search）---
        visible_marker_info_list = []
        if plot_type in self.data and self.datasets:
            for mark in self.data[plot_type]["marks"][param]:
                try:
                    import tkinter as tk
                    display_status = mark.get("display_status", tk.StringVar(value="Display")).get()
                    selected_data_id = mark.get("data_id", tk.StringVar(value="")).get()
                    dataset = next((d for d in self.datasets if str(d['id']) == str(selected_data_id)), None)

                    y_pt = None
                    x_pt_plot = None
                    plot_marker_point = False
                    y_str = "N/A"
                    x_display = ""
                    mark_id = mark.get('id', 'M?')

                    if not dataset:
                        # still prepare legend text (Out of range)
                        if mark.get("is_search", False) and display_status == "Display":
                            # show search range as info even if dataset not found
                            start_str = mark.get("start", tk.StringVar(value="")).get()
                            stop_str = mark.get("stop", tk.StringVar(value="")).get()
                            unit = mark.get("unit", tk.StringVar(value="")).get()
                            x_display = f"{start_str}-{stop_str}{unit}"
                            full_legend_text = f"{mark_id} ({param} ID {selected_data_id}) @{x_display}, N/A (No dataset)"
                            visible_marker_info_list.append((mark_id, str(selected_data_id), full_legend_text))
                        continue

                    s_data = dataset['s_data'][param.lower()]
                    freq = dataset['freq']  # Hz
                # 【核心修复】: 使用 dataset['id'] 而不是 data_id (避免 NameError 和最后一个颜色问题)
                    color = self.custom_id_colors.get(dataset['id'], COLOR_CYCLE[(dataset['id'] - 1) % len(COLOR_CYCLE)])

                    # compute data array for plot_type

                    # compute data array for plot_type
                    if plot_type == "Magnitude (dB)":
                        data_array = 20 * np.log10(np.abs(s_data) + 1e-20)
                    elif plot_type == "Phase (deg)":
                        data_array = np.unwrap(np.angle(s_data)) * 180 / np.pi
                    elif plot_type == "Group Delay (ns)":
                        data_array, _ = self.calculate_group_delay(freq, s_data)
                    else:
                        continue

                    if data_array is None or len(freq) < 2:
                        continue

                    min_f_hz = freq[0]
                    max_f_hz = freq[-1]

                    # Search marker logic
                    if mark.get("is_search", False):
                        if display_status != "Display":
                            continue

                        start_str = mark.get("start", tk.StringVar(value="")).get()
                        stop_str = mark.get("stop", tk.StringVar(value="")).get()
                        unit = mark.get("unit", tk.StringVar(value="MHz")).get()
                        x_display = f"@{start_str}-{stop_str}{unit}"

                        try:
                            start_val = float(start_str)
                            stop_val  = float(stop_str)
                            unit_multiplier = 1e9 if unit == "GHz" else 1e6 if unit == "MHz" else 1e3 if unit == "KHz" else 1
                            start_hz = start_val * unit_multiplier
                            stop_hz  = stop_val * unit_multiplier
                            f_min, f_max = min(start_hz, stop_hz), max(start_hz, stop_hz)

                            # no overlap
                            if f_max < min_f_hz or f_min > max_f_hz:
                                y_str = "Out of Freq Range"
                                x_display = f"{start_str}-{stop_str}{unit}"
                                plot_marker_point = False
                            else:
                                mask = (freq >= f_min) & (freq <= f_max)
                                if not np.any(mask):
                                    y_str = "N/A (No data in range)"
                                    x_display = f"{start_str}-{stop_str}{unit} (No Data)"
                                else:
                                    freq_masked = freq[mask]         # Hz
                                    y_masked = data_array[mask]

                                    # read search_type robustly
                                    search_type = None
                                    if isinstance(mark.get("search_type"), tk.StringVar):
                                        search_type = mark["search_type"].get()
                                    elif isinstance(mark.get("type"), tk.StringVar):
                                        search_type = mark["type"].get()
                                    else:
                                        search_type = str(mark.get("search_type") or mark.get("type") or "")

                                    # Max / Min
                                    if search_type == "Max Value":
                                        idx = np.argmax(y_masked)
                                        precise_f_hz = float(freq_masked[idx])
                                        y_pt = float(y_masked[idx])
                                    elif search_type == "Min Value":
                                        idx = np.argmin(y_masked)
                                        precise_f_hz = float(freq_masked[idx])
                                        y_pt = float(y_masked[idx])
                                    elif search_type == "Custom Search":
                                        # Read custom value & match type with improved robustness
                                        custom_val = 0.0  # Default fallback
                                        try:
                                            custom_val_str = mark.get("custom_value", tk.StringVar(value="0.0"))
                                            if isinstance(custom_val_str, tk.StringVar):
                                                custom_val = float(custom_val_str.get().strip())
                                            else:
                                                custom_val = float(str(custom_val_str).strip())
                                        except (ValueError, TypeError, AttributeError):
                                            custom_val = 0.0  # Specific exceptions for better debugging
                                        
                                        match_type = "First Match"  # Unified default
                                        allowed_match_types = ["First Match", "Last Match"]
                                        try:
                                            cm = mark.get("match_type", tk.StringVar(value="First Match"))  # Correct key: "match_type" from source code
                                            if isinstance(cm, tk.StringVar):
                                                candidate = cm.get().strip()
                                            else:
                                                candidate = str(cm).strip()
                                            
                                            # Validate and set
                                            if candidate in allowed_match_types:
                                                match_type = candidate
                                            else:
                                                match_type = "First Match"  # Fallback to default if invalid
                                        except (ValueError, TypeError, AttributeError, KeyError):
                                            match_type = "First Match"
                                        
                                        # Optional: Log invalid values for debugging (comment out in production)
                                        # print(f"Warning: Invalid match_type '{candidate}' fallback to '{match_type}'")                                           

                                        # call helper (expects freq in Hz and array)
                                        precise = self._find_custom_match_freq_hz(custom_val, freq_masked, y_masked, match_type)
                                        if precise is None:
                                            # fallback: nearest
                                            idx_close = np.argmin(np.abs(y_masked - custom_val))
                                            precise = float(freq_masked[idx_close])
                                            y_pt = float(y_masked[idx_close])
                                        else:
                                            # get y at that precise freq by interpolation (linear)
                                            # use safe_interp with Hz input if available
                                            val_interp = self.safe_interp(precise, freq, data_array)
                                            y_pt = float(val_interp) if val_interp is not None else float(y_masked[np.argmin(np.abs(freq_masked - precise))])
                                        precise_f_hz = float(precise)
                                    else:
                                        # unsupported type -> skip
                                        continue

                                    precise_f_mhz = precise_f_hz / 1e6
                                    # format display
                                    precise_f_str = f"{precise_f_mhz:.3f}".rstrip("0").rstrip(".")
                                    x_display = f"{start_str}-{stop_str}{unit}, {precise_f_str} MHz"
                                    # 修正后的代码
                                    y_str = f"{y_pt:.3f} ns" if plot_type == "Group Delay (ns)" else f"{y_pt:.3f} {y_unit}"                                    
                                    #y_str = f"{y_pt:.3f}" if plot_type == "Group Delay (ns)" else f"{y_pt:.3f} {y_unit}"
                                    x_pt_original = precise_f_mhz
                                    x_pt_plot = np.clip(x_pt_original, x_min_mhz, x_max_mhz)
                                    plot_marker_point = True

                        except Exception:
                            y_str = "Search Error"
                            x_display = f"{start_str}-{stop_str}{unit} (Err)"

                    else:
                        # normal marker
                        target_freq_hz = self._get_marker_freq_hz(mark)
                        f_str = mark.get("freq", tk.StringVar(value="")).get() if isinstance(mark.get("freq"), tk.StringVar) else str(mark.get("freq", ""))
                        unit = mark.get("unit", tk.StringVar(value="MHz")).get() if isinstance(mark.get("unit"), tk.StringVar) else str(mark.get("unit", "MHz"))
                        x_display = f"{f_str} {unit}"

                        marker_is_in_data_range = (target_freq_hz >= min_f_hz) and (target_freq_hz <= max_f_hz)
                        if marker_is_in_data_range:
                            val = self.safe_interp(target_freq_hz, freq, data_array)
                            if val is not None:
                                x_pt_original = target_freq_hz / 1e6
                                y_pt = float(val)
                                x_pt_plot = np.clip(x_pt_original, x_min_mhz, x_max_mhz)
                                y_str = f"{y_pt:.3f} {y_unit}"
                                plot_marker_point = True
                            else:
                                y_str = "N/A (Interp Failed)"
                        else:
                            y_str = "Out of Freq Range"

                    # 绘制点与注释
                    if plot_marker_point:
                        ax.plot(x_pt_plot, y_pt, '.', markerfacecolor='none', markeredgecolor=color,
                                markersize=4, markeredgewidth=2, zorder=5)
                        ax.annotate(mark_id, xy=(x_pt_plot, y_pt), xytext=(5, 5),
                                    textcoords='offset points', fontsize=9, color=color, zorder=6)

                    # legend 文本
                    custom_name = self.custom_id_names.get(str(selected_data_id), f"ID {selected_data_id}")
                    full_legend_text = f"{mark_id} ({param} {custom_name}) @{x_display}, {y_str}"
                    if display_status == "Display":
                        visible_marker_info_list.append((mark_id, str(selected_data_id), full_legend_text))

                except Exception:
                    # 保证稳健：忽略单个 marker 的错误
                    pass

        # 绘制 legend
        if visible_marker_info_list:
            import matplotlib.offsetbox as moffsetbox

            # ────── 最强防御性初始化（关键！）──────
            if not hasattr(self, 'normal_marker_legend_artists'):
                self.normal_marker_legend_artists = {}
            if not hasattr(self, 'normal_legend_backgrounds'):
                self.normal_legend_backgrounds = {}

            # ────── 清理旧图例（安全版）──────
            for storage in (self.normal_marker_legend_artists, self.normal_legend_backgrounds):
                if param in storage and storage[param]:
                    try:
                        storage[param].remove()
                    except:
                        pass
                    storage[param] = None

            # ────── 排序 ──────
            def normal_mode_sort_key(info):
                marker_id_str, data_id_str, _ = info
                try:
                    data_id_int = int(data_id_str)
                except:
                    data_id_int = float('inf')
                marker_num = self.get_marker_id_number(marker_id_str)
                return (data_id_int, marker_num)
            sorted_markers = sorted(visible_marker_info_list, key=normal_mode_sort_key)

            # ────── 位置配置 ──────
            pos_config = self.marker_pos_configs[plot_type][param]
            mode = pos_config["mode_var"].get()
            x_val, y_val = 0.98, 0.98
            h_align, v_align = 'right', 'top'

            if mode == "Top Left":
                x_val, y_val = 0.02, 0.98
                h_align, v_align = 'left', 'top'
            elif mode == "Top Right":
                x_val, y_val = 0.98, 0.98
                h_align, v_align = 'right', 'top'
            elif mode == "Bottom Left":
                x_val, y_val = 0.02, 0.02
                h_align, v_align = 'left', 'bottom'
            elif mode == "Bottom Right":
                x_val, y_val = 0.98, 0.02
                h_align, v_align = 'right', 'bottom'
            elif mode == "Center":
                x_val, y_val = 0.5, 0.5
                h_align, v_align = 'center', 'center'
            elif mode == "Custom":
                try:
                    x_val = float(pos_config["x_var"].get())
                    y_val = float(pos_config["y_var"].get())
                    h_align = 'left' if x_val < 0.5 else 'right'
                    v_align = 'bottom' if y_val < 0.5 else 'top'
                    if x_val == 0.5: h_align = 'center'
                    if y_val == 0.5: v_align = 'center'
                except:
                    x_val, y_val = 0.98, 0.98
                    h_align, v_align = 'right', 'top'

            # ────── 创建彩色 TextArea（真正放进背景框里）──────
            text_areas = []
            auto_font_color_enabled = hasattr(self, 'auto_font_color_enabled') and self.auto_font_color_enabled.get()

            #修复Normal模式下颜色的bug
            for _, data_id_str, full_text in sorted_markers:
                color = 'black'
                if auto_font_color_enabled:
                    try:
                        cid = int(data_id_str)
                        
                        # --- 修复 Bug：同步 Marker 字体颜色时，优先使用自定义 ID 颜色 ---
                        # 1. 检查自定义 ID 颜色 (适用于 Normal 模式)
                        if cid in self.custom_id_colors:
                            color = self.custom_id_colors[cid]
                        else:
                            # 2. 否则使用默认的颜色循环
                            clist = getattr(self, 'COLOR_CYCLE', None) or globals().get('COLOR_CYCLE')
                            if clist:
                                color = clist[(cid - 1) % len(clist)]
                        # ------------------------------------------------------------------
                        
                    except:
                        # 如果 data_id_str 不是数字 (e.g., 'Avg' 或 Max 模式下的非 ID 标记)，保持黑色
                        pass
                ta = moffsetbox.TextArea(
                    full_text,
                    textprops=dict(color=color, fontsize=9, ha=h_align, va='center')
                )
                text_areas.append(ta)

            # 垂直堆叠
            # 强制左对齐，无论图例在左中右，文字永远从左边开始排列
            vp = moffsetbox.VPacker(children=text_areas, align='left', pad=0, sep=3)
            #packer_align = {'left': 'left', 'right': 'right', 'center': 'center'}.get(h_align, 'center')
            #vp = moffsetbox.VPacker(children=text_areas, align=packer_align, pad=0, sep=3)

            # 背景框对齐
            box_align_x = 1.0 if h_align == 'right' else 0.0 if h_align == 'left' else 0.5
            box_align_y = 1.0 if v_align == 'top' else 0.0 if v_align == 'bottom' else 0.5

            bbox_params = self._get_marker_legend_bbox_params()

            ab = moffsetbox.AnnotationBbox(
                vp,
                (x_val, y_val),
                xycoords='axes fraction',
                boxcoords='axes fraction',
                box_alignment=(box_align_x, box_align_y),
                frameon=True,
                pad=0.4,
                bboxprops=dict(
                    boxstyle=bbox_params.get('boxstyle', 'round,pad=0.3'),
                    facecolor=bbox_params['facecolor'],
                    edgecolor='none',
                    alpha=bbox_params['alpha']
                ),
                zorder=7
            )
            ax.add_artist(ab)

            # 存储（拖动只认这一个对象就够了）
            self.normal_marker_legend_artists[param] = ab
            self.normal_legend_backgrounds[param] = ab

        else:
            # ────── 无 marker 时清理（最强防御版）──────
            for attr_name in ('normal_marker_legend_artists', 'normal_legend_backgrounds'):
                storage = getattr(self, attr_name, None)
                if storage is None:
                    setattr(self, attr_name, {})
                    storage = getattr(self, attr_name)
                if param in storage and storage[param]:
                    try:
                        storage[param].remove()
                    except:
                        pass
                    storage[param] = None

        # Limits check status
        if self.limits_check_enabled.get():
            limit_lines = self.data.get(plot_type, {}).get("limit_lines", {}).get(param, [])
            check_results = []
            if not limit_lines:
                check_results = [{'data_id': None, 'name': 'N/A', 'status': 'N/A_NoLimits'}]
            else:
                for dataset in self.datasets:
                    data_id = dataset['id']
                    name = self.custom_id_names.get(str(data_id), f"ID {data_id}")
                    s_data = dataset['s_data'].get(param.lower())
                    if s_data is None or len(s_data) < 2:
                        status = 'N/A_NoData'
                    else:
                        is_pass, has_overlap = self._check_dataset_limits(dataset, plot_type, param)
                        status = 'PASS' if is_pass and has_overlap else ('FAIL' if (not is_pass and has_overlap) else 'N/A_NoOverlap')
                    check_results.append({'data_id': data_id, 'name': name, 'status': status})
                if not self.datasets:
                    check_results = [{'data_id': None, 'name': 'N/A', 'status': 'N/A_NoData'}]
            self._draw_limit_check_status(ax, check_results)

        # X axis cosmetics
        ax.xaxis.set_major_locator(MaxNLocator(10))
        ax.xaxis.set_minor_locator(AutoMinorLocator(2))
        ax.grid(True, which='minor', linestyle=':', linewidth=0.5, color='gray', alpha=0.5)

        # bind marker legend drag callbacks once per canvas
        try:
            canvas = fig.canvas
            if not hasattr(canvas, '_marker_drag_connected_normal_mode'):
                canvas.mpl_connect("button_press_event", self.on_marker_legend_press)
                canvas.mpl_connect("motion_notify_event", self.on_marker_legend_motion)
                canvas.mpl_connect("button_release_event", self.on_marker_legend_release)
                setattr(canvas, '_marker_drag_connected_normal_mode', True)
        except Exception:
            pass

        # ----------------------------------------------------

    #智能刻度定义
    def _optimize_tick_labels_output(self, ax, fig):
        try:
            import numpy as np
            import matplotlib.ticker as ticker
           
            fig.canvas.draw() # 确保当前视图已渲染
           
            # --- 辅助函数：智能 Y 轴标签格式化 ---
            def smart_y_formatter(y):
                if abs(y - round(y)) < 1e-6:
                    return f"{int(round(y))}"
                else:
                    return f"{y:.2f}"
            # --- 辅助函数：智能 X 轴标签格式化 ---
            def smart_x_formatter(x, pos, decimals):
                return f"{x:.{decimals}f}"
            # === X轴动态调整 ===
            xlim = ax.get_xlim()
            span = xlim[1] - xlim[0]
            # 获取当前 param 从 title
            param = ax.get_title()
            if not param:  # 如果隐藏或无标题，跳过或默认
                return
            # 获取布局
            layout = self._determine_normal_layout()
            selected_params = [p for p in self.params if self.show_param_vars[p].get()]
            num_selected = len(selected_params)
            current_layout = layout.get(param, {})
            
            # 判断是否为简单布局 (colspan==1，表示1x1子图)
            is_simple_layout = (current_layout.get('colspan', 1) == 1)
            
            # 🎯 根据模式和布局调整小数位逻辑
            if self.display_mode.get() == "Max":
                # Max模式 → 细化显示 (不变)
                if span < 5:
                    decimals = 4
                elif span < 10:
                    decimals = 3
                elif span < 20:
                    decimals = 2
                else:
                    decimals = 1
                numticks = 10  # Max模式固定10
            else:
                # Normal模式 → 基于布局的逻辑
                if is_simple_layout:
                    # 简单布局 (num=4 all, num=3 upper): if span < 10:1 else:0
                    decimals = 1 if span < 10 else 0
                    numticks = 10  # 简单布局固定10
                else:
                    # 全宽布局 (num=3 lower, num=2 both, num=1 full): 细化如Max
                    if span < 5:
                        decimals = 4
                    elif span < 10:
                        decimals = 3
                    elif span < 20:
                        decimals = 2
                    else:
                        decimals = 1
                    numticks = 15  # 全宽布局使用15
            # 设置刻度与格式化器
            ax.xaxis.set_major_locator(ticker.LinearLocator(numticks=numticks))
            ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: smart_x_formatter(x, pos, decimals)))
            # === Y轴格式化 ===
            y_ticks = ax.get_yticks()
            ax.set_yticklabels([smart_y_formatter(y) for y in y_ticks])
            fig.canvas.draw()
        except Exception:
            pass

    # [新增/修改] _draw_marker_frame (根据 is_search 绘制不同 UI 布局)
    # ----------------------------------------------------
    # 【修复】普通 Marker 的 UI 绘制（支持 Display/Hide 按钮）
    # ----------------------------------------------------
    def _draw_marker_frame(self, mark_data, container, plot_type, param):
        frame = tk.Frame(container, bg="#ffffff", relief="groove", bd=1)
        frame.pack(fill="x", pady=4, padx=5)
        mark_data["frame"] = frame

        # ID
        tk.Label(frame, text=mark_data["id"] + ":", bg="#ffffff", font=("sans-serif", 10, "bold")).grid(row=0, column=0, padx=3, sticky="w")

        # Freq
        tk.Label(frame, text="Frequency:", bg="#ffffff").grid(row=0, column=1, padx=3)
        tk.Entry(frame, textvariable=mark_data["freq"], width=9).grid(row=0, column=2, padx=1)

        # Unit
        tk.Label(frame, text="Unit:", bg="#ffffff").grid(row=0, column=3, padx=3)
        ttk.Combobox(frame, textvariable=mark_data["unit"], values=["MHz", "GHz"], state="readonly", width=5).grid(row=0, column=4, padx=1)

        # Data ID
        tk.Label(frame, text="Data ID:", bg="#ffffff").grid(row=0, column=5, padx=3)
        data_id_options = [str(d['id']) for d in self.datasets]
        combo = ttk.Combobox(frame, textvariable=mark_data["data_id"], values=data_id_options, state="readonly", width=4)
        combo.grid(row=0, column=6, padx=3)

        # ------------------------------------------------
        # Display / Hide 按钮（关键修复：传 status_btn）
        # ------------------------------------------------
        status_btn = tk.Button(
            frame,
            textvariable=mark_data["display_status"],
            width=8,
            command=lambda: self._toggle_display_status(mark_data["display_status"], status_btn)
        )
        status_btn.grid(row=0, column=7, padx=5)
        self._update_status_button_color(status_btn, mark_data["display_status"].get())
        mark_data["status_btn"] = status_btn  # 保存引用

        # ------------------------------------------------
        # Remove 按钮
        # ------------------------------------------------
        def remove_and_update():
            frame.destroy()
            marks = self.data[plot_type]["marks"][param]
            if mark_data in marks:
                marks.remove(mark_data)
            self._reindex_markers_and_refresh_ui(plot_type, param)
            self.update_plots()

        tk.Button(frame, text="Remove", bg="#e74c3c", fg="white", command=remove_and_update).grid(row=0, column=8, padx=5)
    # ----------------------------------------------------

    # ----------------------------------------------------
    # 修改: 只刷新普通 Marker 列表 (M1, M2...)
    # ----------------------------------------------------
    def _reindex_markers_and_refresh_ui(self, plot_type, param):
        marks = self.data[plot_type]["marks"].get(param, [])
        marker_list_frame = self.data[plot_type]["ui_refs"][param]["marker_list_frame"]
        
        for w in marker_list_frame.winfo_children():
            w.destroy()
        
        normal_marks = [m for m in marks if not m.get("is_search", False)]
        normal_count = 1
        
        for mark in normal_marks:
            if "frame" in mark and mark["frame"]:
                mark["frame"].destroy()
            
            mark["id"] = f"M{normal_count}"
            normal_count += 1
            self._draw_marker_frame(mark, marker_list_frame, plot_type, param)  # 假设已有此方法
        
        canvas = self.data[plot_type]["ui_refs"][param]["canvas"]
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
    # ----------------------------------------------------    

    # ----------------------------------------------------
    # [新增] Toggle Display Status 辅助函数 (复用现有布局)
    # ----------------------------------------------------
    # 【优化版】切换 Display / Hide 状态（支持 event 参数）
    # ----------------------------------------------------
    def _toggle_display_status(self, status_var, status_btn, event=None):
        """
        切换 Marker 的显示状态
        - status_var: tk.StringVar("Display"/"Hide")
        - status_btn: 按钮控件（用于更新颜色）
        - event: Tkinter 自动传入，忽略即可
        """
        current = status_var.get()
        new_status = "Hide" if current == "Display" else "Display"
        status_var.set(new_status)
        self._update_status_button_color(status_btn, new_status)
        #self.update_plots()  # 立即刷新图表
    # ----------------------------------------------------

    def _update_status_button_color(self, btn, status):
        if status == "Display":
            btn.config(bg="#2ecc71", fg="white")  # 绿色
        else:
            btn.config(bg="#e74c3c", fg="white")  # 红色

    # ----------------------------------------------------

    # ---------- File / data handling ----------
    def clear_all_datasets(self):
        if not messagebox.askyesno("Clear Data", f"Are you sure to clear all {len(self.datasets)} loaded datasets?"):
            return
        
        # ------------------------------------------------------------
        # ⚠️ OPTIMIZATION START: 暂时禁用绘图更新 (self.update_plots)
        # ------------------------------------------------------------
        if hasattr(self, 'update_plots'):
            # 存储原始函数
            self._original_update_plots_clear = self.update_plots
            # 用空函数替换
            def no_op_update_plots(*args, **kwargs):
                pass
            self.update_plots = no_op_update_plots
        
        # 1. 核心数据和状态清空
        self.datasets = []
        self.next_dataset_id = 1
        self.current_img = None
        self.maximized_param = None
        
        # Reset Max Mode Exit and clean up 
        self.exit_max_mode() 
        if hasattr(self, 'max_frame') and self.max_frame:
            self.max_frame.destroy() 
            self.max_frame = None
            self.max_fig = None
            self.max_ax = None
            self.max_canvas = None
            self.max_toolbar = None
            self.max_cids = {}
        
        SUPPORTED_PLOT_TYPES = ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"]
        
        # Reset Limit/Mark Data
        for pt in SUPPORTED_PLOT_TYPES:
            for p in self.params:
                self.data[pt]["limit_lines"][p] = []
                self.data[pt]["marks"][p] = []
                self.data[pt]["ui_refs"][p] = {}
        
        # === 核心修复 1：销毁 Limits & Marks 标签页 UI 框架 ===
        if hasattr(self, 'limit_tabs'):
            for t in list(self.limit_tabs.keys()):
                try:
                    w = self.limit_tabs.pop(t)
                    self.notebook.forget(w)
                    w.destroy()
                except:
                    pass
        # =======================================================

        # Reset show_param_vars
        for p in self.params:
            self.show_param_vars[p].set(True)

        # 2. UI 变量/状态清空 
             
        self.custom_id_names = {} 
        if hasattr(self, 'selected_data_id_var'):
            self.selected_data_id_var.set("")
        if hasattr(self, 'custom_name_var'):
            self.custom_name_var.set("")
        if hasattr(self, "id_combo"):
            self.id_combo.set("")
            self.id_combo["values"] = []
            
        self.title_var.set("SN-001")
        self.plot_type.set("Magnitude (dB)")
        self.display_mode.set("Normal")

        # 3. UI 刷新和重绘 (在禁用绘图刷新的环境中进行)
        self.create_data_information_tab()
        self.create_axis_control_tab()
        self.update_data_information_tab() 
        
        # === 核心修复 2：重建 Limits & Marks 标签页 ===
        self.create_limit_mark_tab(self.plot_type.get())
        # =================================================
        
        if hasattr(self, 'chart_tab'):
            self.notebook.select(self.chart_tab)
            
        self.update_file_list_ui()

        # ------------------------------------------------------------
        # ⚠️ OPTIMIZATION END: 恢复绘图更新函数
        # ------------------------------------------------------------
        if hasattr(self, '_original_update_plots_clear'):
            self.update_plots = self._original_update_plots_clear
            del self._original_update_plots_clear

        # 4. 最终状态和绘图更新
        self.status_var.set("All data cleared. Please load S2P file(s)...")
        # ⚠️ 只在此处执行一次绘图刷新
        self.update_plots() 
        
        messagebox.showinfo("Clear Complete", "All data cleared. Please load S2P file(s).")
        #--------------------------------------------------

    #复位参数
    def reset_application(self):
        if not messagebox.askyesno("Reset Application", "Reset application to initial state?"):
            return

        # ------------------------------------------------------------
        # ⚠️ OPTIMIZATION START: 暂时禁用绘图更新 (self.update_plots)
        # ------------------------------------------------------------
        if hasattr(self, 'update_plots'):
            self._original_update_plots = self.update_plots
            def no_op_update_plots(*args, **kwargs):
                pass
            self.update_plots = no_op_update_plots

        # ------------------------------------------------------------
        # 0. Reset Core Data Structures
        # ------------------------------------------------------------
        self.datasets = []
        self.next_dataset_id = 1
        self.current_img = None
        self.maximized_param = None
        self.custom_id_names = {}

        # Disable Add Tag (default)
        if hasattr(self, 'marker_click_enabled'):
            self.marker_click_enabled.set(False)

        # Disable refresh (default)
        if hasattr(self, 'disable_refresh_var'):
            self.disable_refresh_var.set(False)

        # Disable limits check (default)
        if hasattr(self, 'limits_check_enabled'):
            self.limits_check_enabled.set(False)

        # Disable Marker Legend Color (default)
        if hasattr(self, 'auto_font_color_enabled'):
            self.auto_font_color_enabled.set(False)

        # ------------------------------------------------------------
        # 1. Clear limit lines, markers and UI references
        # ------------------------------------------------------------
        for plot_type in self.data:
            for param in self.params:
                if "limit_lines" in self.data[plot_type]:
                    self.data[plot_type]["limit_lines"][param] = []
                if "marks" in self.data[plot_type]:
                    self.data[plot_type]["marks"][param] = []
                if "ui_refs" in self.data[plot_type]:
                    self.data[plot_type]["ui_refs"][param] = {}

        # ------------------------------------------------------------
        # 2. Reset UI: File Information Fields
        # ------------------------------------------------------------
        if hasattr(self, 'selected_data_id_var'):
            self.selected_data_id_var.set("")
        if hasattr(self, 'custom_name_var'):
            self.custom_name_var.set("")
        if hasattr(self, "id_combo"):
            self.id_combo.set("")
            self.id_combo["values"] = []

        # ------------------------------------------------------------
        # 3. Reset General Settings
        # ------------------------------------------------------------
        self.title_var.set("SN-001")
        self.plot_type.set("Magnitude (dB)")
        self.display_mode.set("Normal")

        SUPPORTED_PLOT_TYPES = ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"]

        # ------------------------------------------------------------
        # 4. Reset Marker Position Configurations
        # ------------------------------------------------------------
        for pt in SUPPORTED_PLOT_TYPES:
            for p in self.params:
                self.marker_pos_configs[pt][p]["mode_var"].set("Top Right")
                self.marker_pos_configs[pt][p]["x_var"].set("0.5")
                self.marker_pos_configs[pt][p]["y_var"].set("0.5")

            # Max mode marker settings
            self.max_marker_pos_configs[pt]["mode_var"].set("Top Right")
            self.max_marker_pos_configs[pt]["x_var"].set("0.5")
            self.max_marker_pos_configs[pt]["y_var"].set("0.5")

        # ------------------------------------------------------------
        # 5. Reset Data Dictionaries (limit lines, markers, UI refs)
        # ------------------------------------------------------------
        for pt in SUPPORTED_PLOT_TYPES:
            for p in self.params:
                self.data[pt]["limit_lines"][p] = []
                self.data[pt]["marks"][p] = []
                self.data[pt]["ui_refs"][p] = {}

        # ------------------------------------------------------------
        # 6. Reset Show/Hide Parameters
        # ------------------------------------------------------------
        for p in self.params:
            self.show_param_vars[p].set(True)

        # ------------------------------------------------------------
        # 7. Reset Axis Configurations
        # ------------------------------------------------------------
        self.axis_configs["x_mode"].set("Default")
        self.axis_configs["x_start"].set("800")
        self.axis_configs["x_stop"].set("1000")
        self.axis_configs["x_unit"].set("MHz")

        y_defaults = {
            "Magnitude (dB)": {"min": "-50", "max": "0"},
            "Phase (deg)": {"min": "-180", "max": "180"},
            "Group Delay (ns)": {"min": "0", "max": "10"}
        }

        for pt in SUPPORTED_PLOT_TYPES:
            for p in self.params:
                self.y_configs[pt][p]["mode"].set("Default")
                self.y_configs[pt][p]["min"].set(y_defaults[pt]["min"])
                self.y_configs[pt][p]["max"].set(y_defaults[pt]["max"])

        # ------------------------------------------------------------
        # 8. Close Max Mode Window (if any)
        # ------------------------------------------------------------
        if hasattr(self, 'max_frame') and self.max_frame:
            self.exit_max_mode()
            self.max_frame.destroy()
            self.max_frame = None
            self.max_fig = None
            self.max_ax = None
            self.max_canvas = None
            self.max_toolbar = None
            self.max_cids = {}

        # ------------------------------------------------------------
        # 9. Recreate Dynamic Tabs (Limit & Axis tabs)
        # ------------------------------------------------------------
        if hasattr(self, 'limit_tabs'):
            for t in list(self.limit_tabs.keys()):
                try:
                    w = self.limit_tabs.pop(t)
                    self.notebook.forget(w)
                    w.destroy()
                except:
                    pass

        # 重新创建 Tabs
        self.create_limit_mark_tab(self.plot_type.get())
        self.create_data_information_tab()
        self.create_axis_control_tab()

        # ------------------------------------------------------------
        # 10. Reset Marker Legend Customization (Key Fix)
        # ------------------------------------------------------------
        if hasattr(self, "marker_legend_configs"):
            self.marker_legend_configs["boxstyle_var"].set("Default")
            self.marker_legend_configs["facecolor_var"].set("Default")
            self.marker_legend_configs["alpha_var"].set("Default")

        # Font settings
        if hasattr(self, "marker_font_color_var"):
            self.marker_font_color_var.set("black")
        if hasattr(self, "marker_font_size_var"):
            self.marker_font_size_var.set("10")
        if hasattr(self, "marker_bg_color_var"):
            self.marker_bg_color_var.set("yellow")
        if hasattr(self, "marker_show_var"):
            self.marker_show_var.set(True)

        # Refresh the legend UI (if supported)
        if hasattr(self, "refresh_marker_legend_ui"):
            try: self.refresh_marker_legend_ui()
            except: pass

        # Refresh legend on plot
        if hasattr(self, "update_marker_legend_display"):
            try: self.update_marker_legend_display()
            except: pass
            
        # ------------------------------------------------------------
        # 11. Reset Report Logo
        # ------------------------------------------------------------
        if hasattr(self, '_clear_report_logo'):
            self._clear_report_logo()
        elif hasattr(self, 'report_logo_path'):
            self.report_logo_path = ""

        # ------------------------------------------------------------
        # ⚠️ OPTIMIZATION END: 恢复绘图更新函数
        # ------------------------------------------------------------
        if hasattr(self, '_original_update_plots'):
            self.update_plots = self._original_update_plots
            del self._original_update_plots

        # ------------------------------------------------------------
        # 12. Final UI Refresh (并执行单次绘图更新)
        # ------------------------------------------------------------
        # 更新数据信息 Tab 中的动态内容（如 Treeview）
        self.update_data_information_tab() 
        if hasattr(self, 'chart_tab'):
            self.notebook.select(self.chart_tab)

        self.update_file_list_ui()
        # ⚠️ 集中在此处执行最后一次绘图刷新，替代了之前多次的隐式调用
        self.update_plots() 

        # ------------------------------------------------------------
        # 13. User Feedback
        # ------------------------------------------------------------
        self.status_var.set("Application reset to initial state.")
        messagebox.showinfo("Reset Complete", "The application has been reset to its initial state.")
	#--------------------------------------------------	


# ------------------------------------------------------------------
    # 【新增私有方法】_show_load_dialog: 负责自定义对话框的 UI 和图标设置
    # ------------------------------------------------------------------
    def _show_load_dialog(self):
        """
        显示自定义加载选项对话框，并返回用户选择 ('files', 'folder', 或 None)。
        已加入 Toplevel 窗口的图标修复。
        """
        # 1. 创建顶层窗口
        dialog = tk.Toplevel(self.root) 
        dialog.title("Select Load Option")
        dialog.resizable(False, False)

        # ----------------------------------------------------
        # 💥 关键修复：显式设置 Toplevel 窗口的图标
        # ----------------------------------------------------
        try:
            # 假设 resource_path 是在类外部定义的全局函数
            icon_path = resource_path("StoreLogo.ico")
            dialog.iconbitmap(icon_path)
        except Exception:
            # 如果设置失败，保持默认图标（羽毛），但不阻止程序运行
            pass
        # ----------------------------------------------------

        # ------------------------------------------------------------------
        # 【样式和窗口居中逻辑】
        # ------------------------------------------------------------------
        style = ttk.Style(dialog)
        style.theme_use('clam')
        style.configure('Rounded.TButton', 
                        font=('Arial', 10),
                        relief='raised',
                        borderwidth=3)
        
        # 预设对话框的尺寸
        dialog_width = 350
        dialog_height = 150
        dialog.update_idletasks() 
        
        # 计算居中位置
        root_x = self.root.winfo_rootx()
        root_w = self.root.winfo_width()
        start_x = root_x + (root_w - dialog_width) // 2
        
        root_y = self.root.winfo_rooty()
        root_h = self.root.winfo_height()
        start_y = root_y + (root_h - dialog_height) // 5

        # 设置几何参数
        dialog.geometry(f"{dialog_width}x{dialog_height}+{start_x}+{start_y}")
        # ------------------------------------------------------------------

        # 2. 使其成为模态对话框
        dialog.grab_set() 
        
        # 3. 结果变量
        result = None
        
        # 4. 按钮点击处理函数
        def on_button_click(choice):
            nonlocal result
            result = choice
            dialog.destroy() # 关闭对话框

        # 5. 界面元素
        label = tk.Label(dialog, text="How would you like to load the S2P files?", pady=15)
        label.pack()

        # 6. 按钮框架
        button_frame = tk.Frame(dialog)
        button_frame.pack(pady=20) 

        # Files 按钮
        btn_files = ttk.Button(button_frame, text="Files", width=8, style='Rounded.TButton', 
                               command=lambda: on_button_click('files'))
        btn_files.pack(side=tk.LEFT, padx=10)
        
        # Folder 按钮
        btn_folder = ttk.Button(button_frame, text="Folder", width=8, style='Rounded.TButton', 
                                command=lambda: on_button_click('folder'))
        btn_folder.pack(side=tk.LEFT, padx=10)

        # Cancel 按钮
        btn_cancel = ttk.Button(button_frame, text="Cancel", width=8, style='Rounded.TButton', 
                                command=lambda: on_button_click(None))
        btn_cancel.pack(side=tk.LEFT, padx=10)
        
        dialog.protocol("WM_DELETE_WINDOW", lambda: on_button_click(None))

        # 7. 等待对话框关闭
        dialog.wait_window()
        
        return result

    # ------------------------------------------------------------------
    # 【修改后的公共方法】load_s2p: 负责流程控制
    # ------------------------------------------------------------------
    # 加载s2p文件，支持单文件/多文件/文件夹批量加载
    def load_s2p(self):
        
        # ------------------------------------------------------------
        # 1. Ask User for Loading Method (调用私有方法)
        # ------------------------------------------------------------
        choice = self._show_load_dialog() # choice 将是 'files', 'folder', 或 None

        if choice is None:
            return # 用户选择了 Cancel

        file_paths = []

        if choice == 'files': # Select File(s)
            file_paths = filedialog.askopenfilenames(
                title="Select S2P File(s)",
                filetypes=[("S2P files", "*.s2p"), ("All files", "*.*")]
            )
        elif choice == 'folder': # Select Folder
            directory_path = filedialog.askdirectory(title="Select Folder containing S2P Files")
            if directory_path:
                file_paths = [
                    os.path.join(directory_path, filename)
                    for filename in os.listdir(directory_path)
                    if filename.lower().endswith(".s2p")
                ]
                
                if not file_paths:
                    messagebox.showinfo("Information", "No .s2p files found in the selected folder.")
                    return
        
        if not file_paths:
            return

        # ------------------------------------------------------------
        # 2. Batch Processing of File List (保持不变)
        # ------------------------------------------------------------
        loaded_count = 0
        failed_files = []
        
        for file_path in file_paths:
            try:
                # ... (文件加载和解析逻辑) ...
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                freq_unit = "Hz"
                s_format = None

                # Parse header line
                for line in lines:
                    line = line.strip()
                    if line.startswith('#'):
                        parts = line.upper().split()
                        if 'GHZ' in parts: freq_unit = "GHz"
                        elif 'MHZ' in parts: freq_unit = "MHz"
                        elif 'KHZ' in parts: freq_unit = "KHz"
                        if 'DB' in parts: s_format = "DB"
                        elif 'MA' in parts: s_format = "MA"
                        elif 'RI' in parts: s_format = "RI"
                        break

                if s_format is None:
                    raise ValueError("No # line or S-parameter format found")

                # Extract data lines
                data_lines = []
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith('!') or line.startswith('#'):
                        continue
                    numbers = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', line)
                    if len(numbers) >= 9:
                        try:
                            data_lines.append([float(x) for x in numbers[:9]])
                        except:
                            continue

                if not data_lines:
                    raise ValueError("No valid data lines found")

                data = np.array(data_lines)
                freq = data[:, 0]
                if freq_unit == "GHz": freq *= 1e9
                elif freq_unit == "MHz": freq *= 1e6
                elif freq_unit == "KHz": freq *= 1e3

                # Convert S-parameters based on format
                if s_format == "RI":
                    s_data = {
                        's11': data[:, 1] + 1j * data[:, 2],
                        's21': data[:, 3] + 1j * data[:, 4],
                        's12': data[:, 5] + 1j * data[:, 6],
                        's22': data[:, 7] + 1j * data[:, 8],
                    }
                elif s_format == "DB":
                    def db_angle_to_complex(mag_db, angle_deg):
                        mag = 10 ** (mag_db / 20.0)
                        rad = np.deg2rad(angle_deg)
                        return mag * (np.cos(rad) + 1j * np.sin(rad))
                    s_data = {
                        's11': db_angle_to_complex(data[:, 1], data[:, 2]),
                        's21': db_angle_to_complex(data[:, 3], data[:, 4]),
                        's12': db_angle_to_complex(data[:, 5], data[:, 6]),
                        's22': db_angle_to_complex(data[:, 7], data[:, 8]),
                    }
                elif s_format == "MA":
                    def mag_angle_to_complex(mag_lin, angle_deg):
                        rad = np.deg2rad(angle_deg)
                        return mag_lin * (np.cos(rad) + 1j * np.sin(rad))
                    s_data = {
                        's11': mag_angle_to_complex(data[:, 1], data[:, 2]),
                        's21': mag_angle_to_complex(data[:, 3], data[:, 4]),
                        's12': mag_angle_to_complex(data[:, 5], data[:, 6]),
                        's22': mag_angle_to_complex(data[:, 7], data[:, 8]),
                    }

                # Create new dataset
                new_dataset = {
                    'id': self.next_dataset_id,
                    'name': os.path.basename(file_path),
                    'path': file_path,
                    'freq': freq,
                    's_data': s_data,
                    'format': s_format,
                    'points': len(freq)
                }
                self.datasets.append(new_dataset)
                self.next_dataset_id += 1
                loaded_count += 1

            except Exception as e:
                failed_files.append(f"{os.path.basename(file_path)}: {e}")

        # ------------------------------------------------------------
        # 3. Update UI (Status messages in English)
        # ------------------------------------------------------------
        if loaded_count > 0:
            self.status_var.set(
                f"Loaded {loaded_count} file(s) successfully | Total Files: {len(self.datasets)}"
            )
            self.update_file_list_ui()
            self.on_plot_type_change()
            self.update_data_information_tab()
            
            # --- Refresh Marker UI Lists ---
            current_plot_type = self.plot_type.get()
            
            if current_plot_type in self.data:
                for param in self.params: 
                    if self.data[current_plot_type]["marks"].get(param):
                        self._reindex_markers_and_refresh_ui(current_plot_type, param)
                        
                        ui_refs_param = self.data[current_plot_type]["ui_refs"].get(param, {})
                        if "search_marker_list_frame" in ui_refs_param:
                            self._refresh_search_markers_ui(current_plot_type, param)
                # ---------------------------------------------

                if self.display_mode.get() == "Normal":
                    self.restore_plots_layout()

                if hasattr(self, "id_combo"):
                    self.id_combo["values"] = [str(d["id"]) for d in self.datasets]

        # Display failed files
        if failed_files:
            messagebox.showwarning(
                "Partial Load Warning",
                "Some files could not be loaded:\n\n" + "\n".join(failed_files)
            )
        #----------------------------------
        

    def calculate_group_delay(self, freq, s):
        if len(s) < 3:
            return np.array([]), freq / 1e6
        phase_rad = np.unwrap(np.angle(s))
        d_phase_rad = np.gradient(phase_rad)
        d_freq = np.gradient(freq)
        valid_indices = d_freq != 0
        group_delay_s = np.zeros_like(freq, dtype=float)
        group_delay_s[valid_indices] = -d_phase_rad[valid_indices] / (2 * np.pi * d_freq[valid_indices])
        group_delay_ns = group_delay_s * 1e9
        freq_mhz = freq / 1e6
        return group_delay_ns, freq_mhz

    def plot_parameter(self, ax, fig, canvas, param, plot_type):
        self.plot_parameter_output(ax, fig, param, plot_type)
        canvas.draw()

    # ---------- Copy / Save 复制和保持图表----------
    def copy_all_charts(self):
        self._handle_chart_output(copy=True)

    def save_chart(self):
        self._handle_chart_output(copy=False)

    def _handle_chart_output(self, copy=False):
        # ⚠️ 注意: 确保您已定义 COLOR_CYCLE, copy_image_to_clipboard, _generate_filename 等辅助对象或函数。
        out_fig = None
        
        try:
            # ------------------- Max 模式 (Logo 尺寸、偏移量条件切换) -------------------
            if self.display_mode.get() == "Max" and self.max_fig:
                
                target_fig = self.max_fig
                
                # 1. 在绘制前，先清除所有 Figure 级别的残留元素。
                self._clear_figure_elements(target_fig)
                
                # 2. 💥 强制同步 Matplotlib Figure 尺寸。
                if hasattr(self, 'max_canvas') and self.max_canvas:
                    self.max_canvas.get_tk_widget().update_idletasks() 
                    target_fig.canvas.draw() 
                
                # 3. 添加输出专用的元素 
                
                # 3.1. 添加 Title
                title_line1 = f"{self.title_var.get()}"
                self.max_fig.text(0.5, 0.975, title_line1, ha='center', va='top',
                                 fontsize=14, fontweight="bold") 
                                                
                # --- Logo 尺寸和偏移量切换逻辑 ---
                current_height = self.max_fig.bbox.height
                default_height = getattr(self, 'max_fig_default_height_px', 850) 
                
                default_w = self.report_logo_width.get()
                default_h = self.report_logo_height.get()                

                # 检查当前高度是否远大于默认高度（例如，超过 50 像素），判断是否是最大化或调整后的状态
                if current_height > default_height + 50: 
                    # 状态：最大化/调整大小（Logo 尺寸变大：225x90, 210x84, 180x72, 165x66）
                    logo_w, logo_h = "165", "66"  # 优化后的新尺寸
                    # 💥 使用经验证的最大化/调整大小状态下的大偏移量
                    logo_y_offset = -10 
                else:
                    # 状态：默认大小（Logo 尺寸使用配置值）
                    logo_w, logo_h = default_w, default_h 
                    # 💥 使用经验证的默认大小状态下的大偏移量
                    logo_y_offset = -10
                # --- 结束切换逻辑 ---
                
                # 3.3. 添加 Logo (使用新的参数名进行调用)
                self._draw_report_logo(target_fig, y_offset=logo_y_offset, logo_width=logo_w, logo_height=logo_h) 
                
                # 4. 生成输出 (Copy/Save)
                if copy:
                    buf = io.BytesIO()
                    target_fig.savefig(buf, format='png', dpi=200, bbox_inches='tight')
                    buf.seek(0)
                    img = Image.open(buf)
                    ok = copy_image_to_clipboard(img)
                    buf.close()
                    if ok:
                        messagebox.showinfo("Copied", "Max mode plot copied to clipboard.")
                    else:
                        messagebox.showwarning("Not supported", "Clipboard copy not supported on this platform.")
                else:
                    filename = self._generate_filename()
                    f = filedialog.asksaveasfilename(defaultextension=".png",
                                                     filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")],
                                                     initialfile=filename)
                    if not f:
                        pass 
                    else:
                        target_fig.savefig(f, dpi=200, bbox_inches='tight')
                        messagebox.showinfo("Saved", f"Max mode plot saved to {f}")

                # 5. 💥 事后清理：清除所有只用于输出的元素。
                self._clear_figure_elements(target_fig) 
                # 强制 Canvas 重绘以清除屏幕上的残留
                if hasattr(self, 'max_canvas') and self.max_canvas:
                    #self.max_canvas.get_tk_widget().delete("all")
                    self.max_canvas.draw_idle() 

            # ------------------- Normal 模式 -------------------
            elif self.display_mode.get() == "Normal":
                layout_config = self._determine_normal_layout()
                selected_params = list(layout_config.keys())
                num_selected = len(selected_params)
                if num_selected == 0:
                    messagebox.showwarning("Warning", "No S-parameters are currently selected for plotting.")
                    return

                # --- 渲染阶段：从每个 on-screen fig 获取精确渲染 (保持不变) ---
                rendered_images = {}  # param -> PIL.Image
                for param in selected_params:
                    cfg = self.plot_configs.get(param)
                    if not cfg:
                        tmp_fig = plt.Figure(figsize=(4,3), dpi=150)
                        tmp_ax = tmp_fig.add_subplot(111)
                        self.plot_parameter_output(tmp_ax, tmp_fig, param, self.plot_type.get())
                        buf = io.BytesIO()
                        tmp_fig.savefig(buf, format='png', bbox_inches='tight', dpi=150)
                        buf.seek(0)
                        rendered_images[param] = Image.open(buf).convert('RGBA')
                        buf.close()
                        plt.close(tmp_fig)
                        continue

                    fig = cfg.get('fig')
                    try:
                        fig.canvas.draw()
                    except Exception:
                        pass

                    buf = io.BytesIO()
                    fig.savefig(buf, format='png', bbox_inches='tight', dpi=150)
                    buf.seek(0)
                    rendered_images[param] = Image.open(buf).convert('RGBA')
                    buf.close()

                # --- 拼接阶段：将多个小图拼接到一个大图 (保持不变) ---
                OUT_W, OUT_H = 1200, 800
                canvas_img = Image.new('RGBA', (OUT_W, OUT_H), (255,255,255,255))
                cell_w = OUT_W // 2
                cell_h = OUT_H // 2
                for param, cfg in layout_config.items():
                    img = rendered_images.get(param)
                    if img is None:
                        continue
                    row = cfg.get('row', 0)
                    col = cfg.get('col', 0)
                    rowspan = cfg.get('rowspan', 1)
                    colspan = cfg.get('colspan', 1)

                    target_w = cell_w * colspan
                    target_h = cell_h * rowspan
                    
                    img_resized = img.resize((target_w, target_h), Image.LANCZOS)
                    paste_x = col * cell_w
                    paste_y = row * cell_h
                    canvas_img.paste(img_resized, (paste_x, paste_y), img_resized)

                # --- Normal 模式下的最终处理：将 PIL 图像导入 Matplotlib Figure 添加标题 ---
                final_img = canvas_img.convert('RGB')
                
                fig_w, fig_h = final_img.size
                out_fig = plt.figure(figsize=(fig_w/100, fig_h/100), dpi=100) 
                out_ax = out_fig.add_subplot(111)

                out_ax.axis('off')
                out_ax.imshow(final_img)
                
                normal_w = self.report_logo_width.get()
                normal_h = self.report_logo_height.get()
                
                # ---------------------------------------------------------------------
                
                title_line1 = f"{self.title_var.get()}"
                out_fig.text(0.5, 0.975, title_line1, ha='center', va='top',
                                     fontsize=14, fontweight="bold")

                # 第二行（ID + 彩色横线）
                start_x = 0.25
                spacing = 0.15
                y_pos = 0.94
                for i, d in enumerate(self.datasets):
                    data_id = d['id']
                    custom_name = self.custom_id_names.get(str(data_id), f"ID {data_id}")
                    if data_id in self.custom_id_colors:
                        color = self.custom_id_colors[data_id] 
                    else:
                        color = COLOR_CYCLE[(data_id - 1) % len(COLOR_CYCLE)]
                    x_pos = start_x + i * spacing
                    
                    out_fig.text(x_pos - 0.02, y_pos, f"{custom_name}", ha='right', va='center',
                                         fontsize=12, color='black', fontweight="bold")
                    out_fig.text(x_pos, y_pos, "—", ha='left', va='center',
                                         fontsize=16, color=color, fontweight="bold")
                    
                out_fig.tight_layout(rect=[0, 0, 1, 0.95]) # 为标题留出顶部空间
                
                # ----------------- 在最终图上插入 Logo (Normal Mode) -----------------
                self._draw_report_logo(out_fig, y_offset= 10, logo_width=normal_w, logo_height=normal_h) 
                # ------------------------------------------------------------------------
                
                # 5. 保存/复制流程使用 out_fig
                if copy:
                    buf = io.BytesIO()
                    out_fig.savefig(buf, format='png', dpi=200, bbox_inches='tight') 
                    plt.close(out_fig) # 关闭临时 Figure
                    buf.seek(0)
                    img = Image.open(buf)
                    ok = copy_image_to_clipboard(img)
                    if ok:
                        messagebox.showinfo("Copied", "Normal mode plots copied to clipboard.")
                    else:
                        messagebox.showwarning("Not supported", "Clipboard copy not supported on this platform.")
                else:
                    filename = self._generate_filename()
                    f = filedialog.asksaveasfilename(defaultextension=".png",
                                                     filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")],
                                                     initialfile=filename)
                    if not f:
                        plt.close(out_fig) # 关闭临时 Figure
                        return
                    out_fig.savefig(f, dpi=200, bbox_inches='tight')
                    plt.close(out_fig) # 关闭临时 Figure
                    messagebox.showinfo("Saved", f"Normal mode plots saved to {f}")

        except Exception as e:
            # 确保在异常发生时，如果 out_fig 存在，也被关闭
            if 'out_fig' in locals() and isinstance(out_fig, plt.Figure):
                plt.close(out_fig)
            messagebox.showerror("Operation Failed", f"An error occurred: {e}")
        #------------------------------------------------------------------

    # ---------- UI for limits & marks & data info (kept similar to original) ----------
    def create_limit_mark_tab(self, plot_type):
        if plot_type in self.limit_tabs:
            return
        tab = tk.Frame(self.notebook, bg="#f0f2f5")
        self.notebook.add(tab, text=f" {plot_type} Limits & Marks ")
        self.limit_tabs[plot_type] = tab
        sub_notebook = ttk.Notebook(tab)
        sub_notebook.pack(fill="both", expand=True, padx=15, pady=15)
        for param in self.params:
            frame = tk.Frame(sub_notebook, bg="#f0f2f5")
            sub_notebook.add(frame, text=f" {param} ")
            self.create_limit_mark_section(frame, plot_type, param)       

    # 修改: create_limit_mark_section (添加 Peak Marker Search 组)
    # ----------------------------------------------------
    def create_limit_mark_section(self, parent, plot_type, param):
        canvas = tk.Canvas(parent, bg="#f0f2f5")
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas, bg="#f0f2f5")
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        lines = self.data[plot_type]["limit_lines"][param]
        marks = self.data[plot_type]["marks"][param]
        
        limit_container = tk.Frame(scrollable, bg="#f0f2f5")
        limit_container.pack(fill="x", pady=(0, 15))
        tk.Label(limit_container, text="Limit Lines", font=("sans-serif", 11, "bold"), bg="#f0f2f5", fg="#2c3e50").pack(anchor="w", padx=5)

        # 新增：Limit Control Frame (类似 Markers)
        limit_control_frame = tk.Frame(limit_container, bg="#f0f2f5")
        limit_control_frame.pack(fill="x", pady=(5, 10))

        # 新增：Limit Lines Frame (用于放置所有 limit line frames)
        limit_lines_frame = tk.Frame(limit_container, bg="#f0f2f5")
        limit_lines_frame.pack(fill="x")

        def draw_limit_line_frame(line_data, container):
            frame = tk.Frame(container, bg="#ffffff", relief="groove", bd=1)
            frame.pack(fill="x", pady=4, padx=5)

            unit_map = {
                "Magnitude (dB)": ("dB", "-20", "-20"),
                "Phase (deg)": ("deg", "-180", "-180"),
                "Group Delay (ns)": ("ns", "10", "10")
            }
            unit, default_lower, default_upper = unit_map.get(plot_type, ("?", "0", "0"))

            # Limit Lines 默认显示
            type_var = line_data.get("type", tk.StringVar(value="Upper Limit"))
            start_var = line_data.get("start", tk.StringVar(value="800"))
            stop_var = line_data.get("stop", tk.StringVar(value="900"))

            start_unit_var = line_data.get("start_unit", tk.StringVar(value="MHz"))
            # ❌ 移除这一行：start_unit_var.set("MHz") # 固定 MHz  # 不再固定，让其跟随
            stop_unit_var = line_data.get("stop_unit", tk.StringVar(value="MHz"))
            
            # ✅ 新增：绑定 stop_unit_var 的变化回调，让 start_unit_var 跟随
            def on_stop_unit_change(*args):
                start_unit_var.set(stop_unit_var.get())  # 同步单位
                # 可选：如果需要，调用 self.update_plots() 实时刷新绘图
                # self.update_plots()
            
            stop_unit_var.trace_add("write", on_stop_unit_change)  # 监听 "write" 事件（值变化时触发）
            
            lower_var = line_data.get("lower", tk.StringVar(value=default_lower))
            upper_var = line_data.get("upper", tk.StringVar(value=default_upper))

            #UI控件
            tk.Label(frame, text="Type:", bg="#ffffff").grid(row=0, column=0, padx=3)
            ttk.Combobox(frame, textvariable=type_var, values=["Upper Limit", "Lower Limit"], width=12, state="readonly").grid(row=0, column=1, padx=3)

            tk.Label(frame, text="Start:", bg="#ffffff").grid(row=0, column=2, padx=3)
            tk.Entry(frame, textvariable=start_var, width=9).grid(row=0, column=3, padx=1)
            #limit line移除Start频率后面MHz的显示
            #tk.Label(frame, text="MHz", bg="#ffffff", width=4).grid(row=0, column=4, padx=1)

            tk.Label(frame, text="Stop:", bg="#ffffff").grid(row=0, column=5, padx=3)
            tk.Entry(frame, textvariable=stop_var, width=9).grid(row=0, column=6, padx=1)
            ttk.Combobox(frame, textvariable=stop_unit_var, values=["MHz", "GHz"], width=4, state="readonly").grid(row=0, column=7, padx=1)

            tk.Label(frame, text=f"Lower ({unit}):", bg="#ffffff").grid(row=0, column=8, padx=3)
            tk.Entry(frame, textvariable=lower_var, width=7).grid(row=0, column=9, padx=3)
            tk.Label(frame, text=f"Upper ({unit}):", bg="#ffffff").grid(row=0, column=10, padx=3)
            tk.Entry(frame, textvariable=upper_var, width=7).grid(row=0, column=11, padx=3)

            line_data.update({
                "frame": frame,
                "type": type_var,
                "start": start_var,
                "stop": stop_var,
                "start_unit": start_unit_var,
                "stop_unit": stop_unit_var,
                "lower": lower_var,
                "upper": upper_var
            })

            def remove_and_update():
                frame.destroy()
                lines.remove(line_data)
                # ❌ 移除自动刷新
                # self.update_plots()

            tk.Button(frame, text="Remove", bg="#e74c3c", fg="white",
                      command=remove_and_update).grid(row=0, column=12, padx=5)

            # ❌ 移除自动刷新绑定
            # for var in [type_var, start_var, stop_var, start_unit_var, stop_unit_var, lower_var, upper_var]:
            #     var.trace_add("write", lambda *args: self.update_plots())

        # 绘制现有 limit lines 到 limit_lines_frame
        for line in lines:
            draw_limit_line_frame(line, limit_lines_frame)

        # Add Limit Line 按钮放在 control frame 的左侧
        def add_limit_and_draw():
            # 【BUG 修复 1：无文件时禁止添加 Limit Line】
            if not self.datasets:
                messagebox.showwarning("Warning", "Please load an S2P file before adding a Limit Line.")
                return
            new_line = {}
            lines.append(new_line)
            draw_limit_line_frame(new_line, limit_lines_frame)
            self.update_plots() # 新增 Limit Line 后调用更新绘图
        tk.Button(limit_control_frame, text="Add Limit Line", bg="#3498db", fg="white", command=add_limit_and_draw, width=12).pack(side="left", padx=5)

        #Regular Marker组
        mark_container = tk.Frame(scrollable, bg="#f0f2f5")
        mark_container.pack(fill="x", pady=(15, 0))
        tk.Label(mark_container, text="Regular Marker", font=("sans-serif", 11, "bold"), bg="#f0f2f5", fg="#2c3e50").pack(anchor="w", padx=5)
        marker_control_frame = tk.Frame(mark_container, bg="#f0f2f5")
        marker_control_frame.pack(fill="x", pady=(6, 10))
        marker_list_frame = tk.Frame(mark_container, bg="#f0f2f5")
        marker_list_frame.pack(fill="x")
        self.data[plot_type]["ui_refs"][param] = {"marker_list_frame": marker_list_frame, "canvas": canvas}
        def add_mark_and_draw():
            # 【BUG 修复 2：无文件时禁止添加 Marker】
            if not self.datasets:
                messagebox.showwarning("Warning", "Please load an S2P file before adding a Marker.")
                return

            data_id_options = [str(d['id']) for d in self.datasets]
            default_data_id = data_id_options[0] if data_id_options else "1"
            
            # 优化后的 new_mark 定义，新增 display_status 字段
            new_mark = {
                "id": "TEMP", 
                "freq": tk.StringVar(value="100"), 
                "unit": tk.StringVar(value="MHz"), 
                "data_id": tk.StringVar(value=default_data_id),
                "display_status": tk.StringVar(value="Display"), # <<< 新增：默认状态为 "Display"
                "is_search": False  # [新增] 标识为普通 Marker
            }
            
            # 假设 marks 变量在 add_mark_and_draw 的作用域内可用，指向 self.data[plot_type]["marks"][param]
            marks.append(new_mark)
            self._reindex_markers_and_refresh_ui(plot_type, param)

        tk.Button(marker_control_frame, text="Add Marker", bg="#2ecc71", fg="white", command=add_mark_and_draw, width=12).pack(side="left", padx=5)

        # [新增] Peak Marker Search 组
        # Peak Marker Search 容器 (类似 mark_container)
        search_mark_container = tk.Frame(scrollable, bg="#f0f2f5")
        search_mark_container.pack(fill="x", pady=(15, 0))
        tk.Label(search_mark_container, text="Peak Marker Search", font=("sans-serif", 11, "bold"), bg="#f0f2f5", fg="#2c3e50").pack(anchor="w", padx=5)
        
        # Peak Marker Search 控制 Frame (类似 marker_control_frame)
        search_marker_control_frame = tk.Frame(search_mark_container, bg="#f0f2f5")
        search_marker_control_frame.pack(fill="x", pady=(6, 10))
        
        # Peak Marker Search 列表 Frame (类似 marker_list_frame)
        search_marker_list_frame = tk.Frame(search_mark_container, bg="#f0f2f5")
        search_marker_list_frame.pack(fill="x")
        
        # [新增] 存储 search_marker_list_frame 到 ui_refs (可选，如果需要单独管理)
        self.data[plot_type]["ui_refs"][param]["search_marker_list_frame"] = search_marker_list_frame
        
        # [新增] Add Marker 按钮 for Search
        def add_search_mark_and_draw():
            # 【BUG 修复 3：无文件时禁止添加 Peak Marker Search】
            if not self.datasets:
                messagebox.showwarning("Warning", "Please load an S2P file before adding a Marker.")
                return            
            data_id_options = [str(d['id']) for d in self.datasets]
            default_data_id = data_id_options[0] if data_id_options else "1"
            
            new_search_mark = {
                    "id": "TEMP", 
                    "start": tk.StringVar(value="800"),  
                    "stop": tk.StringVar(value="900"),   
                    "unit": tk.StringVar(value="MHz"),   
                    "search_type": tk.StringVar(value="Max Value"),  
                    "data_id": tk.StringVar(value=default_data_id),  
                    "display_status": tk.StringVar(value="Display"), 
                    "is_search": True,
                    # 新增：Custom Search 相关变量
                    "custom_value": tk.StringVar(value="0"),  # 默认 Value 为 0
                    "match_type": tk.StringVar(value="First Match")  # 默认 First Match
                }
                    
            marks = self.data[plot_type]["marks"][param]  # 明确获取
            marks.append(new_search_mark)
            
            # 【关键修复】只刷新 Search Marker 列表
            self._refresh_search_markers_ui(plot_type, param)
        
        tk.Button(search_marker_control_frame, text="Add Marker", bg="#2ecc71", fg="white", command=add_search_mark_and_draw, width=12).pack(side="left", padx=5)
        
        self._reindex_markers_and_refresh_ui(plot_type, param)

    # ----------------------------------------------------

    # ----------------------------------------------------
    # [新增] 仅刷新 Marker Search 列表 UI
    # ----------------------------------------------------
    def _refresh_search_markers_ui(self, plot_type, param):
        marks = self.data[plot_type]["marks"].get(param, [])
        search_list_frame = self.data[plot_type]["ui_refs"][param].get("search_marker_list_frame")
        if not search_list_frame:
            return
        
        # 清空旧 UI
        for w in search_list_frame.winfo_children():
            w.destroy()
        
        # 只绘制 is_search == True 的 Marker
        search_marks = [m for m in marks if m.get("is_search", False)]
        search_count = 1
        
        for mark in search_marks:
            if "frame" in mark and mark["frame"]:
                mark["frame"].destroy()
            
            mark["id"] = f"P{search_count}"
            search_count += 1
            self._draw_search_marker_frame(mark, search_list_frame, plot_type, param)
        
        # 更新滚动区域
        canvas = self.data[plot_type]["ui_refs"][param]["canvas"]
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
    # ----------------------------------------------------
 
    # [新增] Peak Marker Custom Search 辅助方法
    # ----------------------------------------------------
    def _get_plot_type_unit_display(self, plot_type):
        """根据 Plot Type 返回 Y 轴单位，用于 Custom Value 提示。"""
        if plot_type == "Magnitude (dB)":
            return "dB"
        elif plot_type == "Phase (deg)":
            return "deg"
        elif plot_type == "Group Delay (ns)":
            return "ns"
        return "Value" # 默认值

    #Peak Marker Custom Search辅助方法，在给定的频率-数据曲线中，查找与特定目标值（target_value）相匹配的频率
    def _find_custom_match_freq_hz(self, target_value, search_freq_hz, search_data_array, match_type):
        """
        允许 First Match / Last Match，有 crossing 用 crossing，没有 crossing 用最近的点，但左右侧分别取。
        """

        # crossing detection
        is_below = search_data_array < target_value
        cross_indices = np.where(np.diff(is_below))[0]

        crossing_freqs = []
        for i in cross_indices:
            x1, x2 = search_freq_hz[i], search_freq_hz[i+1]
            y1, y2 = search_data_array[i], search_data_array[i+1]
            if abs(y2 - y1) > 1e-12:
                interpolated_freq = x1 + (target_value - y1) * (x2 - x1) / (y2 - y1)
                crossing_freqs.append(interpolated_freq)

        # ----------------------
        # Case 1: 有 crossing（优先使用）
        # ----------------------
        if crossing_freqs:
            if match_type == "First Match":
                return crossing_freqs[0]
            else:  # Last Match
                return crossing_freqs[-1]

        # ----------------------
        # Case 2: 无 crossing → fallback
        # 需要区分 First 与 Last
        # ----------------------
        diffs = search_data_array - target_value

        if match_type == "First Match":
            # 从左开始，找最早接近 target 的一段
            idx = np.argmin(np.abs(diffs))
        else:
            # Last Match → 从右侧选择最近的
            idx = len(diffs) - 1 - np.argmin(np.abs(diffs[::-1]))

        return search_freq_hz[idx]
    #-------------------------------    

    # 【优化版】绘制 Search Marker 行（UI + 交互）
    # ----------------------------------------------------
    def _draw_search_marker_frame(self, mark_data, container, plot_type, param):
        frame = tk.Frame(container, bg="#ffffff", relief="groove", bd=1)
        frame.pack(fill="x", pady=4, padx=5)
        mark_data["frame"] = frame

        # ID
        tk.Label(frame, text=mark_data["id"] + ":", bg="#ffffff", font=("sans-serif", 10, "bold")).grid(row=0, column=0, padx=3, sticky="w")

        # Start
        tk.Label(frame, text="Start:", bg="#ffffff").grid(row=0, column=1, padx=3)
        tk.Entry(frame, textvariable=mark_data["start"], width=9).grid(row=0, column=2, padx=1)

        # Stop
        tk.Label(frame, text="Stop:", bg="#ffffff").grid(row=0, column=3, padx=3)
        tk.Entry(frame, textvariable=mark_data["stop"], width=9).grid(row=0, column=4, padx=1)

        # Unit (下拉菜单：MHz / GHz)
        ttk.Combobox(frame, textvariable=mark_data["unit"], values=["MHz", "GHz"], width=4, state="readonly").grid(row=0, column=5, padx=1)

        # Ref ID
        tk.Label(frame, text="Ref ID:", bg="#ffffff").grid(row=0, column=6, padx=3)
        data_id_options = [str(d['id']) for d in self.datasets]
        combo = ttk.Combobox(frame, textvariable=mark_data["data_id"], values=data_id_options, state="readonly", width=4)
        combo.grid(row=0, column=7, padx=3)

        # Type
        tk.Label(frame, text="Type:", bg="#ffffff").grid(row=0, column=8, padx=3)
        type_combo = ttk.Combobox(frame, textvariable=mark_data["search_type"], values=MARKER_SEARCH_TYPES, state="readonly", width=13)
        type_combo.grid(row=0, column=9, padx=3)

        # 新增：Extra Frame 用于 Custom Search 控件（Value 输入 + Unit + Match 下拉）
        extra_frame = tk.Frame(frame, bg="#ffffff")
        extra_frame.grid(row=0, column=10, columnspan=2, padx=3, sticky="w")

        value_label = tk.Label(extra_frame, text="Value:", bg="#ffffff")
        value_label.pack(side="left", padx=3)
        
        value_entry = tk.Entry(extra_frame, textvariable=mark_data["custom_value"], width=6)
        value_entry.pack(side="left", padx=1)
        
        # 动态单位（基于当前 Plot Type）
        unit = self._get_plot_type_unit_display(plot_type)  # 使用新增的_get_plot_type_unit_display辅助函数
        unit_label = tk.Label(extra_frame, text=unit, bg="#ffffff", width=5)
        unit_label.pack(side="left", padx=1)
        
        match_combo = ttk.Combobox(extra_frame, textvariable=mark_data["match_type"], values=MATCH_TYPES, state="readonly", width=10)
        match_combo.pack(side="left", padx=3)

        # ------------------------------------------------
        # Display / Hide 按钮（关键修复）
        # ------------------------------------------------
        status_btn = tk.Button(
            frame,
            textvariable=mark_data["display_status"],
            width=8,
            command=lambda: self._toggle_display_status(mark_data["display_status"], status_btn)
        )
        status_btn.grid(row=0, column=12, padx=5)  # 调整 column 以容纳 extra_frame
        self._update_status_button_color(status_btn, mark_data["display_status"].get())
        mark_data["status_btn"] = status_btn  # 保存引用

        # ------------------------------------------------
        # Remove 按钮
        # ------------------------------------------------
        def remove_and_update():
            frame.destroy()
            marks = self.data[plot_type]["marks"][param]
            if mark_data in marks:
                marks.remove(mark_data)
            self._refresh_search_markers_ui(plot_type, param)
            #删除后不刷新
            #self.update_plots()

        tk.Button(frame, text="Remove", bg="#e74c3c", fg="white", command=remove_and_update).grid(row=0, column=13, padx=5)  # 调整 column

        # 新增：监听 search_type 变化，动态显示/隐藏 extra_frame
        def on_search_type_change(*args):
            # 【关键修正：检查 extra_frame 是否存活】
            if extra_frame.winfo_exists():
                if mark_data["search_type"].get() == "Custom Search":
                    extra_frame.grid()  # 显示
                else:
                    extra_frame.grid_remove()  # 隐藏
                
                # 仅在 extra_frame 存活时更新图表
                #不刷新图表
                #self.update_plots() 
            
            # 如果 extra_frame 不存活，则不执行任何操作，避免 TclError

        mark_data["search_type"].trace_add("write", on_search_type_change)
        on_search_type_change()  # 初始调用以设置隐藏/显示
    
    # ---------- create_data_information_tab ----------
    def create_data_information_tab(self):
        
        # 1. 创建 Tab 页 (保持不变)
        if not hasattr(self, 'data_information_tab'):
            self.data_information_tab = tk.Frame(self.notebook, bg="#f0f2f5")
        try:
            self.notebook.index(self.data_information_tab)
        except tk.TclError:
            self.notebook.add(self.data_information_tab, text=" Loaded File Information ")
            
        try:
            current_index = self.notebook.index(self.data_information_tab)
            if current_index != 1:
                self.notebook.insert(1, self.data_information_tab)
        except tk.TclError:
            pass
            
        # 2. 创建文件列表区域 (Loaded Files) - (保持不变)
        if not hasattr(self, 'file_list_frame'):
            self.file_list_frame = tk.LabelFrame(self.data_information_tab, text="Loaded S2P File List",
                                                 font=("sans-serif", 10), bg="#f0f2f5")
            self.file_list_frame.pack(fill="x", pady=(10, 0), padx=15)
            
            # --- 滚动区域容器 ---
            scroll_container = tk.Frame(self.file_list_frame, bg="#f0f2f5")
            scroll_container.pack(fill="x", padx=5, pady=5)
            
            # 关键：Canvas 限制高度并设置滚动
            self.file_list_canvas = tk.Canvas(scroll_container, bg="#f0f2f5", height=180, highlightthickness=0)
            self.file_list_scrollbar = tk.Scrollbar(scroll_container, orient="vertical", command=self.file_list_canvas.yview)
            self.file_list_content = tk.Frame(self.file_list_canvas, bg="#f0f2f5")
            
            def _update_scrollregion(event):
                if self.file_list_content.winfo_reqheight() > self.file_list_canvas.winfo_height():
                    self.file_list_canvas.configure(scrollregion=self.file_list_canvas.bbox("all"))
                else:
                    self.file_list_canvas.configure(scrollregion=(0, 0, 0, self.file_list_canvas.winfo_height()))
            self.file_list_content.bind("<Configure>", _update_scrollregion)
            
            if not hasattr(self, 'file_list_content_id'):
                self.file_list_content_id = self.file_list_canvas.create_window((0, 0), window=self.file_list_content, anchor="nw")
                
            self.file_list_canvas.configure(yscrollcommand=self.file_list_scrollbar.set)
            
            self.file_list_scrollbar.pack(side="right", fill="y")
            self.file_list_canvas.pack(side="left", fill="x", expand=True)

        # 3. 创建自定义 ID 名称区域 (S2P File ID Customization) (保持不变)
        if not hasattr(self, 'custom_id_outer'):
            custom_id_outer = tk.Frame(self.data_information_tab, bg="#f0f2f5")
            custom_id_outer.pack(fill="x", side="top", anchor="w", padx=15, pady=(10, 0))    
            self.custom_id_outer = custom_id_outer    
            
            custom_id_frame = tk.LabelFrame(custom_id_outer, text="S2P File ID Customization",
                                             font=("sans-serif", 10), bg="#f0f2f5", labelanchor="nw")
            custom_id_frame.pack(fill="x", anchor="w", padx=0, pady=0)
            input_frame = tk.Frame(custom_id_frame, bg="#f0f2f5")
            #优化S2P File ID Customization显示
            #input_frame.pack(fill="x", padx=5, pady=5, anchor="w") 
            input_frame.pack(pady=12, padx=10, anchor="w")         
            
            if not hasattr(self, 'selected_data_id_var'): self.selected_data_id_var = tk.StringVar(value="")
            if not hasattr(self, 'custom_name_var'): self.custom_name_var = tk.StringVar(value="")
                
            tk.Label(input_frame, text="Select ID:", bg="#f0f2f5").pack(side="left", padx=(0, 5))
            self.id_combo = ttk.Combobox(input_frame, textvariable=self.selected_data_id_var, state="readonly", width=10)
            self.id_combo.pack(side="left", padx=5)
            tk.Label(input_frame, text=" Custom ID:", bg="#f0f2f5").pack(side="left", padx=(15, 5))
            tk.Entry(input_frame, textvariable=self.custom_name_var, width=13).pack(side="left", padx=5)
            tk.Button(input_frame, text="Apply", command=self.set_custom_id_name, width=10).pack(side="left", padx=(10, 10))
            tk.Button(input_frame, text="Reset ID", bg="#e74c3c", fg="white", command=self.clear_custom_names, width=10).pack(side="left", padx=(5, 5))
            self.id_combo.bind("<<ComboboxSelected>>", self._on_id_selected_for_rename)
        
        # 4. [新增] Marker Legend 自定义区域 (保持不变)
        if not hasattr(self, 'marker_legend_outer'):
             self.marker_legend_outer = self._create_marker_legend_config_ui(self.data_information_tab)

        # 【新增】Marker Legend Position 控制区（放在 Background Customization 下面）
        self.create_marker_position_config_ui()

        # ============================
        # 5. [新增]Report Logo
        # ============================
        if not hasattr(self, 'report_logo_group'):
            # 更改 LabelFrame 文本以提醒用户尺寸已固定
            self.report_logo_group = tk.LabelFrame(self.data_information_tab, text="Report Logo (Fixed Size 150x60px)",
                                                   font=("sans-serif", 10), bg="#f0f2f5")
            self.report_logo_group.pack(fill="x", padx=10, pady=5)
            
            # --- 主控制容器：用于垂直排列 Logo、路径和按钮 ---
            logo_controls_frame = tk.Frame(self.report_logo_group, bg="#f0f2f5")
            logo_controls_frame.pack(fill="x", padx=5, pady=(5, 5))
            
            # 1. Logo 预览 (位于最上方，靠左)
            blank_img = ImageTk.PhotoImage(Image.new('RGBA', (1, 1), (0, 0, 0, 0)))
            self.logo_preview_label = tk.Label(logo_controls_frame, image=blank_img, bg="#f0f2f5")
            self.logo_preview_label.image = blank_img # 保持引用
            self.logo_preview_label.pack(side="top", anchor="w", padx=10, pady=(5, 0)) 
            
            # 2. 路径标签 (文件名，位于 Logo 预览的正下方，靠左)
            self.logo_path_label = tk.Label(logo_controls_frame, text="(No image selected)",
                                             bg="#f0f2f5", fg="#555", 
                                             wraplength=300, 
                                             anchor="w",        # 确保 Label widget 内容靠左
                                             justify="left")   # 确保多行文本靠左
            
            # ⚠️ 关键修改：移除 fill="x"，依靠 anchor="w" 实现靠左对齐
            self.logo_path_label.pack(side="top", padx=10, pady=(0, 5), anchor="w")

            # 3. 按钮容器 (位于路径标签下方，靠左)
            btn_frame = tk.Frame(logo_controls_frame, bg="#f0f2f5")
            btn_frame.pack(side="top", anchor="w", pady=5)
            
            # 选择按钮
            tk.Button(btn_frame, text="Choose Logo Image",
                     command=self._select_report_logo_file, width=18).pack(side="left", padx=(10, 10)) 
            
            # 清除 Logo 按钮
            tk.Button(btn_frame, text="Clear Logo", 
                     command=self._clear_report_logo, bg="#e74c3c", fg="white", width=12).pack(side="left", padx=(5, 5))

            # 确保初始化时，如果 self.report_logo_path 已经有值，显示预览和路径
            if hasattr(self, 'report_logo_path') and self.report_logo_path:
                try:
                    # 尝试加载旧 Logo 以设置预览
                    self._select_report_logo_file() 
                except Exception:
                    # 如果旧路径无效，清除它
                    self._clear_report_logo()
                            
        # 6. 创建可滚动的总结内容区域 (Summary Content) - 关键修改：移除 pack()
        if not hasattr(self, 'summary_content_frame'):
            canvas = tk.Canvas(self.data_information_tab, bg="#f0f2f5")
            self.summary_canvas = canvas # 必须保留引用
            scrollbar = tk.Scrollbar(self.data_information_tab, orient="vertical", command=canvas.yview)
            
            self.summary_content_frame = tk.Frame(canvas, bg="#f0f2f5")
            self.summary_content_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=self.summary_content_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # ❗ 移除 pack() 调用: 这样 Treeview 区域就不会显示在界面上
            # scrollbar.pack(side="right", fill="y")
            # canvas.pack(side="top", fill="both", expand=True, padx=15, pady=(10, 15))    
            
        # 7. 刷新文件列表 UI
        if not hasattr(self, 'display_vars'): # 【新增】初始化 display 状态变量的字典
            self.display_vars = {}
            
        self.update_file_list_ui()
        #------------------------------------------

    def _clear_report_logo(self):
        """清除 Report Logo 的路径、预览和配置。"""
        # 清除路径
        self.report_logo_path = ""
        
        # 清除 Tkinter 预览图像
        if hasattr(self, 'report_logo_preview_tk'):
            self.report_logo_preview_tk = None
            
        # 更新 UI
        if hasattr(self, 'logo_path_label'):
            self.logo_path_label.config(text="(No image selected)")
        
        if hasattr(self, 'logo_preview_label'):
            # 使用一个 1x1 像素的透明图像来清除 Label 上的旧图像显示
            blank_img = ImageTk.PhotoImage(Image.new('RGBA', (1, 1), (0, 0, 0, 0)))
            self.logo_preview_label.config(image=blank_img)
            self.logo_preview_label.image = blank_img # 保持引用
        
        # 可选：通知用户
        # messagebox.showinfo("Report Logo", "Report Logo has been cleared.")

    def _clear_figure_elements(self, fig):
        # 清除文字元素
        for t in list(fig.texts):
            t.remove()

        # 清除 figimage()
        for img in list(fig.images):
            img.remove()

        # 清除 patches
        for p in list(fig.patches):
            p.remove()

        # 只删除 Logo Axes：add_axes 产生并且非常小
        for ax in list(fig.axes):
            # 主绘图区通常占据 0.1~0.9 区域，不会这么小
            x0, y0, w, h = ax.get_position().bounds

            # 这是 Logo Axes 的典型尺寸，图表不可能这么小
            if w < 0.3 and h < 0.3:
                ax.remove()



    def _select_report_logo_file(self):
        """打开文件对话框选择 Logo 文件，更新路径和预览。"""
        file_path = filedialog.askopenfilename(
            title="Select Logo Image",
            filetypes=[("Image Files (PNG/JPG)", "*.png;*.jpg;*.jpeg")]
        )
        
        if not file_path:
            return

        try:
            # 1. 加载和验证
            logo_img_full = Image.open(file_path).convert("RGBA")
            self.report_logo_path = file_path
            
            # 2. 更新路径标签
            self.logo_path_label.config(text=os.path.basename(file_path))
            
            # 3. 生成预览图 (例如最大 100x100 像素)
            preview_size = (100, 100)
            # 使用 thumbnail 保持纵横比
            logo_img_full.thumbnail(preview_size, Image.LANCZOS)
            
            # 4. 转换为 PhotoImage 并更新预览 Label
            logo_preview_tk = ImageTk.PhotoImage(logo_img_full)
            self.logo_preview_label.config(image=logo_preview_tk)
            # 必须保留引用，防止 Tkinter 垃圾回收
            self.logo_preview_label.image = logo_preview_tk 
            self.report_logo_preview_tk = logo_preview_tk # 保持类引用
            
        except Exception as e:
            messagebox.showerror("File Error", f"Failed to load image file: {e}")
            self._clear_report_logo() # 加载失败时清除所有设置

    # Logo图片
    def _draw_report_logo(self, fig, y_offset=10, logo_width="150", logo_height="60"):
        """
        【Axes 方案】在图像左上角绘制 Logo，尺寸由 logo_width, logo_height 指定。
        y_offset 现在解释为 Logo 距离顶部的像素边距 (top margin)。
        """        
        if not self.report_logo_path:
            return

        try:
            w_px = int(logo_width)
            h_px = int(logo_height)
            # 左边距固定为 10 像素
            x_offset_px = 10 
            
            # --- 1. 加载和处理图片 ---
            logo_img = Image.open(self.report_logo_path).convert("RGBA")
            logo_img = logo_img.resize((w_px, h_px), Image.LANCZOS)
            arr = np.array(logo_img)

            # --- 2. 计算相对坐标系 (0到1) 的 Axes 参数 ---
            
            # 获取 Figure 尺寸 (英寸) 和 DPI
            fig_width_in, fig_height_in = fig.get_size_inches()
            dpi = fig.get_dpi()
            
            # 将像素尺寸和边距转换为 Figure 的相对尺寸 (0到1)
            # Logo 相对宽度/高度
            logo_width_rel = (w_px / dpi) / fig_width_in
            logo_height_rel = (h_px / dpi) / fig_height_in
            
            # 边距相对距离
            x_offset_rel = (x_offset_px / dpi) / fig_width_in
            y_offset_rel = (y_offset / dpi) / fig_height_in
            
            # 确定 Axes 的左下角位置 [left, bottom, width, height]
            # left = 左边距 (x_offset_rel)
            # bottom = 1 - 顶部边距(y_offset_rel) - Logo相对高度(logo_height_rel)
            left = x_offset_rel
            bottom = 1 - y_offset_rel - logo_height_rel
            
            # --- 3. 创建 Axes 并显示 Logo ---
            logo_ax = fig.add_axes(
                [
                    left, 
                    bottom, 
                    logo_width_rel, 
                    logo_height_rel
                ]
            )
            
            logo_ax.imshow(arr)
            
            # 4. 清理 Axes
            logo_ax.axis('off') 
            logo_ax.set_zorder(20) 
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to add report logo (Axes mode):\n{e}")
        # 确保这里有一个缩进块，以防止 IndentationError


    def update_marker_position_visibility(self):
        """根据当前 Display Mode 安全地切换 Marker Legend Position 控件显示"""
        if not hasattr(self, 'position_content_frame') or not self.position_content_frame.winfo_exists():
            return

        mode = self.display_mode.get()

        # --- Normal 模式：显示 4 个独立标签页 ---
        if mode == "Normal":
            # 隐藏 Max 模式的全局控件
            if hasattr(self, 'max_position_frame') and self.max_position_frame.winfo_children():
                try:
                    self.max_position_frame.pack_forget()
                except:
                    pass
            # 显示 Normal 模式的 notebook
            if hasattr(self, 'normal_position_notebook'):
                self.normal_position_notebook.pack(fill="x", pady=8)

        # --- Max 模式：显示全局控件 ---
        else:
            # 隐藏 Normal 模式的 notebook
            if hasattr(self, 'normal_position_notebook'):
                try:
                    self.normal_position_notebook.pack_forget()
                except:
                    pass
            # 显示 Max 模式的全局控件
            if hasattr(self, 'max_position_frame') and self.max_position_frame.winfo_children():
                self.max_position_frame.pack(fill="x", pady=8)


    def update_marker_position_ui(self):
        """安全绑定当前 Plot Type 的配置 + 动态显示/隐藏 Custom 输入框"""
        if not hasattr(self, 'normal_position_controls') or not hasattr(self, 'max_position_controls'):
            return

        current_pt = self.plot_type.get()

        # 安全检查：当前 plot_type 是否有配置
        if current_pt not in self.marker_pos_configs or current_pt not in self.max_marker_pos_configs:
            return

        # ====================== Normal 模式：4 个参数独立绑定 ======================
        for param in self.params:
            if param not in self.normal_position_controls:
                continue
            ctrl = self.normal_position_controls[param]
            cfg = self.marker_pos_configs[current_pt][param]

            ctrl["combo"].config(textvariable=cfg["mode_var"])
            ctrl["x_entry"].config(textvariable=cfg["x_var"])
            ctrl["y_entry"].config(textvariable=cfg["y_var"])

            # Custom 输入框显示控制
            try:
                if cfg["mode_var"].get() == "Custom":
                    if not ctrl["custom_frame"].winfo_ismapped():
                        ctrl["custom_frame"].pack(side="left", padx=(10, 0))
                else:
                    if ctrl["custom_frame"].winfo_ismapped():
                        ctrl["custom_frame"].pack_forget()
            except:
                pass

        # ====================== Max 模式：全局绑定 ======================
        max_cfg = self.max_marker_pos_configs[current_pt]
        m = self.max_position_controls

        m["combo"].config(textvariable=max_cfg["mode_var"])
        m["x_entry"].config(textvariable=max_cfg["x_var"])
        m["y_entry"].config(textvariable=max_cfg["y_var"])

        try:
            if max_cfg["mode_var"].get() == "Custom":
                if not m["custom_frame"].winfo_ismapped():
                    m["custom_frame"].pack(side="left", padx=(10, 0))
            else:
                if m["custom_frame"].winfo_ismapped():
                    m["custom_frame"].pack_forget()
        except:
            pass
        #----------------------------    


    def toggle_dataset_display(self, data_id):
        """
        切换指定 ID 文件的显示状态，不触发绘图更新。
        用户需要手动刷新图表才能看到变化。
        """
        # 从 self.display_vars 中获取当前状态
        # 注意：这里获取的是点击 Checkbutton 后的新状态
        is_visible = self.display_vars.get(data_id).get()
        
        # 1. 更新内部数据集的状态
        for dataset in self.datasets:
            if dataset.get('id') == data_id:
                # 更新数据集的显示标志
                dataset['is_displayed'] = is_visible 
                break
        
        # 2. 移除绘图更新的调用
        # if hasattr(self, 'update_plots'):
        #      self.update_plots() # 移除此行，不自动更新
        
        # 可以在状态栏给出提示，通知用户需要手动刷新
        if hasattr(self, 'status_var'):
            action = "displayed" if is_visible else "hidden"
            self.status_var.set(f"Dataset ID {data_id} is now {action}. Please refresh plots to see changes.")

    def update_file_list_ui(self):
        if not hasattr(self, 'file_list_content'):
            return
       
        # Canvas autosize handling
        def _on_canvas_resize(event):
            if hasattr(self, 'file_list_content_id'):
                self.file_list_canvas.itemconfig(self.file_list_content_id, width=event.width)
        self.file_list_canvas.unbind("<Configure>")
        self.file_list_canvas.bind("<Configure>", _on_canvas_resize)

        # Clear old rows
        for widget in self.file_list_content.winfo_children():
            widget.destroy()

        if not self.datasets:
            tk.Label(self.file_list_content, text="No files loaded.", bg="#f0f2f5", fg="gray").pack(padx=5, pady=5)
            return

        # 初始化字典
        if not hasattr(self, 'custom_id_colors'):
            self.custom_id_colors = {}
        if not hasattr(self, 'custom_sparam_colors'):
            self.custom_sparam_colors = {}
        if not hasattr(self, 'display_vars'):
            self.display_vars = {}

        # Loop through datasets
        for i, dataset in enumerate(self.datasets):
            data_id = dataset['id']

            # Init display var
            if data_id not in self.display_vars:
                self.display_vars[data_id] = tk.BooleanVar(value=True)
                dataset['is_displayed'] = True
           
            display_var = self.display_vars[data_id]

            # 颜色逻辑
            if data_id in self.custom_id_colors:
                color = self.custom_id_colors[data_id]
            else:
                color = COLOR_CYCLE[(data_id - 1) % len(COLOR_CYCLE)]

            file_name_only = os.path.basename(dataset['name'])

            # 每行容器
            file_row_frame = tk.Frame(self.file_list_content, bg="#f0f2f5")
            file_row_frame.pack(fill="x", padx=5, pady=2, anchor="w")

            # ==================== 左侧：颜色按钮 + 复位 ====================
            # ==========================================================
            # 🟦🟦🟦 新增：颜色按钮 Color🎨（插入在行最左边）🟦🟦🟦
            # ==========================================================
            # 新增：颜色设置 + 一键复位按钮
            # ==========================================================
            btn_frame = tk.Frame(file_row_frame, bg="#f0f2f5")
            btn_frame.pack(side="left", padx=(2, 6))

            color_button = tk.Button(
                btn_frame,
                text="🎨",
                width=3,
                font=("Segoe UI Symbol", 8),
                command=lambda id=data_id: self.open_color_setting_dialog(id)
            )
            color_button.pack(side="left")
            self.create_tooltip(color_button, "Set custom color")

            reset_button = tk.Button(
                btn_frame,
                text="↺",  # 循环箭头
                width=2,
                font=("Segoe UI Symbol", 9, "bold"),
                fg="#d35400",
                relief="flat",
                command=lambda id=data_id: self.reset_custom_color(id)
            )
            reset_button.pack(side="left", padx=(4, 0))
            self.create_tooltip(reset_button, "Reset to default color")

            # ==================== 中间：文件名标签 ====================
            text = f"ID {data_id} - {file_name_only}"
            label = tk.Label(
                file_row_frame,
                text=text,
                bg="#f0f2f5",
                fg=color,
                font=("sans-serif", 10, "bold"),
                anchor="w"
            )
            label.pack(side="left", padx=5, fill="x", expand=True)
            # 可选：悬停显示完整路径
            self.create_tooltip(label, dataset['name'])

            # ==================== 右侧：Display 复选框 ====================
            display_check = tk.Checkbutton(
                file_row_frame,
                text="Display",
                variable=display_var,
                bg="#f0f2f5",
                relief="flat",
                command=lambda id=data_id: self.toggle_dataset_display(id)
            )
            display_check.pack(side="right", padx=(5, 5))
            self.create_tooltip(display_check, "Show / Hide this file in plot")

            # ==================== 最右侧：删除按钮 ====================
            def remove_data(data_id_to_remove=data_id):
                self.remove_dataset(data_id_to_remove)
                if data_id_to_remove in self.display_vars:
                    del self.display_vars[data_id_to_remove]

            remove_btn = tk.Button(
                file_row_frame,
                text="X",
                command=remove_data,
                bg="#e74c3c",
                fg="white",
                font=("sans-serif", 8, "bold"),
                width=2,
                height=1,
                relief="flat"
            )
            remove_btn.pack(side="right", padx=(5, 10))
            self.create_tooltip(remove_btn, "Delete this file")


    # S2P曲线自定义颜色对话框
    def open_color_setting_dialog(self, dataset_id):
        """颜色设置对话框：Normal 模式立即生效，Max 模式需要确认，智能定位右下角"""
        if not hasattr(self, 'custom_id_colors'):
            self.custom_id_colors = {}
        if not hasattr(self, 'custom_sparam_colors'):
            self.custom_sparam_colors = {}

        mode = self.display_mode.get()

        win = tk.Toplevel(self.root)
        win.title(f"Color Settings - ID {dataset_id}")
        
        # ----------------------------------------------------
        # 💥 关键修复：显式设置 Toplevel 窗口的图标
        # ----------------------------------------------------
        try:
            # 假设 resource_path 是在类外部定义的全局函数
            icon_path = resource_path("StoreLogo.ico")
            win.iconbitmap(icon_path)
        except Exception:
            # 如果设置失败（例如找不到文件），保持默认图标，不阻止程序运行
            pass
        # ----------------------------------------------------
        
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        win.focus_force()

        # ==================== 智能定位：右下角 ====================
        self.root.update_idletasks()
        main_x = self.root.winfo_rootx()
        main_y = self.root.winfo_rooty()
        main_w = self.root.winfo_width()
        main_h = self.root.winfo_height()
        pos_x = main_x + main_w - 1250
        pos_y = main_y + main_h - 950

        if mode == "Normal":
            win.geometry(f"340x210+{pos_x + 40}+{pos_y + 60}")
        else:
            win.geometry(f"380x340+{pos_x}+{pos_y}")

        # ================================== Normal 模式 ==================================
        if mode == "Normal":
            tk.Label(win, text=f"Set color for ID {dataset_id}:", font=("sans-serif", 11, "bold")).pack(pady=18)

            current_color = self.custom_id_colors.get(dataset_id,
                                    COLOR_CYCLE[(dataset_id - 1) % len(COLOR_CYCLE)])

            preview = tk.Label(win, text="  ", bg=current_color, relief="sunken", bd=2, width=10, height=1)
            preview.pack(pady=12)

            def pick_and_apply():
                color = tk.colorchooser.askcolor(initialcolor=current_color)[1]
                if color:
                    self.custom_id_colors[dataset_id] = color
                    preview.config(bg=color)
                    self.update_file_list_ui()
                    self.update_plots()
                    win.destroy()

            tk.Button(win, text="Choose", width=12,
                        command=pick_and_apply).pack(pady=15)

        # ================================== Max 模式 ==================================
        else:
            tk.Label(win, text=f"Set S-Parameter colors for ID {dataset_id}:",
                        font=("sans-serif", 11, "bold")).pack(pady=18)

            # 强制顺序：S11, S21, S12, S22 → 对应 COLOR_CYCLE 的第 0,1,2,3 位（每条文件依次递增）
            FIXED_PARAM_ORDER = ["S11", "S21", "S12", "S22"]

            if dataset_id not in self.custom_sparam_colors:
                self.custom_sparam_colors[dataset_id] = {}

            temp_colors = {}
            preview_labels = {}

            for idx, param in enumerate(FIXED_PARAM_ORDER):
                # 计算该参数在整个数据集中的全局索引
                # (dataset_id-1)*4 + idx  → 保证每条文件四个参数颜色连续且不重复
                global_idx = (dataset_id - 1) * 4 + idx
                default_color = COLOR_CYCLE[global_idx % len(COLOR_CYCLE)]

                current_color = self.custom_sparam_colors[dataset_id].get(param, default_color)
                temp_colors[param] = current_color

                row = tk.Frame(win)
                row.pack(fill="x", pady=8, padx=22)

                tk.Label(row, text=param, width=6, font=("sans-serif", 10, "bold")).pack(side="left")
                lbl = tk.Label(row, text="  ", bg=current_color, relief="groove", bd=2, width=10, height=1)
                lbl.pack(side="left", padx=15)
                preview_labels[param] = lbl

                def pick(p=param):
                    color = tk.colorchooser.askcolor(initialcolor=temp_colors[p])[1]
                    if color:
                        temp_colors[p] = color
                        preview_labels[p].config(bg=color)

                tk.Button(row, text="Choose", width=10, command=pick).pack(side="right")

            # 底部按钮区
            btn_frame = tk.Frame(win)
            btn_frame.pack(pady=25)

            def apply():
                self.custom_sparam_colors[dataset_id] = temp_colors.copy()
                self.update_plots()
                win.destroy()

            def cancel():
                win.destroy()

            tk.Button(btn_frame, text="Confirm", width=12, height=2, bg="#27ae60", fg="white",
                        font=("sans-serif", 10, "bold"), command=apply).pack(side="left", padx=15)
            tk.Button(btn_frame, text="Cancel", width=12, height=2, bg="#e74c3c", fg="white",
                        font=("sans-serif", 10), command=cancel).pack(side="left", padx=15)

            win.bind("<Return>", lambda e: apply())
            win.bind("<Escape>", lambda e: cancel())


    #清空自定义颜色按钮
    def reset_custom_color(self, dataset_id):
        """一键清除指定 ID 的自定义颜色（支持 Normal 和 Max 模式）"""
        removed = False

        # Normal 模式：清除 ID 颜色
        if dataset_id in self.custom_id_colors:
            del self.custom_id_colors[dataset_id]
            removed = True

        # Max 模式：清除该 ID 下的所有 S 参数颜色
        if dataset_id in self.custom_sparam_colors:
            del self.custom_sparam_colors[dataset_id]
            removed = True

        if removed:
            self.status_var.set(f"ID {dataset_id} color has been reset to default.")
            self.update_plots()  # 实时刷新图表
            self.update_file_list_ui()  # 更新文件列表中的颜色显示
        else:
            self.status_var.set(f"ID {dataset_id} has no custom color to reset.")

    #悬停提示
    def create_tooltip(self, widget, text):
        """简单实用的鼠标悬停提示（Tooltip）"""
        def on_enter(event):
            # 创建一个无边框小窗口
            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)  # 去掉窗口边框
            tooltip.wm_geometry(f"+{event.x_root + 15}+{event.y_root + 10}")

            label = tk.Label(
                tooltip,
                text=text,
                background="#ffffe0",
                relief="solid",
                borderwidth=1,
                font=("Segoe UI", 8),
                padx=5,
                pady=2
            )
            label.pack()

            # 把 tooltip 窗口保存到 widget 上，方便后面销毁
            widget._tooltip = tooltip

        def on_leave(event):
            if hasattr(widget, '_tooltip'):
                widget._tooltip.destroy()
                try:
                    del widget._tooltip
                except:
                    pass

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)


    def _on_id_selected_for_rename(self, event=None):
        """选中下拉框时自动填入当前自定义名称"""
        selected_id = self.selected_data_id_var.get()
        if selected_id and selected_id in self.custom_id_names:
            self.custom_name_var.set(self.custom_id_names[selected_id])
        else:
            self.custom_name_var.set("")

    #自定义文件ID名称
    def set_custom_id_name(self):
        selected_id = self.selected_data_id_var.get()
        new_name = self.custom_name_var.get().strip()

        if not selected_id:
            messagebox.showerror("Error", "Please select a Data ID first.")
            return

        # 检查 new_name 是否为空
        if not new_name:
            if selected_id in self.custom_id_names:
                # 如果输入为空，则视为清除自定义名称
                del self.custom_id_names[selected_id]
                self.custom_name_var.set("")
                self.status_var.set(f"ID {selected_id} custom name cleared.")
                
                # 修复 Bug: 移除 self._update_legend()
                self.update_plots()
                self.update_file_list_ui() # 新增: 刷新文件信息列表 UI
                
                return

        # ------------------- 【优化点】新增：重复名称检测 -------------------
        # 排除当前正在编辑的 ID，检查其他 ID 是否已经使用了这个新名称
        for id_str, name in self.custom_id_names.items():
            # 确保 id_str 是字符串类型进行比较
            if str(id_str) != selected_id and name == new_name:
                messagebox.showerror("Error", f"The Custom ID '{new_name}' is already used by Data ID {id_str}. Please choose a unique name.")
                return
        # ------------------------------------------------------------------

        # 保存新名称
        self.custom_id_names[selected_id] = new_name
        self.status_var.set(f"Data ID {selected_id} set to '{new_name}'.")
        
        # 修复 Bug: 移除 self._update_legend()
        self.update_plots()
        self.update_file_list_ui() # 新增: 刷新文件信息列表 UI

    def clear_custom_names(self):
        """清空所有自定义 ID 名称，恢复到未自定义状态。"""
        # 1. 清空核心字典
        self.custom_id_names = {}
        
        # 2. 清空输入框变量
        self.selected_data_id_var.set("")
        self.custom_name_var.set("")
        
        # 3. 刷新 UI 和 plots (必须步骤，以更新 Legend 和文件列表)
        self.update_file_list_ui()
        self.update_plots()
        
        # 4. 给出状态提示
        messagebox.showinfo("Operation Complete", "All custom data names have been cleared.")

    def remove_dataset(self, data_id):
        # 暂存旧的 custom_id_names，用于重映射
        old_custom_id_names = self.custom_id_names
        
        # 1. 移除数据集
        self.datasets = [d for d in self.datasets if d['id'] != data_id]
        
        # 2. 重新编号剩余的数据集，并同时重映射 self.custom_id_names
        self.custom_id_names = {}
        for i, d in enumerate(self.datasets):
            old_id = d['id']
            new_id = i + 1
            
            d['id'] = new_id
            
            # 重映射 custom_id_names
            if str(old_id) in old_custom_id_names:
                self.custom_id_names[str(new_id)] = old_custom_id_names[str(old_id)]
                
        self.next_dataset_id = len(self.datasets) + 1

        # 【修复 Bug 1: 载入文件删除后，自动更新 Customize File 的 Select ID 下拉菜单】
        if hasattr(self, "id_combo"):
            # 1. 更新下拉菜单的选项值（重新生成新的 ID 列表）
            self.id_combo["values"] = [str(d["id"]) for d in self.datasets]
            # 2. 清空当前选择的值，防止选中已被删除的 ID
            self.selected_data_id_var.set("")

        # 【修复 Bug 2: 文件删除后，清空 Customize File 的 New Name 输入框】
        # 修复用户报告的 UI 遗留问题：确保 New Name 输入框被清空
        if hasattr(self, 'custom_name_var'):
            self.custom_name_var.set("") 
            
        # 刷新 UI
        self.update_file_list_ui()
        self.update_plots()
        self.update_data_information_tab()


    def on_plot_type_change(self, *args):
        plot_type = self.plot_type.get()
        is_supported = plot_type in ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"]

        # 1. 创建和管理 Limit & Mark Tab（保持原有逻辑）
        if is_supported:
            self.create_limit_mark_tab(plot_type)

        # 2. 切换 Limits & Marks 标签页的显示/隐藏（保持原有逻辑）
        active_tab_found = False
        if hasattr(self, 'limit_tabs'):
            for key, tab_widget in self.limit_tabs.items():
                if key == plot_type:
                    try:
                        self.notebook.tab(tab_widget, state='normal')
                        # ------------------------------------------------------------------
                        # 【核心修复】：移除这行代码，取消加载文件后或切换 Plot Type 后的自动切换行为
                        # self.notebook.select(tab_widget)
                        # ------------------------------------------------------------------
                        active_tab_found = True
                    except:
                        pass
                else:
                    try:
                        self.notebook.tab(tab_widget, state='hidden')
                    except:
                        pass

        # 3. 无有效 Limits & Marks 页面时回退到 Chart Tab
        self.create_data_information_tab()  # 确保信息页始终最新
        if not active_tab_found or not is_supported:
            try:
                self.notebook.select(self.chart_tab)
            except:
                pass

        # 4. 切换 Y Axis Control 子标签页（如果存在）
        if hasattr(self, 'y_sub_notebook'):
            plot_types = ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"]
            try:
                index = plot_types.index(plot_type)
                self.y_sub_notebook.select(index)
            except ValueError:
                pass

        # 5. 【新增关键】更新 Loaded File Information 页的 Marker Legend Position 控件绑定
        #    - 自动绑定当前 plot_type 对应的配置
        #    - 自动显示/隐藏 Custom X/Y 输入框
        if hasattr(self, 'update_marker_position_ui'):
            self.update_marker_position_ui()

        # 6. 根据当前 Display Mode 执行正确的绘图刷新
        display_mode = self.display_mode.get()

        if display_mode == "Normal":
            self.update_plots()          # Normal 模式：完整重绘
        else:  # Max 模式
            self.plot_combined()         # Max 模式：使用合并绘图函数

        # 7. 【可选增强】如果切换 Plot Type 时 Display Mode 是 Max，确保 Legend Position 控件也正确显示全局版
        if hasattr(self, 'update_marker_position_visibility'):
            self.update_marker_position_visibility()

    # ----------------------------------------------------
    # [新增] Marker Legend BBox 参数获取辅助函数
    # ----------------------------------------------------
    def _get_marker_legend_bbox_params(self):
        """根据用户选择返回 Matplotlib bbox 参数字典，并应用默认值。"""
        # --- Box Style ---
        boxstyle_choice = self.marker_legend_configs["boxstyle_var"].get()
        # 默认值: "round,pad=0.3"
        if boxstyle_choice == "Default":
            boxstyle_val = "round,pad=0.3"
        else:
            # 确保始终附加 pad=0.3
            boxstyle_val = f"{boxstyle_choice},pad=0.3"
            
        # --- Face Color ---
        facecolor_choice = self.marker_legend_configs["facecolor_var"].get()
        # 默认值: "yellow"
        facecolor_val = facecolor_choice if facecolor_choice != "Default" else "yellow"
        
        # --- Alpha ---
        alpha_choice = self.marker_legend_configs["alpha_var"].get()
        # 默认值: 0.9
        alpha_val = 0.9
        if alpha_choice != "Default":
            try:
                # 尝试将用户输入解析为浮点数
                alpha_val = float(alpha_choice)
            except ValueError:
                # 如果输入无效，回退到默认
                alpha_val = 0.9

        return dict(boxstyle=boxstyle_val, facecolor=facecolor_val, alpha=alpha_val)
    # ----------------------------------------------------

    # create_marker_legend_config_ui
    def _create_marker_legend_config_ui(self, master_frame):
        """
        创建 Marker Legend 自定义区域
        """
        # --- 外层 Frame ---
        marker_legend_outer = tk.Frame(master_frame, bg="#f0f2f5")
        marker_legend_outer.pack(fill="x", side="top", anchor="w", padx=15, pady=(10, 10))

        marker_legend_labelframe = tk.LabelFrame(
            marker_legend_outer,
            text="Marker Legend Background Customization",
            font=("sans-serif", 10),
            bg="#f0f2f5",
            labelanchor="nw"
        )
        marker_legend_labelframe.pack(fill="x", anchor="w", padx=0, pady=0)

        input_frame = tk.Frame(marker_legend_labelframe, bg="#f0f2f5")
        input_frame.pack(pady=12, padx=10, anchor="w")

        # --- Box Style ---
        tk.Label(input_frame, text="Box Style:", bg="#f0f2f5").pack(side="left", padx=(0, 5))
        boxstyle_options = ["Default"] + self.MARKER_LEGEND_BOXSTYLE_OPTIONS
        boxstyle_combo = ttk.Combobox(
            input_frame,
            textvariable=self.marker_legend_configs["boxstyle_var"],
            values=boxstyle_options,
            width=10,
            state="readonly"
        )
        boxstyle_combo.pack(side="left", padx=5)
        
        # 关键：加上这一行！！
        self.marker_legend_ui_refs['boxstyle_combo'] = boxstyle_combo   # ← 加这行！

        # --- Face Color ---
        tk.Label(input_frame, text="Face Color:", bg="#f0f2f5").pack(side="left", padx=(15, 5))
        facecolor_options = ["Default"] + self.MARKER_LEGEND_FACECOLOR_OPTIONS
        facecolor_combo = ttk.Combobox(
            input_frame,
            textvariable=self.marker_legend_configs["facecolor_var"],
            values=facecolor_options,
            width=10,
            state="readonly"
        )
        facecolor_combo.pack(side="left", padx=5)
        self.marker_legend_ui_refs['facecolor_combo'] = facecolor_combo   # ← 你已经有了

        # --- Alpha ---
        tk.Label(input_frame, text="Alpha:", bg="#f0f2f5").pack(side="left", padx=(15, 5))
        alpha_options = ["Default"] + self.MARKER_LEGEND_ALPHA_OPTIONS
        alpha_combo = ttk.Combobox(
            input_frame,
            textvariable=self.marker_legend_configs["alpha_var"],
            values=alpha_options,
            width=10,
            state="readonly"
        )
        alpha_combo.pack(side="left", padx=5)
        self.marker_legend_ui_refs['alpha_combo'] = alpha_combo         # ← 你已经有了

        return marker_legend_outer
    #-------------------------------    


    def create_marker_position_config_ui(self):
        """在 Loaded File Information 页创建 Marker Legend Position 控制区（仅创建一次）"""
        if hasattr(self, 'position_labelframe'):
            return  # 已创建，避免重复

        # 外层容器
        position_outer = tk.Frame(self.data_information_tab, bg="#f0f2f5")
        position_outer.pack(fill="x", side="top", anchor="w", padx=15, pady=(0, 10))

        # 主 LabelFrame
        self.position_labelframe = tk.LabelFrame(
            position_outer,
            text="Marker Legend Position",
            font=("sans-serif", 10),
            bg="#f0f2f5",
            labelanchor="nw"
        )
        self.position_labelframe.pack(fill="x", padx=0, pady=0)

        # 内容容器（所有控件都放在这里，方便后续 pack_forget）
        self.position_content_frame = tk.Frame(self.position_labelframe, bg="#f0f2f5")
        self.position_content_frame.pack(fill="x", padx=10, pady=8)

        # ==================== Normal 模式：4个独立标签页 ====================
        self.normal_position_notebook = ttk.Notebook(self.position_content_frame)
        self.normal_position_controls = {}  # 必须初始化！

        for param in self.params:
            tab = tk.Frame(self.normal_position_notebook, bg="#f0f2f5")
            display_text = f" {param} "                     # # 修改S11,S21,S12,S22直接的间隙
            self.normal_position_notebook.add(tab, text=display_text)
            #self.normal_position_notebook.add(tab, text=param)

            inner = tk.Frame(tab, bg="#f0f2f5")
            inner.pack(pady=12, padx=10, anchor="w")

            tk.Label(inner, text=f"{param} Legend Position:", bg="#f0f2f5", font=("sans-serif", 10)).pack(side="left")

            combo = ttk.Combobox(inner, values=self.MARKER_POSITIONS, state="readonly", width=11)
            combo.pack(side="left", padx=(8, 0))

            custom_frame = tk.Frame(inner, bg="#f0f2f5")
            tk.Label(custom_frame, text="X (0-1):", bg="#f0f2f5").pack(side="left")
            x_entry = tk.Entry(custom_frame, width=8, justify="center")
            x_entry.pack(side="left", padx=2)
            tk.Label(custom_frame, text="Y (0-1):", bg="#f0f2f5").pack(side="left", padx=(8, 2))
            y_entry = tk.Entry(custom_frame, width=8, justify="center")
            y_entry.pack(side="left")

            self.normal_position_controls[param] = {
                "combo": combo,
                "custom_frame": custom_frame,
                "x_entry": x_entry,
                "y_entry": y_entry
            }

        # ==================== Max 模式：单个全局控件 ====================
        self.max_position_frame = tk.Frame(self.position_content_frame, bg="#f0f2f5")

        max_inner = tk.Frame(self.max_position_frame, bg="#f0f2f5")
        max_inner.pack(pady=12, padx=10, anchor="w")

        tk.Label(max_inner, text="Legend Position (All Params):", bg="#f0f2f5", font=("sans-serif", 10)).pack(side="left")

        max_combo = ttk.Combobox(max_inner, values=self.MARKER_POSITIONS, state="readonly", width=15)
        max_combo.pack(side="left", padx=(8, 0))

        max_custom_frame = tk.Frame(max_inner, bg="#f0f2f5")
        tk.Label(max_custom_frame, text="X (0-1):", bg="#f0f2f5").pack(side="left")
        max_x_entry = tk.Entry(max_custom_frame, width=8, justify="center")
        max_x_entry.pack(side="left", padx=2)
        tk.Label(max_custom_frame, text="Y (0-1):", bg="#f0f2f5").pack(side="left", padx=(8, 2))
        max_y_entry = tk.Entry(max_custom_frame, width=8, justify="center")
        max_y_entry.pack(side="left")

        self.max_position_controls = {
            "combo": max_combo,
            "custom_frame": max_custom_frame,
            "x_entry": max_x_entry,
            "y_entry": max_y_entry
        }
        # 在 create_marker_position_config_ui() 最后加上这几行
        #style = ttk.Style()
        #style.configure("BigTab.TNotebook.Tab", 
        #                font=("Microsoft YaHei UI", 12, "bold"),   # 修改S11,S21,S12,S22字体
        #                padding=[12, 8])                          # 可选：让标签更宽松
        self.normal_position_notebook.configure(style="BigTab.TNotebook")
        
        # ==================== 关键：初始化显示状态 ====================
        # 必须在所有控件创建完毕后调用，确保不报错
        try:
            self.update_marker_position_visibility()
            self.update_marker_position_ui()
        except Exception as e:
            print(f"[Marker Position UI] 初始化警告: {e}")  # 静默处理，防止启动崩溃
        #---------------------------------------------------------

    # ---------- Data information tab ----------
    def update_data_information_tab(self):
        import tkinter as tk
        from tkinter import ttk
        
        # 确保关键组件存在
        if not hasattr(self, 'summary_content_frame') or not hasattr(self, 'summary_canvas'):
            return

        # ----------------------------------------------------------------------
        # 清空 Treeview 所在的 summary_content_frame 的所有子控件
        # ----------------------------------------------------------------------
        for w in self.summary_content_frame.winfo_children():
            w.destroy()

        # ----------------------------------------------------------------------
        # [保留] 更新 Customize ID Color 和 Customize Name 组合框的值 (同步 Data ID)
        # ----------------------------------------------------------------------
        data_id_list = [str(d['id']) for d in self.datasets]
        
        # 1. 更新 Customize Files (ID - Name) Combo Box (self.id_combo)
        if hasattr(self, "id_combo"):
            self.id_combo["values"] = data_id_list
            # 如果当前选中的 ID 不在列表中，则清空选中和输入框
            if self.selected_data_id_var.get() not in data_id_list:
                self.selected_data_id_var.set("")
                if hasattr(self, "custom_name_var"):
                    self.custom_name_var.set("")
        # ----------------------------------------------------------------------

        if not self.datasets:
            # ❗ 删除了 self.summary_canvas.pack_forget()
            
            # 显示“没有文件”的提示（在隐藏的 Frame 中，不显示，仅为逻辑完整）
            tk.Label(self.summary_content_frame, text="No S2P files loaded.", font=("sans-serif", 12), fg="gray", bg="#f0f2f5").pack(padx=20, pady=20)
            self.summary_content_frame.update_idletasks()
            return
            
        # ❗ 删除了 self.summary_canvas.pack()
        # try:
        #     self.summary_canvas.pack(side="top", fill="both", expand=True, padx=15, pady=(10, 15)) 
        # except tk.TclError:
        #     pass

        # --- Treeview 创建及配置 (保留以保证数据结构和内部使用) ---
        columns = ("ID", "File Path", "Points", "Format", "Frequency Range")
        tree = ttk.Treeview(self.summary_content_frame, columns=columns, show="headings", height=8)
        
        # ❗ 保存 Treeview 实例以供内部代码使用
        self.file_info_treeview = tree 
        
        style = ttk.Style()
        style.configure("LeftAligned.Treeview.Heading", font=("Microsoft YaHei", 10, "bold"), foreground="#1a1a1a")
        style.configure("LeftAligned.Treeview", font=("Microsoft YaHei", 9), rowheight=28, background="#ffffff", foreground="#2c3e50", fieldbackground="#ffffff")
        tree.configure(style="LeftAligned.Treeview")

        for col in columns:
            tree.heading(col, text=col, anchor="w")
            tree.column(col, anchor="w", stretch=True)

        tree.column("ID", width=60, minwidth=50)
        tree.column("File Path", width=500, minwidth=300)
        tree.column("Points", width=100, minwidth=80)
        tree.column("Format", width=100, minwidth=80)
        tree.column("Frequency Range", width=240, minwidth=180)

        # --- 滚动条配置和布局 (在隐藏的 Frame 内部进行 Grid 布局) ---
        v_scrollbar = ttk.Scrollbar(self.summary_content_frame, orient="vertical", command=tree.yview)
        h_scrollbar = ttk.Scrollbar(self.summary_content_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        tree.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")

        self.summary_content_frame.grid_rowconfigure(0, weight=1)
        self.summary_content_frame.grid_columnconfigure(0, weight=1)

        # --- 数据插入 (保留) ---
        for dataset in self.datasets:
            data_id = dataset['id']
            name = dataset['name']
            points = dataset['points']
            s_format = dataset['format']
            freq = dataset['freq']
            min_f = freq.min()
            max_f = freq.max()
            
            def format_freq(f_hz):
                if f_hz >= 1e9: return f"{f_hz / 1e9:.3f} GHz"
                elif f_hz >= 1e6: return f"{f_hz / 1e6:.3f} MHz"
                elif f_hz >= 1e3: return f"{f_hz / 1e3:.3f} KHz"
                else: return f"{f_hz:.3f} Hz"
                    
            freq_range_str = f"{format_freq(min_f)} to {format_freq(max_f)}"
            tree.insert("", "end", values=(str(data_id), name, str(points), s_format, freq_range_str))
            
        # --- 事件绑定 (保留) ---
        def on_treeview_motion(event):
            item = tree.identify_row(event.y)
            if item:
                col = tree.identify_column(event.x)
                if col == "#2":
                    value = tree.item(item, "values")[1]
                    # 假设 self.status_var 是状态栏变量
                    if hasattr(self, 'status_var'):
                        self.status_var.set(f"Full Path: {value}")
                else:
                    if hasattr(self, 'status_var'):
                        self.status_var.set("Loaded File Information")
            else:
                if hasattr(self, 'status_var'):
                    self.status_var.set("Loaded File Information")
                
        tree.bind("<Motion>", on_treeview_motion)
        self.summary_content_frame.update_idletasks()
    #------------------------------------------------    


if __name__ == '__main__':
    root = tk.Tk()

    if check_license(root):
        
        app = SViewGUI(root)

        app.setup_ui()
        app.plot_type.trace_add("write", app.on_plot_type_change)
        app.display_mode.trace_add("write", app.on_display_mode_change)
        
        root.mainloop()