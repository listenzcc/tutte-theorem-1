# -*- coding: utf-8 -*-
"""
Stanford Bunny 上的 Tutte 嵌入：离线渲染出图。

管线与 bunny-tutte.html 完全一致（同一份 OBJ、同一套 BFS 取环、同一套权重与线性系统），
区别只在于：这里用 scipy 直接解线性系统（页面里是 Gauss-Seidel 迭代），
以及用 matplotlib 出静态图（页面是 canvas 逐三角形仿射贴图）。

运行：
  C:/Users/liste/miniconda3/envs/python3.11/python.exe render-bunny-figs.py

输出：figs/*.png + 一组量化指标（打印到 stdout，供 blog 引用）
"""
import os
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
_PREF = ('msyh.ttc', 'msyhbd.ttc', 'msyhl.ttc', 'simhei.ttf', 'simsun.ttc', 'deng.ttf')
_fonts = {os.path.basename(f).lower(): f for f in fm.findSystemFonts()}
_pick = next((_fonts[n] for n in _PREF if n in _fonts), None)
if _pick:
    fm.fontManager.addfont(_pick)
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = [fm.FontProperties(fname=_pick).get_name()]
plt.rcParams['axes.unicode_minus'] = False
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path as MplPath
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection

HERE = os.path.dirname(os.path.abspath(__file__))
OBJ = os.path.join(HERE, 'model', 'bunny_small.obj')
OUT = os.path.join(HERE, 'figs')
os.makedirs(OUT, exist_ok=True)

GREY = np.array([0.855, 0.878, 0.906])
RED = np.array([0.85, 0.35, 0.30])

# UV 贴图：4×4 格，沿 u 走色相、沿 v 走明度，叠加棋盘明暗与中心块
NCEL = 4
TEXPX = 512


# ---------------------------------------------------------------- UV 贴图
def hsl_to_rgb(h, s, l):
    """h∈[0,360), s,l∈[0,1] → (r,g,b)∈[0,1]"""
    h = (h % 360.0) / 60.0
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs(h % 2 - 1))
    m = l - c / 2
    tbl = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)]
    r, g, b = tbl[min(int(h), 5)]
    return r + m, g + m, b + m


