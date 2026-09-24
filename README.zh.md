# dsh-tray — DeepSeek Harness 托盘助手

> 已装好 [DeepSeek Harness (dsh)](https://github.com/deepseek-ai/deepseek-harness)，但是——
> 没有桌面图标、没有托盘、桌宠要手动配、后台跑没跑完全不知道？
>
> **打开 dsh-tray，选个路径，一键全部配好。**

![screenshot](docs/screenshot-placeholder.png)

## 它做什么

| 功能 | 说明 |
|---|---|
| 🖥 桌面快捷方式 | 双击即启动服务并自动打开网页（无黑窗口，自动带登录 token） |
| 🔺 系统托盘图标 | 服务在跑就显示；右键菜单见下 |
| 🐟 大肥鱼桌宠控制 | 托盘菜单一键显示/隐藏桌宠（[dsh-dafeiyu](https://github.com/qcytsn/dsh-dafeiyu) 插件） |
| 🚪 干净退出 | 一键停止服务 + 桌宠，不留残余进程 |

托盘右键菜单：**打开网页**（自动带 token 秒进）/ **启动大肥鱼** / **关闭大肥鱼** / **退出**。

## 使用前提

- Windows 10/11
- 已安装 Node.js ^22.19 或 >=24
- 已通过 `npm install @deepseek-ai/dsh` 安装 dsh（本工具不负责安装 dsh 本体）

## 快速开始

### 方式一：下载 exe（推荐普通用户）

1. 从 [Releases](../../releases) 下载 `dsh-tray.exe`
2. 双击运行（首次会自动弹出配置向导）
3. 选择你的 dsh 安装目录（里面应有 `node_modules\.bin\dsh.cmd`）
4. 点「创建桌面快捷方式」和「安装大肥鱼桌宠插件」
5. 完成！以后双击桌面图标即可

### 方式二：从源码运行

```bat
git clone https://github.com/<you>/dsh-tray.git
cd dsh-tray
pip install -r requirements.txt
python dsh_tray.py --setup    :: 配置向导
python dsh_tray.py            :: 直接运行托盘
```

### 自己构建 exe

双击 `build.bat`，生成的 exe 在 `dist\dsh-tray.exe`。

## 配置文件

`%APPDATA%\DshTray\config.json`：

```json
{
  "agent_dir": "E:\\dsh",
  "use_mirror": true
}
```

## 常见问题

**Q: 点了启动没反应？**
服务冷启动需要 1~2 分钟初始化，网页就绪后会自动弹出。已运行时双击是秒开。

**Q: 托盘图标在哪？**
默认收在任务栏右下角 `^` 展开区，拖到任务栏可常驻。

**Q: 安装桌宠插件后桌宠没出现？**
插件需要重启 dsh 才生效：托盘右键【退出】→ 重新双击桌面图标。

**Q: 卸载？**
删除桌面快捷方式、exe 和 `%APPDATA%\DshTray` 目录即可，不残留任何系统级修改。

## 踩坑记录（给想研究原理的你）

以下是开发过程中实测踩过的坑，也是本项目存在的理由：

1. **helper 不能独立启动**：dsh-dafeiyu 的 helper 进程脱离 dsh 服务后，10 秒内必定自杀（stdio 协议无握手对象）。所以"启动桌宠"必须由服务重生 helper，实现上是「隐藏/显示窗口」而非「启动/杀进程」。
2. **杀 helper 没用**：dsh 服务会 2 秒内重生被杀的 helper。
3. **helper 会自己弹控制台**：启动时 AllocConsole 打印 JSON 协议（`{"protocolVersion":1,...}`）。给它 CREATE_NO_WINDOW 的隐藏控制台 + 托盘监控兜底隐藏。
4. **pystray 并发 stop 会死锁**：watchdog 线程和菜单退出 handler 同时调 `icon.stop()` 会卡死消息循环。必须加锁保证全进程只 stop 一次。
5. **psutil 枚举会崩**：系统里有受保护进程，无防护的 `process_iter` 访问 cmdline 直接崩。全部用 `as_dict(ad_value=None)` + try/except。
6. **netstat 输出是 GBK**：Windows 中文环境 `subprocess` 解码必须用 `mbcs`。
7. **图标缓存按路径做键**：换图标内容必须连文件名一起换，`ie4uinit -show` 不够。
8. **重复双击互杀**：托盘单实例用命名互斥锁（`CreateMutex`）而非"新实例杀旧实例"——用户看不到托盘图标（收在 `^` 里）时会反复双击，互杀最后归零。

## License

MIT
