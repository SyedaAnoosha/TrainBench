import React from 'react';
import { Activity, Layers, PlayCircle, Server } from 'lucide-react';

interface NavigationProps {
  currentTab: string;
  onSelectTab: (tab: string) => void;
  systemHealthy: boolean;
}

export const Navigation: React.FC<NavigationProps> = ({ currentTab, onSelectTab, systemHealthy }) => {
  return (
    <header style={{
      backgroundColor: 'var(--color-surface)',
      borderBottom: '1px solid var(--color-border)',
      padding: '0 24px',
      height: '60px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      position: 'sticky',
      top: 0,
      zIndex: 100
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
        <div 
          onClick={() => onSelectTab('dashboard')} 
          style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}
        >
          <div style={{
            width: '28px',
            height: '28px',
            backgroundColor: 'var(--color-primary)',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#FFF',
            fontWeight: 700,
            fontSize: '14px'
          }}>
            TB
          </div>
          <span style={{ fontSize: '18px', fontWeight: 650, letterSpacing: '-0.3px', color: 'var(--color-text-primary)' }}>
            TrainBench
          </span>
          <span style={{
            fontSize: '11px',
            fontFamily: 'var(--font-mono)',
            backgroundColor: 'var(--color-bg-secondary)',
            color: 'var(--color-text-secondary)',
            padding: '2px 6px',
            borderRadius: '3px'
          }}>
            v0.1.0
          </span>
        </div>

        <nav style={{ display: 'flex', gap: '4px' }}>
          {[
            { id: 'dashboard', label: 'Dashboard', icon: Activity },
            { id: 'projects', label: 'Projects', icon: Layers },
            { id: 'runs', label: 'Runs History', icon: PlayCircle },
            { id: 'system', label: 'Diagnostics', icon: Server },
          ].map(item => {
            const Icon = item.icon;
            const active = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 14px',
                  border: 'none',
                  borderRadius: '4px',
                  backgroundColor: active ? 'var(--color-bg-secondary)' : 'transparent',
                  color: active ? 'var(--color-primary)' : 'var(--color-text-secondary)',
                  fontWeight: active ? 600 : 500,
                  fontSize: '14px',
                  transition: 'all 0.15s ease'
                }}
              >
                <Icon size={16} />
                {item.label}
              </button>
            );
          })}
        </nav>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          fontSize: '12px',
          fontFamily: 'var(--font-mono)',
          padding: '4px 10px',
          backgroundColor: systemHealthy ? 'var(--color-success-bg)' : 'var(--color-error-bg)',
          color: systemHealthy ? 'var(--color-success)' : 'var(--color-error)',
          borderRadius: '12px',
          border: `1px solid ${systemHealthy ? '#BBF7D0' : '#FECACA'}`
        }}>
          <div style={{
            width: '7px',
            height: '7px',
            borderRadius: '50%',
            backgroundColor: systemHealthy ? 'var(--color-success)' : 'var(--color-error)'
          }} />
          {systemHealthy ? 'API ONLINE' : 'DISCONNECTED'}
        </div>
      </div>
    </header>
  );
};