def uv_checker(n=NCEL, res=TEXPX, tile=None, phase=0, base_hue=10.0, hue_span=200.0,
               sat=0.42, l_hi=0.82, l_lo=0.52):
    """生成 UV checker 贴图，返回 (res,res,3) 的 float 数组，行 0 对应 v=+1。

    n     —— 总格数（贴图覆盖的范围被切成 n×n 格）
    tile  —— 基本图案的格数；n > tile 时把图案平铺 n/tile 次
    phase —— 平铺相位。定理页的纹理范围是 [-4,4]、取 n=16/tile=4，用 phase=2 让
             单位圆 [-1,1]（格 6..9）正好落在一个完整图案上
    """
    tile = n if tile is None else tile
    img = np.zeros((res, res, 3))
    cell = res / n
    for j in range(n):                      # 行 → v 从上到下
        y0, y1 = int(round(j * cell)), int(round((j + 1) * cell))
        jj = (j + phase) % tile
        l_base = l_hi - (l_hi - l_lo) * jj / (tile - 1)
        for i in range(n):                  # 列 → u 从左到右
            x0, x1 = int(round(i * cell)), int(round((i + 1) * cell))
            ii = (i + phase) % tile
            dark = ((ii + jj) % 2) == 1
            hue = base_hue + hue_span * ii / (tile - 1)
            l = l_base - (0.07 if dark else 0.0)
            img[y0:y1, x0:x1] = hsl_to_rgb(hue, sat, l)
            s2 = int(round((x1 - x0) * 0.46))
            o = ((x1 - x0) - s2) // 2
            img[y0 + o:y0 + o + s2, x0 + o:x0 + o + s2] = \
                hsl_to_rgb(hue, sat + 0.06, l + (0.11 if dark else -0.13))
    # 网格线：每格细白线，主格线更粗更亮
    for j in range(n + 1):
        y = min(res - 1, int(round(j * cell)))
        main = ((j + phase) % tile) % 2 == 0
        w = 3 if main else 2
        y0, y1 = max(0, y - w // 2), min(res, y - w // 2 + w)
        img[y0:y1, :] = 0.25 * img[y0:y1, :] + 0.75 if main else 0.62 * img[y0:y1, :] + 0.38
    for i in range(n + 1):
        x = min(res - 1, int(round(i * cell)))
        main = ((i + phase) % tile) % 2 == 0
        w = 3 if main else 2
        x0, x1 = max(0, x - w // 2), min(res, x - w // 2 + w)
        img[:, x0:x1] = 0.25 * img[:, x0:x1] + 0.75 if main else 0.62 * img[:, x0:x1] + 0.38
    return np.clip(img, 0, 1)


MP = uv_checker()


def uv_to_st(UV):
    """3D/参数化坐标 (−1..1) → 贴图坐标 (0..1)，s 为列(u)，t 为行(1−v)/2"""
    return np.stack([(UV[:, 0] + 1) / 2, (1 - UV[:, 1]) / 2], 1)


def sample_map(mp, st):
    """最近邻采样，st 为 (N,2) 的 (s,t)"""
    h = mp.shape[0]
    r = np.clip((st[:, 1] * h).astype(int), 0, h - 1)
    c = np.clip((st[:, 0] * h).astype(int), 0, h - 1)
    return mp[r, c]


def tex_triangles(Q, T, inside, ST, mp=MP, maxk=3):
    """inside 里的三角形按 UV 跨度自适应细分，每个子三角形取三顶点贴图色的均值。

    返回 (顶点 (M,3,3), 颜色 (M,3), 所属大面号 (M,))。
    """
    verts, cols, parent = [], [], []
    cellw = 2.0 / NCEL
    for fi in inside:
        a, b, c = T[fi]
        A, B, C = Q[a], Q[b], Q[c]
        ua, ub, uc = ST[a], ST[b], ST[c]
        span = max(abs(ua[0] - ub[0]), abs(ub[0] - uc[0]), abs(uc[0] - ua[0]),
                   abs(ua[1] - ub[1]), abs(ub[1] - uc[1]), abs(uc[1] - ua[1]))
        k = int(min(maxk, max(1, np.ceil(span / cellw / 0.25))))
        if k == 1:
            sub = [((A, ua), (B, ub), (C, uc))]
        else:
            P = {}
            for ii in range(k + 1):
                for jj in range(k + 1 - ii):
                    wi, wj = ii / k, jj / k
                    P[(ii, jj)] = (A * (1 - wi - wj) + B * wi + C * wj,
                                   ua * (1 - wi - wj) + ub * wi + uc * wj)
            sub = []
            for ii in range(k):
                for jj in range(k - ii):
                    sub.append((P[(ii, jj)], P[(ii + 1, jj)], P[(ii, jj + 1)]))
                    if ii + jj <= k - 2:
                        sub.append((P[(ii + 1, jj)], P[(ii + 1, jj + 1)], P[(ii, jj + 1)]))
        if not len(sub):
            continue
        cent = np.asarray([(t[0][1] + t[1][1] + t[2][1]) / 3.0 for t in sub])   # 子三角形重心
        sm = sample_map(mp, cent)
        for m_, trio in enumerate(sub):
            verts.append([trio[0][0], trio[1][0], trio[2][0]])
            cols.append(sm[m_])
            parent.append(fi)
    return np.asarray(verts), np.asarray(cols), np.asarray(parent)


# ---------------------------------------------------------------- OBJ
def load_obj(path):
    vs, fs = [], []
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if line.startswith('v '):
                a = line.split()
                vs.append([float(a[1]), float(a[2]), float(a[3])])
            elif line.startswith('f '):
                a = line.split()[1:]
                idx = [int(s.split('/')[0]) - 1 for s in a]
                for i in range(1, len(idx) - 1):
                    fs.append([idx[0], idx[i], idx[i + 1]])
    V = np.asarray(vs, dtype=np.float64)
    T = np.asarray(fs, dtype=np.int64)
    c = (V.min(0) + V.max(0)) / 2
    V = V - c
    V /= np.abs(V).max()
    return V, T


# ---------------------------------------------------------------- 拓扑
def build_adj(V, T):
    NV = len(V)
    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    src = np.concatenate([a, b, c, b, c, a])
    dst = np.concatenate([b, c, a, a, b, c])
    key = src * NV + dst
    order = np.lexsort((dst, src))
    src, dst = src[order], dst[order]
    keep = np.ones(len(src), bool)
    keep[1:] = (src[1:] != src[:-1]) | (dst[1:] != dst[:-1])
    src, dst = src[keep], dst[keep]
    counts = np.bincount(src, minlength=NV)
    off = np.concatenate([[0], np.cumsum(counts)]).astype(np.int64)
    return off, dst.astype(np.int64)


def build_edge_maps(V, T):
    """返回 (edge_key_of_face_edge, edge->faces dict)"""
    NV = len(V)
    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    lo = np.minimum(a, b); hi = np.maximum(a, b); kab = lo * NV + hi
    lo = np.minimum(b, c); hi = np.maximum(b, c); kbc = lo * NV + hi
    lo = np.minimum(c, a); hi = np.maximum(c, a); kca = lo * NV + hi
    keys = np.concatenate([kab, kbc, kca])
    # keys 按「边类型分块」排列（先所有 ab、再 bc、再 ca），faceid 必须同样分块，不能按面重复
    faceid = np.concatenate([np.arange(len(T))] * 3)
    order = np.argsort(keys, kind='stable')
    ks, fs_ = keys[order], faceid[order]
    uniq, starts = np.unique(ks, return_index=True)
    ends = np.append(starts[1:], len(ks))
    e2f = {int(u): fs_[s:e] for u, s, e in zip(uniq, starts, ends)}
    return kab, kbc, kca, e2f


def ek(i, j, NV):
    return (i * NV + j) if i < j else (j * NV + i)


# ---------------------------------------------------------------- 区域
def bfs_dist(seed, hops, off, adj):
    NV = len(off) - 1
    dist = np.full(NV, -1, dtype=np.int64)
    dist[seed] = 0
    frontier = [seed]
    for d in range(hops):
        nxt = []
        for v in frontier:
            for k in range(off[v], off[v + 1]):
                w = adj[k]
                if dist[w] < 0:
                    dist[w] = d + 1
                    nxt.append(w)
        frontier = nxt
        if not frontier:
            break
    return dist


def build_disk(dist, T, e2f, NV):
    inside = np.where((dist[T[:, 0]] >= 0) & (dist[T[:, 1]] >= 0) & (dist[T[:, 2]] >= 0))[0]
    in_set = set(inside.tolist())
    out = {}
    for fi in inside:
        t = T[fi]
        for i in range(3):
            a, b = int(t[i]), int(t[(i + 1) % 3])
            faces = e2f.get(ek(a, b, NV), np.array([], dtype=np.int64))
            if not any((g != fi) and (int(g) in in_set) for g in faces):
                out.setdefault(a, []).append(b)
    visited, cycles = set(), []
    for start in list(out.keys()):
        if start in visited:
            continue
        cyc, cur, clean, guard = [start], start, True, 0
        while guard < 200000:
            guard += 1
            ends = out.get(cur, [])
            if len(ends) != 1:
                clean = False
                break
            nx = ends[0]
            visited.add(cur)
            if nx == start:
                break
            if nx in visited:
                clean = False
                break
            cyc.append(nx)
            cur = nx
        cycles.append({'pts': cyc, 'clean': clean})
    vset, eset = set(), set()
    for fi in inside:
        a, b, c = (int(x) for x in T[fi])
        vset.update((a, b, c))
        eset.update((ek(a, b, NV), ek(b, c, NV), ek(c, a, NV)))
    chi = len(vset) - len(eset) + len(inside)
    ok = (len(cycles) == 1 and cycles[0]['clean'] and chi == 1 and len(inside) > 0)
    return dict(inside=inside, cycles=cycles, chi=chi, v=len(vset), e=len(eset), f=len(inside),
                loop=(cycles[0]['pts'] if ok else None), ok=ok)


def find_disk(seed, hops, allow_fallback, off, adj, T, e2f, NV):
    tried = build_disk(bfs_dist(seed, hops, off, adj), T, e2f, NV)
    if tried['ok']:
        return dict(disk=tried, hops=hops, fallback=0, tried=tried)
    if not allow_fallback:
        return dict(disk=None, hops=hops, fallback=0, tried=tried)
    for d in range(1, 11):
        for cand in (hops - d, hops + d):
            if cand < 3 or cand > 60:
                continue
            r = build_disk(bfs_dist(seed, cand, off, adj), T, e2f, NV)
            if r['ok']:
                return dict(disk=r, hops=cand, fallback=d, tried=tried)
    return dict(disk=None, hops=hops, fallback=-1, tried=tried)


# ---------------------------------------------------------------- 边界形状
def shape_point(name, t):
    if name == 'circle':
        a = 2 * np.pi * t
        return np.array([np.cos(a), np.sin(a)])
    if name == 'square':
        pts = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
    elif name == 'star':
        pts = []
        for i in range(10):
            R = 0.42 if i % 2 else 1.0
            a = -np.pi / 2 + i * np.pi / 5
            pts.append((R * np.cos(a), R * np.sin(a)))
    else:  # ell
        pts = [(1, 1), (-0.15, 1), (-0.15, -0.2), (-1, -0.2), (-1, -1), (1, -1)]
    pts = [np.array(p) for p in pts]
    n = len(pts)
    seg = [np.linalg.norm(pts[(i + 1) % n] - pts[i]) for i in range(n)]
    total = sum(seg)
    d = t * total
    for i in range(n):
        if d <= seg[i] or i == n - 1:
            s = min(d / seg[i], 1.0) if seg[i] > 0 else 0.0
            return pts[i] + (pts[(i + 1) % n] - pts[i]) * s
        d -= seg[i]
    return pts[0]


# ---------------------------------------------------------------- 权重
def face_angles(V, T):
    A, B, C = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]

    def ang(P, Q, R):
        u, w = Q - P, R - P
        cs = (u * w).sum(1) / (np.linalg.norm(u, axis=1) * np.linalg.norm(w, axis=1) + 1e-18)
        return np.arccos(np.clip(cs, -1, 1))
    return ang(A, B, C), ang(B, C, A), ang(C, A, B)


def build_weights(kind, V, T, NV):
    """返回 (tan_lo, tan_hi, cot, edge_len, key->compact index map, uniq_keys)"""
    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    A0, A1, A2 = face_angles(V, T)
    first = np.concatenate([a, b, c])
    second = np.concatenate([b, c, a])
    lo = np.minimum(first, second)
    hi = np.maximum(first, second)
    keys = lo * NV + hi
    tan_first = np.concatenate([np.tan(A0 / 2), np.tan(A1 / 2), np.tan(A2 / 2)])
    tan_second = np.concatenate([np.tan(A1 / 2), np.tan(A2 / 2), np.tan(A0 / 2)])
    cot_opp = np.concatenate([1.0 / np.tan(A2), 1.0 / np.tan(A0), 1.0 / np.tan(A1)])
    uniq, inv = np.unique(keys, return_inverse=True)
    nE = len(uniq)
    tan_lo = np.zeros(nE); tan_hi = np.zeros(nE); cot = np.zeros(nE)
    is_lo_first = first < second
    np.add.at(tan_lo, inv[is_lo_first], tan_first[is_lo_first])
    np.add.at(tan_hi, inv[is_lo_first], tan_second[is_lo_first])
    np.add.at(tan_hi, inv[~is_lo_first], tan_first[~is_lo_first])
    np.add.at(tan_lo, inv[~is_lo_first], tan_second[~is_lo_first])
    np.add.at(cot, inv, cot_opp)
    elen = np.linalg.norm(V[uniq // NV] - V[uniq % NV], axis=1)
    return tan_lo, tan_hi, cot, elen, uniq, inv


def solve_tutte(V, T, off, adj, disk, kind, shape, NV):
    """解 Tutte 嵌入。返回 (UV, info)"""
    inside = disk['inside']
    loop = disk['loop']
    vset = set()
    for fi in inside:
        vset.update(int(x) for x in T[fi])
    bset = set(loop)
    interior = np.array(sorted(vset - bset), dtype=np.int64)
    boundary = np.array(loop, dtype=np.int64)

    UV = np.zeros((NV, 2))
    # 边界：按 3D 弧长分配目标周长
    n = len(boundary)
    cum = np.zeros(n + 1)
    for j in range(n):
        p, q = V[boundary[j]], V[boundary[(j + 1) % n]]
        cum[j + 1] = cum[j] + np.linalg.norm(q - p)
    total = cum[-1]
    for j in range(n):
        t = cum[j] / total if total > 0 else j / n
        UV[boundary[j]] = shape_point(shape, t)

    tan_lo, tan_hi, cot, elen, uniq, inv = build_weights(kind, V, T, NV)
    pos = {int(k): i for i, k in enumerate(uniq)}

    rows, cols, vals, neg = [], [], [], 0
    for i in interior:
        js = adj[off[i]:off[i + 1]]
        ws = []
        for j in js:
            if int(j) not in vset:
                continue
            ei = pos[ek(int(i), int(j), NV)]
            if kind == 'uniform':
                w = 1.0
            elif kind == 'cotan':
                w = cot[ei]
            else:  # mvc
                w = (tan_lo[ei] if i < j else tan_hi[ei]) / max(elen[ei], 1e-12)
            if not (w > 0):
                neg += 1
            ws.append((int(j), w))
        s = sum(w for _, w in ws)
        if s <= 1e-12:                      # 权重和非正：退化为均匀权重，并记为违反前提
            ws = [(j, 1.0) for j, _ in ws]
            s = float(len(ws))
            neg += len(ws)
        for j, w in ws:
            rows.append(int(i)); cols.append(j); vals.append(w / s)

    W = sp.csr_matrix((vals, (rows, cols)), shape=(NV, NV))
    A = (sp.identity(NV, format='csr') - W)
    b = W @ UV
    for d in range(2):
        UV[interior, d] = spla.spsolve(A[interior][:, interior].tocsc(), b[interior, d])
    return UV, dict(neg=neg, interior=interior, boundary=boundary, inside=inside)


# ---------------------------------------------------------------- 指标
def metrics(V, T, UV, inside):
    a, b, c = T[inside, 0], T[inside, 1], T[inside, 2]
    uv_signed = ((UV[b, 0] - UV[a, 0]) * (UV[c, 1] - UV[a, 1])
                 - (UV[c, 0] - UV[a, 0]) * (UV[b, 1] - UV[a, 1]))
    flips = int((uv_signed <= 0).sum())
    u3 = V[T[inside, 1]] - V[T[inside, 0]]
    w3 = V[T[inside, 2]] - V[T[inside, 0]]
    a3 = 0.5 * np.linalg.norm(np.cross(u3, w3), axis=1)
    auv = np.abs(uv_signed) * 0.5
    area_ratio = auv.sum() / a3.sum()
    # 尺度无关的面积畸变：把 UV 整体缩放到 ΣUV = Σ3D，再看每个三角形面积比的离散程度
    lg = np.log2((auv / np.maximum(a3, 1e-18)) / area_ratio)
    area_spread = dict(p25=float(np.percentile(lg, 25)), p50=float(np.median(lg)),
                       p75=float(np.percentile(lg, 75)), std=float(lg.std()))

    def tri_angles(P):
        A, B, C = P[T[inside, 0]], P[T[inside, 1]], P[T[inside, 2]]
        out = []
        for (p, q, r) in ((A, B, C), (B, C, A), (C, A, B)):
            u, w = q - p, r - p
            cs = (u * w).sum(1) / (np.linalg.norm(u, axis=1) * np.linalg.norm(w, axis=1) + 1e-18)
            out.append(np.degrees(np.arccos(np.clip(cs, -1, 1))))
        return np.stack(out, 1)
    ang3 = tri_angles(V)
    ang2 = tri_angles(UV)
    ang_err = np.abs(ang3 - ang2)
    return dict(flips=flips, n=int(len(inside)), area_ratio=float(area_ratio), **area_spread,
                ang_mean=float(ang_err.mean()), ang_p90=float(np.percentile(ang_err, 90)),
                ang_max=float(ang_err.max()))


# ---------------------------------------------------------------- 绘图
def vertex_normals(V, T):
    n = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    VN = np.zeros_like(V)
    for k in range(3):
        np.add.at(VN, T[:, k], n)
    ln = np.linalg.norm(VN, axis=1)
    ln[ln < 1e-18] = 1.0
    return VN / ln[:, None]


def heat(r):
    t = np.clip((np.log(np.maximum(r, 1e-6), where=r > 0, out=np.full_like(r, -20.0)) / np.log(2) + 1.6) / 3.2, 0, 1)
    stops = np.array([[91, 143, 214], [231, 238, 246], [224, 138, 95]]) / 255.0
    s = t * 2
    i = np.where(s < 1, 0, 1)
    f = np.where(s < 1, s, s - 1)
    return stops[i] + (stops[i + 1] - stops[i]) * f[:, None]


def shade(Q, T, lum_base=0.42, ldir=(0.35, 0.55, 0.76)):
    n = np.cross(Q[T[:, 1]] - Q[T[:, 0]], Q[T[:, 2]] - Q[T[:, 0]])
    n /= (np.linalg.norm(n, axis=1) + 1e-18)[:, None]
    L = np.array(ldir); L = L / np.linalg.norm(L)
    nd = np.clip(n @ L, 0, 1)
    return lum_base + (1 - lum_base) * nd


def area_colors(V, T, UV, inside):
    a, b, c = T[inside, 0], T[inside, 1], T[inside, 2]
    auv = np.abs((UV[b, 0] - UV[a, 0]) * (UV[c, 1] - UV[a, 1])
                 - (UV[c, 0] - UV[a, 0]) * (UV[b, 1] - UV[a, 1])) * 0.5
    a3 = 0.5 * np.linalg.norm(np.cross(V[T[inside, 1]] - V[T[inside, 0]],
                                       V[T[inside, 2]] - V[T[inside, 0]]), axis=1)
    r = auv / np.maximum(a3, 1e-18)
    r = r / (auv.sum() / a3.sum())
    return heat(r)


def draw_3d(ax, V, T, inside, UV, mode, elev, azim, loops=None, loop_color='#2f6fd0',
            vnorm=None, offset=0.022, focus=None):
    # mplot3d 以 z 为「上」，而兔子模型以 y 为「上」→ 置换 (x,y,z) -> (x,z,y)
    Q = V[:, [0, 2, 1]]
    QN = None if vnorm is None else vnorm[:, [0, 2, 1]]
    NT = len(T)
    lum = shade(Q, T, lum_base=(0.66 if mode == "tex" else 0.42))[:, None]
    mask_in = np.zeros(NT, bool); mask_in[inside] = True
    uv_signed = ((UV[T[:, 1], 0] - UV[T[:, 0], 0]) * (UV[T[:, 2], 1] - UV[T[:, 0], 1])
                 - (UV[T[:, 2], 0] - UV[T[:, 0], 0]) * (UV[T[:, 1], 1] - UV[T[:, 0], 1]))
    flipflag = (mask_in & (uv_signed <= 0)) if mode != 'plain' else np.zeros(NT, bool)
    rectri = lambda idx: (np.tile(GREY, (len(idx), 1)) * lum[idx] * 1.05)

    if mode == 'tex':
        # inside 里的三角形按 UV 跨度细分后逐块从 UV 贴图上取色，outside 保持灰色
        ou = np.where(~mask_in)[0]
        vs, cs, pa = tex_triangles(Q, T, inside, uv_to_st(UV))
        VERT = np.concatenate([Q[T[ou]], vs])
        COL = np.concatenate([rectri(ou), cs * lum[pa]])
        fl = np.zeros(len(VERT), bool)
        fl[len(ou):] = flipflag[pa]
        COL = np.where(fl[:, None], RED, COL)
        poly = Poly3DCollection(VERT, facecolors=COL, linewidths=0, shade=False)
        ax.add_collection3d(poly)
    else:
        if mode == 'dist':
            a, b, c = T[inside, 0], T[inside, 1], T[inside, 2]
            uvs = ((UV[b, 0] - UV[a, 0]) * (UV[c, 1] - UV[a, 1])
                   - (UV[c, 0] - UV[a, 0]) * (UV[b, 1] - UV[a, 1]))
            u3 = Q[T[inside, 1]] - Q[T[inside, 0]]
            w3 = Q[T[inside, 2]] - Q[T[inside, 0]]
            a3 = 0.5 * np.linalg.norm(np.cross(u3, w3), axis=1)
            col_full = np.tile(np.array([0.95, 0.95, 0.95]), (NT, 1))
            col_full[inside] = heat(np.abs(uvs) * 0.5 / np.maximum(a3, 1e-18))
            col = col_full
        elif mode == 'plain':
            col = np.tile(np.array([0.855, 0.902, 0.968]), (NT, 1))
        else:
            col = np.tile(np.array([1.0, 1.0, 1.0]), (NT, 1))
        col = col * lum
        col = np.where(mask_in[:, None], col, np.tile(GREY, (NT, 1)) * lum * 1.05)
        col = np.where(flipflag[:, None], RED, col)
        poly = Poly3DCollection(Q[T], facecolors=col, linewidths=0, shade=False)
        ax.add_collection3d(poly)
    if loops:
        for pts, cl in loops:
            idx = np.array(pts + [pts[0]])
            P = Q[idx].copy()
            if QN is not None:                      # 沿顶点法线外推，避免被网格面挡住
                P = P + QN[idx] * offset
            ax.add_collection3d(Line3DCollection(
                [P], colors=[cl], linewidths=[3.2 if cl == loop_color else 2.6], zorder=10))
    if focus is not None and len(focus):
        Fq = Q[np.asarray(focus)]
        lo, hi = Fq.min(0), Fq.max(0)
        mid, half = (lo + hi) / 2, (hi - lo) / 2 * 1.6 + 0.02
        ax.set_xlim(mid[0] - half[0], mid[0] + half[0])
        ax.set_ylim(mid[1] - half[1], mid[1] + half[1])
        ax.set_zlim(mid[2] - half[2], mid[2] + half[2])
        ax.set_box_aspect(tuple(half / half.max()))
    else:
        ax.set_xlim(-1.05, 1.05); ax.set_ylim(-1.05, 1.05); ax.set_zlim(-1.05, 1.05)
        ax.set_box_aspect((1, 1, 1))
    ax.set_proj_type('ortho')
    ax.set_axis_off()
    ax.view_init(elev=elev, azim=azim)
    ax.set_facecolor('white')


def draw_uv(ax, T, inside, UV, loop, title='', show_checker=True, n=8, tri_colors=None):
    ax.set_facecolor('white')
    if show_checker:
        # 框内是实际用到的 UV 区域，框外淡显同一张贴图作为上下文
        ax.imshow(MP, extent=(-1, 1, -1, 1), origin='upper',
                  interpolation='nearest', zorder=0, alpha=0.15)
        im = ax.imshow(MP, extent=(-1, 1, -1, 1), origin='upper',
                       interpolation='nearest', zorder=0)
        if loop is not None:
            path = MplPath(np.c_[UV[loop + [loop[0]], 0], UV[loop + [loop[0]], 1]])
            patch = PathPatch(path, transform=ax.transData)
            im.set_clip_path(patch)
    ax.add_patch(Rectangle((-1, -1), 2, 2, fill=False, ls='--', lw=1,
                           ec='#3c4654', alpha=0.6, zorder=3))
    if tri_colors is not None:
        ax.add_collection(PolyCollection(UV[T[inside]], facecolors=tri_colors,
                                         edgecolors=(0.55, 0.60, 0.66, 0.35),
                                         linewidths=0.15, zorder=2))
    segs = []
    for fi in inside:
        a, b, c = T[fi]
        segs += [[UV[a], UV[b]], [UV[b], UV[c]], [UV[c], UV[a]]]
    wcol = '#ffffff' if show_checker else '#8b95a3'
    ax.add_collection(LineCollection(segs, colors=wcol, linewidths=0.35,
                                     alpha=0.75 if show_checker else 0.5, zorder=4))
    a, b, c = T[inside, 0], T[inside, 1], T[inside, 2]
    uv_signed = ((UV[b, 0] - UV[a, 0]) * (UV[c, 1] - UV[a, 1])
                 - (UV[c, 0] - UV[a, 0]) * (UV[b, 1] - UV[a, 1]))
    bad = inside[uv_signed <= 0]
    if len(bad):
        ax.add_collection(PolyCollection(UV[T[bad]], facecolors='#cf4438',
                                         edgecolors='#cf4438', linewidths=0.4, alpha=0.7, zorder=5))
    if loop is not None:
        ax.plot(UV[loop + [loop[0]], 0], UV[loop + [loop[0]], 1], color='#2f6fd0', lw=2.5, zorder=6)
    ax.set_xlim(-1.15, 1.15); ax.set_ylim(-1.15, 1.15)
    ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color('#dfe3e8')
    if title:
        ax.set_title(title, fontsize=10, color='#1b2027', pad=6)


def two_panel(path, V, T, NV, r, UV, info, mode, elev, azim, left_title, right_title,
              loops=None, loop_color='#2f6fd0', vnorm=None, focus=None, uv_colors=None):
    fig = plt.figure(figsize=(11.2, 5.4), dpi=150)
    ax1 = fig.add_subplot(1, 2, 1, projection='3d')
    ax2 = fig.add_subplot(1, 2, 2)
    lp = r['disk']['loop'] if (r['disk'] and r['disk']['loop']) else None
    draw_3d(ax1, V, T, info['inside'], UV, mode, elev, azim,
            loops=([(lp, loop_color)] if lp else None), loop_color=loop_color, vnorm=vnorm, focus=focus)
    draw_uv(ax2, T, info['inside'], UV, (r['disk']['loop'] if r['disk'] and r['disk']['loop'] else None),
            right_title, show_checker=(mode == 'tex'), tri_colors=uv_colors)
    ax1.set_title(left_title, fontsize=10, color='#1b2027', pad=2)
    fig.tight_layout()
    fig.savefig(path, bbox_inches='tight', facecolor='white')
    plt.close(fig)


# ---------------------------------------------------------------- 主流程
def main():
    V, T = load_obj(OBJ)
    NV, NT = len(V), len(T)
    off, adj = build_adj(V, T)
    kab, kbc, kca, e2f = build_edge_maps(V, T)

    # 模型自身的洞
    bkeys = [k for k, v in e2f.items() if len(v) == 1]
    print(f'模型: {NV} 顶点 / {NT} 三角面 / {len(bkeys)} 条边界边')
    # 洞的数量：把边界边串成环
    bset = {}
    for k in bkeys:
        a, b = k // NV, k % NV
        bset.setdefault(a, []).append(b)
        bset.setdefault(b, []).append(a)
    seen, holes = set(), 0
    for s in bset:
        if s in seen:
            continue
        holes += 1
        cur, guard = s, 0
        while cur not in seen and guard < 10000:
            seen.add(cur); guard += 1
            nbrs = bset[cur]
            nxt = [x for x in nbrs if x not in seen]
            if not nxt:
                break
            cur = nxt[0]
    print(f'边界环(洞)数量: {holes}, 欧拉特征 χ = {NV - len(e2f) + NT}')
    print()

    SEEDS = {
        'ear': 1,      # y 最大
        'nose': 0,     # x 最大
        'tail': -0,    # x 最小
        'back': 2,     # z 最大
        'belly': -1,   # y 最小
    }
    def seed_v(name):
        k = SEEDS[name]
        col = V[:, abs(k)] * (1 if k >= 0 else -1)
        return int(np.argmax(col))

    results = {}

    def run(tag, seed, hops, kind='mvc', shape='circle', fallback=True):
        s = seed_v(seed)
        r = find_disk(s, hops, fallback, off, adj, T, e2f, NV)
        if r['disk'] is None:
            print(f'[{tag}] seed={seed} h={hops}: 非圆盘 χ={r["tried"]["chi"]} '
                  f'边界环={len(r["tried"]["cycles"])} 条 → 无法做 Tutte 嵌入')
            results[tag] = dict(r=r, UV=None, info=None, m=None)
            return results[tag]
        UV, info = solve_tutte(V, T, off, adj, r['disk'], kind, shape, NV)
        m = metrics(V, T, UV, info['inside'])
        d = r['disk']
        print(f'[{tag}] seed={seed} h={r["hops"]} w={kind} shape={shape} | '
              f'区域 {d["v"]}/{d["e"]}/{d["f"]} χ=1 环长={len(d["loop"])} | '
              f'翻面 {m["flips"]}/{m["n"]} | 面积比 {m["area_ratio"]*100:.1f}% | '
              f'角度畸变 均值 {m["ang_mean"]:.2f}° p90 {m["ang_p90"]:.2f}° | '
              f'log2 面积比 p25 {m["p25"]:.2f} 中位 {m["p50"]:.2f} p75 {m["p75"]:.2f} σ {m["std"]:.2f} | 非正权重 {info["neg"]}')
        results[tag] = dict(r=r, UV=UV, info=info, m=m)
        return results[tag]

    VN = vertex_normals(V, T)
    ELEV, AZIM = 42, -72

    # 1 默认：耳朵附近小圆盘
    a = run('default', 'ear', 10)
    two_panel(os.path.join(OUT, 'fig1-default.png'), V, T, NV, a['r'], a['UV'], a['info'],
              'tex', ELEV, AZIM,
              f'左：耳朵附近圆盘 · {a["r"]["disk"]["f"]} 面 · 闭环 {len(a["r"]["disk"]["loop"])} 顶点',
              '右：摊平后的 UV（4×4 UV 贴图）', focus=np.concatenate([a['r']['disk']['loop'], a['info']['interior']]), vnorm=VN)
    # 2 大圆盘
    b = run('large', 'ear', 26)
    two_panel(os.path.join(OUT, 'fig2-large.png'), V, T, NV, b['r'], b['UV'], b['info'],
              'tex', ELEV, AZIM,
              f'左：半径 26 的大圆盘 · {b["r"]["disk"]["f"]} 面',
              '右：摊平后的 UV', vnorm=VN)
    # 3 非圆盘：区域绕过底部的洞，χ ≠ 1，边界裂成多条环
    c = run('nondisk', 'nose', 30, fallback=False)
    fig = plt.figure(figsize=(6.6, 5.6), dpi=150)
    ax = fig.add_subplot(111, projection='3d')
    loops = [(cy['pts'], '#e08a2c') for cy in c['r']['tried']['cycles']]
    draw_3d(ax, V, T, c['r']['tried']['inside'], np.zeros((NV, 2)),
            'plain', -28, -72, loops=loops, loop_color='#2f6fd0', vnorm=VN, offset=0.035)
    ax.set_title(f'半径 30 的区域（浅蓝）：χ = {c["r"]["tried"]["chi"]}，'
                 f'边界裂成 {len(c["r"]["tried"]["cycles"])} 条环（橙）', fontsize=10, pad=2)
    fig.text(0.5, 0.02,
             '拓扑圆盘要求 χ = V − E + F = 1。区域一旦绕过模型自带的洞，χ 变负、边界不再是单条闭环，\n'
             'Tutte 定理的前提不成立，无法得到 UV。此时边界凸不凸、权重正不正都不影响这个结论。',
             ha='center', fontsize=8.5, color='#5b6573', linespacing=1.6)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(os.path.join(OUT, 'fig3-nondisk.png'), bbox_inches='tight', facecolor='white')
    plt.close(fig)

    # 4 非凸边界 → 翻面
    d = run('star', 'ear', 10, shape='star')
    two_panel(os.path.join(OUT, 'fig4-star.png'), V, T, NV, d['r'], d['UV'], d['info'],
              'tex', ELEV, AZIM,
              f'左：闭环钉成五角星 · 翻面 {d["m"]["flips"]} 个（红）',
              '右：UV 中的翻面三角形（红）',
              focus=np.concatenate([d['r']['disk']['loop'], d['info']['interior']]), vnorm=VN)
    # 5 面积畸变热图
    e = run('dist', 'ear', 20)
    two_panel(os.path.join(OUT, 'fig5-distortion.png'), V, T, NV, e['r'], e['UV'], e['info'],
              'dist', ELEV, AZIM,
              f'左：面积畸变 UV面积/3D面积（蓝=压缩，橙=拉伸）',
              f'右：UV 中的面积畸变（ΣUV/Σ3D = {e["m"]["area_ratio"]*100:.0f}%）',
              focus=np.concatenate([e['r']['disk']['loop'], e['info']['interior']]), vnorm=VN,
              uv_colors=area_colors(V, T, e['UV'], e['info']['inside']))
    # 6 权重对比：按三角形最大角度误差上色
    W = {}
    for kind in ('uniform', 'mvc', 'cotan'):
        W[kind] = run('w_' + kind, 'ear', 20, kind=kind)
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 4.7), dpi=150, layout='constrained')
    vmax = 60.0
    for ax, kind, label in zip(axes, ('uniform', 'mvc', 'cotan'),
                               ('均匀 1/deg（Tutte 原始）', '均值坐标 MVC', '余切 cotan')):
        rr = W[kind]
        ins = rr['info']['inside']
        UV = rr['UV']

        def tri_angles(P):
            A, B, C = P[T[ins, 0]], P[T[ins, 1]], P[T[ins, 2]]
            out = []
            for (p_, q_, r_) in ((A, B, C), (B, C, A), (C, A, B)):
                u, w = q_ - p_, r_ - p_
                cs = (u * w).sum(1) / (np.linalg.norm(u, axis=1) * np.linalg.norm(w, axis=1) + 1e-18)
                out.append(np.degrees(np.arccos(np.clip(cs, -1, 1))))
            return np.stack(out, 1)
        err = np.abs(tri_angles(V) - tri_angles(UV)).max(1)
        order = np.argsort(err)                       # 大误差后画，避免被小误差盖住
        pc = PolyCollection(UV[T[ins[order]]], array=err[order], cmap='YlOrRd',
                            norm=matplotlib.colors.Normalize(0, vmax), linewidths=0.15,
                            edgecolors=(1, 1, 1, 0.35))
        ax.add_collection(pc)
        lp = rr['r']['disk']['loop']
        ax.plot(UV[lp + [lp[0]], 0], UV[lp + [lp[0]], 1], color='#2f6fd0', lw=2.0)
        ax.set_xlim(-1.05, 1.05); ax.set_ylim(-1.05, 1.05)
        ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_color('#dfe3e8')
        m = rr['m']
        ax.set_title(f'{label}\n角度畸变 均值 {m["ang_mean"]:.1f}° / p90 {m["ang_p90"]:.1f}° / '
                     f'最大 {m["ang_max"]:.0f}°\nlog2 面积比 σ = {m["std"]:.2f}，非正权重 {rr["info"]["neg"]}',
                     fontsize=9, pad=5)
        sm = plt.cm.ScalarMappable(cmap='YlOrRd', norm=matplotlib.colors.Normalize(0, vmax))
        cb = fig.colorbar(sm, ax=ax, fraction=0.046, pad=0.03)
        cb.set_label('三角形最大角度误差 (°)', fontsize=8)
        cb.ax.tick_params(labelsize=7)
    fig.suptitle('同一区域（耳朵圆盘，1783 面）、不同凸组合权重下的 UV 摊平质量', fontsize=10)
    fig.savefig(os.path.join(OUT, 'fig6-weights.png'), facecolor='white')
    plt.close(fig)

    # 7 贴图本身：4×4 UV checker，标出 u / v 方向
    fig = plt.figure(figsize=(5.2, 5.0), dpi=150)
    ax = fig.add_subplot(111)
    ax.imshow(MP, extent=(-1, 1, -1, 1), origin='upper', interpolation='nearest', zorder=0)
    ax.set_xticks([-1, -0.5, 0, 0.5, 1]); ax.set_yticks([-1, -0.5, 0, 0.5, 1])
    ax.set_xticklabels(['0', '0.25', '0.5', '0.75', '1'])
    ax.set_yticklabels(['0', '0.25', '0.5', '0.75', '1'])
    ax.tick_params(labelsize=8, colors='#5b6573')
    ax.set_xlabel('$u$（色相沿此方向变化）', fontsize=9, color='#3c4654')
    ax.set_ylabel('$v$（明度沿此方向变化）', fontsize=9, color='#3c4654')
    for sp in ax.spines.values():
        sp.set_color('#dfe3e8')
    ax.set_title(f'本文用的 UV 贴图：{NCEL}×{NCEL} 格 · 每格中心叠一个半尺寸方块',
                 fontsize=10, pad=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, 'fig7-uvmap.png'), bbox_inches='tight', facecolor='white')
    plt.close(fig)

    print('\n图已输出到', OUT)


if __name__ == '__main__':
    main()
