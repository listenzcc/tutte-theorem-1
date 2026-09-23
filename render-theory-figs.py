# -*- coding: utf-8 -*-
"""
blog-tutte-theory.md 的配图。

几何与 tutte-embedding-theorem.html 完全一致：同一张参数曲面、同一套三角形绕向、
同一种 MVC 权重、边界按 3D 弧长比例分配到目标形状。区别只在于这里用 scipy 直接解
线性系统（页面是 Gauss-Seidel 迭代）。

运行：
  C:/Users/liste/miniconda3/envs/python3.11/python.exe render-theory-figs.py

输出：figs/theory1-setup.png ... theory4-topology.png
"""
import os
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.collections import PolyCollection
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from mpl_toolkits.mplot3d.art3d import Line3DCollection

_PREF = ('msyh.ttc', 'msyhbd.ttc', 'msyhl.ttc', 'simhei.ttf', 'simsun.ttc', 'deng.ttf')
_fonts = {os.path.basename(f).lower(): f for f in fm.findSystemFonts()}
_pick = next((_fonts[n] for n in _PREF if n in _fonts), None)
if _pick:
    fm.fontManager.addfont(_pick)
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = [fm.FontProperties(fname=_pick).get_name()]
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 10

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'figs')
os.makedirs(OUT, exist_ok=True)

BLUE = '#2f6fd0'
RED = '#cf4438'
ORANGE = '#e08a2c'
GREEN = '#17864f'
GREY = '#5b6573'
LINE = '#c6ced9'
FACE = '#eef2f7'
FACE_IN = '#ffffff'

NR, NS = 10, 36


# ------------------------------------------------------------------ 网格
def height_at(x, z, amp=1.0):
    A = 0.55 * amp
    h1 = A * np.exp(-((x - 0.35) ** 2 + (z - 0.15) ** 2) / 0.10)
    h2 = 0.80 * A * np.exp(-((x + 0.30) ** 2 + (z + 0.35) ** 2) / 0.07)
    h3 = -0.55 * A * np.exp(-((x + 0.10) ** 2 + (z - 0.42) ** 2) / 0.06)
    h4 = 0.40 * A * np.sin(3.0 * x) * np.cos(3.0 * z)
    return h1 + h2 + h3 + h4


def build_mesh():
    vid = lambda i, j: 1 + (i - 1) * NS + (j % NS)
    P = np.zeros((1 + NR * NS, 3))
    P[0] = [0.0, height_at(0.0, 0.0), 0.0]
    ring = np.zeros(1 + NR * NS, int)
    for i in range(1, NR + 1):
        r = i / NR
        for j in range(NS):
            th = 2 * np.pi * j / NS
            x, z = r * np.cos(th), r * np.sin(th)
            P[vid(i, j)] = [x, height_at(x, z), z]
            ring[vid(i, j)] = i
    F = []
    for i in range(1, NR + 1):
        for j in range(NS):
            j2 = (j + 1) % NS
            if i == 1:
                F.append([0, vid(1, j), vid(1, j2)])
            else:
                a, b = vid(i - 1, j), vid(i - 1, j2)
                c, d = vid(i, j2), vid(i, j)
                F.append([a, d, c])
                F.append([a, c, b])
    return P, np.array(F), ring, vid


# ------------------------------------------------------------------ 目标形状
SHAPES = {
    'circle': None,
    'square': np.array([[1, 1], [-1, 1], [-1, -1], [1, -1]], float),
    'star': np.array([[ (0.42 if i % 2 else 1.0) * np.cos(-np.pi/2 + i*np.pi/5),
                        (0.42 if i % 2 else 1.0) * np.sin(-np.pi/2 + i*np.pi/5)]
                      for i in range(10)]),
    'ell': np.array([[1, 1], [-0.15, 1], [-0.15, -0.2], [-1, -0.2], [-1, -1], [1, -1]], float),
}
CONVEX = {'circle': True, 'square': True, 'star': False, 'ell': False}


