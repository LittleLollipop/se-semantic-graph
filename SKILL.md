---
name: se-semantic-graph
description: 软件工程语义图谱——把项目全知识域（客户画像/需求/成本/架构/分层/模块运行逻辑/历史决策）落进 axolotl 图库，修 bug/加功能/重构时沿跨域语义边定向查询精确上下文，根治上下文爆炸与注意力分散。触发词：项目语义图谱、修 bug 前查上下文、这段代码为什么存在、功能来源、为何这么设计、影响面查询。
description_zh: "软件工程语义图谱：图库定向查询项目语义上下文，根治上下文爆炸"
---

# 软件工程语义图谱（se-semantic-graph）

## 是什么

把经典软件工程的**全知识域**（不是只有需求）落进 axolotl 图库，节点带字段级摘要，跨域语义边连接。编程/调试/重构时，从任意入口（报错栈函数、模块、需求、决策）沿语义边**定向遍历**，只取与当前任务相关的上下文——替代"把整个项目塞进 prompt 硬扛"。

## 核心命题

编程中反复调试修改的根因，往往不是"不会写"，而是**上下文爆炸 + 注意力分散**：
修 bug 时看不到这段代码服务于什么需求、为什么存在、当初为什么这么设计。
写作用图库解决"长篇跨章一致性"，编程用图库解决"跨代码库的功能-需求-约束一致性"。
**同一个病，同一副药。**

## 依赖（前置安装）

底层 axolotl 图库需支持 `in_neighbors`（入边遍历）：

```bash
# axolotl (dev 分支) 需含 in_neighbors API：
# src/graph_db.rs / mmap_graph.rs / py_bindings.rs 三层都已补齐后构建：
cd <axolotl>/prototype-rust
maturin build --release --features python-bindings -o target/wheels
# 用有 axolotl_rs 的 venv python 安装 wheel
pip install --force-reinstall --no-deps target/wheels/axolotl_rs-*.whl
```

验证：`python -c "import axolotl_rs; print('in_neighbors' in dir(axolotl_rs.AxolotlGraph))"` → `True`

## 环境变量

| 变量 | 含义 | 默认 |
|---|---|---|
| `SE_SEMANTIC_DIR` | 图文件目录（**每个项目一个目录**） | `~/.workbuddy/se-semantic-graph` |
| `SE_SEMANTIC_ENGINE` | lobster-memory 引擎目录 | `~/.workbuddy/skills/lobster-memory` |

## 运行

```bash
PY=<lobster-memory venv python>   # 有 axolotl_rs 的那个
RUN=~/.workbuddy/skills/se-semantic-graph/runner.py

cd <项目根>                       # ← 唯一需要的"配置"：在项目根目录下调用
$PY $RUN init                                  # 初始化项目图
$PY $RUN add --id <id> --label <名> --type <类型> --summary <一句话> --source <来源>
$PY $RUN connect --from <id> --to <id> --kind <边类型> [--note <说明>]
$PY $RUN get --id <id>                         # 读节点 + **正文** + 出/入边
                                               #   （`--no-content` 只要元信息）
$PY $RUN append --id <id> --file <文件>        # 追加正文（写 content，**永不裂**）
$PY $RUN trace --start <id> --direction up|down --depth 4 [--verbose]   # 核心
$PY $RUN list --type <类型>
$PY $RUN stats
$PY $RUN doctor                                # 图库体检（有问题 exit 1，可当门禁）
$PY $RUN types                                 # 列出全部节点/边类型
```

## 🔴 写完图库**必须**跑一次 `doctor`（2026-09-19 实证：39% 的节点是隐形的）

一个真实事故：某项目图库 **422 个节点里有 163 个（39%）** `stats` / `list` / `trace`
**根本看不到**，而没有任何一处报错。根因是**两条写法配根方式不同**：

| 写法 | 配根 | 后果 |
|---|---|---|
| `runner.py add` | **自动**补 `ROOT_ID --has_member--> 新节点` | ✅ 可见 |
| `graph_crud bulk` | **不补** | ❌ 只要它没连到别的可达节点，就永远看不见 |

症状极像"我明明写过这个节点" —— 而人不会怀疑工具，只会以为自己记错了。

