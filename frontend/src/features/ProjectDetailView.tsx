import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Dataset, Project, RunSummary } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { PlayCircle, ArrowLeft, BarChart2, Filter, Layers, Database, Trash2, AlertCircle } from 'lucide-react';

interface ProjectDetailViewProps {
  projectId: string;
  onBack: () => void;
  onNavigateRun: (runId: string) => void;
  onNewRun: (projectId: string) => void;
  onCompare: (runIds: string[]) => void;
}

export const ProjectDetailView: React.FC<ProjectDetailViewProps> = ({
  projectId,
  onBack,
  onNavigateRun,
  onNewRun,
  onCompare,
}) => {
  const [project, setProject] = useState<Project | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [activeTab, setActiveTab] = useState<'runs' | 'datasets'>('runs');
  const [selectedRunIds, setSelectedRunIds] = useState<string[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [frameworkFilter, setFrameworkFilter] = useState<string>('');
  const [taskFilter, setTaskFilter] = useState<string>('');
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const [projData, runData, dsData] = await Promise.all([
        api.getProject(projectId),
        api.listRuns({
          projectId,
          status: statusFilter || undefined,
          framework: frameworkFilter || undefined,
          task: taskFilter || undefined,
        }),
        api.listProjectDatasets(projectId),
      ]);
      setProject(projData);
      setRuns(runData);
      setDatasets(dsData);
    } catch (err) {
      console.error('Failed to load project details:', err);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 3000);
    return () => clearInterval(interval);
  }, [projectId, statusFilter, frameworkFilter, taskFilter]);

  const toggleSelectRun = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedRunIds(prev =>
      prev.includes(id) ? prev.filter(rId => rId !== id) : [...prev, id]
    );
  };

  const handleDeleteDataset = async (datasetId: string, filename: string) => {
    if (!window.confirm(`Delete dataset "${filename}"? This cannot be undone.`)) return;
    setDeleteError(null);
    try {
      await api.deleteDataset(datasetId);
      setDatasets(prev => prev.filter(d => d.id !== datasetId));
    } catch (err: any) {
      setDeleteError(err.message);
    }
  };

  return (
    <div style={{ padding: '32px 40px', maxWidth: '1280px', margin: '0 auto' }}>
      {/* Back button */}
      <button
        onClick={onBack}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          background: 'none',
          border: 'none',
          color: 'var(--color-text-secondary)',
          fontSize: '14px',
          fontWeight: 600,
          marginBottom: '16px',
          padding: 0
        }}
      >
        <ArrowLeft size={16} /> Back to Projects
      </button>

      {/* Project Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        backgroundColor: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '6px',
        padding: '24px 28px',
        marginBottom: '20px'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <Layers size={20} color="var(--color-primary)" />
            <h1 style={{ fontSize: '24px', fontWeight: 650, color: 'var(--color-text-primary)' }}>
              {project?.name || 'Project'}
            </h1>
          </div>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: '15px', maxWidth: '800px', lineHeight: 1.4 }}>
            {project?.description || 'No description provided.'}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          {selectedRunIds.length >= 2 && (
            <button
              onClick={() => onCompare(selectedRunIds)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                backgroundColor: 'var(--color-accent)',
                color: '#FFF',
                border: 'none',
                padding: '9px 16px',
                borderRadius: '6px',
                fontWeight: 600,
                fontSize: '14px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
              }}
            >
              <BarChart2 size={16} />
              Compare ({selectedRunIds.length}) Selected
            </button>
          )}

          <button
            onClick={() => onNewRun(projectId)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              backgroundColor: 'var(--color-primary)',
              color: '#FFF',
              border: 'none',
              padding: '9px 16px',
              borderRadius: '6px',
              fontWeight: 600,
              fontSize: '14px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
            }}
          >
            <PlayCircle size={16} />
            New Benchmark Run
          </button>
        </div>
      </div>

      {deleteError && (
        <div style={{
          padding: '12px 16px',
          backgroundColor: '#FEE2E2',
          color: '#991B1B',
          borderRadius: '6px',
          marginBottom: '20px',
          border: '1px solid #FECACA',
          fontSize: '14px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <AlertCircle size={16} />
          {deleteError}
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '16px', borderBottom: '1px solid var(--color-border)', marginBottom: '20px' }}>
        <button
          onClick={() => setActiveTab('runs')}
          style={{
            padding: '10px 16px',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'runs' ? '2px solid var(--color-primary)' : '2px solid transparent',
            color: activeTab === 'runs' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
            fontWeight: activeTab === 'runs' ? 700 : 500,
            fontSize: '15px',
            cursor: 'pointer',
          }}
        >
          Runs ({runs.length})
        </button>
        <button
          onClick={() => setActiveTab('datasets')}
          style={{
            padding: '10px 16px',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'datasets' ? '2px solid var(--color-primary)' : '2px solid transparent',
            color: activeTab === 'datasets' ? 'var(--color-primary)' : 'var(--color-text-secondary)',
            fontWeight: activeTab === 'datasets' ? 700 : 500,
            fontSize: '15px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}
        >
          <Database size={15} />
          Datasets ({datasets.length})
        </button>
      </div>

      {activeTab === 'runs' ? (
        <>
          {/* Filters Bar */}
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
                <p style={{ fontSize: '15px', marginBottom: '16px' }}>No runs match the selected filters in this project.</p>
                <button
                  onClick={() => onNewRun(projectId)}
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
                  Start First Experiment
                </button>
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
                <thead>
                  <tr style={{ backgroundColor: 'var(--color-bg-secondary)', borderBottom: '1px solid var(--color-border)' }}>
                    <th style={{ width: '40px', padding: '10px 16px', textAlign: 'center' }}>
                      <input
                        type="checkbox"
                        checked={runs.length > 0 && selectedRunIds.length === runs.length}
                        onChange={e => {
                          if (e.target.checked) setSelectedRunIds(runs.map(r => r.id));
                          else setSelectedRunIds([]);
                        }}
                      />
                    </th>
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
                  {runs.map(r => {
                    const isSelected = selectedRunIds.includes(r.id);
                    return (
                      <tr
                        key={r.id}
                        onClick={() => onNavigateRun(r.id)}
                        style={{
                          borderBottom: '1px solid var(--color-border-subtle)',
                          cursor: 'pointer',
                          backgroundColor: isSelected ? 'var(--color-bg)' : 'transparent',
                        }}
                      >
                        <td
                          style={{ padding: '12px 16px', textAlign: 'center' }}
                          onClick={e => toggleSelectRun(r.id, e)}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => {}}
                          />
                        </td>
                        <td style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--color-primary)' }}>
                          {r.name}
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
                          {new Date(r.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </>
      ) : (
        /* Datasets Tab */
        <div style={{
          backgroundColor: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: '6px',
          overflow: 'hidden'
        }}>
          {datasets.length === 0 ? (
            <div style={{ padding: '60px 20px', textAlign: 'center', color: 'var(--color-text-secondary)' }}>
              <Database size={40} style={{ color: 'var(--color-border)', margin: '0 auto 12px' }} />
              <p style={{ fontSize: '15px', marginBottom: '8px' }}>No uploaded datasets in this project yet.</p>
              <p style={{ fontSize: '13px', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
                Upload a CSV or JSON dataset when configuring a new benchmark run.
              </p>
              <button
                onClick={() => onNewRun(projectId)}
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
                Create Run with Dataset
              </button>
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
              <thead>
                <tr style={{ backgroundColor: 'var(--color-bg-secondary)', borderBottom: '1px solid var(--color-border)' }}>
                  <th style={{ padding: '10px 16px', fontWeight: 600 }}>Original Filename</th>
                  <th style={{ padding: '10px 16px', fontWeight: 600 }}>Format</th>
                  <th style={{ padding: '10px 16px', fontWeight: 600 }}>Rows</th>
                  <th style={{ padding: '10px 16px', fontWeight: 600 }}>Columns</th>
                  <th style={{ padding: '10px 16px', fontWeight: 600 }}>Size</th>
                  <th style={{ padding: '10px 16px', fontWeight: 600 }}>SHA-256 Checksum</th>
                  <th style={{ padding: '10px 16px', fontWeight: 600 }}>Status</th>
                  <th style={{ padding: '10px 16px', textAlign: 'right', fontWeight: 600 }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {datasets.map(d => (
                  <tr key={d.id} style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
                    <td style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                      {d.original_filename}
                    </td>
                    <td style={{ padding: '12px 16px', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
                      {d.format.toUpperCase()}
                    </td>
                    <td style={{ padding: '12px 16px', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
                      {d.row_count}
                    </td>
                    <td style={{ padding: '12px 16px', fontSize: '13px' }}>
                      {d.columns.join(', ')}
                    </td>
                    <td style={{ padding: '12px 16px', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
                      {(d.size_bytes / 1024).toFixed(1)} KB
                    </td>
                    <td style={{ padding: '12px 16px', fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--color-text-muted)' }}>
                      {d.checksum.slice(0, 12)}...
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{
                        display: 'inline-block',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        backgroundColor: 'var(--color-success-bg)',
                        color: 'var(--color-success)',
                        fontSize: '12px',
                        fontWeight: 600,
                      }}>
                        {d.validation_status}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                      <button
                        onClick={() => handleDeleteDataset(d.id, d.original_filename)}
                        title="Delete Dataset"
                        style={{
                          background: 'none',
                          border: 'none',
                          color: 'var(--color-error)',
                          cursor: 'pointer',
                          padding: '4px',
                        }}
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
};