def shape_curve(name, n=400):
    if name == 'circle':
        a = np.linspace(0, 2 * np.pi, n, endpoint=True)
        return np.c_[np.cos(a), np.sin(a)]
    pts = SHAPES[name]
    seg = []
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        seg.append(np.linspace(a, b, n // len(pts), endpoint=False))
    return np.vstack(seg)


def shape_point(name, t):
    """t ∈ [0,1) 按弧长取点"""
    if name == 'circle':
        a = 2 * np.pi * t
        return np.array([np.cos(a), np.sin(a)])
    pts, n = SHAPES[name], len(SHAPES[name])
    seg = [np.hypot(*(pts[(i + 1) % n] - pts[i])) for i in range(n)]
    total = sum(seg)
    d = t * total
    for i in range(n):
        if d <= seg[i] or i == n - 1:
            s = min(d / seg[i], 1) if seg[i] > 0 else 0
            return pts[i] + (pts[(i + 1) % n] - pts[i]) * s
        d -= seg[i]
    return pts[0]


# ------------------------------------------------------------------ Tutte
def boundary_arclen(P, bnd):
    """闭环上每个顶点的累积弧长比例"""
    n = len(bnd)
    cum = np.zeros(n + 1)
    for j in range(n):
        a, b = P[bnd[j]], P[bnd[(j + 1) % n]]
        cum[j + 1] = cum[j] + np.linalg.norm(b - a)
    return cum / cum[-1]


def mvc_weights(P, F, interior):
    """均值坐标权重：返回 {i: (neighbors, weights)}，权重未归一化"""
    edge = {}
    for (a, b, c) in F:
        for (i, j, k) in ((a, b, c), (b, c, a), (c, a, b)):
            ui, uj, uk = P[j] - P[i], P[k] - P[i], P[k] - P[j]
            li, lj = np.linalg.norm(ui), np.linalg.norm(uj)
            if li < 1e-12 or lj < 1e-12:
                ang = np.pi / 3
            else:
                ang = np.arccos(np.clip(ui @ uj / (li * lj), -1, 1))
            key = (min(i, j), max(i, j))
            e = edge.setdefault(key, {'tan_lo': 0.0, 'tan_hi': 0.0, 'len': np.linalg.norm(P[i] - P[j])})
            t = np.tan(min(ang, np.pi * 0.999) / 2)
            if i == key[0]:
                e['tan_lo'] += t
            else:
                e['tan_hi'] += t
    adj = {}
    for (a, b, c) in F:
        for (i, j) in ((a, b), (b, c), (c, a)):
            adj.setdefault(i, set()).add(j)
            adj.setdefault(j, set()).add(i)
    rows = {}
    for i in interior:
        js = sorted(adj[i])
        ws = []
        for j in js:
            e = edge[(min(i, j), max(i, j))]
            tan = e['tan_lo'] if i == min(i, j) else e['tan_hi']
            ws.append(tan / max(e['len'], 1e-9))
        rows[i] = (js, np.array(ws))
    return rows


def solve_tutte(P, F, interior, bnd, shape):
    """解凸组合方程，返回 UV (NV,2)"""
    NV = len(P)
    UV = np.zeros((NV, 2))
    t = boundary_arclen(P, bnd)
    for j, v in enumerate(bnd):
        UV[v] = shape_point(shape, t[j])
    rows = mvc_weights(P, F, interior)
    idx = {v: k for k, v in enumerate(interior)}
    n = len(interior)
    mat = sp.lil_matrix((n, n))
    rhs = np.zeros((n, 2))
    inb = set(bnd)
    for i in interior:
        js, ws = rows[i]
        s = ws.sum()
        if abs(s) < 1e-12:
            continue
        wn = ws / s
        r = idx[i]
        mat[r, r] = 1.0
        for w, j in zip(wn, js):
            if j in idx:
                mat[r, idx[j]] -= w
            elif j in inb:
                rhs[r] += w * UV[j]
    sol = spla.spsolve(mat.tocsr(), rhs)
    for i in interior:
        UV[i] = sol[idx[i]]
    return UV


def flip_count(UV, F, tris):
    a, b, c = F[tris, 0], F[tris, 1], F[tris, 2]
    s = (UV[b, 0] - UV[a, 0]) * (UV[c, 1] - UV[a, 1]) - (UV[c, 0] - UV[a, 0]) * (UV[b, 1] - UV[a, 1])
    return int((s <= 0).sum()), s


# ------------------------------------------------------------------ 绘图辅助
def tri_mesh_2d(ax, UV, F, facecolor=FACE_IN, edgecolor=LINE, lw=0.5, flips=None):
    polys = UV[F][:, :, :]
    pc = PolyCollection(polys, facecolors=facecolor, edgecolors=edgecolor, linewidths=lw)
    ax.add_collection(pc)
    if flips is not None and len(flips):
        pc2 = PolyCollection(UV[F[flips]], facecolors=RED, edgecolors=RED, linewidths=0.6, alpha=0.75)
        ax.add_collection(pc2)
    ax.autoscale_view()
    ax.set_aspect('equal')
    ax.set_xticks([])
    ax.set_yticks([])
    for sp_ in ax.spines.values():
        sp_.set_color(LINE)


def q3(ax, P, F, tris, colors, elev=26, azim=-58, lw=0.0):
    """mplot3d：坐标置换 (x,y,z) → (x,z,y)，因为 mplot3d 的 up 是 z"""
    Q = P[:, [0, 2, 1]]
    ax.add_collection3d(Poly3DCollection(Q[F[tris]], facecolors=colors, linewidths=lw, shade=False))
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    r = 1.05
    ax.set_xlim(-r, r); ax.set_ylim(-r, r); ax.set_zlim(-0.45, 0.45)
    try:
        ax.set_box_aspect((1, 1, 0.55))
    except Exception:
        pass


# ================================================================== 图 1
def fig_setup():
    P, F, ring, vid = build_mesh()
    k = 8
    bnd = [vid(k, j) for j in range(NS)]
    interior = [0] + [vid(i, j) for i in range(1, k) for j in range(NS)]
    active = [f for f, t in enumerate(F) if all(ring[v] <= k for v in t)]
    outside = [f for f in range(len(F)) if f not in set(active)]
    UV = solve_tutte(P, F, interior, bnd, 'circle')

    fig = plt.figure(figsize=(13.2, 4.5))
    fig.subplots_adjust(left=0.01, right=0.99, top=0.90, bottom=0.02, wspace=0.18)

    # (a) 3D 区域
    ax = fig.add_subplot(1, 3, 1, projection='3d')
    q3(ax, P, F, outside, [FACE] * len(outside))
    q3(ax, P, F, active, ['#ffffff'] * len(active))
    Q = P[:, [0, 2, 1]]
    lp = [Q[bnd + [bnd[0]]]]
    ax.add_collection3d(Line3DCollection(lp, colors=BLUE, linewidths=2.6))
    ax.set_title('(a) 曲面上的圆盘区域与闭环', fontsize=11, pad=2)

    # (b) 边界按弧长分配
    ax = fig.add_subplot(1, 3, 2)
    t = boundary_arclen(P, bnd)
    th_out, th_in = 2 * np.pi * t, np.linspace(0, 2 * np.pi, NS, endpoint=False)
    R1, R0 = 1.0, 0.62
    ax.plot(R1 * np.cos(th_out), R1 * np.sin(th_out), '-', color=BLUE, lw=1.6)
    ax.scatter(R1 * np.cos(th_out), R1 * np.sin(th_out), s=14, color=BLUE, zorder=3)
    ax.scatter(R0 * np.cos(th_in), R0 * np.sin(th_in), s=14, color=GREY, zorder=3)
    for j in range(0, NS, 3):
        ax.plot([R0 * np.cos(th_in[j]), R1 * np.cos(th_out[j])],
                [R0 * np.sin(th_in[j]), R1 * np.sin(th_out[j])],
                color=LINE, lw=0.7, zorder=1)
    ac = np.linspace(0, 2 * np.pi, 300)
    ax.plot(np.cos(ac), np.sin(ac), '--', color=BLUE, lw=0.8, alpha=0.5)
    ax.text(0, 1.20, '外环：按 3D 弧长 $t_j$ 分配', color=BLUE, ha='center', fontsize=10)
    ax.text(0, -1.30, '内环：按顶点序号均分', color=GREY, ha='center', fontsize=10)
    ax.set_xlim(-1.35, 1.35); ax.set_ylim(-1.45, 1.45)
    ax.set_aspect('equal'); ax.axis('off')
    ax.set_title('(b) 闭环钉到单位圆', fontsize=11, pad=2)

    # (c) UV 摊平
    ax = fig.add_subplot(1, 3, 3)
    tri_mesh_2d(ax, UV, F[active], facecolor='#ffffff', edgecolor=LINE, lw=0.45)
    lp = np.vstack([UV[bnd + [bnd[0]]]])
    ax.plot(lp[:, 0], lp[:, 1], color=BLUE, lw=2.6)
    ac = np.linspace(0, 2 * np.pi, 300)
    ax.plot(np.cos(ac), np.sin(ac), '--', color=BLUE, lw=0.8, alpha=0.5)
    flips, _ = flip_count(UV, F, active)
    ax.set_title(f'(c) 摊平结果（翻面 {flips}）', fontsize=11, pad=2)

    fig.suptitle('图 1  Tutte 嵌入的设定：区域 → 边界 → 摊平（k=8，684 面中的 540 面，MVC 权重）',
                 fontsize=11.5, y=0.985)
    p = os.path.join(OUT, 'theory1-setup.png')
    fig.savefig(p, dpi=125, facecolor='white')
    plt.close(fig)
    print('图 1 →', p, f'（区域 {len(active)} 面，翻面 {flips}）')


# ================================================================== 图 2
def fig_convex_combo():
    """凸组合与星形邻域：正权重 vs 负权重"""
    rng = np.random.default_rng(7)
    # 邻居分布在一个半圆上（对应靠近边界的内部顶点），半径 0.8~1.0
    th = np.linspace(-np.pi / 2, np.pi / 2, 7) + rng.uniform(-0.05, 0.05, 7)
    rad = rng.uniform(0.80, 1.0, 7)
    nb = np.c_[rad * np.cos(th), rad * np.sin(th)]
    nb = nb[np.argsort(np.arctan2(nb[:, 1], nb[:, 0]))]
    k = len(nb)

    from matplotlib.gridspec import GridSpec
    # 用 constrained layout 让 matplotlib 自己算间距：总标题在顶、图例在底，
    # 不再手工写 top/bottom，避免文字互相压到
    fig = plt.figure(figsize=(10.2, 6.75), layout='constrained')
    gs = GridSpec(2, 2, figure=fig, height_ratios=[4.4, 1.0])
    fig.get_layout_engine().set(wspace=0.16, hspace=0.10, w_pad=0.02, h_pad=0.06)

    from scipy.spatial import ConvexHull, Delaunay
    hull_idx = ConvexHull(nb).vertices
    hull = nb[hull_idx]
    inside = Delaunay(hull)

    # 正权重：Σw = 1
    w = rng.uniform(0.25, 1.0, k)
    w = w / w.sum()
    ctr = w @ nb
    # 负权重：把 w_1 改成 -0.60，其余按原比例放大，仍保持 Σw = 1
    NEG = -0.60
    w2 = w.copy()
    rest = 1.0 - w[1]
    w2[1] = NEG
    others = [i for i in range(k) if i != 1]
    w2[others] = w[others] * (1.0 - NEG) / rest
    ctr2 = w2 @ nb
    print('  图 2：Σw = %.3f / %.3f；正权重重心在凸包内 = %s，负权重重心在凸包外 = %s'
          % (w.sum(), w2.sum(), bool(inside.find_simplex(ctr) >= 0),
             bool(inside.find_simplex(ctr2) < 0)))

    for col, (ctr_i, w_i, title, sub) in enumerate((
        (ctr, w, '(a) $w_{ij}>0$、$\\sum_j w_{ij}=1$', '重心落在邻居凸包内，绕向一致'),
        (ctr2, w2, '(b) $w_1=-0.60$（仍有 $\\sum_j w_{ij}=1$）', '重心被推出凸包，绕向翻转'),
    )):
        from matplotlib.patches import Polygon as MplPoly
        ax = fig.add_subplot(gs[0, col])
        ax.add_patch(MplPoly(hull, closed=True, facecolor='#eef3fa', edgecolor=LINE, lw=1.0, zorder=0))
        nflip = 0
        for j in range(k):
            a, b = nb[j], nb[(j + 1) % k]
            tri = np.vstack([ctr_i, a, b])
            s = (a[0] - ctr_i[0]) * (b[1] - ctr_i[1]) - (b[0] - ctr_i[0]) * (a[1] - ctr_i[1])
            bad = s <= 0
            nflip += bad
            ax.add_patch(MplPoly(tri, closed=True,
                                 facecolor=(RED if bad else '#dce9f8'),
                                 edgecolor=(RED if bad else BLUE), lw=1.0, alpha=0.9, zorder=1))
        cols = [RED if x < 0 else GREEN for x in w_i]
        ax.scatter(nb[:, 0], nb[:, 1], s=560, c=cols, zorder=3,
                   edgecolors='white', linewidths=1.4)
        for j in range(k):
            ax.text(nb[j, 0], nb[j, 1], str(j), ha='center', va='center',
                    fontsize=9, color='white', zorder=5)
        ax.scatter([ctr_i[0]], [ctr_i[1]], s=170, c=BLUE, marker='*', zorder=4,
                   edgecolors='white', linewidths=0.8)
        ax.annotate('重心', (ctr_i[0], ctr_i[1]), xytext=(0, -30),
                    textcoords='offset points', fontsize=9.5, color=BLUE, ha='center',
                    arrowprops=dict(arrowstyle='->', color=BLUE, lw=1.0,
                                    shrinkA=2, shrinkB=6))
        ax.set_xlim(-1.60, 1.60); ax.set_ylim(-1.50, 1.55)
        ax.set_aspect('equal'); ax.axis('off')
        ax.set_title(title + '\n' + sub + f'（翻面 {nflip}）', fontsize=10.5, pad=6)

        # 权重条形图
        axb = fig.add_subplot(gs[1, col])
        axb.bar(np.arange(k), w_i, width=0.62,
                color=[RED if x < 0 else GREEN for x in w_i], zorder=2)
        axb.axhline(0, color=GREY, lw=0.9, zorder=3)
        for j, v in enumerate(w_i):
            axb.text(j, v + (0.03 if v >= 0 else -0.13), f'{v:+.2f}',
                     ha='center', fontsize=8.5, color=(RED if v < 0 else GREY))
        axb.set_xticks(np.arange(k))
        axb.set_xticklabels([f'$w_{j}$' for j in range(k)], fontsize=9)
        axb.set_ylim(-0.95, 0.62)
        axb.set_ylabel('权重', fontsize=9)
        for s_ in ('top', 'right'):
            axb.spines[s_].set_visible(False)
        for s_ in ('left', 'bottom'):
            axb.spines[s_].set_color(LINE)
        axb.tick_params(labelsize=8.5, color=LINE)

    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D

    handles = [
        Patch(facecolor='#eef3fa', edgecolor=LINE, lw=1.0, label='邻居凸包'),
        Patch(facecolor='#dce9f8', edgecolor=BLUE, lw=1.0, label='扇形：绕向一致'),
        Patch(facecolor=RED, edgecolor=RED, lw=1.0, label='扇形：绕向翻转（翻面）'),
        Line2D([], [], marker='o', ls='', ms=8, mfc=GREEN, mec='white',
               mew=1.2, label='邻居顶点 $w_j>0$'),
        Line2D([], [], marker='o', ls='', ms=8, mfc=RED, mec='white',
               mew=1.2, label='邻居顶点 $w_j<0$'),
        Line2D([], [], marker='*', ls='', ms=13, mfc=BLUE, mec='white',
               mew=0.8, label='凸组合重心 $\\mathbf{u}_v$'),
    ]
    # loc='outside lower center'：图例排在图的最下方，constrained layout 会为它预留高度
    fig.legend(handles=handles, loc='outside lower center', ncol=3, frameon=False,
               fontsize=9.5, columnspacing=1.6, handletextpad=0.5, labelspacing=0.5)
    fig.suptitle('图 2  凸组合条件：内部顶点取邻居的加权平均，$w_{ij}>0$ 时重心不跑出邻居凸包，'
                 '绕向保持不变', fontsize=11.5)

    p = os.path.join(OUT, 'theory2-convex-combo.png')
    fig.savefig(p, dpi=125, facecolor='white')
    plt.close(fig)
    print('图 2 →', p)


# ================================================================== 图 3
def fig_boundary():
    P, F, ring, vid = build_mesh()
    k = 8
    bnd = [vid(k, j) for j in range(NS)]
    interior = [0] + [vid(i, j) for i in range(1, k) for j in range(NS)]
    active = np.array([f for f, t in enumerate(F) if all(ring[v] <= k for v in t)])

    names = ['circle', 'square', 'star', 'ell']
    labels = ['圆（凸）', '正方形（凸）', '五角星（非凸）', 'L 形（非凸）']
    fig, axes = plt.subplots(2, 4, figsize=(13.6, 6.6))
    fig.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.03, wspace=0.08, hspace=0.14)

    for col, (name, lab) in enumerate(zip(names, labels)):
        ax = axes[0, col]
        cur = shape_curve(name)
        conv = CONVEX[name]
        ax.fill(cur[:, 0], cur[:, 1], color=('#e8f2ea' if conv else '#fbeae8'), zorder=0)
        ax.plot(cur[:, 0], cur[:, 1], color=(GREEN if conv else RED), lw=1.8, zorder=1)
        pts = np.array([shape_point(name, t) for t in np.linspace(0, 1, NS, endpoint=False)])
        ax.scatter(pts[:, 0], pts[:, 1], s=9, color=GREY, zorder=2)
        if not conv:
            pts2 = SHAPES[name]
            for q in pts2:
                # 凹角：内角 > 180°
                ax.scatter([q[0]], [q[1]], s=42, marker='o', facecolors='none',
                           edgecolors=RED, linewidths=1.3, zorder=3)
        ax.set_xlim(-1.25, 1.25); ax.set_ylim(-1.25, 1.25)
        ax.set_aspect('equal'); ax.axis('off')
        ax.set_title(lab, fontsize=11, color=(GREEN if conv else RED), pad=4)

        UV = solve_tutte(P, F, interior, bnd, name)
        flips, s = flip_count(UV, F, active)
        ax = axes[1, col]
        tri_mesh_2d(ax, UV, F[active], facecolor='#ffffff', edgecolor=LINE, lw=0.35,
                    flips=np.where(s <= 0)[0])
        lp = np.vstack([UV[bnd + [bnd[0]]]])
        ax.plot(lp[:, 0], lp[:, 1], color=BLUE, lw=2.0)
        ax.set_title(f'翻面 {flips} / {len(active)}', fontsize=10.5,
                     color=(GREEN if flips == 0 else RED), pad=4)

    fig.suptitle('图 3  目标边界的形状：凸边界 0 翻面，凹角处出现翻面（同一闭环，k=8，540 面）',
                 fontsize=11.5, y=0.965)
    p = os.path.join(OUT, 'theory3-boundary.png')
    fig.savefig(p, dpi=125, facecolor='white')
    plt.close(fig)
    print('图 3 →', p)


# ================================================================== 图 4
def fig_topology():
    """拓扑圆盘 vs 有洞的环带"""
    def disk_mesh(hole=0):
        """同心环网格。hole=0 时含中心顶点与中心扇面（拓扑圆盘）；
        hole>0 时挖掉最里面 hole 圈（拓扑环带）。"""
        rings = 7
        P = [[0.0, 0.0]] if hole == 0 else []
        for i in range(hole, rings + 1):
            r = (i + 1) / (rings + 1)
            for j in range(NS):
                th = 2 * np.pi * j / NS
                P.append([r * np.cos(th), r * np.sin(th)])
        P = np.array(P)
        base = 1 if hole == 0 else 0
        vidx = lambda i, j: base + (i - hole) * NS + (j % NS)
        F = []
        if hole == 0:
            for j in range(NS):
                F.append([0, vidx(0, j), vidx(0, (j + 1) % NS)])
        for i in range(hole, rings):
            for j in range(NS):
                j2 = (j + 1) % NS
                a, b = vidx(i, j), vidx(i, j2)
                c, d = vidx(i + 1, j2), vidx(i + 1, j)
                F.append([a, d, c]); F.append([a, c, b])
        return P, np.array(F), rings, vidx

    from collections import defaultdict
    def chi_and_loops(P, F):
        vset, eset = set(), set()
        for (a, b, c) in F:
            vset.update((a, b, c))
            eset.add((min(a, b), max(a, b)))
            eset.add((min(b, c), max(b, c)))
            eset.add((min(c, a), max(c, a)))
        chi = len(vset) - len(eset) + len(F)
        # 边界半边
        e2f = defaultdict(list)
        for fi, (a, b, c) in enumerate(F):
            for (x, y) in ((a, b), (b, c), (c, a)):
                e2f[(x, y)].append(fi)
        bnd = []
        for (x, y), fs in e2f.items():
            if len(e2f.get((y, x), [])) == 0:
                bnd.append((x, y))
        out = defaultdict(list)
        for x, y in bnd:
            out[x].append(y)
        seen, cycles = set(), []
        for st in list(out.keys()):
            if st in seen:
                continue
            cyc, cur = [st], st
            while True:
                seen.add(cur)
                nxt = out[cur]
                if len(nxt) != 1:
                    break
                cur = nxt[0]
                if cur == st:
                    break
                if cur in seen:
                    break
                cyc.append(cur)
            cycles.append(cyc)
        return chi, len(vset), len(eset), len(F), cycles

    fig, axes = plt.subplots(1, 2, figsize=(10.4, 5.0))
    fig.subplots_adjust(left=0.02, right=0.98, top=0.88, bottom=0.03, wspace=0.10)

    for ax, hole, title, ok in (
        (axes[0], 0, '(a) 拓扑圆盘：一条边界环', True),
        (axes[1], 3, '(b) 中间挖洞：两条边界环', False),
    ):
        P, F, nr, vidx = disk_mesh(hole)
        chi, V, E, Ft, cycles = chi_and_loops(P, F)
        tri_mesh_2d(ax, P, F, facecolor='#ffffff', edgecolor=LINE, lw=0.35)
        colors = [BLUE] + [ORANGE] * 9
        for ci, cyc in enumerate(cycles):
            lp = np.vstack([P[cyc + [cyc[0]]]])
            ax.plot(lp[:, 0], lp[:, 1], color=colors[ci % len(colors)], lw=2.4, zorder=3)
        txt = f'$V={V},\\;E={E},\;F={Ft}$\n$\\chi = V-E+F = {chi}$'
        ax.text(0.0, -1.32, txt, ha='center', fontsize=11.5, color=(GREEN if ok else RED))
        ax.text(0.0, 1.30, title, ha='center', fontsize=11.5,
                color=(GREEN if ok else RED))
        ax.set_xlim(-1.25, 1.25); ax.set_ylim(-1.45, 1.45)
        ax.set_aspect('equal'); ax.axis('off')

    fig.suptitle('图 4  前提一：区域必须是拓扑圆盘（$\\chi = 1$、单条边界环）',
                 fontsize=11.5, y=0.965)
    p = os.path.join(OUT, 'theory4-topology.png')
    fig.savefig(p, dpi=125, facecolor='white')
    plt.close(fig)
    print('图 4 →', p)


if __name__ == '__main__':
    fig_setup()
    fig_convex_combo()
    fig_boundary()
    fig_topology()
    print('\n图已输出到', OUT)
