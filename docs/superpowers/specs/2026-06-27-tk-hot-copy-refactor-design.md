# TK 爆款复刻 - 架构重构设计文档

> 日期: 2026-06-27 · 状态: 待实施

## 1. 背景与目标

**当前状态**: tk-hot-copy 是一个 PyQt6 桌面应用，6 步线性 pipeline（TTS分离 → 文案改写 → 镜头匹配 → 音频生成 → 视频拼接 → 剪映草稿），流程可通但体验不适合对外发布。

**目标**: 重构为可对外发布的消费级产品，核心体验对标 ComfyUI——节点式画布、可视化流水线、每个步骤可调试可重跑。

**四个核心 UX 问题及对应方案**:

| 问题 | 方案 |
|------|------|
| A. 设置太复杂 | 全局只存 API Key，每节点自己管理参数 |
| B. 看不到进展 | 节点图实时显示状态+进度，WebSocket 推送 |
| C. 不好调试 | 每个节点产物单独预览，可单独调参重跑 |
| D. 太技术化 | React 现代 UI，模板驱动快速上手 |

## 2. 技术栈

| 层 | 技术 | 理由 |
|----|------|------|
| 前端 | React 18 + React Flow + Tailwind CSS + Zustand | React Flow 是成熟的节点图库，开箱即用 |
| 后端 | FastAPI + WebSocket | 轻量 Python web 框架，原生 async 支持 |
| Pipeline SDK | 纯 Python (app/pipeline/) | 无外部依赖，可独立测试 |
| 持久化 | SQLite | 轻量，无需额外服务 |
| 桌面打包 | PyWebView | 约 30MB，远轻于 Electron |
| 外部工具 | ffmpeg, whisper-cli, demucs | 保持不变 |

## 3. Pipeline SDK 设计

### 3.1 核心概念

```
Node ──Edge──▶ Node ──Edge──▶ Node
  │                              │
  └── params                    └── outputs (cached)
       inputs                         │
                                 preview (缩略图)
```

**Node**: 最小执行单元。声明式接口——inputs/outputs/params 都有 schema，run() 是纯函数逻辑，产物自动缓存。

**Edge**: 有向边。source_node.output_port → target_node.input_port。隐含依赖关系和类型约束。

**Graph**: 节点 + 连线的集合。可序列化为 JSON。模板本质就是一个预连好的 Graph JSON。

**Executor**: 接收 Graph，拓扑排序，逐个执行 Node，处理缓存和错误，通过回调上报进度。

### 3.2 Node 基类

```python
class Node:
    id: str
    type: str        # 节点类型标识，如 "TTSExtract"
    label: str       # 画布上显示的名字
    x, y: float      # 画布位置

    # 端口定义（声明式）
    inputs: dict[str, PortSpec]    # 输入端口 → 类型约束
    outputs: dict[str, PortSpec]   # 输出端口 → 类型约束
    params: dict[str, ParamSpec]   # 可调参数 → schema

    # 状态机: idle → queued → running → done / failed / skipped
    status: NodeStatus

    # 核心方法
    async def run(self, inputs: dict, params: dict, work_dir: Path) -> NodeResult

    # 缓存键
    def cache_key(self, inputs: dict, params: dict) -> str
```

### 3.3 Edge

```python
class Edge:
    source_node_id: str
    source_port: str
    target_node_id: str
    target_port: str
    # 类型检查: source.output[port].type 必须兼容 target.input[port].type
```

### 3.4 Graph

```python
class Graph:
    nodes: dict[str, Node]
    edges: list[Edge]
    template_id: str | None
    metadata: dict  # name, description, created_at

    def topological_order(self) -> list[str]  # 返回 node_id 列表
    def validate(self) -> list[str]           # 返回错误列表
    def to_json(self) -> str
    @staticmethod
    def from_json(json_str: str) -> Graph
```

### 3.5 Executor

```python
class Executor:
    def __init__(self, cache_dir: Path, progress_callback, error_strategy: str)

    async def run(self, graph: Graph) -> ExecutorResult
    # 流程:
    # 1. graph.validate()
    # 2. topological_order()
    # 3. for each node in order:
    #    a. 收集 inputs（从上游节点的 outputs 获取）
    #    b. cache_key = hash(params + input_file_hashes)
    #    c. 查缓存 → 命中则跳过
    #    d. 未命中则 node.run()
    #    e. 存缓存
    #    f. 通过 progress_callback 推事件
```

### 3.6 端口类型系统

```python
class PortType(Enum):
    FILE_PATH = "file_path"       # 文件路径
    SRT_CONTENT = "srt_content"   # 字幕数据
    VIDEO_INFO = "video_info"     # {path, fps, width, height, duration}
    AUDIO_SEGMENTS = "audio_segments"  # 音频段列表
    JSON_DATA = "json_data"       # 通用 JSON
```

