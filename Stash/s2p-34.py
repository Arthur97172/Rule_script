# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import matplotlib.pyplot as plt
# 导入 NavigationToolbar2Tk 以实现缩放和平移功能
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk 
import os
import re
from PIL import Image
import io
import platform
import subprocess
import matplotlib.font_manager as fm
import datetime 

# 关闭警告
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

# 支持 Smith 图
try:
    import skrf as rf
    SMITH_AVAILABLE = True
except ImportError:
    SMITH_AVAILABLE = False

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

# 颜色循环，用于区分不同的文件
COLOR_CYCLE = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

# 跨平台剪贴板复制
def copy_image_to_clipboard(img):
    system = platform.system()
    output = io.BytesIO()
    img.convert("RGB").save(output, format="PNG")
    img_data = output.getvalue()
    output.close()

    if system == "Windows":
        try:
            import win32clipboard
            def send_to_clipboard(clip_type, data):
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(clip_type, data)
                win32clipboard.CloseClipboard()
            output = io.BytesIO()
            Image.open(io.BytesIO(img_data)).convert("RGB").save(output, "BMP")
            data = output.getvalue()[14:]
            output.close()
            send_to_clipboard(win32clipboard.CF_DIB, data)
            return True
        except: pass

    elif system == "Linux":
        try:
            process = subprocess.Popen(['xclip', '-selection', 'clipboard', '-t', 'image/png'], stdin=subprocess.PIPE)
            process.communicate(input=img_data)
            return True
        except: pass

    fallback = "S参数_4图合并.png"
    img.save(fallback, "PNG")
    messagebox.showwarning("Clipboard Failed", f"Saved to:\n{os.path.abspath(fallback)}")
    return False

class SViewGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("S-View")
        self.root.geometry("1450x980")
        self.root.resizable(True, True)
        self.root.minsize(1150, 780)
        self.root.configure(bg="#f0f2f5")

        self.datasets = []
        self.next_dataset_id = 1
        
        self.serial_var = tk.StringVar(value="SN-001")
        self.current_img = None
        self.plot_type = tk.StringVar(value="Magnitude (dB)")
        
        self.params = ["S11", "S21", "S12", "S22"]
        
        SUPPORTED_PLOT_TYPES = ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"] 
        
        self.marker_pos_configs = {
            pt: {
                p: {
                    "mode_var": tk.StringVar(value="Top Right"), 
                    "x_var": tk.StringVar(value="0.5"),
                    "y_var": tk.StringVar(value="0.5")
                } for p in self.params
            } for pt in SUPPORTED_PLOT_TYPES
        }
        
        # NOTE: self.data 字典只包含支持 Limit Lines 和 Markers 的图表类型
        self.data = {
            "Magnitude (dB)": {
                "limit_lines": {p: [] for p in self.params},
                "marks": {p: [] for p in self.params},
                "mark_counter": {p: 1 for p in self.params},
            },
            "Phase (deg)": {
                "limit_lines": {p: [] for p in self.params},
                "marks": {p: [] for p in self.params},
                "mark_counter": {p: 1 for p in self.params},
            },
            "Group Delay (ns)": {
                "limit_lines": {p: [] for p in self.params},
                "marks": {p: [] for p in self.params},
                "mark_counter": {p: 1 for p in self.params},
            }
        }
        
        self.MARKER_POSITIONS = ["Top Left", "Top Right", "Bottom Left", "Bottom Right", "Center", "Custom"]
        
        self.maximized_param = None 
        self.plot_configs = {} 

        self.setup_ui()
        self.plot_type.trace("w", self.on_plot_type_change)

    def setup_ui(self):
        main_frame = tk.Frame(self.root, bg="#f0f2f5")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        top_frame = tk.Frame(main_frame, bg="#f0f2f5")
        top_frame.pack(fill="x", pady=(0, 10))

        tk.Label(top_frame, text="Serial Number:", font=("sans-serif", 12), bg="#f0f2f5").pack(side="left", padx=5)
        tk.Entry(top_frame, textvariable=self.serial_var, font=("sans-serif", 12), width=15).pack(side="left")

        tk.Button(top_frame, text="Load S2P File", font=("sans-serif", 14),
                  bg="#4CAF50", fg="white", relief="flat", padx=20, pady=8,
                  command=self.load_s2p).pack(side="left", padx=10)

        tk.Label(top_frame, text="Plot Type:", font=("sans-serif", 12), bg="#f0f2f5").pack(side="left", padx=10)
        
        plot_values = ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"] 
        if SMITH_AVAILABLE:
            plot_values.append("Smith Chart")
            
        plot_combo = ttk.Combobox(top_frame, textvariable=self.plot_type,
                     values=plot_values,
                     state="readonly", width=18)
        plot_combo.pack(side="left", padx=5)

        tk.Button(top_frame, text="Refresh", font=("sans-serif", 12, "bold"),
                  bg="#FF9800", fg="white", relief="flat", padx=20, pady=8,
                  command=self.update_plots).pack(side="left", padx=5)
        
        tk.Button(top_frame, text="Clear Data", font=("sans-serif", 12),
                  bg="#e74c3c", fg="white", relief="flat", padx=20, pady=8,
                  command=self.clear_all_datasets).pack(side="left", padx=5)

        tk.Button(top_frame, text="Copy Plots", font=("sans-serif", 12, "bold"),
                  bg="#FF5722", fg="white", relief="flat", padx=20, pady=8,
                  command=self.copy_all_charts).pack(side="right", padx=5)

        tk.Button(top_frame, text="Save as", font=("sans-serif", 12),
                  bg="#9C27B0", fg="white", relief="flat", padx=20, pady=8,
                  command=self.save_chart).pack(side="right", padx=5)
        
        self.file_list_frame = tk.LabelFrame(main_frame, text="Loaded Files (ID - Name)", font=("sans-serif", 10), bg="#f0f2f5")
        self.file_list_frame.pack(fill="x", pady=(5, 10))
        self.file_list_content = tk.Frame(self.file_list_frame, bg="#f0f2f5")
        self.file_list_content.pack(fill="x", padx=5, pady=5)
        self.loaded_file_labels = {} 

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True, pady=10)

        self.chart_tab = tk.Frame(self.notebook, bg="#f0f2f5")
        self.notebook.add(self.chart_tab, text="S-Parameter Plots")
        self.limit_tabs = {}
        self.setup_chart_tab()

        self.status_var = tk.StringVar(value="Please load S2P file(s)...")
        tk.Label(main_frame, textvariable=self.status_var, font=("sans-serif", 10),
                 bg="#e0e0e0", anchor="w", relief="sunken").pack(side="bottom", fill="x", pady=(10, 0))
        tk.Label(main_frame, text="© 2025 S-View | By Arthur", font=("sans-serif", 9),
                 bg="#f0f2f5", fg="gray").pack(side="bottom", pady=10)

    def setup_chart_tab(self):
        charts_frame = tk.Frame(self.chart_tab, bg="#f0f2f5")
        charts_frame.pack(fill="both", expand=True)
        self.charts_frame = charts_frame 

        param_list = ["S11", "S21", "S12", "S22"]
        colors = {"S11": "#d32f2f", "S21": "#1976d2", "S12": "#7b1fa2", "S22": "#388e3c"}

        for i, param in enumerate(param_list):
            row = i // 2
            col = i % 2
            
            frame = tk.LabelFrame(charts_frame, text=f" {param} ", font=("sans-serif", 11, "bold"), bg="#f0f2f5", fg=colors[param])
            frame.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            
            # Note: Each frame contains its own Figure and Canvas
            fig = plt.Figure(figsize=(5, 4), dpi=100)
            ax = fig.add_subplot(111)
            canvas = FigureCanvasTkAgg(fig, frame)
            canvas_widget = canvas.get_tk_widget()
            canvas_widget.pack(fill="both", expand=True)
            
            # --- 添加导航工具栏 ---
            toolbar_frame = tk.Frame(frame)
            toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)
            toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
            toolbar.update()
            # --- 结束添加导航工具栏 ---

            self.plot_configs[param] = {
                "frame": frame, "fig": fig, "ax": ax, "canvas": canvas, "canvas_widget": canvas_widget,
                "toolbar_frame": toolbar_frame, "toolbar": toolbar
            }
            # 绑定双击事件进行最大化
            canvas_widget.bind("<Double-1>", lambda event, p=param: self.toggle_maximize(p))

        for i in range(2):
            charts_frame.grid_rowconfigure(i, weight=1)
            charts_frame.grid_columnconfigure(i, weight=1)
            
    def update_file_list_ui(self):
        """更新已加载文件的列表显示"""
        for widget in self.file_list_content.winfo_children():
            widget.destroy()
        self.loaded_file_labels.clear()

        if not self.datasets:
            tk.Label(self.file_list_content, text="No files loaded.", bg="#f0f2f5", fg="gray").pack(padx=5, pady=5)
            return
            
        for i, dataset in enumerate(self.datasets):
            color = COLOR_CYCLE[(dataset['id'] - 1) % len(COLOR_CYCLE)]
            text = f"**{dataset['id']}** - {dataset['name']}"
            
            label = tk.Label(self.file_list_content, text=text, 
                             bg="#f0f2f5", fg=color, font=("sans-serif", 10, "bold"))
            label.pack(side="left", padx=10, pady=2)
            self.loaded_file_labels[dataset['id']] = label
            
            def remove_data(data_id=dataset['id']):
                self.remove_dataset(data_id)
            
            remove_btn = tk.Button(self.file_list_content, text="X", 
                                   command=remove_data, 
                                   bg="#e74c3c", fg="white", 
                                   font=("sans-serif", 8), width=2, height=1, relief="flat")
            remove_btn.pack(side="left", padx=(0, 15), pady=2)
            
    def remove_dataset(self, data_id):
        """根据 ID 移除数据集"""
        self.datasets = [d for d in self.datasets if d['id'] != data_id]
        
        # 重新分配 ID
        for i, d in enumerate(self.datasets):
            d['id'] = i + 1
        self.next_dataset_id = len(self.datasets) + 1
        
        self.update_file_list_ui()
        self.update_plots()
        
        if not self.datasets:
            self.status_var.set("All data cleared. Please load S2P file(s)...")

    def on_scroll_zoom(self, mpl_event, param):
        """处理 Matplotlib 滚轮事件，实现缩放"""
        if mpl_event.inaxes is None or self.plot_type.get() == "Smith Chart":
            return
            
        ax = mpl_event.inaxes
        config = self.plot_configs[param]
        
        # 只有在 Matplotlib 工具栏处于默认模式或缩放模式时才允许滚轮缩放，避免与平移/官方缩放冲突
        if config["toolbar"].mode not in ('', 'zoom rect'): 
            return

        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()
        
        # 获取鼠标位置 (数据坐标)
        xdata = mpl_event.xdata 
        ydata = mpl_event.ydata
        
        # 如果数据坐标无效，则返回
        if xdata is None or ydata is None:
            return

        scale_factor = 1.25
        if mpl_event.button == 'up':  # Zoom in
            scale = 1/scale_factor
        elif mpl_event.button == 'down': # Zoom out
            scale = scale_factor
        else:
            return

        # 计算新的 X 限制
        new_xlim = [xdata - (xdata - cur_xlim[0]) * scale,
                    xdata + (cur_xlim[1] - xdata) * scale]
        
        # 计算新的 Y 限制
        new_ylim = [ydata - (ydata - cur_ylim[0]) * scale,
                    ydata + (cur_ylim[1] - ydata) * scale]

        ax.set_xlim(new_xlim)
        ax.set_ylim(new_ylim)
        
        config["canvas"].draw()

    def add_marker_on_click(self, mpl_event, param):
        """Matplotlib 鼠标点击图表时添加 Marker 的处理函数"""
        if not self.datasets: return
        plot_type = self.plot_type.get()
        if plot_type in ["Smith Chart", "Phase (deg)"]: # Smith Chart 和 Phase 不支持点击添加 Marker
             # Phase 图可能需要 Marker，但通常不通过点击添加
             pass 
        if plot_type not in self.data or plot_type == "Smith Chart": return
        
        # 确保是左键点击且点击在坐标轴内
        if mpl_event.inaxes is None or mpl_event.button != 1 or mpl_event.xdata is None:
            return

        # mpl_event.xdata 提供了 Matplotlib 绘图的数据坐标值 (GHz)
        x_data_ghz = mpl_event.xdata 
        
        # 为了兼容性，使用第一个数据集的频率来确定最接近的实际频率点
        ref_freq = self.datasets[0]['freq'] 

        # 1. 查找最接近的数据点
        target_freq_hz = x_data_ghz * 1e9
        idx = np.argmin(np.abs(ref_freq - target_freq_hz))
        closest_freq_hz = ref_freq[idx] # 使用第一个数据集的实际频率点

        # 2. 确定显示单位
        if closest_freq_hz >= 1e9:
            f_val = closest_freq_hz / 1e9
            f_unit = "GHz"
        elif closest_freq_hz >= 1e6:
            f_val = closest_freq_hz / 1e6
            f_unit = "MHz"
        else:
            f_val = closest_freq_hz
            f_unit = "Hz"

        # 3. 添加新的 Marker 数据
        current_count = self.data[plot_type]["mark_counter"][param]
        mark_id = f"M{current_count}"
        self.data[plot_type]["mark_counter"][param] += 1
        
        data_id_options = [str(d['id']) for d in self.datasets]
        default_data_id = data_id_options[0] if data_id_options else "1"

        mark = {
            "id": mark_id,
            "freq": tk.StringVar(value=f"{f_val:.3f}"),
            "unit": tk.StringVar(value=f_unit),
            "data_id": tk.StringVar(value=default_data_id) # 默认参考 ID 仍然需要，因为它是 Marker UI 的一个字段
        }
        self.data[plot_type]["marks"][param].append(mark)
        
        # 4. 刷新 Limits & Marks 标签页 UI
        self.refresh_limit_mark_section(plot_type, param)

        # 5. 重绘图表
        self.update_plots()
        self.status_var.set(f"Marker {mark_id} added at {f_val:.3f} {f_unit} on {param} plot.")

    def toggle_maximize(self, param):
        if not self.datasets: return

        config = self.plot_configs[param]

        if self.maximized_param == param:
            self.maximized_param = None
            self.restore_plots_layout()
            # 退出最大化时，解绑 Matplotlib 事件
            if 'cid_click' in config:
                config["fig"].canvas.mpl_disconnect(config['cid_click'])
                del config['cid_click']
            if 'cid_scroll' in config:
                config["fig"].canvas.mpl_disconnect(config['cid_scroll'])
                del config['cid_scroll']
        else:
            # 先解绑其他可能存在的最大化图表事件
            if self.maximized_param and self.maximized_param in self.plot_configs:
                 other_config = self.plot_configs[self.maximized_param]
                 if 'cid_click' in other_config:
                    other_config["fig"].canvas.mpl_disconnect(other_config['cid_click'])
                    del other_config['cid_click']
                 if 'cid_scroll' in other_config:
                    other_config["fig"].canvas.mpl_disconnect(other_config['cid_scroll'])
                    del other_config['cid_scroll']
                    
            self.maximized_param = param
            self.maximize_plot_layout(param)
            
            # 1. 绑定左键点击事件 (Button-1)
            config['cid_click'] = config["fig"].canvas.mpl_connect(
                'button_press_event', lambda event: self.add_marker_on_click(event, param)
            )
            # 2. 绑定滚轮缩放事件 (Scroll)
            config['cid_scroll'] = config["fig"].canvas.mpl_connect(
                'scroll_event', lambda event: self.on_scroll_zoom(event, param)
            )

        self.update_plots()

    def restore_plots_layout(self):
        self.charts_frame.grid_rowconfigure(0, weight=1)
        self.charts_frame.grid_rowconfigure(1, weight=1)
        self.charts_frame.grid_columnconfigure(0, weight=1)
        self.charts_frame.grid_columnconfigure(1, weight=1)

        for i, (p, config) in enumerate(self.plot_configs.items()):
            row = i // 2
            col = i % 2
            config["frame"].grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            
            # 隐藏工具栏
            config["toolbar_frame"].pack_forget() 
            config["canvas_widget"].pack(side=tk.TOP, fill="both", expand=True) 

            # 退出最大化时，解绑 Matplotlib 事件
            if 'cid_click' in config:
                config["fig"].canvas.mpl_disconnect(config['cid_click'])
                del config['cid_click']
            if 'cid_scroll' in config:
                config["fig"].canvas.mpl_disconnect(config['cid_scroll'])
                del config['cid_scroll']
        
        self.charts_frame.update_idletasks()
        for p, config in self.plot_configs.items():
            if config["canvas_widget"].winfo_ismapped():
                 config["canvas_widget"].update() 

    def maximize_plot_layout(self, param):
        self.charts_frame.grid_rowconfigure(0, weight=1)
        self.charts_frame.grid_rowconfigure(1, weight=1)
        self.charts_frame.grid_columnconfigure(0, weight=1)
        self.charts_frame.grid_columnconfigure(1, weight=1)

        for p, config in self.plot_configs.items():
            if p == param:
                config["frame"].grid(row=0, column=0, rowspan=2, columnspan=2, padx=8, pady=8, sticky="nsew")
                
                # 显示工具栏
                config["toolbar_frame"].pack(side=tk.BOTTOM, fill=tk.X)
                config["canvas_widget"].pack(side=tk.TOP, fill="both", expand=True) 
                config["toolbar"].set_message(f"Zoom & Pan enabled for {param}")
            else:
                config["frame"].grid_forget()
                
    def refresh_limit_mark_section(self, plot_type, param):
        """清除并重建 Limits & Marks 标签页中指定参数的UI，以显示最新的 Marker"""
        # 找到 Limit & Mark Tab
        if plot_type not in self.limit_tabs:
            self.create_limit_mark_tab(plot_type)
            return

        tab_widget = self.limit_tabs[plot_type]
        # 找到 sub_notebook
        sub_notebook = tab_widget.winfo_children()[0]
        # 找到 param 对应的 frame
        param_index = self.params.index(param)
        frame = sub_notebook.winfo_children()[param_index]

        for widget in frame.winfo_children():
            widget.destroy()
            
        self.create_limit_mark_section(frame, plot_type, param)
        sub_notebook.select(frame) # 确保选中了当前的参数 tab

    def create_limit_mark_tab(self, plot_type):
        if plot_type in self.limit_tabs:
            return

        tab = tk.Frame(self.notebook, bg="#f0f2f5")
        self.notebook.add(tab, text=f"{plot_type} Limits & Marks")
        self.limit_tabs[plot_type] = tab

        sub_notebook = ttk.Notebook(tab)
        sub_notebook.pack(fill="both", expand=True, padx=15, pady=15)

        for param in self.params:
            frame = tk.Frame(sub_notebook, bg="#f0f2f5")
            sub_notebook.add(frame, text=f" {param} ")
            self.create_limit_mark_section(frame, plot_type, param)

    def create_limit_mark_section(self, parent, plot_type, param):
        # 创建滚动区
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

        # --- Limit Lines UI ---
        limit_container = tk.Frame(scrollable, bg="#f0f2f5")
        limit_container.pack(fill="x", pady=(0, 15))
        tk.Label(limit_container, text="Limit Lines", font=("sans-serif", 11, "bold"), bg="#f0f2f5", fg="#2c3e50").pack(anchor="w", padx=5)

        def draw_limit_line_frame(line_data):
            frame = tk.Frame(limit_container, bg="#ffffff", relief="groove", bd=1)
            frame.pack(fill="x", pady=4, padx=5)
            
            unit_map = {
                "Magnitude (dB)": ("dB", "-20", "-20"),
                "Phase (deg)": ("deg", "-180", "-180"),
                "Group Delay (ns)": ("ns", "10", "10") 
            }
            unit, default_lower, default_upper = unit_map.get(plot_type, ("?", "0", "0"))

            type_var = line_data.get("type", tk.StringVar(value="Max"))
            start_var = line_data.get("start", tk.StringVar(value="800"))
            stop_var = line_data.get("stop", tk.StringVar(value="900"))
            start_unit_var = line_data.get("start_unit", tk.StringVar(value="MHz"))
            stop_unit_var = line_data.get("stop_unit", tk.StringVar(value="MHz"))
            lower_var = line_data.get("lower", tk.StringVar(value=default_lower))
            upper_var = line_data.get("upper", tk.StringVar(value=default_upper))
            
            for var in [type_var, start_var, stop_var, lower_var, upper_var, start_unit_var, stop_unit_var]:
                var.trace_add("write", lambda *args: self.update_plots())

            tk.Label(frame, text="Type:", bg="#ffffff").grid(row=0, column=0, padx=3)
            ttk.Combobox(frame, textvariable=type_var, values=["Max", "Min"], width=6, state="readonly").grid(row=0, column=1, padx=3)

            tk.Label(frame, text="Start:", bg="#ffffff").grid(row=0, column=2, padx=3)
            tk.Entry(frame, textvariable=start_var, width=6).grid(row=0, column=3, padx=1)
            ttk.Combobox(frame, textvariable=start_unit_var, values=["MHz", "GHz"], width=4, state="readonly").grid(row=0, column=4, padx=1)

            tk.Label(frame, text="Stop:", bg="#ffffff").grid(row=0, column=5, padx=3)
            tk.Entry(frame, textvariable=stop_var, width=6).grid(row=0, column=6, padx=1)
            ttk.Combobox(frame, textvariable=stop_unit_var, values=["MHz", "GHz"], width=4, state="readonly").grid(row=0, column=7, padx=1)

            tk.Label(frame, text=f"Lower ({unit}):", bg="#ffffff").grid(row=0, column=8, padx=3)
            tk.Entry(frame, textvariable=lower_var, width=7).grid(row=0, column=9, padx=3)

            tk.Label(frame, text=f"Upper ({unit}):", bg="#ffffff").grid(row=0, column=10, padx=3)
            tk.Entry(frame, textvariable=upper_var, width=7).grid(row=0, column=11, padx=3)
            
            line_data.update({
                "frame": frame, "type": type_var, 
                "start": start_var, "stop": stop_var,
                "start_unit": start_unit_var, "stop_unit": stop_unit_var,
                "lower": lower_var, "upper": upper_var
            })

            def remove_and_update():
                frame.destroy()
                lines.remove(line_data)
                self.update_plots()

            tk.Button(frame, text="Remove", bg="#e74c3c", fg="white", command=remove_and_update).grid(row=0, column=12, padx=5)

        for line in lines:
            draw_limit_line_frame(line)

        def add_limit_and_draw():
            new_line = {}
            lines.append(new_line) # 先添加到列表，再绘制
            draw_limit_line_frame(new_line)
            self.update_plots()
        
        tk.Button(limit_container, text="Add Limit Line", bg="#3498db", fg="white", command=add_limit_and_draw).pack(pady=6)

        # --- Markers UI ---
        mark_container = tk.Frame(scrollable, bg="#f0f2f5")
        mark_container.pack(fill="x", pady=(15, 0))
        tk.Label(mark_container, text="Markers", font=("sans-serif", 11, "bold"), bg="#f0f2f5", fg="#2c3e50").pack(anchor="w", padx=5)

        def draw_marker_frame(mark_data):
            frame = tk.Frame(mark_container, bg="#f8f9fa", relief="solid", bd=1)
            frame.pack(fill="x", pady=3, padx=5)

            freq_var = mark_data.get("freq", tk.StringVar(value="100"))
            unit_var = mark_data.get("unit", tk.StringVar(value="MHz"))
            data_id_var = mark_data.get("data_id", tk.StringVar(value="1"))
            
            for var in [freq_var, unit_var, data_id_var]:
                var.trace_add("write", lambda *args: self.update_plots())

            tk.Label(frame, text=f"{mark_data['id']}:", bg="#f8f9fa", font=("sans-serif", 10, "bold"), fg="#c0392b").grid(row=0, column=0, padx=3)
            tk.Entry(frame, textvariable=freq_var, width=10).grid(row=0, column=1, padx=3)

            ttk.Combobox(frame, textvariable=unit_var, values=["MHz", "GHz"], width=6, state="readonly").grid(row=0, column=2, padx=3)

            tk.Label(frame, text="Ref ID:", bg="#f8f9fa").grid(row=0, column=3, padx=3)
            data_id_options = [str(d['id']) for d in self.datasets] if self.datasets else ["1"]
            ttk.Combobox(frame, textvariable=data_id_var, values=data_id_options, width=4, state="readonly").grid(row=0, column=4, padx=3)

            def remove_and_update():
                frame.destroy()
                marks.remove(mark_data)
                self.update_plots()

            tk.Button(frame, text="Remove", bg="#95a5a6", fg="white", command=remove_and_update).grid(row=0, column=5, padx=5)

            mark_data.update({"frame": frame, "freq": freq_var, "unit": unit_var, "data_id": data_id_var})

        for mark in marks:
            draw_marker_frame(mark)

        def add_mark_and_draw():
            current_count = self.data[plot_type]["mark_counter"][param]
            mark_id = f"M{current_count}"
            self.data[plot_type]["mark_counter"][param] += 1
            
            data_id_options = [str(d['id']) for d in self.datasets]
            default_data_id = data_id_options[0] if data_id_options else "1"

            new_mark = {
                "id": mark_id, 
                "freq": tk.StringVar(value="100"), 
                "unit": tk.StringVar(value="MHz"),
                "data_id": tk.StringVar(value=default_data_id)
            }
            marks.append(new_mark) # 先添加到列表，再绘制
            draw_marker_frame(new_mark)
            self.update_plots()

        marker_control_frame = tk.Frame(mark_container, bg="#f0f2f5")
        marker_control_frame.pack(fill="x", pady=6)

        tk.Button(marker_control_frame, text="Add Marker", bg="#2ecc71", fg="white", command=add_mark_and_draw).pack(side="left", padx=5)

        tk.Label(marker_control_frame, text="Legend Pos:", font=("sans-serif", 10), bg="#f0f2f5").pack(side="left", padx=(10, 5))
        
        pos_config = self.marker_pos_configs[plot_type][param]
        mode_var = pos_config["mode_var"]
        x_var = pos_config["x_var"]
        y_var = pos_config["y_var"]
        
        pos_combo = ttk.Combobox(marker_control_frame, textvariable=mode_var,
                     values=self.MARKER_POSITIONS,
                     state="readonly", width=12)
        pos_combo.pack(side="left", padx=5)

        custom_frame = tk.Frame(marker_control_frame, bg="#f0f2f5")
        
        tk.Label(custom_frame, text="X:", font=("sans-serif", 10), bg="#f0f2f5").pack(side="left", padx=(5, 2))
        x_entry = tk.Entry(custom_frame, textvariable=x_var, width=5)
        x_entry.pack(side="left")
        
        tk.Label(custom_frame, text="Y:", font=("sans-serif", 10), bg="#f0f2f5").pack(side="left", padx=(5, 2))
        y_entry = tk.Entry(custom_frame, textvariable=y_var, width=5)
        y_entry.pack(side="left")
        
        def on_mode_change(*args):
            if mode_var.get() == "Custom":
                custom_frame.pack(side="left", padx=(10, 5))
            else:
                custom_frame.pack_forget()
            
            self.update_plots()

        if mode_var.get() == "Custom":
            custom_frame.pack(side="left", padx=(10, 5))

        mode_var.trace_add("write", on_mode_change)
        x_var.trace_add("write", lambda *args: self.update_plots()) 
        y_var.trace_add("write", lambda *args: self.update_plots()) 

    def on_plot_type_change(self, *args):
        plot_type = self.plot_type.get()
        
        # 仅对支持 Limit/Mark 的图表创建或显示 Tab
        is_supported = plot_type in ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"]
        
        if is_supported and self.datasets:
            self.create_limit_mark_tab(plot_type)

        active_tab_found = False
        for key, tab_widget in self.limit_tabs.items():
            if key == plot_type:
                self.notebook.tab(tab_widget, state='normal')
                self.notebook.select(tab_widget)
                active_tab_found = True
            else:
                # 隐藏不相关的 Limits & Marks 标签页
                self.notebook.tab(tab_widget, state='hidden')
                
        # 确保在切换到 Smith Chart 或不支持的模式时，选中图表标签页
        if not active_tab_found or not is_supported:
            self.notebook.select(self.chart_tab)

        self.update_plots()

    def load_s2p(self):
        file_path = filedialog.askopenfilename(
            title="Select S2P File",
            filetypes=[("S2P files", "*.s2p"), ("All files", "*.*")]
        )
        if not file_path: return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            freq_unit = "Hz"
            s_format = None
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

            data_lines = []
            for line in lines:
                line = line.strip()
                if not line or line.startswith('!') or line.startswith('#'): continue
                numbers = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', line)
                if len(numbers) >= 9:
                    try:
                        data_lines.append([float(x) for x in numbers[:9]])
                    except: continue

            if not data_lines:
                raise ValueError("No valid data lines found")

            data = np.array(data_lines)
            freq = data[:, 0]
            if freq_unit == "GHz": freq *= 1e9
            elif freq_unit == "MHz": freq *= 1e6
            elif freq_unit == "KHz": freq *= 1e3

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
            
            new_dataset = {
                'id': self.next_dataset_id,
                'name': os.path.basename(file_path),
                'freq': freq,
                's_data': s_data,
                'format': s_format,
                'points': len(freq)
            }
            self.datasets.append(new_dataset)
            self.next_dataset_id += 1

            self.status_var.set(f"Loaded: {os.path.basename(file_path)} (ID {new_dataset['id']}) | Format: {s_format} | Total Files: {len(self.datasets)}")
            
            self.update_file_list_ui()
            self.update_plots()
            self.on_plot_type_change()

        except Exception as e:
            messagebox.showerror("Load Failed", f"Cannot parse S2P file:\n{e}")
            self.status_var.set("Load failed")


    def calculate_group_delay(self, freq, s):
        """
        Calculates group delay in nanoseconds (ns) using numerical differentiation.
        """
        if len(s) < 3:
            return np.array([]), freq / 1e9

        phase_rad = np.unwrap(np.angle(s))
        d_phase_rad = np.gradient(phase_rad)
        d_freq = np.gradient(freq)
        
        valid_indices = d_freq != 0
        group_delay_s = np.zeros_like(freq, dtype=float)
        # 避免除以零
        group_delay_s[valid_indices] = -d_phase_rad[valid_indices] / (2 * np.pi * d_freq[valid_indices])
        
        group_delay_ns = group_delay_s * 1e9
        freq_ghz = freq / 1e9
        
        return group_delay_ns, freq_ghz

    def update_plots(self):
        if not self.datasets:
            for param in self.params:
                config = self.plot_configs[param]
                config["ax"].clear()
                config["ax"].set_title(param)
                config["ax"].text(0.5, 0.5, "No Data Loaded", 
                                  transform=config["ax"].transAxes, ha='center', va='center', fontsize=12, color='gray')
                config["canvas"].draw()
            return
            
        plot_type = self.plot_type.get()
        
        # --- 1. 优化点：保存最大化图表的当前 X/Y 轴范围 ---
        saved_xlim = None
        saved_ylim = None
        if self.maximized_param:
            config = self.plot_configs[self.maximized_param]
            try:
                saved_xlim = config["ax"].get_xlim()
                saved_ylim = config["ax"].get_ylim()
            except:
                pass # 忽略错误，在无数据时可能会发生

        # 2. 绘制所有子图 (Plotting only, no layout or draw calls here)
        for param in self.params:
            config = self.plot_configs[param]
            # 仅在 widget 映射时绘制
            if config["canvas_widget"].winfo_ismapped():
                self.plot_parameter(config["ax"], config["fig"], config["canvas"], param, plot_type)
            
        # --- 3. 优化点：恢复最大化图表的 X/Y 轴范围 ---
        if self.maximized_param and saved_xlim is not None and saved_ylim is not None:
             config = self.plot_configs[self.maximized_param]
             config["ax"].set_xlim(saved_xlim)
             config["ax"].set_ylim(saved_ylim)
             
        # 4. 布局和图例处理
        if not self.maximized_param:
            main_fig = self.plot_configs["S11"]["fig"]
            
            # 清除旧的 Figure-level 图例 (它只存在于 S11 Figure 上)
            if main_fig.legends:
                 main_fig.legends[0].remove()
            
            handles, labels = [], []
            # 只有在非 Smith Chart 模式下才尝试获取图例（Smith Chart 的图例在轴内）
            if plot_type != "Smith Chart" and self.plot_configs["S11"]["ax"].lines:
                lines = self.plot_configs["S11"]["ax"].lines
                for line in lines:
                    # 使用 get_label() 来过滤掉非数据线（如限制线）
                    label = line.get_label()
                    if label and label not in labels and label.startswith("ID"): 
                        if label not in labels:
                             handles.append(line)
                             labels.append(label)

                # 绘制通用的顶部图例
                if labels:
                    main_fig.legend(handles, labels, 
                                    loc='upper center', 
                                    bbox_to_anchor=(0.5, 1.05), # 移动到顶部区域
                                    ncol=len(labels), 
                                    fontsize=9, 
                                    frameon=False) 
                    
            # A. 对所有 4 个 Figure 应用默认紧凑布局 (rect=[0, 0, 1, 1])
            for param in self.params:
                 self.plot_configs[param]["fig"].tight_layout(rect=[0, 0, 1, 1])
            
            # B. 重新对 S11 Figure 应用布局，以适应顶部的通用图例
            if labels: # 只有当图例存在时才调整 S11 的绘图区域
                main_fig.tight_layout(rect=[0, 0, 1, 0.9])
            
        else: # Maximized mode
             maximized_fig = self.plot_configs[self.maximized_param]["fig"]
             
             # 清除可能残留的 figure-level 图例
             if maximized_fig.legends:
                 maximized_fig.legends[0].remove()
                 
             # 对最大化的 Figure 应用紧凑布局
             maximized_fig.tight_layout()


        # 4. 强制重绘所有画布以显示更新后的内容和布局
        for param in self.params:
            config = self.plot_configs[param]
            # 仅重绘当前显示的 Canvas，节省资源
            if config["canvas_widget"].winfo_ismapped():
                config["canvas"].draw()


    def plot_parameter(self, ax, fig, canvas, param, plot_type):
        ax.clear()
        ax.set_title(param, fontsize=12, fontweight='bold')
        # 确保在 Smith 图时设置了 aspect，否则设置为 auto
        is_smith_chart = (plot_type == 'Smith Chart' and SMITH_AVAILABLE)
        ax.set_aspect('equal' if is_smith_chart else 'auto')

        marker_legend_text = []
        all_y_values = []
        all_freq_values = []
        
        # --- Plotting All Datasets ---
        for dataset in self.datasets:
            data_id = dataset['id']
            freq = dataset['freq']
            s = dataset['s_data'][param.lower()]
            color = COLOR_CYCLE[(data_id - 1) % len(COLOR_CYCLE)]
            
            if len(s) == 0: continue

            freq_ghz = freq / 1e9
            all_freq_values.extend(freq_ghz)
            
            # 曲线标签只显示 ID
            line_label = f"ID {data_id}"

            if plot_type == "Magnitude (dB)":
                y_data = 20 * np.log10(np.abs(s) + 1e-20)
                ax.plot(freq_ghz, y_data, color=color, linewidth=1.5, label=line_label)
                all_y_values.extend(y_data)
                ax.set_ylabel("Magnitude (dB)")
                ax.set_xlabel("Frequency (GHz)")

            elif plot_type == "Phase (deg)":
                y_data = np.unwrap(np.angle(s)) * 180 / np.pi
                ax.plot(freq_ghz, y_data, color=color, linewidth=1.5, label=line_label)
                all_y_values.extend(y_data)
                ax.set_ylabel("Phase (deg)")
                ax.set_xlabel("Frequency (GHz)")

            elif plot_type == "Group Delay (ns)":
                y_data, _ = self.calculate_group_delay(freq, s)
                ax.plot(freq_ghz, y_data, color=color, linewidth=1.5, label=line_label)
                all_y_values.extend(y_data)
                ax.set_ylabel("Group Delay (ns)")
                ax.set_xlabel("Frequency (GHz)")
            
            elif is_smith_chart:
                # Smith Chart 绘图
                ax.plot(np.real(s), np.imag(s), 'o-', color=color, markersize=3, linewidth=1, label=line_label)
        
        ax.grid(True, alpha=0.3)

        # --- Axis Scaling ---
        # 注意: 如果处于最大化状态，这些自动缩放的限制将在 update_plots 中被恢复
        if plot_type == "Magnitude (dB)":
            if all_y_values:
                y_max_data = np.max(all_y_values)
                buffer = 5.0
                ax.set_ylim(bottom=-100.0, top=max(y_max_data + buffer, 0.0))
            else:
                 ax.set_ylim(bottom=-100.0, top=0.0)

        elif plot_type in ["Phase (deg)", "Group Delay (ns)"]:
            if all_y_values:
                y_min_data = np.min(all_y_values)
                y_max_data = np.max(all_y_values)
                y_range = max(y_max_data - y_min_data, 1e-3)
                buffer = y_range * 0.05
                ax.set_ylim(y_min_data - buffer, y_max_data + buffer)

        elif is_smith_chart:
            ax.set_xlim(-1.1, 1.1)
            ax.set_ylim(-1.1, 1.1)
            # 在 clear() 之后重新添加圆圈
            circle = plt.Circle((0, 0), 1, fill=False, color='black', linewidth=1)
            ax.add_patch(circle)
            ax.set_aspect('equal') # 确保重新设置了纵横比
            ax.set_xlabel("Real Axis")
            ax.set_ylabel("Imaginary Axis")


        # --- Limit Line Logic ---
        if plot_type in self.data and self.datasets: 
            freq_ghz_all = np.array(all_freq_values)
            
            for line in self.data[plot_type]["limit_lines"][param]:
                try:
                    start_val = float(line["start"].get())
                    start_unit = line["start_unit"].get()
                    stop_val = float(line["stop"].get())
                    stop_unit = line["stop_unit"].get()

                    start_ghz = start_val / 1000 if start_unit == "MHz" else start_val
                    stop_ghz = stop_val / 1000 if stop_unit == "MHz" else stop_val

                    lower = float(line["lower"].get())
                    upper = float(line["upper"].get())
                    ltype = line["type"].get()

                    if all_freq_values:
                        min_f_ghz = max(min(all_freq_values), start_ghz)
                        max_f_ghz = min(max(all_freq_values), stop_ghz)
                        
                        if min_f_ghz >= max_f_ghz: continue
                        
                        if ltype == "Max":
                            ax.hlines(upper, min_f_ghz, max_f_ghz, colors='red', linestyles='--', linewidth=1.5, zorder=4)
                        else:
                            ax.hlines(lower, min_f_ghz, max_f_ghz, colors='green', linestyles='--', linewidth=1.5, zorder=4)
                except: pass

        # --- Marker Logic (Optimized for multiple traces and labels) ---
        unit_label = {"Magnitude (dB)": "dB", "Phase (deg)": "°", "Group Delay (ns)": "ns"}.get(plot_type, "")
        marker_legend_text = []
        is_freq_added = False

        if plot_type in self.data and self.datasets:
            for mark in self.data[plot_type]["marks"][param]:
                try:
                    # 1. Get Marker Frequency
                    f_str = mark["freq"].get()
                    unit = mark["unit"].get()
                    f = float(f_str)
                    freq_val = f * 1e6 if unit == "MHz" else f * 1e9
                    freq_show = f"{f_str}{unit}"
                    
                    # 2. Iterate through ALL datasets to get values and plot points
                    for dataset in self.datasets:
                        data_id = dataset['id']
                        s_data = dataset['s_data'][param.lower()]
                        freq = dataset['freq']
                        color = COLOR_CYCLE[(data_id - 1) % len(COLOR_CYCLE)]

                        # Calculate Y data for the current dataset
                        if plot_type == "Magnitude (dB)":
                            data_array = 20 * np.log10(np.abs(s_data) + 1e-20)
                        elif plot_type == "Phase (deg)":
                            data_array = np.unwrap(np.angle(s_data)) * 180 / np.pi
                        elif plot_type == "Group Delay (ns)":
                            data_array, _ = self.calculate_group_delay(freq, s_data)
                        else: 
                            continue 
                        
                        # Find closest index
                        idx = np.argmin(np.abs(freq - freq_val))
                        if idx >= len(data_array): continue
                        
                        val = data_array[idx]
                        val_show = f"{val:.3f}{unit_label}"
                        x_pt = freq[idx] / 1e9 
                        y_pt = val
                        
                        # 3. Add to Legend Text (Marker ID + Trace ID + Value)
                        if not is_freq_added:
                             marker_legend_text.append(f"{mark['id']} Freq: {freq_show}") # 统一的频率值放在头部
                             is_freq_added = True

                        # 附加所有 ID 的 Marker 值
                        marker_legend_text.append(f"{mark['id']} (ID {data_id}): {val_show}")
                        
                        # 4. Plot Marker Point on the current trace (the 'X' symbol)
                        # 使用 'X' 符号标记，使用曲线颜色
                        ax.plot(x_pt, y_pt, 'X', markerfacecolor='none', markeredgecolor=color, markersize=7, markeredgewidth=1.5, zorder=5)

                        # 5. Place Annotation (Marker Label) - 优化点: 移除 ref_data_id 限制，为所有曲线放置 Marker 标签
                        ax.annotate(mark['id'], xy=(x_pt, y_pt), xytext=(5, 5),
                                    textcoords='offset points', fontsize=9, color=color, # 使用曲线颜色
                                    arrowprops=dict(arrowstyle="-", connectionstyle="arc3,rad=.2", color=color, lw=0.5), # 使用曲线颜色
                                    zorder=6)
                            
                except Exception as e:
                    # print(f"Error drawing marker: {e}") # for debugging
                    pass
        
        # --- Marker/Legend Position ---
        if is_smith_chart:
            marker_legend_text = [] # Smith Chart 模式下，不显示传统的文本图例，因为它会遮挡图

        pos_map = {
            "Top Left": (0.05, 0.95, 'left', 'top'),
            "Bottom Left": (0.05, 0.05, 'left', 'bottom'),
            "Top Right": (0.95, 0.95, 'right', 'top'),
            "Bottom Right": (0.95, 0.05, 'right', 'bottom'),
            "Center": (0.5, 0.5, 'center', 'center'),
        }
        
        current_config = self.marker_pos_configs.get(plot_type, {}).get(param)
        x, y, ha, va = pos_map["Top Right"] 

        if current_config:
            current_mode = current_config["mode_var"].get()
            if current_mode in pos_map:
                x, y, ha, va = pos_map[current_mode]
            elif current_mode == "Custom":
                try:
                    custom_x = float(current_config["x_var"].get())
                    custom_y = float(current_config["y_var"].get())
                    x = np.clip(custom_x, 0.0, 1.0)
                    y = np.clip(custom_y, 0.0, 1.0)
                    ha = 'left' if x < 0.33 else ('right' if x > 0.67 else 'center')
                    va = 'bottom' if y < 0.33 else ('top' if y > 0.67 else 'center')
                except ValueError: pass

        if marker_legend_text:
            # 标记图例文本
            marker_legend_str = "\n".join(marker_legend_text)
            
            ax.text(x, y, marker_legend_str, transform=ax.transAxes,
                    fontsize=9, verticalalignment=va, horizontalalignment=ha,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.9),
                    linespacing=1.2, zorder=7)

        ax.relim()
        
    def clear_all_datasets(self):
        if messagebox.askyesno("Clear Data", f"Are you sure to clear all {len(self.datasets)} loaded datasets?"):
            self.datasets = []
            self.next_dataset_id = 1
            self.maximized_param = None
            
            self.restore_plots_layout()
            self.update_plots()
            
            self.update_file_list_ui()
            self.status_var.set("All data cleared. Please load S2P file(s)...")

    def reset_app(self):
        if messagebox.askyesno("Reset", "Reset to initial state?\nAll data, markers and limits will be cleared."):
            self.clear_all_datasets() 
            self.serial_var.set("SN-001")

            for mode in self.marker_pos_configs:
                for param in self.marker_pos_configs[mode]:
                    self.marker_pos_configs[mode][param]["mode_var"].set("Top Right")
                    self.marker_pos_configs[mode][param]["x_var"].set("0.5")
                    self.marker_pos_configs[mode][param]["y_var"].set("0.5")

            for mode in self.data:
                for param in self.data[mode]["limit_lines"]:
                    # 清除 UI 元素
                    for line in self.data[mode]["limit_lines"][param][:]:
                        if "frame" in line and line["frame"].winfo_exists():
                            line["frame"].destroy()
                    self.data[mode]["limit_lines"][param].clear()
                    self.data[mode]["mark_counter"][param] = 1
                for param in self.data[mode]["marks"]:
                    # 清除 UI 元素
                    for mark in self.data[mode]["marks"][param][:]:
                        if "frame" in mark and mark["frame"].winfo_exists():
                            mark["frame"].destroy()
                    self.data[mode]["marks"][param].clear()

            for tab_widget in self.limit_tabs.values():
                self.notebook.tab(tab_widget, state='hidden')

            self.status_var.set("Reset complete. Please load an S2P file.")
            messagebox.showinfo("Reset", "Application reset to initial state.")
            
    def _copy_plot_content(self, ax_old, ax_new):
        """Helper to copy all content from one axes to another"""
        
        plot_type = self.plot_type.get()
        is_smith_chart = (plot_type == 'Smith Chart' and SMITH_AVAILABLE)
        
        # 复制纵横比设置
        if is_smith_chart:
            ax_new.set_aspect('equal')
        else:
            ax_new.set_aspect('auto')
        
        for line in ax_old.lines:
            x_data, y_data = line.get_data()
            # 确保复制了 ID 标签
            ax_new.plot(x_data, y_data, color=line.get_color(), linewidth=line.get_linewidth(),
                        marker=line.get_marker(), markersize=line.get_markersize(), linestyle=line.get_linestyle(),
                        markeredgewidth=line.get_markeredgewidth(), # 复制 Mark 边的宽度
                        markerfacecolor=line.get_markerfacecolor(), # 复制 Mark 面的颜色
                        markeredgecolor=line.get_markeredgecolor(), # 复制 Mark 边的颜色
                        zorder=line.get_zorder(), label=line.get_label()) 

        for patch in ax_old.patches:
            # 复制圆圈
            if isinstance(patch, plt.Circle):
                 ax_new.add_patch(plt.Circle((0, 0), 1, fill=False, color='black', linewidth=1))
            else:
                 # 复制其他 patch 
                 ax_new.add_patch(patch.__class__(**patch.properties()))

        for ann_old in ax_old.findobj(plt.Annotation):
            try:
                ann_text = ann_old.get_children()[0].get_text()
                # 仅复制 Marker 的 Annotation
                if not ann_text.startswith('M'): continue

                arrow_props = {} 
                if ann_old.arrow_patch:
                    try:
                        # 复制箭头属性
                        arrow_props.update(ann_old.arrow_patch.properties().copy())
                        conn_style_raw = ann_old.arrow_patch.get_connectionstyle()
                        if conn_style_raw:
                            arrow_props['connectionstyle'] = str(conn_style_raw)
                        
                        # 确保箭头样式被复制
                        if 'arrowstyle' not in arrow_props:
                             arrow_props['arrowstyle'] = '-'

                    except: pass
                
                # 复制 Marker Annotation，包括颜色
                ax_new.annotate(ann_text, xy=ann_old.xy, xytext=ann_old.get_position(),
                                textcoords=ann_old.get_textcoords(),
                                fontsize=ann_old.get_children()[0].get_fontsize(),
                                color=ann_old.get_children()[0].get_color(), # 复制 Marker 标签颜色
                                arrowprops=arrow_props, zorder=ann_old.get_zorder())
            except Exception as e: pass

        ax_new.set_title(ax_old.get_title())
        ax_new.set_xlabel(ax_old.get_xlabel())
        ax_new.set_ylabel(ax_old.get_ylabel())
        ax_new.grid(ax_old.get_xgridlines())
        ax_new.set_xlim(ax_old.get_xlim())
        
        ax_new.set_ylim(ax_old.get_ylim())

        for txt in ax_old.texts:
            if txt.get_bbox_patch() is not None:
                # 复制 Marker Legend 文本框
                ax_new.text(txt.get_position()[0], txt.get_position()[1], txt.get_text(),
                            transform=ax_new.transAxes,
                            fontsize=txt.get_fontsize(),
                            verticalalignment=txt.get_verticalalignment(),
                            horizontalalignment=txt.get_horizontalalignment(),
                            bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.9),
                            linespacing=1.2, zorder=7)
            else:
                # 复制 Hlines (Limit Lines)
                if ax_old.get_hlines():
                    for hline in ax_old.get_hlines():
                         ax_new.hlines(hline.get_ydata(), hline.get_segments()[0][0][0], hline.get_segments()[0][0][1], 
                                       colors=hline.get_colors(), linestyles=hline.get_linestyles(), linewidth=hline.get_linewidth(), zorder=hline.get_zorder())


        if not is_smith_chart:
            ax_new.relim()
            ax_new.autoscale_view()
            
    def generate_combined_image(self):
        if not self.datasets: return None
        serial = self.serial_var.get().strip() or "Unknown"
        
        self.update_plots() # 确保在最终保存前，所有图表都已最新绘制

        if self.maximized_param:
            param = self.maximized_param
            config = self.plot_configs[param]
            fig_old = config["fig"]
            
            combined_fig = plt.Figure(figsize=(10, 7), dpi=120)
            combined_fig.suptitle(f"{param} {self.plot_type.get()} | Serial Number: {serial}", fontsize=14, fontweight='bold', y=0.98)
            ax_new = combined_fig.add_subplot(111)

            self._copy_plot_content(ax_old=fig_old.axes[0], ax_new=ax_new)
            
            combined_fig.tight_layout(rect=[0, 0.03, 1, 0.95])
        else:
            combined_fig = plt.Figure(figsize=(14, 10), dpi=120)
            combined_fig.suptitle(f"S-Parameter Analysis ({self.plot_type.get()}) | Serial Number: {serial}", fontsize=16, fontweight='bold', y=0.98)

            param_list = ["S11", "S21", "S12", "S22"]
            for i, param in enumerate(param_list):
                config = self.plot_configs[param]
                ax_old = config["fig"].axes[0]
                ax_new = combined_fig.add_subplot(2, 2, i+1)
                
                self._copy_plot_content(ax_old=ax_old, ax_new=ax_new)

            # 复制顶部通用图例
            main_fig = self.plot_configs["S11"]["fig"]
            if main_fig.legends:
                # 重新在新的 Figure 上创建图例
                handles = main_fig.legends[0].legendHandles
                labels = [text.get_text() for text in main_fig.legends[0].get_texts()]

                if labels:
                    combined_fig.legend(handles, labels, 
                                        loc='upper center', 
                                        bbox_to_anchor=(0.5, 1.05),
                                        ncol=len(labels), 
                                        fontsize=10, 
                                        frameon=False)
            
            combined_fig.tight_layout(rect=[0, 0.03, 1, 0.95])
        
        buf = io.BytesIO()
        combined_fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close(combined_fig)
        return Image.open(buf)

    def copy_all_charts(self):
        img = self.generate_combined_image()
        if img:
            state_text = f"Maximized {self.maximized_param}" if self.maximized_param else "4 plots merged"
            success = copy_image_to_clipboard(img)
            if success:
                messagebox.showinfo("Copy Success", f"{state_text} + Serial Number\nCopied to clipboard!")
            else:
                messagebox.showwarning("Copy Failed", "Saved to local file")

    def save_chart(self):
        img = self.generate_combined_image()
        if not img: return
        
        serial = self.serial_var.get().strip() or "SN-Unknown"
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") 
        plot_type_abbr = self.plot_type.get().split(' ')[0]

        if self.maximized_param:
            default_name = f"{serial}_{timestamp}_{self.maximized_param}_{plot_type_abbr}_Maximized"
        else:
            default_name = f"{serial}_{timestamp}_{plot_type_abbr}_4Plot_Combined"

        file_path = filedialog.asksaveasfilename(
            title="Save as Image",
            defaultextension=".png",
            initialfile=default_name,
            filetypes=[("PNG File", "*.png"), ("JPG File", "*.jpg"), ("All Files", "*.*")]
        )
        if file_path:
            fmt = "JPEG" if file_path.lower().endswith(".jpg") else "PNG"
            img.save(file_path, fmt)
            messagebox.showinfo("Save Success", f"Image saved as:\n{file_path}")

if __name__ == "__main__":
    root = tk.Tk()
    app = SViewGUI(root)
    root.mainloop()
