import React from 'react';
import type { RunStatus } from '../api/client';
import { Clock, Play, CheckCircle2, XCircle, Ban } from 'lucide-react';

interface StatusBadgeProps {
  status: RunStatus;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const configs = {
    queued: {
      label: 'Queued',
      bg: 'var(--color-bg-secondary)',
      color: 'var(--color-text-secondary)',
      border: 'var(--color-border)',
      icon: Clock,
    },
    running: {
      label: 'Running',
      bg: 'var(--color-info-bg)',
      color: 'var(--color-info)',
      border: '#A5F3FC',
      icon: Play,
    },
    succeeded: {
      label: 'Succeeded',
      bg: 'var(--color-success-bg)',
      color: 'var(--color-success)',
      border: '#BBF7D0',
      icon: CheckCircle2,
    },
    failed: {
      label: 'Failed',
      bg: 'var(--color-error-bg)',
      color: 'var(--color-error)',
      border: '#FECACA',
      icon: XCircle,
    },
    cancelled: {
      label: 'Cancelled',
      bg: 'var(--color-warning-bg)',
      color: 'var(--color-warning)',
      border: '#FEF08A',
      icon: Ban,
    },
  };

  const cfg = configs[status] || configs.queued;
  const Icon = cfg.icon;

  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '5px',
      padding: '3px 8px',
      borderRadius: '4px',
      fontSize: '12px',
      fontWeight: 600,
      fontFamily: 'var(--font-mono)',
      textTransform: 'uppercase',
      letterSpacing: '0.3px',
      backgroundColor: cfg.bg,
      color: cfg.color,
      border: `1px solid ${cfg.border}`,
    }}>
      <Icon size={12} />
      {cfg.label}
    </span>
  );
};