```
$PY $RUN doctor
[图库体检] 节点 425 ｜ 边 991
✅ ① 枚举完整性：所有 live 节点都可达
✅ ② 类型越界：全部在 schema 的 17 种内
✅ ③ 边类型越界：用过 ≥5 次的 kind 都已在 schema 内
   ⚠️ 长尾（用过 1~4 次的自造 kind，23 种 / 35 条）：solves×3、documents×3、…
✅ ④ 重边：无平行重复边
✅ ⑤ id 污染：无
```

五项检查与各自的修法（**别混**）：

| 检查 | 修法 |
|---|---|
| ① 枚举完整性（live 节点不在 walk 内）| 补一条 `edge_add {from: ROOT_ID, to: <id>, kind: has_member}` |
| ② 节点类型越界 | `upsert` 带新 type 改名 —— ⚠️ **content 传原 content，别传 `node_body`** |
| ③ 边类型越界（≥5 次）| 登记进 `schema.EDGE_KINDS`，或并到语义最近的 kind（**先并纯同义词**）|
| ④ 重边（同一 (src,dst) >1 条）| 对每对先 `edge_rm` 再 `edge_add`（`rm` 会删光全部副本 ⇒ 净剩 1 条）|
| ⑤ id 污染 | 见 `graph_crud check-ids` |

### 边类型越界：**分两档处理**，长尾不要动（2026-09-19 实测）

同一个项目图库普查出 **37 种越界 kind**，其中 `has_member` 352 条、`relates_to` 56 条 ——
**实践早就长出了它需要的边，而 schema 里没有**（`connect` 会拒绝写）。分两档：

**A. 用得多的 ⇒ 吸收进 schema。** 判据与节点类型同源：**用得够多（≥5 条）
且语义不与其他 kind 重合**。一次整理吸收了 7 种：`has_member` / `relates_to` /
`extends` / `refines` / `supersedes` / `uses` / `supports`。

**B. 纯同义词 ⇒ 并到主流写法。** 一次并掉 48 条边：
`related` / `related_to` / `sibling_of` / `complements` / `mirrors` → `relates_to`
（都是无方向的关联）；`amends` / `corrects` → `refines`（都是对既有东西做修订）。

**C. 长尾（用过 1~4 次，这个库有 23 种 / 35 条）⇒ 只报警，不自动改。**
它们各自有细微差别（`closes` vs `closes_partial` vs `resolves` vs `answers`…），
而且**方向未必一致** —— 批量改名会把语义搞错，风险大于收益。
`doctor` 会列出它们，但**不算失败**；那部分留给人在真要查那几条边时逐条判。
⚠️ 别把 doctor 报的长尾当成"待办清单"去清空 —— 那会把 35 条边的语义清成 0 信息。

### 两条批量操作的坑（都在同一次整理里踩到）

**① 批量改名时，`content` 一定要传「原 content」而不是 `node_body`。**
本项目 **62% 的节点正文在 `summary` 里**（`seed_semantic.py` 走
`graph_api.upsert_node` 的 summary 形参写的），而 `node_body` 是"content 优先、
回落 summary"的**读侧**兜底。把 `node_body` 写进 `content` ⇒ 同一节点出现**两份正文**
（且下次重跑 seed 会把 summary 那份覆盖掉，两份还会不一致）。
⇒ 改名只该动 `type`；用 `graph_crud dump`/`all_nodes` 取原始字段值，别用读侧合成值。
判据：改完跑一次**逐字段比对**（`content` / `summary` 的 md5、`weight`、`domain`、
`label`、`status`）—— 只有 `type` 该变。

**② 用底层 `graph_crud append` 追加「技能建的节点」会把正文写成两半。**
本技能 `add` 建节点时正文在 `summary`（seed 字段），底层 append 只写 `content`，
而读侧 `node_body` 是「content 优先」⇒ 追加完之后**只看得见新追加的那半段**，
读起来像"原内容被删了"（实测踩到过一次）。
⇒ 追加一律走 `runner.py append`：它先取 `node_body` 再整体写回 `content`，
所以永远不会裂；也不要在库里直接手改 `summary`（重跑 seed 会覆盖它）。

**③ 批量补边之后必跑 `scan-dups`。** 引擎的 `raw add_edge` 会**偶发为同一对
生成平行边**（工具自己的注释里有记录）。一次给 root 补 161 条边之后实测多出 7 组重边。
⇒ 补边 → `scan-dups` → 有重边就 `rm + add` 去重（代码见上表）。


