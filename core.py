# -*- coding: utf-8 -*-
"""dsh-tray 核心：配置、服务管理、桌宠控制、快捷方式、图标生成。

所有与具体机器相关的路径都来自配置文件，本模块不含硬编码用户路径。
"""
import glob
import json
import os
import re
import socket
import subprocess
import threading
import time
import webbrowser

import psutil
import win32con
import win32gui
import win32process

APP_NAME = "DshTray"
PORT = 3080
PLUGIN_NAME = "dsh-dafeiyu"
PET_TITLE = "DSH 大肥鱼"
LOG_NAME = "dsh-web.log"
MIRROR = "https://registry.npmmirror.com"

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
ICON_PATH = os.path.join(CONFIG_DIR, "dsh.ico")
TRAY_LOG = os.path.join(CONFIG_DIR, "tray.log")

DEFAULT_CONFIG = {"agent_dir": "", "use_mirror": True}


# ---------- 日志 / 配置 ----------

def tlog(msg):
    """托盘运行日志（写在用户配置目录，不属于仓库）"""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(TRAY_LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + str(msg) + "\n")
    except OSError:
        pass


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = dict(DEFAULT_CONFIG)
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def validate_agent_dir(agent_dir):
    """校验目录是否为合法的 dsh 安装目录，返回 (ok, 信息)"""
    dsh = os.path.join(agent_dir, "node_modules", ".bin", "dsh.cmd")
    if not os.path.exists(dsh):
        return False, "未找到 node_modules\\.bin\\dsh.cmd，请确认这是 dsh 的安装目录"
    return True, dsh


def dsh_cmd(cfg):
    return os.path.join(cfg["agent_dir"], "node_modules", ".bin", "dsh.cmd")


def server_log_path(cfg):
    return os.path.join(cfg["agent_dir"], LOG_NAME)


# ---------- 服务 ----------

def server_running():
    s = socket.socket()
    s.settimeout(2)
    try:
        s.connect(("127.0.0.1", PORT))
        s.close()
        return True
    except OSError:
        return False


def start_server(cfg):
    """无窗口启动 dsh web，输出重定向到 agent 目录下的日志"""
    dsh = dsh_cmd(cfg)
    log = open(server_log_path(cfg), "w", encoding="utf-8")
    return subprocess.Popen(
        ["cmd", "/c", dsh, "web"],
        stdout=log, stderr=subprocess.STDOUT,
        cwd=cfg["agent_dir"],
        creationflags=0x08000000,  # CREATE_NO_WINDOW
    )


def token_url(cfg):
    """从服务日志提取最新的带 token 访问地址（宽松匹配，容忍 dsh 改路径格式）"""
    try:
        with open(server_log_path(cfg), encoding="utf-8", errors="ignore") as f:
            m = re.findall(r"http://[\d.]+:\d+/\?[^\s\"']*token=[^\s\"']*",
                           f.read())
            return m[-1] if m else None
    except OSError:
        return None


def open_page(cfg):
    webbrowser.open(token_url(cfg) or f"http://127.0.0.1:{PORT}")


def kill_server_tree():
    out = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True,
                         text=True, encoding="mbcs", errors="ignore").stdout or ""
    pids = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[1].endswith(":%d" % PORT) and parts[3] == "LISTENING":
            pids.add(int(parts[4]))
    for pid in pids:
        try:
            p = psutil.Process(pid)
            for proc in [p] + p.children(recursive=True):
                try:
                    proc.kill()
                except Exception:
                    continue
        except Exception:
            continue
    kill_pets()


def restart_server(cfg, log=None):
    """杀掉现有服务并以无窗口方式重启"""
    (log or tlog)("restarting server ...")
    kill_server_tree()
    time.sleep(2)
    start_server(cfg)
    for _ in range(36):  # 最多等 3 分钟
        time.sleep(5)
        if server_running():
            break
    for _ in range(20):  # 等 helper 被 dsh 带出来
        if helper_procs():
            break
        time.sleep(3)
    (log or tlog)("server restarted")


# ---------- 进程安全枚举 ----------

def iter_procs():
    """安全枚举：任何属性访问失败都跳过（受保护进程会让无防护的枚举崩溃）"""
    for p in psutil.process_iter():
        try:
            yield p.as_dict(attrs=["pid", "name", "cmdline"], ad_value=None)
        except Exception:
            continue


def helper_glob():
    return os.path.join(os.environ.get("LOCALAPPDATA", ""), PLUGIN_NAME,
                        "*", "dsh-dafeiyu-helper-*.exe")


def helper_procs():
    out = []
    for info in iter_procs():
        if "dsh-dafeiyu-helper" in (info.get("name") or "").lower():
            try:
                out.append(psutil.Process(info["pid"]))
            except Exception:
                continue
    return out


