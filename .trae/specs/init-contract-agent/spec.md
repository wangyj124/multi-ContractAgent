# 合同智能处理系统 Spec

## Why
构建专为长合同（40页+，100k-150k Token）设计的智能处理系统，利用多模型协同（Supervisor, Worker, Retriever）实现极速提取与零幻觉目标。

## What Changes
- 初始化项目结构，配置 Python 3.11+ 环境与 `uv` 依赖管理。
- 实现基于 python-docx 的文档解析与逻辑感知切片（Archivist）。
- 实现基于 LangGraph 的多智能体编排（Supervisor, Worker, Retriever）。
- 集成 Qdrant 向量库用于语义检索。
- 实现基于 `XT.xlsx` 的任务初始化与 Schema 定义。
- 实现 ReAct 闭环协同与上下文校验逻辑。
- 实现符合 XT 兼容规范的 CSV 输出格式。

## Impact
- 新增功能：完整的合同解析与提取流程。
- 影响范围：项目根目录下的所有代码文件。

## ADDED Requirements

### Requirement: 技术栈与异构模型配置
- **环境**：Python 3.11+，使用 `uv` 管理依赖。
- **框架**：LangGraph (核心编排)、python-docx (解析)、qdrant-client (向量库)。
- **模型分工**：
    - Supervisor: qwen3-32B (8192 ctx)，负责规划、分发、逻辑判断。
    - Worker: qwen3-30B-A3B-Instruct (8192 ctx)，负责提取、摘要。
    - Retriever: qwen3-embedding-8B，负责向量化。

### Requirement: 第一阶段：逻辑文档树与感知分块 (Archivist)
- **正则层级识别**：识别章节编号（如：第X章、1.1、1.1.1），构建逻辑文档树。
- **逻辑切片**：以“条款/章节”为单位。超长条款按段落切分，500 Tokens 重叠。
- **元数据注入**：每个 Chunk 包含 path（章节路径）、type（文本/表格）、章节 summary。

### Requirement: 第二阶段：任务初始化 (Task Init)
- **业务对标**：解析 `XT.xlsx`。
- **Schema 驱动**：定义 `ContractInterpretation` Pydantic 模型，将 CSV “备注”作为字段描述。

### Requirement: 第三阶段：ReAct 闭环协同 (Master & Tools)
- **中枢思考**：Supervisor 阅读文档树与 XT 清单，输出规划。
- **双路检索**：
    - `Structural_Lookup`：按文档树 path 跳转。
    - `Semantic_Fallback`：向量检索兜底，按 path 聚合。
- **结果提取**：Worker 提取 `{value, evidence, clause_no}`。

### Requirement: 第四阶段：扩大上下文校验与空值保障 (Validation)
- **视野扩展**：Validator 调用工具回溯前后 1000 字上下文。
- **有据空值判定**：区分“原文留空”与“未找到”。
- **数理规则**：校验“金额守恒”与“日期顺序”。

### Requirement: 第五阶段：XT 兼容输出 (Formatter)
- **映射逻辑**：导出 CSV，列包括：序号 / 关注点 / 内容 / 合同描述 / 备注。
- **格式规范**：“合同描述”列拼合为 `{clause_no}: {原文证据}`。
