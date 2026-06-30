import type { NodeData } from './types';
import { apiGet } from './api/client';

export const NODE_TYPES = [
  'VideoInput',
  'VideoAudioExtract',
  'VocalSeparation',
  'VoiceVAD',
  'DominantSpeaker',
  'SegmentASR',
  'SRTRewrite',
  'VideoMatch',
  'VideoMatchVMF',
  'TTSGenerate',
  'VideoCompose',
  'JianyingMerge',
  'JianyingExport',
];

const defaultNodeSpecs: Record<string, NodeData> = {
  VideoAudioExtract: {
    id: 'VideoAudioExtract',
    type: 'VideoAudioExtract',
    label: 'Extract Audio',
    x: 160,
    y: 160,
    status: 'idle',
    inputs: {
      audio_path: {
        name: 'audio_path',
        port_type: 'file_path',
        required: true,
        description: '',
      },
    },
    outputs: {
      audio_path: {
        name: 'audio_path',
        port_type: 'file_path',
        required: true,
        description: 'Extracted audio WAV',
      },
    },
    params: {
      audio_format: {
        name: 'audio_format',
        param_type: 'select',
        default: 'wav',
        description: '',
        options: ['wav'],
      },
    },
    paramValues: {},
  },
  VocalSeparation: {
    id: 'VocalSeparation',
    type: 'VocalSeparation',
    label: 'Vocal Separation',
    x: 160,
    y: 160,
    status: 'idle',
    inputs: {
      video_info: {
        name: 'video_info',
        port_type: 'video_info',
        required: true,
        description: '',
      },
    },
    outputs: {
      vocals_audio: {
        name: 'vocals_audio',
        port_type: 'file_path',
        required: true,
        description: 'Separated vocals WAV',
      },
      accompaniment_audio: {
        name: 'accompaniment_audio',
        port_type: 'file_path',
        required: true,
        description: 'Separated accompaniment WAV',
      },
      separated_dir: {
        name: 'separated_dir',
        port_type: 'file_path',
        required: true,
        description: 'Demucs output directory',
      },
    },
    params: {
      model: {
        name: 'model',
        param_type: 'select',
        default: 'htdemucs',
        description: '',
        options: ['htdemucs', 'htdemucs_ft', 'htdemucs_6s', 'mdx_extra', 'mdx_extra_q'],
      },
    },
    paramValues: {},
  },
  VoiceVAD: {
    id: 'VoiceVAD',
    type: 'VoiceVAD',
    label: 'Voice VAD',
    x: 160,
    y: 160,
    status: 'idle',
    inputs: {
      audio_path: {
        name: 'audio_path',
        port_type: 'file_path',
        required: true,
        description: '',
      },
    },
    outputs: {
      speech_segments_json: {
        name: 'speech_segments_json',
        port_type: 'file_path',
        required: true,
        description: 'VAD speech segments JSON',
      },
      speech_segments_dir: {
        name: 'speech_segments_dir',
        port_type: 'file_path',
        required: true,
        description: 'Directory containing split speech WAV files',
      },
    },
    params: {
      vad_model: {
        name: 'vad_model',
        param_type: 'string',
        default: 'ggml-silero-v6.2.0.bin',
        description: '',
      },
      vad_threshold: {
        name: 'vad_threshold',
        param_type: 'float',
        default: 0.25,
        description: '',
      },
      min_speech_ms: {
        name: 'min_speech_ms',
        param_type: 'int',
        default: 10,
        description: '',
      },
      min_silence_ms: {
        name: 'min_silence_ms',
        param_type: 'int',
        default: 50,
        description: '',
      },
    },
    paramValues: {},
  },
  DominantSpeaker: {
    id: 'DominantSpeaker',
    type: 'DominantSpeaker',
    label: 'Dominant Speaker',
    x: 160,
    y: 160,
    status: 'idle',
    inputs: {
      speech_segments_json: {
        name: 'speech_segments_json',
        port_type: 'file_path',
        required: true,
        description: '',
      },
    },
    outputs: {
      dominant_segments_json: {
        name: 'dominant_segments_json',
        port_type: 'file_path',
        required: true,
        description: 'Segments belonging to the dominant speaker',
      },
      speaker_report_json: {
        name: 'speaker_report_json',
        port_type: 'file_path',
        required: true,
        description: 'Speaker clustering report',
      },
      dominant_speaker_id: {
        name: 'dominant_speaker_id',
        port_type: 'json_data',
        required: true,
        description: 'Selected speaker cluster id',
      },
    },
    params: {
      similarity_threshold: {
        name: 'similarity_threshold',
        param_type: 'float',
        default: 0.82,
        description: '',
      },
      pyannote_model: {
        name: 'pyannote_model',
        param_type: 'string',
        default: 'pyannote/wespeaker-voxceleb-resnet34-LM',
        description: '',
      },
      hf_token: {
        name: 'hf_token',
        param_type: 'string',
        default: '',
        description: '',
      },
    },
    paramValues: {},
  },
  SegmentASR: {
    id: 'SegmentASR',
    type: 'SegmentASR',
    label: 'Segment ASR',
    x: 160,
    y: 160,
    status: 'idle',
    inputs: {
      segments_json: {
        name: 'segments_json',
        port_type: 'file_path',
        required: true,
        description: '',
      },
    },
    outputs: {
      srt_content: {
        name: 'srt_content',
        port_type: 'srt_content',
        required: true,
        description: 'ASR SRT text',
      },
    },
    params: {
      whisper_model: {
        name: 'whisper_model',
        param_type: 'string',
        default: 'ggml-large-v3-turbo.bin',
        description: '',
      },
      asr_language: {
        name: 'asr_language',
        param_type: 'select',
        default: 'en',
        description: '',
        options: ['en', 'zh', 'auto'],
      },
      prompt: {
        name: 'prompt',
        param_type: 'string',
        default: '',
        description: '',
      },
      speaker_filter: {
        name: 'speaker_filter',
        param_type: 'bool',
        default: true,
        description: '',
      },
      speaker_threshold: {
        name: 'speaker_threshold',
        param_type: 'float',
        default: 0.3,
        description: '',
      },
      timing_offset_ms: {
        name: 'timing_offset_ms',
        param_type: 'int',
        default: 0,
        description: '',
      },
    },
    paramValues: {},
  },
  VideoMatchVMF: {
    id: 'VideoMatchVMF',
    type: 'VideoMatchVMF',
    label: 'VMF Video Match',
    x: 160,
    y: 160,
    status: 'idle',
    inputs: {
      viral_video_info: {
        name: 'viral_video_info',
        port_type: 'video_info',
        required: true,
        description: '',
      },
      source_video_info: {
        name: 'source_video_info',
        port_type: 'video_info',
        required: true,
        description: '',
      },
    },
    outputs: {
      segments_json: {
        name: 'segments_json',
        port_type: 'file_path',
        required: true,
        description: '',
      },
      vmf_results_json: {
        name: 'vmf_results_json',
        port_type: 'file_path',
        required: true,
        description: '',
      },
    },
    params: {
      vmf_bin: {
        name: 'vmf_bin',
        param_type: 'string',
        default: 'vmf',
        description: '',
      },
      fps: {
        name: 'fps',
        param_type: 'float',
        default: 2.0,
        description: '',
      },
      model: {
        name: 'model',
        param_type: 'select',
        default: 'dinov2_vits14',
        description: '',
        options: ['dinov2_vits14', 'dinov2_vitb14'],
      },
      device: {
        name: 'device',
        param_type: 'select',
        default: 'auto',
        description: '',
        options: ['auto', 'cpu', 'cuda'],
      },
      no_mirror: {
        name: 'no_mirror',
        param_type: 'bool',
        default: false,
        description: '',
      },
      keyframes_only: {
        name: 'keyframes_only',
        param_type: 'bool',
        default: false,
        description: '',
      },
      no_cropdetect: {
        name: 'no_cropdetect',
        param_type: 'bool',
        default: false,
        description: '',
      },
      legacy_ransac: {
        name: 'legacy_ransac',
        param_type: 'bool',
        default: false,
        description: '',
      },
    },
    paramValues: {},
  },
  JianyingMerge: {
    id: 'JianyingMerge',
    type: 'JianyingMerge',
    label: 'Jianying Merge',
    x: 160,
    y: 160,
    status: 'idle',
    inputs: {
      segments_json: {
        name: 'segments_json',
        port_type: 'file_path',
        required: true,
        description: '',
      },
      rewritten_srt: {
        name: 'rewritten_srt',
        port_type: 'file_path',
        required: true,
        description: '',
      },
    },
    outputs: {
      draft_path: {
        name: 'draft_path',
        port_type: 'file_path',
        required: true,
        description: '',
      },
    },
    params: {
      draft_name: {
        name: 'draft_name',
        param_type: 'string',
        default: '',
        description: '',
      },
      draft_folder: {
        name: 'draft_folder',
        param_type: 'string',
        default: '',
        description: '',
      },
    },
    paramValues: {},
  },
};

