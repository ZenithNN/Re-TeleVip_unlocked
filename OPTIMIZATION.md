# televip-unlocked 破解流程优化 v2 —— 字符串锚点定位

对 `ZenithNN/televip-unlocked` 做了一次**完整流程优化**：把原来按类名硬编码的补丁
脚本（每版 R8 重排都要手工重找类名）改造成**按字符串锚点自动定位**的可复跑流水线，
并补上 1.7.1 支持与「隐藏死入口」优化。

---

## 一、核心思路：锚点定位（抗 R8 版本漂移）

R8 full mode 每版会重排业务类名（`a`…`z`/`a0`…，1.6.12/1.7/1.7.1 各不相同），
但**字符串字面量不会被混淆**。因此用字符串锚点定位类，再按方法签名取补丁点，
即可一套脚本覆盖多个版本。

| 角色 | 锚点（字符串字面量） | 1.6.12 | 1.7 | 1.7.1 |
|---|---|---|---|---|
| 凭证类 | `re-televip-account` | `uc` | `qf` | `sf` |
| 高级版子系统 | `PremiumPass` + 含 `i()L<凭证>;` | `qc` | `hf` | `lf` |
| 盗版判决 | `CloneKillVerdict` | `l3` | `i5` | `k5` |
| 通知弹窗 | `n0t1ce` | `n3` | `k5` | `m5` |
| 构建身份 | `build identity` | `t1` | `i3` | `k3` |
| 设置注册 | 同时含 `CloudBackup`/`DailyCloudBackup`/`LiveAdListRefresh`/`PremiumSettings` | — | — | `t6` |

补丁点（方法签名，跨版稳定）：

1. `premium.d()Z` → 恒 `true`（高级版子系统可用）
2. `premium.q()Z` → 恒 `true`（已订阅）
3. `premium.i()L<凭证>;` → 伪造长期凭证（2100 到期 / 账号不限）
4. `judge.a()Z` → 恒 `false`（判决查询）
5. `judge.b()Z` → 恒 `false`（判决入口带弹窗）
6. `judge.c(Ljava/lang/String;)Z` → 恒 `false`（接收/落盘判决）
7. `notify.d()V` → `return-void`（通知弹窗本体，双保险）
8. `identity.d()Ljava/lang/String;` → 官方证书 SHA-256 常量

## 二、1.7.1 实测结果（本次完整流程）

- 官方 1.7.1（versionCode 392）APK sha256 `fbbb22a2…`，签名 `CN=TeleVip`。
- 锚点定位全部命中：`sf`/`lf`/`k5`/`m5`/`k3`/`t6`，与交接简报 §3 的 1.7.1 表一致。
- 核心解锁 8 处 + 死入口隐藏 1 处 = **9 个方法改动**，指令级校验全部 OK，无预期外改动。
- 产物：`TeleVip-1.7.1-unlocked-optimized.apk`（957,706 B）

```
f75e98412b231fc4400ccd10b4bc5489754e34e26f8e141996ba88600a241a71  TeleVip-1.7.1-unlocked-optimized.apk
```

验证清单（交接简报 §6 全绿）：`apksigner verify`（v2+v3）、`zipalign -c -p 4`、
`unzip -t`、dex magic `dex\n038`、包内 classes.dex sha256 == 构建产物、
文件清单只差 3 个签名文件（`META-INF/xposed/*` 逐字节保留）。

## 三、⚠️ 已撤回：隐藏死入口（交接简报 §8.1）——会导致模块入口消失

> 实测结论：过滤 `t6.a(Lr6;)` 里那 4 个 key 后，Telegram 设置页顶部的
> 「Re: TeleVIP 设置 🛸」入口整体消失（核心版有入口、优化版无入口，唯一差异
> 就是这一处）。根因未完全定位（疑似 `PremiumSettings` 作为 section 头，被移除后
> 破坏了渲染结构，或该列表被多处消费）。**此优化已从交付物中撤回**，待有真机可逐步
> 验证时再单独评估。

