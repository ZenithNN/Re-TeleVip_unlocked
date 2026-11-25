#!/usr/bin/env python3
"""
Re:TeleVip 解锁补丁生成器 v2 —— 字符串锚点定位版（抗 R8 版本漂移）
================================================================

与 v1（按类名硬编码 hf/i5/k5…）不同，本版**按字符串锚点自动定位类**，再按方法
签名取补丁点。R8 full mode 每版会重排类名（a..z / a0..），但字符串字面量不会被
混淆，因此以锚点定位类可以跨 1.6.12 / 1.7 / 1.7.1 / 未来版本复用，无需每版手工
重找类名。

锚点（字符串字面量，均已在 1.7.1 复核唯一或结构性唯一）：

  - 凭证类   cred_class   : 含 "re-televip-account"
  - 高级版子系统 premium   : 含 "PremiumPass" 且含返回凭证类的方法 i()L<cred>;
  - 盗版判决 judge_class   : 含 "CloneKillVerdict"
  - 通知弹窗 notify_class  : 含 "n0t1ce"
  - 构建身份 identity      : 含 "build identity"
  - 设置注册 settings      : 同时含 CloudBackup/DailyCloudBackup/LiveAdListRefresh/PremiumSettings

补丁点（方法签名，跨版稳定）：

  1) premium.d()Z                 -> return true   (高级版子系统可用)
  2) premium.q()Z                 -> return true   (已订阅)
  3) premium.i()L<cred>;          -> 伪证(2100 到期 / 账号不限)
  4) judge.a()Z                   -> return false  (判决查询)
  5) judge.b()Z                   -> return false  (判决入口带弹窗)
  6) judge.c(Ljava/lang/String;)Z -> return false  (接收/落盘判决)
  7) notify.d()V                  -> return-void   (通知弹窗本体)
  8) identity.d()Ljava/lang/String; -> 官方证书 SHA-256 常量 (骗过 CloneKill)

可选优化（--optimize，对应交接简报 §8）：

  9) settings 的注册方法(把条目加入静态 ArrayList 的唯一方法) -> 按 key 过滤，
     摘掉 CloudBackup / DailyCloudBackup / LiveAdListRefresh / PremiumSettings
     四个依赖作者服务器的死入口，避免"此手机上没有你的激活码"之类提示。

用法：
  python3 patch.py --apk TeleVip-1.7.1-release.apk
  python3 patch.py --apk official.apk --optimize --out TeleVip-1.7.1-unlocked-optimized.apk
"""
import argparse, hashlib, os, re, shutil, subprocess, sys, tempfile, zipfile

# ---------------------------------------------------------------------------
# 工具定位：优先用仓库内置的 baksmali/smali 3.0.10（确保 dex 容器格式正确、
# 体积稳定），否则回退到系统 PATH。
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
BAKSMALI_JAR = os.path.join(_HERE, 'tools', 'baksmali.jar')
SMALI_JAR = os.path.join(_HERE, 'tools', 'smali.jar')


def baksmali_cmd():
    return ['java', '-jar', BAKSMALI_JAR] if os.path.exists(BAKSMALI_JAR) else ['baksmali']


def smali_cmd():
    return ['java', '-jar', SMALI_JAR] if os.path.exists(SMALI_JAR) else ['smali']

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
CERT_SHA256 = "044e2c8aade4dbda44a2d9c40826ce1a33821fde51ade86bf0a80cad7d35c0bf"

DEAD_KEYS = ["CloudBackup", "DailyCloudBackup", "LiveAdListRefresh", "PremiumSettings"]

# 伪凭证时间：iat=0x65000000(2023-09-12)，exp/until=0xf485e680(2100-01-01)。
# 用 2100 而非 0x7fffffff(2038-01-19)，避开 32 位时间戳崖（交接简报 §7.3）。
IAT  = "0x65000000"
EXP  = "0xf485e680L"   # L 后缀 => 64 位长整型，4102416000ms = 2100-01-01


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"命令失败: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r.stdout


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# smali 解析：把目录里的类 -> 方法体指令序列（规范化，去行号/标签/注释）
# ---------------------------------------------------------------------------
def parse_smali_dir(smali_dir):
    """返回 { (class_name, method_decl): [norm_instr, ...] }"""
    out = {}
    for root, _, files in os.walk(smali_dir):
        for fn in files:
            if not fn.endswith('.smali'):
                continue
            cls = None
            cur = None
            buf = []
            path = os.path.join(root, fn)
            for ln in open(path, encoding='utf-8', errors='replace'):
                s = ln.strip()
                if s.startswith('.class'):
                    m = re.search(r'L([^;]+);', s)
                    cls = m.group(1) if m else s
                    continue
                if s.startswith('.method'):
                    cur = (cls, s)
                    buf = []
                    continue
                if s.startswith('.end method'):
                    if cur:
                        out[cur] = buf
                    cur = None
                    continue
                if cur is None or not s or s.startswith(('.', '#', ':')):
                    continue
                # 规范化：标签跳转只留指令助记符
                toks = s.split()
                if toks and (toks[0].startswith(('goto', 'if-')) or
                             toks[0] in ('packed-switch', 'sparse-switch')):
                    s = toks[0]
                buf.append(s)
    return out


