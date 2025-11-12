# -*- coding: utf-8 -*-
"""
S-View - Integrates 'Display Mode' with Normal / Max modes.
Author: Arthur Gu
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, scrolledtext # 新增 simpledialog, scrolledtext
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.ticker import MaxNLocator, MultipleLocator, AutoMinorLocator
import os
import re
import sys # 确保导入 sys
import platform
import matplotlib.font_manager as fm
import warnings
from PIL import Image
import io
# FIX 1: 导入 collections 模块
import matplotlib.collections as mcollections 
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

CHINESE_FONT = get_chinese_font()
plt.rcParams['font.sans-serif'] = [CHINESE_FONT]
plt.rcParams['axes.unicode_minus'] = False

# 颜色循环
#颜色信息1: [#1f77b4 (深蓝色), #7030a0 (紫色), #2ca02c (绿色), #7f7f7f (灰色), #e377c2 (粉红色), #d62728 (红色), #002060 (海军蓝), #9467bd (淡紫色)]
#颜色信息2: [#8c564b (棕色), #bcbd22 (黄绿色), #17becf (青色), #00b0f0 (亮蓝色), #375623 (深橄榄绿), #ffc000 (金色), #ff7f0e (橙色), #44546a (深青灰色)]
COLOR_CYCLE = ['#1f77b4', '#7030a0', '#2ca02c', '#7f7f7f', '#e377c2', '#d62728', '#002060', '#9467bd', '#8c564b', '#bcbd22', '#17becf', '#00b0f0', '#375623', '#ffc000', '#ff7f0e', '#44546a']


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
        self.root.title("S-View Created By Arthur Gu | V2.46.11")
        self.root.geometry("1450x980")
        self.root.resizable(True, True)
        self.root.minsize(1150, 780)
        self.root.configure(bg="#f0f2f5")

        self.params = ["S11", "S21", "S12", "S22"]
        # S 参数显示状态变量 (默认全部显示)
        self.show_param_vars = {p: tk.BooleanVar(value=True) for p in self.params}
        # 允许 Center
        self.MARKER_POSITIONS = ["Top Left", "Top Right", "Bottom Left", "Bottom Right", "Center", "Custom"] 
        self.plot_configs = {}
        self.limit_tabs = {}

        # --- 新增：拖拽平移状态追踪 ---
        self.pan_drag_active = False
        self.pan_start_x = None
        self.pan_start_y = None
        self.left_button_pressed = False
        self.right_button_pressed = False
        self.pan_ax = None
        self.pan_param = None
        
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

        # 创建 UI
        # 假设这里有一个 self.setup_ui() 方法
        # self.setup_ui()
        # self.plot_type.trace("w", self.on_plot_type_change)
        # self.display_mode.trace("w", self.on_display_mode_change)

    def _initialize_state(self):
        self.datasets = []
        self.next_dataset_id = 1
        self.current_img = None
        self.maximized_param = None

        self.title_var = tk.StringVar(value="SN-001")
        self.plot_type = tk.StringVar(value="Magnitude (dB)")
        self.display_mode = tk.StringVar(value="Normal") # 新增：Normal / Max

        SUPPORTED_PLOT_TYPES = ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"]
        
        # 新增：Marker 鼠标操作控制
        self.marker_click_enabled = tk.BooleanVar(value=False) # 默认设置为关闭
        
        # [新增功能] 新增：Disable Refresh 控制变量 (默认未勾选，即默认刷新功能是开启的)
        self.disable_refresh_var = tk.BooleanVar(value=False)

        # [新增功能] Limits Check 控制变量 (默认为关闭)
        self.limits_check_enabled = tk.BooleanVar(value=False) # <--- NEW: Limits Check
 
        # --- Marker Dragging State (NEW) ---
        self.dragging_marker_legend = False
        self.drag_start_point_axes = None # 拖动起始点的归一化坐标 (0-1)
        self.drag_ax = None # 正在拖动的 Axes 对象
        self.drag_x_var = None # 绑定的 Custom X 变量引用 (tk.StringVar)
        self.drag_y_var = None # 绑定的 Custom Y 变量引用 (tk.StringVar)
        self.drag_mode_var = None # 绑定的 Position Mode 变量引用 (tk.StringVar)
        self.drag_canvas = None # 正在拖动的 Canvas 对象
        # 【新增优化】用于拖动Marker性能优化的变量
        self._drag_update_id = None      # 存储 Tkinter.after 的 ID
        self.DRAG_UPDATE_INTERVAL = 40     # 更新间隔 (毫秒)。推荐 30-50ms
 
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
    # ----------------------------------------------------
    # Main execution block (文件最底部)
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
                
                # --- 检查违规 ---
                violation = False
                
                if ltype in ["Max", "Band", "Upper Only", "Upper/Lower", "Upper Limit"]:
                     if np.any(y_data_masked > upper):
                         violation = True

                if ltype in ["Min", "Band", "Lower Only", "Upper/Lower", "Lower Limit"]:
                     if np.any(y_data_masked < lower):
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
                line = f"{name} FAIL"
                is_fail_overall = True
                has_limit_check_results = True
            elif status == 'PASS':
                line = f"{name} PASS"
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
        #    由于 plot_combined 在开始时调用 ax.clear()，当跳过它时，
        #    我们必须手动移除 Marker Artists 以防止重叠。
        #    假设您将 Marker 和 Annotation Artists 存储在一个列表 self.max_marker_artists 中
        #    如果您的 Marker 绘制没有收集 Artists，您可能需要调整 plot_combined 中的绘制代码来收集它们。
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
             x_min_mhz, x_max_mhz = ax.get_xlim()
        except Exception:
             return
             
        y_unit = ""
        if plot_type == "Magnitude (dB)": y_unit = "dB"
        elif plot_type == "Phase (deg)": y_unit = "deg"
        elif plot_type == "Group Delay (ns)": y_unit = "ns"
        
        marker_info_list = []
        txt_artist = None

        # ----------------------------------------------------
        # 4. 重新执行 plot_combined 中的 Marker 绘制逻辑 (步骤 9)
        #    请从 plot_combined 中复制 Marker 绘制代码，并确保将绘制的 Artist 
        #    (ax.plot/ax.annotate 返回的对象) 添加到 self.max_marker_artists 列表中。
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
                              
                          val = self.safe_interp(target_freq_hz, freq, data_array)
                          if val is None:
                              continue
                              
                          x_pt_original = target_freq_hz / 1e6
                          y_pt = val
                          
                          x_pt_plot = max(x_min_mhz, min(x_max_mhz, x_pt_original))
                          
                          color = self.get_max_mode_color(dataset['id'], p)
                          custom_name = self.custom_id_names.get(selected_data_id, f"ID {selected_data_id}") 
                          
                          # Draw marker 
                          # FIX: 收集 Artists
                          marker_line = ax.plot(x_pt_plot, y_pt, '.', markerfacecolor='none', markeredgecolor=color, 
                                                markersize=4, markeredgewidth=2, zorder=5)
                          # FIX: 收集 Artists
                          marker_text = ax.annotate(mark['id'], xy=(x_pt_plot, y_pt), xytext=(5, 5),
                                                  textcoords='offset points', fontsize=9, color=color,
                                                  zorder=6)

                          # 收集 Marker 信息 
                          full_legend_text = f"{mark['id']} ({p} {custom_name}) @{x_display}, {val:.3f} {y_unit}"
                          marker_info_list.append((mark['id'], p, full_legend_text, selected_data_id))
                          
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

            txt_artist = ax.text(x_val, y_val, txt, transform=ax.transAxes, fontsize=9, 
                                 verticalalignment=v_align, horizontalalignment=h_align, 
                                 multialignment='left', 
                                 bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.9), zorder=7)
                                 
        # 6. 更新 Marker Artist 引用
        if not hasattr(self, 'max_marker_legend_artists'):
            self.max_marker_legend_artists = {} 
            
        self.max_marker_legend_artists[plot_type] = txt_artist

        # 7. 刷新画布
        self.max_canvas.draw()
 
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
                                      font=("sans-serif", 9, "bold"), bg="#f0f2f5") 
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
            
        # Chart ops
        chart_ops_group = tk.LabelFrame(control_stack_frame, text="Chart Output", font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        chart_ops_group.pack(fill="x", padx=5, pady=2)
        
        tk.Button(chart_ops_group, text="Copy Plots", font=("sans-serif", 10, "bold"),
                      bg="#FF5722", fg="white", relief="flat", anchor="w",
                      padx=left_margin, pady=6, command=self.copy_all_charts)\
                .pack(fill="x", padx=5, pady=2)

        tk.Button(chart_ops_group, text="Save as Image", font=("sans-serif", 10, "bold"),
                      bg="#9C27B0", fg="white", relief="flat", anchor="w",
                      padx=left_margin, pady=6, command=self.save_chart)\
                .pack(fill="x", padx=5, pady=2)

        # 新增：Marker Click Control Feature 控制组
        marker_control_group = tk.LabelFrame(control_stack_frame, text="Add Tag Control", 
                                                 font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        marker_control_group.pack(fill="x", padx=5, pady=2)
        
        inner_frame = tk.Frame(marker_control_group, bg="#f0f2f5")
        inner_frame.pack(anchor='w', padx=5, pady=2)  
        
        tk.Checkbutton(inner_frame,
                          text=" Enable ",
                          variable=self.marker_click_enabled,
                          bg="#f0f2f5",
                          anchor='w', 
                          justify='left').pack(anchor='w', padx=(5, 0), pady=0)  

        # [新增功能] Disable Refresh Feature关闭自动刷新控制组
        disable_refresh_group = tk.LabelFrame(control_stack_frame, text="Auto Refresh", 
                                                 font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        disable_refresh_group.pack(fill="x", padx=5, pady=2)

        inner_refresh_frame = tk.Frame(disable_refresh_group, bg="#f0f2f5")
        inner_refresh_frame.pack(anchor='w', padx=5, pady=2)  

        tk.Checkbutton(inner_refresh_frame,
                          text=" Disable ",
                          variable=self.disable_refresh_var,
                          bg="#f0f2f5",
                          anchor='w', 
                          justify='left').pack(anchor='w', padx=(5, 0), pady=0)  

        # [新增功能] Limits Check 控制组
        limits_check_group = tk.LabelFrame(control_stack_frame, text="Limits Check", 
                                                 font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        limits_check_group.pack(fill="x", padx=5, pady=2)  

        inner_limits_frame = tk.Frame(limits_check_group, bg="#f0f2f5")
        inner_limits_frame.pack(anchor='w', padx=5, pady=2)  

        tk.Checkbutton(inner_limits_frame,
                          text=" Enable ",
                          variable=self.limits_check_enabled,
                          bg="#f0f2f5",
                          anchor='w',
                          justify='left',
                          command=self.update_plots).pack(anchor='w', padx=(5, 0), pady=0)  

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
                     bg="#f0f2f5", fg="gray").pack(side="bottom", pady=10)

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
        x_frame = tk.LabelFrame(self.axis_control_tab, text="X Axis Control", font=("sans-serif", 11, "bold"), bg="#f0f2f5")
        x_frame.pack(fill="x", padx=15, pady=10)

        x_mode_var = self.axis_configs["x_mode"]

        # --- 1. 模式选择 Frame ---
        x_mode_frame = tk.Frame(x_frame, bg="#f0f2f5")
        x_mode_frame.pack(fill="x", padx=10, pady=(5, 0))

        tk.Label(x_mode_frame, text="Mode:", bg="#f0f2f5", 
                 font=("sans-serif", 9, "bold")).pack(side="left", padx=(0, 5))
        
        # X 轴模式选择：Default / Custom
        x_mode_combo = ttk.Combobox(x_mode_frame, textvariable=x_mode_var, 
                                     values=["Default", "Custom"], state="readonly", width=10)
        x_mode_combo.pack(side="left", padx=5)

        # --- 2. 自定义 X 轴 Start/Stop 输入框和 Apply 按钮 Frame ---
        custom_x_frame = tk.Frame(x_frame, bg="#f0f2f5")
        # 初始状态由回调函数控制

        # Start频率
        tk.Label(custom_x_frame, text="Start:", bg="#f0f2f5").pack(side="left", padx=(0, 5))
        tk.Entry(custom_x_frame, textvariable=self.axis_configs["x_start"], width=10).pack(side="left", padx=5)

        # Stop频率
        tk.Label(custom_x_frame, text="Stop:", bg="#f0f2f5").pack(side="left", padx=(20, 5))
        tk.Entry(custom_x_frame, textvariable=self.axis_configs["x_stop"], width=10).pack(side="left", padx=5)
        
        # 频率单位选择
        ttk.Combobox(custom_x_frame, textvariable=self.axis_configs["x_unit"], 
                     values=["MHz", "GHz"], state="readonly", width=6).pack(side="left", padx=5)
        
        # Apply Button (同步到绘图函数)
        tk.Button(custom_x_frame, text="Apply X Axis", font=("sans-serif", 9, "bold"),
                  command=self.update_plots).pack(side="left", padx=(20, 5))

        # --- 3. 动态显示/隐藏逻辑 ---
        def on_x_mode_change(*args):
            current_mode = x_mode_var.get()
            if current_mode == "Custom":
                custom_x_frame.pack(fill="x", padx=10, pady=(0, 10))
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
                                                font=("sans-serif", 11, "bold"), bg="#f0f2f5")
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
                                                    font=("sans-serif", 11, "bold"), bg="#f0f2f5")
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
                p_y_frame = tk.LabelFrame(pt_tab, text=f"{p} Y Limits", font=("sans-serif", 10, "bold"), bg="#f0f2f5")
                p_y_frame.pack(fill="x", padx=10, pady=5)

                # 获取该 S 参数的配置字典
                config = self.y_configs[pt][p]
                
                # --- 1. 模式选择 Frame (统一风格) ---
                mode_frame = tk.Frame(p_y_frame, bg="#f0f2f5")
                mode_frame.pack(fill="x", padx=10, pady=(5, 0))

                tk.Label(mode_frame, text=f"{p} Mode:", bg="#f0f2f5", 
                         font=("sans-serif", 9, "bold")).pack(side="left", padx=(0, 5))
                
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
                tk.Button(custom_y_frame, text="Apply Y Axis", font=("sans-serif", 9, "bold"),
                          command=self.update_plots).pack(side="left", padx=(20, 5))


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
        self.axis_configs["x_mode"].trace("w", self.on_axis_change)
        for pt in SUPPORTED_PLOT_TYPES:
            for p in self.params:
                # 注意：这里我们移除了对 mode 的重复绑定，因为我们已经在循环中使用了 trace_add
                # 但是为了兼容您原代码的 on_axis_change，如果它有其他用途，我们可以保留
                # 如果 on_axis_change 只用于触发 update_plots，则保留原代码：
                if pt in self.y_configs and p in self.y_configs[pt]:
                     self.y_configs[pt][p]["mode"].trace("w", self.on_axis_change)

        # 绑定变化事件
        self.axis_configs["x_mode"].trace("w", self.on_axis_change)
        for pt in SUPPORTED_PLOT_TYPES:
            for p in self.params:
                self.y_configs[pt][p]["mode"].trace("w", self.on_axis_change)

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
        mode_frame.pack(fill="x", padx=10, pady=(5, 0))

        tk.Label(mode_frame, text="Mode:", bg="#f0f2f5", 
                 font=("sans-serif", 9, "bold")).pack(side="left", padx=(0, 5))
        
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
        tk.Button(custom_y_frame, text="Apply Y Axis", font=("sans-serif", 9, "bold"),
                  command=self.update_plots).pack(side="left", padx=(20, 5))

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
        charts_frame = tk.Frame(self.chart_tab, bg="#f0f2f5")
        charts_frame.pack(fill="both", expand=True)
        self.charts_frame = charts_frame

        param_list = ["S11", "S21", "S12", "S22"]
        colors = {"S11": "#d32f2f", "S21": "#1976d2", "S12": "#7b1fa2", "S22": "#388e3c"}

        for i, param in enumerate(param_list):
            row = i // 2
            col = i % 2

            # --- Normal 模式：使用普通 Frame；Max 模式：使用 LabelFrame ---
            if self.display_mode.get() == "Normal":
                frame = tk.Frame(charts_frame, bg="#f0f2f5")
            else:
                frame = tk.LabelFrame(
                    charts_frame,
                    text=f" {param} ",
                    font=("sans-serif", 11, "bold"),
                    bg="#f0f2f5",
                    fg=colors[param]
                )

            frame.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

            # --- 创建图表 ---
            fig = plt.Figure(figsize=(5, 4), dpi=100)
            ax = fig.add_subplot(111)
            canvas = FigureCanvasTkAgg(fig, frame)
            canvas_widget = canvas.get_tk_widget()
            canvas_widget.pack(fill="both", expand=True)

            # --- 隐藏 Matplotlib 工具栏（Normal 模式下不显示） ---
            toolbar_frame = tk.Frame(frame)
            toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
            # toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)  # 如果需要工具栏可取消注释

            # --- 鼠标滚轮缩放（Normal 模式） ---
            canvas.mpl_connect(
                'scroll_event',
                lambda event, p=param: self.on_scroll_zoom_normal(event, p)
            )

            # --- 鼠标移动事件：实时更新 Normal 模式下的坐标显示 ---
            canvas.mpl_connect(
                'motion_notify_event',
                lambda event, p=param: self._on_mouse_move_cursor_normal(event)
            )
            
            # --- 【新增功能】: Dual-Button Pan Bindings (Normal Mode) ---
            canvas.mpl_connect(
                'button_press_event',
                lambda event, p=param: self.on_dual_button_pan_press(event, p)
            )
            canvas.mpl_connect(
                'button_release_event',
                self.on_dual_button_pan_release
            )
            canvas.mpl_connect(
                'motion_notify_event',
                self.on_dual_button_pan_motion
            )
            # ----------------------------------------------------

            # --- 保存绘图配置 ---
            self.plot_configs[param] = {
                "frame": frame,
                "fig": fig,
                "ax": ax,
                "canvas": canvas,
                "canvas_widget": canvas_widget,
                "toolbar_frame": toolbar_frame,
                "toolbar": toolbar
            }

        # --- 使四个子图等比例伸展 ---
        for i in range(2):
            charts_frame.grid_rowconfigure(i, weight=1)
            charts_frame.grid_columnconfigure(i, weight=1)

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
        # param_or_combined: can be 'COMBINED' or actual param name
        if event.inaxes and event.xdata is not None and event.ydata is not None:
            msg = self._format_coords(event.xdata, event.ydata)
            # choose toolbar message
            tb = None
            if param_or_combined == 'COMBINED':
                tb = self.max_toolbar
            elif param_or_combined in self.plot_configs:
                tb = self.plot_configs[param_or_combined]["toolbar"]
            if tb:
                try:
                    tb.set_message(msg)
                except:
                    pass
        else:
            # show default
            if param_or_combined == 'COMBINED' and self.max_toolbar:
                try:
                    if self.max_toolbar.mode == '':
                        self.max_toolbar.set_message("Zoom & Pan enabled (Combined)")
                except:
                    pass
            elif param_or_combined in self.plot_configs:
                try:
                    tb = self.plot_configs[param_or_combined]["toolbar"]
                    if tb.mode == '':
                        tb.set_message(f"Zoom & Pan enabled for {param_or_combined}")
                except:
                    pass

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
        在 Normal 模式下实时显示鼠标坐标。
        鼠标移动到任意子图区域内时，更新右下角的 Cursor Coordinates。
        """
        # 仅在 Normal 模式下启用
        if self.display_mode.get() != "Normal":
            return

        # 判断鼠标是否在坐标轴内
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
        """处理鼠标按下事件，用于启动组合键平移。"""
        self._update_mouse_button_state(mpl_event)

        # 1. 检查核心条件：Marker Click Feature 必须关闭
        if self.marker_click_enabled.get():
            return
        
        # 2. 检查组合键启动条件：左键或右键按下，且另一按键已按下，且在 Axes 区域内
        is_left_press_with_right_down = (mpl_event.button == 1 and self.right_button_pressed)
        is_right_press_with_left_down = (mpl_event.button == 3 and self.left_button_pressed)

        if (is_left_press_with_right_down or is_right_press_with_left_down) and mpl_event.inaxes:
            if self.pan_drag_active: # 避免重复启动
                return
            
            self.pan_drag_active = True
            
            # 存储起始位置和 Axes 引用
            self.pan_start_x = mpl_event.xdata
            self.pan_start_y = mpl_event.ydata
            self.pan_ax = mpl_event.inaxes
            self.pan_param = p if self.display_mode.get() == "Normal" else None
    
    def on_dual_button_pan_motion(self, mpl_event):
        """处理鼠标移动事件，执行 X/Y 轴的平移。"""
        if not self.pan_drag_active or not mpl_event.inaxes or mpl_event.inaxes != self.pan_ax:
            return

        # 再次检查条件：必须满足组合键和平移状态
        if not self.marker_click_enabled.get() and self.left_button_pressed and self.right_button_pressed:
            current_x = mpl_event.xdata
            current_y = mpl_event.ydata

            # 核心平移逻辑
            # 计算位移 (注意：平移方向与鼠标移动方向相反)
            dx = current_x - self.pan_start_x
            dy = current_y - self.pan_start_y
            
            # 获取并应用新的轴限制
            xlim = self.pan_ax.get_xlim()
            ylim = self.pan_ax.get_ylim()
            
            new_xlim = (xlim[0] - dx, xlim[1] - dx)
            new_ylim = (ylim[0] - dy, ylim[1] - dy)

            self.pan_ax.set_xlim(new_xlim)
            self.pan_ax.set_ylim(new_ylim)
            
            # 立即重绘
            self.pan_ax.figure.canvas.draw_idle()
        
    def on_dual_button_pan_release(self, mpl_event):
        """处理鼠标释放事件，停止平移。"""
        self._update_mouse_button_state(mpl_event)

        # 检查是否应该结束平移
        if self.pan_drag_active and not self.left_button_pressed and not self.right_button_pressed:
            self.pan_drag_active = False
            self.pan_ax = None
            self.pan_param = None
            if mpl_event.inaxes:
                 mpl_event.inaxes.figure.canvas.draw_idle()

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
        import tkinter as tk # 确保导入 tk
        import numpy as np   # 确保导入 np
        
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

    # Normal mode添加Marker信息
    def add_marker_on_click_normal(self, event, param):
        """
        在 Normal 模式下添加 Marker 的核心逻辑。
        """
        # 确保导入 tk
        import tkinter as tk # 确保导入 tk
        import numpy as np   # 确保导入 np
        
        if not self.marker_click_enabled.get(): # <--- 检查 Marker 点击功能是否开启
            return        
        # 确保点击事件有效且存在数据集
        if not event.inaxes or event.xdata is None or event.ydata is None or not self.datasets:
            return

        # 检查是否为左键点击 (button=1)
        if event.button != 1:
            return

        # 1. 获取点击坐标和当前绘图类型
        plot_type = self.plot_type.get()
        x_click_mhz = event.xdata
        x_click_hz = x_click_mhz * 1e6
        y_click_value = event.ydata

        # 2. 寻找最接近点击位置的 Dataset ID 
        # ----------------------------------------------------
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
                    data_array, _ = self.calculate_group_delay(freq, s_data)
                except:
                    continue 

            if data_array is not None and len(freq) > 1:
                # 使用 safe_interp 进行插值
                y_interpolated = self.safe_interp(x_click_hz, freq, data_array)
                
                if y_interpolated is not None:
                    # 计算 Y 轴差值
                    y_diff = abs(y_click_value - y_interpolated)
                    
                    if y_diff < min_y_diff:
                        min_y_diff = y_diff
                        closest_data_id = str(data_id) 

        # ----------------------------------------------------
        
        # 3. 确定用于 Marker 的 Data ID
        if closest_data_id is None:
            data_id_options = [str(d['id']) for d in self.datasets]
            target_data_id = data_id_options[0] if data_id_options else "1"
            self.status_var.set(f"Warning: Marker defaulted to Data ID {target_data_id} (No curves found or click outside valid range).")
        else:
            target_data_id = closest_data_id

        # 4. 确定频率显示格式
        if x_click_hz >= 3e9:
            f_val = x_click_hz / 1e9
            f_unit = "GHz"
        else:
            f_val = x_click_hz / 1e6
            f_unit = "MHz"

        # 5. 创建 Marker 对象并添加
        
        # 【修复 TEMP ID Bug】：计算下一个 ID
        # 确保数据结构存在
        if plot_type not in self.data:
            self.data[plot_type] = {"marks": {}}
        if "marks" not in self.data[plot_type]:
            self.data[plot_type]["marks"] = {}
        if param not in self.data[plot_type]["marks"]:
            self.data[plot_type]["marks"][param] = []
            
        current_marks = self.data[plot_type]["marks"][param]
        next_id_number = len(current_marks) + 1
        mark_id = f"M{next_id_number}"
        
        new_mark = {
            "id": mark_id, # <-- FIX: 使用计算出的 ID
            "freq": tk.StringVar(value=f"{f_val:g}"),
            "unit": tk.StringVar(value=f_unit),
            "data_id": tk.StringVar(value=target_data_id),
            # 【核心修复】：添加缺失的 'display_status' 键，防止 KeyError 
            "display_status": tk.StringVar(value="Display")
        }
        
        self.data[plot_type]["marks"][param].append(new_mark)

        # 6. 刷新 UI
        # _reindex_markers_and_refresh_ui 负责删除和重新创建 Marker UI 框架
        self._reindex_markers_and_refresh_ui(plot_type, param)
        
        # [修改后的核心逻辑] 检查 'Disable Refresh Feature' 状态
        if not self.disable_refresh_var.get():
            # 允许刷新：执行完整刷新 (可能重置 Limits)
            self.update_plots()
            # 状态栏使用已修正的 ID
            self.status_var.set(f"Marker {mark_id} added at {f_val:g} {f_unit} for {param} on Data ID {target_data_id}.")
        else:
            # 【FIX Bug 1: Normal模式下禁用自动刷新无法添加Marker】
            # 关闭刷新：执行安全刷新，确保 Marker 显示，但不重置 Limits。
            # 替换 self.plot_normal(param)
            try:
                self._safe_refresh_markers(reset_limits=False)
                self.status_var.set(f"Marker {mark_id} added at {f_val:g} {f_unit} for {param} on Data ID {target_data_id}. Zoom state preserved.")
            except Exception as e:
                self.status_var.set(f"Marker added, but manual update failed: {e}. Zoom state preserved.")
                        
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
        处理鼠标左键按下事件：
        1. 检查是否点击了 Marker Legend (Normal 或 Max Mode)。
        2. 如果是，则启动 Marker 拖动并初始化偏移量（修复 AttributeError）。
        3. 如果未命中 Marker，强制清除 Matplotlib Pan 状态。
        """
        # 仅处理左键按下和有效 Axes
        if mpl_event.button != 1 or not mpl_event.inaxes:
            return

        # 【新功能保护】：如果平移拖拽功能已激活，则退出 Marker Legend 拖拽
        if self.pan_drag_active:
            return

        # 【BUG 修复 v2.42.5】：仅当 marker_click_enabled 为 False 时，才允许拖动 Marker Legend。
        if self.marker_click_enabled.get():
            return

        is_max_mode = (self.display_mode.get() == "Max")
        plot_type = self.plot_type.get()
        hit_artist = None
        hit_pos_config = None
        
        # 将显示坐标转换为归一化的 Axes 坐标 (0-1)
        current_click_axes = mpl_event.inaxes.transAxes.inverted().transform((mpl_event.x, mpl_event.y))

        # --- 1. Marker 命中检测 ---

        # 1.1. Max Mode 命中检测（增强检测）
        if is_max_mode:
            artist = self.max_marker_legend_artists.get(plot_type)
            is_hit = False
            
            if artist:
                try:
                    extent = artist.get_window_extent()
                    if extent.contains(mpl_event.x, mpl_event.y):
                        is_hit = True
                except AttributeError:
                    if artist.contains(mpl_event)[0]:
                        is_hit = True
            
            if is_hit:
                hit_artist = artist
                hit_pos_config = self.max_marker_pos_configs[plot_type]
                self.drag_ax = self.max_ax
                self.drag_canvas = self.max_canvas
        
        # 1.2. Normal Mode 命中检测
        else: 
            for p, artist in self.normal_marker_legend_artists.items():
                if artist and artist.contains(mpl_event)[0] and artist.axes == mpl_event.inaxes:
                    hit_artist = artist
                    hit_pos_config = self.marker_pos_configs[plot_type][p]
                    self.drag_ax = mpl_event.inaxes
                    self.drag_canvas = self.plot_configs[p]["canvas"]
                    break 
        
        # --- 2. 如果命中，启动拖动并强制退出 ---
        if hit_artist:
            self.dragging_marker_legend = True
            
            # 存储拖动参数
            self.drag_start_point_axes = current_click_axes
            self.drag_x_var = hit_pos_config["x_var"]
            self.drag_y_var = hit_pos_config["y_var"]
            self.drag_mode_var = hit_pos_config["mode_var"]

            # 【核心修复 1】计算并存储拖动偏移量（修复 AttributeError）
            try:
                # Marker 当前的归一化位置 (从 Tkinter 变量获取)
                marker_x_norm = float(self.drag_x_var.get())
                marker_y_norm = float(self.drag_y_var.get())
                
                # 鼠标点击位置 (归一化)
                click_x_norm = current_click_axes[0]
                click_y_norm = current_click_axes[1]
                
                # 计算偏移量 (Marker 位置 - 鼠标点击位置)
                # 这样在 motion 中，用新的鼠标位置 + 偏移量，就能准确找到 Marker 的新起始点。
                self.drag_offset_x = marker_x_norm - click_x_norm
                self.drag_offset_y = marker_y_norm - click_y_norm
            except Exception as e:
                # 容错处理，如果获取 Tkinter 变量失败，设置偏移量为 0，防止崩溃
                self.drag_offset_x = 0.0
                self.drag_offset_y = 0.0
                print(f"Error calculating drag offset: {e}") 
            
            # 强制将模式切换到 "Custom"
            self.drag_mode_var.set("Custom")
                
            self.status_var.set(f"Marker Legend drag started.")
            
            # 确保 Max Toolbar 的 Pan/Zoom 模式被强制释放 (防止冲突残留)
            if is_max_mode and self.max_toolbar:
                self.max_toolbar.release_pan(mpl_event)
                self.max_toolbar.release_zoom(mpl_event)
                self.max_toolbar._active = None 

            return 
        
        # --- 3. 如果未命中且处于 Max Mode，强制清除激活状态 (Bug 2 修复) ---
        if is_max_mode and self.max_toolbar:
            if self.max_toolbar._active:
                self.max_toolbar._active = None
                self.max_toolbar.canvas.set_cursor(0) 
                
        return

    #鼠标Marker拖拽
    def on_marker_legend_motion(self, mpl_event):
        """
        处理鼠标移动事件，更新 Marker Legend 的归一化坐标。
        【优化】：使用 Tkinter.after 限制 update_plots 的调用频率，实现拖动流畅。
        """
        if not self.dragging_marker_legend or mpl_event.canvas != self.drag_canvas:
            return
        
        # 确保鼠标在 Axes 内且有有效坐标
        if mpl_event.inaxes is None or mpl_event.x is None or mpl_event.y is None:
            return 
            
        # 1. 计算新的归一化坐标
        current_point_axes = mpl_event.inaxes.transAxes.inverted().transform((mpl_event.x, mpl_event.y))
        
        # 安全检查 drag_offset_x/y 是否存在
        if self.drag_offset_x is None or self.drag_offset_y is None:
            return 

        x_new = current_point_axes[0] + self.drag_offset_x
        y_new = current_point_axes[1] + self.drag_offset_y

        # 钳位归一化坐标 (0.0 到 1.0)
        x_new = max(0.0, min(1.0, x_new))
        y_new = max(0.0, min(1.0, y_new))

        # 2. 立即更新 Tkinter 变量 (数据更新)
        self.drag_x_var.set(f"{x_new:.4f}")
        self.drag_y_var.set(f"{y_new:.4f}")
        
        # 3. 【核心优化】使用 Tkinter after 限制 update_plots 的调用频率
        # 每次移动时，如果已有 pending update，则取消它
        if self._drag_update_id:
            self.root.after_cancel(self._drag_update_id)
            
        # 延迟 DRAG_UPDATE_INTERVAL 毫秒后调用 _throttled_update_plots
        # 这就是节流的关键，它确保在短时间内只执行一次重绘。
        self._drag_update_id = self.root.after(
            self.DRAG_UPDATE_INTERVAL, 
            self._throttled_update_plots
        )

    # Marker拖拽的辅助函数
    def _throttled_update_plots(self):
        """辅助函数，用于在拖动时节流地调用 update_plots，并清除 ID。"""
        # 清除 pending ID，表示更新已执行
        self._drag_update_id = None 
        # 调用完整的重绘逻辑
        self.update_plots()
        
        # 更新状态栏以提供反馈
        if self.dragging_marker_legend:
            self.status_var.set(f"Marker Legend dragging: ({self.drag_x_var.get()}, {self.drag_y_var.get()})")

    #Marker拖拽释放
    def on_marker_legend_release(self, mpl_event):
        """处理鼠标左键释放事件，停止拖动 Marker Legend。"""
        
        # 1. 检查和处理 Marker Legend 拖动结束
        if self.dragging_marker_legend:
            
            # 【新增优化】取消任何待处理的节流更新
            if self._drag_update_id:
                self.root.after_cancel(self._drag_update_id)
                self._drag_update_id = None
            
            # 标记拖动状态结束 (Bug 1 修复关键点)
            self.dragging_marker_legend = False
            
            # 清除所有拖动相关的临时引用
            self.drag_start_point_axes = None
            self.drag_ax = None
            self.drag_x_var = None
            self.drag_y_var = None
            self.drag_mode_var = None
            
            # 清除拖动偏移量。
            self.drag_offset_x = None
            self.drag_offset_y = None
            
            # 强制确保 Max Toolbar 的 Pan/Zoom 模式被强制释放 (防止冲突残留)
            if self.display_mode.get() == "Max" and self.max_toolbar:
                self.max_toolbar.release_pan(mpl_event)
                self.max_toolbar._active = None 
                
            self.status_var.set("Marker Legend drag finished. Position updated.")
            
            # 确保最终位置被可靠绘制
            if self.drag_canvas:
                self.drag_canvas = None 
            
            self.update_plots() # 立即执行最终位置的重绘
            return
            
        # 2. 如果不是 Marker 拖动，但 Max Mode 的 Matplotlib Pan 处于活动状态（二次保险）
        if self.display_mode.get() == "Max" and self.max_toolbar:
            if self.max_toolbar._active:
                self.max_toolbar.release_pan(mpl_event)
                self.max_toolbar._active = None

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
    def delete_marker_on_right_click(self, mpl_event, param=None):
        """处理鼠标右键点击事件，删除最近的 Marker，支持 Y 轴容忍度的模式和自动调整。"""
        
        # 检查是否为右键点击 (button=3) 且在坐标轴内
        if not self.marker_click_enabled.get(): # <--- 检查 Marker 点击功能是否开启
            return
        if mpl_event.inaxes is None or mpl_event.button != 3 or mpl_event.xdata is None or mpl_event.ydata is None:
            return
            
        if not self.datasets:
            self.status_var.set("No dataset loaded.")
            return

        click_mhz = mpl_event.xdata
        click_value = mpl_event.ydata # 获取点击的 Y 坐标 (值)
        plot_type = self.plot_type.get()

        # 确定要检查的参数(Max模式检查所有可见参数，Normal模式检查当前参数)
        if param:
            params_to_check = [param]
        else: # Max/Combined Mode
            params_to_check = [p for p in self.params if self.show_param_vars[p].get()]
            
        hit_marker = None
        hit_param = None
            
        # --- Marker X 轴 (频率) 点击容忍度优化 (保持原有逻辑) ---
        TOLERANCE_MULTIPLIER = 10.0
        MIN_ABSOLUTE_TOLERANCE_MHZ = 0.5
            
        # 确保数据集不为空且频率点大于 1
        if self.datasets and len(self.datasets[0]['freq']) > 1:
            # 查找数据集中最小的频率分辨率
            min_delta_hz = np.min([np.min(np.diff(d['freq'])) for d in self.datasets if len(d['freq']) > 1])
            data_resolution_tolerance_mhz = (min_delta_hz / 1e6) * TOLERANCE_MULTIPLIER
            tolerance_mhz = max(data_resolution_tolerance_mhz, MIN_ABSOLUTE_TOLERANCE_MHZ)
        else:
            tolerance_mhz = MIN_ABSOLUTE_TOLERANCE_MHZ
        # --- X 轴容忍度定义结束 ---

        # --- Marker Y 轴 (值) 点击容忍度优化 (根据 plot_type 和 Y 轴范围自适应) ---
        
        # 1. 定义不同模式下的基础 Y 轴容忍度 (绝对值)
        if plot_type == "Magnitude (dB)":
            Y_TOLERANCE_BASE = 0.5   # dB
        elif plot_type == "Phase (deg)":
            Y_TOLERANCE_BASE = 15.0  # 度 (相位变化快，容忍度可以大一点)
        elif plot_type == "Group Delay (ns)":
            Y_TOLERANCE_BASE = 5.0  # ns (群延迟变化剧烈，可能需要更大的容忍度)
        else:
            Y_TOLERANCE_BASE = 1.0   # 默认值
            
        # 2. 根据 Y 轴显示范围进行自适应调整 (自适应容忍度)
        # 假设 self.ax 是绘图的 Matplotlib Axes 对象
        try:
            y_min, y_max = mpl_event.inaxes.get_ylim() # 从点击事件所在的坐标轴获取范围
            y_range = y_max - y_min
            
            # 设定一个百分比容忍度 (例如：Y 轴总范围的 0.5%)
            # 避免在范围非常小时百分比容忍度太小，设置一个最小值
            PERCENTAGE_TOLERANCE_FACTOR = 0.005 # 0.5% of Y range
            
            y_auto_tolerance = y_range * PERCENTAGE_TOLERANCE_FACTOR
            
            # 最终 Y 轴容忍度：取基础容忍度和自动计算容忍度中的最大值
            tolerance_value = max(Y_TOLERANCE_BASE, y_auto_tolerance)
            
        except Exception:
            # 如果无法获取 Y 轴范围 (例如，在某些非标准情况下)，则回退到基础容忍度
            tolerance_value = Y_TOLERANCE_BASE

        # --- Y 轴容忍度定义结束 ---

        # 在所有相关的参数列表中查找命中的 Marker
        for p in params_to_check:
            marks_list = self.data[plot_type]["marks"].get(p, [])
            for mark in marks_list:
                marker_freq_hz = self._get_marker_freq_hz(mark)
                marker_freq_mhz = marker_freq_hz / 1e6
                
                # 1. 检查 X 坐标 (频率) 容忍度
                if abs(click_mhz - marker_freq_mhz) <= tolerance_mhz:
                    
                    # 2. 计算 Marker 的 Y 坐标 (值) 使用插值 (保持原有逻辑)
                    marker_value = None
                    try:
                        # ... (Marker Y 值计算逻辑保持不变，确保它能计算出 marker_value) ...
                        # 简化：假设下面的 try/except 块成功计算出 marker_value
                        selected_data_id = int(mark["data_id"].get())
                        dataset = next((d for d in self.datasets if d['id'] == selected_data_id), None)
                        if dataset:
                            freq = dataset['freq']
                            s_data = dataset['s_data'][p.lower()]
                            
                            # 计算 data_array based on plot_type
                            if plot_type == "Magnitude (dB)":
                                data_array = 20 * np.log10(np.abs(s_data) + 1e-20)
                            elif plot_type == "Phase (deg)":
                                data_array = np.unwrap(np.angle(s_data)) * 180 / np.pi
                            elif plot_type == "Group Delay (ns)":
                                # 确保 self.calculate_group_delay 存在
                                # 需要检查 self.calculate_group_delay 的返回值结构
                                data_array, _ = self.calculate_group_delay(freq, s_data)
                            else:
                                continue
                                
                            # 使用安全插值
                            marker_value = self.safe_interp(marker_freq_hz, freq, data_array)
                    except Exception:
                        marker_value = None
                        
                    # 3. 检查 Y 轴点击是否在容忍范围内
                    is_hit = False
                    if marker_value is not None:
                        # 使用动态容忍度 tolerance_value
                        if isinstance(marker_value, (int, float)) and abs(click_value - marker_value) <= tolerance_value:
                            is_hit = True
                    else:
                        # 容错处理：如果无法计算精确的 Y 值，则回退到只检查 X 轴
                        is_hit = True

                    if is_hit:
                        # X 和 Y (或容错处理后) 都命中
                        hit_marker = mark
                        hit_param = p
                        break # 退出 inner loop (marks_list)

            if hit_marker:
                break # 退出 outer loop (params_to_check)

        # 执行删除和刷新 (后续逻辑保持不变)
        if hit_marker:
            marker_id = hit_marker.get('id', 'Unknown')
            
            # 从列表中删除 Marker
            self.data[plot_type]["marks"][hit_param].remove(hit_marker)
            
            # 重新编号并刷新 UI
            self._reindex_markers_and_refresh_ui(plot_type, hit_param)
            
            # [核心修改] 检查 'Disable Refresh Feature' 状态并调用安全刷新函数
            if not self.disable_refresh_var.get():
                # 允许刷新：执行完整刷新
                self.update_plots()
                self.status_var.set(f"Marker {marker_id} deleted on {hit_param}.")
            else:
                # 关闭刷新：执行安全刷新 (保持 Limits)
                self._safe_refresh_markers(reset_limits=False)
                self.status_var.set(f"Marker {marker_id} deleted on {hit_param}. Zoom state preserved.")

        elif mpl_event.inaxes is not None:
              # 如果点击在图上但未命中 Marker，显示提示
            self.status_var.set(f"Right-click: No marker found near {click_mhz:.3f} MHz to delete.")
    
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
        mode = self.display_mode.get()
        
        # 控制 Legend (Data ID) 的显示/隐藏
        if hasattr(self, "legend_frame"):
            if mode == "Max":
                # Max 模式: 隐藏 Legend 边框
                self.legend_frame.pack_forget()
            else:
                # Normal 模式: 显示 Legend 边框
                self.legend_frame.pack(fill="x", padx=5, pady=(5, 0), side="bottom") 

        # 控制 Cursor Coordinates 显示（两种模式都显示，并确保在底部）
        if hasattr(self, "cursor_frame"):
            # 两种模式下 pack 行为相同，简化处理
            self.cursor_frame.pack(fill="x", padx=5, pady=(5, 0), side="bottom")

        # 动态显示或隐藏 Show Params 复选框区域 (cb_frame)
        # [修改点1] 在 Normal 模式下也显示 'Show Params' 选项 (cb_frame)，满足用户要求。
        if hasattr(self, "cb_frame"):
            # 在两种模式下都显示
            self.cb_frame.pack(fill="x", padx=5, pady=(2, 8))

        # 动态显示或隐藏 Show Params 复选框区域
        #if hasattr(self, "cb_frame"):
        #    if mode == "Max":
        #        self.cb_frame.pack(fill="x", padx=5, pady=(2, 8))
        #    else:
        #        self.cb_frame.pack_forget()

        # 更新 Marker 控件可见性
        self.update_marker_controls_visibility()

        # === 核心逻辑：切换显示模式和 Y 轴控制界面 ===
        if mode == "Max":
            # 切换到 Max 模式
            
            # Y 轴控制切换：隐藏四个独立的 Y 轴控制，显示统一控制
            if hasattr(self, 'normal_y_control_frame'):
                self.normal_y_control_frame.pack_forget() 
            if hasattr(self, 'unified_y_control_frame'):
                self.unified_y_control_frame.pack(fill="both", expand=True)

            self.enter_max_mode()
        else:
            # 切换到 Normal 模式
            
            # Y 轴控制切换：隐藏统一控制，恢复四个独立的 Y 轴控制
            if hasattr(self, 'unified_y_control_frame'):
                self.unified_y_control_frame.pack_forget()
            if hasattr(self, 'normal_y_control_frame'):
                 self.normal_y_control_frame.pack(fill="both", expand=True)

            self.exit_max_mode()
            
        self.update_plots()

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

    def enter_max_mode(self):
        # Hide individual param frames, create combined frame if not exists
        for p, cfg in self.plot_configs.items():
            cfg["frame"].grid_forget()

        # Create combined frame if not exists
        if not self.max_frame:
            # ... UI setup code (max_frame, max_fig, max_ax, max_canvas) ...
            self.max_frame = tk.LabelFrame(self.charts_frame, text=" Combined S-Parameters (Max) ", font=("sans-serif", 12, "bold"), bg="#f0f2f5")
            self.max_frame.grid(row=0, column=0, rowspan=2, columnspan=2, sticky="nsew", padx=8, pady=8)
            self.max_fig = plt.Figure(figsize=(10, 7), dpi=120)
            self.max_ax = self.max_fig.add_subplot(111)
            self.max_canvas = FigureCanvasTkAgg(self.max_fig, self.max_frame)
            self.max_canvas_widget = self.max_canvas.get_tk_widget()
            self.max_canvas_widget.pack(fill="both", expand=True)
            
            # toolbar setup
            toolbar_frame = tk.Frame(self.max_frame)
            # toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X) # 保持注释
            self.max_toolbar = NavigationToolbar2Tk(self.max_canvas, toolbar_frame)
            self.max_toolbar.update()
            
            # =========================================================
            # === 核心修复 2：创建后立即解除 Matplotlib 默认拖拽事件 ===
            # =========================================================
            if self.max_toolbar:
                self._disable_mpl_default_pan_zoom(self.max_toolbar)
            
            # =========================================================================
            # === 【Max 模式事件绑定】: 首次创建时，定义并统一存储所有 CIDs ===
            # =========================================================================
            
            # 1. 基础事件
            cid_click = self.max_fig.canvas.mpl_connect('button_press_event', lambda e: self.add_marker_on_click_combined(e))
            cid_rclick = self.max_fig.canvas.mpl_connect('button_press_event', lambda e: self.delete_marker_on_right_click(e))
            cid_scroll = self.max_fig.canvas.mpl_connect('scroll_event', lambda e: self.on_scroll_zoom_combined(e))
            cid_motion = self.max_fig.canvas.mpl_connect('motion_notify_event', lambda e: self._on_mouse_move_custom(e, 'COMBINED'))
            
            # 2. 【新增的 Dual-Button Pan 事件】: 必须先定义，再使用
            cid_pan_press = self.max_fig.canvas.mpl_connect('button_press_event', lambda e: self.on_dual_button_pan_press(e)) 
            cid_pan_release = self.max_fig.canvas.mpl_connect('button_release_event', self.on_dual_button_pan_release)
            cid_pan_motion = self.max_fig.canvas.mpl_connect('motion_notify_event', self.on_dual_button_pan_motion)
            
            # 3. 统一存储所有 CIDs (包括 Pan 事件)
            self.max_cids = {
                'click': cid_click, 
                'rclick': cid_rclick, 
                'scroll': cid_scroll, 
                'motion': cid_motion,
                'pan_press': cid_pan_press,    # 正确引用已定义的变量
                'pan_release': cid_pan_release,
                'pan_motion': cid_pan_motion
            }
            # =========================================================================
            
        else:
            # re-grid it
            self.max_frame.grid(row=0, column=0, rowspan=2, columnspan=2, sticky="nsew", padx=8, pady=8)
            
            # ... (Axes recreation logic) ...
            if self.max_fig and not self.max_fig.axes:
                self.max_ax = self.max_fig.add_subplot(111)
            elif self.max_fig and self.max_fig.axes:
                self.max_ax = self.max_fig.axes[0]
                
            # 【关键修复 3】：重新进入 Max 模式时，再次解除 Matplotlib 默认拖拽事件
            if self.max_toolbar:
                self._disable_mpl_default_pan_zoom(self.max_toolbar)
                
            # rebind events if needed (logic remains the same)
            # 仅在 self.max_cids 为空时才需要重新绑定
            if self.max_fig and not self.max_cids:
                # =========================================================================
                # === 【Max 模式事件绑定】: 重新进入时，重新定义并存储所有 CIDs ===
                # =========================================================================
                # 1. 基础事件
                cid_click = self.max_fig.canvas.mpl_connect('button_press_event', lambda e: self.add_marker_on_click_combined(e))
                cid_rclick = self.max_fig.canvas.mpl_connect('button_press_event', lambda e: self.delete_marker_on_right_click(e))
                cid_scroll = self.max_fig.canvas.mpl_connect('scroll_event', lambda e: self.on_scroll_zoom_combined(e))
                cid_motion = self.max_fig.canvas.mpl_connect('motion_notify_event', lambda e: self._on_mouse_move_custom(e, 'COMBINED'))
                
                # 2. 【新增的 Dual-Button Pan 事件】
                cid_pan_press = self.max_fig.canvas.mpl_connect('button_press_event', lambda e: self.on_dual_button_pan_press(e)) 
                cid_pan_release = self.max_fig.canvas.mpl_connect('button_release_event', self.on_dual_button_pan_release)
                cid_pan_motion = self.max_fig.canvas.mpl_connect('motion_notify_event', self.on_dual_button_pan_motion)
                
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
                # =========================================================================

        # =============================================================
        # === 核心修复：无论是新建还是重新进入，都调用管理函数初始化绑定 ===
        # =============================================================
        enable_drag = not self.marker_click_enabled.get()
        self._manage_max_mode_drag_bindings(enable_drag)
        
        self.charts_frame.update_idletasks()
        # --- Show Cursor Coordinates frame in Max mode ---
        self.cursor_frame.pack(fill="x", padx=5, pady=(5, 0), side="bottom")

        # 绑定鼠标移动事件 (使用一个单独的 CID，以便在 exit_max_mode 中断开)
        def _on_mouse_move_cursor(event):
            if event.inaxes:
                x, y = event.xdata, event.ydata
                self.cursor_content.config(text=f"X: {x:.3f}, Y: {y:.3f}") #调节X和Y轴的精确度
            else:
                self.cursor_content.config(text="X: ---, Y: ---")
        
        # 确保 motion 事件只被绑定一次。如果它已经在 max_cids['motion'] 中，这里不应该再次绑定。
        # 这里单独处理，并更新 self._cursor_move_cid 确保旧的被替换。
        
        # 移除旧的 _cursor_move_cid 绑定（如果有）
        if hasattr(self, "_cursor_move_cid") and self._cursor_move_cid is not None:
             self.max_canvas.mpl_disconnect(self._cursor_move_cid)
        
        # 重新绑定，使用 Max 模式专用的 max_canvas
        self._cursor_move_cid = self.max_canvas.mpl_connect("motion_notify_event", _on_mouse_move_cursor)

        self.max_mode_active = True
        self.update_plots()

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

    def restore_plots_layout(self):
        # Place each param frame back into 2x2 grid
        for i, (p, config) in enumerate(self.plot_configs.items()):
            row = i // 2
            col = i % 2
            config["frame"].grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            config["toolbar_frame"].pack_forget()
            config["canvas_widget"].pack(side=tk.TOP, fill="both", expand=True)
            # disconnect any per-plot custom cids
            # 确保 'cid_rclick' 和拖动相关的 CID 已被添加到断开连接的列表中
            for key in ('cid_click', 'cid_scroll', 'cid_mouse_move', 'cid_rclick', 'cid_drag_press', 'cid_drag_motion', 'cid_drag_release'): # <-- 增加拖动 CID
                if key in config:
                    try:
                        config["fig"].canvas.mpl_disconnect(config[key])
                    except:
                        pass
                    config.pop(key, None)
            
            # 重新绑定事件
            
            # --- Marker Dragging Bindings (NEW) ---
            # 仅在 Marker Click Feature 关闭 (默认) 时，绑定拖动事件
            if not self.marker_click_enabled.get():
                cid_press = config["fig"].canvas.mpl_connect('button_press_event', self.on_marker_legend_press)
                cid_motion = config["fig"].canvas.mpl_connect('motion_notify_event', self.on_marker_legend_motion)
                cid_release = config["fig"].canvas.mpl_connect('button_release_event', self.on_marker_legend_release)
                config['cid_drag_press'] = cid_press
                config['cid_drag_motion'] = cid_motion
                config['cid_drag_release'] = cid_release
            # -------------------------------------

            # 绑定左键点击添加 Marker 事件 (button=1)
            cid_click = config["fig"].canvas.mpl_connect('button_press_event', lambda e, pp=p: self.add_marker_on_click_normal(e, pp))
            config['cid_click'] = cid_click
            
            # 绑定右键点击删除 Marker 事件 (button=3)
            cid_rclick = config["fig"].canvas.mpl_connect('button_press_event', lambda e, pp=p: self.delete_marker_on_right_click(e, pp))
            config['cid_rclick'] = cid_rclick
            
            
        self.charts_frame.update_idletasks()
        self.max_mode_active = False
        self.update_plots()

    def get_max_mode_color(self, data_id, param):
        """ 为 Max 模式生成基于 ID 和 param 的独特颜色 """
        param_index = self.params.index(param)
        color_index = ((data_id - 1) * len(self.params) + param_index) % len(COLOR_CYCLE)
        return COLOR_CYCLE[color_index]

    # Max模式配置
    def plot_combined(self, redraw_full=True): 
        # 1. 绘图环境和数据检查
        if not self.max_ax or not self.max_canvas:
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
        
        x_min_mhz, x_max_mhz = None, None

        # 获取 Limit Check 全局开关状态
        try:
            is_limit_check_enabled = self.limits_check_enabled.get() 
        except AttributeError:
            is_limit_check_enabled = False 

        # 4. 绘制数据曲线 (Data Plotting Loop)
        visible_params = [p for p in self.params if self.show_param_vars[p].get()]
        
        for p in visible_params:
            # 获取该参数的所有 Limit Lines
            limit_lines = self.data.get(plot_type, {}).get("limit_lines", {}).get(p, [])
            
            for dataset in self.datasets:
                data_id = dataset['id']
                freq = dataset['freq']
                s = dataset['s_data'].get(p.lower())
                
                if s is None or len(s) == 0:
                    continue

                color = self.get_max_mode_color(data_id, p)
                freq_mhz = freq / 1e6
                
                # 统一的数据计算逻辑
                y_data = None
                if plot_type == "Magnitude (dB)":
                    y_data = 20 * np.log10(np.abs(s) + 1e-20)
                elif plot_type == "Phase (deg)":
                    y_data = np.unwrap(np.angle(s)) * 180 / np.pi
                elif plot_type == "Group Delay (ns)":
                    y_data, temp_freq_mhz = self.calculate_group_delay(freq, s)
                    if temp_freq_mhz is not None:
                        freq_mhz = temp_freq_mhz # 使用 Group Delay 计算后的频率数组
                
                if y_data is None:
                    continue 

                # 获取自定义 ID 名称
                custom_name = self.custom_id_names.get(str(data_id), f"ID {data_id}")
                
                # =========================================================
                # === 修复区域：PASS/FAIL 检查逻辑 (Max Mode Legend) ===
                # =========================================================
                pass_fail_suffix = "" # 默认后缀为空
                
                # 仅在全局开关打开且存在限制线配置时才进行检查
                if is_limit_check_enabled and limit_lines:
                    
                    # 调用统一的检查函数，它返回 (是否通过, 是否存在频率重叠)
                    is_pass, has_freq_overlap = self._check_dataset_limits(dataset, plot_type, p)
                    
                    if not has_freq_overlap:
                        # S参数显示Limit Line信息【核心修复】: 无频率重叠时，显示 N/A
                        pass_fail_suffix = "(N/A)"
                    elif is_pass:
                        pass_fail_suffix = " (PASS)"
                    else:
                        pass_fail_suffix = " (FAIL)"
                
                # 绘制曲线，标签格式: Sxx ID CustomName( 状态)
                label_text = f"{p} {custom_name}{pass_fail_suffix}"
                
                ax.plot(freq_mhz, y_data, color=color, linewidth=1.0, label=label_text)

                # 收集 Y 值和频率值用于后续自动缩放
                all_y_values.extend(y_data)
                all_freq_values.extend(freq_mhz)

        # 5. X/Y 轴标签、网格设置
        ax.set_xlabel("Frequency (MHz)")
        
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

        # 启用主网格线
        ax.grid(True, which='major', alpha=0.3)

        # 6. Y 轴自动/自定义范围和刻度优化 (Max Mode Unified Control)
        is_custom_y = False
        
        # === 修改开始：使用统一 Y 轴控制变量 ===
        unified_y_mode = self.axis_configs["unified_y_mode"].get()
        
        if unified_y_mode == "Custom":
            try:
                # 使用统一控制的 Min/Max 值
                y_min_custom = float(self.axis_configs["unified_y_min"].get())
                y_max_custom = float(self.axis_configs["unified_y_max"].get())
                ax.set_ylim(y_min_custom, y_max_custom)
                
                # 需要导入 MaxNLocator, MultipleLocator, AutoMinorLocator
                from matplotlib.ticker import MaxNLocator, MultipleLocator, AutoMinorLocator
                ax.yaxis.set_major_locator(MaxNLocator(12)) 
                is_custom_y = True
                
                # --- [新增] Y 轴细线网格配置 (Custom) ---
                ax.yaxis.set_minor_locator(AutoMinorLocator(2))
                ax.grid(True, which='minor', linestyle=':', linewidth=0.5, color='gray', alpha=0.5)
                # ----------------------------------------
            except ValueError:
                pass 
                
        # 如果不是自定义模式 (即 "Default") 或自定义值无效，则进行自动缩放
        if not is_custom_y and all_y_values:
            # 排除 NaN/Inf 值，防止自动缩放出错
            valid_y_values = np.array([v for v in all_y_values if np.isfinite(v)])
            if valid_y_values.size > 0:
                y_min_data = np.min(valid_y_values)
                y_max_data = np.max(valid_y_values)
            else:
                y_min_data, y_max_data = 0, 1 # 默认值
            
            y_min, y_max, y_step = self._calculate_friendly_y_limits(y_min_data, y_max_data)
            
            ax.set_ylim(y_min, y_max)
            # 需要导入 MultipleLocator, AutoMinorLocator
            from matplotlib.ticker import MultipleLocator, AutoMinorLocator
            ax.yaxis.set_major_locator(MultipleLocator(y_step))
            
            # --- [新增] Y 轴细线网格配置 (Auto) ---
            ax.yaxis.set_minor_locator(MultipleLocator(y_step / 2)) # 次刻度步长为主刻度的一半
            ax.grid(True, which='minor', linestyle=':', linewidth=0.5, color='gray', alpha=0.5)
            # --------------------------------------
        # === 修改结束：使用统一 Y 轴控制变量 ===

        # 7. X 轴刻度和自定义限制
        from matplotlib.ticker import MaxNLocator, AutoMinorLocator
        # 设置 X 轴主刻度定位器 (MaxNLocator(15))
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

        # --- [新增] X 轴细线网格配置 ---
        ax.xaxis.set_minor_locator(AutoMinorLocator(2))
        ax.grid(True, which='minor', linestyle=':', linewidth=0.5, color='gray', alpha=0.5)
        # -----------------------------

        # 8. Limit lines drawing for Combined Plot - 确保限制线始终绘制 (保持不变)
        if plot_type in self.data and self.datasets:
            for p in visible_params:
                for line in self.data[plot_type]["limit_lines"].get(p, []):
                    try:
                        start_val = float(line["start"].get())
                        start_unit = line["start_unit"].get()
                        stop_val = float(line["stop"].get())
                        stop_unit = line["stop_unit"].get()
                        start_mhz = start_val * 1000 if start_unit == "GHz" else start_val
                        stop_mhz = stop_val * 1000 if stop_unit == "GHz" else stop_val
                        lower = float(line["lower"].get())
                        upper = float(line["upper"].get())
                        ltype = line["type"].get()

                        # 确保绘制范围在当前 X 轴限制内
                        min_f_mhz = max(x_min_mhz, min(start_mhz, stop_mhz))
                        max_f_mhz = min(x_max_mhz, max(start_mhz, stop_mhz))

                        if min_f_mhz < max_f_mhz:
                            # 绘制上限 (已包含所有类型)
                            if ltype in ["Max", "Band", "Upper Only", "Upper/Lower", "Upper Limit"]:
                                ax.hlines(upper, min_f_mhz, max_f_mhz, colors='blue',
                                          linestyles='-', linewidth=1.0, zorder=4)
                            # 绘制下限（已包含所有类型，使用 if 确保并行绘制）
                            if ltype in ["Min", "Band", "Lower Only", "Upper/Lower", "Lower Limit"]: 
                                ax.hlines(lower, min_f_mhz, max_f_mhz, colors='blue',
                                          linestyles='-', linewidth=1.0, zorder=4)
                        
                    except Exception:
                        pass

        # 9. 绘制 Marker (保持不变)
        marker_info_list = []
        
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
                             
                         val = self.safe_interp(target_freq_hz, freq, data_array)
                         if val is None:
                             continue
                             
                         x_pt_original = target_freq_hz / 1e6
                         y_pt = val
                         
                         x_pt_plot = max(x_min_mhz, min(x_max_mhz, x_pt_original))
                         
                         color = self.get_max_mode_color(dataset['id'], p)
                         custom_name = self.custom_id_names.get(selected_data_id, f"ID {selected_data_id}") 
                         
                         # Draw marker 
                         marker_artist = ax.plot(x_pt_plot, y_pt, '.', markerfacecolor='none', markeredgecolor=color, 
                                                 markersize=4, markeredgewidth=2, zorder=5)
                         
                         # 注释
                         annotation_artist = ax.annotate(mark['id'], xy=(x_pt_plot, y_pt), xytext=(5, 5),
                                                         textcoords='offset points', fontsize=9, color=color,
                                                         zorder=6)
                         
                         # 收集 Marker Artists 用于后续的 _update_max_marker_display
                         if hasattr(self, 'max_marker_artists'):
                             self.max_marker_artists.extend(marker_artist)
                             self.max_marker_artists.append(annotation_artist)

                         # 收集 Marker 信息 
                         full_legend_text = f"{mark['id']} ({p} {custom_name}) @{x_display}, {val:.3f} {y_unit}"
                         marker_info_list.append((mark['id'], p, full_legend_text, selected_data_id))
                         
                     except Exception:
                         pass

        # 10. Matplotlib Legend for Data Lines 
        ax.legend(loc='best', fontsize=9, framealpha=0.7)
        
        # 11. Max Mode Marker Legend 排序和显示 (保持不变)
        txt_artist = None
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

            txt_artist = ax.text(x_val, y_val, txt, transform=ax.transAxes, fontsize=9, 
                                     verticalalignment=v_align, horizontalalignment=h_align, 
                                     multialignment='left', 
                                     bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.9), zorder=7)
                                     
            # 将 Marker Legend Text Artist 引用也收集起来，用于 _update_max_marker_display
            if hasattr(self, 'max_marker_artists'):
                self.max_marker_artists.append(txt_artist)

        # 12. 更新 Marker Artist 引用 (保持不变)
        if not hasattr(self, 'max_marker_legend_artists'):
            self.max_marker_legend_artists = {} 
            
        self.max_marker_legend_artists[plot_type] = txt_artist

        # 13. Figure 标题和布局 (保持不变)
        if self.max_fig:
            sn_text = f"{plot_title_info}"
            self.max_fig.text(0.5, 0.97, sn_text, fontsize=11, ha='center', va='top', fontweight='bold')
            self.max_fig.subplots_adjust(top=0.92, bottom=0.08, left=0.10, right=0.95)

        if redraw_full: # 根据需要决定是否重绘
            self.max_canvas.draw()
            
            
    # ---------- Plot / draw logic ----------
    def update_plots(self):
        self.status_var.set("Refreshing plots... Please wait")
        self.root.update_idletasks()

        # Update legend frame
        for widget in self.legend_content.winfo_children():
            widget.destroy()
        legend_items = {}
        if self.datasets:
            for dataset in self.datasets:
                data_id = dataset['id']
                color = COLOR_CYCLE[(data_id - 1) % len(COLOR_CYCLE)]
                file_name_only = os.path.basename(dataset['name'])
                display_name = self.custom_id_names.get(str(data_id), f"ID {data_id}")
                legend_items[data_id] = {'label': f"{display_name}: {file_name_only}", 'color': color}

        if legend_items:
            for data_id, item in legend_items.items():
                legend_row = tk.Frame(self.legend_content, bg="#f0f2f5")
                legend_row.pack(fill="x", pady=1)
                color_swatch = tk.Label(legend_row, bg=item['color'], width=2, height=1, relief="solid", bd=1)
                color_swatch.pack(side="left", padx=(5, 5))
                text_label = tk.Label(legend_row, text=item['label'], font=("sans-serif", 9), bg="#f0f2f5", anchor="w", fg="#333333")
                text_label.pack(side="left", fill="x", expand=True)

        if not self.datasets:
            # clear all axes
            for p in self.params:
                cfg = self.plot_configs[p]
                cfg["ax"].clear()
                cfg["ax"].set_title(p)
                cfg["ax"].text(0.5, 0.5, "No Data Loaded", transform=cfg["ax"].transAxes, ha='center', va='center', fontsize=12, color='gray')
                cfg["canvas"].draw()
            if self.max_ax:
                self.max_ax.clear()
                self.max_ax.text(0.5, 0.5, "No Data Loaded", transform=self.max_ax.transAxes, ha='center', va='center', fontsize=14, color='gray')
                if self.max_canvas:
                    self.max_canvas.draw()
            self.status_var.set("No data loaded. Please load S2P file(s).")
            return

        mode = self.display_mode.get()
        if mode == "Max":
            # plot combined
            self.plot_combined()
        else:
            # plot each param normally
            plot_type = self.plot_type.get()
            saved_xlim = saved_ylim = None
            if self.maximized_param:
                cfg = self.plot_configs[self.maximized_param]
                try:
                    saved_xlim = cfg["ax"].get_xlim()
                    saved_ylim = cfg["ax"].get_ylim()
                except:
                    pass
            for param in self.params:
                cfg = self.plot_configs[param]
                self.plot_parameter(cfg["ax"], cfg["fig"], cfg["canvas"], param, plot_type)
            if self.maximized_param and saved_xlim is not None and saved_ylim is not None:
                cfg = self.plot_configs[self.maximized_param]
                cfg["ax"].set_xlim(saved_xlim)
                cfg["ax"].set_ylim(saved_ylim)
            for p in self.params:
                self.plot_configs[p]["canvas"].draw()

        self.status_var.set(f"Plots refreshed: {len(self.datasets)} dataset(s), {self.plot_type.get()}")

    # Max模式配置
    def plot_combined(self, redraw_full=True): 
        # 1. 绘图环境和数据检查
        if not self.max_ax or not self.max_canvas:
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
        
        x_min_mhz, x_max_mhz = None, None

        # 获取 Limit Check 全局开关状态
        try:
            is_limit_check_enabled = self.limits_check_enabled.get() 
        except AttributeError:
            is_limit_check_enabled = False 
            
        # 确保 Matplotlib 导入
        from matplotlib.ticker import MaxNLocator, MultipleLocator, AutoMinorLocator


        # 4. 绘制数据曲线 (Data Plotting Loop)
        visible_params = [p for p in self.params if self.show_param_vars[p].get()]
        
        for p in visible_params:
            # 获取该参数的所有 Limit Lines
            limit_lines = self.data.get(plot_type, {}).get("limit_lines", {}).get(p, [])
            
            for dataset in self.datasets:
                data_id = dataset['id']
                freq = dataset['freq']
                s = dataset['s_data'].get(p.lower())
                
                if s is None or len(s) == 0:
                    continue

                color = self.get_max_mode_color(data_id, p)
                freq_mhz = freq / 1e6
                
                # 统一的数据计算逻辑
                y_data = None
                if plot_type == "Magnitude (dB)":
                    y_data = 20 * np.log10(np.abs(s) + 1e-20)
                elif plot_type == "Phase (deg)":
                    y_data = np.unwrap(np.angle(s)) * 180 / np.pi
                elif plot_type == "Group Delay (ns)":
                    y_data, temp_freq_mhz = self.calculate_group_delay(freq, s)
                    if temp_freq_mhz is not None:
                        freq_mhz = temp_freq_mhz # 使用 Group Delay 计算后的频率数组
                
                if y_data is None:
                    continue 

                # 获取自定义 ID 名称
                custom_name = self.custom_id_names.get(str(data_id), f"ID {data_id}")
                
                # =========================================================
                # === PASS/FAIL 检查逻辑 (Max Mode Legend) ===
                # =========================================================
                pass_fail_suffix = "" # 默认后缀为空
                
                if is_limit_check_enabled and limit_lines:
                    
                    is_pass, has_freq_overlap = self._check_dataset_limits(dataset, plot_type, p)
                    
                    if not has_freq_overlap:
                        pass_fail_suffix = "(N/A)"
                    elif is_pass:
                        pass_fail_suffix = " (PASS)"
                    else:
                        pass_fail_suffix = " (FAIL)"
                
                # 绘制曲线，标签格式: Sxx ID CustomName( 状态)
                label_text = f"{p} {custom_name}{pass_fail_suffix}"
                
                ax.plot(freq_mhz, y_data, color=color, linewidth=1.0, label=label_text)

                # 收集 Y 值和频率值用于后续自动缩放
                all_y_values.extend(y_data)
                all_freq_values.extend(freq_mhz)

        # 5. X/Y 轴标签、网格设置
        ax.set_xlabel("Frequency (MHz)")
        
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

        # 启用主网格线
        ax.grid(True, which='major', alpha=0.3)

        # 6. Y 轴自动/自定义范围和刻度优化 (Max Mode Unified Control)
        is_custom_y = False
        
        unified_y_mode = self.axis_configs["unified_y_mode"].get()
        
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
            valid_y_values = np.array([v for v in all_y_values if np.isfinite(v)])
            if valid_y_values.size > 0:
                y_min_data = np.min(valid_y_values)
                y_max_data = np.max(valid_y_values)
            else:
                y_min_data, y_max_data = 0, 1
            
            y_min, y_max, y_step = self._calculate_friendly_y_limits(y_min_data, y_max_data)
            
            ax.set_ylim(y_min, y_max)
            ax.yaxis.set_major_locator(MultipleLocator(y_step))
            
            ax.yaxis.set_minor_locator(MultipleLocator(y_step / 2)) 
            ax.grid(True, which='minor', linestyle=':', linewidth=0.5, color='gray', alpha=0.5)

        # 7. X 轴刻度和自定义限制
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

        # 8. Limit lines drawing (保持不变)
        if plot_type in self.data and self.datasets:
            for p in visible_params:
                for line in self.data[plot_type]["limit_lines"].get(p, []):
                    try:
                        start_val = float(line["start"].get())
                        start_unit = line["start_unit"].get()
                        stop_val = float(line["stop"].get())
                        stop_unit = line["stop_unit"].get()
                        start_mhz = start_val * 1000 if start_unit == "GHz" else start_val
                        stop_mhz = stop_val * 1000 if stop_unit == "GHz" else stop_val
                        lower = float(line["lower"].get())
                        upper = float(line["upper"].get())
                        ltype = line["type"].get()

                        min_f_mhz = max(x_min_mhz, min(start_mhz, stop_mhz))
                        max_f_mhz = min(x_max_mhz, max(start_mhz, stop_mhz))

                        if min_f_mhz < max_f_mhz:
                            if ltype in ["Max", "Band", "Upper Only", "Upper/Lower", "Upper Limit"]:
                                ax.hlines(upper, min_f_mhz, max_f_mhz, colors='blue',
                                          linestyles='-', linewidth=1.0, zorder=4)
                            if ltype in ["Min", "Band", "Lower Only", "Upper/Lower", "Lower Limit"]: 
                                ax.hlines(lower, min_f_mhz, max_f_mhz, colors='blue',
                                          linestyles='-', linewidth=1.0, zorder=4)
                        
                    except Exception:
                        pass

        # 9. 绘制 Marker (实现始终显示点和标签，控制 Legend 收集)
        # 临时列表，用于存储需要绘制 Legend 的 Marker 信息
        visible_marker_info_list = []
        
        # 清除旧的 Max 模式 Marker Artists
        if hasattr(self, 'max_marker_artists'):
            for artist in self.max_marker_artists:
                try:
                    artist.remove()
                except:
                    pass
            self.max_marker_artists = [] 
        else:
            self.max_marker_artists = [] 

        if plot_type in self.data:
            for p in visible_params:
                for mark in self.data[plot_type]["marks"].get(p, []):
                    try:
                        # --------------------- 【Marker 状态获取】 ---------------------
                        marker_status_var = mark.get("display_status")
                        status_val = "Display" # 默认值

                        if marker_status_var is not None:
                            try:
                                status_val = marker_status_var.get() 
                            except AttributeError:
                                status_val = marker_status_var
                        # -------------------------------------------------------------------------
                        
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
                            
                        val = self.safe_interp(target_freq_hz, freq, data_array)
                        if val is None:
                            continue
                            
                        x_pt_original = target_freq_hz / 1e6
                        y_pt = val
                        
                        x_pt_plot = max(x_min_mhz, min(x_max_mhz, x_pt_original))
                        
                        color = self.get_max_mode_color(dataset['id'], p)
                        custom_name = self.custom_id_names.get(selected_data_id, f"ID {selected_data_id}")
                        
                        # --- 【核心修改点：Marker 点和标签始终绘制】 ---
                        
                        # 绘制 Marker 点 (圆点) - 始终绘制
                        marker_artist_1, = ax.plot(x_pt_plot, y_pt, '.', markerfacecolor='none', markeredgecolor=color, markersize=4, markeredgewidth=2, zorder=5)
                        self.max_marker_artists.append(marker_artist_1)
                        
                        # 绘制 Marker 标签 (M1, M2...注释) - 始终绘制
                        annotation_artist = ax.annotate(mark_id, xy=(x_pt_plot, y_pt), xytext=(5, 5), textcoords='offset points', fontsize=9, color=color, zorder=6)
                        self.max_marker_artists.append(annotation_artist)

                        # 收集 Marker Legend 文本
                        full_legend_text = f"{mark['id']} ({p} {custom_name}) @{x_display}, {val:.3f} {y_unit}"
                        
                        # --- 【核心修改点：Legend 信息仅在 Display 状态下收集】 ---
                        if status_val == "Display":
                            visible_marker_info_list.append((mark['id'], p, full_legend_text, selected_data_id))
                        
                    except Exception:
                        pass

        # 10. Matplotlib Legend for Data Lines 
        ax.legend(loc='best', fontsize=9, framealpha=0.7)
        
        # 11. Max Mode Marker Legend 排序和显示 (现在使用 visible_marker_info_list)
        txt_artist = None
        
        # 只有当 visible_marker_info_list 非空时才绘制 Legend
        if visible_marker_info_list:
            
            PARAM_ORDER = {'S11': 0, 'S21': 1, 'S12': 2, 'S22': 3}
            
            def max_mode_sort_key(info):
                param_str = info[1]
                data_id_str = info[3]
                
                try: data_id_number = int(data_id_str)
                except ValueError: data_id_number = 9999
                        
                param_index = PARAM_ORDER.get(param_str, 99)
                # 加上 Marker ID 编号作为次级排序键 (假设存在 get_marker_id_number)
                marker_num = self.get_marker_id_number(info[0]) if hasattr(self, 'get_marker_id_number') else 0
                return (data_id_number, param_index, marker_num)

            sorted_markers = sorted(visible_marker_info_list, key=max_mode_sort_key)
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

            txt_artist = ax.text(x_val, y_val, txt, transform=ax.transAxes, fontsize=9, 
                                     verticalalignment=v_align, horizontalalignment=h_align, 
                                     multialignment='left', 
                                     bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.9), zorder=7)
                                     
            # 将 Marker Legend Text Artist 引用也收集起来
            if hasattr(self, 'max_marker_artists'):
                self.max_marker_artists.append(txt_artist)

        # 12. 更新 Marker Artist 引用 
        if not hasattr(self, 'max_marker_legend_artists'):
            self.max_marker_legend_artists = {} 
            
        self.max_marker_legend_artists[plot_type] = txt_artist

        # 13. Figure 标题和布局 
        if self.max_fig:
            sn_text = f"{plot_title_info}"
            self.max_fig.text(0.5, 0.97, sn_text, fontsize=11, ha='center', va='top', fontweight='bold')
            self.max_fig.subplots_adjust(top=0.92, bottom=0.08, left=0.10, right=0.95)

        if redraw_full: 
            self.max_canvas.draw()

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

    # Normal模式配置
    def plot_parameter_output(self, ax, fig, param, plot_type):
        # --- [新增优化 1]：检查参数是否被隐藏（Show Params 状态检查） ---
        # self.show_param_vars 是一个字典，存储每个参数的显示状态 (tk.BooleanVar)
        if not self.show_param_vars[param].get():
            ax.clear()
            ax.set_title("")
            ax.set_xticks([]) # 隐藏 X 轴刻度
            ax.set_yticks([]) # 隐藏 Y 轴刻度
            ax.set_xlabel("")
            ax.set_ylabel("")
            ax.grid(False) # 禁用网格线
            # 在中央显示参数已隐藏的提示
            ax.text(0.5, 0.5, f"{param} Hidden", transform=ax.transAxes,
                    ha='center', va='center', fontsize=14, color='gray')
            # 确保清除 Marker Legend 引用，防止在隐藏的图表上残留
            if param in self.normal_marker_legend_artists:
                self.normal_marker_legend_artists[param] = None 
            return # 隐藏时直接退出绘图，避免执行后续逻辑

        ax.clear()
        ax.set_title(param, fontsize=12, fontweight='bold')
        is_smith_chart = False
        # ---------------------------
        
        ax.clear()
        ax.set_title(param, fontsize=12, fontweight='bold')
        is_smith_chart = False
        ax.set_aspect('equal' if is_smith_chart else 'auto')
        
        # --- [修改 1]：初始化 Marker 信息列表 ---
        # 结构现在是: (Marker ID str, Data ID str, 完整文本)
        marker_info_list = []  
        all_y_values = []
        all_freq_values = []
        
        # Determine Y unit and set Y label
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
            
        for dataset in self.datasets:
            data_id = dataset['id']
            freq = dataset['freq']
            s = dataset['s_data'][param.lower()]
            color = COLOR_CYCLE[(data_id - 1) % len(COLOR_CYCLE)]
            if len(s) == 0:
                continue
            freq_mhz = freq / 1e6
            all_freq_values.extend(freq_mhz)
            line_label = f"ID {data_id}"
            #修改线的粗细从linewidth=1.5到linewidth=1.0
            if plot_type == "Magnitude (dB)":
                y_data = 20 * np.log10(np.abs(s) + 1e-20)
                ax.plot(freq_mhz, y_data, color=color, linewidth=1.0, label=line_label)
                all_y_values.extend(y_data)
                ax.set_xlabel("Frequency (MHz)")
            elif plot_type == "Phase (deg)":
                y_data = np.unwrap(np.angle(s)) * 180 / np.pi
                ax.plot(freq_mhz, y_data, color=color, linewidth=1.0, label=line_label)
                all_y_values.extend(y_data)
                ax.set_xlabel("Frequency (MHz)")
            elif plot_type == "Group Delay (ns)":
                y_data, freq_mhz_gd = self.calculate_group_delay(freq, s)
                ax.plot(freq_mhz_gd, y_data, color=color, linewidth=1.0, label=line_label)
                all_y_values.extend(y_data)
                ax.set_xlabel("Frequency (MHz)")
                
        # 启用主网格线（原代码）
        ax.grid(True, which='major', alpha=0.3)
        
        # 新增：应用自定义 X 轴限制 (Global)
        if self.axis_configs["x_mode"].get() == "Custom":
            try:
                start_val = float(self.axis_configs["x_start"].get())
                stop_val = float(self.axis_configs["x_stop"].get())
                unit = self.axis_configs["x_unit"].get()
                x_start_mhz = start_val * 1000 if unit == "GHz" else start_val
                x_stop_mhz = stop_val * 1000 if unit == "GHz" else stop_val
                ax.set_xlim(x_start_mhz, x_stop_mhz)
            except ValueError:
                pass # Invalid values, skip

        # 新增：应用自定义 Y 轴限制 (per param & plot_type, for Normal mode)
        # Auto Y limit calculation
        y_mode = self.y_configs[plot_type][param]["mode"].get()
        
        if not y_mode == "Custom": # Default mode: calculate auto range
            # --- START: Normal Mode Y-Axis Grouping Logic (S11/S22 & S21/S12) ---
            s_param_index = self.params.index(param)
            
            # 确定分组参数：S11 (0) & S22 (3) 或 S21 (1) & S12 (2)
            if s_param_index in [0, 3]:
                group_params = ["S11", "S22"]
            elif s_param_index in [1, 2]:
                group_params = ["S21", "S12"]
            else:
                group_params = [param] # 兜底逻辑
                
            grouped_y_values = []
            for dataset in self.datasets:
                # 假设 Normal 模式下，所有加载的数据集都用于计算 Y 轴范围
                for p in group_params:
                    # 使用 self._get_y_data_for_limit_calc 来获取 Y 轴数据 (来自之前实现)
                    y_data = self._get_y_data_for_limit_calc(dataset, p, plot_type)
                    if len(y_data) > 0:
                        grouped_y_values.append(y_data)
                
            if grouped_y_values:
                y_all = np.concatenate(grouped_y_values)
                y_min_data = np.min(y_all)
                y_max_data = np.max(y_all)

                # **使用友好的刻度计算函数**
                y_min, y_max, y_step = self._calculate_friendly_y_limits(y_min_data, y_max_data)
                
                # 设置 Y 轴范围
                ax.set_ylim(y_min, y_max)
                
                # **设置 Y 轴主刻度定位器为计算出的步长**
                ax.yaxis.set_major_locator(MultipleLocator(y_step))
                
                # --- [新增] Y 轴细线网格配置 ---
                # 次刻度步长为主刻度的一半
                ax.yaxis.set_minor_locator(MultipleLocator(y_step / 2))
                # 启用次网格线
                ax.grid(True, which='minor', linestyle=':', linewidth=0.5, color='gray', alpha=0.5)
                # -----------------------------
                
            # --- END: Normal Mode Y-Axis Grouping Logic ---

        elif y_mode == "Custom":  
            try:
                # ... (保持原有的 Custom Y limit 设置逻辑) ...
                y_min_custom = float(self.y_configs[plot_type][param]["min"].get())
                y_max_custom = float(self.y_configs[plot_type][param]["max"].get())
                ax.set_ylim(y_min_custom, y_max_custom)
                
                # --- [新增] 自定义模式下的细线网格配置 ---
                # 自定义模式下，刻度数量不固定，使用 AutoMinorLocator(2)
                ax.yaxis.set_minor_locator(AutoMinorLocator(2))
                ax.grid(True, which='minor', linestyle=':', linewidth=0.5, color='gray', alpha=0.5)
                # ------------------------------------
                
            except ValueError:
                pass # Invalid values, skip
        
        # Limit lines
        if plot_type in self.data and self.datasets:
            freq_mhz_all = np.array(all_freq_values)
            for line in self.data[plot_type]["limit_lines"][param]:
                try:
                    start_val = float(line["start"].get())
                    start_unit = line["start_unit"].get()
                    stop_val = float(line["stop"].get())
                    stop_unit = line["stop_unit"].get()
                    start_mhz = start_val * 1000 if start_unit == "GHz" else start_val
                    stop_mhz = stop_val * 1000 if stop_unit == "GHz" else stop_val
                    lower = float(line["lower"].get())
                    upper = float(line["upper"].get())
                    ltype = line["type"].get()
                    #Normal模式下修改线的粗细从linewidth=1.5到linewidth=1.0
                    if all_freq_values:
                        min_f_mhz = max(min(all_freq_values), start_mhz)
                        max_f_mhz = min(max(all_freq_values), stop_mhz)
                        
                        # 检查交集，无交集不绘制
                        if min_f_mhz >= max_f_mhz:
                            continue
                            
                        if ltype in ["Max", "Band", "Upper Only", "Upper/Lower", "Upper Limit"]:
                            # limit line从虚线linestyles='--'改成实线linestyles='-'
                            ax.hlines(upper, min_f_mhz, max_f_mhz, colors='blue', linestyles='-', linewidth=1.0, zorder=4)
                        
                        if ltype in ["Min", "Band", "Lower Only", "Upper/Lower", "Lower Limit"]:
                                ax.hlines(lower, min_f_mhz, max_f_mhz, colors='blue', linestyles='-', linewidth=1.0, zorder=4)
                except:
                    pass
        
        # markers drawing (per param)
        # --- 【优化点】新增：获取当前子图的 X 轴限制用于 Marker 钳位 ---
        x_min_mhz, x_max_mhz = ax.get_xlim()
        # -------------------------------------------------------------
        
        # 临时列表，用于存储需要绘制 Legend 的 Marker 信息
        visible_marker_info_list = []

        if plot_type in self.data and self.datasets:
            for mark in self.data[plot_type]["marks"][param]:
                try:
                    # --------------------- 【新增 Marker 状态检查】 ---------------------
                    # Marker 标记 (M1, M2...) 始终绘制
                    display_status = mark.get("display_status", tk.StringVar(value="Display")).get()
                    
                    target_freq_hz = self._get_marker_freq_hz(mark)
                    f_str = mark["freq"].get()
                    unit = mark["unit"].get()
                    x_display = f"{f_str} {unit}"
                    mark_id = mark['id']
                    selected_data_id = mark["data_id"].get()
                    
                    for dataset in self.datasets:
                        data_id = dataset['id']
                        if str(data_id) != selected_data_id:
                            continue
                        s_data = dataset['s_data'][param.lower()]
                        freq = dataset['freq']
                        color = COLOR_CYCLE[(data_id - 1) % len(COLOR_CYCLE)]
                        
                        if plot_type == "Magnitude (dB)":
                            data_array = 20 * np.log10(np.abs(s_data) + 1e-20)
                        elif plot_type == "Phase (deg)":
                            data_array = np.unwrap(np.angle(s_data)) * 180 / np.pi
                        elif plot_type == "Group Delay (ns)":
                            data_array, _ = self.calculate_group_delay(freq, s_data)
                        else:
                            continue
                            
                        if len(freq) < 2:
                            continue
                            
                        val = self.safe_interp(target_freq_hz, freq, data_array)
                        if val is None:
                            continue
                        
                        # 原始频率值 (MHz)
                        x_pt_original = target_freq_hz / 1e6 # Frequency in MHz
                        y_pt = val
                        
                        # --- 【优化点】Marker 频率钳位到 X 轴范围 ---
                        # 用于绘图的 X 坐标 (钳位)
                        x_pt_plot = x_pt_original
                        if x_pt_plot < x_min_mhz:
                            x_pt_plot = x_min_mhz
                        elif x_pt_plot > x_max_mhz:
                            x_pt_plot = x_max_mhz
                        # ---------------------------------------------
                        
                        # Plot marker (使用钳位后的 x_pt_plot) - M1, M2 标记始终显示
                        # Marker标记从'X'改为原点'.'
                        ax.plot(x_pt_plot, y_pt, '.', markerfacecolor='none', markeredgecolor=color, markersize=4, markeredgewidth=2, zorder=5)
                        # 注释也使用钳位后的 x_pt_plot
                        ax.annotate(mark_id, xy=(x_pt_plot, y_pt), xytext=(5, 5),
                                                textcoords='offset points', fontsize=9, color=color,
                                                zorder=6)
                                                
                        # Normal模式Marker信息update
                        # 获取自定义 ID 名称（若未定义则显示默认 ID）
                        custom_name = self.custom_id_names.get(str(data_id), f"ID {data_id}")  
                        
                        # Marker Legend 文本生成
                        full_legend_text = f"{mark_id} ({custom_name}) @{x_display}, {val:.3f} {y_unit}"
                        
                        # --- 【新增 Legend 文本收集逻辑】 ---
                        # 只有当 display_status 为 "Display" 时，才收集 Legend 文本
                        if display_status == "Display":
                            # 存储: (Marker ID str, Data ID str, Full Legend Text)
                            visible_marker_info_list.append((mark_id, selected_data_id, full_legend_text))
                        # -------------------------------------------
                        
                except Exception:
                    pass
        
        # FIX B: 绘制标记信息框 (Marker Legend Box)
        # --- [修改 3]：现在使用 visible_marker_info_list 进行绘制 ---
        if visible_marker_info_list:
            
            # 1. 定义 Normal Mode 排序键（数据 ID -> Marker ID）
            def normal_mode_sort_key(info):
                # info = (Marker ID str, Data ID str, Full Legend Text)
                marker_id_str = info[0]
                data_id_str = info[1] # Data ID 作为主键
                
                # 1.1 获取 Data ID 数字 (主键)
                try:
                    data_id_int = int(data_id_str)
                except ValueError:
                    data_id_int = float('inf') # 非数字 ID 排在最后

                # 1.2 获取 Marker ID 数字 (副键)
                marker_num = self.get_marker_id_number(marker_id_str)  
                
                # 返回一个元组 (ID 编号, Marker 编号)
                return (data_id_int, marker_num)  

            # 2. 执行排序
            sorted_markers = sorted(visible_marker_info_list, key=normal_mode_sort_key)
            
            # 3. 生成 Legend 文本
            # 提取第三个元素 (Full Legend Text)，因为它现在是 index 2
            marker_legend_text = [info[2] for info in sorted_markers]  
            txt = "\n".join(marker_legend_text)
            
            # -----------------------------------------------------------------
            
            # 读取配置
            pos_config = self.marker_pos_configs[plot_type][param]
            mode = pos_config["mode_var"].get()
            
            # 设置默认 Top Right
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
                    # 根据位置自动调整对齐方式
                    h_align = 'left' if x_val < 0.5 else 'right'
                    v_align = 'bottom' if y_val < 0.5 else 'top'
                    if x_val == 0.5: h_align = 'center'
                    if y_val == 0.5: v_align = 'center'
                except:
                    # 无效时回退到 Top Right
                    x_val, y_val = 0.98, 0.98
                    h_align, v_align = 'right', 'top'

            # -------------------------------------------------------------
            # 绘制 Marker Legend
            legend_artist = ax.text(
                x_val, y_val, txt, transform=ax.transAxes, fontsize=9,  
                verticalalignment=v_align, horizontalalignment=h_align,  
                multialignment='left', # 确保多行文本在框内左对齐
                bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.9),  
                zorder=7
            )
            self.normal_marker_legend_artists[param] = legend_artist
            # -------------------------------------------------------------
        else:
            # 如果没有 Marker Legend，则清除 Artist 引用
            self.normal_marker_legend_artists[param] = None

        # ----------------------------------------------------
        # Limits Check Status (Normal Mode) - 【核心修复区域】
        # ----------------------------------------------------
        if self.limits_check_enabled.get():
            
            # 1. 获取限制线配置
            limit_lines = self.data.get(plot_type, {}).get("limit_lines", {}).get(param, [])
            check_results = []

            # 2. 检查是否有任何限制线
            if not limit_lines:
                # Normal模式 无限制线，整个图表直接标记 N/A_NoLimits
                check_results = [{'data_id': None, 'name': 'N/A', 'status': 'N/A_NoLimits'}]
            else:
                # 3. 检查每个数据集
                for dataset in self.datasets:
                    data_id = dataset['id']
                    # 获取 ID 名称，例如 'ID 1' 或自定义名称
                    name = self.custom_id_names.get(str(data_id), f"ID {data_id}")
                    
                    s_data = dataset['s_data'].get(param.lower())
                    
                    if s_data is None or len(s_data) < 2:
                        # 无数据
                        status = 'N/A_NoData'
                    else:
                        # 【核心修改点】: 调用并接收 (is_pass, has_overlap)
                        is_pass, has_overlap = self._check_dataset_limits(dataset, plot_type, param)
                        
                        if has_overlap:
                            # 有频率交集，显示 PASS 或 FAIL
                            status = 'PASS' if is_pass else 'FAIL'
                        else:
                            # 无频率交集，显示 N/A (NoOverlap)
                            status = 'N/A_NoOverlap'  
                            
                    check_results.append({'data_id': data_id, 'name': name, 'status': status})
                    
                # 4. 如果没有数据集，则显示 N/A
                if not self.datasets:
                    check_results = [{'data_id': None, 'name': 'N/A', 'status': 'N/A_NoData'}]
                    
            # 5. 绘制结果
            self._draw_limit_check_status(ax, check_results)
        # ----------------------------------------------------
        
        # --- [新增/修正] 确保 X 轴也有细线网格 ---
        # 确保 X 轴刻度最多为 10 个 (MaxNLocator(10) 已在原代码中)
        ax.xaxis.set_major_locator(MaxNLocator(10)) 
        # 添加 X 轴细线网格
        ax.xaxis.set_minor_locator(AutoMinorLocator(2))
        ax.grid(True, which='minor', linestyle=':', linewidth=0.5, color='gray', alpha=0.5)
        # -----------------------------------------

        # ax.yaxis.set_major_locator(MaxNLocator(10)) # 已被新的 MultipleLocator/Custom 逻辑取代或覆盖
        # hide odd tick labels (keep interface similar)
        #self._optimize_tick_labels_output(ax, fig)
        # 不调用canvas.draw()，留给调用者

    def _optimize_tick_labels_output(self, ax, fig):
        try:
            import numpy as np
            import matplotlib.ticker as ticker
            
            fig.canvas.draw()  # 确保当前视图已渲染
            
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

            # 🎯 根据模式调整小数位逻辑
            if self.display_mode.get() == "Max":
                # Max模式 → 细化显示
                if span < 5:
                    decimals = 4
                elif span < 10:
                    decimals = 3 
                elif span < 20:
                    decimals = 2                    
                else:
                    decimals = 1
            else:
                # Normal模式 → 原有逻辑
                if span < 10:
                    decimals = 1                 
                else:
                    decimals = 0

            # 设置刻度与格式化器
            ax.xaxis.set_major_locator(ticker.LinearLocator(numticks=10))
            ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: smart_x_formatter(x, pos, decimals)))

            # === Y轴格式化 ===
            y_ticks = ax.get_yticks()
            ax.set_yticklabels([smart_y_formatter(y) for y in y_ticks])

            fig.canvas.draw()

        except Exception:
            pass

    # ---------- Optimized marker UI helpers with Display/Hide button (Removed all trace_add) ----------
    def _draw_marker_frame_and_bind(self, mark_data, plot_type, param, marker_list_frame, canvas):
        import tkinter as tk
        from tkinter import ttk 
        
        frame = tk.Frame(marker_list_frame, bg="#ffffff", relief="solid", bd=1)
        frame.pack(fill="x", pady=3, padx=5)

        freq_var = mark_data["freq"]
        unit_var = mark_data["unit"]
        data_id_var = mark_data["data_id"]
        mark_id = mark_data["id"] # mark_id 现在是一个 'str' 
        
        # ------------------ 新增 Display Status 变量 ------------------
        display_var = mark_data["display_status"] 
        
        def toggle_display_status():
            """切换 Marker Legend 的显示状态并刷新图表 (用户主动点击，必须刷新)。"""
            current = display_var.get()
            new_status = "Hide" if current == "Display" else "Display"
            display_var.set(new_status)
            # 必须调用刷新函数来更新 Marker Legend
            #self.update_plots() # 保留：因为这是功能的核心
            
        # ------------------ Remove 逻辑 ------------------
        def remove_and_update():
            try:
                self.data[plot_type]["marks"][param].remove(mark_data)
            except:
                pass
            self._reindex_markers_and_refresh_ui(plot_type, param)
            
        # ------------------ UI 布局 (Grid Column Index: 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7) ------------------
        
        # Col 0: Marker ID (M1:) - 保持不变
        tk.Label(frame, text=f"{mark_id}:", bg="#ffffff", font=("sans-serif", 10, "bold"), fg="#c0392b").grid(row=0, column=0, padx=3) 
        
        # Col 1: Freq Entry - 保持不变
        tk.Entry(frame, textvariable=freq_var, width=10).grid(row=0, column=1, padx=3)
        
        # Col 2: Unit Combobox - 保持不变
        ttk.Combobox(frame, textvariable=unit_var, values=["MHz", "GHz"], width=6, state="readonly").grid(row=0, column=2, padx=3)
        
        # Col 3: Ref ID Label - 保持不变
        tk.Label(frame, text="Ref ID:", bg="#ffffff").grid(row=0, column=3, padx=3)
        
        # Col 4: Data ID Combobox - 保持不变
        data_id_options_current = [str(d['id']) for d in self.datasets] if self.datasets else ["1"]
        ttk.Combobox(frame, textvariable=data_id_var, values=data_id_options_current, width=4, state="readonly").grid(row=0, column=4, padx=3)
        
        # **新的 Col 5: Display Status Label (插入)**
        # 这个标签在 Data ID Combobox (Col 4) 和 Display/Hide Button (新 Col 6) 之间
        tk.Label(frame, text="Display Status:", bg="#ffffff").grid(row=0, column=5, padx=(10, 3))

        # Col 6 (原 Col 5): 新增 Display/Hide 切换按钮 - 向右移动到 column=6
        tk.Button(frame, 
                  textvariable=display_var, 
                  command=toggle_display_status, # 保留：用户主动点击，需要刷新
                  bg="#5DADE2", fg="white", relief="flat", 
                  width=6).grid(row=0, column=6, padx=(5, 0), sticky="ew")

        # Col 7 (原 Col 6): Remove 按钮 - 向右移动到 column=7
        tk.Button(frame, text="Remove", bg="#95a5a6", fg="white", command=remove_and_update).grid(row=0, column=7, padx=5)

        # --- 移除原有代码中的所有 freq_var.trace_add, unit_var.trace_add, data_id_var.trace_add ---
        # 如果要避免卡顿，这些 trace_add 应该在用户完成输入后（例如，通过一个 "Apply" 按钮或 Entry 的 <Return> 事件）再触发更新。
        
        # 确保列 1 (Freq Entry) 具有伸缩权重
        frame.grid_columnconfigure(1, weight=1)
        
        mark_data["frame"] = frame
        canvas.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _reindex_markers_and_refresh_ui(self, plot_type, param):
        marks = self.data[plot_type]["marks"][param]
        ui_refs = self.data[plot_type]["ui_refs"].get(param, {})
        marker_list_frame = ui_refs.get("marker_list_frame")
        canvas = ui_refs.get("canvas")
        if not marker_list_frame or not canvas:
            return
        for widget in marker_list_frame.winfo_children():
            widget.destroy()
        for i, mark_data in enumerate(marks):
            new_id = f"M{i + 1}"
            mark_data["id"] = new_id
            self._draw_marker_frame_and_bind(mark_data, plot_type, param, marker_list_frame, canvas)

    # ---------- File / data handling ----------
    def clear_all_datasets(self):
        if not messagebox.askyesno("Clear Data", f"Are you sure to clear all {len(self.datasets)} loaded datasets?"):
            return
        
        # 1. 核心数据和状态清空
        self.datasets = []
        self.next_dataset_id = 1
        self.current_img = None
        self.maximized_param = None
        
        # Reset Max Mode Exit and clean up 
        self.exit_max_mode() 
        if self.max_frame:
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
        
        # === 核心修复 1：销毁 Limits & Marks 标签页 UI 框架，解决 ui_refs 引用丢失问题 ===
        if hasattr(self, 'limit_tabs'):
            for t in list(self.limit_tabs.keys()):
                try:
                    w = self.limit_tabs.pop(t)
                    self.notebook.forget(w)
                    w.destroy()
                except:
                    pass
        # ==============================================================================

        # Reset show_param_vars
        for p in self.params:
            self.show_param_vars[p].set(True)

        # 2. UI 变量/状态清空 
        if hasattr(self, 'marker_click_enabled'):
            self.marker_click_enabled.set(False) 
 
        # [新增修改] 恢复 "Disable Refresh" 为默认状态 (False)
        if hasattr(self, 'disable_refresh_var'):
            self.disable_refresh_var.set(False)
 
         # --- [新增] 2. 重置 Limits Check 状态、数据和 UI 引用 ---
        if hasattr(self, 'limits_check_enabled'):
            self.limits_check_enabled.set(False) # 恢复默认状态 (关闭)
            
        for plot_type in self.data:
            for param in self.params:
                # 清空限制线数据
                if "limit_lines" in self.data[plot_type]:
                    self.data[plot_type]["limit_lines"][param] = []
                # 清空 Marker 数据 (通常也需要一同清空)
                if "marks" in self.data[plot_type]:
                    self.data[plot_type]["marks"][param] = []
                # 清空 UI 引用 (Limit Line 和 Marker)
                if "ui_refs" in self.data[plot_type]:
                    self.data[plot_type]["ui_refs"][param] = {}
 
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

        # 3. UI 刷新和重绘
        self.create_data_information_tab()
        self.create_axis_control_tab()
        self.update_data_information_tab() 
        
        # === 核心修复 2：重建当前 Plot Type 的 Limits & Marks 标签页，确保 UI 引用立即可用 ===
        # 这样当 Load S2P 后的 update_plots 运行 Marker 逻辑时，ui_refs 是有效的。
        self.create_limit_mark_tab(self.plot_type.get())
        # ====================================================================================

        if hasattr(self, 'chart_tab'):
            self.notebook.select(self.chart_tab)
            
        self.update_file_list_ui()

        # 4. 最终状态和绘图更新 
        self.status_var.set("All data cleared. Please load S2P file(s)...")
        self.update_plots() 
        messagebox.showinfo("Clear Complete", "All data cleared. Please load S2P file(s).")

    def reset_application(self):
        if not messagebox.askyesno("Reset Application", "Reset application to initial state?"):
            return
        
        # Reset variables without recreating them
        self.datasets = []
        self.next_dataset_id = 1
        self.current_img = None
        self.maximized_param = None
        
        # --- 1. 重置 Marker 交互状态和自定义名称 ---
        if hasattr(self, 'marker_click_enabled'):
            self.marker_click_enabled.set(False) 
        self.custom_id_names = {} # 清空自定义名称映射
 
        # [新增修改] 恢复 "Disable Refresh" 为默认状态 (False)
        if hasattr(self, 'disable_refresh_var'):
            self.disable_refresh_var.set(False)

        # --- [新增] 2. 重置 Limits Check 状态、数据和 UI 引用 ---
        if hasattr(self, 'limits_check_enabled'):
            self.limits_check_enabled.set(False) # 恢复默认状态 (关闭)
            
        for plot_type in self.data:
            for param in self.params:
                # 清空限制线数据
                if "limit_lines" in self.data[plot_type]:
                    self.data[plot_type]["limit_lines"][param] = []
                # 清空 Marker 数据 (通常也需要一同清空)
                if "marks" in self.data[plot_type]:
                    self.data[plot_type]["marks"][param] = []
                # 清空 UI 引用 (Limit Line 和 Marker)
                if "ui_refs" in self.data[plot_type]:
                    self.data[plot_type]["ui_refs"][param] = {}
 
        # 2. 清空 Loaded File Information UI 变量和 Combobox
        if hasattr(self, 'selected_data_id_var'):
            self.selected_data_id_var.set("")
        if hasattr(self, 'custom_name_var'):
            self.custom_name_var.set("")
        if hasattr(self, "id_combo"):
            self.id_combo.set("")
            self.id_combo["values"] = []
            
        # --- 3. 移除不必要的 Treeview 清空逻辑（它在 update_data_information_tab 中被销毁） ---
        # 之前尝试清空 self.file_info_tree 的逻辑已被删除，因为 update_data_information_tab 会处理销毁。

        self.title_var.set("SN-001")
        self.plot_type.set("Magnitude (dB)")
        self.display_mode.set("Normal")

        SUPPORTED_PLOT_TYPES = ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"]
        
        # Reset Marker 位置配置
        for pt in SUPPORTED_PLOT_TYPES:
            for p in self.params:
                self.marker_pos_configs[pt][p]["mode_var"].set("Top Right")
                self.marker_pos_configs[pt][p]["x_var"].set("0.5")
                self.marker_pos_configs[pt][p]["y_var"].set("0.5")

        # Reset Max 模式 Marker 位置配置
        for pt in SUPPORTED_PLOT_TYPES:
            self.max_marker_pos_configs[pt]["mode_var"].set("Top Right")
            self.max_marker_pos_configs[pt]["x_var"].set("0.5")
            self.max_marker_pos_configs[pt]["y_var"].set("0.5")

        # Reset data
        for pt in SUPPORTED_PLOT_TYPES:
            for p in self.params:
                self.data[pt]["limit_lines"][p] = []
                self.data[pt]["marks"][p] = []
                self.data[pt]["ui_refs"][p] = {}

        # Reset show_param_vars
        for p in self.params:
            self.show_param_vars[p].set(True)

        # Reset Axis configs
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

        # Reset Max 模式的图形对象引用
        if self.max_frame:
            self.exit_max_mode()
            self.max_frame.destroy()
            self.max_frame = None
            self.max_fig = None
            self.max_ax = None
            self.max_canvas = None
            self.max_toolbar = None
            self.max_cids = {}

        # destroy existing limit tabs and recreate
        if hasattr(self, 'limit_tabs'):
            for t in list(self.limit_tabs.keys()):
                try:
                    w = self.limit_tabs.pop(t)
                    self.notebook.forget(w)
                    w.destroy()
                except:
                    pass
        self.create_limit_mark_tab(self.plot_type.get())

        self.create_data_information_tab()
        self.create_axis_control_tab()
        
        # --- 关键修复：强制刷新文件详细信息列表 (Treeview) ---
        # 确保在 datasets=[] 后，销毁旧的 Treeview 并显示 "No files loaded."
        self.update_data_information_tab() 
        
        if hasattr(self, 'chart_tab'):
            self.notebook.select(self.chart_tab)
            
        self.update_file_list_ui()
        self.status_var.set("Application reset to initial state.")
        self.update_plots()
        messagebox.showinfo("Reset Complete", "The application has been reset to its initial state.")

    def load_s2p(self):
        file_paths = filedialog.askopenfilenames(
            title="Select S2P File(s)",
            filetypes=[("S2P files", "*.s2p"), ("All files", "*.*")]
        )
        if not file_paths:
            return

        loaded_count = 0
        failed_files = []

        for file_path in file_paths:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                freq_unit = "Hz"
                s_format = None

                # 解析头部行
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

                # 提取数值行
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

                # 根据格式转换S参数
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

                # 创建新数据集
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

        # 更新界面
        if loaded_count > 0:
            self.status_var.set(
                f"Loaded {loaded_count} file(s) successfully | Total Files: {len(self.datasets)}"
            )
            self.update_file_list_ui()
            self.on_plot_type_change()
            self.update_plots()
            self.update_data_information_tab()

            if self.display_mode.get() == "Normal":
                self.restore_plots_layout()

            if hasattr(self, "id_combo"):
                self.id_combo["values"] = [str(d["id"]) for d in self.datasets]

        # 显示失败文件
        if failed_files:
            messagebox.showwarning(
                "Partial Load Warning",
                "Some files could not be loaded:\n\n" + "\n".join(failed_files)
            )

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
        try:
            # ------------------- Max 模式 -------------------
            if self.display_mode.get() == "Max" and self.max_fig:
                # 您的 Max 模式代码保持不变（或使用之前推荐的 fig.tight_layout）：
                # 双行标题（无彩色横线）
                title_line1 = f"{""}"
                # 删除第二行的data_id
                self.max_fig.suptitle(f"{title_line1}",
                                         fontsize=12, fontweight="bold", y=0.98)

                if copy:
                    buf = io.BytesIO()
                    # 确保使用 bbox_inches='tight' 和合适的 DPI
                    self.max_fig.savefig(buf, format='png', dpi=200, bbox_inches='tight')
                    buf.seek(0)
                    img = Image.open(buf)
                    ok = copy_image_to_clipboard(img)
                    buf.close()
                    if ok:
                        messagebox.showinfo("Copied", "Max mode plot copied to clipboard.")
                    else:
                        messagebox.showwarning("Not supported", "Clipboard copy not supported on this platform.")
                else:
                    # >>> 优化开始 (Max 模式保存) <<<
                    filename = self._generate_filename() # <--- 新增: 生成文件名
                    f = filedialog.asksaveasfilename(defaultextension=".png",
                                                     filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")],
                                                     initialfile=filename) # <--- 修改: 传入 initialfile
                    if not f:
                        return
                    self.max_fig.savefig(f, dpi=200, bbox_inches='tight')
                    messagebox.showinfo("Saved", f"Max mode plot saved to {f}")
                    # >>> 优化结束 <<<

            # ------------------- Normal 模式 -------------------
            else:
                out_fig = plt.Figure(figsize=(12, 8), dpi=150)
                axs = out_fig.subplots(2, 2)
                axs = axs.flatten()

                # ✅ 第一行标题
                #最顶部的Plot title信息
                title_line1 = f"{self.title_var.get()}"
                out_fig.text(0.5, 0.975, title_line1, ha='center', va='top',
                              fontsize=14, fontweight="bold")

                # ✅ 第二行（ID + 彩色横线）
                start_x = 0.25
                spacing = 0.15
                y_pos = 0.94
                for i, d in enumerate(self.datasets):
                    data_id = d['id']
                    custom_name = self.custom_id_names.get(str(data_id), f"ID {data_id}")
                    color = COLOR_CYCLE[(data_id - 1) % len(COLOR_CYCLE)]
                    x_pos = start_x + i * spacing
                    # 绘制ID文字
                    #自定义曲线示例名称从ID {data_id}改为{custom_name}
                    out_fig.text(x_pos - 0.02, y_pos, f"{custom_name}", ha='right', va='center',
                                  fontsize=12, color='black', fontweight="bold")
                    # 绘制彩色横线
                    out_fig.text(x_pos, y_pos, "—", ha='left', va='center',
                                  fontsize=16, color=color, fontweight="bold")

                plot_type = self.plot_type.get()
                
                # --- 关键修改部分开始 ---
                for i, p in enumerate(self.params):
                    ax_new = axs[i]
                    # 1. 重新绘制数据到新的 Axes 对象
                    self.plot_parameter_output(ax_new, out_fig, p, plot_type)
                    
                    # 2. 从当前显示的 Normal 模式图表中获取缩放后的限制
                    if p in self.plot_configs:
                        ax_current = self.plot_configs[p]["ax"]
                        
                        # 3. 将当前 Axes 的 X/Y 限制同步到新的 Axes 对象
                        # 这样 out_fig 上的图表就和用户屏幕上看到的一致了
                        ax_new.set_xlim(ax_current.get_xlim())
                        ax_new.set_ylim(ax_current.get_ylim())
                # --- 关键修改部分结束 ---

                out_fig.subplots_adjust(left=0.08, right=0.96, top=0.90,
                                         bottom=0.08, wspace=0.28, hspace=0.32)

                if copy:
                    buf = io.BytesIO()
                    out_fig.savefig(buf, format='png', dpi=200)
                    buf.seek(0)
                    img = Image.open(buf)
                    ok = copy_image_to_clipboard(img)
                    buf.close()
                    if ok:
                        messagebox.showinfo("Copied", "Normal mode plots copied to clipboard.")
                    else:
                        messagebox.showwarning("Not supported", "Clipboard copy not supported on this platform.")
                else:
                    # >>> 优化开始 (Normal 模式保存) <<<
                    filename = self._generate_filename() # <--- 新增: 生成文件名
                    f = filedialog.asksaveasfilename(defaultextension=".png",
                                                     filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")],
                                                     initialfile=filename) # <--- 修改: 传入 initialfile
                    if not f:
                        return
                    out_fig.savefig(f, dpi=200)
                    messagebox.showinfo("Saved", f"Normal mode plots saved to {f}")
                    # >>> 优化结束 <<<

        except Exception as e:
            messagebox.showerror("Operation Failed", f"An error occurred: {e}")

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
                start_unit_var.set("MHz")  # 固定 MHz
                stop_unit_var = line_data.get("stop_unit", tk.StringVar(value="MHz"))
                lower_var = line_data.get("lower", tk.StringVar(value=default_lower))
                upper_var = line_data.get("upper", tk.StringVar(value=default_upper))

                tk.Label(frame, text="Type:", bg="#ffffff").grid(row=0, column=0, padx=3)
                ttk.Combobox(frame, textvariable=type_var, values=["Upper Limit", "Lower Limit"], width=12, state="readonly").grid(row=0, column=1, padx=3)

                tk.Label(frame, text="Start:", bg="#ffffff").grid(row=0, column=2, padx=3)
                tk.Entry(frame, textvariable=start_var, width=6).grid(row=0, column=3, padx=1)
                tk.Label(frame, text="MHz", bg="#ffffff", width=4).grid(row=0, column=4, padx=1)

                tk.Label(frame, text="Stop:", bg="#ffffff").grid(row=0, column=5, padx=3)
                tk.Entry(frame, textvariable=stop_var, width=6).grid(row=0, column=6, padx=1)
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
                new_line = {}
                lines.append(new_line)
                draw_limit_line_frame(new_line, limit_lines_frame)
                self.update_plots() # 新增 Limit Line 后调用更新绘图
            tk.Button(limit_control_frame, text="Add Limit Line", bg="#3498db", fg="white", command=add_limit_and_draw).pack(side="left", padx=5)

            mark_container = tk.Frame(scrollable, bg="#f0f2f5")
            mark_container.pack(fill="x", pady=(15, 0))
            tk.Label(mark_container, text="Markers", font=("sans-serif", 11, "bold"), bg="#f0f2f5", fg="#2c3e50").pack(anchor="w", padx=5)
            marker_control_frame = tk.Frame(mark_container, bg="#f0f2f5")
            marker_control_frame.pack(fill="x", pady=(6, 10))
            marker_list_frame = tk.Frame(mark_container, bg="#f0f2f5")
            marker_list_frame.pack(fill="x")
            self.data[plot_type]["ui_refs"][param] = {"marker_list_frame": marker_list_frame, "canvas": canvas}
            def add_mark_and_draw():
                data_id_options = [str(d['id']) for d in self.datasets]
                default_data_id = data_id_options[0] if data_id_options else "1"
                
                # 优化后的 new_mark 定义，新增 display_status 字段
                new_mark = {
                    "id": "TEMP", 
                    "freq": tk.StringVar(value="100"), 
                    "unit": tk.StringVar(value="MHz"), 
                    "data_id": tk.StringVar(value=default_data_id),
                    "display_status": tk.StringVar(value="Display") # <<< 新增：默认状态为 "Display"
                }
                
                # 假设 marks 变量在 add_mark_and_draw 的作用域内可用，指向 self.data[plot_type]["marks"][param]
                marks.append(new_mark)
                self._reindex_markers_and_refresh_ui(plot_type, param)

            tk.Button(marker_control_frame, text="Add Marker", bg="#2ecc71", fg="white", command=add_mark_and_draw).pack(side="left", padx=5)

            # Marker Legend Position (Normal mode)
            legend_label = tk.Label(marker_control_frame, text="Marker Position:", font=("sans-serif", 10), bg="#f0f2f5")
            pos_config = self.marker_pos_configs[plot_type][param]
            mode_var = pos_config["mode_var"]
            x_var = pos_config["x_var"]
            y_var = pos_config["y_var"]
            pos_combo = ttk.Combobox(marker_control_frame, textvariable=mode_var, values=self.MARKER_POSITIONS, state="readonly", width=12)
            legend_custom_frame = tk.Frame(marker_control_frame, bg="#f0f2f5")
            tk.Label(legend_custom_frame, text="X:", font=("sans-serif", 10), bg="#f0f2f5").pack(side="left", padx=(5, 2))
            x_entry = tk.Entry(legend_custom_frame, textvariable=x_var, width=5)
            x_entry.pack(side="left")
            tk.Label(legend_custom_frame, text="Y:", font=("sans-serif", 10), bg="#f0f2f5").pack(side="left", padx=(5, 2))
            y_entry = tk.Entry(legend_custom_frame, textvariable=y_var, width=5)
            y_entry.pack(side="left")

            # Marker Legend Position (Max mode)
            max_pos_config = self.max_marker_pos_configs[plot_type]
            max_mode_var = max_pos_config["mode_var"]
            max_x_var = max_pos_config["x_var"]
            max_y_var = max_pos_config["y_var"]
            max_label = tk.Label(marker_control_frame, text="Marker Position:", font=("sans-serif", 10), bg="#f0f2f5")
            max_combo = ttk.Combobox(marker_control_frame, textvariable=max_mode_var, values=self.MARKER_POSITIONS, state="readonly", width=12)
            max_custom_frame = tk.Frame(marker_control_frame, bg="#f0f2f5")
            tk.Label(max_custom_frame, text="X:", font=("sans-serif", 10), bg="#f0f2f5").pack(side="left", padx=(5, 2))
            max_x_entry = tk.Entry(max_custom_frame, textvariable=max_x_var, width=5)
            max_x_entry.pack(side="left")
            tk.Label(max_custom_frame, text="Y:", font=("sans-serif", 10), bg="#f0f2f5").pack(side="left", padx=(5, 2))
            max_y_entry = tk.Entry(max_custom_frame, textvariable=max_y_var, width=5)
            max_y_entry.pack(side="left")

            # 初始 pack Legend Pos (Normal mode)
            legend_label.pack(side="left", padx=(10, 5))
            pos_combo.pack(side="left", padx=5)
            if mode_var.get() == "Custom":
                legend_custom_frame.pack(side="left", padx=(10, 5))

            # Trace for Legend Pos
            mode_var.trace_add("write", lambda *args: self.on_legend_mode_change(plot_type, param))

            # 初始不 pack Max Marker Config
            # max_label.pack_forget() 等已在 update_marker_controls_visibility 中处理

            # Trace for Max Marker Config
            max_mode_var.trace_add("write", lambda *args: self.on_max_mode_change(plot_type))

            # 存储控件引用
            self.data[plot_type]["ui_refs"][param]["legend_controls"] = {
                "label": legend_label,
                "combo": pos_combo,
                "custom_frame": legend_custom_frame
            }
            self.data[plot_type]["ui_refs"][param]["max_controls"] = {
                "label": max_label,
                "combo": max_combo,
                "custom_frame": max_custom_frame
            }

            self._reindex_markers_and_refresh_ui(plot_type, param)

    def create_data_information_tab(self):
        # 1. 创建 Tab 页
        if not hasattr(self, 'data_information_tab'):
            self.data_information_tab = tk.Frame(self.notebook, bg="#f0f2f5")

        try:
            self.notebook.index(self.data_information_tab)
        except tk.TclError:
            self.notebook.add(self.data_information_tab, text=" Loaded File Information ")
            
        # 确保该 Tab 位于索引 1 (第二个位置)
        try:
            current_index = self.notebook.index(self.data_information_tab)
            if current_index != 1:
                self.notebook.insert(1, self.data_information_tab)
        except tk.TclError:
            # 如果 tab 尚未添加，上面的 add 语句已经处理，这里只是预防性检查
            pass
        
        # 2. 创建文件列表区域 (Loaded Files)
        if not hasattr(self, 'file_list_frame'):
            self.file_list_frame = tk.LabelFrame(self.data_information_tab, text="Loaded Files (ID - Name)",
                                                 font=("sans-serif", 10), bg="#f0f2f5")
            # 保持原始打包：占据顶部第一行，左右填充并带边距
            self.file_list_frame.pack(fill="x", pady=(10, 0), padx=15) 
            
            self.file_list_content = tk.Frame(self.file_list_frame, bg="#f0f2f5")
            self.file_list_content.pack(fill="x", padx=5, pady=5)

        # 3. 创建自定义 ID 名称区域 (Customize Files (ID - Name))
        # 此区域被移到文件列表下方，总结内容上方
        if not hasattr(self, 'custom_id_outer'):
            
            # 使用独立外层Frame保证独立成行并左对齐
            custom_id_outer = tk.Frame(self.data_information_tab, bg="#f0f2f5")
            # 保持原始打包：占据顶部第二行，与 file_list_frame 对齐 (padx=15)
            custom_id_outer.pack(fill="x", side="top", anchor="w", padx=15, pady=(10, 10))
            self.custom_id_outer = custom_id_outer # 保存引用
            
            custom_id_frame = tk.LabelFrame(custom_id_outer, text="Customize Files (ID - Name)",
                                             font=("sans-serif", 10), bg="#f0f2f5", labelanchor="nw")
            custom_id_frame.pack(fill="x", anchor="w", padx=0, pady=0)

            input_frame = tk.Frame(custom_id_frame, bg="#f0f2f5")
            input_frame.pack(fill="x", padx=10, pady=8, anchor="w")

            # 变量检查（虽然在 __init__ 中可能已创建，但为安全起见）
            if not hasattr(self, 'selected_data_id_var'):
                 self.selected_data_id_var = tk.StringVar(value="")
            if not hasattr(self, 'custom_name_var'):
                 self.custom_name_var = tk.StringVar(value="")

            tk.Label(input_frame, text="Select ID:", bg="#f0f2f5").pack(side="left", padx=(0, 5))
            self.id_combo = ttk.Combobox(input_frame, textvariable=self.selected_data_id_var, state="readonly", width=8)
            self.id_combo.pack(side="left", padx=5)

            tk.Label(input_frame, text="New Name:", bg="#f0f2f5").pack(side="left", padx=(15, 5))
            tk.Entry(input_frame, textvariable=self.custom_name_var, width=22).pack(side="left", padx=5)

            tk.Button(input_frame, text="Set Name", command=self.set_custom_id_name, width=10).pack(side="left", padx=(20, 0))
            # 新增：清空自定义名称按钮
            tk.Button(input_frame, text="Clear Names", bg="#e74c3c", fg="white", command=self.clear_custom_names).pack(side="left", padx=(15, 5))

            # 下拉事件绑定
            self.id_combo.bind("<<ComboboxSelected>>", self._on_id_selected_for_rename)
        # --- 自定义功能区结束 ---

        # 4. 创建可滚动的总结内容区域 (Summary Content)
        if not hasattr(self, 'summary_content_frame'):
            canvas = tk.Canvas(self.data_information_tab, bg="#f0f2f5")
            scrollbar = tk.Scrollbar(self.data_information_tab, orient="vertical", command=canvas.yview)
            
            # summary_content_frame 放在 canvas 内部
            self.summary_content_frame = tk.Frame(canvas, bg="#f0f2f5")
            self.summary_content_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=self.summary_content_frame, anchor="nw")
            
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # 使用 side="left" / "right" 让 canvas 和 scrollbar 占据剩余空间
            canvas.pack(side="left", fill="both", expand=True, padx=15, pady=15)
            scrollbar.pack(side="right", fill="y")
        
        # 5. 刷新文件列表 UI
        self.update_file_list_ui()

    def update_file_list_ui(self):
        if not hasattr(self, 'file_list_content'):
            return
        for widget in self.file_list_content.winfo_children():
            widget.destroy()
        if not self.datasets:
            tk.Label(self.file_list_content, text="No files loaded.", bg="#f0f2f5", fg="gray").pack(padx=5, pady=5)
            return
        for i, dataset in enumerate(self.datasets):
            color = COLOR_CYCLE[(dataset['id'] - 1) % len(COLOR_CYCLE)]
            file_name_only = os.path.basename(dataset['name'])
            text = f"ID {dataset['id']} - {file_name_only}"
            label = tk.Label(self.file_list_content, text=text, bg="#f0f2f5", fg=color, font=("sans-serif", 10, "bold"))
            label.pack(side="left", padx=10, pady=2)
            def remove_data(data_id=dataset['id']):
                self.remove_dataset(data_id)
            remove_btn = tk.Button(self.file_list_content, text="X", command=remove_data, bg="#e74c3c", fg="white", font=("sans-serif", 8), width=2, height=1, relief="flat")
            remove_btn.pack(side="left", padx=(0, 15), pady=2)

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
                messagebox.showerror("Error", f"The new name '{new_name}' is already used by Data ID {id_str}. Please choose a unique name.")
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
        current_plot_type = self.plot_type.get()
        
        # 现有逻辑：处理 Limit & Mark Tab 的创建或切换
        # (假设 create_limit_mark_tab 会确保在主 notebook 中只显示当前类型的 Limit/Mark Tab)
        self.create_limit_mark_tab(current_plot_type)
        
        # --- 优化逻辑: 切换 Y Axis Control Sub-Notebook 中的标签页 ---
        # 确保 y_sub_notebook 已经创建
        if hasattr(self, 'y_sub_notebook'):
            # 这里的顺序必须与 create_axis_control_tab 中添加标签页的顺序一致
            plot_types = ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"]
            try:
                # 找到当前 Plot Type 对应的索引
                index = plot_types.index(current_plot_type)
                # 切换到对应的标签页
                self.y_sub_notebook.select(index)
            except ValueError:
                # 如果 plot_type 值不匹配，则不做任何操作
                pass
        # ----------------------------------------------------
                
        # 刷新图表以应用新的 Plot Type 
        self.update_plots()

    # ---------- Data information tab ----------
    def update_data_information_tab(self):
        if not hasattr(self, 'summary_content_frame'):
            return
        for w in self.summary_content_frame.winfo_children():
            w.destroy()
        if not self.datasets:
            tk.Label(self.summary_content_frame, text="No S2P files loaded.", font=("sans-serif", 12), fg="gray", bg="#f0f2f5").pack(padx=20, pady=20)
            self.summary_content_frame.update_idletasks()
            return
        columns = ("ID", "File Path", "Points", "Format", "Frequency Range")
        tree = ttk.Treeview(self.summary_content_frame, columns=columns, show="headings", height=8)
        style = ttk.Style()
        # 增加 TNotebook.Tab 的水平内边距（[水平填充, 垂直填充]）。
        # 将水平填充从默认值（通常很小）增加到 15 像素。
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
        v_scrollbar = ttk.Scrollbar(self.summary_content_frame, orient="vertical", command=tree.yview)
        h_scrollbar = ttk.Scrollbar(self.summary_content_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        tree.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.summary_content_frame.grid_rowconfigure(0, weight=1)
        self.summary_content_frame.grid_columnconfigure(0, weight=1)
        for dataset in self.datasets:
            data_id = dataset['id']
            name = dataset['name']
            points = dataset['points']
            s_format = dataset['format']
            freq = dataset['freq']
            min_f = freq.min()
            max_f = freq.max()
            def format_freq(f_hz):
                if f_hz >= 1e9:
                    return f"{f_hz / 1e9:.3f} GHz"
                elif f_hz >= 1e6:
                    return f"{f_hz / 1e6:.3f} MHz"
                elif f_hz >= 1e3:
                    return f"{f_hz / 1e3:.3f} KHz"
                else:
                    return f"{f_hz:.3f} Hz"
            freq_range_str = f"{format_freq(min_f)} to {format_freq(max_f)}"
            tree.insert("", "end", values=(str(data_id), name, str(points), s_format, freq_range_str))
        def on_treeview_motion(event):
            item = tree.identify_row(event.y)
            if item:
                col = tree.identify_column(event.x)
                if col == "#2":
                    value = tree.item(item, "values")[1]
                    self.status_var.set(f"Full Path: {value}")
                else:
                    self.status_var.set("Loaded File Information")
            else:
                self.status_var.set("Loaded File Information")
        tree.bind("<Motion>", on_treeview_motion)
        self.summary_content_frame.update_idletasks()

if __name__ == '__main__':
    root = tk.Tk()

    if check_license(root):
        
        app = SViewGUI(root)

        app.setup_ui()
        app.plot_type.trace("w", app.on_plot_type_change)
        app.display_mode.trace("w", app.on_display_mode_change)
        
        root.mainloop()