# -*- coding: utf-8 -*-
"""无浏览器环境下检查出图脚本产出的图里，文字有没有互相压到。

做法：拦截 Figure.savefig 把每个 figure 留下来，用 Agg renderer 取每个文字对象的
window_extent，两两求交。坐标轴被 axis('off') 关掉的那些刻度标签不可见，跳过。

    python check-fig-overlap.py                 # 检查两个 render 脚本
    python check-fig-overlap.py render-xxx.py   # 只检查指定脚本
"""
import runpy
import io
import os
import re
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding='utf-8')

TARGETS = ['render-theory-figs.py', 'render-bunny-figs.py']


def collect(script):
    """执行出图脚本，返回 [(保存路径, figure), ...]"""
    saved, logs = [], []

    def fake_savefig(self, *a, **k):
        saved.append(self)

    def fake_close(*a, **k):
        pass

    orig_savefig = matplotlib.figure.Figure.savefig
    orig_close = plt.close
    matplotlib.figure.Figure.savefig = fake_savefig
    plt.close = fake_close
    try:
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            # run_name='__main__'：出图脚本的主流程通常在 __main__ 块里
            runpy.run_path(script, run_name='__main__')
        finally:
            sys.stdout = old
        logs = buf.getvalue().splitlines()
    finally:
        matplotlib.figure.Figure.savefig = orig_savefig
        plt.close = orig_close

    names = []
    for ln in logs:
        m = re.search(r'→\s*(.+\.png)', ln)
        if m:
            names.append(m.group(1).strip())
    if len(names) != len(saved):
        names = [f'figure[{i}]' for i in range(len(saved))]
    return list(zip(names, saved))


def bbox(art, r):
    try:
        b = art.get_window_extent(renderer=r)
    except Exception:
        return None
    return b if (b.width > 0 and b.height > 0) else None


def items_of(fig, r):
    out = []
    for ax in fig.axes:
        if not ax.get_visible():
            continue
        for t in list(ax.texts) + [ax.title]:
            if t.get_visible() and t.get_text().strip():
                b = bbox(t, r)
                if b:
                    out.append(('text', t.get_text()[:24].replace('\n', '/'), b))
        if ax.axison:                       # 只统计坐标轴真的开着的刻度标签
            for tk in ax.get_xticklabels() + ax.get_yticklabels():
                if tk.get_visible() and tk.get_text().strip():
                    b = bbox(tk, r)
                    if b:
                        out.append(('tick', tk.get_text(), b))
    sup = getattr(fig, '_suptitle', None)
    for t in fig.texts:
        if t is sup:                        # suptitle 也在 fig.texts 里，下面单独统计
            continue
        b = bbox(t, r)
        if b:
            out.append(('figtext', t.get_text()[:24], b))
    for lg in fig.legends:
        b = bbox(lg, r)
        if b:
            out.append(('legend', '<图例整块>', b))
        for t in lg.get_texts():
            b = bbox(t, r)
            if b:
                out.append(('legendtext', t.get_text()[:18], b))
    if sup is not None:
        b = bbox(sup, r)
        if b:
            out.append(('suptitle', sup.get_text()[:24], b))
    return out


def check(fig, name):
    r = fig.canvas.get_renderer()
    fig.canvas.draw()
    items = items_of(fig, r)
    bad = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            (k1, t1, b1), (k2, t2, b2) = items[i], items[j]
            if k1.startswith('legend') and k2.startswith('legend'):
                continue
            ix = min(b1.x1, b2.x1) - max(b1.x0, b2.x0)
            iy = min(b1.y1, b2.y1) - max(b1.y0, b2.y0)
            if ix > 1.0 and iy > 1.0:
                bad.append((k1, t1, k2, t2, ix, iy))
    W, H = fig.canvas.get_width_height()
    # 文字是否被画布切掉
    clipped = [(k, t) for k, t, b in items
               if b.x0 < -1 or b.y0 < -1 or b.x1 > W + 1 or b.y1 > H + 1]
    ok = (not bad) and (not clipped)
    print('%-28s %4dx%-4d  受检 %2d 项  重叠 %d  出界 %d  %s'
          % (os.path.basename(name), W, H, len(items), len(bad), len(clipped),
             'OK' if ok else 'FAIL'))
    for k1, t1, k2, t2, ix, iy in bad[:6]:
        print('      重叠 [%s]%r × [%s]%r  %.0f×%.0f px' % (k1, t1, k2, t2, ix, iy))
    for k, t in clipped[:6]:
        print('      出界 [%s]%r' % (k, t))
    return 0 if ok else 1


def main():
    scripts = sys.argv[1:] or [os.path.join(HERE, s) for s in TARGETS]
    fail = 0
    for s in scripts:
        s = s if os.path.isabs(s) else os.path.join(HERE, s)
        print('== %s' % os.path.basename(s))
        for path, fig in collect(s):
            fail |= check(fig, path)
        plt.close('all')
    print('结论：%s' % ('全部无重叠' if fail == 0 else '存在重叠，见上'))
    return fail


if __name__ == '__main__':
    sys.exit(main())