库目录**自动推导** = `~/.workbuddy/se-semantic-graph/<当前目录名小写>/`。
也可 `--project <dir>` 显式指定（须写在子命令**之前**），或 `SE_SEMANTIC_DIR` 覆盖。

## 🔴 库放在哪：**技能数据目录**，不要放项目里

这不是偏好，是**不弹窗的唯一前提**。2026-09-19 用户连问三次"为什么一直弹窗"之后查清：

### 判据不是"要不要提权"，而是"**路径**"
- 产品数据目录 `~/.workbuddy/` **默认放行** —— 实测 `init` / `add` / `stats` / `get` 全零弹窗
- 工作区之外的**其它**路径，任何写都要授权 —— 而图库「**只读也会写**」：
  - `MemoryGraph.__init__` 用 `open(lock, "w")` 建 `<db>.lock`
  - `MemoryGraph.close()` → Rust 侧**原子保存**（写 `.tmp` 再 rename 覆盖 `<db>`）
  - 而 **rename 覆盖在安全策略里被判成「删除」**（`audit-log` 里的事件是
    `file-safety.RequestDelete`）⇒ 同一个库文件被请求授权 **380 次**
  - 带 `dangerouslyDisableSandbox` 只是把弹窗换成一次点击，**根因没动**

### 所以别照抄"库放项目里"
- 放项目里**没有好处**：`.semantic-graph/` 本来就 gitignored，进不了版本控制
- 代价却是**每次读写弹一次窗**
- 放技能数据目录后：零弹窗、**不需要每个项目登记**、也不需要手配 `SE_SEMANTIC_DIR`

### 若确实需要动工作区外的文件（项目代码 / git / 引擎重建）
那是另一层（`sandbox.extraAllowWrite`，见 `settings.json`），且该数组由 Security Center
在**启动时 reconcile** 写入 —— 手工加可能被覆盖 ⇒ **要长期生效请在「安全中心」UI 里加**。

### 判据（别看"有没有弹窗"，看输出）
一次真实写 + **新进程回读**，命令里**不带** `dangerouslyDisableSandbox`：
输出里既无 `SANDBOX EXECUTION REJECTED`、也无 `⚠️ Sandbox bypassed`，
且 `close()` 不抛 `Io("Operation not permitted (os error 1)")` ⇒ 路径是放行的。
⚠️「新进程回读」是唯一真值 —— CLI 打印的成功行、`⚠️ Sandbox bypassed` 那行，都不算证据。

### 迁移已有库（库原本在项目里）
```bash
mkdir -p ~/.workbuddy/se-semantic-graph/<项目名小写>
cp <项目>/.semantic-graph/memory.axeb ~/.workbuddy/se-semantic-graph/<项目名小写>/
$PY $RUN stats     # 在项目根下跑，节点/边数应与迁移前一致
```

⚠️ **能走 `runner.py` 就别绕底层** `lobster-memory/tools/graph_crud.py`：绕底层的代价是
手拼路径、手写 bulk JSON（`content` 里的直引号会**静默炸整批**）、以及自己判断沙箱。
缺接口就补 runner —— `get` 就是这么补上来的。

### 🔴 读取端**静默丢字段**是最坏的一类"接口缺陷"（2026-09-19 实录）

`get` 补上来之后又踩了一次：`runner.py get` 只打 `summary`，而**大量节点的知识全在
`content` 里、`summary` 是空的**（例：`decision_grass_materials_13` 的 13 种材料表）。
用技能读到的是一具空壳 ⇒ 又只能绕回底层 `graph_crud get` ——
**用户抱怨的"你总绕开技能"有一半是这类接口缺陷造成的。**

根因在 `graph_api.get_node()`：它把字段**白名单**成 7 个
（id/label/type/summary/detail_ref/source/status），**`content` 不在其中**。
现在两处都改了：
- `graph_api.get_node()` → `return dict(v)`（**返回全部字段**，宁可多给）
- `runner.py get` → 默认打印 `content`（要元信息用 `--no-content`）

⚠️ 一般化：**读接口不要做字段白名单**。加一条边/加一个字段是进化的常态，
白名单会让"节点没写内容"和"读取端把它丢了"看起来一模一样。
自己写库的读函数时同理 —— 丢掉字段不报错，这才是它危险的地方。

