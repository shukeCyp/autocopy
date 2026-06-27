# Phase 4 — React 前端 实施计划

> **Goal:** React Flow 画布 + 三栏布局 + 模板选择 + WebSocket 实时更新

**Architecture:** React 18 + React Flow + Tailwind CSS + Zustand. Vite dev server + FastAPI backend proxy.

## 文件结构

```
frontend/
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── tsconfig.json
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx                 # 三栏主布局
    ├── api/
    │   └── client.ts           # REST + WS 封装
    ├── stores/
    │   └── useStore.ts         # Zustand 全局状态
    ├── components/
    │   ├── TaskList.tsx         # 左侧任务列表
    │   ├── Canvas.tsx           # React Flow 画布
    │   ├── NodeDetail.tsx       # 右侧节点详情
    │   ├── TemplateDialog.tsx   # 模板选择弹窗
    │   ├── TopBar.tsx           # 顶部栏
    │   └── custom/
    │       └── PipelineNode.tsx # 自定义节点渲染
    └── types.ts                 # TypeScript 类型定义
```

## 核心功能

1. 三栏可拖拽布局 (TaskList | Canvas | NodeDetail)
2. 顶部栏: Logo + 新建任务按钮 + 设置入口
3. 新建任务 → 模板选择弹窗 → 加载到画布
4. 画布: React Flow 节点图, 节点状态颜色, 连线, 缩略图预览
5. 点击节点 → 右侧面板: 参数/输入/输出/日志 Tab
6. 运行按钮 → POST /api/graph/run → WebSocket 实时更新节点状态
7. 任务列表: 切换任务 → 加载对应图到画布

## Notes

- Vite proxy: /api → localhost:8000, /ws → localhost:8000
- React Flow nodes use custom PipelineNode component
- Node status colors: idle=gray, queued=yellow, running=blue, done=green, failed=red, skipped=gray
- Zustand store: tasks, currentTaskId, selectedNodeId, graph (nodes+edges), templates
