#!/usr/bin/env python3
"""se-semantic-graph runner — 软件工程语义图谱 CLI。

把软件工程全知识域（客户画像/需求/成本/架构/分层/模块/运行逻辑/历史决策）
落进 axolotl 图库，支持：
- init: 初始化项目图
- add: 录入语义节点（字段级摘要）
- connect: 加跨域语义边（正反成对，双向可遍历）
- trace: 定向遍历查询（修 bug/加功能/重构时取精确上下文）
- list: 列出节点
- stats: 统计
- get: 读一个节点（含正文）
- doctor: 图库体检（枚举完整性 / 类型越界 / 重边 / id 污染）

用法示例见 SKILL.md。所有路径可经环境变量覆盖：
  SE_SEMANTIC_ENGINE  引擎目录（默认 ~/.workbuddy/skills/lobster-memory）
  SE_SEMANTIC_DIR     图文件目录（默认 ~/.workbuddy/se-semantic-graph）
"""
import argparse
import collections
import json
import os
import sys

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if _SKILL_DIR not in sys.path:
    sys.path.insert(0, _SKILL_DIR)

from graph_api import SEManticGraph, DEFAULT_GRAPH_FILE, ROOT_ID  # noqa: E402
from schema import NODE_TYPES, EDGE_KINDS  # noqa: E402

## 引擎自带的只读枚举工具（`all_nodes` / `all_edges`）。
## 🔴 直接复用它，**不要自己再写一份 BFS** —— 引擎没有「列出全部顶点」的 API，
##    `graph_crud._all_vertex_ids` 是「root 双向 BFS + pagerank 二次播种」才凑齐的，
##    重写一份必然与它产生口径差异（体检工具的口径不一，比没有体检更糟）。
_TOOLS = os.path.join(
    os.environ.get("SE_SEMANTIC_ENGINE",
                   os.path.expanduser("~/.workbuddy/skills/lobster-memory")),
    "tools",
)
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

## ── 库目录解析（2026-09-19 改）
##
## 🔴 **不要把库放进项目目录，也不要每次手配 `SE_SEMANTIC_DIR`。**
##
## 库放项目里 = 每次读写都触发「工作区外删除保护」的授权弹窗：
## 引擎 `close()` 是**原子保存**（写 `<db>.tmp` 再 rename 覆盖原文件），
## 而 rename 覆盖在安全策略里被判成**删除** ⇒ 每次操作弹一次。
## 实测：同一个库文件被请求授权 **380 次**（`~/.workbuddy/audit-log/*.jsonl`
## 的 `file-safety.RequestDelete`）。
##
## 而 `~/.workbuddy/` 是产品数据目录、**默认放行** ⇒ 库放这里零弹窗（已实测）。
## 这也正是本技能 `SE_SEMANTIC_DIR` 的默认值 —— 一开始就该用这里。
DEFAULT_ROOT = os.path.expanduser("~/.workbuddy/se-semantic-graph")

## 项目根的常见标记。用途只有一个：**在 cwd 不像项目时提醒一声** ——
## 否则"按当前目录名推导"会在错误的位置静默建一个新库（症状是"我的节点不见了"）。
_PROJECT_MARKERS = (".git", "project.godot", "package.json", "pyproject.toml",
                    "go.mod", "Cargo.toml", "pom.xml", "build.gradle")


def _looks_like_project(d: str) -> bool:
    return any(os.path.exists(os.path.join(d, m)) for m in _PROJECT_MARKERS)


def resolve_graph_dir(project: str = None) -> str:
    """库目录：`SE_SEMANTIC_DIR` > `<DEFAULT_ROOT>/<项目名小写>`。

    `project` 缺省用当前工作目录 ⇒ **在项目根目录下调用时无需任何配置**。
    每个项目一个子目录，互不干扰，也不必逐个登记。
    """
    env = os.environ.get("SE_SEMANTIC_DIR")
    if env:
        return env
    src = os.path.abspath(project or os.getcwd())
    if project is None and not _looks_like_project(src):
        sys.stderr.write(
            "[se-semantic-graph] ⚠️ %s 不像项目根（没找到 %s）—— 库目录仍按它的名字推导。"
            "要指定别的目录用 `--project <dir>`（写在子命令前）或环境变量 SE_SEMANTIC_DIR。\n"
            % (src, "/".join(_PROJECT_MARKERS[:4])))
    slug = os.path.basename(src).lower().replace(" ", "-")
    return os.path.join(DEFAULT_ROOT, slug)


def _graph(project: str = None):
    d = resolve_graph_dir(project)
    os.makedirs(d, exist_ok=True)
    return SEManticGraph(os.path.join(d, DEFAULT_GRAPH_FILE))


