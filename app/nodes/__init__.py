from app.pipeline.node import Node

from app.nodes.video_input import VideoInput
from app.nodes.video_audio_extract import VideoAudioExtract
from app.nodes.vocal_separation import VocalSeparation
from app.nodes.voice_vad import VoiceVAD
from app.nodes.dominant_speaker import DominantSpeaker
from app.nodes.segment_asr import SegmentASR
from app.nodes.tts_extract import TTSExtract
from app.nodes.srt_rewrite import SRTRewrite
from app.nodes.video_match import VideoMatch
from app.nodes.video_match_vmf import VideoMatchVMF
from app.nodes.tts_generate import TTSGenerate
from app.nodes.video_compose import VideoCompose
from app.nodes.jianying_merge import JianyingMerge
from app.nodes.jianying_export import JianyingExport

_REGISTERED_NODE_CLASSES = [
    VideoInput,
    VideoAudioExtract,
    VocalSeparation,
    VoiceVAD,
    DominantSpeaker,
    SegmentASR,
    TTSExtract,
    SRTRewrite,
    VideoMatch,
    VideoMatchVMF,
    TTSGenerate,
    VideoCompose,
    JianyingMerge,
    JianyingExport,
]

# Register all known nodes so from_dict can reconstruct saved workflows.
for cls in _REGISTERED_NODE_CLASSES:
    Node.register(cls)

__all__ = [
    "VideoInput",
    "VideoAudioExtract",
    "VocalSeparation",
    "VoiceVAD",
    "DominantSpeaker",
    "SegmentASR",
    "SRTRewrite",
    "VideoMatch",
    "VideoMatchVMF",
    "TTSGenerate",
    "VideoCompose",
    "JianyingMerge",
    "JianyingExport",
]
