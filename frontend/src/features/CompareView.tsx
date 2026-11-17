import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { ComparisonResult } from '../api/client';
import { StatusBadge } from '../components/StatusBadge';
import { ArrowLeft, BarChart2, AlertTriangle, CheckCircle } from 'lucide-react';

interface CompareViewProps {
  runIds: string[];
  onBack: () => void;
  onNavigateRun: (runId: string) => void;
}

export const CompareView: React.FC<CompareViewProps> = ({
  runIds,
  onBack,
  onNavigateRun,
}) => {
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchComparison = async () => {
      setLoading(true);
      try {
        const data = await api.compareRuns(runIds);
        setComparison(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    if (runIds.length >= 2) {
      fetchComparison();
    }
  }, [runIds]);

  if (loading) {
    return <div style={{ padding: '60px', textAlign: 'center' }}>Aligning and comparing experiment runs...</div>;
  }

  if (error || !comparison) {
    return (
      <div style={{ padding: '40px', maxWidth: '800px', margin: '0 auto' }}>
        <button onClick={onBack} style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'none', border: 'none', color: 'var(--color-primary)', fontWeight: 600, marginBottom: '20px' }}>
          <ArrowLeft size={16} /> Back
        </button>
        <div style={{ padding: '20px', backgroundColor: 'var(--color-error-bg)', color: 'var(--color-error)', borderRadius: '6px' }}>
          Failed to load comparison: {error}
        </div>
      </div>
    );
  }

  const { runs, compatible, incompatibility_reason, metric_comparison, hyperparameter_deltas } = comparison;

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
        <ArrowLeft size={16} /> Back to Project
      </button>

      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        backgroundColor: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '6px',
        padding: '24px 28px',
        marginBottom: '24px'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <BarChart2 size={22} color="var(--color-primary)" />
            <h1 style={{ fontSize: '24px', fontWeight: 650, color: 'var(--color-text-primary)' }}>
              Experiment Comparison ({runs.length} Runs)
            </h1>
          </div>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: '14px' }}>
            Side-by-side alignment of hyperparameters, metrics, and execution performance.
          </p>
        </div>

        <div>
          {compatible ? (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              backgroundColor: 'var(--color-success-bg)',
              color: 'var(--color-success)',
              borderRadius: '20px',
              fontSize: '12px',
              fontWeight: 600,
              border: '1px solid #BBF7D0'
            }}>
              <CheckCircle size={14} /> Compatible Tasks
            </div>
          ) : (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              backgroundColor: 'var(--color-warning-bg)',
              color: 'var(--color-warning)',
              borderRadius: '20px',
              fontSize: '12px',
              fontWeight: 600,
              border: '1px solid #FEF08A'
            }}>
              <AlertTriangle size={14} /> {incompatibility_reason}
            </div>
          )}
        </div>
      </div>

      {/* Side by side run headers */}
      <div style={{
        backgroundColor: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '6px',
        overflow: 'hidden',
        marginBottom: '28px'
      }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--color-border)', fontWeight: 650, fontSize: '15px' }}>
          Overview & Execution Summary
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
          <thead>
            <tr style={{ backgroundColor: 'var(--color-bg-secondary)', borderBottom: '1px solid var(--color-border)' }}>
              <th style={{ padding: '12px 16px', width: '220px' }}>Attribute</th>
              {runs.map(r => (
                <th key={r.id} style={{ padding: '12px 16px', fontWeight: 600 }}>
                  <span
                    onClick={() => onNavigateRun(r.id)}
                    style={{ color: 'var(--color-primary)', cursor: 'pointer', textDecoration: 'underline' }}
                  >
                    {r.name}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
              <td style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--color-text-secondary)' }}>Status</td>
              {runs.map(r => (
                <td key={r.id} style={{ padding: '10px 16px' }}>
                  <StatusBadge status={r.status} />
                </td>
              ))}
            </tr>
            <tr style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
              <td style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--color-text-secondary)' }}>Framework</td>
              {runs.map(r => (
                <td key={r.id} style={{ padding: '10px 16px', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
                  {r.framework.toUpperCase()}
                </td>
              ))}
            </tr>
            <tr style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
              <td style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--color-text-secondary)' }}>Task</td>
              {runs.map(r => (
                <td key={r.id} style={{ padding: '10px 16px' }}>{r.task}</td>
              ))}
            </tr>
            <tr style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
              <td style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--color-text-secondary)' }}>Duration</td>
              {runs.map(r => (
                <td key={r.id} style={{ padding: '10px 16px', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
                  {r.duration_ms ? `${(r.duration_ms / 1000).toFixed(2)}s` : '-'}
                </td>
              ))}
            </tr>
            <tr style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
              <td style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--color-text-secondary)' }}>Seed</td>
              {runs.map(r => (
                <td key={r.id} style={{ padding: '10px 16px', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
                  {r.provenance?.seed ?? 42}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>

      {/* Metrics Deltas Table */}
      <div style={{
        backgroundColor: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '6px',
        overflow: 'hidden',
        marginBottom: '28px'
      }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--color-border)', fontWeight: 650, fontSize: '15px' }}>
          Terminal Metrics Comparison
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
          <thead>
            <tr style={{ backgroundColor: 'var(--color-bg-secondary)', borderBottom: '1px solid var(--color-border)' }}>
              <th style={{ padding: '12px 16px', width: '220px' }}>Metric</th>
              {runs.map(r => (
                <th key={r.id} style={{ padding: '12px 16px', fontWeight: 600 }}>{r.name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(metric_comparison).map(([metricKey, valMap]) => (
              <tr key={metricKey} style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
                <td style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--color-text-secondary)', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
                  {metricKey}
                </td>
                {runs.map(r => {
                  const val = valMap[r.id];
                  return (
                    <td key={r.id} style={{ padding: '10px 16px', fontFamily: 'var(--font-mono)', fontSize: '14px', fontWeight: 600 }}>
                      {val !== undefined ? val.toFixed(4) : '-'}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Hyperparameters Deltas Table */}
      <div style={{
        backgroundColor: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '6px',
        overflow: 'hidden'
      }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--color-border)', fontWeight: 650, fontSize: '15px' }}>
          Hyperparameter Configuration Deltas
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
          <thead>
            <tr style={{ backgroundColor: 'var(--color-bg-secondary)', borderBottom: '1px solid var(--color-border)' }}>
              <th style={{ padding: '12px 16px', width: '220px' }}>Parameter</th>
              {runs.map(r => (
                <th key={r.id} style={{ padding: '12px 16px', fontWeight: 600 }}>{r.name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Object.entries(hyperparameter_deltas).map(([paramKey, valMap]) => (
              <tr key={paramKey} style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
                <td style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--color-text-secondary)', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
                  {paramKey}
                </td>
                {runs.map(r => (
                  <td key={r.id} style={{ padding: '10px 16px', fontFamily: 'var(--font-mono)', fontSize: '13px' }}>
                    {valMap[r.id] !== undefined ? String(valMap[r.id]) : '-'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