def cmd_init(args):
    g = _graph(getattr(args, "project", None))
    try:
        st = g.stats()
        g.close()
    except Exception as e:
        sys.stderr.write(f"[se-semantic-graph] init 失败: {e}\n")
        sys.exit(1)
    print(f"已初始化项目语义图谱: {resolve_graph_dir(getattr(args, 'project', None))}")
    print(f"  当前: {st['vertices']} 节点 | {st['edges']} 边")


def cmd_add(args):
    g = _graph(getattr(args, "project", None))
    try:
        r = g.upsert_node(
            id_str=args.id,
            label=args.label,
            node_type=args.type,
            summary=args.summary or "",
            detail_ref=args.detail_ref or "",
            source=args.source or "",
        )
        g.close()
    except Exception as e:
        sys.stderr.write(f"[se-semantic-graph] add 失败（未落盘）: {e}\n")
        sys.exit(1)
    print(f"节点已写入: {r['id']} ({r['type']}) {r['label']}")


def cmd_connect(args):
    g = _graph(getattr(args, "project", None))
    try:
        r = g.connect(args.from_id, args.to_id, args.kind, note=args.note or "")
        g.close()
    except Exception as e:
        sys.stderr.write(f"[se-semantic-graph] connect 失败（未落盘）: {e}\n")
        sys.exit(1)
    print(f"边已建立: {r['from']} --{r['kind']}--> {r['to']} [{r['status']}]")


def cmd_trace(args):
    g = _graph(getattr(args, "project", None))
    try:
        r = g.trace(
            start_id=args.start,
            direction=args.direction,
            max_depth=args.depth,
            max_results=args.limit,
            kind_filter=args.kind,
            node_type_filter=args.type,
        )
        g.close()
    except Exception as e:
        sys.stderr.write(f"[se-semantic-graph] trace 失败: {e}\n")
        sys.exit(1)

    if "error" in r:
        print(r["error"])
        sys.exit(1)

    print(f"[追踪] 起点: {r['start']} | 方向: {r['direction']} | 命中 {r['total_nodes']} 节点")
    for n in r["nodes"]:
        depth = n.get("depth", 0)
        indent = "  " * depth
        summ = n.get("summary", "")
        summ = summ[:60] + ("…" if len(summ) > 60 else "")
        print(f"{indent}- [{n.get('type')}] {n.get('label')}"
              + (f" | {summ}" if summ else ""))
    if r["paths"] and args.verbose:
        print("\n[路径]")
        for (d, frm, to, kind) in r["paths"]:
            print(f"  {'  ' * d}{frm} --{kind}--> {to}")


def cmd_get(args):
    """读一个节点的字段 + 出/入边。

    ⚠️ 这个子命令是 2026-09-19 补的：在那之前 runner 只有 `list` / `trace`，
    "读单个节点"没有入口 ⇒ 每次都得绕到底层 `graph_crud.py get --db <路径>`，
    于是又得手拼路径、又要自己判断沙箱。**能走技能就别绕底层。**
    （实现用的是 `graph_api.SEManticGraph.get_node` —— 它一直在，只是没暴露。）

    🔴 2026-09-19 二次修正：**默认打印 `content`**。第一版只打 `summary`，
    而很多节点的 `summary` 是空的（知识全在 `content` 里 —— 例如
    `decision_grass_materials_13` 的 13 种材料表）⇒ 用技能读等于读了个空壳，
    于是又得绕回底层 `graph_crud get`。**"用技能读不到正文"是接口缺陷，
    不是使用者的姿势问题。** 只要元信息时用 `--no-content`。
    """
    g = _graph(getattr(args, "project", None))
    try:
        n = g.get_node(args.id)
        r = g.trace(start_id=args.id, direction="both", max_depth=1) if n else {}
        g.close()
    except Exception as e:
        sys.stderr.write(f"[se-semantic-graph] get 失败: {e}\n")
        sys.exit(1)
    if not n:
        print(f"节点不存在: {args.id}")
        sys.exit(1)
    print(f"id: {n.get('id')}")
    print(f"label: {n.get('label')}")
    print(f"type: {n.get('type')} | domain: {n.get('domain')} | "
          f"weight: {n.get('weight')} | status: {n.get('status')}")
    for k in ("summary", "detail_ref", "source"):
        if n.get(k):
            print(f"{k}: {n[k]}")
    if not getattr(args, "no_content", False):
        c = (n.get("content") or "").strip()
        print("content:" if c else "content: （空）")
        if c:
            print(c)
    outs, ins = [], []
    for path in r.get("paths", []):
        _d, frm, to, kind = path
        if frm == args.id:
            outs.append(f"  -> {to} [{kind}]")
        elif to == args.id:
            ins.append(f"  <- {frm} [{kind}]")
    print("出边:")
    for x in outs:
        print(x)
    print("入边:")
    for x in ins:
        print(x)


