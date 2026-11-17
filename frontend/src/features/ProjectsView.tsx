import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Project } from '../api/client';
import { Plus, ArrowRight, Folder } from 'lucide-react';

interface ProjectsViewProps {
  onSelectProject: (projectId: string) => void;
}

export const ProjectsView: React.FC<ProjectsViewProps> = ({ onSelectProject }) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadProjects = async () => {
    try {
      const data = await api.listProjects();
      setProjects(data);
    } catch (err: any) {
      setError(err.message);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const created = await api.createProject({ name: name.trim(), description: description.trim() || undefined });
      setName('');
      setDescription('');
      setShowCreateModal(false);
      await loadProjects();
      onSelectProject(created.id);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ padding: '32px 40px', maxWidth: '1280px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 650, color: 'var(--color-text-primary)', marginBottom: '4px' }}>
            Projects
          </h1>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: '15px' }}>
            Workspaces containing machine-learning benchmark suites and experiment histories.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
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
          }}
        >
          <Plus size={18} />
          New Project
        </button>
      </div>

      {error && (
        <div style={{
          padding: '12px 16px',
          backgroundColor: 'var(--color-error-bg)',
          color: 'var(--color-error)',
          borderRadius: '4px',
          marginBottom: '24px',
          border: '1px solid #FECACA',
          fontSize: '14px'
        }}>
          {error}
        </div>
      )}

      {/* Projects Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
        gap: '20px'
      }}>
        {projects.map(p => (
          <div
            key={p.id}
            onClick={() => onSelectProject(p.id)}
            style={{
              backgroundColor: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: '6px',
              padding: '24px',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              transition: 'border-color 0.15s ease, box-shadow 0.15s ease',
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = 'var(--color-primary)';
              e.currentTarget.style.boxShadow = '0 2px 6px rgba(0,0,0,0.06)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = 'var(--color-border)';
              e.currentTarget.style.boxShadow = 'none';
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <Folder size={18} color="var(--color-primary)" />
                <h3 style={{ fontSize: '17px', fontWeight: 650, color: 'var(--color-text-primary)' }}>
                  {p.name}
                </h3>
              </div>
              <p style={{
                color: 'var(--color-text-secondary)',
                fontSize: '14px',
                marginBottom: '20px',
                minHeight: '42px',
                lineHeight: 1.4
              }}>
                {p.description || 'No description provided.'}
              </p>
            </div>

            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              borderTop: '1px solid var(--color-border-subtle)',
              paddingTop: '16px',
              fontSize: '13px',
              color: 'var(--color-text-muted)'
            }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--color-text-secondary)' }}>
                {p.run_count} {p.run_count === 1 ? 'run' : 'runs'}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--color-primary)', fontWeight: 600 }}>
                Open workspace <ArrowRight size={14} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Create Project Modal */}
      {showCreateModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.4)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'var(--color-surface-elevated)',
            borderRadius: '8px',
            padding: '28px',
            width: '100%',
            maxWidth: '480px',
            border: '1px solid var(--color-border)',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.15)'
          }}>
            <h2 style={{ fontSize: '18px', fontWeight: 650, marginBottom: '8px' }}>Create New Project</h2>
            <p style={{ color: 'var(--color-text-secondary)', fontSize: '14px', marginBottom: '20px' }}>
              Set up a project to organize model experiments and benchmarks.
            </p>
            <form onSubmit={handleCreate}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                  Project Name *
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="e.g. PyTorch vs NumPy Linear Benchmarks"
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    border: '1px solid var(--color-border)',
                    borderRadius: '4px',
                    outline: 'none',
                  }}
                />
              </div>

              <div style={{ marginBottom: '24px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                  Description (Optional)
                </label>
                <textarea
                  rows={3}
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  placeholder="Explain the objectives, models, or comparative goals..."
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    border: '1px solid var(--color-border)',
                    borderRadius: '4px',
                    outline: 'none',
                    resize: 'vertical'
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  style={{
                    padding: '8px 16px',
                    backgroundColor: 'transparent',
                    border: '1px solid var(--color-border)',
                    borderRadius: '4px',
                    fontSize: '14px',
                    fontWeight: 500
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || !name.trim()}
                  style={{
                    padding: '8px 18px',
                    backgroundColor: 'var(--color-primary)',
                    color: '#FFF',
                    border: 'none',
                    borderRadius: '4px',
                    fontSize: '14px',
                    fontWeight: 600
                  }}
                >
                  {submitting ? 'Creating...' : 'Create Project'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
