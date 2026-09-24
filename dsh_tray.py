# -*- coding: utf-8 -*-
"""dsh-tray 程序入口：
    dsh-tray.exe            -> 托盘运行（无参数）
    dsh-tray.exe --setup    -> 配置向导
"""
import sys


def main():
    if "--setup" in sys.argv:
        import gui
        gui.run()
    else:
        import tray_app
        tray_app.run()


if __name__ == "__main__":
    main()