def read_smali_file(smali_dir, cls):
    """按类名读回 smali 文件文本。类名形如 lf / com.my.televip.xposed.X。"""
    path = os.path.join(smali_dir, cls + '.smali')
    if not os.path.exists(path):
        # 支持默认包（无 /）与带包路径
        hits = []
        for root, _, files in os.walk(smali_dir):
            if cls + '.smali' in files:
                hits.append(os.path.join(root, cls + '.smali'))
        if len(hits) == 1:
            path = hits[0]
        else:
            raise KeyError(f"找不到类文件 {cls}（命中 {len(hits)} 个）")
    return open(path, encoding='utf-8', errors='replace').read(), path


def write_smali_file(smali_dir, cls, text):
    _, path = read_smali_file(smali_dir, cls)
    open(path, 'w', encoding='utf-8').write(text)


# ---------------------------------------------------------------------------
# 锚点定位
# ---------------------------------------------------------------------------
def class_contains(smali_dir, cls, needle):
    try:
        txt, _ = read_smali_file(smali_dir, cls)
    except KeyError:
        return False
    return needle in txt


def classes_containing(smali_dir, needle):
    """返回所有包含某字符串字面量的类名列表。"""
    hits = []
    for root, _, files in os.walk(smali_dir):
        for fn in files:
            if not fn.endswith('.smali'):
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, smali_dir)
            cls = rel[:-6].replace(os.sep, '/')
            if needle in open(path, encoding='utf-8', errors='replace').read():
                hits.append(cls)
    return hits


def class_methods(smali_dir, cls):
    """返回某类的全部方法声明列表（含 .method 行原文）。"""
    txt, _ = read_smali_file(smali_dir, cls)
    return re.findall(r'^\.method\b.*$', txt, flags=re.M)


def method_exists(smali_dir, cls, sig_re):
    for decl in class_methods(smali_dir, cls):
        if re.search(sig_re, decl):
            return True
    return False


def locate(smali_dir):
    """按锚点定位全部类，返回 dict。"""
    # 1) 凭证类：唯一含 "re-televip-account"
    cred = classes_containing(smali_dir, 're-televip-account')
    assert len(cred) == 1, f"凭证类锚点命中 {len(cred)} 个: {cred}"
    cred = cred[0]

    # 2) 高级版子系统：含 "PremiumPass" 且含 i()L<cred>;
    premium = None
    for c in classes_containing(smali_dir, 'PremiumPass'):
        if method_exists(smali_dir, c, rf'\.method\s+public\s+static\s+i\(\)L{re.escape(cred)};'):
            premium = c
            break
    assert premium, "未找到高级版子系统类（PremiumPass + i()L<cred>;）"

    # 3) 盗版判决：唯一含 "CloneKillVerdict"
    judge = classes_containing(smali_dir, 'CloneKillVerdict')
    assert len(judge) == 1, f"判决类锚点命中 {len(judge)} 个: {judge}"
    judge = judge[0]

    # 4) 通知弹窗：唯一含 "n0t1ce"
    notify = classes_containing(smali_dir, 'n0t1ce')
    assert len(notify) == 1, f"通知类锚点命中 {len(notify)} 个: {notify}"
    notify = notify[0]

    # 5) 构建身份：唯一含 "build identity"
    identity = classes_containing(smali_dir, 'build identity')
    assert len(identity) == 1, f"身份类锚点命中 {len(identity)} 个: {identity}"
    identity = identity[0]

    # 6) 设置注册：同时含 4 个死入口 key
    settings = None
    for c in classes_containing(smali_dir, 'CloudBackup'):
        if all(class_contains(smali_dir, c, k) for k in DEAD_KEYS):
            settings = c
            break
    assert settings, "未找到设置注册类（需同时含 4 个死入口 key）"

    return {
        'cred': cred,
        'premium': premium,
        'judge': judge,
        'notify': notify,
        'identity': identity,
        'settings': settings,
    }


