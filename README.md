<p align="center"><img src="banner.png" width="640" alt="Re: TeleVIP Unlocked"></p>

# Re:TeleVip — 本地解锁版

Re: TeleVIP 的本地解锁补丁：去掉服务器判决、付费门控和「盗版判定」弹窗，让模块内置功能在本地可用。仅供研究与自用。

## 下载

见 [Releases](../../releases)，校验值在 [SHA256SUMS.txt](SHA256SUMS.txt)。

## 需要

- LSPosed / Vector（API 102）或 LSPatch
- Android 8.1+（minSdk 27）

## 安装

1. 卸载已装的 Re: TeleVIP（官方版或其它破解版），保留 Telegram。
2. 安装 Release 里的 `TeleVip-<版本>-unlocked.apk`。
3. LSPosed → 模块 → 启用 **Re: TeleVIP** → 作用域勾选 Telegram。
4. 强停 Telegram，再打开。

> 各版本签名可能不同，覆盖装不上就先卸载重装；卸载会清掉作用域，装完需重新勾选。

## 改了什么

见 [PATCHES.md](PATCHES.md)。一句话：付费状态恒激活、不采信服务器盗版判决、构建身份伪装成官方签名。

## 已知限制

- 云备份、实时广告/诈骗词库刷新依赖作者服务器，不可用。
- Telegram 服务端按账号校验的东西（真 Premium、下载加速等）绕不过。

## License

1.5.3 及以前的 GPL-3.0 部分按 GPL-3.0 提供；其余仅作研究与兼容用途分发。
