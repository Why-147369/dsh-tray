# -*- coding: utf-8 -*-
"""dsh-tray 配置向导（tkinter）"""
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import core


class SetupWizard:
    def __init__(self, root):
        self.root = root
        self.cfg = core.load_config()
        self.q = queue.Queue()
        root.title("dsh-tray 配置向导")
        root.geometry("640x480")
        root.resizable(False, False)

        pad = {"padx": 12, "pady": 6}

        ttk.Label(root, text="DeepSeek Harness 托盘助手",
                  font=("Microsoft YaHei UI", 14, "bold")).pack(pady=(14, 4))
        ttk.Label(root, text="已安装 dsh 但没有图标和托盘？选好路径，一键配好。",
                  foreground="#666").pack()

        # 路径选择
        frm = ttk.LabelFrame(root, text="第 1 步：选择 dsh 安装目录", padding=8)
        frm.pack(fill="x", **pad)
        row = ttk.Frame(frm)
        row.pack(fill="x")
        self.var_dir = tk.StringVar(value=self.cfg.get("agent_dir", ""))
        ttk.Entry(row, textvariable=self.var_dir).pack(side="left", fill="x",
                                                       expand=True, padx=(0, 6))
        ttk.Button(row, text="浏览…", command=self.browse).pack(side="left")
        self.lbl_check = ttk.Label(frm, text="", foreground="#888")
        self.lbl_check.pack(anchor="w")
        self.var_dir.trace_add("write", lambda *_: self.check_dir())

        # 一键操作
        frm2 = ttk.LabelFrame(root, text="第 2 步：一键配置", padding=8)
        frm2.pack(fill="x", **pad)
        grid = ttk.Frame(frm2)
        grid.pack(fill="x")
        ttk.Button(grid, text="创建桌面快捷方式",
                   command=lambda: self.async_run(self.do_shortcut)).grid(
            row=0, column=0, padx=4, sticky="ew")
        ttk.Button(grid, text="安装大肥鱼桌宠插件",
                   command=lambda: self.async_run(self.do_plugin)).grid(
            row=0, column=1, padx=4, sticky="ew")
        ttk.Button(grid, text="生成/更新图标",
                   command=lambda: self.async_run(self.do_icon)).grid(
            row=0, column=2, padx=4, sticky="ew")
        ttk.Button(grid, text="环境自检",
                   command=lambda: self.async_run(self.do_selfcheck)).grid(
            row=0, column=3, padx=4, sticky="ew")
        grid.columnconfigure((0, 1, 2, 3), weight=1)
        self.var_mirror = tk.BooleanVar(value=self.cfg.get("use_mirror", True))
        ttk.Checkbutton(frm2, text="使用国内镜像（npmmirror）",
                        variable=self.var_mirror).pack(anchor="w", pady=(6, 0))

        # 日志
        frm3 = ttk.LabelFrame(root, text="日志", padding=4)
        frm3.pack(fill="both", expand=True, **pad)
        self.txt = tk.Text(frm3, height=10, state="disabled",
                           font=("Consolas", 9), background="#111", foreground="#9f9")
        self.txt.pack(fill="both", expand=True)

        self.check_dir()
        self.root.after(150, self._poll_queue)

    # ---------- 工具 ----------

    def log(self, msg):
        self.q.put(str(msg))

    def _poll_queue(self):
        try:
            while True:
                msg = self.q.get_nowait()
                self.txt.configure(state="normal")
                self.txt.insert("end", msg + "\n")
                self.txt.see("end")
                self.txt.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(150, self._poll_queue)

    def async_run(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def browse(self):
        d = filedialog.askdirectory(title="选择 dsh 安装目录")
        if d:
            self.var_dir.set(d)

    def check_dir(self):
        d = self.var_dir.get().strip()
        ok, info = core.validate_agent_dir(d) if d else (False, "请选择目录")
        self.lbl_check.configure(
            text=("✔ " + info) if ok else ("✘ " + info),
            foreground="#0a0" if ok else "#c00")

    def _cfg(self):
        cfg = dict(self.cfg)
        cfg["agent_dir"] = self.var_dir.get().strip()
        cfg["use_mirror"] = self.var_mirror.get()
        core.save_config(cfg)
        self.cfg = cfg
        return cfg

    # ---------- 动作 ----------

    def do_shortcut(self):
        ok, info = core.validate_agent_dir(self.var_dir.get().strip())
        if not ok:
            self.log("✘ " + info)
            return
        cfg = self._cfg()
        try:
            lnk = core.create_desktop_shortcut(cfg)
            self.log(f"✔ 桌面快捷方式已创建：{lnk}")
            self.log("  双击它即可启动服务并打开网页（托盘图标会同时出现）")
        except Exception as e:
            self.log(f"✘ 创建失败：{e}")

    def do_plugin(self):
        ok, info = core.validate_agent_dir(self.var_dir.get().strip())
        if not ok:
            self.log("✘ " + info)
            return
        cfg = self._cfg()
        self.log("开始安装大肥鱼桌宠插件，全程可能需要几分钟…")
        ok2, msg = core.install_pet_plugin(cfg, log=self.log)
        self.log(("✔ " if ok2 else "✘ ") + msg)
        if ok2:
            self.log("提示：插件需要重启 dsh 才生效。可通过托盘菜单【退出】后重新双击图标。")

    def do_selfcheck(self):
        self.log("—— 环境自检 ——")
        cfg = self._cfg()
        if self.var_dir.get().strip():
            ok, info = core.validate_agent_dir(self.var_dir.get().strip())
            cfg["agent_dir"] = self.var_dir.get().strip()
            core.save_config(cfg)
        for name, ok, detail in core.self_check(cfg):
            self.log(f"{'✔' if ok else '✘'} {name}：{detail}")
        self.log("—— 若某项 ✘ 且 dsh 刚更新过，可能是 dsh 改了接口，欢迎提 Issue ——")

    def do_icon(self):
        try:
            path = core.refresh_pet_icon()
            self.log(f"✔ 图标已更新：{path}（桌面快捷方式图标需刷新桌面后生效）")
        except Exception as e:
            self.log(f"✘ 图标生成失败：{e}")


def run():
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    SetupWizard(root)
    root.mainloop()