设置注册方法 `t6.a(Lr6;)V` 是**唯一**把条目加入静态 ArrayList 的入口。
在其上按 key 过滤，摘掉 4 个依赖作者服务器的死入口：

```
CloudBackup / DailyCloudBackup / LiveAdListRefresh / PremiumSettings
```

避免点进去出现「此手机上没有你的激活码」之类提示。过滤逻辑读的是条目类的
`b` 字段（设置 key），对 section/label/toggle 三类条目统一生效。

## 四、构建流程要点（交接简报 §5，已固化进脚本）

1. 不用 apktool 整包反编译（`resources.arsc` 被改过会崩）。
2. 只解 `classes.dex` → **baksmali 3.0.10** → 改 smali → **smali assemble `-a 26`**
   （输出 dex 038；避免 `--api 35` 的 041 格式）。仓库已内置 3.0.10 的 jar
   （`tools/baksmali.jar`、`tools/smali.jar`），不再依赖系统 PATH。
3. 重打包用 Python `zipfile` 逐条复制原 APK，仅替换 `classes.dex`，保留每个条目
   `compress_type`/时间戳/属性；`META-INF/xposed/*` 原样保留。
4. `zipalign -f 4` → `apksigner sign --v1 --v2 --v3`（RSA2048，minSdk 27 时 v1 可选）。

## 五、使用

```bash
python3 patch.py --apk TeleVip-1.7.1-release.apk --optimize
# 输出 TeleVip-unlocked-optimized.apk（默认），或 --out 指定
```

脚本流程：解 dex → baksmali 3.0.10 反编译 → 锚点定位 → 方法级精确替换 →
指令级范围校验（只允许预期方法）→ smali 3.0.10 编译 → zipalign → 重签名 → 输出 SHA256。

## 六、仍未做 / 待评估（交接简报 §8 其余项）

| 项 | 现状 | 落地难度 |
|---|---|---|
| §8.2 名单本地化 | `PremiumAdListText` 纯文本缓存已确认；刷新源在 `h9` 的 `case 4` | 中（需预置名单或改刷新源） |
| §8.3 本地备份 | `x3`(save)/`b1`(load) 换设备内文件 + 自设口令 AES-GCM | 高（密钥派生逻辑要重写） |
| §8.4 断掉上报 | 活跃上报入口在 1.7.1 已重排，疑似域名池在 `rl` 类 `<clinit>`（含 `771.nz`/`721qs.cc`/`39085.vip`/`103.41.4.58:7899`）；判决已被忽略，上报本身无害 | 低（但定位点需再精确定到 `q.a` 等价常量） |
| §8.6 身份伪装完整性 | `k3.d()` 只改「对外报的证书哈希」；`a1` 类还有一处读被安装 APK 真实签名做比对（APK 安装拦截功能用） | 中（需评估是否要一起骗过） |

> 后两项风险高于收益，未在本次「完整流程」里盲改；锚点定位已就位，后续可随时按
> 锚点补丁。

---

## 七、1.7.2 验证（锚点定位首次实战）

上游紧急发布 1.7.2（versionCode 393），R8 全量重排。直接用本脚本跑官方包，
**零手工干预**自动命中全部类：

| 角色 | 1.7.1 | 1.7.2 |
|---|---|---|
| 凭证类 | `sf` | `uf` |
| 高级版子系统 | `lf` | `nf` |
| 盗版判决 | `k5` | `m5` |
| 通知弹窗 | `m5` | `o5` |
| 构建身份 | `k3` | `m3` |

8 个核心补丁一次命中，指令级校验全 OK，产物 `TeleVip-1.7.2-unlocked-core.apk`
sha256 `fe359488bac1356686c8e8ce5af7194559511dd1dedccaa8ac400ab475c82206`。
证明「字符串锚点定位」确实扛住了版本漂移，后续版本无需手工重找类名。
