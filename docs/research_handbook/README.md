# 从极端降水反演学科研

以云南复杂地形 YunTAPR-Net 为例的中文科研方法讲义。案例证据截至 2026-11-21，覆盖问题卡、数据契约、模型与消融、开发比较、强雨诊断、过程与独立验证、组会表达。PDF 内目录、术语、案例收据和练习答案均可点击。

- [阅读 PDF](handbook.pdf)
- [排版与正文前半部分](main.tex)
- [案例判读、练习与参考答案](casework.tex)
- [术语与证据链接](annotations.tex)
- [矢量图](figures/)

## 编辑和编译

保留三个 TeX 文件和 figures 目录的相对位置。Windows 下安装带 ctex 的 MiKTeX 或 TeX Live，使用 XeLaTeX 连续编译 main.tex 两次。第二次更新目录页码与 PDF 链接。

```text
xelatex -interaction=nonstopmode -halt-on-error main.tex
xelatex -interaction=nonstopmode -halt-on-error main.tex
```

main.tex 默认使用 ctex 的 windows 字体集。若在没有该字体集的平台编译，可改用带 Fandol 的 TeX Live 并将文档类中的 fontset=windows 改为 fontset=fandol。图示为网页版 ChatGPT 生成的单页矢量 PDF，修改内容时可以替换对应图文件。

## 证据范围与核验

讲义由 Obsidian 项目主页、证据地图、进度快照和阅读索引整理。讲义内的项目链接指向公开工作分支的固定提交。教学算例、当前开发结果、拟议的过程评价以及最终测试各有明示范围。

网页 ChatGPT 提供结构审校和图件。Harness 对文稿的科学口径进行了独立只读核验。交付版补齐 A20 原筛查的代价、TAIL20 的八项通过与一项失守、REAL/ZERO 的全域反例和事件限制。随后复核了修订文字、图中数字和图例。

交付检查包含两遍 XeLaTeX 编译、17 页逐页渲染、6 张图、34 个术语双向导览锚点、20 个外部链接和 13 个固定仓库来源。复算了案例的像元时分母、命中率和精确率。科学状态沿用 NOT_VERIFIED，新增科研计算为零。