def cmd_doctor(args):
    """图库体检：**一条命令**回答「这个库还健康吗」。

    🔴 存在的理由（2026-09-19 实证，SerpentSurge 项目图库）：
    该库 422 个节点里有 **163 个（39%）** `stats` / `list` / `trace` **根本看不到** ——
    因为 `runner.py add` 会自动连根（`upsert_node` 末尾补 `ROOT_ID --has_member--> 新节点`），
    而作者们常用的 `graph_crud bulk` **不会**。症状是"我明明写过这个节点，它却没出现"，
    而**没有任何一处会报错** —— 正是最该被一条命令拦住的那种问题。

    四项检查（任一有问题 ⇒ exit 1，可以直接当门禁跑）：

      ① **枚举完整性**：live 节点里有多少不在 walk 范围内（= 写了但看不见）
      ② **类型越界**：`type` 不在 `schema.NODE_TYPES` 里（按类型统计/过滤会漏掉它）
      ③ **重边**：同一 (src,dst) 出现 >1 次（引擎 raw add_edge 会偶发产出平行边）
      ④ **id 污染**：`props['id']` 变成纯数字（症状：get 入边为空、list --prefix 漏检）

    ⚠️ 修法各不同，别混：
      ① 补 `edge_add {from: ROOT_ID, to: <id>, kind: has_member}`（就这一条边的事）
      ② 改名（`upsert` 带新 type；**content 要传原 content**，别传 node_body ——
         本项目 62% 的节点正文在 `summary` 里，传 node_body 会造出重复正文）
      ③ `edge_rm` 再 `edge_add`（`edge_rm` 会删光该点对的全部副本，所以 rm+add = 去重）
      ④ 见 `graph_crud check-ids`
    """
    try:
        import graph_crud as GC
    except ImportError as e:
        sys.stderr.write(f"[se-semantic-graph] doctor 需要引擎工具目录：{_TOOLS}\n  {e}\n")
        sys.exit(2)
    sg = _graph(getattr(args, "project", None))
    nodes = GC.all_nodes(sg._g._g)
    edges = GC.all_edges(sg._g._g)
    reach = set(sg._iter_all_vertices().keys()) | {ROOT_ID}
    sg.close()

    problems = 0
    print(f"[图库体检] 节点 {len(nodes)} ｜ 边 {len(edges)}")

    # ① 枚举完整性（`lobster_root` = 引擎自建的**全局**根，不是本项目节点，
    #    把它挂到项目根下是错的 ⇒ 与 ② 一样单独放过）
    unreach = sorted(i for i in nodes
                     if i not in reach and i != "lobster_root"
                     and (nodes[i].get("status") or "live") == "live")
    if unreach:
        problems += 1
        print(f"❌ ① 枚举完整性：{len(unreach)} 个 **live** 节点不在 walk 范围内"
              "（它们不会被 stats/list/trace 看到）")
        print(f"   样例：{unreach[:8]}")
        print(f"   修：补 `edge_add {{from: {ROOT_ID}, to: <id>, kind: has_member}}`")
    else:
        print("✅ ① 枚举完整性：所有 live 节点都可达")

    # ② 类型越界（`lobster_root` 是引擎自建根，不属于本项目，单独放过）
    off = collections.Counter(
        d.get("type") for i, d in nodes.items()
        if i != "lobster_root" and d.get("type") not in NODE_TYPES
    )
    if off:
        problems += 1
        print(f"❌ ② 类型越界：{len(off)} 种不在 schema 里 —— "
              + "、".join(f"{t}×{c}" for t, c in off.most_common()))
        print("   修：改名到 schema 内（见 SKILL.md 的「类型越界怎么收」）")
    else:
        print(f"✅ ② 类型越界：全部在 schema 的 {len(NODE_TYPES)} 种内")

    # ③ 重边
    dup = collections.Counter((e[0], e[1]) for e in edges)
    dup = {k: v for k, v in dup.items() if v > 1}
    if dup:
        problems += 1
        print(f"❌ ③ 重边：{len(dup)} 组（引擎 raw add_edge 的已知 quirk）")
        for (a, b), c in list(dup.items())[:5]:
            print(f"   {a} -> {b} ×{c}")
        print("   修：对每对先 `edge_rm` 再 `edge_add`（rm 会删光全部副本 ⇒ 净剩 1 条）")
    else:
        print("✅ ③ 重边：无平行重复边")

    # ④ id 污染
    bad_id = [i for i, d in nodes.items()
              if str(d.get("id") or "").isdigit()]
    if bad_id:
        problems += 1
        print(f"❌ ④ id 污染：{len(bad_id)} 个节点的 props['id'] 是纯数字：{bad_id[:5]}")
    else:
        print("✅ ④ id 污染：无")

    print(f"\nDOCTOR {'✅ 健康' if problems == 0 else f'❌ {problems} 类问题'}")
    sys.exit(1 if problems else 0)


