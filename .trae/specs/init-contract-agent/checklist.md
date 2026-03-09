# Checklist

- [x] 项目环境 (uv, python 3.11+) 配置正确，依赖安装无误
- [x] 文档解析 (python-docx) 能正确识别章节层级
- [x] 逻辑切片 (Archivist) 生成的 Chunk 包含正确元数据 (path, type)
- [x] 向量库 (Qdrant) 能够正确索引和检索 Chunk
- [x] XT.xlsx 解析正确，能够生成 Pydantic Schema
- [x] Supervisor 能够根据文档树规划任务
- [x] Structural_Lookup 工具能准确跳转章节
- [x] Semantic_Fallback 工具能进行语义检索兜底
- [x] Worker 能够提取 {value, evidence, clause_no}
- [x] Validator 能够回溯上下文并校验逻辑 (金额, 日期)
- [x] 空值判定逻辑正确 (原文留空 vs 未找到)
- [x] CSV 输出格式符合规范，包含所有必要字段
