@echo off
rem dsh-tray 一键打包脚本（需要已安装 Python 3.10+）
cd /d "%~dp0"
echo [1/3] 安装依赖...
pip install -r requirements.txt pyinstaller || goto :err
echo [2/3] 生成默认图标...
python -c "import core; core.ensure_icon()" || goto :err
echo [3/3] 构建 dsh-tray.exe（约 2~5 分钟）...
pyinstaller --noconsole --onefile --name dsh-tray --icon assets\dsh.ico dsh_tray.py || goto :err
echo.
echo 完成！exe 位于 dist\dsh-tray.exe
pause
exit /b 0
:err
echo 构建失败，请检查上方错误信息。
pause
exit /b 1
