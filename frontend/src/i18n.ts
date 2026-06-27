export type Language = 'zh' | 'en';

type TranslationKey =
  | 'app.title'
  | 'top.queuePrompt'
  | 'top.queueRunning'
  | 'top.save'
  | 'top.noWorkflow'
  | 'top.nodes'
  | 'top.links'
  | 'top.language'
  | 'sidebar.workflows'
  | 'sidebar.newWorkflow'
  | 'sidebar.workflowCreateFailed'
  | 'sidebar.workflowCopyFailed'
  | 'sidebar.workflowDeleteFailed'
  | 'sidebar.templatesLoadFailed'
  | 'sidebar.templateLoadFailed'
  | 'sidebar.loading'
  | 'sidebar.builtin'
  | 'sidebar.fullFlow'
  | 'sidebar.ttsOnly'
  | 'sidebar.tasks'
  | 'sidebar.emptyTasks'
  | 'canvas.ready'
  | 'canvas.emptyHint'
  | 'canvas.emptySubHint'
  | 'context.inspect'
  | 'context.open'
  | 'context.duplicate'
  | 'context.resetStatus'
  | 'context.copyId'
  | 'context.delete'
  | 'node.dropVideo'
  | 'node.pathCaptured'
  | 'node.pathUnavailable'
  | 'detail.selectNode'
  | 'detail.params'
  | 'detail.inputs'
  | 'detail.outputs'
  | 'detail.logs'
  | 'detail.optional'
  | 'detail.noOutputs'
  | 'detail.noLogs'
  | 'node.noInputs'
  | 'node.noOutputs'
  | 'status.pending'
  | 'status.running'
  | 'status.done'
  | 'status.failed';

const translations: Record<Language, Record<TranslationKey, string>> = {
  zh: {
    'app.title': 'TK 爆款复刻',
    'top.queuePrompt': '运行队列',
    'top.queueRunning': '运行中',
    'top.save': '保存',
    'top.noWorkflow': '未选择工作流',
    'top.nodes': '节点',
    'top.links': '连线',
    'top.language': '语言',
    'sidebar.workflows': '工作流模板',
    'sidebar.newWorkflow': '新建工作流',
    'sidebar.workflowCreateFailed': '创建工作流失败',
    'sidebar.workflowCopyFailed': '复制工作流失败',
    'sidebar.workflowDeleteFailed': '删除工作流失败',
    'sidebar.templatesLoadFailed': '模板列表加载失败',
    'sidebar.templateLoadFailed': '加载模板失败',
    'sidebar.loading': '加载中...',
    'sidebar.builtin': '内置',
    'sidebar.fullFlow': '6步全流程',
    'sidebar.ttsOnly': '仅TTS',
    'sidebar.tasks': '任务历史',
    'sidebar.emptyTasks': '暂无历史任务',
    'canvas.ready': '队列已就绪',
    'canvas.emptyHint': '空白工作流',
    'canvas.emptySubHint': '双击画布添加节点，或从左侧节点库添加',
    'context.inspect': '查看属性',
    'context.open': '打开',
    'context.duplicate': '复制',
    'context.resetStatus': '重置状态',
    'context.copyId': '复制节点ID',
    'context.delete': '删除',
    'node.dropVideo': '拖入视频文件',
    'node.pathCaptured': '已设置文件路径',
    'node.pathUnavailable': '浏览器无法读取文件绝对路径，请在右侧参数里粘贴路径',
    'detail.selectNode': '选择一个节点\n查看参数和输出',
    'detail.params': '参数',
    'detail.inputs': '输入',
    'detail.outputs': '输出',
    'detail.logs': '日志',
    'detail.optional': '可选',
    'detail.noOutputs': '无输出端口',
    'detail.noLogs': '暂无日志',
    'node.noInputs': '无输入',
    'node.noOutputs': '无输出',
    'status.pending': '等待中',
    'status.running': '运行中',
    'status.done': '完成',
    'status.failed': '失败',
  },
  en: {
    'app.title': 'TK Hot Copy',
    'top.queuePrompt': 'Queue Prompt',
    'top.queueRunning': 'Queue running',
    'top.save': 'Save',
    'top.noWorkflow': 'No workflow',
    'top.nodes': 'nodes',
    'top.links': 'links',
    'top.language': 'Language',
    'sidebar.workflows': 'Workflow Templates',
    'sidebar.newWorkflow': 'New workflow',
    'sidebar.workflowCreateFailed': 'Failed to create workflow',
    'sidebar.workflowCopyFailed': 'Failed to copy workflow',
    'sidebar.workflowDeleteFailed': 'Failed to delete workflow',
    'sidebar.templatesLoadFailed': 'Failed to load templates',
    'sidebar.templateLoadFailed': 'Failed to load template',
    'sidebar.loading': 'Loading...',
    'sidebar.builtin': 'Built-in',
    'sidebar.fullFlow': '6-step flow',
    'sidebar.ttsOnly': 'TTS only',
    'sidebar.tasks': 'Task History',
    'sidebar.emptyTasks': 'No task history',
    'canvas.ready': 'Queue ready',
    'canvas.emptyHint': 'Blank workflow',
    'canvas.emptySubHint': 'Double-click the canvas to add a node, or use the node library',
    'context.inspect': 'Inspect',
    'context.open': 'Open',
    'context.duplicate': 'Duplicate',
    'context.resetStatus': 'Reset status',
    'context.copyId': 'Copy node ID',
    'context.delete': 'Delete',
    'node.dropVideo': 'Drop video file',
    'node.pathCaptured': 'File path set',
    'node.pathUnavailable': 'Browser cannot read the absolute file path. Paste it in the right panel.',
    'detail.selectNode': 'Select a node\nto inspect params and outputs',
    'detail.params': 'Params',
    'detail.inputs': 'Inputs',
    'detail.outputs': 'Outputs',
    'detail.logs': 'Logs',
    'detail.optional': 'optional',
    'detail.noOutputs': 'No output ports',
    'detail.noLogs': 'No logs',
    'node.noInputs': 'no inputs',
    'node.noOutputs': 'no outputs',
    'status.pending': 'pending',
    'status.running': 'running',
    'status.done': 'done',
    'status.failed': 'failed',
  },
};

