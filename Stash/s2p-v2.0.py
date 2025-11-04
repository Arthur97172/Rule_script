# -*- coding: utf-8 -*-
"""
S-View (modified) - Integrates 'Display Mode' with Normal / Max modes.
Author: Arthur Gu (modified)
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.ticker import MaxNLocator
import os
import re
import platform
import matplotlib.font_manager as fm
import warnings
from PIL import Image
import io
# FIX 1: 导入 collections 模块
import matplotlib.collections as mcollections 

warnings.filterwarnings("ignore", category=UserWarning)

# 支持 Smith 图 - 已移除 skrf 依赖
SMITH_AVAILABLE = False  # 显式设置为 False

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
COLOR_CYCLE = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']

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
        self.root.title("S-View Created By Arthur Gu | V2.0")
        self.root.geometry("1450x980")
        self.root.resizable(True, True)
        self.root.minsize(1150, 780)
        self.root.configure(bg="#f0f2f5")

        self.params = ["S11", "S21", "S12", "S22"]
        # 允许 Center
        self.MARKER_POSITIONS = ["Top Left", "Top Right", "Bottom Left", "Bottom Right", "Center", "Custom"] 
        self.plot_configs = {}
        self.limit_tabs = {}

        # 初始化核心状态
        self._initialize_state()

        # 创建 UI
        self.setup_ui()
        self.plot_type.trace("w", self.on_plot_type_change)
        self.display_mode.trace("w", self.on_display_mode_change)

    def _initialize_state(self):
        self.datasets = []
        self.next_dataset_id = 1
        self.current_img = None
        self.maximized_param = None

        self.serial_var = tk.StringVar(value="SN-001")
        self.plot_type = tk.StringVar(value="Magnitude (dB)")
        self.display_mode = tk.StringVar(value="Normal")  # 新增：Normal / Max

        SUPPORTED_PLOT_TYPES = ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"]
        
        # 初始化 Marker 位置配置
        self.marker_pos_configs = {
            pt: {
                p: {
                    "mode_var": tk.StringVar(value="Top Right"),
                    "x_var": tk.StringVar(value="0.5"),
                    "y_var": tk.StringVar(value="0.5")
                } for p in self.params
            } for pt in SUPPORTED_PLOT_TYPES
        }

        # 新增：Max 模式 Marker 位置配置（per plot_type，共享）
        self.max_marker_pos_configs = {
            pt: {
                "mode_var": tk.StringVar(value="Top Right"),
                "x_var": tk.StringVar(value="0.5"),
                "y_var": tk.StringVar(value="0.5")
            } for pt in SUPPORTED_PLOT_TYPES
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
        self.notebook.add(self.chart_tab, text="S-Parameter Plots")
        self.setup_chart_tab()

        self.create_data_information_tab()
        self.create_limit_mark_tab(self.plot_type.get())

        # 右侧垂直控制区
        vertical_control_frame = tk.Frame(content_frame, bg="#f0f2f5", width=300)
        vertical_control_frame.grid(row=0, column=1, sticky="ns")

        control_stack_frame = tk.Frame(vertical_control_frame, bg="#f0f2f5")
        control_stack_frame.pack(fill="x", side="top")

        # Serial Number
        sn_group = tk.Frame(control_stack_frame, bg="#f0f2f5")
        sn_group.pack(fill="x", pady=(5, 5), padx=5)
        tk.Label(sn_group, text="Serial Number:", font=("sans-serif", 12, "bold"), bg="#f0f2f5").pack(padx=5)
        tk.Entry(sn_group, textvariable=self.serial_var, font=("sans-serif", 12), width=18).pack(fill="x", padx=5)

        # File Operations
        file_ops_group = tk.LabelFrame(control_stack_frame, text="File Operations", font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        file_ops_group.pack(fill="x", padx=5, pady=5)
        tk.Button(file_ops_group, text="Load S2P File", font=("sans-serif", 12, "bold"),
                  bg="#4CAF50", fg="white", relief="flat", padx=10, pady=8, command=self.load_s2p).pack(fill="x", padx=5, pady=5)
        tk.Button(file_ops_group, text="Clear Data", font=("sans-serif", 12),
                  bg="#e74c3c", fg="white", relief="flat", padx=10, pady=8, command=self.clear_all_datasets).pack(fill="x", padx=5, pady=5)
        tk.Button(file_ops_group, text="Reset App", font=("sans-serif", 12, "bold"),
                  bg="#3F51B5", fg="white", relief="flat", padx=10, pady=8, command=self.reset_application).pack(fill="x", padx=5, pady=5)

        # Plot Type
        plot_type_group = tk.LabelFrame(control_stack_frame, text="Plot Type", font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        plot_type_group.pack(fill="x", padx=5, pady=5)
        plot_values = ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"]
        plot_combo = ttk.Combobox(plot_type_group, textvariable=self.plot_type, values=plot_values, state="readonly")
        plot_combo.pack(fill="x", padx=5, pady=5)

        # Display Mode (新增)
        display_mode_group = tk.LabelFrame(control_stack_frame, text="Display Mode", font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        display_mode_group.pack(fill="x", padx=5, pady=5)
        display_combo = ttk.Combobox(display_mode_group, textvariable=self.display_mode, values=["Normal", "Max"], state="readonly")
        display_combo.pack(fill="x", padx=5, pady=(8, 5))

        # Max 模式：显示隐藏复选框（放在 Display Mode 下方，分两行显示）
        self.cb_frame = tk.Frame(display_mode_group, bg="#f0f2f5")  # <-- 改为 self.cb_frame 以便动态控制显示/隐藏
        self.cb_frame.pack_forget() # 默认隐藏
        tk.Label(self.cb_frame, text="Show Params:", bg="#f0f2f5").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))

        # 两行两列布局
        param_grid = [["S11", "S21"], ["S12", "S22"]]
        for r, row_params in enumerate(param_grid, start=1):
            for c, p in enumerate(row_params):
                chk = tk.Checkbutton(self.cb_frame, text=p, variable=self.show_param_vars[p], bg="#f0f2f5", anchor="w")
                chk.grid(row=r, column=c, sticky="w", padx=(5, 15))

        # Refresh
        tk.Button(control_stack_frame, text="Refresh Plots", font=("sans-serif", 12, "bold"),
                  bg="#FF9800", fg="white", relief="flat", padx=10, pady=8, command=self.update_plots).pack(fill="x", padx=5, pady=5)

        # Chart ops
        chart_ops_group = tk.LabelFrame(control_stack_frame, text="Chart Output", font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        chart_ops_group.pack(fill="x", padx=5, pady=5)
        tk.Button(chart_ops_group, text="Copy Plots", font=("sans-serif", 12, "bold"),
                  bg="#FF5722", fg="white", relief="flat", padx=10, pady=8, command=self.copy_all_charts).pack(fill="x", padx=5, pady=5)
        tk.Button(chart_ops_group, text="Save as Image", font=("sans-serif", 12),
                  bg="#9C27B0", fg="white", relief="flat", padx=10, pady=8, command=self.save_chart).pack(fill="x", padx=5, pady=5)

        # Legend frame at bottom
        self.legend_frame = tk.LabelFrame(vertical_control_frame, text="Legend (Data ID)", font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        self.legend_frame.pack(fill="x", padx=5, pady=(5, 0), side="bottom")
        self.legend_content = tk.Frame(self.legend_frame, bg="#f0f2f5")
        self.legend_content.pack(fill="x", padx=5, pady=5)

        # Status bar
        self.status_var = tk.StringVar(value="Please load S2P file(s)...")
        tk.Label(main_frame, textvariable=self.status_var, font=("sans-serif", 10),
                 bg="#e0e0e0", anchor="w", relief="sunken").pack(side="bottom", fill="x", pady=(10, 0))
        tk.Label(main_frame, text="© 2025 S-View | Created By Arthur Gu", font=("sans-serif", 9),
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

            fig = plt.Figure(figsize=(5, 4), dpi=100)
            ax = fig.add_subplot(111)
            canvas = FigureCanvasTkAgg(fig, frame)
            canvas_widget = canvas.get_tk_widget()
            canvas_widget.pack(fill="both", expand=True)

            toolbar_frame = tk.Frame(frame)
            toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)
            toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
            toolbar.update()

            self.plot_configs[param] = {
                "frame": frame, "fig": fig, "ax": ax, "canvas": canvas, "canvas_widget": canvas_widget,
                "toolbar_frame": toolbar_frame, "toolbar": toolbar
            }
            canvas_widget.bind("<Double-1>", lambda event, p=param: self.toggle_maximize(p))

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
        self.max_canvas.draw()

    def add_marker_on_click_combined(self, mpl_event):
        # 在 Combined 图中点击添加 Marker：为每个被选中的 param 创建 marker
        if not self.datasets: return
        if mpl_event.inaxes is None or mpl_event.button != 1 or mpl_event.xdata is None:
            return
        x_mhz = mpl_event.xdata
        # Convert MHz to Hz (freq stored in Hz)
        click_hz = x_mhz * 1e6
        plot_type = self.plot_type.get()
        # For each param shown, add marker at nearest frequency
        for param in self.params:
            if not self.show_param_vars[param].get():
                continue
            # find nearest freq from first dataset reference
            ref_freq = self.datasets[0]['freq']
            idx = np.argmin(np.abs(ref_freq - click_hz))
            closest_freq_hz = ref_freq[idx]
            if closest_freq_hz >= 3e9:
                f_val = closest_freq_hz / 1e9
                f_unit = "GHz"
            else:
                f_val = closest_freq_hz / 1e6
                f_unit = "MHz"
            data_id_options = [str(d['id']) for d in self.datasets]
            default_data_id = data_id_options[0] if data_id_options else "1"
            new_mark = {
                "id": "TEMP",
                "freq": tk.StringVar(value=f"{f_val:.3f}"),
                "unit": tk.StringVar(value=f_unit),
                "data_id": tk.StringVar(value=default_data_id)
            }
            self.data[plot_type]["marks"][param].append(new_mark)
            # reindex and refresh UI
            self._reindex_markers_and_refresh_ui(plot_type, param)
        self.update_plots()
        self.status_var.set(f"Marker added at {x_mhz:.3f} MHz on combined view for visible params.")

    # ---------- Layout switchers (Normal <-> Max) ----------
    def on_display_mode_change(self, *args):
        mode = self.display_mode.get()
        # 动态显示或隐藏 Show Params 复选框区域
        if hasattr(self, "cb_frame"):
            if mode == "Max":
                self.cb_frame.pack(fill="x", padx=5, pady=(2, 8))
            else:
                self.cb_frame.pack_forget()

        # 新增：更新 Marker 控件可见性
        self.update_marker_controls_visibility()

        if mode == "Max":
            self.enter_max_mode()
        else:
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
        pos_config = self.marker_pos_configs[plot_type][param]
        mode = pos_config["mode_var"].get()
        custom_frame = self.data[plot_type]["ui_refs"][param]["legend_controls"]["custom_frame"]
        if mode == "Custom":
            custom_frame.pack(side="left", padx=(10, 5))
        else:
            custom_frame.pack_forget()

    def on_max_mode_change(self, plot_type):
        mode = self.max_marker_pos_configs[plot_type]["mode_var"].get()
        for param in self.params:
            if plot_type in self.data and param in self.data[plot_type]["ui_refs"]:
                custom_frame = self.data[plot_type]["ui_refs"][param]["max_controls"]["custom_frame"]
                if mode == "Custom":
                    custom_frame.pack(side="left", padx=(10, 5))
                else:
                    custom_frame.pack_forget()
                break  # 只需更新一个，共享

    def enter_max_mode(self):
        # Hide individual param frames, create combined frame if not exists
        # Hide existing frames
        for p, cfg in self.plot_configs.items():
            cfg["frame"].grid_forget()

        # Create combined frame if not exists
        if not self.max_frame:
            self.max_frame = tk.LabelFrame(self.charts_frame, text=" Combined S-Parameters (Max) ", font=("sans-serif", 12, "bold"), bg="#f0f2f5")
            self.max_frame.grid(row=0, column=0, rowspan=2, columnspan=2, sticky="nsew", padx=8, pady=8)
            # create figure
            self.max_fig = plt.Figure(figsize=(10, 7), dpi=120)
            self.max_ax = self.max_fig.add_subplot(111)
            self.max_canvas = FigureCanvasTkAgg(self.max_fig, self.max_frame)
            self.max_canvas_widget = self.max_canvas.get_tk_widget()
            self.max_canvas_widget.pack(fill="both", expand=True)
            # toolbar
            toolbar_frame = tk.Frame(self.max_frame)
            toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)
            self.max_toolbar = NavigationToolbar2Tk(self.max_canvas, toolbar_frame)
            self.max_toolbar.update()
            # connect events
            cid_click = self.max_fig.canvas.mpl_connect('button_press_event', lambda e: self.add_marker_on_click_combined(e))
            cid_scroll = self.max_fig.canvas.mpl_connect('scroll_event', lambda e: self.on_scroll_zoom_combined(e))
            cid_motion = self.max_fig.canvas.mpl_connect('motion_notify_event', lambda e: self._on_mouse_move_custom(e, 'COMBINED'))
            self.max_cids = {'click': cid_click, 'scroll': cid_scroll, 'motion': cid_motion}
        else:
            # re-grid it
            self.max_frame.grid(row=0, column=0, rowspan=2, columnspan=2, sticky="nsew", padx=8, pady=8)
            # rebind events if needed
            if self.max_fig and not self.max_cids:
                cid_click = self.max_fig.canvas.mpl_connect('button_press_event', lambda e: self.add_marker_on_click_combined(e))
                cid_scroll = self.max_fig.canvas.mpl_connect('scroll_event', lambda e: self.on_scroll_zoom_combined(e))
                cid_motion = self.max_fig.canvas.mpl_connect('motion_notify_event', lambda e: self._on_mouse_move_custom(e, 'COMBINED'))
                self.max_cids = {'click': cid_click, 'scroll': cid_scroll, 'motion': cid_motion}

    def exit_max_mode(self):
        # destroy or hide combined frame and restore individual frames
        if self.max_frame:
            # disconnect events
            try:
                for k, cid in self.max_cids.items():
                    self.max_fig.canvas.mpl_disconnect(cid)
            except:
                pass
            self.max_cids = {}
            self.max_frame.grid_forget()
        # restore individual frames layout
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
            for key in ('cid_click', 'cid_scroll', 'cid_mouse_move'):
                if key in config:
                    try:
                        config["fig"].canvas.mpl_disconnect(config[key])
                    except:
                        pass
                    config.pop(key, None)

        self.charts_frame.update_idletasks()

    def get_max_mode_color(self, data_id, param):
        """ 为 Max 模式生成基于 ID 和 param 的独特颜色 """
        param_index = self.params.index(param)
        color_index = ((data_id - 1) * len(self.params) + param_index) % len(COLOR_CYCLE)
        return COLOR_CYCLE[color_index]

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
                legend_items[data_id] = {'label': f"ID {data_id}: {file_name_only}", 'color': color}
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
            self.status_var.set("No data loaded. Please load S2P file(s)...")
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

    def plot_combined(self):
        # Plot selected parameters on self.max_ax
        if not self.max_ax or not self.max_canvas:
            return
        ax = self.max_ax
        ax.clear()
        ax.set_title("Combined: " + self.plot_type.get(), fontsize=14, fontweight='bold')
        plot_type = self.plot_type.get()
        all_y_values = []
        all_freq_values = []
        
        # For each selected parameter, draw a line per dataset
        for p in self.params:
            if not self.show_param_vars[p].get():
                continue
            for dataset in self.datasets:
                data_id = dataset['id']
                freq = dataset['freq']
                s = dataset['s_data'][p.lower()]
                # 新增：使用基于 ID 和 param 的颜色
                color = self.get_max_mode_color(data_id, p)
                if len(s) == 0:
                    continue
                freq_mhz = freq / 1e6
                if plot_type == "Magnitude (dB)":
                    y_data = 20 * np.log10(np.abs(s) + 1e-20)
                elif plot_type == "Phase (deg)":
                    y_data = np.unwrap(np.angle(s)) * 180 / np.pi
                elif plot_type == "Group Delay (ns)":
                    y_data, freq_mhz = self.calculate_group_delay(freq, s)
                else:
                    y_data = np.zeros_like(freq_mhz)
                ax.plot(freq_mhz, y_data, color=color, linewidth=1.5, label=f"{p} ID {data_id}")
                all_y_values.extend(y_data)
                all_freq_values.extend(freq_mhz)

        # --- Limit lines drawing for Combined Plot ---
        if plot_type in self.data and self.datasets:
            for p in self.params:
                # Only draw limit lines for parameters that are set to show
                if not self.show_param_vars[p].get():
                    continue

                for line in self.data[plot_type]["limit_lines"][p]:
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

                        # Determine the frequency range for the plot
                        if all_freq_values:
                            min_f_mhz = max(min(all_freq_values), start_mhz)
                            max_f_mhz = min(max(all_freq_values), stop_mhz)

                            if min_f_mhz < max_f_mhz:
                                # Use the color-coding found in plot_parameter
                                color_to_use = 'red' if ltype == "Max" else 'green'
                                value_to_use = upper if ltype == "Max" else lower

                                ax.hlines(value_to_use, min_f_mhz, max_f_mhz, colors=color_to_use, 
                                          linestyles='--', linewidth=1.5, zorder=4,
                                          label=f"Limit ({p} {ltype})") # Added label for potential legend

                    except Exception as e:
                        # Silently skip if line data is invalid
                        pass
        # --- End Limit lines drawing ---
        
        ax.set_xlabel("Frequency (MHz)")
        
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

        ax.grid(True, alpha=0.3)
        if all_y_values:
            y_min = np.min(all_y_values)
            y_max = np.max(all_y_values)
            buffer = max(5.0, (y_max - y_min) * 0.05)
            ax.set_ylim(y_min - buffer, y_max + buffer)
        ax.xaxis.set_major_locator(MaxNLocator(10))
        ax.yaxis.set_major_locator(MaxNLocator(10))
        
        # draw markers that correspond to visible params
        marker_legend_text = []
        if plot_type in self.data:
            for p in self.params:
                if not self.show_param_vars[p].get(): continue
                for mark in self.data[plot_type]["marks"][p]:
                    try:
                        f_str = mark["freq"].get()
                        unit = mark["unit"].get()
                        f = float(f_str)
                        if unit == "GHz":
                            freq_val = f * 1e9
                        elif unit == "MHz":
                            freq_val = f * 1e6
                        else:
                            freq_val = f
                        for dataset in self.datasets:
                            data_id = dataset['id']
                            s_data = dataset['s_data'][p.lower()]
                            freq = dataset['freq']
                            
                            # Calculate data_array based on plot_type
                            if plot_type == "Magnitude (dB)":
                                data_array = 20 * np.log10(np.abs(s_data) + 1e-20)
                            elif plot_type == "Phase (deg)":
                                data_array = np.unwrap(np.angle(s_data)) * 180 / np.pi
                            elif plot_type == "Group Delay (ns)":
                                data_array, freq_mhz_gd = self.calculate_group_delay(freq, s_data)
                            else:
                                continue
                            
                            idx = np.argmin(np.abs(freq - freq_val))
                            if idx >= len(data_array): continue
                            
                            val = data_array[idx]
                            x_pt = freq[idx] / 1e6 # Frequency in MHz
                            y_pt = val
                            
                            # 新增：使用基于 ID 和 param 的颜色
                            color = self.get_max_mode_color(data_id, p)
                            
                            # Draw marker
                            ax.plot(x_pt, y_pt, 'X', markerfacecolor='none', markeredgecolor=color, markersize=7, markeredgewidth=1.2, zorder=5)
                            ax.annotate(mark['id'], xy=(x_pt, y_pt), xytext=(5, 5),
                                        textcoords='offset points', fontsize=9, color=color,
                                        arrowprops=dict(arrowstyle="-", connectionstyle="arc3,rad=.2", color=color, lw=0.5),
                                        zorder=6)

                            # Marker Legend Text Format Update
                            marker_legend_text.append(f"{mark['id']} ({p} ID {data_id}): Freq: {x_pt:.3f} MHz, {val:.3f} {y_unit}")
                            
                    except:
                        pass
        
        # --- Add Matplotlib Legend for Data Lines ---
        ax.legend(loc='best', fontsize=9, framealpha=0.7)
        # --- End Add Legend ---
        
        if marker_legend_text:
            # 使用 Max Marker Config 位置
            pos_config = self.max_marker_pos_configs[plot_type]
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

            txt = "\n".join(marker_legend_text)
            ax.text(x_val, y_val, txt, transform=ax.transAxes, fontsize=9, 
                    verticalalignment=v_align, horizontalalignment=h_align, 
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.9), zorder=7) 
        self.max_canvas.draw()

    # ---------- Existing marker UI helpers reused ----------
    def _draw_marker_frame_and_bind(self, mark_data, plot_type, param, marker_list_frame, canvas):
        frame = tk.Frame(marker_list_frame, bg="#ffffff", relief="solid", bd=1)
        frame.pack(fill="x", pady=3, padx=5)

        freq_var = mark_data["freq"]
        unit_var = mark_data["unit"]
        data_id_var = mark_data["data_id"]
        mark_id = mark_data["id"]

        tk.Label(frame, text=f"{mark_id}:", bg="#ffffff", font=("sans-serif", 10, "bold"), fg="#c0392b").grid(row=0, column=0, padx=3)
        tk.Entry(frame, textvariable=freq_var, width=10).grid(row=0, column=1, padx=3)
        ttk.Combobox(frame, textvariable=unit_var, values=["MHz", "GHz"], width=6, state="readonly").grid(row=0, column=2, padx=3)
        tk.Label(frame, text="Ref ID:", bg="#ffffff").grid(row=0, column=3, padx=3)
        data_id_options_current = [str(d['id']) for d in self.datasets] if self.datasets else ["1"]
        ttk.Combobox(frame, textvariable=data_id_var, values=data_id_options_current, width=4, state="readonly").grid(row=0, column=4, padx=3)

        def remove_and_update():
            try:
                self.data[plot_type]["marks"][param].remove(mark_data)
            except:
                pass
            self._reindex_markers_and_refresh_ui(plot_type, param)

        tk.Button(frame, text="Remove", bg="#95a5a6", fg="white", command=remove_and_update).grid(row=0, column=5, padx=5)
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
        if messagebox.askyesno("Clear Data", f"Are you sure to clear all {len(self.datasets)} loaded datasets?"):
            self.datasets = []
            self.next_dataset_id = 1
            self.maximized_param = None
            self.exit_max_mode()
            self.update_plots()
            self.update_file_list_ui()
            self.update_data_information_tab()
            self.status_var.set("All data cleared. Please load S2P file(s)...")

    def reset_application(self):
        if not messagebox.askyesno("Reset Application", "Reset application to initial state?"):
            return
        self._initialize_state()
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
        if hasattr(self, 'chart_tab'):
            self.notebook.select(self.chart_tab)
        self.update_file_list_ui()
        self.status_var.set("Application reset to initial state.")
        self.update_plots()
        messagebox.showinfo("Reset Complete", "The application has been reset to its initial state.")

    def load_s2p(self):
        file_path = filedialog.askopenfilename(title="Select S2P File", filetypes=[("S2P files", "*.s2p"), ("All files", "*.*")])
        if not file_path:
            return
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
                'name': file_path,
                'freq': freq,
                's_data': s_data,
                'format': s_format,
                'points': len(freq)
            }
            self.datasets.append(new_dataset)
            self.next_dataset_id += 1
            self.status_var.set(f"Loaded: {os.path.basename(file_path)} (ID {new_dataset['id']}) | Format: {s_format} | Total Files: {len(self.datasets)}")
            self.update_file_list_ui()
            self.on_plot_type_change()
            self.update_plots()
            self.update_data_information_tab()
        except Exception as e:
            messagebox.showerror("Load Failed", f"Cannot parse S2P file:\n{e}")
            self.status_var.set("Load failed")

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
        ax.clear()
        ax.set_title(param, fontsize=12, fontweight='bold')
        is_smith_chart = False
        ax.set_aspect('equal' if is_smith_chart else 'auto')
        
        marker_legend_text = [] # 初始化 Marker 文本列表
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
            
            if plot_type == "Magnitude (dB)":
                y_data = 20 * np.log10(np.abs(s) + 1e-20)
                ax.plot(freq_mhz, y_data, color=color, linewidth=1.5, label=line_label)
                all_y_values.extend(y_data)
                ax.set_xlabel("Frequency (MHz)")
            elif plot_type == "Phase (deg)":
                y_data = np.unwrap(np.angle(s)) * 180 / np.pi
                ax.plot(freq_mhz, y_data, color=color, linewidth=1.5, label=line_label)
                all_y_values.extend(y_data)
                ax.set_xlabel("Frequency (MHz)")
            elif plot_type == "Group Delay (ns)":
                y_data, freq_mhz_gd = self.calculate_group_delay(freq, s)
                ax.plot(freq_mhz_gd, y_data, color=color, linewidth=1.5, label=line_label)
                all_y_values.extend(y_data)
                ax.set_xlabel("Frequency (MHz)")
        
        ax.grid(True, alpha=0.3)
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
                    if all_freq_values:
                        min_f_mhz = max(min(all_freq_values), start_mhz)
                        max_f_mhz = min(max(all_freq_values), stop_mhz)
                        if min_f_mhz >= max_f_mhz:
                            continue
                        if ltype == "Max":
                            ax.hlines(upper, min_f_mhz, max_f_mhz, colors='red', linestyles='--', linewidth=1.5, zorder=4)
                        else:
                            ax.hlines(lower, min_f_mhz, max_f_mhz, colors='green', linestyles='--', linewidth=1.5, zorder=4)
                except:
                    pass
        
        # markers drawing (per param)
        if plot_type in self.data and self.datasets:
            for mark in self.data[plot_type]["marks"][param]:
                try:
                    f_str = mark["freq"].get()
                    unit = mark["unit"].get()
                    f = float(f_str)
                    if unit == "GHz":
                        freq_val = f * 1e9
                    elif unit == "MHz":
                        freq_val = f * 1e6
                    else:
                        freq_val = f
                    mark_id = mark['id']
                    
                    for dataset in self.datasets:
                        data_id = dataset['id']
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
                            
                        idx = np.argmin(np.abs(freq - freq_val))
                        if idx >= len(data_array):
                            continue
                        val = data_array[idx]
                        x_pt = freq[idx] / 1e6 # Frequency in MHz
                        y_pt = val
                        
                        # Plot marker
                        ax.plot(x_pt, y_pt, 'X', markerfacecolor='none', markeredgecolor=color, markersize=7, markeredgewidth=1.5, zorder=5)
                        ax.annotate(mark_id, xy=(x_pt, y_pt), xytext=(5, 5),
                                    textcoords='offset points', fontsize=9, color=color,
                                    arrowprops=dict(arrowstyle="-", connectionstyle="arc3,rad=.2", color=color, lw=0.5),
                                    zorder=6)
                                    
                        # FIX A: 收集标记文本信息
                        marker_legend_text.append(f"{mark_id} (ID {data_id}): Freq: {x_pt:.3f} MHz, {val:.3f} {y_unit}")
                        
                except Exception:
                    pass
        
        # FIX B: 绘制标记信息框 (Marker Legend Box)
        if marker_legend_text:
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

            txt = "\n".join(marker_legend_text)
            ax.text(x_val, y_val, txt, transform=ax.transAxes, fontsize=9, 
                    verticalalignment=v_align, horizontalalignment=h_align, 
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.9), zorder=7)
        
        ax.xaxis.set_major_locator(MaxNLocator(10))
        ax.yaxis.set_major_locator(MaxNLocator(10))
        # hide odd tick labels (keep interface similar)
        self._optimize_tick_labels(ax)
        canvas.draw()

    def _optimize_tick_labels(self, ax):
        try:
            canvas = ax.figure.canvas
            canvas.draw()
            x_labels = ax.get_xticklabels()
            new_x = []
            for i, lbl in enumerate(x_labels):
                new_x.append(lbl.get_text() if i % 2 == 0 else '')
            ax.set_xticklabels(new_x)
            y_labels = ax.get_yticklabels()
            new_y = []
            for i, lbl in enumerate(y_labels):
                new_y.append(lbl.get_text() if i % 2 == 0 else '')
            ax.set_yticklabels(new_y)
        except:
            pass

    # ---------- Copy / Save ----------
    def copy_all_charts(self):
        self._handle_chart_output(copy=True)

    def save_chart(self):
        self._handle_chart_output(copy=False)

    def _handle_chart_output(self, copy=False):
        try:
            if self.display_mode.get() == "Max" and self.max_fig:
                if copy:
                    buf = io.BytesIO()
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
                    f = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")])
                    if not f: return
                    self.max_fig.savefig(f, dpi=200, bbox_inches='tight')
                    messagebox.showinfo("Saved", f"Max mode plot saved to {f}")
            else:
                # Normal mode: Tiled 2x2 image
                out_fig = plt.Figure(figsize=(12, 8), dpi=150)
                axs = out_fig.subplots(2, 2)
                axs = axs.flatten()

                # Known style for the yellow marker legend box
                YELLOW_BBOX_STYLE = dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.9)
                YELLOW_FACECOLOR = (1.0, 1.0, 0.0, 0.9) # RGBA for the yellow box

                for i, p in enumerate(self.params):
                    ax_new = axs[i]
                    old_ax = self.plot_configs[p]["ax"]

                    # 复制标题和标签
                    ax_new.set_title(old_ax.get_title())
                    ax_new.set_xlabel(old_ax.get_xlabel())
                    ax_new.set_ylabel(old_ax.get_ylabel())

                    # 复制曲线
                    for line in old_ax.lines:
                        try:
                            x, y = line.get_data()
                            ax_new.plot(x, y, color=line.get_color(),
                                        linewidth=line.get_linewidth(),
                                        linestyle=line.get_linestyle())
                        except Exception:
                            pass

                    # 复制 marker 文本和信息框
                    for text in old_ax.texts:
                        try:
                            pos = text.get_position()
                            bbox_style = None
                            
                            # FIX 2: 检查是否是 Marker Legend Box 并重新构造 bbox dict
                            bbox_patch = text.get_bbox_patch()
                            if bbox_patch and np.allclose(bbox_patch.get_facecolor(), YELLOW_FACECOLOR):
                                bbox_style = YELLOW_BBOX_STYLE
                            
                            ax_new.text(
                                pos[0], pos[1],
                                text.get_text(),
                                transform=ax_new.transAxes if text.get_transform() == old_ax.transAxes else ax_new.transData, 
                                fontsize=text.get_fontsize(),
                                color=text.get_color(),
                                ha=text.get_ha(),
                                va=text.get_va(),
                                bbox=bbox_style # Pass the reconstructed style or None
                            )
                        except Exception:
                            pass

                    # 复制网格线
                    ax_new.grid(True)
                    
                    # 复制限制线（hlines/vlines）
                    for coll in old_ax.collections:
                        # FIX 1: 使用 mcollections.LineCollection
                        if isinstance(coll, mcollections.LineCollection):
                             segments = coll.get_segments()
                             if segments:
                                 is_h_line = all(abs(s[0][1] - s[1][1]) < 1e-6 for s in segments)
                                 if is_h_line:
                                     y_val = segments[0][0][1]
                                     x_min = min(s[0][0] for s in segments)
                                     x_max = max(s[1][0] for s in segments)
                                     ax_new.hlines(y_val, x_min, x_max, 
                                                   colors=coll.get_colors()[0], 
                                                   linestyles=coll.get_linestyles()[0], 
                                                   linewidth=coll.get_linewidths()[0])

                out_fig.subplots_adjust(left=0.08, right=0.96, top=0.93, bottom=0.08, wspace=0.28, hspace=0.32)

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
                    f = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")])
                    if not f: return
                    out_fig.savefig(f, dpi=200) 
                    messagebox.showinfo("Saved", f"Normal mode plots saved to {f}")
        
        except Exception as e:
            messagebox.showerror("Operation Failed", f"An error occurred: {e}")

    # ---------- UI for limits & marks & data info (kept similar to original) ----------
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
        def draw_limit_line_frame(line_data):
            frame = tk.Frame(limit_container, bg="#ffffff", relief="groove", bd=1)
            frame.pack(fill="x", pady=4, padx=5)
            unit_map = {"Magnitude (dB)": ("dB", "-20", "-20"), "Phase (deg)": ("deg", "-180", "-180"), "Group Delay (ns)": ("ns", "10", "10")}
            unit, default_lower, default_upper = unit_map.get(plot_type, ("?", "0", "0"))
            type_var = line_data.get("type", tk.StringVar(value="Min"))
            start_var = line_data.get("start", tk.StringVar(value="800"))
            stop_var = line_data.get("stop", tk.StringVar(value="900"))
            start_unit_var = line_data.get("start_unit", tk.StringVar(value="MHz"))
            stop_unit_var = line_data.get("stop_unit", tk.StringVar(value="MHz"))
            lower_var = line_data.get("lower", tk.StringVar(value=default_lower))
            upper_var = line_data.get("upper", tk.StringVar(value=default_upper))
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
            line_data.update({"frame": frame, "type": type_var, "start": start_var, "stop": stop_var, "start_unit": start_unit_var, "stop_unit": stop_unit_var, "lower": lower_var, "upper": upper_var})
            def remove_and_update():
                frame.destroy()
                lines.remove(line_data)
            tk.Button(frame, text="Remove", bg="#e74c3c", fg="white", command=remove_and_update).grid(row=0, column=12, padx=5)
        for line in lines:
            draw_limit_line_frame(line)
        def add_limit_and_draw():
            new_line = {}
            lines.append(new_line)
            draw_limit_line_frame(new_line)
        tk.Button(limit_container, text="Add Limit Line", bg="#3498db", fg="white", command=add_limit_and_draw).pack(pady=6)
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
            new_mark = {"id": "TEMP", "freq": tk.StringVar(value="100"), "unit": tk.StringVar(value="MHz"), "data_id": tk.StringVar(value=default_data_id)}
            marks.append(new_mark)
            self._reindex_markers_and_refresh_ui(plot_type, param)
        tk.Button(marker_control_frame, text="Add Marker", bg="#2ecc71", fg="white", command=add_mark_and_draw).pack(side="left", padx=5)

        # Legend Pos (Normal mode)
        legend_label = tk.Label(marker_control_frame, text="Legend Position:", font=("sans-serif", 10), bg="#f0f2f5")
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

        # Max Marker Config (Max mode)
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
        if not hasattr(self, 'data_information_tab'):
            self.data_information_tab = tk.Frame(self.notebook, bg="#f0f2f5")
        try:
            self.notebook.index(self.data_information_tab)
            is_in_notebook = True
        except tk.TclError:
            self.notebook.add(self.data_information_tab, text="Loaded File Information")
        self.notebook.insert(1, self.data_information_tab)
        if not hasattr(self, 'file_list_frame'):
            self.file_list_frame = tk.LabelFrame(self.data_information_tab, text="Loaded Files (ID - Name)", font=("sans-serif", 10), bg="#f0f2f5")
            self.file_list_frame.pack(fill="x", pady=(10, 0), padx=15)
            self.file_list_content = tk.Frame(self.file_list_frame, bg="#f0f2f5")
            self.file_list_content.pack(fill="x", padx=5, pady=5)
        if not hasattr(self, 'summary_content_frame'):
            canvas = tk.Canvas(self.data_information_tab, bg="#f0f2f5")
            scrollbar = tk.Scrollbar(self.data_information_tab, orient="vertical", command=canvas.yview)
            self.summary_content_frame = tk.Frame(canvas, bg="#f0f2f5")
            self.summary_content_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=self.summary_content_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True, padx=15, pady=15)
            scrollbar.pack(side="right", fill="y")
        self.update_file_list_ui()
        self.update_data_information_tab()

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

    def remove_dataset(self, data_id):
        self.datasets = [d for d in self.datasets if d['id'] != data_id]
        for i, d in enumerate(self.datasets):
            d['id'] = i + 1
        self.next_dataset_id = len(self.datasets) + 1
        self.update_file_list_ui()
        self.update_plots()
        self.update_data_information_tab()
        if not self.datasets:
            self.status_var.set("All data cleared. Please load S2P file(s)...")

    def on_plot_type_change(self, *args):
        plot_type = self.plot_type.get()
        is_supported = plot_type in ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"]
        if is_supported:
            self.create_limit_mark_tab(plot_type)
        active_tab_found = False
        for key, tab_widget in self.limit_tabs.items():
            if key == plot_type:
                try:
                    self.notebook.tab(tab_widget, state='normal')
                    self.notebook.select(tab_widget)
                except:
                    pass
                active_tab_found = True
            else:
                try:
                    self.notebook.tab(tab_widget, state='hidden')
                except:
                    pass
        self.create_data_information_tab()
        if not active_tab_found or not is_supported:
            try:
                self.notebook.select(self.chart_tab)
            except:
                pass
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
        tree = ttk.Treeview(self.summary_content_frame, columns=columns, show="headings", height=15)
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
    app = SViewGUI(root)
    root.mainloop()