## 节点类型（五域）

| 域 | 类型 | 说明 |
|---|---|---|
| 问题域 | `persona` 客户画像 | 谁在用、场景、痛点 |
| 问题域 | `requirement` 需求 | 功能/非功能、优先级、来源（**开放问题 / 待办也归这里**）|
| 问题域 | `cost` 成本约束 | 预算、时间线、ROI、为何不做更重的 |
| 问题域 | `business_rule` 业务规则 | 不可违背的领域约束（铁律 / 规约 / 方法论）|
| 方案域 | `architecture` 架构层 | 分层架构中的一层（接入/业务/领域/设施） |
| 方案域 | `module` 模块 | 职责边界、归属层 |
| 方案域 | `interface` 接口契约 | 对外服务定义 |
| 方案域 | `tech_stack` 技术栈 | 选型 |
| 实现域 | `runtime_logic` 运行逻辑 | 状态机、关键路径 |
| 实现域 | `data_flow` 数据流 | 输入输出、流转 |
| 实现域 | `data_model` 数据模型 | 实体关系 |
| 实现域 | `function` 函数锚点 | 被反复改动的重点函数 |
| 决策域 | `decision` 历史决策 ADR | 为何这么写 |
| 决策域 | `rejected` 被否方案 | 被否的替代方案（往往更值钱） |
| **证据域** | `fact` 实测事实 | 带数字/引用的「已核实」：实测值、资产记录、体检结果 |
| **证据域** | `case` 案例 | 发生过的事（事故 / 教训 / 修复记录），**规则引用它作为证据** |
| 结构 | `project_root` 图根锚点 | 只有一条，`graph_api.ROOT_ID` 指向它。**不是领域类型** |

### 🔴 什么时候**该**加类型、什么时候该归并（2026-09-19 批量整理后定）

判据一句话：**一个类型值得存在，当且仅当没有别的类型能在不丢区分的前提下覆盖它。**

- 该加（证据域就是这么来的）：`fact`（49 条）塞进 `runtime_logic` 会让「列出所有运行逻辑」
  返回一堆资产清单 —— **查询语义当场作废**；`case` 与 `business_rule` 是两件事
  （发生过的事 vs 以后要怎么做），且规则要靠案例作证据。
- 该归并（**只有 1~2 条、且明显是别的类型的近义写法**，一律不要新增）：
  实测一次整理把 8 种这样的类型并掉了 —— `open_q` / `open_question` / `todo` → `requirement`；
  `lesson` / `fix` / `change` → `case`；`method` → `business_rule`。
  ⚠️ 归并的收益不只是好看：类型多了之后**按类型查**这件事就废了。

## 跨域语义边（⚠️ 方向约定，勿反）

**所有边统一方向 = 问题域 → 实现域**（from 在上游，to 在下游）：

```
画像 → 需求 → 架构层 → 模块 → 运行逻辑 → 函数
  ↑drives   ↑mapped_to ↑part_of ↑implements ↑traced_to
成本/规则 → 需求（constrains）
决策 → 任意（affects）   决策 → 被否方案（rejects）
```

- **修 bug 反向追溯（为什么做）** = 沿边反向 = `trace --direction up`（原生 in_neighbors）
- **加功能正向展开（影响什么）** = 沿边正向 = `trace --direction down`（原生 out_neighbors）

反了方向（如 serves 写成 模块→需求）会导致追溯断链——录入时严格照此约定。

## 对话驱动工作流（核心，勿跳步）

**本技能不只是查询工具，它定义项目怎么推进。** 四个阶段严格顺序，每阶段结束必须用户确认，确认后才能进下一阶段。跳步 = 用假设替代用户真实意图 = 上下文爆炸的另一种形式。

```
阶段一 画像对话  →  阶段二 需求对话  →  阶段三 架构评审  →  阶段四 开发+实时录入
（用户确认画像）    （用户确认需求）    （用户确认架构）      （边写边录，修 bug 时 trace）
```

### 阶段一：画像对话（必须主动问，不猜）
- **向用户提问，不自行假设**：谁在用？什么场景？什么痛点？什么算"玩得好"？
- 问题示例：目标用户是谁 / 核心体验是什么 / 一个"爽"时刻 / 一个"崩溃"时刻 / 平台与分发
- 用户回答后录入 `persona` 节点，**展示给用户确认**后才算完成
- 完整提问脚手架见 `templates/onboarding-dialogue.md`

