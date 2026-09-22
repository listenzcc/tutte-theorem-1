# Tutte 嵌入定理：交互演示与一篇实测笔记

**[在线演示 → listenzcc.github.io/tutte-theorem-1](https://listenzcc.github.io/tutte-theorem-1/)**

三角网格上"取一条闭环、把闭环钉到凸多边形边界上、内部顶点取邻居的凸组合"——Tutte 在 1963 年证明这样得到的分片线性映射**全局单射**，一个三角形都不会翻。这正是 UV 参数化里最基础的那个无翻转保证。

仓库里有三个零依赖的单文件演示页面，外加一篇把整条流程在 Stanford Bunny 上跑一遍的技术笔记。

**在线打开：** <https://listenzcc.github.io/tutte-theorem-1/>

---

## 定理速览

设网格区域是一个拓扑圆盘（$\chi = 1$、单条边界环）。把边界顶点按顺序钉到一个凸多边形的边界上，内部顶点满足

$$\mathbf{u}_i = \sum_{j \in N(i)} w_{ij}\,\mathbf{u}_j, \qquad w_{ij} > 0, \qquad \sum_{j \in N(i)} w_{ij} = 1$$

也就是解两个稀疏线性系统 $L_W \mathbf{x} = \mathbf{b}_x$、$L_W \mathbf{y} = \mathbf{b}_y$，其中 $L_W = I - W$。那么得到的分片线性映射是全局单射。

两个前提：

1. **边界凸。** 换成五角星或 L 形，翻面就集中出现在凹角附近。
2. **权重严格凸组合。** 余切权重在钝角三角形上会变负，凸组合条件被破坏。

这是充分条件。前提不成立时定理不做任何承诺——实测里有 709 条边权重非正却 0 翻面的例子，也有边界一换五角星就出 14 个翻面的例子。

定理不管的另一件事是**畸变**。它只保证不翻，不保证形状好看。

---

## 三个演示

| 页面 | 内容 |
|---|---|
| [`tutte-embedding-theorem.html`](tutte-embedding-theorem.html) | 参数曲面上取闭环，调边界形状（圆 / 五角星 / L 形）与权重（均匀 / 余切 / 均值坐标），看翻面被标红、UV 面板同步更新 |
| [`uv-texture-mapping.html`](uv-texture-mapping.html) | 上传本地图片或填 URL 当作贴图，按算出的 UV 铺到曲面上；内置 UV checker 与色卡两种预设 |
| [`bunny-tutte.html`](bunny-tutte.html) | 真实扫描模型 Stanford Bunny。从种子点 BFS 扩张取区域，先判拓扑圆盘，合法了才解嵌入 |

前两个直接双击打开就行。`bunny-tutte.html` 要 `fetch` 加载 OBJ，得走 http：

```bash
python -m http.server 8765
# 打开 http://127.0.0.1:8765/index.html
```

页面支持用 URL 参数固定状态：

```
?seed=ear&hop=10&shape=circle&weight=mvc&view=tex&fb=1&yaw=0.6&pitch=0.25&zoom=1
```

---

## 实测数据（Stanford Bunny）

兔子是**带 4 个洞的开曲面**，不是闭曲面：

| 指标 | 数值 |
|---|---|
| 顶点 / 三角面（`bunny_small.obj`） | 2503 / 4968 |
| 边界边（只属于 1 个面） | 42 |
| 欧拉特征 $\chi = V - E + F$ | $-2$ |
| 洞的数量 | 4 |

这一条决定了能圈出多大区域。从种子点按 BFS 跳数扩张，扫一遍半径：

| 种子 | h=6 | h=10 | h=14 | h=18 | h=22 | h=26 | h=30 |
|---|---|---|---|---|---|---|---|
| 耳朵尖 | ✓ 211面 | ✓ 433面 | ✗ χ=0 | ✗ χ=0 | ✗ χ=0 | ✓ 2899面 | ✓ 3751面 |
| 鼻子 | ✓ 218面 | ✓ 523面 | ✗ χ=0 | ✗ χ=−3 | ✗ χ=−3 | ✗ | ✗ χ=−3 |
| 尾巴 | ✓ 261面 | ✓ 723面 | ✗ χ=0 | ✗ χ=0 | ✓ 3288面 | ✗ χ=0 | ✗ χ=−3 |
| 背部 | ✓ 229面 | ✓ 621面 | ✓ 1169面 | ✗ χ=0 | ✗ | ✗ | ✗ |
| 腹部 | ✗ χ=0 | ✗ χ=−2 | ✗ χ=−3 | ✗ χ=−4 | ✗ χ=−4 | ✗ | ✗ χ=−4 |

合法半径**不连续**：耳朵尖 h=10 合法，h=14 到 22 全不合法（区域骑到了洞上），h=26 又合法。腹部种子紧贴洞边，全程无解。

前提满足时的结果：

| 配置 | 面数 | χ | 闭环 | 翻面 | 角度畸变均值 | $\log_2$ 面积比中位 |
|---|---|---|---|---|---|---|
| 耳朵 h=10，圆形，MVC | 433 | 1 | 27 | 0 | 13.38° | −4.08 |
| 耳朵 h=26，圆形，MVC | 2899 | 1 | 91 | 0 | 9.46° | −0.87 |
| 耳朵 h=10，五角星，MVC | 433 | 1 | 27 | **14** | 18.19° | −3.95 |
| 耳朵 h=20，圆形，余切 | 1783 | 1 | — | 0 | 10.36° | −1.61 |

面积畸变的尾部很重：中位数 −4.08 意味着一半的三角形被压缩了 16 倍以上，四分位距跨 9 个 $\log_2$ 单位。这是固定边界的参数化的典型形态。

![耳朵附近的圆盘：433 面，闭环 27 顶点，摊平后 0 翻面](figs/fig1-default.png)

左图是 3D 侧（贴 UV checker），右图是摊平后的 UV 平面，红色标翻面三角形。同一个闭环把边界换成五角星，右图立刻出现 14 个红块，全堆在凹角上。

![闭环钉成五角星：14 个翻面](figs/fig4-star.png)

完整分析在 [`blog-bunny-tutte.md`](blog-bunny-tutte.md)，含 7 张配图。

## 文章

| 文章 | 内容 |
|---|---|
| [`blog-tutte-theory.md`](blog-tutte-theory.md) | 定理理论：表述与证明骨架（极值原理 → 局部单射 → 度论证）、三种权重的来头与正值性、定理的覆盖范围、与 Radó–Kneser–Choquet 定理的对应 |
| [`blog-web-pages.md`](blog-web-pages.md) | 页面实现：管线七阶段、区域与圆盘判定、Gauss–Seidel 求解、逐三角形仿射贴图的矩阵推导、Canvas 2D 的取舍、两条实现的交叉校验 |
| [`blog-bunny-tutte.md`](blog-bunny-tutte.md) | 实测笔记：模型拓扑体检、半径扫描表、翻面与畸变的量化结果、7 张配图 |

---

## 文件

```
index.html                      引导页（GitHub Pages 入口）
.nojekyll                       关掉 Jekyll，让 Markdown 按原文件托管
tutte-embedding-theorem.html    定理演示（参数曲面）
uv-texture-mapping.html         任意图片贴图演示
bunny-tutte.html                Stanford Bunny 演示

blog-tutte-theory.md            定理理论
blog-web-pages.md               页面实现
blog-bunny-tutte.md             实测笔记（七节 + 7 张图）
tutte-embedding-theorem.md      定理速查

render-bunny-figs.py            离线出图与量化指标（numpy / scipy / matplotlib）
model/bunny_small.obj           2503 顶点 / 4968 面
model/stanford-bunny.obj        35947 顶点 / 69451 面
figs/*.png                      笔记里的 7 张图

check-bunny-page.js             页面 JS 与离线脚本的数字交叉验算
check-tex-parity.py             页面贴图与离线贴图逐像素比对
check-tex-raster.js             上面那个脚本用的 canvas 光栅化器
check-html-syntax.js            三个页面内联 script 的编译检查（无浏览器环境下用）
check-blog-style.py             笔记交付前校验（禁用句式、公式配对、图片引用）
```

## 复现

两条实现相互独立：JS 版自己写解析、BFS、权重与 Gauss–Seidel 松弛；Python 版用 numpy 向量化 + `scipy.sparse.linalg.spsolve` 直接解。同参数下区域顶点数、面数、$\chi$、闭环长度、翻面数、面积比全部一致。

离线出图：

```bash
pip install numpy scipy matplotlib
python render-bunny-figs.py        # 图输出到 figs/，指标打印到 stdout
```

交叉验算：

```bash
node check-bunny-page.js           # JS / Python 数字逐项比对
node check-html-syntax.js *.html   # 内联 script 语法检查
python check-tex-parity.py         # 两张 UV 贴图逐像素比对
python check-blog-style.py         # 笔记风格与引用校验
```

---

## 参考

- W. T. Tutte, *How to draw a graph*, Proc. London Math. Soc. 13(3):743–767, 1963.
- M. S. Floater, *Mean value coordinates*, Computer Aided Geometric Design 20(1):19–27, 2003.
- M. S. Floater, K. Hormann, *Surface parameterization: a tutorial and survey*, 2005.
- Stanford 3D Scanning Repository（Stanford Bunny 模型）。
- CGAL, *Planar Parameterization of Triangulated Surface Meshes*（各方法的 bijectivity 条件）。

模型下载自 <https://graphics.stanford.edu/~mdfisher/Data/Meshes/bunny.obj> 与
[common-3d-test-models](https://github.com/alecjacobson/common-3d-test-models)。