def kill_pets():
    for p in helper_procs():
        try:
            p.kill()
        except Exception:
            continue


# ---------- 桌宠窗口 ----------

def _windows_of(pids, exact_title=None):
    hwnds = []

    def cb(hwnd, _):
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid not in pids:
                return
            title = win32gui.GetWindowText(hwnd)
            if exact_title is None:
                if title:
                    hwnds.append(hwnd)
            elif title == exact_title:
                hwnds.append(hwnd)
        except Exception:
            pass
    win32gui.EnumWindows(cb, None)
    return hwnds


def pet_hwnds():
    return _windows_of({p.pid for p in helper_procs()}, exact_title=PET_TITLE)


def pet_visible():
    return any(win32gui.IsWindowVisible(h) for h in pet_hwnds())


def hide_helper_consoles():
    """helper 自己 AllocConsole 弹出的控制台窗口（打印 JSON 协议）一律隐藏"""
    pids = {p.pid for p in helper_procs()}

    def cb(hwnd, _):
        try:
            cls = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if cls == "ConsoleWindowClass" and win32gui.IsWindowVisible(hwnd) and (
                    pid in pids or "dsh-dafeiyu" in title.lower()):
                win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
        except Exception:
            pass
    win32gui.EnumWindows(cb, None)


def start_pet(cfg, log=None):
    """显示桌宠。helper 全死时等 3 秒服务重生，仍无则重启服务（helper 独立启动活不过 10 秒）"""
    log = log or tlog
    log("start_pet")
    if not server_running():
        log("server down, abort")
        return
    if not helper_procs():
        log("no helper, wait 3s for server respawn")
        time.sleep(3)
    if not helper_procs():
        log("helper still dead -> restarting server")
        restart_server(cfg, log)
    _hide_helper_consoles()
    if not pet_hwnds():
        log("helpers alive but no pet window -> kill for respawn")
        kill_pets()
        for _ in range(10):
            time.sleep(2)
            if pet_hwnds():
                break
    _hide_helper_consoles()
    for h in pet_hwnds():
        win32gui.ShowWindow(h, win32con.SW_RESTORE)
        win32gui.ShowWindow(h, win32con.SW_SHOW)
    log(f"start_pet done, visible={pet_visible()}")


def close_pet():
    """隐藏桌宠主窗口和内部窗口（helper 由服务托管，杀掉会被立刻重生）"""
    for h in _windows_of({p.pid for p in helper_procs()}):
        win32gui.ShowWindow(h, win32con.SW_HIDE)


# ---------- 图标 ----------

def _draw_fish_icon(path):
    """自绘兜底图标：一条橙胖鱼"""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 尾巴
    d.polygon([(200, 128), (252, 76), (252, 180)], fill=(255, 150, 60, 255))
    # 身体
    d.ellipse([(24, 48), (216, 208)], fill=(255, 170, 80, 255),
              outline=(210, 120, 40, 255), width=6)
    # 鱼鳍
    d.polygon([(110, 60), (140, 20), (160, 66)], fill=(255, 200, 120, 255))
    d.polygon([(110, 196), (140, 236), (160, 190)], fill=(255, 200, 120, 255))
    # 眼睛
    d.ellipse([(66, 100), (96, 130)], fill=(255, 255, 255, 255))
    d.ellipse([(76, 108), (90, 122)], fill=(40, 40, 40, 255))
    # 嘴
    d.arc([(40, 130), (78, 160)], 20, 160, fill=(210, 120, 40, 255), width=5)
    # 气泡
    for xy, r in [((28, 40), 10), ((52, 20), 7), ((20, 76), 5)]:
        d.ellipse([(xy[0] - r, xy[1] - r), (xy[0] + r, xy[1] + r)],
                  outline=(140, 200, 255, 220), width=4)
    img.save(path, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])