export function cloneDefaultNodeSpec(nodeType: string): NodeData | null {
  const spec = defaultNodeSpecs[nodeType];
  return spec ? JSON.parse(JSON.stringify(spec)) : null;
}

export function schemaToNodeSpec(schema: NodeData): NodeData {
  return {
    ...JSON.parse(JSON.stringify(schema)),
    id: schema.type,
    label: schema.label || schema.type,
    x: 160,
    y: 160,
    status: 'idle',
    paramValues: {},
    validationIssues: [],
    error: undefined,
    outputs_cache: undefined,
  };
}

export function createNodeSampleMap(): Map<string, NodeData> {
  const samples = new Map<string, NodeData>();
  for (const nodeType of NODE_TYPES) {
    const spec = cloneDefaultNodeSpec(nodeType);
    if (spec) samples.set(nodeType, spec);
  }
  return samples;
}

export async function loadNodeSpecMap(): Promise<Map<string, NodeData>> {
  try {
    const schemas = await apiGet<NodeData[]>('/nodes');
    const samples = new Map<string, NodeData>();
    for (const schema of schemas) {
      samples.set(schema.type, schemaToNodeSpec(schema));
    }
    return samples.size > 0 ? samples : createNodeSampleMap();
  } catch {
    return createNodeSampleMap();
  }
}
