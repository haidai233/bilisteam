"""构建 exe 发布包"""
import subprocess
import sys
import shutil
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 安装 pyinstaller
subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

# 打包
subprocess.check_call([
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--onedir",
    "--windowed",
    "--name", "BiliSteamSign",
    "--add-data", "start.bat;.",
    "main.py",
])

# 复制 README 到输出目录
dist_dir = os.path.join("dist", "BiliSteamSign")
if os.path.exists("README.md"):
    shutil.copy2("README.md", dist_dir)

print(f"\n构建完成: {os.path.abspath(dist_dir)}")
print("将 dist/BiliSteamSign 整个目录打包为 zip 即可发布。")
