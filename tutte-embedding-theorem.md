# 那个"闭环钉在圆上就能摊平"的定理：Tutte 嵌入定理

## 一句话答案

**Tutte 嵌入定理**（Tutte's barycentric embedding theorem，W. T. Tutte, 1963，《How to draw a graph》）。

它是 UV 参数化里"固定边界"这一整类方法的理论地基：CGAL 的 `Barycentric_mapping_parameterizer_3`、Blender 的 UV unwrap、UVAtlas、各类自动 UV 展开流程，底层兜底的那一步基本都是它。

连续（光滑）版本的对应物叫 **Radó–Kneser–Choquet 定理**（RKC，Radó 1926 / Kneser 1926 / Choquet 1945）。Tutte 定理可以看成 RKC 的离散版本——这两条经常在论文里成对出现。

---

## 定理到底说了什么

设有一片**拓扑圆盘**的三角网格：在曲面上画一条简单闭曲线（不自我交叉、不重复经过顶点），闭曲线内部连同边界就是这片网格。把这 $n$ 个边界顶点按原来的循环顺序记作 $v_1,\dots,v_n$，内部顶点记作集合 $I$。

**两个前提：**

1. **边界凸**：把边界顶点映到平面上某个**凸多边形**上（圆是它的特例，正方形也是），且保持循环顺序；
2. **凸组合**：每个内部顶点的 uv 坐标，是它所有邻居 uv 坐标的**严格凸组合**

$$\mathbf{u}_i=\sum_{j\in N(i)} w_{ij}\,\mathbf{u}_j,\qquad w_{ij}>0,\quad \sum_{j\in N(i)} w_{ij}=1,\quad i\in I$$

**结论：** 用三角形内的线性插值把映射延拓到整片网格，得到的分片线性映射是**全局单射（globally injective）**——没有三角形翻面，没有区域重叠。

写成线性系统就是解两个稀疏方程（$u$ 和 $v$ 各一个）：

$$L_W \mathbf{x} = \mathbf{b}_x,\qquad L_W \mathbf{y} = \mathbf{b}_y,\qquad L_W = I - W$$

$W$ 的每行和为 1，所以 $L_W$ 是（归一化）图 Laplacian，对角占优，Gauss–Seidel 迭代必然收敛。这也是为什么实现里可以直接"松弛"而不需要"求解器"。

---

## 你记忆里需要修正的两处

**1. 凸性要求不在原曲面上，在目标边界上。**

原曲面本身完全不要求是凸的。马鞍面、带褶皱的扫描件、人脸模型，只要切出来的那片是拓扑圆盘，定理照样成立。要求凸的是**你把闭环钉上去的那个平面形状**：必须是凸多边形。钉成星形、L 形这类凹形状，定理的前提就没了，翻面真的会出现（HTML 演示里可以直接试）。

**2. "凸面"这个印象大概来自 Steinitz 定理。**

Tutte 原始表述针对的是 **3-connected 平面图**。而 **Steinitz 定理**说：一个图是某个凸多面体的边图，当且仅当它是 3-connected 平面图。所以"凸多面体表面 → 一定能摊平"这条链路是真的，只是凸性是用来保证 3-connected 的，而不是摊平过程本身需要它。

**3. 闭环的要求是拓扑的，不是几何的。**

闭环只需要是简单闭曲线，把曲面切成 genus 0、单边界的圆盘。曲面上任意取一条闭环都能满足（只要不打结、不自交、不绕着柄转一圈）。高亏格曲面必须先沿割线切开成圆盘才能用。

---

## 为什么它和 UV 坐标 / 表面贴图绑在一起

贴图需要的是一个从 3D 表面到 2D 纹理图的映射 $\phi: S \to \mathbb{R}^2$。这个映射可以有畸变（拉伸、压缩都行），但**必须单射**——一旦有三角形翻面，那块纹理就会在模型上打成结、出现镜像撕裂，渲染出来是明显的破面。

定理的价值就在这里：它把"无翻转"从一个需要事后检查的性质，变成了**构造时就带保证**的性质。只要做到两件事（边界钉凸 + 权重全正），单射是免费的，不用跑任何后验检查。

CGAL 文档里那串方法（Tutte 重心映射、离散保面积、离散共形、均值坐标）全都写着同一句话：*"a one-to-one mapping is guaranteed only if the convex combination condition is fulfilled and the border is convex"*——这就是定理前提的直接翻译。

---

## 证明直觉（三步）

**第一步：内部点跑不出边界的凸包。**

设 $u$ 是某一坐标分量，取内部顶点中 $u$ 值最大的那个 $i$。因为 $u_i$ 是邻居 $u_j$ 的严格凸组合，而它已经是最大值，所以所有邻居都必须等于 $u_i$。沿着"等于最大值"的关系扩散到整个连通网格，会推到某个边界顶点也等于 $u_i$——于是 $u_i \le \max$ 边界值。对最小值同理。结论：**所有内部点都落在边界凸包的内部**。

**第二步：边界三角形的定向是正的。**