# ---------------------------------------------------------------------------
# 方法体替换
# ---------------------------------------------------------------------------
def replace_method(text, header, new_body):
    lines = text.splitlines(keepends=True)
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == header.strip():
            start = i
            break
    if start is None:
        raise KeyError(f"未找到方法: {header}")
    end = None
    for j in range(start + 1, len(lines)):
        if lines[j].strip() == '.end method':
            end = j
            break
    if end is None:
        raise KeyError(f"方法缺少 .end method: {header}")
    body = [header + '\n'] + ['    ' + x + '\n' for x in new_body.splitlines()] + ['.end method\n']
    lines[start:end + 1] = body
    return ''.join(lines)


def find_method_decl(smali_dir, cls, sig_re):
    """按正则找方法声明行（原样返回）。"""
    for decl in class_methods(smali_dir, cls):
        if re.search(sig_re, decl):
            return decl
    raise KeyError(f"{cls} 中找不到匹配 {sig_re} 的方法")


# ---------------------------------------------------------------------------
# 补丁体生成
# ---------------------------------------------------------------------------
def body_ret_z(v):
    return f".registers 1\nconst/4 v0, 0x{v:x}\nreturn v0"


def body_fake_cred(cred):
    return (".registers 9\n"
            f"const-wide v2, {IAT}\n"
            f"const-wide v4, {EXP}\n"
            f"const-wide v6, {EXP}\n"
            "const/4 v8, 0x0\n"                        # Set=null -> 账号不限
            f"new-instance v1, L{cred};\n"
            f"invoke-direct/range {{v1 .. v8}}, L{cred};-><init>(JJJLjava/util/Set;)V\n"
            "return-object v1")


def body_return_void():
    return ".registers 0\nreturn-void"


def body_identity():
    return f'.registers 1\nconst-string v0, "{CERT_SHA256}"\nreturn-object v0'


# ---------------------------------------------------------------------------
# 核心解锁补丁
# ---------------------------------------------------------------------------
def apply_core_patches(smali_dir, loc):
    cred = loc['cred']
    patches = [
        (loc['premium'], r'\.method\s+public\s+static\s+d\(\)Z',
         body_ret_z(1), '高级版子系统可用 -> 恒 true'),
        (loc['premium'], r'\.method\s+public\s+static\s+q\(\)Z',
         body_ret_z(1), '已订阅 -> 恒 true'),
        (loc['premium'], rf'\.method\s+public\s+static\s+i\(\)L{re.escape(cred)};',
         body_fake_cred(cred), '凭证 -> 伪证(2100 到期/账号不限)'),
        (loc['judge'], r'\.method\s+public\s+static\s+a\(\)Z',
         body_ret_z(0), '判决查询 -> 恒 false'),
        (loc['judge'], r'\.method\s+public\s+static\s+b\(\)Z',
         body_ret_z(0), '判决入口(带弹窗) -> 恒 false'),
        (loc['judge'], r'\.method\s+public\s+static\s+c\(Ljava/lang/String;\)Z',
         body_ret_z(0), '接收判决 -> 不采信/不落盘'),
        (loc['notify'], r'\.method\s+public\s+static\s+d\(\)V',
         body_return_void(), '通知弹窗本体 -> return-void'),
        (loc['identity'], r'\.method\s+public\s+static\s+d\(\)Ljava/lang/String;',
         body_identity(), '构建身份 -> 官方证书 SHA-256'),
    ]
    results = []
    for cls, sig_re, body, desc in patches:
        decl = find_method_decl(smali_dir, cls, sig_re)
        txt, _ = read_smali_file(smali_dir, cls)
        txt = replace_method(txt, decl, body)
        write_smali_file(smali_dir, cls, txt)
        print(f"  - {cls}.{decl.split()[-1]:40} {desc}")
        results.append((cls, decl))
    return results


