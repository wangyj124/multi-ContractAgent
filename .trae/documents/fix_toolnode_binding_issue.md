# 修复 Agent 调用检索工具失效的方案

## 摘要
本方案旨在解决执行 `uv run python main.py` 时，`structural_lookup` 等工具在被 Agent 实际调用时无法找到有效内容，但在独立脚本中却能正常工作的问题。根本原因是由于 Python 的模块导入机制导致 LangGraph 的 `ToolNode` 绑定了旧的（未注入数据的）工具实例。

## 当前状态分析
1. **依赖注入时机问题**：在 `main.py` 中，程序实例化了真正的 `Retriever` 并建立了文档索引，随后通过 `src.agents.nodes.tools = _lookup_tools.get_tools()` 进行依赖注入。
2. **模块早期绑定**：在 `src/core/subgraph.py` 中，使用了 `from src.agents.nodes import tools`。这种导入方式会在模块加载时立即获取 `tools` 列表。此时，`tools` 仍然绑定着初始化的那个空的、未建立索引的 `_retriever`。
3. **工具执行失败**：当 LangGraph 执行 `ToolNode` 时，它使用的是导入时绑定的旧工具。因此，无论实际建立的索引有多完善，`ToolNode` 始终在一个空的内存数据库中查询，必然返回“未找到”，进而导致 Agent 认为工具未能获取有效内容并陷入不断重试的死循环。

## 拟议的更改

### 1. 修改 `src/core/subgraph.py`
- **What**: 改变 `tools` 的引用方式，使其在创建图的时刻动态读取注入后的最新 `tools`。
- **Why**: 确保 `ToolNode` 使用的工具实例是经过 `main.py` 依赖注入后带有真实数据的实例。
- **How**: 
  ```python
  # 修改前
  from src.agents.nodes import field_supervisor_node, worker_node, validator_node, tools
  
  # ...
  workflow.add_node("tools", ToolNode(tools, messages_key="field_messages"))
  
  # 修改后
  from src.agents.nodes import field_supervisor_node, worker_node, validator_node
  import src.agents.nodes as nodes
  
  # ...
  workflow.add_node("tools", ToolNode(nodes.tools, messages_key="field_messages"))
  ```
*(注：上述修改已在此前的探索阶段通过工具完成应用)*

### 2. 测试配置优化（仅为减少测试耗时）
- **What**: 在 `main.py` 中针对 `--tasks` 参数的处理逻辑后，临时截取任务列表为 1 个任务（或执行时通过其他方式截取）。
- **Why**: 用户建议“测试可只用一个任务来对测试问题，减少测试耗时”。
- **How**: 在 `main.py` 中添加逻辑限制 `task_list = task_list[:1]`。

## 假设与决策
- 假设底层检索工具本身的逻辑（如 `search_by_path`）没有问题，问题仅出在对象引用上（已通过独立脚本验证证实了底层工具能正确查出 140 字的合同封面内容）。
- 决定使用动态模块属性引用（`nodes.tools`）来解决 Python 的绑定闭包问题，这是最直接且不破坏现有架构的方法。

## 验证步骤
1. 修改 `main.py` 使其只执行第一个任务（如“合同编号”或“签署日期”）。
2. 执行测试指令：`uv run python main.py --doc "data/input/甘露机岛合同-20181211版最终-签字版（无价格版）.docx" --tasks "data/input/XT.xlsx"`。
3. 观察控制台日志，确认 `[Field Supervisor] 决策: 工具执行完毕且有内容，转交 Worker 进行提取` 是否出现。
4. 确认最终输出中该单个任务被正确提取。