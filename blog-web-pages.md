# 三个演示页面的实现：Canvas 2D 上跑 Tutte 嵌入

[在线演示 → listenzcc.github.io/tutte-theorem-1](https://listenzcc.github.io/tutte-theorem-1/)

这一篇写页面上做了什么：数据怎么组织、区域怎么取、线性系统怎么解、三角形怎么贴到屏幕上、为什么用 Canvas 2D 而不是 WebGL。定理本身另有一篇 [Tutte 嵌入定理](https://github.com/listenzcc/tutte-theorem-1/blob/main/blog-tutte-theory.md)。

---

## 一、三个页面

| 页面                                                                                 | 几何来源                            | 可调参数                                   |
| ------------------------------------------------------------------------------------ | ----------------------------------- | ------------------------------------------ |
| [定理演示](https://listenzcc.github.io/tutte-theorem-1/tutte-embedding-theorem.html) | 参数曲面，361 顶点 / 684 面         | 闭环半径、边界形状、权重、起伏幅度         |
| [Bunny 演示](https://listenzcc.github.io/tutte-theorem-1/bunny-tutte.html)           | Stanford Bunny，2503 顶点 / 4968 面 | 种子点、BFS 半径、边界形状、权重、显示模式 |
| [贴图演示](https://listenzcc.github.io/tutte-theorem-1/uv-texture-mapping.html)      | 参数曲面                            | 同上，外加任意图片贴图                     |

三者共用一套管线，差别只在几何来源和贴图来源。

---

## 二、管线

一次完整的更新走七个阶段：

```
几何  →  拓扑  →  区域  →  边界 UV  →  权重  →  迭代求解  →  渲染 + 统计
```

- **几何**：顶点坐标 `Float64Array(3N)`，三角形 `Int32Array(3F)`；
- **拓扑**：CSR 邻接表（`adjOff` / `adjDat`）+ 有向边到面的映射 `e2f`；
- **区域**：BFS 距离场 → 内部三角面 → 边界半边 → 串环 → 欧拉特征 $\chi$；
- **边界 UV**：按 3D 弧长比例把闭环分配到目标形状上；
- **权重**：遍历三角形，把 $\tan(\theta/2)$ 和 $\cot\theta$ 累加到边上；
- **求解**：Gauss–Seidel 松弛，逐帧推进；
- **渲染**：3D 视图 + UV 视图两个 canvas，外加状态面板。

区域和权重只在参数变化时重建，UV 在每帧迭代，渲染每帧全量重画。4968 面的模型在现代浏览器上能维持 60 fps。

---

## 三、几何来源

### 参数曲面

极坐标环网格：中心 1 个顶点，外面 $N_R = 10$ 圈、每圈 $N_S = 36$ 个顶点，共 $1 + 10 \times 36 = 361$ 顶点。三角形分两块：中心扇面 36 个，第 2 圈起每圈的每个四边形拆成 2 个三角形，共 $36 + 9 \times 36 \times 2 = 684$ 面。

高度是四个高斯包与一个正弦项的叠加：

$$h(x,z) = 0.55A\Big[e^{-\frac{(x-0.35)^2+(z-0.15)^2}{0.10}} + 0.8\,e^{-\frac{(x+0.30)^2+(z+0.35)^2}{0.07}} - 0.55\,e^{-\frac{(x+0.10)^2+(z-0.42)^2}{0.06}}\Big] + 0.22A\sin(3x)\cos(3z)$$

$A$ 是页面上的起伏幅度滑块。

网格按规则拓扑生成，绕向由构造保证。页面里仍然做了一次自检：所有三角形在 $(x,z)$ 平面上的有向面积同号。翻面判据依赖绕向一致，这一步不能省。

因为拓扑是规则的，这个页面取闭环的方式很直接：把第 $k$ 圈当作边界，圈内所有顶点为内部顶点。

### OBJ 模型

`parseOBJ` 只取 `v` 和 `f` 两行，忽略法线与纹理坐标，面按扇形三角化。读完做归一化：平移到包围盒中心，除以最大半边长，把模型缩到 $[-1,1]^3$。归一化方式会影响 $\Sigma UV / \Sigma 3D$ 这类面积比指标，两条实现（页面与离线脚本）必须一致，否则数字对不上。

---

## 四、拓扑与区域

### 邻接结构

邻接表用 CSR（compressed sparse row）：`adjOff[v]` 到 `adjOff[v+1]` 是顶点 $v$ 的邻居区间。建表时邻居会有重复（一条边被两个三角形共享），先去重再打包，否则数组尺寸算错会静默丢数据。

有向边 $(a,b)$ 编码成整数键 `ekey(a,b) = min·N + max`，映射到包含这条边的两个面。判定边界半边时用它查：半边 $a\to b$ 是边界，当且仅当它的反向边所属的面里没有别的内部面。

### 取区域

从种子点做 BFS，取跳数 $\le h$ 的顶点集合 $S$。内部三角面定义为三顶点全在 $S$ 里的面。种子点是按坐标极值选的特征点：耳朵尖（y 最大）、鼻子（x 最大）、尾巴（x 最小）、背部（z 最大）、腹部（y 最小）。

### 判定拓扑圆盘

两条硬指标同时满足才算圆盘：

$$\chi = V_{in} - E_{in} + F_{in} = 1, \qquad \text{边界半边恰好串成 1 条简单闭环}$$

串环的做法：每个边界顶点应当有且只有一条出边，沿着走一圈回到起点。中途出现分叉（出边数 $\ne 1$）或撞到已访问顶点，就是环裂开或者自交。

区域把模型的洞圈进来时 $\chi$ 会掉到 0 或负数，边界同时裂成多条。页面把每条环单独画成橙色，$\chi$ 标红，状态面板直接给出"非圆盘：定理前提不成立"。

半径不合法时页面会向两侧扫描 $\pm 1 \dots \pm 10$ 找一个合法的邻近半径，把实际使用的半径显示在状态栏。因为合法半径本身不连续，这个回退能显著提升交互体验。

---

## 五、权重与求解

### 权重累加

遍历每个三角形 $(a,b,c)$，算出三个内角，然后为三条边各累加一次：

```
addEdge(a, b, A, B, C)    // A 在 a 处，B 在 b 处，C 是 b 的对角（c 处）
```

同一条无向边被两个三角形各访问一次，键值相同，累加到同一个条目上。最终每个条目存了 $\tan$ 的两个端点分量之和、$\cot$ 之和、边长。三种权重在取用时各自归一化：

$$
w_{ij}^{uni} = \frac{1}{\deg(i)}, \qquad
w_{ij}^{cot} = \frac{\cot\alpha + \cot\beta}{\sum_k(\cot\alpha_{ik}+\cot\beta_{ik})}, \qquad
w_{ij}^{mvc} = \frac{\big(\tan\frac{\delta}{2} + \tan\frac{\gamma}{2}\big)/\|x_i-x_j\|}{\sum_k \cdots}
$$

构建时顺带统计非正权重的条数，状态面板用它显示定理前提是否被破坏。

### Gauss–Seidel

每个内部顶点就地更新为邻居的加权平均：

$$\mathbf{u}_i \leftarrow \frac{\sum_j w_{ij}\mathbf{u}_j}{\sum_j w_{ij}}$$

就地更新意味着后面的顶点立刻用到本轮已更新的值，收敛比 Jacobi 快。每帧跑 3 次 sweep，判据是单次最大位移 $< 10^{-8}$。

选择逐帧迭代而不是一次性解完，是为了让摊平过程可见：拖动半径滑块能看到 UV 从初始猜测逐步展开。

初始猜测取顶点 $(x,z)$ 坐标的缩放版本加上一点随机扰动。凸组合方程的解唯一，初始值只影响收敛速度。

### 统计

每次渲染前算三个量：翻面数（UV 有向面积 $\le 0$ 的三角形数）、$\Sigma UV / \Sigma 3D$、角度畸变。翻面数是定理的直接检验，后两个是畸变指标，定理对它们没有承诺。

---

## 六、渲染

### 投影

正交投影，绕 y 轴转 yaw、绕 x 轴转 pitch，再统一缩放：

$$x_1 = x\cos\psi_y - z\sin\psi_y, \quad z_1 = x\sin\psi_y + z\cos\psi_y$$
$$y_1 = y\cos\psi_p - z_1\sin\psi_p, \quad z_2 = y\sin\psi_p + z_1\cos\psi_p$$
$$s_x = o_x + x_1 s, \quad s_y = o_y - y_1 s$$

$z_2$ 存下来作深度用。所有顶点每帧重算一次，缓存进 `Float64Array`。

### 深度排序

画家算法：按三角形三个顶点的平均深度升序绘制。没有 z-buffer，排序是唯一的遮挡手段。凸模型上结果正确；自穿透的模型会出现排序错误，本项目不涉及。

### 明暗

面法线与视空间光源方向做 Lambert：

$$lum = 0.42 + 0.58\,\max(0, \mathbf{n}\cdot\mathbf{l}), \qquad \mathbf{l} = (0.35, 0.55, 0.76)$$

贴图模式下，明暗用一层黑色半透明覆盖（alpha $= 1 - lum$）压上去，而不是逐像素乘。Canvas 2D 没有 shader，这是能拿到逐面明暗的最省做法。

### UV 视图

右图画的是 UV 平面：底图是同一张贴图，闭环外压暗，网格线白色半透明，翻面三角形填红，闭环本身蓝色描边。左图 3D 侧和右图 UV 侧共用同一份 UV 数组，翻面在两侧同步标红。

---

## 七、逐三角形仿射贴图

Canvas 2D 只有仿射变换，没有透视变换，但这里恰好够用：正交投影下，一个平面三角形从 UV 到屏幕的映射本身就是仿射的。

设屏幕三角形 $s_0, s_1, s_2$ 对应贴图坐标 $u_0, u_1, u_2$。记

$$e_1 = s_1 - s_0, \quad e_2 = s_2 - s_0, \qquad \delta_1 = u_1 - u_0, \quad \delta_2 = u_2 - u_0$$

求 $M$ 与 $d$ 使 $s = M u + d$：

$$M = \begin{bmatrix} e_1 & e_2 \end{bmatrix} \begin{bmatrix} \delta_1 & \delta_2 \end{bmatrix}^{-1}, \qquad d = s_0 - M u_0$$

行列式 $\Delta = \det[\delta_1\ \delta_2]$ 接近 0 时三角形在 UV 上退化，跳过不画。

代码里展开成四个标量，避免构造中间矩阵：

```js
const d = (u1 - u0) * (v2 - v0) - (u2 - u0) * (v1 - v0);
const m11 = ((s1x - s0x) * (v2 - v0) - (s2x - s0x) * (v1 - v0)) / d;
const m12 = ((s2x - s0x) * (u1 - u0) - (s1x - s0x) * (u2 - u0)) / d;
const m21 = ((s1y - s0y) * (v2 - v0) - (s2y - s0y) * (v1 - v0)) / d;
const m22 = ((s2y - s0y) * (u1 - u0) - (s1y - s0y) * (u2 - u0)) / d;
```

然后交给 canvas：

```js
g.save();
g.beginPath();                       // clip 到三角形（外扩 2%~3% 抗锯齿缝）
g.moveTo(...); g.lineTo(...); g.lineTo(...); g.closePath(); g.clip();
g.transform(m11, m21, m12, m22, dx, dy);
g.drawImage(img, 0, 0, 1, 1);        // 单位方块正好被变换到三角形位置
g.restore();
```

`drawImage(img, 0, 0, 1, 1)` 把整张贴图绘制到 $(0,0)$–$(1,1)$ 的单位方块上，前面的 `transform` 把这个方块映射到三角形的三个角。UV 坐标要先归一化到 $[0,1]$：Bunny 页用 $s = (u+1)/2,\ t = (1-v)/2$；定理页的纹理范围取 $[-4,4]$（UV 乘 4，贴图按 $8\times8$ 的方块绘制），这样单位圆内正好落一个完整的 4 格图案，UV 的拉伸在格子变形上直接读得出来。

clip 时把三角形按重心外扩 2%–3%，否则相邻三角形的抗锯齿边缘之间会露出白缝。

每个三角形一次 `save/clip/transform/drawImage/restore`，684 面或 4968 面都是这个量级，Canvas 2D 能扛住。

---

## 八、为什么是 Canvas 2D

项目目录叫 `webgl-theorem`，三个页面用的都是 Canvas 2D。选择理由：

- **仿射贴图正好落在 Canvas 2D 的能力范围内**。正交投影下不存在透视校正问题，`transform` + `drawImage` 给出的结果与 GPU 光栅化一致。透视投影才需要逐像素的 $w$ 除法，那时必须上 WebGL。
- **单文件、零依赖**。三个 HTML 各自独立，没有构建步骤，没有 shader 字符串，也没有 WebGL 上下文丢失的问题。Pages 上直接托管就能跑。
- **面数规模在射程内**。几千个三角形每帧几千次 `drawImage`，桌面浏览器 60 fps 有余量。

代价主要有两个：

- 没有深度缓冲，遮挡靠排序，自穿透几何会出错；
- 没有 shader，明暗只能逐面做，无法做逐像素光照、法线贴图这类效果。

要换成 WebGL 的话，改动集中在两处：顶点数据上传成 VBO（UV 每帧更新用 `bufferSubData`），绘制改成一次 `drawElements` + 深度测试，明暗和贴图进 fragment shader。拓扑、权重、求解的部分完全不用动。

---

## 九、两条独立实现

每个结论都有两条独立实现互相验证：

|          | 页面（JS）             | 离线脚本（Python）                   |
| -------- | ---------------------- | ------------------------------------ |
| 求解     | Gauss–Seidel，逐帧推进 | `scipy.sparse.linalg.spsolve` 直接解 |
| 数据结构 | 手写 CSR + Map         | numpy 向量化                         |
| 渲染     | Canvas 2D              | matplotlib `Poly3DCollection`        |
| 用途     | 交互                   | 出图与量化指标                       |

同参数下区域顶点数、面数、$\chi$、闭环长度、翻面数、面积比全部一致。三个校验脚本：

```bash
node check-bunny-page.js           # JS / Python 数字逐项比对
python check-tex-parity.py         # 两张 UV 贴图逐像素比对
node check-html-syntax.js *.html   # 内联 script 编译检查
```

贴图那一项的做法：通过 `check-tex-raster.js` 从 HTML 里正则抽出 `makeChecker()` 的源码，在 node 里用一个只实现 `fillRect` 和 hsl 解析的最小 canvas stub 光栅化，再与 Python 版的 `uv_checker()` 逐通道比对，$512^2 \times 3 = 786432$ 个通道里排除格线取整的 1 px 边界后最大差为 0。这样在无浏览器环境下也能验证页面里的绘图代码。

---

## 十、部署

三个页面都是单文件，相对路径互相引用，直接放到静态托管上即可。两个注意点：

1. **`.nojekyll`**。GitHub Pages 默认用 Jekyll 构建，会把 `.md` 转成 `.html`，导致指向 Markdown 的相对链接 404。放一个空的 `.nojekyll` 关掉它。
2. **`fetch` 需要 http**。`bunny-tutte.html` 启动时加载 `model/bunny_small.obj`，`file://` 协议下会被浏览器拦截，本地要用 `python -m http.server` 打开。

页面状态可以用 URL 参数固定，便于复现和分享：

```
?seed=ear&hop=10&shape=circle&weight=mvc&view=tex&fb=1&yaw=0.6&pitch=0.25&zoom=1
```

---

## 参考

- 仓库：<https://github.com/listenzcc/tutte-theorem-1>
- 定理说明：[Tutte 嵌入定理](https://github.com/listenzcc/tutte-theorem-1/blob/main/blog-tutte-theory.md)
- 实测数据：[在 Stanford Bunny 上跑 Tutte 嵌入](https://github.com/listenzcc/tutte-theorem-1/blob/main/blog-bunny-tutte.md)
- M. S. Floater, _Mean value coordinates_, CAGD 20(1):19–27, 2003.
- M. S. Floater, K. Hormann, _Surface parameterization: a tutorial and survey_, 2005.