def cmd_list(args):
    g = _graph(getattr(args, "project", None))
    try:
        nodes = g.list_nodes(node_type=args.type, limit=args.limit)
        g.close()
    except Exception as e:
        sys.stderr.write(f"[se-semantic-graph] list 失败: {e}\n")
        sys.exit(1)
    print(f"[节点清单] {len(nodes)} 条")
    for n in nodes:
        summ = (n.get("summary") or "")[:50]
        print(f"- [{n.get('type')}] {n.get('id')} | {n.get('label')}"
              + (f" | {summ}" if summ else ""))


def cmd_stats(args):
    g = _graph(getattr(args, "project", None))
    try:
        st = g.stats()
        g.close()
    except Exception as e:
        sys.stderr.write(f"[se-semantic-graph] stats 失败: {e}\n")
        sys.exit(1)
    print(f"[图谱统计] 节点 {st['vertices']} | 边 {st['edges']} | 文件 {st['path']}")
    if st["by_type"]:
        print("[按类型]")
        for t, c in sorted(st["by_type"].items(), key=lambda x: -x[1]):
            print(f"  {NODE_TYPES.get(t, t)} ({t}): {c}")


def cmd_types(args):
    print("[节点类型]")
    for t, zh in NODE_TYPES.items():
        print(f"  {t} = {zh}")
    print("\n[边类型]")
    for k, zh in EDGE_KINDS.items():
        print(f"  {k} = {zh}")


def main():
    p = argparse.ArgumentParser(
        description="软件工程语义图谱 CLI",
        epilog="库目录默认 = ~/.workbuddy/se-semantic-graph/<当前目录名小写>（产品数据目录，"
               "零弹窗）。可用环境变量 SE_SEMANTIC_DIR 覆盖；--project 需写在子命令**之前**。",
    )
    p.add_argument("--project", default=None,
                   help="项目目录（缺省 = 当前工作目录；库目录按它的名字推导）")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="初始化项目图")
    sp.set_defaults(fn=cmd_init)

    sp = sub.add_parser("add", help="录入语义节点")
    sp.add_argument("--id", required=True, help="稳定标识符（英文/拼音，无空格）")
    sp.add_argument("--label", required=True, help="可读名称")
    sp.add_argument("--type", required=True, choices=NODE_TYPES.keys(), help="节点类型")
    sp.add_argument("--summary", default="", help="一句话摘要（≤200字）")
    sp.add_argument("--detail-ref", default="", help="详细文档/源码位置引用")
    sp.add_argument("--source", default="", help="来源（需求文档/issue/PR/会议）")
    sp.set_defaults(fn=cmd_add)

    sp = sub.add_parser("connect", help="加跨域语义边")
    sp.add_argument("--from", dest="from_id", required=True)
    sp.add_argument("--to", dest="to_id", required=True)
    sp.add_argument("--kind", required=True, choices=EDGE_KINDS.keys())
    sp.add_argument("--note", default="")
    sp.set_defaults(fn=cmd_connect)

    sp = sub.add_parser("trace", help="定向遍历查询（核心）")
    sp.add_argument("--start", required=True, help="起点节点 id")
    sp.add_argument("--direction", default="up", choices=["up", "down", "both"],
                    help="up=反向追溯(为什么做) down=正向展开(影响什么) both=双向")
    sp.add_argument("--depth", type=int, default=4)
    sp.add_argument("--limit", type=int, default=50)
    sp.add_argument("--kind", default=None, help="只走指定边类型")
    sp.add_argument("--type", dest="type", default=None, help="只保留指定节点类型")
    sp.add_argument("--verbose", action="store_true", help="显示完整路径")
    sp.set_defaults(fn=cmd_trace)

    sp = sub.add_parser("get", help="读一个节点 + 正文 + 出/入边")
    sp.add_argument("--id", required=True, help="节点 id")
    sp.add_argument("--no-content", action="store_true",
                    help="只打元信息，不打正文（默认打正文 —— 很多节点的知识全在 content 里）")
    sp.set_defaults(fn=cmd_get)

    sp = sub.add_parser("doctor", help="图库体检（枚举完整性/类型越界/重边/id 污染）")
    sp.set_defaults(fn=cmd_doctor)

    sp = sub.add_parser("list", help="列出节点")
    sp.add_argument("--type", default=None, choices=list(NODE_TYPES) + [None])
    sp.add_argument("--limit", type=int, default=500)
    sp.set_defaults(fn=cmd_list)

    sp = sub.add_parser("stats", help="图谱统计")
    sp.set_defaults(fn=cmd_stats)

    sp = sub.add_parser("types", help="列出节点/边类型")
    sp.set_defaults(fn=cmd_types)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
