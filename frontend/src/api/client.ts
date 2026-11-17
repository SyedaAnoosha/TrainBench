export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
export type Framework = 'pytorch' | 'numpy';
export type TaskType = 'classification' | 'regression';
export type DeviceType = 'cpu' | 'cuda';

export interface Project {
  id: string;
  name: string;
  description?: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
  run_count: number;
}

export interface MetricSummary {
  name: string;
  split: string;
  value: number;
  step: number;
  unit?: string;
}

export interface RunSummary {
  id: string;
  project_id: string;
  name: string;
  status: RunStatus;
  framework: Framework;
  task: TaskType;
  created_at: string;
  duration_ms?: number;
  primary_metric?: MetricSummary;
}

export interface Artifact {
  id: string;
  run_id: string;
  kind: string;
  filename: string;
  checksum: string;
  size_bytes: number;
  download_url: string;
  created_at: string;
}

export interface RunEvent {
  id: number;
  event_type: string;
  payload?: any;
  occurred_at: string;
}

export interface RunDetail {
  id: string;
  project_id: string;
  name: string;
  parent_run_id?: string;
  status: RunStatus;
  framework: Framework;
  task: TaskType;
  created_by: string;
  created_at: string;
  started_at?: string;
  finished_at?: string;
  duration_ms?: number;
  terminal_error?: string;
  terminal_error_code?: string;
  config?: any;
  provenance?: {
    config_hash: string;
    dataset_hash: string;
    seed: number;
    device: string;
    dependencies?: Record<string, string>;
  };
  events: RunEvent[];
  artifacts: Artifact[];
  metrics_summary: Record<string, MetricSummary>;
}

export interface MetricPoint {
  name: string;
  split: string;
  step: number;
  value: number;
  unit?: string;
}

export interface ComparisonResult {
  runs: RunDetail[];
  compatible: boolean;
  incompatibility_reason?: string;
  metric_comparison: Record<string, Record<string, number>>;
  hyperparameter_deltas: Record<string, Record<string, any>>;
}

export interface DatasetColumnInfo {
  name: string;
  dtype: string;
  unique_count: number;
  sample_values: any[];
}

export interface Dataset {
  id: string;
  project_id: string;
  owner_id: string;
  original_filename: string;
  format: string;
  size_bytes: number;
  checksum: string;
  validation_status: string;
  columns: string[];
  column_details?: DatasetColumnInfo[];
  row_count: number;
  created_at: string;
}

const API_BASE = '/api/v1';
const API_KEY = (import.meta.env.VITE_API_KEY as string | undefined) || '';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Correlation-ID': crypto.randomUUID(),
      ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
      ...(options?.headers || {}),
    },
  });

  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const body = await res.json();
      errorDetail = body.detail || body.title || JSON.stringify(body);
    } catch {
      // Keep status text
    }
    throw new Error(typeof errorDetail === 'string' ? errorDetail : JSON.stringify(errorDetail));
  }

  return res.json();
}

export const api = {
  getHealth: () => fetchJson<{ status: string }>(`${API_BASE}/health`),
  getDiagnostics: () => fetchJson<any>(`${API_BASE}/diagnostics`),
  listProjects: () => fetchJson<Project[]>(`${API_BASE}/projects`),
  createProject: (data: { name: string; description?: string }) =>
    fetchJson<Project>(`${API_BASE}/projects`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getProject: (id: string) => fetchJson<Project>(`${API_BASE}/projects/${id}`),
  listRuns: (params?: { projectId?: string; status?: string; framework?: string; task?: string }) => {
    const q = new URLSearchParams();
    if (params?.projectId) q.set('project_id', params.projectId);
    if (params?.status) q.set('status', params.status);
    if (params?.framework) q.set('framework', params.framework);
    if (params?.task) q.set('task', params.task);
    return fetchJson<RunSummary[]>(`${API_BASE}/runs?${q.toString()}`);
  },
  getRun: (id: string) => fetchJson<RunDetail>(`${API_BASE}/runs/${id}`),
  createRun: (data: any) =>
    fetchJson<RunSummary>(`${API_BASE}/runs`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  cancelRun: (id: string) =>
    fetchJson<{ run_id: string; status: string }>(`${API_BASE}/runs/${id}/cancel`, {
      method: 'POST',
    }),
  reproduceRun: (id: string) =>
    fetchJson<RunSummary>(`${API_BASE}/runs/${id}/reproduce`, {
      method: 'POST',
    }),
  getRunMetrics: (runId: string) =>
    fetchJson<{ run_id: string; points: MetricPoint[] }>(`${API_BASE}/runs/${runId}/metrics?max_points=2000`),
  compareRuns: (runIds: string[]) =>
    fetchJson<ComparisonResult>(`${API_BASE}/runs/compare`, {
      method: 'POST',
      body: JSON.stringify({ run_ids: runIds }),
    }),
  uploadDataset: async (projectId: string, file: File, idempotencyKey?: string): Promise<Dataset> => {
    const formData = new FormData();
    formData.append('project_id', projectId);
    formData.append('file', file);

    const headers: Record<string, string> = {
      'X-Correlation-ID': crypto.randomUUID(),
      ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
      ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}),
    };

    const res = await fetch(`${API_BASE}/datasets`, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!res.ok) {
      let errorDetail = res.statusText;
      try {
        const body = await res.json();
        errorDetail = body.detail || body.title || JSON.stringify(body);
      } catch {}
      throw new Error(typeof errorDetail === 'string' ? errorDetail : JSON.stringify(errorDetail));
    }
    return res.json();
  },
  getDataset: (id: string) => fetchJson<Dataset>(`${API_BASE}/datasets/${id}`),
  listProjectDatasets: (projectId: string) => fetchJson<Dataset[]>(`${API_BASE}/projects/${projectId}/datasets`),
  deleteDataset: (id: string) =>
    fetchJson<{ deleted: boolean; dataset_id: string }>(`${API_BASE}/datasets/${id}`, {
      method: 'DELETE',
    }),
};
