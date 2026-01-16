import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
import subprocess
import threading
import sys
from pathlib import Path

# === 全局配置 ===
CONFIG_FILE = "config.json"
APP_TITLE = "PicToSvg 图片批量转矢量工具"
APP_VERSION = "v1.1 | by Carry Cai | 微信：imcc1688 | 公众号：无趣研习社"
EXECUTABLE_NAME = "vtracer.exe" if os.name == 'nt' else "vtracer"

# === 核心：获取 vtracer 路径 (支持打包模式) ===
def get_exe_path():
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.getcwd()
    return os.path.join(base_path, EXECUTABLE_NAME)

# === 预设参数 ===
PRESETS = {
    "默认 (Default)": {
        "colormode": "color", "hierarchical": "stacked", "mode": "spline",
        "filter_speckle": 4, "color_precision": 6, "gradient_step": 16,
        "corner_threshold": 60, "segment_length": 5.0, "splice_threshold": 45, "path_precision": 8
    },
    "黑白 (BW)": {
        "colormode": "bw", "hierarchical": "stacked", "mode": "spline",
        "filter_speckle": 4, "color_precision": 6, "gradient_step": 16,
        "corner_threshold": 60, "segment_length": 5.0, "splice_threshold": 45, "path_precision": 8
    },
    "海报 (Poster)": {
        "colormode": "color", "hierarchical": "stacked", "mode": "spline",
        "filter_speckle": 8, "color_precision": 8, "gradient_step": 64,
        "corner_threshold": 60, "segment_length": 5.0, "splice_threshold": 45, "path_precision": 8
    },
    "照片 (Photo)": {
        "colormode": "color", "hierarchical": "stacked", "mode": "spline",
        "filter_speckle": 2, "color_precision": 8, "gradient_step": 16,
        "corner_threshold": 180, "segment_length": 3.5, "splice_threshold": 180, "path_precision": 10
    }
}

# === 图形绘制辅助函数：通用圆角矩形 ===
def create_rounded_rect(canvas, x1, y1, x2, y2, radius=25, **kwargs):
    points = [x1+radius, y1, x1+radius, y1, x2-radius, y1, x2-radius, y1, x2, y1, x2, y1+radius, x2, y1+radius, x2, y2-radius, x2, y2-radius, x2, y2, x2-radius, y2, x2-radius, y2, x1+radius, y2, x1+radius, y2, x1, y2, x1, y2-radius, x1, y2-radius, x1, y1+radius, x1, y1+radius, x1, y1]
    return canvas.create_polygon(points, **kwargs, smooth=True)

# === 自定义控件：极简细线圆角滚动条 ===
class MinimalScrollbar(tk.Canvas):
    def __init__(self, parent, command=None, width=8, bg_color="#ffffff", thumb_color="#dee2e6"):
        super().__init__(parent, width=width, bg=bg_color, highlightthickness=0)
        self.command = command
        self.thumb_color = thumb_color
        self.bg_color = bg_color
        self.thumb_loc = (0.0, 1.0)
        self.width_val = width
        self.bind("<Configure>", self.draw)
        self.bind("<Button-1>", self.on_click)
        self.bind("<B1-Motion>", self.on_drag)
    def set(self, first, last):
        self.thumb_loc = (float(first), float(last))
        self.draw()
    def draw(self, event=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if h <= 0: return
        start_y, end_y = self.thumb_loc[0] * h, self.thumb_loc[1] * h
        if end_y - start_y < 20: end_y = start_y + 20
        padding = 2
        create_rounded_rect(self, padding, start_y, self.width_val-padding*2, end_y, radius=(self.width_val-padding*2)/2, fill=self.thumb_color, outline="")
    def on_click(self, e): self.command("moveto", e.y/self.winfo_height()) if self.command else None
    def on_drag(self, e): self.command("moveto", e.y/self.winfo_height()) if self.command else None

# === 自定义控件：圆角按钮 ===
class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command=None, width=150, height=38, bg_color="#28a745", hover_color="#218838", text_color="white"):
        super().__init__(parent, width=width, height=height, bg="white", highlightthickness=0)
        self.command, self.bg_color, self.hover_color, self.text_color = command, bg_color, hover_color, text_color
        self.state = "normal"
        self.rect = create_rounded_rect(self, 2, 2, width-2, height-2, radius=15, fill=bg_color, outline="")
        self.text_id = self.create_text(width/2, height/2, text=text, fill=text_color, font=("Microsoft YaHei", 11, "bold"))
        self.bind("<Button-1>", self.on_click)
        self.bind("<Enter>", lambda e: self.itemconfig(self.rect, fill=self.hover_color) if self.state=="normal" else None)
        self.bind("<Leave>", lambda e: self.itemconfig(self.rect, fill=self.bg_color) if self.state=="normal" else None)
    def on_click(self, e): 
        if self.state == "normal" and self.command: self.command()
    def set_state(self, state, text=None):
        self.state = state
        if text: self.itemconfig(self.text_id, text=text)
        self.itemconfig(self.rect, fill="#cccccc" if state=="disabled" else self.bg_color)

