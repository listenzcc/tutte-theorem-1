# -*- coding: utf-8 -*-
"""文档交付前校验：禁用句式、公式配对、本地链接/图片存在。

用法：python check-blog-style.py [文件 ...]
不给参数时校验默认三件：blog-bunny-tutte.md、README.md、index.html
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = ['blog-bunny-tutte.md', 'README.md', 'index.html']
sys.stdout.reconfigure(encoding='utf-8')

BAD = [r'不是[^。；\n]{0,30}而是', r'并非[^。；\n]{0,30}而是', r'先不看[^。；\n]{0,20}而看',
       r'不只是[^。；\n]{0,20}更是', r'不在于[^。；\n]{0,20}而在于', r'与其说[^。；\n]{0,20}不如说',
       r'不仅仅?是[^。；\n]{0,20}更', r'说到底', r'不妨说', r'某种意义上',
       r'让我们', r'值得一提', r'总而言之', r'综上', r'如上所述']

targets = sys.argv[1:] or DEFAULT
allok = True

for name in targets:
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        print(f'[{name}] 文件不存在 ✗')
        allok = False
        continue
    src = open(path, encoding='utf-8').read()
    lines = src.split('\n')
    print(f'--- {name} ---')

    hit = [(i, b, ln.strip()[:60]) for i, ln in enumerate(lines, 1) for b in BAD
           if re.search(b, ln)]
    print(f'  禁用句式命中: {len(hit)}')
    for h in hit:
        print('    行%4d  %s  | %s' % h)
    allok &= not hit

    block = src.count('$$')
    inline = len(re.findall(r'(?<!\$)\$(?!\$)', src))
    if block:
        print(f'  块级公式 $$ 计数: {block}（{"配对 OK" if block % 2 == 0 else "不配对 ✗"}）')
        allok &= block % 2 == 0
    if inline:
        print(f'  行内 $ 计数: {inline}（{"配对 OK" if inline % 2 == 0 else "不配对 ✗"}）')
        allok &= inline % 2 == 0

    # 图片与本地链接
    imgs = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', src)
    hrefs = re.findall(r'href="([^"]+)"', src)
    mds = re.findall(r'\]\(([^)]+)\)', src)
    local = [p for p in imgs + hrefs + mds
             if not p.startswith(('http', '#', 'mailto:', 'data:'))]
    miss = [p for p in local if not os.path.exists(os.path.join(HERE, p))]
    print(f'  本地引用: {len(local)} 个，缺失 {len(miss)} 个'
          f'{"  ✓" if not miss else "  ✗"}')
    for m in miss:
        print('    缺:', m)
    allok &= not miss

    print(f'  篇幅: {len(src)} 字符 / {len(lines)} 行')

print('\n全部通过 ✓' if allok else '\n有未通过项 ✗')
sys.exit(0 if allok else 1)
