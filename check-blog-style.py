# -*- coding: utf-8 -*-
"""blog 交付前校验：禁用句式、块级公式配对、行内公式配对、图片引用存在。"""
import os, re, sys, glob

HERE = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(HERE, 'blog-bunny-tutte.md')
src = open(path, encoding='utf-8').read()
lines = src.split('\n')
sys.stdout.reconfigure(encoding='utf-8')

BAD = [r'不是[^。；\n]{0,30}而是', r'并非[^。；\n]{0,30}而是', r'先不看[^。；\n]{0,20}而看',
       r'不只是[^。；\n]{0,20}更是', r'不在于[^。；\n]{0,20}而在于', r'与其说[^。；\n]{0,20}不如说',
       r'不仅仅?是[^。；\n]{0,20}更', r'说到底', r'不妨说', r'某种意义上',
       r'让我们', r'值得一提', r'总而言之', r'综上', r'如上所述']
hit = []
for i, ln in enumerate(lines, 1):
    for b in BAD:
        if re.search(b, ln):
            hit.append((i, b, ln.strip()[:60]))
print(f'禁用句式命中: {len(hit)}')
for h in hit:
    print('   ', h)

block = src.count('$$')
inline = len(re.findall(r'(?<!\$)\$(?!\$)', src))
print(f'块级公式 $$ 计数: {block}（{"配对 OK" if block % 2 == 0 else "不配对 ✗"}）')
print(f'行内 $ 计数: {inline}（{"配对 OK" if inline % 2 == 0 else "不配对 ✗"}）')

imgs = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', src)
miss = [p for p in imgs if not os.path.exists(os.path.join(HERE, p))]
print(f'图片引用: {len(imgs)} 张，缺失 {len(miss)} 张')
for m in miss:
    print('    缺:', m)
print('   ', ' '.join(os.path.basename(p) for p in imgs))

print(f'字数: 正文 {len(src)} 字符 / {len(lines)} 行')
