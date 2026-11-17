import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Project, RunSummary } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { Filter, PlayCircle } from 'lucide-react';

interface RunsHistoryViewProps {
  onNavigateRun: (runId: string) => void;
  onNavigateProject: (projectId: string) => void;
  onNewRun: () => void;
}

export const RunsHistoryView: React.FC<RunsHistoryViewProps> = ({
  onNavigateRun,
  onNavigateProject,
  onNewRun,
}) => {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [frameworkFilter, setFrameworkFilter] = useState<string>('');
  const [taskFilter, setTaskFilter] = useState<string>('');

  const projectNames = new Map(projects.map(p => [p.id, p.name]));

  const loadData = async () => {
    try {
      const [runData, projData] = await Promise.all([
        api.listRuns({
          status: statusFilter || undefined,
          framework: frameworkFilter || undefined,
          task: taskFilter || undefined,
        }),
        api.listProjects(),
      ]);
      setRuns(runData);
      setProjects(projData);
    } catch (err) {
      console.error('Failed to load runs history:', err);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 4000);
    return () => clearInterval(interval);
  }, [statusFilter, frameworkFilter, taskFilter]);

  return (
    <div style={{ padding: '32px 40px', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: '28px'
      }}>
        <div>
          <h1 style={{ fontSize: '26px', fontWeight: 650, color: 'var(--color-text-primary)', marginBottom: '6px' }}>
            Runs History
          </h1>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: '15px' }}>
            Every training run across all projects — filter, inspect, reproduce, or compare.
          </p>
        </div>
        <button
          onClick={onNewRun}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: 'var(--color-primary)',
            color: '#FFF',
            border: 'none',
            padding: '10px 18px',
            borderRadius: '6px',
            fontWeight: 600,
            fontSize: '14px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
          }}
        >
          <PlayCircle size={18} />
          Launch New Run
        </button>
      </div>

      {/* Filter Strip */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
        backgroundColor: 'var(--color-bg-secondary)',
        padding: '12px 20px',
        borderRadius: '6px',
        marginBottom: '20px',
        border: '1px solid var(--color-border)',
        fontSize: '13px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, color: 'var(--color-text-secondary)' }}>
          <Filter size={15} />
          Filters:
        </div>

        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid var(--color-border)' }}
        >
          <option value="">All Statuses</option>
          <option value="queued">Queued</option>
          <option value="running">Running</option>
          <option value="succeeded">Succeeded</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
        </select>

        <select
          value={frameworkFilter}
          onChange={e => setFrameworkFilter(e.target.value)}
          style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid var(--color-border)' }}
        >
          <option value="">All Frameworks</option>
          <option value="pytorch">PyTorch</option>
          <option value="numpy">NumPy</option>
        </select>

        <select
          value={taskFilter}
          onChange={e => setTaskFilter(e.target.value)}
          style={{ padding: '4px 8px', borderRadius: '4px', border: '1px solid var(--color-border)' }}
        >
          <option value="">All Tasks</option>
          <option value="classification">Classification</option>
          <option value="regression">Regression</option>
        </select>

        <span style={{ marginLeft: 'auto', color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>
          {runs.length} runs listed
        </span>
      </div>

      {/* Runs Table */}
      <div style={{
        backgroundColor: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '6px',
        overflow: 'hidden'
      }}>
        {runs.length === 0 ? (
          <div style={{ padding: '60px 20px', textAlign: 'center', color: 'var(--color-text-secondary)' }}>
            <p style={{ fontSize: '15px', marginBottom: '16px' }}>No runs match the selected filters.</p>
            <button
              onClick={onNewRun}
              style={{
                padding: '8px 16px',
                backgroundColor: 'var(--color-primary)',
                color: '#FFF',
                border: 'none',
                borderRadius: '4px',
                fontWeight: 600,
                fontSize: '13px'
              }}
            >
              Start First Run
            </button>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
            <thead>
              <tr style={{ backgroundColor: 'var(--color-bg-secondary)', borderBottom: '1px solid var(--color-border)' }}>
                <th style={{ padding: '10px 16px', fontWeight: 600 }}>Run Name</th>
                <th style={{ padding: '10px 16px', fontWeight: 600 }}>Project</th>
                <th style={{ padding: '10px 16px', fontWeight: 600 }}>Status</th>
                <th style={{ padding: '10px 16px', fontWeight: 600 }}>Framework</th>
                <th style={{ padding: '10px 16px', fontWeight: 600 }}>Task</th>
                <th style={{ padding: '10px 16px', fontWeight: 600 }}>Primary Metric</th>
                <th style={{ padding: '10px 16px', fontWeight: 600 }}>Duration</th>
                <th style={{ padding: '10px 16px', fontWeight: 600 }}>Created</th>
              </tr>
            </thead>
            <tbody>
              {runs.map(r => (
                <tr
                  key={r.id}
                  onClick={() => onNavigateRun(r.id)}
                  style={{
                    borderBottom: '1px solid var(--color-border-subtle)',
                    cursor: 'pointer',
                    transition: 'background 0.1s ease',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.backgroundColor = 'var(--color-bg)')}
                  onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <td style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--color-primary)' }}>
                    {r.name}
                  </td>
                  <td
                    style={{ padding: '12px 16px', fontSize: '13px', color: 'var(--color-text-secondary)' }}
                    onClick={e => {
                      e.stopPropagation();
                      onNavigateProject(r.project_id);
                    }}
                  >
                    {projectNames.get(r.project_id) || r.project_id}
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <StatusBadge status={r.status} />
                  </td>
                  <td style={{ padding: '12px 16px', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
                    {r.framework.toUpperCase()}
                  </td>
                  <td style={{ padding: '12px 16px', fontSize: '13px', color: 'var(--color-text-secondary)' }}>
                    {r.task}
                  </td>
                  <td style={{ padding: '12px 16px', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
                    {r.primary_metric ? (
                      <span>
                        {r.primary_metric.name}: <strong>{r.primary_metric.value.toFixed(4)}</strong>
                      </span>
                    ) : (
                      <span style={{ color: 'var(--color-text-muted)' }}>-</span>
                    )}
                  </td>
                  <td style={{ padding: '12px 16px', fontFamily: 'var(--font-mono)', fontSize: '13px', color: 'var(--color-text-muted)' }}>
                    {r.duration_ms ? `${(r.duration_ms / 1000).toFixed(2)}s` : '-'}
                  </td>
                  <td style={{ padding: '12px 16px', fontSize: '13px', color: 'var(--color-text-muted)' }}>
                    {new Date(r.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
