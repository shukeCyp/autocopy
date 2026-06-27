# Phase 2 — 内置节点 & 模板 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** 把 `app/copied/` 中的算法逻辑包装为 7 个 Node 子类，连同 3 个预置模板，可以通过 Executor 命令行运行。

**Architecture:** 每个节点是一个 Node 子类，`run()` 内部调用 copied/ 中的纯函数。参数在 `_define()` 中声明为 ParamSpec。节点文件放在 `app/nodes/`。

**Tech Stack:** 纯 Python，依赖 app/pipeline/ (Phase 1), app/copied/*, app/jianying.py

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `app/nodes/__init__.py` | 注册所有内置节点 |
| `app/nodes/video_input.py` | VideoInput — 输入节点，读取视频元信息 |
| `app/nodes/tts_extract.py` | TTSExtract — 包装 tts_srt_extractor |
| `app/nodes/srt_rewrite.py` | SRTRewrite — 包装 srt_llm_rewriter |
| `app/nodes/video_match.py` | VideoMatch — 包装 match_tuil |
| `app/nodes/tts_generate.py` | TTSGenerate — Minimax TTS |
| `app/nodes/video_compose.py` | VideoCompose — ffmpeg 拼接 |
| `app/nodes/jianying_export.py` | JianyingExport — 剪映草稿 |
| `app/templates/quick_chinese.json` | 快速复刻·中文 |
| `app/templates/quick_english.json` | 快速复刻·英文 |
| `app/templates/tts_only.json` | 仅提取+改写 TTS |
| `tests/test_nodes/__init__.py` | 空 |
| `tests/test_nodes/test_video_input.py` | VideoInput 测试 |
| `tests/test_nodes/test_tts_extract.py` | TTSExtract 测试 |
| `tests/test_nodes/test_srt_rewrite.py` | SRTRewrite 测试 |
| `tests/test_nodes/test_video_match.py` | VideoMatch 测试 |
| `tests/test_nodes/test_tts_generate.py` | TTSGenerate 测试 |
| `tests/test_nodes/test_video_compose.py` | VideoCompose 测试 |
| `tests/test_nodes/test_jianying_export.py` | JianyingExport 测试 |

---

### Task 1: VideoInput 节点

最简单——读视频文件，用 ffprobe 获取元信息。

**Create:** `app/nodes/__init__.py`, `app/nodes/video_input.py`, `tests/test_nodes/__init__.py`, `tests/test_nodes/test_video_input.py`

```python
# app/nodes/video_input.py
from pathlib import Path
from app.pipeline.node import Node
from app.pipeline.types import NodeResult, NodeStatus, PortSpec, PortType, ParamSpec


class VideoInput(Node):
    node_type = "VideoInput"

    def _define(self):
        self.inputs = {}
        self.outputs = {
            "video_info": PortSpec(name="video_info", port_type=PortType.VIDEO_INFO),
        }
        self.params = {
            "path": ParamSpec(name="path", param_type="string", default="", description="Video file path"),
        }

    async def run(self, inputs, params, work_dir):
        import json, subprocess, fractions
        path = Path(params["path"])
        if not path.exists():
            raise FileNotFoundError(f"video not found: {path}")

        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,duration,avg_frame_rate",
             "-of", "json", str(path)],
            check=True, stdout=subprocess.PIPE,
        )
        stream = json.loads(result.stdout)["streams"][0]
        fps = float(fractions.Fraction(stream.get("avg_frame_rate", "0/1")))
        info = {
            "path": str(path.resolve()),
            "width": int(stream["width"]),
            "height": int(stream["height"]),
            "duration": float(stream.get("duration", 0)),
            "fps": fps,
        }
        return NodeResult(node_id=self.id, status=NodeStatus.DONE, outputs={"video_info": info})
```

测试：mock subprocess.run，验证输出结构。

---

### Task 2: TTSExtract 节点

包装 `app.copied.tts_srt_extractor.extract_tts_srt`。

```python
# app/nodes/tts_extract.py
from pathlib import Path
from app.pipeline.node import Node
from app.pipeline.types import NodeResult, NodeStatus, PortSpec, PortType, ParamSpec


class TTSExtract(Node):
    node_type = "TTSExtract"

    def _define(self):
        self.inputs = {
            "video_info": PortSpec(name="video_info", port_type=PortType.VIDEO_INFO),
        }
        self.outputs = {
            "script_txt": PortSpec(name="script_txt", port_type=PortType.FILE_PATH),
            "full_srt": PortSpec(name="full_srt", port_type=PortType.FILE_PATH),
            "final_srt": PortSpec(name="final_srt", port_type=PortType.FILE_PATH),
        }
        self.params = {
            "api_key": ParamSpec(name="api_key", param_type="string", default=""),
            "gemini_model": ParamSpec(name="gemini_model", param_type="string", default="gemini-3.5-flash"),
            "base_url": ParamSpec(name="base_url", param_type="string", default="https://yunwu.ai"),
            "whisper_model": ParamSpec(name="whisper_model", param_type="string", default=".model/ggml-large-v3-turbo.bin"),
            "vad_model": ParamSpec(name="vad_model", param_type="string", default=".model/ggml-silero-v6.2.0.bin"),
            "vad_threshold": ParamSpec(name="vad_threshold", param_type="float", default=0.25),
            "min_speech_ms": ParamSpec(name="min_speech_ms", param_type="int", default=30),
            "min_silence_ms": ParamSpec(name="min_silence_ms", param_type="int", default=250),
            "min_word_overlap": ParamSpec(name="min_word_overlap", param_type="float", default=0.85),
            "refresh_gemini": ParamSpec(name="refresh_gemini", param_type="bool", default=False),
        }

    async def run(self, inputs, params, work_dir):
        from app.copied.tts_srt_extractor import extract_tts_srt
        video_path = inputs["video_info"]["path"]
        result = extract_tts_srt(
            video_path,
            api_key=params["api_key"],
            gemini_model=params["gemini_model"],
            base_url=params["base_url"],
            whisper_model=Path(params["whisper_model"]),
            vad_model=Path(params["vad_model"]),
            vad_threshold=params["vad_threshold"],
            min_speech_ms=params["min_speech_ms"],
            min_silence_ms=params["min_silence_ms"],
            min_word_overlap=params["min_word_overlap"],
            refresh_gemini=params["refresh_gemini"],
            output_dir=work_dir,
        )
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={
                "script_txt": str(result.script_path),
                "full_srt": str(result.full_asr_srt_path),
                "final_srt": str(result.final_srt_path),
            },
        )
```

测试：用 monkeypatch 替换 extract_tts_srt，验证输入/输出传递。

---

### Task 3: SRTRewrite 节点

包装 `app.copied.srt_llm_rewriter.GeminiSrtRewriter`。

```python
# app/nodes/srt_rewrite.py
class SRTRewrite(Node):
    node_type = "SRTRewrite"
    # inputs: srt_path (FILE_PATH)
    # outputs: rewritten_srt (FILE_PATH)
    # params: api_key, model, base_url, target_language, style, max_segment_seconds, max_gap_ms

    async def run(self, inputs, params, work_dir):
        from app.copied.srt_llm_rewriter import GeminiSrtRewriter
        output_path = work_dir / "rewritten.srt"
        rewriter = GeminiSrtRewriter(
            api_key=params["api_key"],
            model=params["model"],
            base_url=params["base_url"],
        )
        rewriter.rewrite_file(
            inputs["srt_path"],
            output_path,
            params["target_language"],
            params["style"],
            params["max_segment_seconds"],
            params["max_gap_ms"],
        )
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={"rewritten_srt": str(output_path)},
        )
```

测试：mock GeminiSrtRewriter，验证参数传递。

---

### Task 4: VideoMatch 节点

包装 `app.copied.match_tuil.match_video`。

```python
# app/nodes/video_match.py
class VideoMatch(Node):
    node_type = "VideoMatch"
    # inputs: viral_video_info, source_video_info (both VIDEO_INFO)
    # outputs: matched_video, segments_json, review_html (all FILE_PATH)
    # params: use_gpu

    async def run(self, inputs, params, work_dir):
        from app.copied import match_tuil
        result = match_tuil.match_video(
            inputs["viral_video_info"]["path"],
            inputs["source_video_info"]["path"],
            work_dir,
            use_gpu=params.get("use_gpu", False),
        )
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={
                "matched_video": result["output_video"],
                "segments_json": result["segments"],
                "review_html": result["output_html"],
            },
        )
```

测试：monkeypatch match_tuil.match_video。

---

### Task 5: TTSGenerate 节点

Minimax TTS + 时间轴合成。

```python
# app/nodes/tts_generate.py
class TTSGenerate(Node):
    node_type = "TTSGenerate"
    # inputs: rewritten_srt (FILE_PATH)
    # outputs: audio_segments_json (JSON_DATA), timeline_audio (FILE_PATH)
    # params: api_key, group_id, base_url, model, voice_id, speed, volume, pitch, audio_format

    async def run(self, inputs, params, work_dir):
        from app.workflow import srt_entries, generate_minimax_audio, compose_timed_audio

        entries = srt_entries(inputs["rewritten_srt"])
        segment_dir = work_dir / "audio_segments"
        segment_dir.mkdir(parents=True, exist_ok=True)

        minimax_settings = {
            "api_key": params["api_key"],
            "group_id": params["group_id"],
            "base_url": params["base_url"],
            "model": params["model"],
            "voice_id": params["voice_id"],
            "speed": params["speed"],
            "volume": params["volume"],
            "pitch": params["pitch"],
            "audio_format": params["audio_format"],
        }

        audio_paths = []
        for entry in entries:
            audio_path = generate_minimax_audio(
                entry["text"],
                segment_dir / f"{entry['index']:04d}.{params['audio_format']}",
                minimax_settings,
            )
            audio_paths.append(audio_path)

        timeline = compose_timed_audio(entries, audio_paths, work_dir / "voice_timeline.m4a")

        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={
                "timeline_audio": str(timeline),
                "entries_json": str(work_dir / "tts_entries.json"),
            },
        )
```

---

### Task 6: VideoCompose 节点

ffmpeg 最终拼接。

```python
# app/nodes/video_compose.py
class VideoCompose(Node):
    node_type = "VideoCompose"
    # inputs: matched_video (FILE_PATH), timeline_audio (FILE_PATH), tts_entries_json (FILE_PATH)
    # outputs: final_video (FILE_PATH)
    # params: video_codec, audio_codec

    async def run(self, inputs, params, work_dir):
        import json
        from app.workflow import compose_video, srt_entries

        tts_entries = json.loads(Path(inputs["tts_entries_json"]).read_text())
        output = work_dir / "final.mp4"
        compose_video(
            inputs["matched_video"],
            inputs["timeline_audio"],
            output,
            {
                "video_codec": params.get("video_codec", "libx264"),
                "audio_codec": params.get("audio_codec", "aac"),
            },
            tts_entries,
        )
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={"final_video": str(output)},
        )
```

---

### Task 7: JianyingExport 节点

```python
# app/nodes/jianying_export.py
class JianyingExport(Node):
    node_type = "JianyingExport"
    # inputs: final_video (FILE_PATH), viral_video_info (VIDEO_INFO)
    # outputs: draft_path (FILE_PATH)

    async def run(self, inputs, params, work_dir):
        from app.jianying import create_jianying_draft
        draft = create_jianying_draft(
            inputs["final_video"],
            inputs["viral_video_info"]["path"],
        )
        return NodeResult(
            node_id=self.id,
            status=NodeStatus.DONE,
            outputs={"draft_path": str(draft)},
        )
```

---

### Task 8: __init__.py + 注册所有节点 + 模板

`app/nodes/__init__.py` 注册全部 7 个节点。

创建 3 个模板 JSON 文件在 `app/templates/`。

---

### Task 9: 运行全量测试 & 端到端验证

```bash
uv run pytest tests/ -v
```

用 Executor 跑一个完整的 5 节点 pipeline（用 mock）验证端到端流程。

---

## 验收标准

```python
from app.pipeline import Graph, Executor
from app.nodes import VideoInput, TTSExtract, SRTRewrite, VideoMatch, TTSGenerate, VideoCompose

# Quick Chinese template pipeline
async def demo():
    g = Graph()
    viral = VideoInput(label="爆款视频", params={"path": "/path/to/viral.mp4"})
    source = VideoInput(label="原电影", params={"path": "/path/to/movie.mp4"})
    tts = TTSExtract(label="TTS提取")
    rewrite = SRTRewrite(label="文案改写")
    match = VideoMatch(label="镜头匹配")
    audio = TTSGenerate(label="音频生成")
    compose = VideoCompose(label="拼接")
    # ... add all nodes, add edges ...
    
    executor = Executor()
    result = await executor.run(g)
    print(result.to_dict())
```
