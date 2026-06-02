# BiliSteamSign

自动将 Steam 游戏状态同步为 B站 个人签名。

> 起因是看了 [BV1UtV564Eqi](https://www.bilibili.com/video/BV1UtV564Eqi) 这个视频，发现是付费功能，于是一清二白的火速搓了一个自用。

## 功能

- 实时检测 Steam 正在运行的游戏（通过注册表轮询）
- 自动将游戏名写入 B站 个人签名
- 游戏退出后自动恢复原签名
- 扫码登录，Cookie 加密存储（DPAPI）
- 系统托盘后台运行
- 自定义签名模板、排除游戏列表、签名长度限制
- 开机自启（可选）

## 使用

下载 [最新 Release](../../releases) 的 `BiliSteamSign.zip`，解压后双击 `BiliSteamSign.exe` 即可运行。

首次使用点击"扫码登录"，用B站APP扫码完成登录。

## 签名模板占位符

| 占位符 | 说明 |
|--------|------|
| `{game}` | 游戏名称 |
| `{appid}` | Steam 游戏ID |
| `{uname}` | B站昵称 |

示例：`{uname} 正在玩 {game}` → "小明 正在玩 艾尔登法环"

## 数据存储

- 配置：`%APPDATA%/BiliSteamSign/config.json`
- 凭证（加密）：`%LOCALAPPDATA%/BiliSteamSign/credentials.enc`
- 日志：`%APPDATA%/BiliSteamSign/logs/`

## 许可证

MIT License