def _extract_pet_icon(path):
    """从已安装的大肥鱼插件素材提取一帧做图标（MIT 插件，仅本机个性化用）"""
    from PIL import Image
    patterns = [
        os.path.join(os.path.expanduser("~"), ".dsh", "profiles", "web",
                     "node_modules", PLUGIN_NAME, "assets", "pet", "idle", "*.webp"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), PLUGIN_NAME, "*", "pet.ico"),
    ]
    files = sorted(glob.glob(patterns[0])) + sorted(glob.glob(patterns[1]))
    if not files:
        return False
    img = Image.open(files[0]).convert("RGBA")
    alpha = img.getchannel("A").point(lambda a: 255 if a > 8 else 0)
    img = img.crop(alpha.getbbox())
    side = max(img.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    canvas = canvas.resize((256, 256), Image.LANCZOS)
    canvas.save(path, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    return True


def ensure_icon():
    """返回当前使用的图标路径；不存在则生成"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(ICON_PATH):
        if not _extract_pet_icon(ICON_PATH):
            _draw_fish_icon(ICON_PATH)
    return ICON_PATH


def refresh_pet_icon():
    """重新从桌宠素材提取（比如插件更新后）"""
    if _extract_pet_icon(ICON_PATH):
        return ICON_PATH
    _draw_fish_icon(ICON_PATH)
    return ICON_PATH


# ---------- 快捷方式 ----------

def create_desktop_shortcut(cfg):
    """在桌面创建启动快捷方式：
    - 打包成 exe 时：目标就是 exe 本身
    - 源码运行时：目标是 pythonw + tray_app.py（无窗口）"""
    import win32com.client
    desktop = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
    lnk = os.path.join(desktop, "DeepSeek Harness.lnk")
    ensure_icon()

    shell = win32com.client.Dispatch("WScript.Shell")
    sc = shell.CreateShortCut(lnk)
    if getattr(sys_frozen(), "frozen", False):
        sc.TargetPath = sys_frozen().executable
        sc.Arguments = ""
    else:
        import sys as _sys
        pyw = _sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(pyw):
            pyw = _sys.executable
        sc.TargetPath = pyw
        sc.Arguments = '"%s"' % os.path.join(_package_dir(), "tray_app.py")
    sc.WorkingDirectory = cfg["agent_dir"]
    sc.IconLocation = ICON_PATH + ", 0"
    sc.Description = "DeepSeek Harness (dsh) Web UI"
    sc.WindowStyle = 1
    sc.Save()
    if not os.path.exists(lnk):
        raise RuntimeError("快捷方式创建失败")
    return lnk


def sys_frozen():
    import sys
    return sys


def _package_dir():
    import sys
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# ---------- 插件安装 ----------

def self_check(cfg):
    """环境自检：逐项检查对 dsh 的 4 个接触点，返回 [(名称, 是否通过, 详情)]"""
    results = []

    # 1. dsh 可执行文件
    dsh = dsh_cmd(cfg)
    results.append(("dsh 启动脚本",
                    bool(dsh and os.path.exists(dsh)),
                    dsh or "config 中未配置 agent_dir"))

    # 2. 服务端口
    results.append(("服务端口 %d" % PORT, server_running(),
                    "运行中" if server_running() else "未运行（双击图标可启动）"))

    # 3. token URL（dsh 更新最可能变化的点）
    url = token_url(cfg)
    results.append(("网页 token 地址", bool(url), url or "日志中未找到，可能 dsh 改了日志格式"))

    # 4. 桌宠
    if helper_procs():
        hwnds = pet_hwnds()
        results.append(("大肥鱼桌宠", True,
                        f"运行中，窗口{'可见' if pet_visible() else '已隐藏'}"))
    else:
        installed = bool(glob.glob(helper_glob())) or bool(
            glob.glob(os.path.join(os.path.expanduser("~"), ".dsh", "profiles",
                                   "web", "node_modules", PLUGIN_NAME)))
        results.append(("大肥鱼桌宠", installed,
                        "插件未安装（向导可安装）" if not installed
                        else "已安装但未运行（启动服务后自动带出）"))
    return results


def install_pet_plugin(cfg, log=None):
    """安装大肥鱼桌宠插件：本地装 pnpm → dsh plugin add → 提示重启"""
    log = log or tlog
    tool_dir = _package_dir()
    local_pnpm = os.path.join(tool_dir, ".pnpm-local", "node_modules", ".bin")
    env = dict(os.environ)
    env["PATH"] = local_pnpm + os.pathsep + env.get("PATH", "")
    mirror = MIRROR if cfg.get("use_mirror", True) else ""
    if mirror:
        env["npm_config_registry"] = mirror

    def run(cmd, tag):
        log(f"$ {cmd}")
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="ignore", env=env, shell=True)
        tail = (p.stdout or "")[-500:]
        log(f"[{tag}] exit={p.returncode} {tail.strip()[-300:]}")
        return p.returncode == 0

    log("step 1/2: 安装 pnpm（本地目录，不污染系统）")
    npm_args = ["npm", "install", "pnpm", "--prefix",
                os.path.join(tool_dir, ".pnpm-local"), "--no-audit", "--no-fund"]
    if mirror:
        npm_args += ["--registry=" + mirror]
    if not run(" ".join(npm_args), "pnpm"):
        return False, "pnpm 安装失败，请检查网络后重试"

    log("step 2/2: 安装大肥鱼插件（约 170MB，请耐心等待）")
    dsh = dsh_cmd(cfg)
    ok = run(f'"{dsh}" plugin --profile web add {PLUGIN_NAME}', "plugin")
    if ok:
        return True, "安装成功！请通过托盘菜单【退出】后重新双击图标，桌宠即可出现"
    return False, "插件安装失败，详见日志"
