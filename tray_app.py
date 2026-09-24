# -*- coding: utf-8 -*-
"""dsh-tray 托盘运行模式"""
import threading

import pystray
from PIL import Image

import core

_stop_lock = threading.Lock()
_stopped = False


def _safe_stop(icon):
    """全进程唯一的图标退出入口：防止 watchdog 与退出菜单并发双 stop 死锁"""
    global _stopped
    with _stop_lock:
        if _stopped:
            return
        _stopped = True
    try:
        icon.stop()
    except Exception as e:
        core.tlog(f"icon.stop error: {e}")


def _on_open(icon=None, item=None):
    core.open_page(core.load_config())


def _on_start_pet(icon=None, item=None):
    threading.Thread(target=core.start_pet, args=(core.load_config(),),
                     daemon=True).start()


def _on_close_pet(icon=None, item=None):
    core.close_pet()


def _on_selfcheck(icon=None, item=None):
    """环境自检：检查对 dsh 的 4 个接触点，弹窗+日志双输出"""
    cfg = core.load_config()
    lines = [f"{'✔' if ok else '✘'} {name}：{detail}"
             for name, ok, detail in core.self_check(cfg)]
    text = "\n".join(lines)
    core.tlog("self-check:\n" + text)
    import ctypes
    ctypes.windll.user32.MessageBoxW(0, text, "dsh-tray 环境自检", 0x40)


def _on_quit(icon, item):
    core.tlog("quit clicked")
    try:
        core.kill_server_tree()
    except Exception as e:
        core.tlog(f"kill_server_tree error: {e}")
    _safe_stop(icon)
    # 保底：2 秒后无论如何强制退出，绝不留下卡死的图标
    threading.Timer(2.0, _force_exit).start()


def _force_exit():
    import os
    core.tlog("force exit")
    os._exit(0)


def _watchdog(icon, cfg):
    # 等服务首次上线（最多 5 分钟，兼容冷启动）
    for _ in range(60):
        if core.server_running():
            break
        time.sleep(5)
    else:
        core.tlog("watchdog: server never came up, exit")
        _safe_stop(icon)
        return
    core.tlog("watchdog: server online, monitoring")
    while True:
        time.sleep(5)
        try:
            core.hide_helper_consoles()  # 兜底：桌宠控制台自动隐藏
        except Exception:
            pass
        if not core.server_running():
            break
    core.tlog("watchdog: server stopped, icon exits")
    _safe_stop(icon)


def run():
    cfg = core.load_config()
    if not cfg.get("agent_dir") or not core.dsh_cmd(cfg):
        core.tlog("no agent configured, launching setup")
        import gui
        gui.run()
        return

    # 服务没跑就无窗口拉起；在跑则托盘照常
    if not core.server_running():
        core.tlog("starting server")
        core.start_server(cfg)

    import win32event
    import win32api
    import winerror
    mutex = win32event.CreateMutex(None, False, "DshTraySingleInstanceMutex")
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        core.tlog("mutex held by another tray, exit quietly")
        core.open_page(cfg)
        return

    core.tlog(f"tray starting (agent={cfg['agent_dir']})")
    icon = pystray.Icon("dsh", Image.open(core.ensure_icon()),
                        "DeepSeek Harness 正在后台运行",
                        pystray.Menu(
                            pystray.MenuItem("打开网页", _on_open, default=True),
                            pystray.Menu.SEPARATOR,
                            pystray.MenuItem("启动大肥鱼", _on_start_pet),
                            pystray.MenuItem("关闭大肥鱼", _on_close_pet),
                            pystray.Menu.SEPARATOR,
                            pystray.MenuItem("环境自检", _on_selfcheck),
                            pystray.MenuItem("退出", _on_quit),
                        ))
    threading.Thread(target=_watchdog, args=(icon, cfg), daemon=True).start()

    # 双击托盘/启动时顺手把桌宠显示出来
    threading.Thread(target=core.start_pet, args=(cfg,),
                     daemon=True).start()

    icon.run()
    core.tlog("tray exited")