# ---------------------------------------------------------------------------
# 可选优化：隐藏死入口
# ---------------------------------------------------------------------------
def _find_register_method(smali_dir, settings):
    """在设置类中找『把条目 add 进静态 ArrayList 的唯一注册方法』。

    特征：方法体含 `sget-object <r>, L<settings>;-><f>:Ljava/util/ArrayList;`
    且 `invoke-virtual {<r>, p0}, Ljava/util/ArrayList;->add`。
    """
    txt, _ = read_smali_file(smali_dir, settings)
    # 找到静态 ArrayList 字段名（.field public static final a:Ljava/util/ArrayList;）
    mf = re.search(r'\.field\s+[^\n]*static[^\n]*?([A-Za-z_$][\w$]*):Ljava/util/ArrayList;', txt)
    assert mf, "设置类中无静态 ArrayList 字段"
    field = mf.group(1)

    # 逐方法判断：注册方法 = 把参数 add 进该静态 ArrayList 的唯一方法
    methods = re.split(r'(?=^\.method\s)', txt, flags=re.M)
    for m in methods:
        if not m.strip().startswith('.method'):
            continue
        if f'L{settings};->{field}:Ljava/util/ArrayList;' in m and \
           'Ljava/util/ArrayList;->add(Ljava/lang/Object;)Z' in m:
            # 提取条目类型（首个引用类型参数）
            decl = m.splitlines()[0]
            pm = re.search(r'\(([^)]*)\)', decl)
            ref = re.findall(r'L([^;]+);', pm.group(1))
            assert ref, f"注册方法无引用类型参数: {decl}"
            item = ref[0]
            # 条目类的 key 字段：第一个非 static 的 String 实例字段
            item_txt, _ = read_smali_file(smali_dir, item)
            kf = re.search(r'\.field\s+(?!static)[^\n]*?([A-Za-z_$][\w$]*):Ljava/lang/String;', item_txt)
            assert kf, f"条目类 {item} 无实例 String 字段"
            keyfield = kf.group(1)
            return decl, item, keyfield, field
    raise AssertionError("未找到设置注册方法")


def apply_dead_entry_filter(smali_dir, loc):
    settings = loc['settings']
    decl, item, keyfield, _ = _find_register_method(smali_dir, settings)

    # 构造过滤后的注册方法体：
    # 命中任一死入口 key -> 直接 return（不加入列表）；
    # 全部未命中       -> 落到 add（正常注册）。
    # 注意必须是 if-nez（命中才跳走），if-eqz 会把整个列表清空。
    checks = []
    for k in DEAD_KEYS:
        checks.append(
            f'const-string v1, "{k}"\n'
            f'invoke-virtual {{v0, v1}}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z\n'
            f'move-result v1\n'
            f'if-nez v1, :cond_skip'
        )
    body = (
        ".registers 3\n"
        f"iget-object v0, p0, L{item};->{keyfield}:Ljava/lang/String;\n"
        + '\n'.join(checks) + "\n"
        f"sget-object v0, L{settings};->a:Ljava/util/ArrayList;\n"
        f"invoke-virtual {{v0, p0}}, Ljava/util/ArrayList;->add(Ljava/lang/Object;)Z\n"
        ":cond_skip\n"
        "return-void"
    )
    # 回归自检：命中死入口才跳走(if-nez)，否则会把整个列表清空（模块入口也随之消失）。
    assert 'if-nez v1, :cond_skip' in body, "死入口过滤方向错误：应为 if-nez（命中才跳过）"
    assert 'if-eqz' not in body, "死入口过滤方向错误：出现了 if-eqz"
    txt, _ = read_smali_file(smali_dir, settings)
    txt = replace_method(txt, decl, body)
    write_smali_file(smali_dir, settings, txt)
    print(f"  - {settings}.{decl.split()[-1]:40} 隐藏死入口(4 个 key 过滤)")
    return [(settings, decl)]


# ---------------------------------------------------------------------------
# 指令级校验
# ---------------------------------------------------------------------------
def verify(orig_dir, patched_dir, expect_methods):
    a = parse_smali_dir(orig_dir)
    b = parse_smali_dir(patched_dir)
    changed = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    expect = set()
    for cls, sig in expect_methods:
        expect.add((cls, sig.split('(')[0]))   # 只比类 + 方法名
    ok = True
    for cls, sig in sorted(changed):
        key = (cls, sig.split('(')[0])
        flag = 'OK ' if key in expect else '!! '
        if flag.startswith('!!'):
            ok = False
        print(f"    {flag}{cls}::{sig}")
    if not ok:
        print("    [警告] 出现预期外的改动")
    return ok, changed


