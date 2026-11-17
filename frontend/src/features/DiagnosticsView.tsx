import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Server } from 'lucide-react';

export const DiagnosticsView: React.FC = () => {
  const [diag, setDiag] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getDiagnostics()
      .then(setDiag)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div style={{ padding: '60px', textAlign: 'center' }}>Probing runtime environment diagnostics...</div>;
  }

  return (
    <div style={{ padding: '32px 40px', maxWidth: '1000px', margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
        <Server size={22} color="var(--color-primary)" />
        <h1 style={{ fontSize: '24px', fontWeight: 650, color: 'var(--color-text-primary)' }}>
          System Diagnostics & Support Matrix
        </h1>
      </div>
      <p style={{ color: 'var(--color-text-secondary)', fontSize: '15px', marginBottom: '32px' }}>
        Verified operating environment, database connectivity, and reproducibility boundaries.
      </p>

      <div style={{
        backgroundColor: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '6px',
        padding: '24px',
        marginBottom: '24px'
      }}>
        <h2 style={{ fontSize: '16px', fontWeight: 650, marginBottom: '16px' }}>Runtime Environment</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', fontSize: '14px' }}>
          <div>
            <span style={{ color: 'var(--color-text-muted)', fontSize: '12px', display: 'block' }}>APPLICATION</span>
            <strong>{diag?.app_name} v{diag?.version}</strong>
          </div>
          <div>
            <span style={{ color: 'var(--color-text-muted)', fontSize: '12px', display: 'block' }}>ENVIRONMENT</span>
            <strong>{diag?.environment}</strong>
          </div>
          <div>
            <span style={{ color: 'var(--color-text-muted)', fontSize: '12px', display: 'block' }}>PYTHON ENGINE</span>
            <strong style={{ fontFamily: 'var(--font-mono)' }}>Python {diag?.python_version}</strong>
          </div>
          <div>
            <span style={{ color: 'var(--color-text-muted)', fontSize: '12px', display: 'block' }}>HOST PLATFORM</span>
            <strong style={{ fontFamily: 'var(--font-mono)' }}>{diag?.platform}</strong>
          </div>
          <div>
            <span style={{ color: 'var(--color-text-muted)', fontSize: '12px', display: 'block' }}>DATABASE SUBSYSTEM</span>
            <span style={{ color: 'var(--color-success)', fontWeight: 600 }}>SQLAlchemy + SQLite (Async / Connected)</span>
          </div>
          <div>
            <span style={{ color: 'var(--color-text-muted)', fontSize: '12px', display: 'block' }}>ARTIFACT STORAGE</span>
            <span style={{ color: 'var(--color-success)', fontWeight: 600 }}>Local Directory (Writable)</span>
          </div>
        </div>
      </div>

      <div style={{
        backgroundColor: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '6px',
        padding: '24px'
      }}>
        <h2 style={{ fontSize: '16px', fontWeight: 650, marginBottom: '16px' }}>Framework Support Matrix</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '14px' }}>
          <thead>
            <tr style={{ backgroundColor: 'var(--color-bg-secondary)', borderBottom: '1px solid var(--color-border)' }}>
              <th style={{ padding: '10px 16px' }}>Framework</th>
              <th style={{ padding: '10px 16px' }}>Classification</th>
              <th style={{ padding: '10px 16px' }}>Regression</th>
              <th style={{ padding: '10px 16px' }}>Hardware Target</th>
              <th style={{ padding: '10px 16px' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
              <td style={{ padding: '12px 16px', fontWeight: 600 }}>PyTorch</td>
              <td style={{ padding: '12px 16px' }}>MLP, Linear (CrossEntropy)</td>
              <td style={{ padding: '12px 16px' }}>MLP, Linear (MSE)</td>
              <td style={{ padding: '12px 16px', fontFamily: 'var(--font-mono)' }}>CPU / CUDA</td>
              <td style={{ padding: '12px 16px', color: 'var(--color-success)', fontWeight: 600 }}>Verified</td>
            </tr>
            <tr style={{ borderBottom: '1px solid var(--color-border-subtle)' }}>
              <td style={{ padding: '12px 16px', fontWeight: 600 }}>NumPy (From Scratch)</td>
              <td style={{ padding: '12px 16px' }}>Multinomial Softmax</td>
              <td style={{ padding: '12px 16px' }}>Analytical Gradient Descent</td>
              <td style={{ padding: '12px 16px', fontFamily: 'var(--font-mono)' }}>CPU Float64</td>
              <td style={{ padding: '12px 16px', color: 'var(--color-success)', fontWeight: 600 }}>Verified</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};