# === 自定义控件：超细圆角进度条 ===
class RoundedProgressBar(tk.Canvas):
    def __init__(self, parent, height=6, bg_color="#e9ecef", fill_color="#28a745"):
        super().__init__(parent, height=height, bg="white", highlightthickness=0)
        self.height, self.bg_color, self.fill_color, self.value = height, bg_color, fill_color, 0
        self.bind("<Configure>", lambda e: self.draw())
    def set_value(self, val): self.value = val; self.draw()
    def draw(self):
        self.delete("all")
        w = self.winfo_width()
        if w < 1: return
        create_rounded_rect(self, 0, 0, w, self.height, radius=self.height/2, fill=self.bg_color, outline="")
        if self.value > 0:
            fill_w = max(self.height, w * (self.value / 100.0))
            create_rounded_rect(self, 0, 0, fill_w, self.height, radius=self.height/2, fill=self.fill_color, outline="")

# === 自定义控件：无框圆角容器 ===
class RoundedFrame(tk.Canvas):
    def __init__(self, parent, width, height, bg="white", fill_color="#f8f9fa"):
        super().__init__(parent, width=width, height=height, bg="white", highlightthickness=0)
        self.border = create_rounded_rect(self, 0, 0, width, height, radius=10, outline="", width=0, fill=fill_color)

# === 自定义控件：大号复选框 ===
class BigCheck(tk.Frame):
    def __init__(self, parent, text, variable, **kwargs):
        super().__init__(parent, bg="white", cursor="arrow", **kwargs)
        self.variable, self.color_on, self.color_off = variable, "#28a745", "#adb5bd"
        self.icon_lbl = tk.Label(self, text="☐", font=("Microsoft YaHei", 16), bg="white", fg=self.color_off)
        self.icon_lbl.pack(side="left")
        self.text_lbl = tk.Label(self, text=text, font=("Microsoft YaHei", 12), bg="white", fg="#333")
        self.text_lbl.pack(side="left", padx=(5, 0))
        for w in [self, self.icon_lbl, self.text_lbl]: w.bind("<Button-1>", lambda e: self.variable.set(not self.variable.get()))
        self.variable.trace_add("write", lambda *a: self.update_visual())
        self.update_visual()
    def update_visual(self):
        is_on = self.variable.get()
        self.icon_lbl.config(text="☑" if is_on else "☐", fg=self.color_on if is_on else self.color_off)
        self.text_lbl.config(fg="#28a745" if is_on else "#333")

# === 自定义控件：单选文字选项 ===
class ModernRadio(tk.Frame):
    def __init__(self, parent, text, variable, value, **kwargs):
        super().__init__(parent, bg="white", cursor="arrow", **kwargs)
        self.variable, self.value = variable, value
        self.icon_lbl = tk.Label(self, text="○", font=("Microsoft YaHei", 14), bg="white", fg="#adb5bd")
        self.icon_lbl.pack(side="left")
        self.text_lbl = tk.Label(self, text=text, font=("Microsoft YaHei", 11), bg="white", fg="#333")
        self.text_lbl.pack(side="left", padx=(2, 0))
        for w in [self, self.icon_lbl, self.text_lbl]: w.bind("<Button-1>", lambda e: self.variable.set(self.value) if self.icon_lbl.cget("state")!="disabled" else None)
        self.variable.trace_add("write", lambda *a: self.update_visual())
        self.update_visual()
    def update_visual(self):
        if self.icon_lbl.cget("state") == "disabled": return
        is_sel = str(self.variable.get()) == str(self.value)
        self.icon_lbl.config(text="◉" if is_sel else "○", fg="#28a745" if is_sel else "#adb5bd")
        self.text_lbl.config(fg="#28a745" if is_sel else "#333")
    def set_state(self, state):
        self.icon_lbl.config(state=state, fg="#eee" if state=="disabled" else "#adb5bd")
        self.text_lbl.config(state=state, fg="#eee" if state=="disabled" else "#333")
        if state != "disabled": self.update_visual()

