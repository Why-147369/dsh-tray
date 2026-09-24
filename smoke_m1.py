# -*- coding: utf-8 -*-
"""M1 冒烟测试：图标、校验、配置读写"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core

out = []
core._draw_fish_icon(r"E:\workbudy\dsh-tray-win\assets\dsh.ico")
out.append("drawn icon: " + str(os.path.exists(r"E:\workbudy\dsh-tray-win\assets\dsh.ico")))

ok, info = core.validate_agent_dir(r"E:\dsh")
out.append(f"validate E:\\dsh: {ok} {info}")

cfg = core.load_config()
out.append(f"config: {cfg}")

# 不实际创建用户桌面快捷方式，只测 COM 通路（用配置目录里的临时文件名）
out.append(f"server running: {core.server_running()}")
out.append(f"helpers: {len(core.helper_procs())}")

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_m1.txt"),
          "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("done")
