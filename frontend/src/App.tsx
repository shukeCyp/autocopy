import TopBar from './components/TopBar';
import Sidebar from './components/Sidebar';
import Canvas from './components/Canvas';
import NodeDetail from './components/NodeDetail';

export default function App() {
  return (
    <div className="h-screen flex flex-col bg-gray-950 text-gray-200">
      <TopBar />
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <Canvas />
        <NodeDetail />
      </div>
    </div>
  );
}
