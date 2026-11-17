import { useEffect, useState } from 'react';
import { api } from './api/client';
import { Navigation } from './components/Navigation';
import { DashboardView } from './features/DashboardView';
import { ProjectsView } from './features/ProjectsView';
import { ProjectDetailView } from './features/ProjectDetailView';
import { NewRunWizardView } from './features/NewRunWizardView';
import { RunDetailView } from './features/RunDetailView';
import { CompareView } from './features/CompareView';
import { RunsHistoryView } from './features/RunsHistoryView';
import { DiagnosticsView } from './features/DiagnosticsView';

export function App() {
  const [currentTab, setCurrentTab] = useState<string>('dashboard');
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [compareRunIds, setCompareRunIds] = useState<string[]>([]);
  const [systemHealthy, setSystemHealthy] = useState<boolean>(true);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        await api.getHealth();
        setSystemHealthy(true);
      } catch {
        setSystemHealthy(false);
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleSelectProject = (projectId: string) => {
    setSelectedProjectId(projectId);
    setCurrentTab('project-detail');
  };

  const handleNavigateRun = (runId: string) => {
    setSelectedRunId(runId);
    setCurrentTab('run-detail');
  };

  const handleStartNewRun = (projectId?: string) => {
    if (projectId) {
      setSelectedProjectId(projectId);
      setCurrentTab('new-run');
    } else {
      api.listProjects().then(projs => {
        if (projs.length > 0) {
          setSelectedProjectId(projs[0].id);
          setCurrentTab('new-run');
        } else {
          setCurrentTab('projects');
        }
      });
    }
  };

  const handleCompare = (runIds: string[]) => {
    setCompareRunIds(runIds);
    setCurrentTab('compare');
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navigation
        currentTab={currentTab}
        onSelectTab={tab => {
          setCurrentTab(tab);
          if (tab === 'dashboard' || tab === 'projects') {
            setSelectedProjectId(null);
            setSelectedRunId(null);
          }
        }}
        systemHealthy={systemHealthy}
      />

      <main style={{ flex: 1, backgroundColor: 'var(--color-bg)' }}>
        {currentTab === 'dashboard' && (
          <DashboardView
            onNavigateProject={handleSelectProject}
            onNavigateRun={handleNavigateRun}
            onNewRun={() => handleStartNewRun()}
          />
        )}

        {currentTab === 'projects' && (
          <ProjectsView onSelectProject={handleSelectProject} />
        )}

        {currentTab === 'project-detail' && selectedProjectId && (
          <ProjectDetailView
            projectId={selectedProjectId}
            onBack={() => setCurrentTab('projects')}
            onNavigateRun={handleNavigateRun}
            onNewRun={handleStartNewRun}
            onCompare={handleCompare}
          />
        )}

        {currentTab === 'new-run' && selectedProjectId && (
          <NewRunWizardView
            projectId={selectedProjectId}
            onBack={() => setCurrentTab('project-detail')}
            onRunCreated={runId => handleNavigateRun(runId)}
          />
        )}

        {currentTab === 'run-detail' && selectedRunId && (
          <RunDetailView
            runId={selectedRunId}
            onBack={() => {
              if (selectedProjectId) setCurrentTab('project-detail');
              else setCurrentTab('dashboard');
            }}
            onNavigateRun={handleNavigateRun}
          />
        )}

        {currentTab === 'compare' && compareRunIds.length >= 2 && (
          <CompareView
            runIds={compareRunIds}
            onBack={() => {
              if (selectedProjectId) setCurrentTab('project-detail');
              else setCurrentTab('dashboard');
            }}
            onNavigateRun={handleNavigateRun}
          />
        )}

        {currentTab === 'runs' && (
          <RunsHistoryView
            onNavigateRun={handleNavigateRun}
            onNavigateProject={handleSelectProject}
            onNewRun={() => handleStartNewRun()}
          />
        )}

        {currentTab === 'system' && <DiagnosticsView />}
      </main>
    </div>
  );
}

export default App;