### 3.7 缓存策略

- 缓存目录: `.data/cache/{node_type}/{cache_key}/`
- 缓存键 = `sha256(node_params_json + file_content_hash_of_inputs)`
- Node.run() 产物写入缓存目录
- Executor 执行前检查缓存，命中直接跳过
- 用户改任意参数 → cache_key 变化 → 自动重跑该节点及下游
- 用户点"强制重跑" → 忽略缓存

## 4. 内置节点类型

| 节点类型 | 输入 | 输出 | 核心逻辑来源 |
|----------|------|------|-------------|
| `VideoInput` | 无 (用户拖入文件) | video_info | - |
| `TTSExtract` | video_info | script_txt, full_srt, final_srt | tts_srt_extractor.py |
| `SRTRewrite` | srt_content | rewritten_srt | srt_llm_rewriter.py |
| `VideoMatch` | viral_video, source_video | matched_video, segments_json | match_tuil.py |
| `TTSGenerate` | rewritten_srt | audio_segments[], timeline_audio | Minimax API (workflow.py) |
| `VideoCompose` | matched_video, timeline_audio, tts_entries | final_video | ffmpeg 拼接逻辑 (workflow.py) |
| `JianyingExport` | final_video, viral_video | draft_path | jianying.py |

## 5. 前后端通信

### 5.1 REST API

| Method | Path | 说明 |
|--------|------|------|
| POST | /api/graph/run | 提交 Graph JSON，返回 task_id，开始执行 |
| GET | /api/tasks | 任务列表 |
| GET | /api/tasks/{id} | 任务详情 (含 graph + 节点状态) |
| PUT | /api/tasks/{id}/node/{node_id} | 更新节点参数 |
| POST | /api/tasks/{id}/node/{node_id}/rerun | 重跑单个节点 |
| GET | /api/templates | 模板列表 |
| POST | /api/templates | 保存当前图为模板 |
| GET | /api/node/{id}/output/{filename} | 获取节点产物文件（预览用） |
| GET/PUT | /api/settings | 全局设置 |

### 5.2 WebSocket 事件

```json
{"type": "node_status", "node_id": "n3", "status": "running", "progress": 0.5}
{"type": "node_done", "node_id": "n3", "outputs": {...}, "preview_url": "/api/node/n3/preview"}
{"type": "node_error", "node_id": "n3", "error": "Traceback..."}
{"type": "graph_complete", "task_id": "xxx", "final_video_url": "..."}
{"type": "log", "node_id": "n3", "level": "info", "message": "..."}
```

## 6. 前端设计

### 6.1 布局

```
┌──────────────────────────────────────────────┐
│  [Logo] TK爆款复刻    [+ 新建任务]  [⚙️]     │  顶部栏
├────────────┬──────────────────┬───────────────┤
│  📋 任务列表 │                  │   📌 节点详情  │
│            │    🎬 画布区域    │   ─ 参数      │
│  🦇 蝙蝠侠  │   (React Flow)   │   ─ 输入      │
│  🔪 犯罪现场 │                  │   ─ 输出/预览  │
│  🏎️ 飙车   │  节点+连线+缩略图 │   ─ 日志      │
│            │                  │               │
│  (可拖拽   │  可缩放 · 可拖拽  │   (可拖拽     │
│   调整宽度) │                  │    调整宽度)   │
└────────────┴──────────────────┴───────────────┘
```

三个面板均可拖拽调整宽度。

### 6.2 任务创建流程

1. 用户点击"新建任务"或拖入视频文件
2. 弹出模板选择面板: 快速复刻·中文 / 快速复刻·英文 / 自建空白
3. 选择模板后，画布自动加载节点图
4. VideoInput 节点自动填入拖入的文件路径
5. 用户可在画布上调整任意节点参数、连线
6. 点击运行按钮，Executor 开始执行

### 6.3 节点视觉

- 每个节点卡片显示: 类型图标 + 标签 + 状态指示灯
- **idle**: 灰色边框
- **running**: 蓝色边框 + 旋转动画 + 进度环
- **done**: 绿色边框 + 缩略图预览（视频/音频/字幕片段）
- **failed**: 红色边框 + 错误图标
- 点击节点 → 右侧面板显示详情（参数/输入/输出/日志 四个 Tab）
- 节点端口（输入左、输出右）可拖出连线

## 7. 模板系统

- 模板 = 预连好的 Graph JSON 文件
- 存储在 `app/templates/` 目录
- VideoInput 节点的文件路径为空，用户拖入时自动填入
- 预置模板:
  - `quick_chinese.json`: 中文短视频复刻（TTS→改写→匹配→TTS→拼接→剪映）
  - `quick_english.json`: 同上，目标语言英语
  - `tts_extract_only.json`: 仅 TTS 提取+改写，不含视频处理
- 用户在画布上修改后的图可保存为新模板