# ---------------------------------------------------------------------------
# 组装 / 对齐 / 签名
# ---------------------------------------------------------------------------
def assemble_apk(official_apk, new_dex, out, work):
    tmp = os.path.join(work, 'unsigned.apk')
    with zipfile.ZipFile(official_apk) as zin, \
         zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            data = zin.read(it.filename)
            if it.filename == 'classes.dex':
                data = open(new_dex, 'rb').read()
            zout.writestr(it, data)
    aligned = os.path.join(work, 'aligned.apk')
    run(['zipalign', '-f', '4', tmp, aligned])

    # 稳定签名 key：优先复用仓库内的 release.jks（保证可覆盖升级），否则生成一次并存盘。
    ks = os.path.join(_HERE, 'keys', 'release.jks')
    if not os.path.exists(ks):
        os.makedirs(os.path.dirname(ks), exist_ok=True)
        run(['keytool', '-genkeypair', '-alias', 'televip', '-keyalg', 'RSA',
             '-keysize', '2048', '-validity', '10950', '-keystore', ks,
             '-storepass', 'televip', '-keypass', 'televip',
             '-dname', 'CN=ReTeleVip Unlocked'])
    run(['apksigner', 'sign', '--ks', ks, '--ks-pass', 'pass:televip',
         '--ks-key-alias', 'televip', '--key-pass', 'pass:televip',
         '--min-sdk-version', '27',
         '--v1-signing-enabled', 'true', '--v2-signing-enabled', 'true',
         '--v3-signing-enabled', 'true',
         '--out', out, aligned])
    return out


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apk', required=True, help='官方 APK 路径')
    ap.add_argument('--out', default=None, help='输出 APK 路径')
    ap.add_argument('--optimize', action='store_true', help='额外应用死入口隐藏优化')
    ap.add_argument('--work', default=None, help='工作目录（默认临时目录）')
    ap.add_argument('--keep-work', action='store_true', help='保留工作目录')
    args = ap.parse_args()

    work = args.work or tempfile.mkdtemp(prefix='televip-anchor-')
    os.makedirs(work, exist_ok=True)
    smali_orig = os.path.join(work, 'smali_orig')
    smali_patch = os.path.join(work, 'smali_patch')
    dex_dir = os.path.join(work, 'dex')
    os.makedirs(dex_dir, exist_ok=True)

    print(f"[*] 官方 APK: {args.apk}  sha256={sha256(args.apk)[:16]}")

    with zipfile.ZipFile(args.apk) as z:
        assert 'classes.dex' in z.namelist(), 'APK 缺少 classes.dex'
        z.extract('classes.dex', dex_dir)
    dex = os.path.join(dex_dir, 'classes.dex')

    print("[*] baksmali 反编译 ...")
    run(baksmali_cmd() + ['d', dex, '-o', smali_orig])
    if os.path.exists(smali_patch):
        shutil.rmtree(smali_patch)
    shutil.copytree(smali_orig, smali_patch)

    print("[*] 锚点定位类 ...")
    loc = locate(smali_patch)
    for k, v in loc.items():
        print(f"    {k:10} -> {v}")

    expect = []
    print("[*] 应用核心解锁补丁:")
    core = apply_core_patches(smali_patch, loc)
    expect += [(c, decl) for c, decl in core]

    if args.optimize:
        print("[*] 应用优化：隐藏死入口")
        opt = apply_dead_entry_filter(smali_patch, loc)
        expect += [(c, decl) for c, decl in opt]

    print("[*] 指令级校验改动范围:")
    ok, changed = verify(smali_orig, smali_patch, expect)
    if not ok:
        print("[!] 补丁范围异常，终止")
        sys.exit(2)
    print(f"    共改动 {len(changed)} 个方法")

    new_dex = os.path.join(work, 'classes_new.dex')
    print("[*] smali 编译新 dex ...")
    # --api 26 => dex 038 容器；避免 --api 35 生成的 041 格式(交接简报 §5.2)
    run(smali_cmd() + ['assemble', '-a', '26', smali_patch, '-o', new_dex])
    print(f"    dex: {os.path.getsize(new_dex)} 字节")

    out = args.out or os.path.join(os.getcwd(), 'TeleVip-unlocked-optimized.apk')
    print("[*] 组装 / 对齐 / 签名 ...")
    assemble_apk(args.apk, new_dex, out, work)

    print("[*] 校验签名 / 对齐:")
    run(['apksigner', 'verify', '--verbose', out])
    run(['zipalign', '-c', '-p', '4', out])

    print(f"\n[完成] {out}")
    print(f"       sha256 = {sha256(out)}")
    if args.keep_work:
        print(f"       工作目录 = {work}")


if __name__ == '__main__':
    main()