边界被钉在一个凸多边形上，按循环顺序排列，所以紧贴边界的那些三角形定向必然正确（有向面积 > 0）。

**第三步：定向不会在内部"跳变"，于是绕数为 1。**

凸组合条件意味着相邻三角形的定向不可能只翻转一个而保持方程成立——翻面需要通过退化（面积 = 0）才能发生，而严格凸组合排除了退化。所以定向从边界一路保持到内部，所有三角形定向一致。

再配合边界是凸多边形（绕数 = 1），映射的拓扑度是 1，结合局部同胚，推出全局单射。

---

## 局限和常见的坑

**1. 只保证单射，不保证低畸变。**

Tutte 原始权重 $w_{ij}=1/\deg(i)$ 只看连接关系，完全不管 3D 几何，摊平后的面积畸变经常大到没法用。所以工程上会换权重：

| 权重 | 公式 | 恒正？ | 特点 |
|---|---|---|---|
| 均匀（Tutte） | $w_{ij}=1/\deg(i)$ | 是 | 最稳，畸变最大 |
| 余切（cotan / 共形） | $w_{ij}=\cot\alpha_{ij}+\cot\beta_{ij}$ | **否** | 保角最好，钝角三角形上权重变负 |
| 均值坐标（MVC, Floater 2003） | $w_{ij}=\dfrac{\tan(\delta/2)+\tan(\gamma/2)}{\lVert x_i-x_j\rVert}$ | 是 | 恒正 + 保形，工程上最常用 |

**2. 余切权重会破坏前提。**

遇到钝角三角形，$\cot$ 变负，凸组合条件不成立，翻面就可能出现。这正是 Floater 提出均值坐标的动机：权重恒正，等于把定理的前提钉死了。

**3. 固定边界本身会引入畸变。**

把一条任意形状的闭环强行钉到圆上，那一步已经在拉伸了。所以后来才有自由边界方法（LSCM、ARAP、SLIM、对称 Dirichlet）：让边界也参与优化来降畸变，代价是失去定理的保证，必须在优化后额外做去翻转（flip elimination）。

**4. 浮点精度会让理论保证失效。**

定理是在实数域上成立。用 double 解线性系统时，极端网格上仍会算出翻面——SIGGRAPH 2025 那篇 *Divide-and-Conquer Embedding* 专门处理这件事：在 21.4K 个网格上，Tutte 用 IEEE 754 双精度有 150 例失败，换 MPFR 512 位才降到 0。要用精确算术（exact arithmetic）才能真正兑现定理的承诺。

**5. 三维不成立。**

RKC 定理只在 2D 成立：调和映射到 $\mathbb{R}^3$ 的非凸域上不再保证单射。所以体网格参数化没有这条免费的午餐。

---

## 命名速查

| 名字 | 适用场景 | 一句话 |
|---|---|---|
| **Tutte 嵌入定理**（1963） | 离散三角网格 | 边界钉凸 + 凸组合 ⟹ 无翻转 |
| **Radó–Kneser–Choquet** | 连续调和映射 | 边界同胚到凸域边界，调和延拓后是微分同胚 |
| **Floater 凸组合映射**（1997） | 离散，任意正权重 | 把 Tutte 的均匀权重推广到任意正权重 |
| **均值坐标 MVC**（2003） | 离散，权重恒正 | 恒正的凸组合权重，工程首选 |
| **Steinitz 定理** | 凸多面体图 | 凸多面体边图 ⟺ 3-connected 平面图 |
| **Fáry 定理** | 平面图 | 每个平面图都有直线段平面嵌入（Tutte 是构造性证明） |
| Gortler–Gotsman–Thurston（2006） | 离散微分形式 | 用离散 1-form 重证 Tutte，并推广到平环、多连通域 |

---

## 参考

- W. T. Tutte, *How to draw a graph*, Proc. London Math. Soc. 13(3):743–767, 1963.
- M. S. Floater, *Parametrization and smooth approximation of surface triangulations*, CAGD 14(3):231–250, 1997.
- M. S. Floater, *Mean value coordinates*, CAGD 20(1):19–27, 2003.
- M. S. Floater, K. Hormann, *Surface parameterization: a tutorial and survey*, 2005.
- S. Gortler, C. Gotsman, D. Thurston, *Discrete one-forms on meshes and applications to 3D mesh parameterization*, CAGD 23(2):83–112, 2006.
- *Divide-and-Conquer Embedding*, SIGGRAPH Conference Papers, 2025.
- CGAL 文档, *Planar Parameterization of Triangulated Surface Meshes*（各方法的 bijectivity 条件说明）。

---

## 顺带一句：如果真的是"球面大圆"

如果你听到的确实是球面上的**大圆**（great circle），那是另一件事：球面参数化没有无畸变的平坦映射，因为高斯曲率非零，高斯绝妙定理（Theorema Egregium）直接堵死了这条路。球面 UV（经纬度）必然在极点附近有严重的面积畸变。这种情况下用到的工具是球面共形映射、cube map、或者直接在球面上做纹理，而 Tutte 定理是给**拓扑圆盘 → 平面圆盘**用的。
