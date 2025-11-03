# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.ticker import MaxNLocator
import os
import re
from PIL import Image
import io
import platform
import subprocess
import matplotlib.font_manager as fm
import datetime
import warnings
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

# 剪贴板复制 (已修复)
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
        self.root.title("S-View")
        self.root.geometry("1450x980")
        self.root.resizable(True, True)
        self.root.minsize(1150, 780)
        self.root.configure(bg="#f0f2f5")

        self.params = ["S11", "S21", "S12", "S22"]
        self.MARKER_POSITIONS = ["Top Left", "Top Right", "Bottom Left", "Bottom Right", "Center", "Custom"]
        self.plot_configs = {}
        self.limit_tabs = {}

        # 核心状态初始化
        self._initialize_state()
        self.setup_ui()
        self.plot_type.trace("w", self.on_plot_type_change)

    def _initialize_state(self):
        """重置所有核心状态变量到初始值"""
        self.datasets = []
        self.next_dataset_id = 1
        self.current_img = None
        self.maximized_param = None
        
        if not hasattr(self, 'serial_var'):
            self.serial_var = tk.StringVar(value="SN-001")
        else:
            self.serial_var.set("SN-001")
            
        if not hasattr(self, 'plot_type'):
            self.plot_type = tk.StringVar(value="Magnitude (dB)")
        else:
            self.plot_type.set("Magnitude (dB)") 

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

    def setup_ui(self):
        main_frame = tk.Frame(self.root, bg="#f0f2f5")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # --- 1. File List Frame (已移除) ---
        self.loaded_file_labels = {}

        # --- 2. Main Content Frame (Grid: Charts | Controls) ---
        content_frame = tk.Frame(main_frame, bg="#f0f2f5")
        content_frame.pack(fill="both", expand=True)

        content_frame.grid_columnconfigure(0, weight=1) 
        content_frame.grid_columnconfigure(1, weight=0) 
        content_frame.grid_rowconfigure(0, weight=1)

        # --- 2a. Charts Notebook (左侧，展开) ---
        self.notebook = ttk.Notebook(content_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # 1. S-Parameter Plots (Index 0)
        self.chart_tab = tk.Frame(self.notebook, bg="#f0f2f5")
        self.notebook.add(self.chart_tab, text="S-Parameter Plots")
        self.setup_chart_tab()
        
        # 2. Loaded File Information (Index 1)
        self.create_data_information_tab() 

        # 3. Limits & Marks (Index 2)
        self.create_limit_mark_tab(self.plot_type.get())
        
        # --- 2b. Vertical Controls Frame (右侧，固定宽度) ---
        vertical_control_frame = tk.Frame(content_frame, bg="#f0f2f5", width=250) 
        vertical_control_frame.grid(row=0, column=1, sticky="ns")
        
        control_stack_frame = tk.Frame(vertical_control_frame, bg="#f0f2f5")
        control_stack_frame.pack(fill="x", side="top")
        
        # --- 垂直放置控制元素 ---
        sn_group = tk.Frame(control_stack_frame, bg="#f0f2f5")
        sn_group.pack(fill="x", pady=(5, 5), padx=5)
        tk.Label(sn_group, text="Serial Number:", font=("sans-serif", 12, "bold"), bg="#f0f2f5").pack(padx=5)
        tk.Entry(sn_group, textvariable=self.serial_var, font=("sans-serif", 12), width=15).pack(fill="x", padx=5)
        
        file_ops_group = tk.LabelFrame(control_stack_frame, text="File Operations", font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        file_ops_group.pack(fill="x", padx=5, pady=5)
        
        tk.Button(file_ops_group, text="Load S2P File", font=("sans-serif", 12, "bold"),
                  bg="#4CAF50", fg="white", relief="flat", padx=10, pady=8,
                  command=self.load_s2p).pack(fill="x", padx=5, pady=5)
        tk.Button(file_ops_group, text="Clear Data", font=("sans-serif", 12),
                  bg="#e74c3c", fg="white", relief="flat", padx=10, pady=8,
                  command=self.clear_all_datasets).pack(fill="x", padx=5, pady=5)
        tk.Button(file_ops_group, text="Reset App", font=("sans-serif", 12, "bold"),
                  bg="#3F51B5", fg="white", relief="flat", padx=10, pady=8,
                  command=self.reset_application).pack(fill="x", padx=5, pady=5)

        plot_type_group = tk.LabelFrame(control_stack_frame, text="Plot Type", font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        plot_type_group.pack(fill="x", padx=5, pady=5)
        plot_values = ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"]
        plot_combo = ttk.Combobox(plot_type_group, textvariable=self.plot_type, values=plot_values, state="readonly")
        plot_combo.pack(fill="x", padx=5, pady=5)
        
        tk.Button(control_stack_frame, text="Refresh Plots", font=("sans-serif", 12, "bold"),
                  bg="#FF9800", fg="white", relief="flat", padx=10, pady=8,
                  command=self.update_plots).pack(fill="x", padx=5, pady=5)
        
        chart_ops_group = tk.LabelFrame(control_stack_frame, text="Chart Output", font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        chart_ops_group.pack(fill="x", padx=5, pady=5)
        
        tk.Button(chart_ops_group, text="Copy Plots", font=("sans-serif", 12, "bold"),
                  bg="#FF5722", fg="white", relief="flat", padx=10, pady=8,
                  command=self.copy_all_charts).pack(fill="x", padx=5, pady=5)
        tk.Button(chart_ops_group, text="Save as Image", font=("sans-serif", 12),
                  bg="#9C27B0", fg="white", relief="flat", padx=10, pady=8,
                  command=self.save_chart).pack(fill="x", padx=5, pady=5)

        # --- NEW: Shared Legend Display Group ---
        self.legend_frame = tk.LabelFrame(vertical_control_frame, text="Legend (Data ID)", font=("sans-serif", 10, "bold"), bg="#f0f2f5")
        self.legend_frame.pack(fill="x", padx=5, pady=(5, 0), side="bottom") 
        self.legend_content = tk.Frame(self.legend_frame, bg="#f0f2f5")
        self.legend_content.pack(fill="x", padx=5, pady=5)
        
        # --- 3. Status Bar ---
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

    def _on_mouse_move_custom(self, event, param):
        config = self.plot_configs[param]
        toolbar = config["toolbar"]
        if event.inaxes and event.xdata is not None and event.ydata is not None:
            msg = self._format_coords(event.xdata, event.ydata)
            toolbar.set_message(msg)
        else:
            if toolbar.mode == '':
                 toolbar.set_message(f"Zoom & Pan enabled for {param}")

    def _draw_marker_frame_and_bind(self, mark_data, plot_type, param, marker_list_frame, canvas):
        frame = tk.Frame(marker_list_frame, bg="#ffffff", relief="solid", bd=1)
        frame.pack(fill="x", pady=3, padx=5)

        freq_var = mark_data["freq"]
        unit_var = mark_data["unit"]
        data_id_var = mark_data["data_id"]
        mark_id = mark_data["id"]

        def trace_callback(*args):
            self.update_plots()

        for var in [freq_var, unit_var, data_id_var]:
            var.trace_add("write", trace_callback)

        tk.Label(frame, text=f"{mark_id}:", bg="#ffffff", font=("sans-serif", 10, "bold"), fg="#c0392b").grid(row=0, column=0, padx=3)
        tk.Entry(frame, textvariable=freq_var, width=10).grid(row=0, column=1, padx=3)
        ttk.Combobox(frame, textvariable=unit_var, values=["MHz", "GHz"], width=6, state="readonly").grid(row=0, column=2, padx=3)
        tk.Label(frame, text="Ref ID:", bg="#ffffff").grid(row=0, column=3, padx=3)
        data_id_options_current = [str(d['id']) for d in self.datasets] if self.datasets else ["1"]
        ttk.Combobox(frame, textvariable=data_id_var, values=data_id_options_current, width=4, state="readonly").grid(row=0, column=4, padx=3)

        def remove_and_update():
            self.data[plot_type]["marks"][param].remove(mark_data)
            self._reindex_markers_and_refresh_ui(plot_type, param)
            self.update_plots()

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

    def clear_all_datasets(self):
        if messagebox.askyesno("Clear Data", f"Are you sure to clear all {len(self.datasets)} loaded datasets?"):
            self.datasets = []
            self.next_dataset_id = 1
            self.maximized_param = None
            self.restore_plots_layout()
            self.update_plots()
            self.update_file_list_ui()
            self.update_data_information_tab()
            self.status_var.set("All data cleared. Please load S2P file(s)...")

    def reset_application(self):
        if not messagebox.askyesno("Reset Application", "Are you sure you want to reset the application to its initial state? All loaded data, markers, limit lines, and settings will be cleared."):
            return

        self._initialize_state()
        self.restore_plots_layout()

        if hasattr(self, 'limit_tabs') and hasattr(self, 'notebook'):
            tabs_to_forget = list(self.limit_tabs.keys())
            for plot_type in tabs_to_forget:
                tab_widget = self.limit_tabs.pop(plot_type)
                try:
                    self.notebook.forget(tab_widget)
                    tab_widget.destroy()
                except tk.TclError:
                    pass

        self.create_limit_mark_tab(self.plot_type.get())
        self.create_data_information_tab() 

        if hasattr(self, 'chart_tab'):
            self.notebook.select(self.chart_tab)

        self.update_file_list_ui()
        self.status_var.set("Application reset to initial state. Please load S2P file(s)...")
        self.update_plots()
        self.update_data_information_tab()
        messagebox.showinfo("Reset Complete", "The application has been reset to its initial state.")

    def update_plots(self):
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
            for param in self.params:
                config = self.plot_configs[param]
                config["ax"].clear()
                config["ax"].set_title(param)
                config["ax"].text(0.5, 0.5, "No Data Loaded", transform=config["ax"].transAxes, ha='center', va='center', fontsize=12, color='gray')
                config["canvas"].draw()
            return

        plot_type = self.plot_type.get()
        saved_xlim = saved_ylim = None
        if self.maximized_param:
            config = self.plot_configs[self.maximized_param]
            try:
                saved_xlim = config["ax"].get_xlim()
                saved_ylim = config["ax"].get_ylim()
            except: pass

        for param in self.params:
            config = self.plot_configs[param]
            self.plot_parameter(config["ax"], config["fig"], config["canvas"], param, plot_type)

        if self.maximized_param and saved_xlim is not None and saved_ylim is not None:
            config = self.plot_configs[self.maximized_param]
            config["ax"].set_xlim(saved_xlim)
            config["ax"].set_ylim(saved_ylim)

        if not self.maximized_param:
            main_fig = self.plot_configs["S11"]["fig"]
            if main_fig.legends:
                try:
                    main_fig.legends[0].remove()
                except:
                    pass
            for param in self.params:
                self.plot_configs[param]["fig"].tight_layout(rect=[0, 0, 1, 1])
            main_fig.tight_layout()
        else:
            maximized_fig = self.plot_configs[self.maximized_param]["fig"]
            if maximized_fig.legends:
                maximized_fig.legends[0].remove()
            maximized_fig.tight_layout()

        for param in self.params:
            config = self.plot_configs[param]
            config["canvas"].draw()

    def update_file_list_ui(self):
        if not hasattr(self, 'file_list_content'):
            return
        for widget in self.file_list_content.winfo_children():
            widget.destroy()
        self.loaded_file_labels.clear()

        if not self.datasets:
            tk.Label(self.file_list_content, text="No files loaded.", bg="#f0f2f5", fg="gray").pack(padx=5, pady=5)
            return

        for i, dataset in enumerate(self.datasets):
            color = COLOR_CYCLE[(dataset['id'] - 1) % len(COLOR_CYCLE)]
            file_name_only = os.path.basename(dataset['name'])
            text = f"**{dataset['id']}** - {file_name_only}"
            label = tk.Label(self.file_list_content, text=text, bg="#f0f2f5", fg=color, font=("sans-serif", 10, "bold"))
            label.pack(side="left", padx=10, pady=2)
            self.loaded_file_labels[dataset['id']] = label

            def remove_data(data_id=dataset['id']):
                self.remove_dataset(data_id)
            remove_btn = tk.Button(self.file_list_content, text="X", command=remove_data,
                                   bg="#e74c3c", fg="white", font=("sans-serif", 8), width=2, height=1, relief="flat")
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

    def on_scroll_zoom(self, mpl_event, param):
        if mpl_event.inaxes is None:
            return
        ax = mpl_event.inaxes
        config = self.plot_configs[param]
        if config["toolbar"].mode not in ('', 'zoom rect'):
            return
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
        config["canvas"].draw()

    def add_marker_on_click(self, mpl_event, param):
        if not self.datasets: return
        plot_type = self.plot_type.get()
        if plot_type not in self.data: return
        if mpl_event.inaxes is None or mpl_event.button != 1 or mpl_event.xdata is None:
            return

        x_data_mhz = mpl_event.xdata
        ref_freq = self.datasets[0]['freq']
        target_freq_hz = x_data_mhz * 1e6
        idx = np.argmin(np.abs(ref_freq - target_freq_hz))
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
        self._reindex_markers_and_refresh_ui(plot_type, param)
        final_mark_id = self.data[plot_type]["marks"][param][-1]["id"] 
        self.update_plots()
        self.status_var.set(f"Marker {final_mark_id} added at {f_val:.3f} {f_unit} on {param} plot.")

    def toggle_maximize(self, param):
        if not self.datasets: return
        config = self.plot_configs[param]

        if self.maximized_param == param:
            if 'cid_click' in config:
                config["fig"].canvas.mpl_disconnect(config['cid_click'])
                del config['cid_click']
            if 'cid_scroll' in config:
                config["fig"].canvas.mpl_disconnect(config['cid_scroll'])
                del config['cid_scroll']
            if 'cid_mouse_move' in config:
                config["fig"].canvas.mpl_disconnect(config['cid_mouse_move'])
                del config['cid_mouse_move']
            self.maximized_param = None
            self.restore_plots_layout()
        else:
            if self.maximized_param and self.maximized_param in self.plot_configs:
                other_config = self.plot_configs[self.maximized_param]
                if 'cid_click' in other_config:
                    other_config["fig"].canvas.mpl_disconnect(other_config['cid_click'])
                    del other_config['cid_click']
                if 'cid_scroll' in other_config:
                    other_config["fig"].canvas.mpl_disconnect(other_config['cid_scroll'])
                    del other_config['cid_scroll']
                if 'cid_mouse_move' in other_config:
                    other_config["fig"].canvas.mpl_disconnect(other_config['cid_mouse_move'])
                    del other_config['cid_mouse_move']

            self.maximized_param = param
            self.maximize_plot_layout(param)

            config['cid_click'] = config["fig"].canvas.mpl_connect(
                'button_press_event', lambda event: self.add_marker_on_click(event, param)
            )
            config['cid_scroll'] = config["fig"].canvas.mpl_connect(
                'scroll_event', lambda event: self.on_scroll_zoom(event, param)
            )
            config['cid_mouse_move'] = config["fig"].canvas.mpl_connect(
                'motion_notify_event', lambda event: self._on_mouse_move_custom(event, param)
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
            config["toolbar_frame"].pack_forget()
            config["canvas_widget"].pack(side=tk.TOP, fill="both", expand=True)

            if 'cid_click' in config:
                config["fig"].canvas.mpl_disconnect(config['cid_click'])
                del config['cid_click']
            if 'cid_scroll' in config:
                config["fig"].canvas.mpl_disconnect(config['cid_scroll'])
                del config['cid_scroll']
            if 'cid_mouse_move' in config:
                config["fig"].canvas.mpl_disconnect(config['cid_mouse_move'])
                del config['cid_mouse_move']

        self.charts_frame.update_idletasks()

    def maximize_plot_layout(self, param):
        self.charts_frame.grid_rowconfigure(0, weight=1)
        self.charts_frame.grid_rowconfigure(1, weight=1)
        self.charts_frame.grid_columnconfigure(0, weight=1)
        self.charts_frame.grid_columnconfigure(1, weight=1)

        for p, config in self.plot_configs.items():
            if p == param:
                config["frame"].grid(row=0, column=0, rowspan=2, columnspan=2, padx=8, pady=8, sticky="nsew")
                config["toolbar_frame"].pack(side=tk.BOTTOM, fill=tk.X)
                config["canvas_widget"].pack(side=tk.TOP, fill="both", expand=True)
                config["toolbar"].set_message(f"Zoom & Pan enabled for {param}")
            else:
                config["frame"].grid_forget()

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

            unit_map = {
                "Magnitude (dB)": ("dB", "-20", "-20"),
                "Phase (deg)": ("deg", "-180", "-180"),
                "Group Delay (ns)": ("ns", "10", "10")
            }
            unit, default_lower, default_upper = unit_map.get(plot_type, ("?", "0", "0"))

            type_var = line_data.get("type", tk.StringVar(value="Min"))
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
                "frame": frame, "type": type_var, "start": start_var, "stop": stop_var,
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
            lines.append(new_line)
            draw_limit_line_frame(new_line)
            self.update_plots()
        tk.Button(limit_container, text="Add Limit Line", bg="#3498db", fg="white", command=add_limit_and_draw).pack(pady=6)

        mark_container = tk.Frame(scrollable, bg="#f0f2f5")
        mark_container.pack(fill="x", pady=(15, 0))
        tk.Label(mark_container, text="Markers", font=("sans-serif", 11, "bold"), bg="#f0f2f5", fg="#2c3e50").pack(anchor="w", padx=5)

        marker_control_frame = tk.Frame(mark_container, bg="#f0f2f5")
        marker_control_frame.pack(fill="x", pady=(6, 10))

        marker_list_frame = tk.Frame(mark_container, bg="#f0f2f5")
        marker_list_frame.pack(fill="x")

        self.data[plot_type]["ui_refs"][param] = {
            "marker_list_frame": marker_list_frame,
            "canvas": canvas
        }

        def add_mark_and_draw():
            data_id_options = [str(d['id']) for d in self.datasets]
            default_data_id = data_id_options[0] if data_id_options else "1"

            new_mark = {
                "id": "TEMP",
                "freq": tk.StringVar(value="100"),
                "unit": tk.StringVar(value="MHz"),
                "data_id": tk.StringVar(value=default_data_id)
            }
            marks.append(new_mark)
            self._reindex_markers_and_refresh_ui(plot_type, param)
            self.update_plots()

        tk.Button(marker_control_frame, text="Add Marker", bg="#2ecc71", fg="white", command=add_mark_and_draw).pack(side="left", padx=5)

        tk.Label(marker_control_frame, text="Legend Pos:", font=("sans-serif", 10), bg="#f0f2f5").pack(side="left", padx=(10, 5))
        pos_config = self.marker_pos_configs[plot_type][param]
        mode_var = pos_config["mode_var"]
        x_var = pos_config["x_var"]
        y_var = pos_config["y_var"]

        pos_combo = ttk.Combobox(marker_control_frame, textvariable=mode_var, values=self.MARKER_POSITIONS, state="readonly", width=12)
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

        self._reindex_markers_and_refresh_ui(plot_type, param)
        
    def create_data_information_tab(self):
        if not hasattr(self, 'data_information_tab'):
            self.data_information_tab = tk.Frame(self.notebook, bg="#f0f2f5")
        
        try:
            self.notebook.index(self.data_information_tab)
        except tk.TclError:
            self.notebook.add(self.data_information_tab, text="Loaded File Information")
            
        self.notebook.insert(1, self.data_information_tab)

        # 文件列表
        if not hasattr(self, 'file_list_frame'):
            self.file_list_frame = tk.LabelFrame(self.data_information_tab, text="Loaded Files (ID - Name)", font=("sans-serif", 10), bg="#f0f2f5")
            self.file_list_frame.pack(fill="x", pady=(10, 0), padx=15)
            self.file_list_content = tk.Frame(self.file_list_frame, bg="#f0f2f5")
            self.file_list_content.pack(fill="x", padx=5, pady=5)
        
        # 表格容器
        if not hasattr(self, 'summary_content_frame'):
            self.summary_content_frame = tk.Frame(self.data_information_tab, bg="#f0f2f5")
            self.summary_content_frame.pack(fill="both", expand=True, padx=15, pady=15)
            self.summary_content_frame.grid_rowconfigure(0, weight=1)
            self.summary_content_frame.grid_columnconfigure(0, weight=1)

        self.update_file_list_ui()
        self.update_data_information_tab()

    def update_data_information_tab(self):
        """使用 Treeview 构建专业表格，路径过长自动换行 + 全部左对齐 + 标题加黑"""
        for widget in self.summary_content_frame.winfo_children():
            widget.destroy()

        if not self.datasets:
            tk.Label(self.summary_content_frame, text="No S2P files loaded.", 
                     font=("sans-serif", 12), fg="gray", bg="#f0f2f5").pack(padx=20, pady=20)
            return

        columns = ("ID", "File Path", "Points", "Format", "Frequency Range")
        tree = ttk.Treeview(
            self.summary_content_frame,
            columns=columns,
            show="headings",
            height=15,
            style="LeftAligned.Treeview"  # 自定义样式
        )

        # === 自定义样式：左对齐 + 标题加黑 ===
        style = ttk.Style()
        style.configure("LeftAligned.Treeview.Heading",
                        font=("Microsoft YaHei", 10, "bold"),  # 标题加黑
                        foreground="#1a1a1a")
        style.configure("LeftAligned.Treeview",
                        font=("Microsoft YaHei", 9),
                        rowheight=28,
                        background="#ffffff",
                        foreground="#2c3e50",
                        fieldbackground="#ffffff")
        style.map("LeftAligned.Treeview",
                  background=[('selected', '#3498db')])
        tree.configure(style="LeftAligned.Treeview")

        # === 设置列标题（全部左对齐 + 加黑）===
        for col in columns:
            tree.heading(col, text=col, anchor="w")   # 标题左对齐
            tree.column(col, anchor="w", stretch=True)  # 内容左对齐

        # === 精确控制列宽 ===
        tree.column("ID", width=60, minwidth=50)
        tree.column("File Path", width=520, minwidth=300)
        tree.column("Points", width=100, minwidth=80)
        tree.column("Format", width=100, minwidth=80)
        tree.column("Frequency Range", width=240, minwidth=180)

        # === 滚动条 ===
        v_scrollbar = ttk.Scrollbar(self.summary_content_frame, orient="vertical", command=tree.yview)
        h_scrollbar = ttk.Scrollbar(self.summary_content_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)
        v_scrollbar.grid(row=0, column=1, sticky="ns", pady=10)
        h_scrollbar.grid(row=1, column=0, sticky="ew", padx=(10, 0))

        # === 插入数据 ===
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

            tree.insert("", "end", values=(
                str(data_id),
                name,
                str(points),
                s_format,
                freq_range_str
            ))

        # === 鼠标悬停显示完整路径 ===
        def on_treeview_motion(event):
            item = tree.identify_row(event.y)
            if item:
                col = tree.identify_column(event.x)
                if col == "#2":  # File Path 列
                    try:
                        value = tree.item(item, "values")[1]
                        self.status_var.set(f"Full Path: {value}")
                    except:
                        pass
                else:
                    self.status_var.set("Loaded File Information")
            else:
                self.status_var.set("Loaded File Information")

        tree.bind("<Motion>", on_treeview_motion)

    def on_plot_type_change(self, *args):
        plot_type = self.plot_type.get()
        is_supported = plot_type in ["Magnitude (dB)", "Phase (deg)", "Group Delay (ns)"]

        if is_supported:
            self.create_limit_mark_tab(plot_type)

        active_tab_found = False
        for key, tab_widget in self.limit_tabs.items():
            if key == plot_type:
                self.notebook.tab(tab_widget, state='normal')
                self.notebook.select(tab_widget)
                active_tab_found = True
            else:
                self.notebook.tab(tab_widget, state='hidden')

        self.create_data_information_tab()
        
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
            self.update_plots()
            self.on_plot_type_change()
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

        marker_legend_text = []
        all_y_values = []
        all_freq_values = []

        for dataset in self.datasets:
            data_id = dataset['id']
            freq = dataset['freq']
            s = dataset['s_data'][param.lower()]
            color = COLOR_CYCLE[(data_id - 1) % len(COLOR_CYCLE)]

            if len(s) == 0: continue

            freq_mhz = freq / 1e6
            all_freq_values.extend(freq_mhz)
            line_label = f"ID {data_id}"

            if plot_type == "Magnitude (dB)":
                y_data = 20 * np.log10(np.abs(s) + 1e-20)
                ax.plot(freq_mhz, y_data, color=color, linewidth=1.5, label=line_label)
                all_y_values.extend(y_data)
                ax.set_ylabel("Magnitude (dB)")
                ax.set_xlabel("Frequency (MHz)")
            elif plot_type == "Phase (deg)":
                y_data = np.unwrap(np.angle(s)) * 180 / np.pi
                ax.plot(freq_mhz, y_data, color=color, linewidth=1.5, label=line_label)
                all_y_values.extend(y_data)
                ax.set_ylabel("Phase (deg)")
                ax.set_xlabel("Frequency (MHz)")
            elif plot_type == "Group Delay (ns)":
                y_data, freq_mhz_gd = self.calculate_group_delay(freq, s)
                ax.plot(freq_mhz_gd, y_data, color=color, linewidth=1.5, label=line_label)
                all_y_values.extend(y_data)
                ax.set_ylabel("Group Delay (ns)")
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
                        if min_f_mhz >= max_f_mhz: continue
                        if ltype == "Max":
                            ax.hlines(upper, min_f_mhz, max_f_mhz, colors='red', linestyles='--', linewidth=1.5, zorder=4)
                        else:
                            ax.hlines(lower, min_f_mhz, max_f_mhz, colors='green', linestyles='--', linewidth=1.5, zorder=4)
                except: pass

        unit_label = {"Magnitude (dB)": "dB", "Phase (deg)": "°", "Group Delay (ns)": "ns"}.get(plot_type, "")
        marker_legend_text = []

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
                        
                    freq_show = f"{f_str}{unit}"
                    mark_id = mark['id']
                    marker_legend_text.append(f"{mark_id} Freq: {freq_show}")

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
                        if idx >= len(data_array): continue
                        val = data_array[idx]
                        val_show = f"{val:.3f}{unit_label}"
                        x_pt = freq[idx] / 1e6
                        y_pt = val
                        marker_legend_text.append(f"{mark_id} (ID {data_id}): {val_show}")
                        ax.plot(x_pt, y_pt, 'X', markerfacecolor='none', markeredgecolor=color, markersize=7, markeredgewidth=1.5, zorder=5)
                        ax.annotate(mark_id, xy=(x_pt, y_pt), xytext=(5, 5),
                                    textcoords='offset points', fontsize=9, color=color,
                                    arrowprops=dict(arrowstyle="-", connectionstyle="arc3,rad=.2", color=color, lw=0.5),
                                    zorder=6)
                except Exception as e:
                    pass

        if not is_smith_chart:
            ax.xaxis.set_major_locator(MaxNLocator(10)) 
            ax.yaxis.set_major_locator(MaxNLocator(10))
            canvas.draw() 
            x_labels = ax.get_xticklabels()
            new_x_labels = [label.get_text() if i % 2 == 0 else '' for i, label in enumerate(x_labels)]
            ax.set_xticklabels(new_x_labels)
            y_labels = ax.get_yticklabels()
            new_y_labels = [label.get_text() if i % 2 == 0 else '' for i, label in enumerate(y_labels)]
            ax.set_yticklabels(new_y_labels)

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
            marker_legend_str = "\n".join(marker_legend_text)
            ax.text(x, y, marker_legend_str, transform=ax.transAxes,
                    fontsize=9, verticalalignment=va, horizontalalignment=ha,
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.9),
                    linespacing=1.2, zorder=7)

        ax.relim()

    def _copy_plot_content(self, ax_old, ax_new):
        plot_type = self.plot_type.get()
        is_smith_chart = False
        if is_smith_chart:
            ax_new.set_aspect('equal')
        else:
            ax_new.set_aspect('auto')

        for line in ax_old.lines:
            x_data, y_data = line.get_data()
            ax_new.plot(x_data, y_data, color=line.get_color(), linewidth=line.get_linewidth(),
                        marker=line.get_marker(), markersize=line.get_markersize(), linestyle=line.get_linestyle(),
                        markeredgewidth=line.get_markeredgewidth() if hasattr(line, 'get_markeredgewidth') else 1,
                        markerfacecolor=line.get_markerfacecolor(),
                        markeredgecolor=line.get_markeredgecolor(),
                        zorder=line.get_zorder(), label=line.get_label())

        for patch in ax_old.patches:
            try:
                props = patch.properties()
                ax_new.add_patch(patch.__class__(**props))
            except: pass

        for ann_old in ax_old.findobj(plt.Annotation):
            try:
                ann_text = ann_old.get_text()
                if not ann_text or not ann_text.startswith('M'):
                    continue
                xy = ann_old.xy 
                fontsize = ann_old.get_fontsize()
                color = ann_old.get_color()
                zorder = ann_old.get_zorder()
                arrowprops = {
                    "arrowstyle": "-", 
                    "connectionstyle": "arc3,rad=.2", 
                    "color": color, 
                    "lw": 0.5
                }
                ax_new.annotate(
                    ann_text, 
                    xy=xy, 
                    xytext=(5, 5),
                    xycoords='data',
                    textcoords='offset points',
                    fontsize=fontsize, 
                    color=color,
                    arrowprops=arrowprops, 
                    zorder=zorder
                )
            except Exception: 
                pass

        ax_new.set_title(ax_old.get_title())
        ax_new.set_xlabel(ax_old.get_xlabel())
        ax_new.set_ylabel(ax_old.get_ylabel())
        try:
            ax_new.grid(True)
        except: pass
        try:
            ax_new.set_xlim(ax_old.get_xlim())
        except: pass
        try:
            ax_new.set_ylim(ax_old.get_ylim())
        except: pass
        
        if not is_smith_chart:
            try:
                ax_new.xaxis.set_major_locator(ax_old.xaxis.get_major_locator())
                ax_new.yaxis.set_major_locator(ax_old.yaxis.get_major_locator())
                ax_new.set_xticklabels([t.get_text() for t in ax_old.get_xticklabels()])
                ax_new.set_yticklabels([t.get_text() for t in ax_old.get_yticklabels()])
            except: pass

        for txt in ax_old.texts:
            try:
                if txt.get_bbox_patch() is not None:
                    ax_new.text(txt.get_position()[0], txt.get_position()[1], txt.get_text(),
                                transform=ax_new.transAxes,
                                fontsize=txt.get_fontsize(),
                                verticalalignment=txt.get_verticalalignment(),
                                horizontalalignment=txt.get_horizontalalignment(),
                                bbox=dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.9),
                                linespacing=1.2, zorder=7)
            except: pass

        if not is_smith_chart:
            try:
                ax_new.relim()
                ax_new.autoscale_view()
            except: pass

    def generate_combined_image(self):
        if not self.datasets: return None
        serial = self.serial_var.get().strip() or "Unknown"
        self.update_plots()

        handles, labels = [], []
        if self.plot_configs["S11"]["ax"].lines:
            lines = self.plot_configs["S11"]["ax"].lines
            for line in lines:
                label = line.get_label()
                if label and label.startswith("ID") and label not in labels:
                    handles.append(line)
                    labels.append(label)
        
        if self.maximized_param:
            param = self.maximized_param
            config = self.plot_configs[param]
            fig_old = config["fig"]
            
            combined_fig = plt.Figure(figsize=(10, 7), dpi=120)
            combined_fig.suptitle(f"{param} {self.plot_type.get()} | Serial Number: {serial}", fontsize=14, fontweight='bold', y=0.98)
            ax_new = combined_fig.add_subplot(111)
            self._copy_plot_content(ax_old=fig_old.axes[0], ax_new=ax_new)

            if labels:
                combined_fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 0.96), ncol=len(labels), fontsize=10, frameon=False)
                combined_fig.tight_layout(rect=[0, 0.03, 1, 0.93]) 
            else:
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
            
            if labels:
                combined_fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 0.96), ncol=len(labels), fontsize=10, frameon=False)
                combined_fig.tight_layout(rect=[0, 0.03, 1, 0.93]) 
            else:
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
                messagebox.showerror("Copy Failed", "Failed to copy. Please install: pip install pywin32")

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