# === 自定义控件：极简滑块 ===
class ModernSlider(tk.Canvas):
    def __init__(self, parent, variable, from_, to, width=220, height=30):
        super().__init__(parent, width=width, height=height, bg="white", highlightthickness=0)
        self.variable, self.v_min, self.v_max, self.padding = variable, from_, to, 10
        self.state = "normal"; self.col_track, self.col_active, self.col_knob = "#e9ecef", "#28a745", "white"
        cy = height / 2
        self.track = self.create_line(self.padding, cy, width-self.padding, cy, width=4, fill=self.col_track, capstyle="round")
        self.active_track = self.create_line(self.padding, cy, self.padding, cy, width=4, fill=self.col_active, capstyle="round")
        self.knob = self.create_oval(0, 0, 0, 0, fill=self.col_knob, outline=self.col_active, width=2)
        self.bind("<Button-1>", self.update_evt); self.bind("<B1-Motion>", self.update_evt)
        self.variable.trace_add("write", lambda *a: self.update_visual())
        self.update_visual()
    def set_state(self, state):
        self.state = state
        self.itemconfig(self.active_track, state="hidden" if state=="disabled" else "normal")
        self.itemconfig(self.track, fill="#dee2e6" if state=="disabled" else self.col_track)
        self.itemconfig(self.knob, outline="#dee2e6" if state=="disabled" else self.col_active, fill="#f8f9fa" if state=="disabled" else self.col_knob)
    def update_evt(self, e):
        if self.state == "disabled": return
        r = max(0, min(1, (e.x - self.padding) / (self.winfo_width() - 2 * self.padding)))
        self.variable.set(int(round(self.v_min + r*(self.v_max-self.v_min))) if isinstance(self.variable, tk.IntVar) else round(self.v_min + r*(self.v_max-self.v_min), 1))
    def update_visual(self):
        try: val = self.variable.get()
        except: val = self.v_min
        r = (max(self.v_min, min(self.v_max, val)) - self.v_min) / (self.v_max - self.v_min)
        w = self.winfo_width() if self.winfo_width()>1 else 220
        x = self.padding + r * (w - 2*self.padding)
        cy = self.winfo_height()/2 if self.winfo_height()>1 else 15
        self.coords(self.knob, x-8, cy-8, x+8, cy+8); self.coords(self.active_track, self.padding, cy, x, cy)

