import { useEffect } from 'react';
import TopBar from './components/TopBar';
import TaskList from './components/TaskList';
import Canvas from './components/Canvas';
import NodeDetail from './components/NodeDetail';
import TemplateDialog from './components/TemplateDialog';
import { useStore } from './stores/useStore';
import { apiGet } from './api/client';
import type { Task } from './types';

export default function App() {
  const setTasks = useStore((s) => s.setTasks);

  useEffect(() => {
    apiGet<Task[]>('/api/tasks').then(setTasks).catch(() => {});
  }, []);

  return (
    <div className="h-screen flex flex-col bg-gray-950 text-gray-200">
      <TopBar />
      <div className="flex-1 flex overflow-hidden">
        <TaskList />
        <Canvas />
        <NodeDetail />
      </div>
      <TemplateDialog />
    </div>
  );
}
