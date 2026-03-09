# Tasks

- [x] Task 1: 项目环境初始化
  - [x] SubTask 1.1: 初始化 uv 项目，配置 Python 3.11+ 环境
  - [x] SubTask 1.2: 添加核心依赖 (langgraph, python-docx, qdrant-client, pandas, pydantic, langchain, langsmith 等)
  - [x] SubTask 1.3: 创建项目基础目录结构 (src/core, src/agents, src/tools, src/utils, data/input, data/output)

- [x] Task 2: 第一阶段 - 文档解析与切片 (Archivist)
  - [x] SubTask 2.1: 实现 DocxLoader，解析 Word 文档结构
  - [x] SubTask 2.2: 实现逻辑层级识别 (Regex Hierarchy)
  - [x] SubTask 2.3: 实现逻辑切片策略 (Chunking Strategy) 与重叠处理
  - [x] SubTask 2.4: 实现元数据注入 (Path, Type, Summary) 与向量化索引 (Retriever)

- [x] Task 3: 第二阶段 - 任务初始化 (Task Init)
  - [x] SubTask 3.1: 实现 XTParser，读取 `XT.xlsx`
  - [x] SubTask 3.2: 动态生成 ContractInterpretation Pydantic 模型 (Schema Generation)

- [x] Task 4: 第三阶段 - ReAct 闭环协同 (Core Engine)
  - [x] SubTask 4.1: 定义 Supervisor Agent (32B) 与状态图 (StateGraph)
  - [x] SubTask 4.2: 实现 Structural_Lookup 工具
  - [x] SubTask 4.3: 实现 Semantic_Fallback 工具
  - [x] SubTask 4.4: 定义 Worker Agent (30B) 用于提取与摘要

- [x] Task 5: 第四阶段 - 校验与空值保障 (Validation)
  - [x] SubTask 5.1: 定义 Validator Agent (32B)
  - [x] SubTask 5.2: 实现上下文回溯工具 (Context Retrieval)
  - [x] SubTask 5.3: 实现数理规则校验 (金额守恒, 日期顺序)

- [x] Task 6: 第五阶段 - 输出格式化 (Formatter)
  - [x] SubTask 6.1: 实现结果聚合与 CSV 导出逻辑
  - [x] SubTask 6.2: 格式化 "合同描述" 字段

- [x] Task 7: 集成测试与验证
  - [x] SubTask 7.1: 编写主程序入口 (main.py)
  - [x] SubTask 7.2: 运行完整流程测试
