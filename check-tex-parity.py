# -*- coding: utf-8 -*-
"""贴图一致性校验：页面里的贴图生成代码 vs 离线脚本 uv_checker()，逐像素比对。

覆盖两张：
  bunny-tutte.html             → makeChecker()，4×4 格，纹理范围 [-1,1]
  tutte-embedding-theorem.html → texCanvas（IIFE），16 格 / 图案周期 4，纹理范围 [-4,4]

流程：node check-tex-raster.js <html> <tmp.ppm> 把页面源码光栅化，再与 Python 版逐通道比。

运行：
  C:/Users/liste/miniconda3/envs/python3.11/python.exe check-tex-parity.py
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.stdout.reconfigure(encoding='utf-8')


def load_rf():
    spec = importlib.util.spec_from_file_location('rf', os.path.join(HERE, 'render-bunny-figs.py'))
    rf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rf)
    return rf


def raster(node, html, out):
    subprocess.run([node, os.path.join(HERE, 'check-tex-raster.js'),
                    os.path.join(HERE, html), out], check=True)


def read_ppm(p):
    with open(p, 'rb') as f:
        assert f.readline().strip() == b'P6'
        w, h = map(int, f.readline().split())
        assert int(f.readline()) == 255
        return np.frombuffer(f.read(), np.uint8).reshape(h, w, 3).astype(float)


def compare(tag, js, py, n, label):
    d = np.abs(js - py)
    h, w = d.shape[:2]
    edge = np.zeros((h, w), bool)
    for k in range(n + 1):
        p = int(round(k * w / n))
        edge[max(0, p - 2):p + 3, :] = True
        edge[:, max(0, p - 2):p + 3] = True
    inner = d[~edge]
    ok = inner.max() < 1
    print(f'{tag}  [{label}]  {w}×{h}，{d.size} 个通道')
    print(f'    排除网格线 ±2px：最大差 {inner.max():.0f}，平均差 {inner.mean():.4f}，'
          f'差 >8 的通道占比 {100*(inner > 8).mean():.3f}%  → {"完全一致 ✓" if ok else "存在差异 ✗"}')
    print(f'    含网格线：最大差 {d.max():.0f}（差异全部来自 fillRect 与 numpy 切片在格线上的 1px 取整）')
    return ok


def main():
    node = shutil.which('node') or r'C:\Users\liste\.workbuddy\binaries\node\versions\22.22.2-3\node.exe'
    rf = load_rf()
    tmp = os.path.join(tempfile.gettempdir(), '_tex_parity.ppm')
    allok = True

    raster(node, 'bunny-tutte.html', tmp)
    allok &= compare('bunny-tutte.html', read_ppm(tmp), rf.MP * 255.0,
                     rf.NCEL, f'makeChecker {rf.NCEL}×{rf.NCEL}')

    raster(node, 'tutte-embedding-theorem.html', tmp)
    ref = rf.uv_checker(n=16, tile=4, phase=2, res=256) * 255.0
    allok &= compare('tutte-embedding-theorem.html', read_ppm(tmp), ref, 16, 'texCanvas 16 格 / 图案周期 4')

    # 顺带确认平铺图案与 bunny 那张是同一套：tutte 纹理范围 [-4,4]、16 格，
    # 单位圆 [-1,1] 落在中心 4 格（256 像素里的 [96:160]），格底色应与 bunny 的整张一致。
    # 两张分辨率不同（每格 16px vs 128px），中心块与格线的取整位置会差 1-2px，
    # 所以按"格内固定比例位置"取样比较格底色。
    ref4 = rf.uv_checker(n=4, res=512)
    worst = 0.0
    for a in range(4):
        for b in range(4):
            y1 = 96 + int(round((a + 0.2) * 16))
            x1 = 96 + int(round((b + 0.2) * 16))
            y2 = int(round((a + 0.2) * 128))
            x2 = int(round((b + 0.2) * 128))
            worst = max(worst, float(np.abs(ref[y1, x1] - ref4[y2, x2] * 255.0).max()))
    print(f'平铺图案一致性：tutte 贴图单位圆内的 16 个格底色 vs bunny 贴图，'
          f'最大差 {worst:.0f}  → {"同一套图案 ✓" if worst < 2 else "不一致 ✗"}')
    allok &= worst < 2

    os.remove(tmp)
    print('\n结论：', '全部通过 ✓' if allok else '有项目未通过 ✗')
    return 0 if allok else 1


if __name__ == '__main__':
    sys.exit(main())
