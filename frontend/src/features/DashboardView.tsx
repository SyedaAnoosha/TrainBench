import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Project, RunSummary } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { PlayCircle, Layers, TrendingUp, Cpu } from 'lucide-react';

interface DashboardViewProps {
  onNavigateProject: (projectId: string) => void;
  onNavigateRun: (runId: string) => void;
  onNewRun: () => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({
  onNavigateRun,
  onNewRun,
}) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [runs, setRuns] = useState<RunSummary[]>([]);

  const loadData = async () => {
    try {
      const [projData, runData] = await Promise.all([
        api.listProjects(),
        api.listRuns({}),
      ]);
      setProjects(projData);
      setRuns(runData);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 4000);
    return () => clearInterval(interval);
  }, []);

  const totalRuns = runs.length;
  const activeRuns = runs.filter(r => r.status === 'running' || r.status === 'queued');
  const succeededRuns = runs.filter(r => r.status === 'succeeded').length;
  const successRate = totalRuns > 0 ? Math.round((succeededRuns / totalRuns) * 100) : 100;

  return (
    <div style={{ padding: '32px 40px', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Top Banner */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        marginBottom: '32px'
      }}>
        <div>
          <h1 style={{ fontSize: '26px', fontWeight: 650, color: 'var(--color-text-primary)', marginBottom: '6px' }}>
            Experiment Dashboard
          </h1>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: '15px' }}>
            Deterministic machine learning benchmarks across PyTorch, NumPy, and gradient descent references.
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

      {/* Metrics Row */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '16px',
        marginBottom: '32px'
      }}>
        {[
          { label: 'Active Jobs', value: activeRuns.length, icon: PlayCircle, color: 'var(--color-primary)' },
          { label: 'Total Projects', value: projects.length, icon: Layers, color: 'var(--color-secondary)' },
          { label: 'Completed Runs', value: totalRuns, icon: Cpu, color: 'var(--color-text-primary)' },
          { label: 'Success Rate', value: `${successRate}%`, icon: TrendingUp, color: 'var(--color-success)' },
        ].map((stat, i) => {
          const Icon = stat.icon;
          return (
            <div
              key={i}
              style={{
                backgroundColor: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: '6px',
                padding: '20px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '13px', color: 'var(--color-text-secondary)', fontWeight: 600 }}>
                  {stat.label}
                </span>
                <Icon size={18} color={stat.color} />
              </div>
              <span style={{ fontSize: '28px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: stat.color }}>
                {stat.value}
              </span>
            </div>
          );
        })}
      </div>

      {/* Active Runs Alert / Table if any */}
      {activeRuns.length > 0 && (
        <div style={{
          backgroundColor: 'var(--color-surface)',
          border: '1px solid var(--color-primary)',
          borderRadius: '6px',
          padding: '20px',
          marginBottom: '32px'
        }}>
          <h2 style={{ fontSize: '16px', fontWeight: 650, color: 'var(--color-primary)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--color-primary)' }} />
            Active Training Execution ({activeRuns.length})
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {activeRuns.map(r => (
              <div
                key={r.id}
                onClick={() => onNavigateRun(r.id)}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '12px 16px',
                  backgroundColor: 'var(--color-bg)',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  border: '1px solid var(--color-border)'
                }}
              >
                <div>
                  <span style={{ fontWeight: 600, fontSize: '15px' }}>{r.name}</span>
                  <span style={{ marginLeft: '12px', fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--color-text-muted)' }}>
                    {r.framework.toUpperCase()} • {r.task}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <StatusBadge status={r.status} />
                  <span style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>View Live Metrics &rarr;</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Experiments Table */}
      <div style={{
        backgroundColor: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '6px',
        overflow: 'hidden'
      }}>
        <div style={{
          padding: '16px 20px',
          borderBottom: '1px solid var(--color-border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <h2 style={{ fontSize: '16px', fontWeight: 650 }}>Recent Experiment Runs</h2>
          <span style={{ fontSize: '13px', color: 'var(--color-text-muted)' }}>Showing {runs.length} runs</span>
        </div>

        {runs.length === 0 ? (
          <div style={{ padding: '48px 20px', textAlign: 'center', color: 'var(--color-text-secondary)' }}>
            <p style={{ marginBottom: '16px' }}>No training runs recorded yet.</p>
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
                  <td style={{ padding: '12px 16px' }}>
                    <StatusBadge status={r.status} />
                  </td>
                  <td style={{ padding: '12px 16px', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
                    {r.framework}
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
                    {new Date(r.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
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
