from app.pipeline.node import Node

from app.nodes.video_input import VideoInput
from app.nodes.tts_extract import TTSExtract
from app.nodes.srt_rewrite import SRTRewrite
from app.nodes.video_match import VideoMatch
from app.nodes.tts_generate import TTSGenerate
from app.nodes.video_compose import VideoCompose
from app.nodes.jianying_export import JianyingExport

# Register all built-in nodes so from_dict can reconstruct them
for cls in [VideoInput, TTSExtract, SRTRewrite, VideoMatch, TTSGenerate, VideoCompose, JianyingExport]:
    Node.register(cls)

__all__ = [
    "VideoInput",
    "TTSExtract",
    "SRTRewrite",
    "VideoMatch",
    "TTSGenerate",
    "VideoCompose",
    "JianyingExport",
]