### 阶段二：需求对话（基于画像，逐条确认）
- 基于已确认画像，把玩法拆成需求，**逐条问用户**：这个功能是必须(M)/想要(W)/不做(N)？
- 区分功能需求与非功能需求（性能/平台/发布）
- **⚠️ 按项目类型的维度清单覆盖所有"不可避免"的需求维度**，不能只讨论机制/逻辑：
  - 每个维度至少问一遍（哪怕答案是"本轮不做"也要确认，不能跳过）
  - 例（游戏项目）：玩法机制 / 画面视觉 / 音乐音效 / 操作方式 / 手感 / UI与UX / 性能 / 平台兼容 / 发布分发
  - 维度清单见 `templates/requirement-dimensions.md`（含多类项目：游戏/Web/CLI/库/服务）
- 每条需求录入 `requirement` 节点，连 `drives`（画像→需求）
- 需求清单**展示给用户确认**，确认后不再自行增删
- 提问脚手架见 `templates/onboarding-dialogue.md`

### 阶段三：架构评审（设计方案给用户看，不直接写码）
- 基于已确认需求，产出：分层架构 / 模块划分 / 关键流程（状态机）/ 数据流
- **把设计画出来/写清楚给用户评审**（图或文字均可），用户拍板后才落图
- 录入 `architecture` / `module` / `runtime_logic` 节点 + `mapped_to` / `part_of` / `implements` 边
- 用户对设计的修改意见，作为 `decision` 节点记录
- 评审呈现脚手架见 `templates/onboarding-dialogue.md`

### 阶段四：开发 + 实时录入（架构确认后）
- 按确认的架构写码；写码/调试中**顺手**录入/更新语义节点（低成本、贴近现场）
- 关键调试教训（如"为什么不能用信号"）→ `decision` 节点
- 修 bug 前必查：`trace --start <定位点> --direction up` 拿"为什么"链
- 加功能前必查：`trace --start <需求> --direction down` 看影响面

### 跳步惩罚（写进意识）
- 跳过阶段一二 = 画像是猜的、需求是编的 → 架构评审没依据 → 开发出来不是用户要的
- 跳过阶段三 = 代码结构由手顺决定而非设计 → 模块边界模糊 → 语义图谱的模块节点变虚
- 用户说"直接做"时，至少把阶段一二的问题快速问一遍再动手（哪怕一句话确认）

## 使用惯例

### 什么时候录入（按工作流阶段，不脱离流程）
- **阶段一二三**：用户确认画像/需求/架构后，立即录对应节点（不等到开发）
- **阶段四**：龙虾写码/改码时，顺手把接触到的需求/模块/逻辑/决策按模板 `add` + `connect`
- 架构级决策、需求变更，由用户确认后落图（高质量、可观察）
- 不要等"文档完备"才录——边写边录，图库是活的 traceability

### 什么时候查询（修 bug 前必查）
1. 拿到报错栈，定位到函数/模块
2. `trace --start <id> --direction up --depth 4` → 拿"为什么"链（需求/画像/成本/决策）
3. 需要看影响面时 `trace --direction down` 或交给 LSP 查调用关系
4. **只把查到的字段级摘要带进 prompt，不塞全项目**

### 查询只输出差异
图库价值 = 边定向遍历 + 字段级提取 + 只输出差异。**禁止全量 dump 图库给模型**（图库不是存储桶）。查询结果就是"与本次任务相关的上下文子图"。

## 字段规范

每个节点只存摘要级字段，不存全文/源码：
- `id`：稳定标识符（英文/拼音，无空格）
- `label`：可读名称
- `type`：节点类型
- `summary`：一句话摘要（≤200 字，字段级提取的关键）
- `detail_ref`：详细文档/源码位置引用（不存全文）
- `source`：来源（需求文档/issue/PR/会议/对话）

## 与 lobster-memory 的关系

- **底层共用** axolotl 图库（axolotl_rs），但不共用图文件——lobster-memory 记对话记忆（`~/.workbuddy/lobster-memory/memory.axeb`），本技能记**项目语义**（每个项目一个 `SE_SEMANTIC_DIR`）
- 语义边方向约定是本技能特有的：问题域→实现域，使 up/down 天然对应 in/out
