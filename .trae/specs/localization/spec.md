# Localization Spec

## Why
The project target audience is Chinese-speaking. To improve user experience and model performance in the target language, all model prompts and debug outputs (console logs) should be localized to Chinese.

## What Changes
- **Model Prompts**: Translate all files in `src/prompts/` to Chinese.
- **Debug Outputs**: Update `src/agents/nodes.py` to use Chinese for `[THINKING]`, `[DECISION]`, and `[VALIDATION FAILED]` logs.
- **Status Messages**: Update `main.py` progress bar descriptions and logging messages to Chinese.

## Impact
- **Affected Code**: `src/agents/nodes.py`, `main.py`, `src/prompts/*.txt`.
- **Breaking Changes**: None. This is a localization update.

## ADDED Requirements

### Requirement: Chinese Prompts
All system prompts used by LLMs SHALL be in Chinese. This includes the Supervisor and Worker prompts.

### Requirement: Chinese Debug Logging
All console logs intended for user/developer visibility SHALL use Chinese labels and descriptions.
- `[THINKING]` -> `[思考中]`
- `[DECISION]` -> `[决策]`
- `[VALIDATION FAILED]` -> `[验证失败]`
- `Calling tool` -> `调用工具`
- `Processed X/Y tasks` -> `已处理 X/Y 个字段`

## MODIFIED Requirements
- **Prompt Files**: Translate content of `src/prompts/supervisor.txt` and `src/prompts/worker.txt`.
- **Node Logic**: Update logging strings in `field_supervisor_node`, `worker_node`, and `validator_node`.
- **Main Execution**: Update `tqdm` descriptions and final success messages in `main.py`.