export function t(language: Language, key: TranslationKey): string {
  return translations[language][key];
}

const nodeLabelZh: Record<string, string> = {
  VideoInput: '加载视频',
  TTSExtract: '旁白提取',
  SRTRewrite: '文案改写',
  VideoMatch: '镜头匹配',
  TTSGenerate: '音频生成',
  VideoCompose: '视频合成',
  JianyingExport: '剪映导出',
};

const portLabelZh: Record<string, string> = {
  video_info: '视频信息',
  viral_video_info: '爆款视频信息',
  source_video_info: '原片视频信息',
  script_txt: '脚本文本',
  full_srt: '完整字幕',
  final_srt: '旁白字幕',
  srt_path: '字幕路径',
  rewritten_srt: '改写字幕',
  matched_video: '匹配视频',
  segments_json: '片段数据',
  review_html: '复核页面',
  timeline_audio: '时间线音频',
  entries_json: '音频条目',
  tts_entries_json: '配音条目',
  final_video: '成片视频',
  draft_path: '草稿路径',
};

const paramLabelZh: Record<string, string> = {
  path: '路径',
  api_key: 'API 密钥',
  gemini_model: 'Gemini 模型',
  model: '模型',
  base_url: '接口地址',
  whisper_model: 'Whisper 模型',
  vad_model: 'VAD 模型',
  vad_threshold: 'VAD 阈值',
  min_speech_ms: '最短语音',
  min_silence_ms: '最短静音',
  min_word_overlap: '词重叠阈值',
  refresh_gemini: '刷新 Gemini',
  target_language: '目标语言',
  style: '风格',
  max_segment_seconds: '最大分段秒数',
  max_gap_ms: '最大间隔毫秒',
  use_gpu: '启用 GPU',
  group_id: 'Group ID',
  voice_id: '音色 ID',
  speed: '语速',
  volume: '音量',
  pitch: '音调',
  audio_format: '音频格式',
  video_codec: '视频编码',
  audio_codec: '音频编码',
};

const templateLabelZh: Record<string, string> = {
  viral_input: '加载视频',
  source_input: '加载视频',
  tts_extract: 'TTS 提取',
  srt_rewrite: '文案改写',
  video_match: '镜头匹配',
  tts_generate: '音频生成',
  video_compose: '视频拼接',
  jianying_export: '剪映导出',
};

export function nodeLabel(language: Language, nodeType: string, fallback: string, nodeId?: string): string {
  if (language !== 'zh') return fallback;
  return (nodeId && templateLabelZh[nodeId]) || nodeLabelZh[nodeType] || fallback;
}

export function portLabel(language: Language, name: string): string {
  return language === 'zh' ? portLabelZh[name] || name : name;
}

export function paramLabel(language: Language, name: string): string {
  return language === 'zh' ? paramLabelZh[name] || name : name;
}
