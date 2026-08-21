# 下一轮训练与路由改进计划（待用户提醒后执行）

> 记录时间：2026-08-21 白天（用户要求保留算力，仅记录不执行）

## 1. 已知误判案例（真实使用中发现）

| 案例 | 实际类别 | 误判为 | 置信度参考 |
|---|---|---|---|
| 游戏画面 | content（CG 渲染） | structure | 用户实测 |
| SolidWorks 界面截图 | structure（ui） | content | 用户实测 |

## 2. 根因分析：训练数据分布与真实使用场景的差异

当前数据来源（第一轮训练）：
- **content（1000 张）**：picsum/Unsplash 纯照片（风景/建筑/人像等摄影作品）
- **structure（1088 张）**：headless Chromium 渲染的真实**网页**

**缺失的数据类型**（真实使用中高频出现）：
- 游戏画面（CG/3D 渲染，既非照片也非网页）
- 专业桌面软件界面（SolidWorks / Blender / CAD / 建模等，非网页）
- 游戏内 UI、启动器、专业工具面板

→ 游戏画面（CG）与 SolidWorks 界面（深色专业 UI）都是**分布外数据（OOD）**，
第一轮分类器在它们上不可靠，与 val 准确率（L1 100% / L2 88%）不矛盾——val 只覆盖训练分布。

## 3. 改进方向（用户提出 + 分析）

### 3.1 数据补充（第一优先）
- **content 补充**：游戏截图（CG 渲染）、插画/画作、专业软件 3D 视口（SolidWorks/Blender 视口）
- **structure 补充**：桌面应用截图（SolidWorks 等专业软件完整窗口）、游戏内 UI、启动器界面
- **采集方式**：
  1. 本机各软件窗口截图（win 工具 / 系统 PrintScreen，可批量）
  2. 游戏画面截图（用户游玩时收集，或网络游戏壁纸/宣传图——注意真实截图优先）
  3. 软件官网的界面图、应用商店截图（App Store / Microsoft Store / Steam 商店有大量真实软件界面图）
  4. 已渲染网页可保留，但需**平衡各类来源占比**，避免网页主导

### 3.2 路由策略调整（不依赖训练也可改进）
- **分配阈值**：当前 L1 置信度阈值 0.6（< 0.6 → degraded 交叉验证）。可考虑：
  - 置信度落在 0.5~0.7 的模糊区间时降级（不硬分 content/structure）
  - 或对 content/structure 用不同阈值（structure 误判 content 的代价 vs 反之）
- **OmniParser 保底**：OmniParser 内置 OCR + 元素解析，**表单/文本类它也能处理**，
  因此 structure 类可统一走 `parse_ui_screenshot`（而非当前 form→OCR、text→OCR 分流）；
  或 form/text 走 OCR 的同时并行 OmniParser，取信息更全者。
  代价：OmniParser 常驻 GPU（约 2.4GB，可用 manage_vision_backend release 释放）。

### 3.3 重训后的验证
- 用误判样本（游戏画面、SolidWorks 截图）回归
- 补充真实桌面应用截图作为新 val 集，重测 L1/L2 准确率
- 观察 ui/form 灰色地带是否改善

## 4. 待办清单（用户提醒后执行）

- [ ] 收集误判样本：游戏画面、SolidWorks 截图（请用户提供或系统截图）
- [ ] 补充 content/structure 数据（重点：游戏 CG、专业软件界面）
- [ ] 重跑 `train.data` → `train.train_l1` / `train.train_l2`（夜间）
- [ ] export 覆盖权重 + 误判样本回归验证
- [ ] 评估路由阈值调整与 OmniParser 保底策略（可与训练并行评估）
