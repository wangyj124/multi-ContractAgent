# 修复 Agent 无法找到文本内容的方案

## 摘要
本方案旨在解决执行 `uv run python main.py` 时，Agent 在调用工具寻找文本内容时总是返回“未找到相关内容”的问题。根本原因是由于 `Retriever` 初始化时未指定嵌入模型（Embedding Model），导致系统默认使用了基于哈希的 `mock`（伪造）向量生成策略，从而使得语义检索（Semantic Search）返回随机且无关的文档块，最终被 LLM 重排序（Rerank）过滤掉。

## 当前状态分析
1. **未指定模型导致默认使用 mock 嵌入**：在 `main.py` 和 `src/agents/nodes.py` 中实例化 `Retriever` 时，没有从环境变量（如 `MODEL_EMBEDDING`）中读取并传入 `embedding_model` 参数，导致其默认使用 `"mock"`。
2. **Mock 嵌入的随机性**：在 `Retriever._get_embedding` 方法中，当模型为 `"mock"` 时，生成的向量是基于文本哈希的确定性随机向量。
3. **检索流程失效**：因为查询文本与文档块文本不同，它们的哈希值不同，生成的随机向量计算余弦相似度时毫无关联。向量检索返回了不相关的结果。
4. **LLM 过滤**：后续在 `Retriever.search` 和 `LookupToolSet._rerank_results` 中使用了 LLM 对这些不相关的结果进行相关性打分，因为结果确实不相关，打分低于 7，导致所有候选结果被过滤，最终返回“重排序后未找到相关内容”。

## 拟议的更改

### 1. 修改 `main.py`
- **What**: 在实例化 `Archivist` 和 `Retriever` 之前，从环境变量读取 `MODEL_EMBEDDING`。
- **Why**: 确保主程序入口能够正确加载并在建立索引和检索时使用真实的嵌入模型（如 `qwen3-embedding-8B`）。
- **How**: 
  ```python
  # 修改前
  archivist = Archivist()
  retriever = Retriever(location=":memory:", collection_name="contract_chunks")
  
  # 修改后
  embedding_model = os.environ.get("MODEL_EMBEDDING", "qwen3-embedding-8B")
  archivist = Archivist(embedding_model_name=embedding_model)
  retriever = Retriever(location=":memory:", collection_name="contract_chunks", embedding_model=embedding_model)
  ```

### 2. 修改 `src/agents/nodes.py`
- **What**: 更新全局默认的 `_retriever` 实例化逻辑。
- **Why**: 尽管 `main.py` 中进行了依赖注入覆盖了该实例，但为了保证模块的独立运行不抛出同样问题，应该将该处的初始化也修正为读取环境变量。
- **How**:
  ```python
  # 修改前
  _retriever = Retriever(location=":memory:", collection_name="contract_chunks")
  
  # 修改后
  _embedding_model = os.environ.get("MODEL_EMBEDDING", "qwen3-embedding-8B")
  _retriever = Retriever(location=":memory:", collection_name="contract_chunks", embedding_model=_embedding_model)
  ```

## 假设与决策
- 假设环境中的 `.env` 文件已正确配置 `MODEL_EMBEDDING=qwen3-embedding-8B` 以及对应的 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`。
- 假设项目中已安装 `langchain_openai` 依赖（已通过命令验证）。
- 决定仅在入口和关键模块注入配置，不对 `Retriever` 的底层 fallback（降级为 mock）逻辑做破坏性修改，以保持测试代码的兼容性。

## 验证步骤
1. 执行原始任务指令：`uv run python main.py --doc "data/input/甘露机岛合同-20181211版最终-签字版（无价格版）.docx" --tasks "data/input/XT.xlsx"`。
2. 观察控制台输出，确认在 `[索引] 建立向量索引...` 阶段成功连接 Embedding 服务，未报错。
3. 观察 Agent 检索时的工具调用输出，确认不再总是返回“未找到相关内容”，而是返回包含相关上下文的文本块。
4. 验证最终提取结果表格中各字段能够成功提取出对应信息。
