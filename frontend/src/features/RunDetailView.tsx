import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { RunDetail, MetricPoint } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import {
  ArrowLeft,
  RotateCw,
  Ban,
  Download,
  Copy,
  Check,
  ShieldCheck,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface RunDetailViewProps {
  runId: string;
  onBack: () => void;
  onNavigateRun: (runId: string) => void;
}

export const RunDetailView: React.FC<RunDetailViewProps> = ({
  runId,
  onBack,
  onNavigateRun,
}) => {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [metrics, setMetrics] = useState<MetricPoint[]>([]);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [reproducing, setReproducing] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  const loadData = async () => {
    try {
      const [runData, metricsData] = await Promise.all([
        api.getRun(runId),
        api.getRunMetrics(runId),
      ]);
      setRun(runData);
      setMetrics(metricsData.points || []);
    } catch (err) {
      console.error('Failed to load run detail:', err);
    }
  };

  useEffect(() => {
    loadData();
    let terminalMetricRefreshes = 0;
    const interval = setInterval(() => {
      if (!run || run.status === 'running' || run.status === 'queued') {
        loadData();
      } else if (run.status === 'succeeded' && metrics.length === 0 && terminalMetricRefreshes < 3) {
        terminalMetricRefreshes += 1;
        loadData();
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [runId, run?.status, metrics.length]);

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(label);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const handleCancel = async () => {
    if (!confirm('Are you sure you want to cancel this training run?')) return;
    setCancelling(true);
    try {
      await api.cancelRun(runId);
      await loadData();
    } catch (err: any) {
      alert(`Cancellation error: ${err.message}`);
    } finally {
      setCancelling(false);
    }
  };

  const handleReproduce = async () => {
    setReproducing(true);
    try {
      const child = await api.reproduceRun(runId);
      onNavigateRun(child.id);
    } catch (err: any) {
      alert(`Reproduction error: ${err.message}`);
      setReproducing(false);
    }
  };

  if (!run) {
    return <div style={{ padding: '60px', textAlign: 'center' }}>Loading experiment run details...</div>;
  }

  // Format metric series for Recharts
  const chartDataMap: Record<number, any> = {};
  metrics.forEach(p => {
    if (!chartDataMap[p.step]) {
      chartDataMap[p.step] = { step: p.step };
    }
    const key = p.split === 'train' ? `train_${p.name}` : `val_${p.name}`;
    chartDataMap[p.step][key] = p.value;
  });
  const chartData = Object.values(chartDataMap).sort((a, b) => a.step - b.step);

  const hasAccuracy = metrics.some(p => p.name === 'accuracy');
  const hasR2 = metrics.some(p => p.name === 'r2_score');

  return (
    <div style={{ padding: '32px 40px', maxWidth: '1280px', margin: '0 auto' }}>
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
        <ArrowLeft size={16} /> Back to Project Runs
      </button>

      {/* Header Banner */}
      <div style={{
        backgroundColor: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '6px',
        padding: '24px 28px',
        marginBottom: '24px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
            <h1 style={{ fontSize: '24px', fontWeight: 650, color: 'var(--color-text-primary)' }}>
              {run.name}
            </h1>
            <StatusBadge status={run.status} />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '13px', color: 'var(--color-text-secondary)' }}>
            <span style={{ fontFamily: 'var(--font-mono)' }}>ID: {run.id}</span>
            <span>•</span>
            <span>Framework: <strong style={{ color: 'var(--color-text-primary)' }}>{run.framework.toUpperCase()}</strong></span>
            <span>•</span>
            <span>Task: <strong style={{ color: 'var(--color-text-primary)' }}>{run.task}</strong></span>
            {run.duration_ms && (
              <>
                <span>•</span>
                <span>Duration: <strong>{(run.duration_ms / 1000).toFixed(2)}s</strong></span>
              </>
            )}
            {run.parent_run_id && (
              <>
                <span>•</span>
                <span
                  onClick={() => onNavigateRun(run.parent_run_id!)}
                  style={{ color: 'var(--color-primary)', cursor: 'pointer', fontWeight: 600 }}
                >
                  Parent: {run.parent_run_id}
                </span>
              </>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          {(run.status === 'running' || run.status === 'queued') && (
            <button
              onClick={handleCancel}
              disabled={cancelling}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 14px',
                backgroundColor: 'var(--color-error-bg)',
                color: 'var(--color-error)',
                border: '1px solid #FECACA',
                borderRadius: '4px',
                fontWeight: 600,
                fontSize: '13px'
              }}
            >
              <Ban size={15} />
              {cancelling ? 'Cancelling...' : 'Cancel Run'}
            </button>
          )}

          <button
            onClick={handleReproduce}
            disabled={reproducing}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 16px',
              backgroundColor: 'var(--color-primary)',
              color: '#FFF',
              border: 'none',
              borderRadius: '4px',
              fontWeight: 600,
              fontSize: '13px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
            }}
          >
            <RotateCw size={15} />
            {reproducing
              ? 'Starting Run...'
              : run.status === 'succeeded' && metrics.length === 0
                ? 'Re-run to Generate Metrics'
                : 'Reproduce Run'}
          </button>
        </div>
      </div>

      {/* Terminal Error alert if failed */}
      {run.terminal_error && (
        <div style={{
          padding: '16px 20px',
          backgroundColor: 'var(--color-error-bg)',
          color: 'var(--color-error)',
          borderRadius: '6px',
          marginBottom: '24px',
          border: '1px solid #FECACA',
          fontSize: '14px'
        }}>
          <strong>Execution Failure ({run.terminal_error_code || 'ERROR'}):</strong>
          <pre style={{ marginTop: '8px', fontSize: '13px', whiteSpace: 'pre-wrap' }}>{run.terminal_error}</pre>
        </div>
      )}

      {/* Grid: Charts & Provenance */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px', marginBottom: '24px' }}>
        {/* Charts Panel */}
        <div style={{
          backgroundColor: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: '6px',
          padding: '24px'
        }}>
          <h2 style={{ fontSize: '16px', fontWeight: 650, marginBottom: '16px' }}>Training & Validation Loss</h2>
          {chartData.length > 0 ? (
            <div style={{ height: '260px', width: '100%', marginBottom: '32px' }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E7E5E4" />
                  <XAxis dataKey="step" tick={{ fontSize: 12, fill: '#78716C' }} />
                  <YAxis tick={{ fontSize: 12, fill: '#78716C' }} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="train_loss" stroke="#B45309" strokeWidth={2} dot={false} name="Train Loss" />
                  <Line type="monotone" dataKey="val_loss" stroke="#164E63" strokeWidth={2} dot={false} name="Val Loss" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div style={{ minHeight: '200px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '10px', color: 'var(--color-text-muted)', textAlign: 'center', padding: '24px' }}>
              <strong style={{ color: 'var(--color-text-primary)' }}>
                {run.status === 'running' || run.status === 'queued'
                  ? 'Metrics will appear when the first epoch completes.'
                  : run.status === 'succeeded'
                    ? 'This run completed without saved metric points.'
                    : 'No metric points are available for this run.'}
              </strong>
              {run.status === 'succeeded' && (
                <span>
                  It may have been created before metric capture was fully available. Re-run it to generate comparable training and validation metrics.
                </span>
              )}
            </div>
          )}

          {(hasAccuracy || hasR2) && (
            <>
              <h2 style={{ fontSize: '16px', fontWeight: 650, marginBottom: '16px' }}>
                {hasAccuracy ? 'Validation Accuracy' : 'Validation R² Score'}
              </h2>
              <div style={{ height: '220px', width: '100%' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E7E5E4" />
                    <XAxis dataKey="step" tick={{ fontSize: 12, fill: '#78716C' }} />
                    <YAxis tick={{ fontSize: 12, fill: '#78716C' }} domain={hasAccuracy ? [0, 1] : ['auto', 'auto']} />
                    <Tooltip />
                    <Legend />
                    {hasAccuracy && (
                      <Line type="monotone" dataKey="val_accuracy" stroke="#166534" strokeWidth={2} dot={{ r: 3 }} name="Val Accuracy" />
                    )}
                    {hasR2 && (
                      <Line type="monotone" dataKey="val_r2_score" stroke="#166534" strokeWidth={2} dot={{ r: 3 }} name="Val R² Score" />
                    )}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </>
          )}
        </div>

        {/* Provenance Card */}
        <div style={{
          backgroundColor: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: '6px',
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          gap: '20px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid var(--color-border-subtle)', paddingBottom: '12px' }}>
            <ShieldCheck size={20} color="var(--color-primary)" />
            <h2 style={{ fontSize: '16px', fontWeight: 650 }}>Immutable Provenance</h2>
          </div>

          <div>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-secondary)', display: 'block', marginBottom: '4px' }}>
              CONFIG FINGERPRINT (SHA-256)
            </span>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              backgroundColor: 'var(--color-bg)',
              padding: '8px 12px',
              borderRadius: '4px',
              border: '1px solid var(--color-border)',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              wordBreak: 'break-all'
            }}>
              <span>{run.provenance?.config_hash || '-'}</span>
              {run.provenance?.config_hash && (
                <button
                  onClick={() => handleCopy(run.provenance!.config_hash, 'config')}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '2px', marginLeft: '6px' }}
                >
                  {copiedHash === 'config' ? <Check size={14} color="var(--color-success)" /> : <Copy size={14} />}
                </button>
              )}
            </div>
          </div>

          <div>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-secondary)', display: 'block', marginBottom: '4px' }}>
              DATASET FINGERPRINT (SHA-256)
            </span>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              backgroundColor: 'var(--color-bg)',
              padding: '8px 12px',
              borderRadius: '4px',
              border: '1px solid var(--color-border)',
              fontFamily: 'var(--font-mono)',
              fontSize: '11px',
              wordBreak: 'break-all'
            }}>
              <span>{run.provenance?.dataset_hash || '-'}</span>
            </div>
          </div>

          <div>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-secondary)', display: 'block', marginBottom: '4px' }}>
              RANDOM SEED & HARDWARE
            </span>
            <div style={{ fontSize: '13px', fontFamily: 'var(--font-mono)', color: 'var(--color-text-primary)' }}>
              Seed: <strong>{run.provenance?.seed ?? 42}</strong> • Device: <strong>{run.provenance?.device?.toUpperCase() ?? 'CPU'}</strong>
            </div>
          </div>

          {run.provenance?.dependencies && (
            <div>
              <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--color-text-secondary)', display: 'block', marginBottom: '4px' }}>
                DEPENDENCY SNAPSHOT
              </span>
              <div style={{ backgroundColor: 'var(--color-bg)', padding: '10px', borderRadius: '4px', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
                {Object.entries(run.provenance.dependencies).map(([pkg, ver]) => (
                  <div key={pkg} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span>{pkg}:</span>
                    <strong>{ver}</strong>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Artifacts and Events Section */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        {/* Artifacts Panel */}
        <div style={{
          backgroundColor: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: '6px',
          padding: '24px'
        }}>
          <h2 style={{ fontSize: '16px', fontWeight: 650, marginBottom: '16px' }}>
            Generated Checkpoints & Artifacts ({run.artifacts.length})
          </h2>

          {run.artifacts.length === 0 ? (
            <p style={{ color: 'var(--color-text-muted)', fontSize: '14px' }}>No saved checkpoints for this run.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {run.artifacts.map(art => (
                <div
                  key={art.id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '12px 16px',
                    backgroundColor: 'var(--color-bg)',
                    borderRadius: '4px',
                    border: '1px solid var(--color-border)'
                  }}
                >
                  <div>
                    <strong style={{ fontSize: '14px', display: 'block' }}>{art.filename}</strong>
                    <span style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--color-text-muted)' }}>
                      {(art.size_bytes / 1024).toFixed(1)} KB • SHA-256: {art.checksum.slice(0, 12)}...
                    </span>
                  </div>
                  <a
                    href={art.download_url}
                    download={art.filename}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '6px 12px',
                      backgroundColor: 'var(--color-surface)',
                      border: '1px solid var(--color-border)',
                      borderRadius: '4px',
                      color: 'var(--color-primary)',
                      fontSize: '13px',
                      fontWeight: 600,
                      textDecoration: 'none'
                    }}
                  >
                    <Download size={14} /> Download
                  </a>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Execution Events Timeline */}
        <div style={{
          backgroundColor: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: '6px',
          padding: '24px'
        }}>
          <h2 style={{ fontSize: '16px', fontWeight: 650, marginBottom: '16px' }}>Execution Events Timeline</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {run.events.map(ev => (
              <div
                key={ev.id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: '13px',
                  borderBottom: '1px solid var(--color-border-subtle)',
                  paddingBottom: '8px'
                }}
              >
                <div>
                  <strong style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-text-primary)' }}>
                    {ev.event_type}
                  </strong>
                </div>
                <span style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {new Date(ev.occurred_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
