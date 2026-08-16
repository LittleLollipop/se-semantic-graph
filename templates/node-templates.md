# 语义节点录入模板（复制追加）

> 用法：每个项目在自己的 `SE_SEMANTIC_DIR` 下建一个 `templates/` 目录，
> 录新节点时复制对应模板，填好字段后按字段逐个 `runner.py add`。
> 然后按「方向约定」用 `runner.py connect` 连接跨域语义边。

## 方向约定（再强调，勿反）

```
画像 → 需求 → 架构层 → 模块 → 运行逻辑 → 函数
  ↑drives   ↑mapped_to ↑part_of ↑implements ↑traced_to
成本/规则 → 需求（constrains）   决策 → 任意（affects）
```

修 bug 追溯=沿边反向（up），加功能展开=沿边正向（down）。

---

## persona（客户画像）

```bash
add --id persona_<标识> --label "<画像名>" --type persona \
    --summary "<谁在用 · 场景 · 痛点（≤200字）>" --source "<客户访谈/问卷>"
```

## requirement（需求）

```bash
add --id req_<编号> --label "<需求名>" --type requirement \
    --summary "<功能/非功能 · 优先级 · 验收要点>" --source "<需求文档 R-XX>"
```

## cost（成本约束）

```bash
add --id cost_<标识> --label "<成本约束名>" --type cost \
    --summary "<预算/时间线/ROI/为何不做更重方案>" --source "<立项评审>"
```

## architecture（架构层）

```bash
add --id arch_<层名> --label "<层名>" --type architecture \
    --summary "<该层职责 · 在分层架构中的位置>"
```

## module（模块）

```bash
add --id mod_<模块名> --label "<模块名> 模块" --type module \
    --summary "<职责边界 · 关键能力>"
```

## runtime_logic（模块运行逻辑）

```bash
add --id logic_<标识> --label "<运行逻辑名>" --type runtime_logic \
    --summary "<状态机/关键路径/处理链>"
```

## function（函数锚点，只挂重点）

```bash
add --id fn_<函数名> --label "<函数名>()" --type function \
    --summary "<职责 · 入口/校验点>" --detail-ref "<文件:行>"
```

## decision（历史决策 ADR）

```bash
add --id decision_<标识> --label "决策：<主题>" --type decision \
    --summary "<选了什么 · 权衡 · 牺牲了什么>" --source "<ADR/评审>"
```

## rejected（被否方案）

```bash
add --id rejected_<标识> --label "被否：<方案名>" --type rejected \
    --summary "<为什么被否 · 否定的理由>" --source "<ADR>"
```

---

## 连接语义边（方向约定）

```bash
connect --from persona_x     --to req_y       --kind drives       # 画像驱动需求
connect --from cost_x        --to req_y       --kind constrains   # 成本约束需求
connect --from req_y         --to arch_layer  --kind mapped_to    # 需求映射到层
connect --from arch_layer    --to mod_z       --kind part_of      # 层包含模块
connect --from req_y         --to mod_z       --kind serves       # 需求由模块服务
connect --from mod_z         --to logic_w     --kind implements   # 模块实现逻辑
connect --from logic_w       --to fn_f        --kind traced_to    # 逻辑对应函数
connect --from decision_d    --to <任意>       --kind affects     # 决策影响
connect --from decision_d    --to rejected_r  --kind rejects     # 决策否决方案
connect --from mod_a         --to mod_b       --kind depends_on   # 模块依赖
```

## 标准查询

```bash
# 修 bug：从报错函数反向追溯为什么
trace --start fn_f --direction up --depth 4 --verbose

# 加功能：从需求正向展开影响面
trace --start req_y --direction down --depth 4 --verbose

# 重构：从模块看上下层
trace --start mod_z --direction both --depth 3
```