## 8. 设置系统

### 全局设置（SQLite settings 表）

仅包含使应用能启动的必要项:
- API Key (LLM 网关)
- Minimax Group ID + API Key
- 默认输出目录

### 节点参数（存储在 Graph JSON 中）

每个节点自带 params，可在画布右侧面板修改:
- `TTSExtract`: whisper_model, vad_model, vad_threshold, min_speech_ms, min_silence_ms, min_word_overlap, refresh_gemini
- `SRTRewrite`: target_language, style, max_segment_seconds, max_gap_ms, llm_model, llm_base_url
- `VideoMatch`: gpu_enabled
- `TTSGenerate`: voice_id, speed, volume, pitch, audio_format, minimax_model
- `VideoCompose`: video_codec, audio_codec, keep_temp

用户可右键节点 → "Pin 为默认参数" → 存储到 `node_defaults` 表 → 以后新建该类型节点自动填入。

## 9. 项目结构

```
autocopy/
├── app/
│   ├── pipeline/           # Pipeline SDK 核心 (Phase 1)
│   │   ├── node.py         # Node 基类 + 状态机
│   │   ├── edge.py         # Edge + 类型检查
│   │   ├── graph.py        # Graph + 拓扑排序 + 序列化
│   │   ├── executor.py     # Executor + 缓存 + 调度
│   │   └── types.py        # 端口类型定义
│   ├── nodes/              # 内置节点实现 (Phase 2)
│   │   ├── video_input.py
│   │   ├── tts_extract.py
│   │   ├── srt_rewrite.py
│   │   ├── video_match.py
│   │   ├── tts_generate.py
│   │   ├── video_compose.py
│   │   └── jianying_export.py
│   ├── templates/          # 预置模板 (Graph JSON)
│   │   ├── quick_chinese.json
│   │   ├── quick_english.json
│   │   └── tts_extract_only.json
│   ├── server/             # FastAPI 后端 (Phase 3)
│   │   ├── main.py         # 应用入口
│   │   ├── routes/         # REST API 路由
│   │   ├── websocket.py    # WebSocket 管理
│   │   └── database.py     # SQLite 操作
│   ├── settings.py         # 极简全局设置
│   └── copied/             # ⚠️ 保留，逐步迁移后删除
├── frontend/               # React 前端 (Phase 4)
│   ├── src/
│   │   ├── App.tsx
│   │   ├── canvas/         # React Flow 画布组件
│   │   ├── panels/         # 侧边栏/参数面板
│   │   ├── widgets/        # 通用组件
│   │   ├── stores/         # Zustand 状态管理
│   │   └── hooks/          # WebSocket 连接等
│   └── package.json
├── tests/
│   ├── test_pipeline/      # Pipeline SDK 单元测试
│   ├── test_nodes/         # 节点单元测试
│   └── test_server/        # API 集成测试
├── pyproject.toml
└── run.py                  # PyWebView 桌面入口
```

## 10. 迁移计划

### Phase 1 — Pipeline SDK 核心 (app/pipeline/)
- node.py, edge.py, graph.py, executor.py, types.py
- 纯 Python，无 UI 依赖
- 可独立测试
- 产物: 可运行的 Graph → Executor → 结果

### Phase 2 — 迁移算法逻辑 (app/nodes/)
- 从 `app/copied/` 提取核心算法到各 node
- 每个 node 包装为一个 Node 子类
- 旧 `copied/` 保留但不再引用
- 产物: 6 个内置节点 + 3 个模板可通过 Executor 命令行运行

### Phase 3 — FastAPI 后端 (app/server/)
- REST API + WebSocket
- Graph CRUD + 执行触发
- SQLite 替代 JSON 文件
- 产物: 可通过 curl/Postman 调用 API 跑任务

### Phase 4 — React 前端 (frontend/)
- React Flow 画布
- 三栏布局 + 参数面板 + 预览
- WebSocket 实时更新
- 产物: 完整 Web 界面

### Phase 5 — 打包 & 清理
- PyWebView 桌面打包
- 删除旧 `app/main.py` (PyQt6) 和 `app/copied/`
- 全面测试 + 文档
- 产物: 可分发的桌面应用

## 11. 关键设计决策

1. **Pipeline SDK 独立于 UI**: 可在命令行直接使用，也可通过 FastAPI 调用，也可嵌入任何 UI
2. **节点产物缓存基于内容哈希**: 改参数自动重跑，不改直接跳过，高效调试
3. **Graph JSON 是唯一真相源**: 模板、任务、用户自定义流程都用同一种 Graph 格式，模型到 UI 的映射是 1:1
4. **所有中间产物可访问**: 通过 API 和文件系统双重访问，用户可手动替换中间文件后继续
5. **WebSocket 单向推送**: 后端 → 前端的事件流，前端不通过 WS 发送命令（命令走 REST），职责清晰