# === 主程序 ===
class PicToSvgApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        # 紧凑高度：默认 850x600，适合大多数屏幕
        self.root.geometry("850x600") 
        self.root.minsize(800, 550)
        self.root.configure(bg="white")
        
        self.input_dir = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.process_subdirs = tk.BooleanVar(value=False)
        self.delete_original = tk.BooleanVar(value=False)
        self.is_processing = False
        self.log_visible = False
        
        self.p_colormode = tk.StringVar(value="color")
        self.p_hierarchical = tk.StringVar(value="stacked")
        self.p_mode = tk.StringVar(value="spline")
        self.p_filter_speckle = tk.IntVar(value=4)
        self.p_color_precision = tk.IntVar(value=6)
        self.p_gradient_step = tk.IntVar(value=16)
        self.p_corner_threshold = tk.IntVar(value=60)
        self.p_segment_length = tk.DoubleVar(value=5.0)
        self.p_splice_threshold = tk.IntVar(value=45)
        self.p_path_precision = tk.IntVar(value=8)

        self.widget_refs = {}
        self.setup_styles()
        self.load_config()
        self.create_widgets()
        self.check_param_states()
        self.root.update_idletasks(); self.root.geometry("") 

    def setup_styles(self):
        style = ttk.Style()
        if "clam" in style.theme_names(): style.theme_use("clam")
        base_font = ("Microsoft YaHei", 12)
        style.configure("TFrame", background="white")
        style.configure("TLabel", background="white", font=base_font, foreground="#333")
        style.configure("Title.TLabel", font=("Microsoft YaHei", 14, "bold"), foreground="#111")
        style.configure("Desc.TLabel", font=("Microsoft YaHei", 10), foreground="#999")
        style.configure("TEntry", fieldbackground="#f8f9fa", borderwidth=0)
        style.configure("TButton", font=base_font, background="#f1f3f5", borderwidth=0, padding=6)
        style.configure("Preset.TButton", font=("Microsoft YaHei", 10), padding=4)
        
    def create_widgets(self):
        # 减少内边距，更紧凑
        main_pad = ttk.Frame(self.root, padding="25 10")
        main_pad.pack(fill="both", expand=True)

        # 1. 文件夹 (行距减小)
        path_frame = ttk.Frame(main_pad)
        path_frame.pack(fill="x", pady=(0, 10))
        path_frame.columnconfigure(1, weight=1); path_frame.columnconfigure(4, weight=1)

        def create_entry(parent, label, var, cmd, col):
            ttk.Label(parent, text=label, style="Title.TLabel").grid(row=0, column=col, sticky="nw", padx=(0, 8), pady=6)
            # 缩小输入框高度 36 -> 32
            bg = RoundedFrame(parent, width=200, height=32, fill_color="#f8f9fa")
            bg.grid(row=0, column=col+1, sticky="ew", padx=0)
            ent = ttk.Entry(parent, textvariable=var, font=("Microsoft YaHei", 11), width=10)
            ent.place(in_=bg, x=8, y=4, relwidth=0.92, height=24) # y调整
            ttk.Button(parent, text="选择", width=5, command=cmd).grid(row=0, column=col+2, padx=(8, 15))

        create_entry(path_frame, "输入:", self.input_dir, self.select_input, 0)
        create_entry(path_frame, "输出:", self.output_dir, self.select_output, 3)

        # 2. 选项
        opt_frame = ttk.Frame(main_pad)
        opt_frame.pack(fill="x", pady=(0, 10))
        BigCheck(opt_frame, "处理子文件夹文件", self.process_subdirs).pack(side="left", padx=(0, 40))
        BigCheck(opt_frame, "处理成功后删除原文件", self.delete_original).pack(side="left")

        # 3. 参数
        param_area = ttk.Frame(main_pad)
        param_area.pack(fill="both", expand=True)
        preset_frame = ttk.Frame(param_area)
        preset_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(preset_frame, text="快速预设:", style="Title.TLabel").pack(side="left", padx=(0, 10))
        for name in PRESETS.keys():
            ttk.Button(preset_frame, text=name, style="Preset.TButton", command=lambda n=name: self.apply_preset(n)).pack(side="left", padx=4)

        grid_frame = ttk.Frame(param_area)
        grid_frame.pack(fill="x")
        grid_frame.columnconfigure(1, weight=1); grid_frame.columnconfigure(4, weight=1); grid_frame.columnconfigure(2, minsize=30) 

        # 减小参数行距 pady 8 -> 4
        def add_radio(r, c, label, var, opts, desc, tag):
            ttk.Label(grid_frame, text=label).grid(row=r*2, column=c, sticky="w", pady=(4,0))
            box = ttk.Frame(grid_frame); box.grid(row=r*2, column=c+1, sticky="w", padx=5, pady=(4,0))
            for t, v in opts: ModernRadio(box, t, var, v).pack(side="left", padx=(0,15))
            desc_lbl = ttk.Label(grid_frame, text=desc, style="Desc.TLabel")
            desc_lbl.grid(row=r*2+1, column=c+1, sticky="w", padx=5, pady=(0,0))
            self.widget_refs[tag] = [w for w in box.winfo_children() if isinstance(w, ModernRadio)] + [desc_lbl]

        def add_slider(r, c, label, var, min_v, max_v, desc, tag):
            ttk.Label(grid_frame, text=label).grid(row=r*2, column=c, sticky="w", pady=(4,0))
            box = ttk.Frame(grid_frame); box.grid(row=r*2, column=c+1, sticky="ew", padx=5, pady=(4,0))
            sl = ModernSlider(box, variable=var, from_=min_v, to=max_v, height=30)
            sl.pack(side="left", fill="x", expand=True)
            val_lbl = ttk.Label(box, text="0", width=4, anchor="e", foreground="#28a745", font=("Consolas", 12, "bold"))
            val_lbl.pack(side="right", padx=(2,0))
            var.trace_add("write", lambda *a: val_lbl.config(text=f"{int(round(var.get()))}" if isinstance(var, tk.IntVar) else f"{var.get():.1f}"))
            desc_lbl = ttk.Label(grid_frame, text=desc, style="Desc.TLabel")
            desc_lbl.grid(row=r*2+1, column=c+1, sticky="w", padx=5, pady=(0,0))
            self.widget_refs[tag] = [ttk.Label(grid_frame, text=label), sl, val_lbl, desc_lbl]

        add_radio(0, 0, "颜色模式", self.p_colormode, [("Color", "color"), ("BW", "bw")], "彩色或黑白图像", "colormode")
        add_radio(0, 3, "拟合模式", self.p_mode, [("Spline", "spline"), ("Polygon", "polygon"), ("Pixel", "pixel")], "曲线 / 多边形 / 像素", "mode")
        add_slider(1, 0, "去噪强度", self.p_filter_speckle, 0, 16, "忽略小噪点斑块(0-16)", "filter_speckle")
        add_slider(1, 3, "拐角阈值", self.p_corner_threshold, 0, 180, "拐角最小角度", "corner_threshold")
        add_slider(2, 0, "色彩精度", self.p_color_precision, 1, 8, "色彩位深 (仅Color)", "color_precision")
        add_slider(2, 3, "线段长度", self.p_segment_length, 3.5, 10, "细分线段长度(3.5-10)", "segment_length")
        add_slider(3, 0, "梯度步长", self.p_gradient_step, 0, 64, "层级差异 (仅Color)", "gradient_step")
        add_slider(3, 3, "拼接阈值", self.p_splice_threshold, 0, 180, "拼接角度阈值", "splice_threshold")
        add_slider(4, 0, "路径精度", self.p_path_precision, 1, 10, "生成路径小数位", "path_precision")
        add_radio(5, 0, "堆叠方式", self.p_hierarchical, [("Stacked", "stacked"), ("Cutout", "cutout")], "Stacked(推荐) 或 Cutout (仅Color)", "hierarchical")

        # 4. 日志 & 按钮
        log_ctrl = ttk.Frame(main_pad); log_ctrl.pack(fill="x", pady=(15, 5))
        self.btn_log = ttk.Button(log_ctrl, text="▼ 显示日志", command=self.toggle_log); self.btn_log.pack(side="left")
        
        self.log_container = ttk.Frame(main_pad)
        self.log_text = tk.Text(self.log_container, height=5, state="disabled", font=("Consolas", 12), relief="flat", bg="#f8f9fa", fg="#555", padx=10, pady=5)
        self.scrollbar = MinimalScrollbar(self.log_container, command=self.log_text.yview, width=8)
        self.log_text.configure(yscrollcommand=self.scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True); self.scrollbar.pack(side="right", fill="y")

        action_frame = ttk.Frame(main_pad); action_frame.pack(fill="x", pady=(5, 5))
        # 缩小按钮高度 45 -> 38
        self.btn_run = RoundedButton(action_frame, text="开始转换", command=self.start_processing_thread, width=200, height=38)
        self.btn_run.pack(anchor="center")
        
        # 缩小进度条 6 -> 4
        self.progress = RoundedProgressBar(main_pad, height=4, bg_color="#e9ecef", fill_color="#28a745")
        self.progress.pack(fill="x", pady=(5, 10))
        
        ttk.Label(main_pad, text=APP_VERSION, style="Desc.TLabel").pack(side="right")

    def apply_preset(self, name):
        p = PRESETS.get(name)
        if not p: return
        for k, v in p.items(): getattr(self, f"p_{k}").set(v)
        self.check_param_states()
        self.log(f"已应用预设: {name}")

    def check_param_states(self):
        is_bw = (self.p_colormode.get() == 'bw')
        mode = self.p_mode.get()
        rules = [("color_precision", not is_bw), ("gradient_step", not is_bw), ("hierarchical", not is_bw),
                 ("corner_threshold", mode != "pixel"), ("segment_length", mode != "pixel"), ("splice_threshold", mode == "spline")]
        for key, active in rules:
            for w in self.widget_refs.get(key, []):
                state = "normal" if active else "disabled"
                if hasattr(w, 'set_state'): w.set_state(state)
                elif isinstance(w, ttk.Label):
                    is_title = w.cget("text") and not "Desc" in str(w.cget("style"))
                    w.config(foreground=("#333" if is_title else "#999") if active else "#ccc")

    def toggle_log(self):
        if self.log_visible:
            self.log_container.pack_forget()
            self.btn_log.config(text="▼ 显示日志")
        else:
            self.log_container.pack(fill="both", expand=True, pady=(0, 10), before=self.btn_run.master)
            self.btn_log.config(text="▲ 隐藏日志")
        self.log_visible = not self.log_visible
        self.root.geometry("")

    def log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def select_input(self):
        p = filedialog.askdirectory()
        if p:
            self.input_dir.set(p)
            if not self.output_dir.get(): self.output_dir.set(os.path.join(p, "output"))

    def select_output(self):
        p = filedialog.askdirectory()
        if p: self.output_dir.set(p)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.input_dir.set(data.get("input", ""))
                    self.output_dir.set(data.get("output", ""))
                    self.process_subdirs.set(data.get("subdirs", False))
                    self.delete_original.set(data.get("delete", False))
            except: pass

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump({"input": self.input_dir.get(), "output": self.output_dir.get(), "subdirs": self.process_subdirs.get(), "delete": self.delete_original.get()}, f)
        except: pass

    def start_processing_thread(self):
        if self.is_processing: return
        in_d = self.input_dir.get()
        if not in_d or not os.path.exists(in_d): return messagebox.showerror("提示", "请选择输入文件夹")
        exe_path = get_exe_path()
        if not os.path.exists(exe_path): return messagebox.showerror("错误", f"找不到 {EXECUTABLE_NAME}")
        
        self.save_config()
        if not self.log_visible: self.toggle_log()
        self.is_processing = True
        self.btn_run.set_state("disabled", "处理中...")
        self.log_text.config(state="normal"); self.log_text.delete(1.0, "end"); self.log_text.config(state="disabled")
        threading.Thread(target=self.process, args=(exe_path, in_d, self.output_dir.get()), daemon=True).start()

    def process(self, exe, in_dir, out_dir):
        files = []
        exts = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}
        if self.process_subdirs.get():
            for r, _, fs in os.walk(in_dir):
                for f in fs:
                    if Path(f).suffix.lower() in exts: files.append(os.path.join(r, f))
        else:
            if os.path.exists(in_dir):
                for f in os.listdir(in_dir):
                    fp = os.path.join(in_dir, f)
                    if os.path.isfile(fp) and Path(f).suffix.lower() in exts: files.append(fp)
        
        total = len(files)
        if total == 0: self.log("未找到图片"); self.reset_ui(); return
        self.log(f"开始处理 {total} 个文件...")
        if not os.path.exists(out_dir): 
            try: os.makedirs(out_dir) 
            except: pass
            
        success = 0
        for i, fp in enumerate(files):
            rel = os.path.relpath(fp, in_dir)
            out = os.path.join(out_dir, os.path.dirname(rel)) if self.process_subdirs.get() else out_dir
            if not os.path.exists(out): os.makedirs(out)
            out_p = os.path.join(out, Path(fp).stem + ".svg")
            
            cmd = [exe, "--input", fp, "--output", out_p, "--colormode", self.p_colormode.get(), "--mode", self.p_mode.get(), "--filter_speckle", str(self.p_filter_speckle.get()), "--path_precision", str(self.p_path_precision.get())]
            if self.p_colormode.get() == 'color': cmd.extend(["--color_precision", str(self.p_color_precision.get()), "--gradient_step", str(self.p_gradient_step.get()), "--hierarchical", self.p_hierarchical.get()])
            if self.p_mode.get() != 'pixel': cmd.extend(["--corner_threshold", str(self.p_corner_threshold.get()), "--segment_length", str(self.p_segment_length.get())])
            if self.p_mode.get() == 'spline': cmd.extend(["--splice_threshold", str(self.p_splice_threshold.get())])
            
            try:
                startup = None
                if os.name == 'nt': startup = subprocess.STARTUPINFO(); startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                res = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startup)
                if res.returncode == 0:
                    self.log(f"[{i+1}/{total}] ✅ {rel}")
                    success += 1
                    if self.delete_original.get(): 
                        try: os.remove(fp)
                        except: pass
                else: self.log(f"[{i+1}/{total}] ❌ {rel}")
            except Exception as e: self.log(f"错误: {e}")
            self.root.after(10, lambda v=(i+1)/total*100: self.progress.set_value(v))
            
        self.log(f"完成! 成功: {success}/{total}")
        self.reset_ui()

    def reset_ui(self): self.root.after(0, lambda: [self.btn_run.set_state("normal", "开始转换"), setattr(self, 'is_processing', False)])

if __name__ == "__main__":
    root = tk.Tk()
    app = PicToSvgApp(root)
    root.mainloop()