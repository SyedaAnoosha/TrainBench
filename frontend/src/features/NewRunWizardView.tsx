import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { Dataset, Framework, TaskType } from '../api/client';
import { ArrowLeft, Check, PlayCircle, ShieldCheck, Database, Cpu, Sliders, Eye, Upload, CheckCircle2, AlertCircle } from 'lucide-react';

interface NewRunWizardProps {
  projectId: string;
  onBack: () => void;
  onRunCreated: (runId: string) => void;
}

export const NewRunWizardView: React.FC<NewRunWizardProps> = ({
  projectId,
  onBack,
  onRunCreated,
}) => {
  const [step, setStep] = useState<number>(1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form State
  const [runName, setRunName] = useState('Experiment Run #1');
  const [task, setTask] = useState<TaskType>('classification');
  const [framework, setFramework] = useState<Framework>('pytorch');

  // Step 1: Dataset options
  const [datasetMode, setDatasetMode] = useState<'synthetic' | 'upload' | 'existing'>('synthetic');
  const [datasetName] = useState('synthetic_benchmark');
  const [nSamples, setNSamples] = useState<number>(500);
  const [nFeatures, setNFeatures] = useState<number>(10);
  const [nClasses, setNClasses] = useState<number>(3);
  const [noise, setNoise] = useState<number>(0.1);
  const [valSplit, setValSplit] = useState<number>(0.2);

  // Upload state
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadedDataset, setUploadedDataset] = useState<Dataset | null>(null);
  const [targetColumn, setTargetColumn] = useState<string>('');

  // Existing datasets in project
  const [projectDatasets, setProjectDatasets] = useState<Dataset[]>([]);
  const [loadingDatasets, setLoadingDatasets] = useState(false);

  useEffect(() => {
    if (datasetMode === 'existing') {
      setLoadingDatasets(true);
      api.listProjectDatasets(projectId)
        .then(data => {
          setProjectDatasets(data);
          if (data.length > 0 && !uploadedDataset) {
            setUploadedDataset(data[0]);
            if (data[0].columns.length > 0) {
              setTargetColumn(data[0].columns[data[0].columns.length - 1]);
            }
          }
        })
        .catch(err => setUploadError(err.message))
        .finally(() => setLoadingDatasets(false));
    }
  }, [datasetMode, projectId]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadError(null);

    try {
      const ds = await api.uploadDataset(projectId, file);
      setUploadedDataset(ds);
      // Auto-select last column as default target candidate
      if (ds.columns.length > 0) {
        setTargetColumn(ds.columns[ds.columns.length - 1]);
      }
    } catch (err: any) {
      setUploadError(err.message);
    } finally {
      setUploading(false);
    }
  };

  // Step 2: Model
  const [architecture, setArchitecture] = useState('mlp');
  const [hiddenDims, setHiddenDims] = useState('64, 32');
  const [activation, setActivation] = useState('relu');

  // Step 3: Hyperparameters
  const [epochs, setEpochs] = useState<number>(15);
  const [batchSize, setBatchSize] = useState<number>(32);
  const [learningRate, setLearningRate] = useState<number>(0.01);
  const [optimizer, setOptimizer] = useState<string>('adam');
  const [seed, setSeed] = useState<number>(42);

  const canContinueFromStep1 = () => {
    if (datasetMode === 'synthetic') return true;
    return !!uploadedDataset && !!targetColumn.trim();
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);

    const dims = architecture === 'linear' 
      ? [] 
      : hiddenDims.split(',').map(s => parseInt(s.trim(), 10)).filter(n => !isNaN(n) && n > 0);

    const isUploaded = datasetMode !== 'synthetic' && uploadedDataset;

    const datasetPayload = isUploaded
      ? {
          name: uploadedDataset.original_filename,
          task_type: task,
          source: 'uploaded',
          dataset_id: uploadedDataset.id,
          target_column: targetColumn,
          val_split: Number(valSplit),
          n_samples: uploadedDataset.row_count,
          n_features: Math.max(1, uploadedDataset.columns.length - 1),
        }
      : {
          name: datasetName,
          task_type: task,
          source: 'synthetic',
          n_samples: Number(nSamples),
          n_features: Number(nFeatures),
          n_classes: task === 'classification' ? Number(nClasses) : undefined,
          noise: Number(noise),
          val_split: Number(valSplit),
        };

    const payload = {
      project_id: projectId,
      name: runName.trim() || 'Experiment Run',
      framework,
      task,
      dataset: datasetPayload,
      model: {
        architecture,
        hidden_dims: dims,
        activation,
        dropout: 0.0,
      },
      hyperparameters: {
        epochs: Number(epochs),
        batch_size: Number(batchSize),
        learning_rate: Number(learningRate),
        optimizer,
        weight_decay: 0.0,
      },
      seed: Number(seed),
      device: 'cpu',
      tags: ['benchmark', framework, task],
    };

    try {
      const created = await api.createRun(payload);
      onRunCreated(created.id);
    } catch (err: any) {
      setError(err.message);
      setSubmitting(false);
    }
  };

  const steps = [
    { num: 1, title: 'Dataset', icon: Database },
    { num: 2, title: 'Framework & Model', icon: Cpu },
    { num: 3, title: 'Hyperparameters', icon: Sliders },
    { num: 4, title: 'Review & Provenance', icon: Eye },
  ];

  return (
    <div style={{ padding: '32px 40px', maxWidth: '1000px', margin: '0 auto' }}>
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
          marginBottom: '20px',
          padding: 0
        }}
      >
        <ArrowLeft size={16} /> Back to Project
      </button>

      {/* Stepper Header */}
      <div style={{
        backgroundColor: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '6px',
        padding: '20px 28px',
        marginBottom: '24px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        {steps.map(s => {
          const isActive = step === s.num;
          const isDone = step > s.num;
          return (
            <div
              key={s.num}
              onClick={() => s.num < step && setStep(s.num)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                cursor: s.num < step ? 'pointer' : 'default',
                opacity: s.num > step ? 0.5 : 1,
              }}
            >
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                backgroundColor: isDone ? 'var(--color-success)' : (isActive ? 'var(--color-primary)' : 'var(--color-bg-secondary)'),
                color: isDone || isActive ? '#FFF' : 'var(--color-text-secondary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 700,
                fontSize: '13px'
              }}>
                {isDone ? <Check size={16} /> : s.num}
              </div>
              <div>
                <span style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--color-text-muted)', display: 'block', fontWeight: 600 }}>
                  Step {s.num}
                </span>
                <span style={{ fontSize: '14px', fontWeight: 650, color: 'var(--color-text-primary)' }}>
                  {s.title}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {error && (
        <div style={{
          padding: '14px 18px',
          backgroundColor: '#FEE2E2',
          color: '#991B1B',
          borderRadius: '6px',
          marginBottom: '24px',
          border: '1px solid #FECACA',
          fontSize: '14px'
        }}>
          <strong>Configuration Error:</strong> {error}
        </div>
      )}

      {/* Wizard Form Body */}
      <div style={{
        backgroundColor: 'var(--color-surface)',
        border: '1px solid var(--color-border)',
        borderRadius: '6px',
        padding: '32px',
        marginBottom: '24px'
      }}>
        {/* STEP 1: DATASET */}
        {step === 1 && (
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 650, marginBottom: '4px' }}>Step 1: Dataset & Task Definition</h2>
            <p style={{ color: 'var(--color-text-secondary)', fontSize: '14px', marginBottom: '24px' }}>
              Upload your local CSV/JSON dataset, select an existing dataset, or generate synthetic benchmarks.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '24px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Run Name *</label>
                <input
                  type="text"
                  value={runName}
                  onChange={e => setRunName(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: '4px' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Task Type *</label>
                <select
                  value={task}
                  onChange={e => setTask(e.target.value as TaskType)}
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: '4px' }}
                >
                  <option value="classification">Classification (Multi-class / Cross Entropy)</option>
                  <option value="regression">Regression (Continuous / MSE)</option>
                </select>
              </div>
            </div>

            {/* Dataset Mode Tabs */}
            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '8px' }}>Dataset Source</label>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setDatasetMode('synthetic')}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '4px',
                    border: `1px solid ${datasetMode === 'synthetic' ? 'var(--color-primary)' : 'var(--color-border)'}`,
                    backgroundColor: datasetMode === 'synthetic' ? 'var(--color-bg)' : 'transparent',
                    fontWeight: datasetMode === 'synthetic' ? 700 : 500,
                    color: datasetMode === 'synthetic' ? 'var(--color-primary)' : 'inherit',
                  }}
                >
                  Synthetic Generator
                </button>
                <button
                  type="button"
                  onClick={() => setDatasetMode('upload')}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '4px',
                    border: `1px solid ${datasetMode === 'upload' ? 'var(--color-primary)' : 'var(--color-border)'}`,
                    backgroundColor: datasetMode === 'upload' ? 'var(--color-bg)' : 'transparent',
                    fontWeight: datasetMode === 'upload' ? 700 : 500,
                    color: datasetMode === 'upload' ? 'var(--color-primary)' : 'inherit',
                  }}
                >
                  Upload Local File (CSV / JSON)
                </button>
                <button
                  type="button"
                  onClick={() => setDatasetMode('existing')}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '4px',
                    border: `1px solid ${datasetMode === 'existing' ? 'var(--color-primary)' : 'var(--color-border)'}`,
                    backgroundColor: datasetMode === 'existing' ? 'var(--color-bg)' : 'transparent',
                    fontWeight: datasetMode === 'existing' ? 700 : 500,
                    color: datasetMode === 'existing' ? 'var(--color-primary)' : 'inherit',
                  }}
                >
                  Select Existing Dataset
                </button>
              </div>
            </div>

            {/* Mode 1: Upload Local File */}
            {datasetMode === 'upload' && (
              <div style={{
                border: '2px dashed var(--color-border)',
                borderRadius: '6px',
                padding: '24px',
                marginBottom: '20px',
                backgroundColor: 'var(--color-bg)',
                textAlign: 'center'
              }}>
                <Upload size={32} style={{ color: 'var(--color-primary)', margin: '0 auto 12px' }} />
                <h4 style={{ fontSize: '15px', fontWeight: 650, marginBottom: '4px' }}>
                  Choose a dataset from your computer
                </h4>
                <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', marginBottom: '16px' }}>
                  Supports .csv and .json files up to 50MB. File is validated and checksummed before run submission.
                </p>
                <input
                  type="file"
                  accept=".csv,.json"
                  onChange={handleFileUpload}
                  disabled={uploading}
                  style={{ display: 'inline-block', fontSize: '13px' }}
                />
                {uploading && (
                  <p style={{ marginTop: '12px', fontSize: '13px', color: 'var(--color-primary)', fontWeight: 600 }}>
                    Uploading, validating schema, and computing SHA-256 fingerprint...
                  </p>
                )}
                {uploadError && (
                  <div style={{ marginTop: '12px', padding: '8px 12px', backgroundColor: '#FEE2E2', color: '#991B1B', borderRadius: '4px', fontSize: '13px' }}>
                    <AlertCircle size={14} style={{ display: 'inline', marginRight: '6px' }} />
                    {uploadError}
                  </div>
                )}
              </div>
            )}

            {/* Mode 2: Existing Project Datasets */}
            {datasetMode === 'existing' && (
              <div style={{ marginBottom: '20px' }}>
                {loadingDatasets ? (
                  <p style={{ fontSize: '13px', color: 'var(--color-text-muted)' }}>Loading project datasets...</p>
                ) : projectDatasets.length === 0 ? (
                  <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>
                    No datasets uploaded to this project yet. Switch to "Upload Local File" to add one.
                  </p>
                ) : (
                  <div>
                    <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                      Select Project Dataset
                    </label>
                    <select
                      value={uploadedDataset?.id || ''}
                      onChange={e => {
                        const found = projectDatasets.find(d => d.id === e.target.value);
                        if (found) {
                          setUploadedDataset(found);
                          if (found.columns.length > 0) {
                            setTargetColumn(found.columns[found.columns.length - 1]);
                          }
                        }
                      }}
                      style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: '4px' }}
                    >
                      {projectDatasets.map(d => (
                        <option key={d.id} value={d.id}>
                          {d.original_filename} ({d.format.toUpperCase()} â€¢ {d.row_count} rows â€¢ {(d.size_bytes / 1024).toFixed(1)} KB)
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            )}

            {/* Uploaded Dataset Inspection & Column Mapping */}
            {datasetMode !== 'synthetic' && uploadedDataset && (
              <div style={{
                backgroundColor: 'var(--color-surface)',
                border: '1px solid var(--color-border)',
                borderRadius: '6px',
                padding: '16px 20px',
                marginBottom: '20px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', color: 'var(--color-success)' }}>
                  <CheckCircle2 size={18} />
                  <span style={{ fontWeight: 700, fontSize: '14px' }}>Dataset Validated & Attached</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', fontSize: '13px', marginBottom: '16px' }}>
                  <div>
                    <span style={{ color: 'var(--color-text-muted)', display: 'block', fontSize: '11px' }}>FILENAME</span>
                    <strong>{uploadedDataset.original_filename}</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--color-text-muted)', display: 'block', fontSize: '11px' }}>ROWS & COLS</span>
                    <strong>{uploadedDataset.row_count} rows, {uploadedDataset.columns.length} columns</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--color-text-muted)', display: 'block', fontSize: '11px' }}>FORMAT & SIZE</span>
                    <strong>{uploadedDataset.format.toUpperCase()} ({(uploadedDataset.size_bytes / 1024).toFixed(1)} KB)</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--color-text-muted)', display: 'block', fontSize: '11px' }}>CHECKSUM</span>
                    <strong style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                      {uploadedDataset.checksum.slice(0, 12)}...
                    </strong>
                  </div>
                </div>

                {/* Target Column Selection */}
                <div style={{ borderTop: '1px solid var(--color-border-subtle)', paddingTop: '14px' }}>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 650, marginBottom: '6px' }}>
                    Target / Label Column * (Required for {task})
                  </label>
                  <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '8px' }}>
                    Select which column represents the prediction target. All other columns will be used as input features.
                  </p>
                  <select
                    value={targetColumn}
                    onChange={e => setTargetColumn(e.target.value)}
                    style={{ width: '100%', maxWidth: '350px', padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: '4px' }}
                  >
                    <option value="">-- Choose Target Column --</option>
                    {uploadedDataset.columns.map(col => (
                      <option key={col} value={col}>{col}</option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            {/* Mode 3: Synthetic Dataset Parameters */}
            {datasetMode === 'synthetic' && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px', marginBottom: '20px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Sample Count (N)</label>
                  <input
                    type="number"
                    min={50}
                    max={10000}
                    value={nSamples}
                    onChange={e => setNSamples(Number(e.target.value))}
                    style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: '4px' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Input Features (D)</label>
                  <input
                    type="number"
                    min={2}
                    max={200}
                    value={nFeatures}
                    onChange={e => setNFeatures(Number(e.target.value))}
                    style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: '4px' }}
                  />
                </div>

                {task === 'classification' ? (
                  <div>
                    <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Classes (K)</label>
                    <input
                      type="number"
                      min={2}
                      max={20}
                      value={nClasses}
                      onChange={e => setNClasses(Number(e.target.value))}
                      style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: '4px' }}
                    />
                  </div>
                ) : (
                  <div>
                    <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Noise Scale (Ïƒ)</label>
                    <input
                      type="number"
                      step="0.05"
                      min={0.0}
                      max={1.0}
                      value={noise}
                      onChange={e => setNoise(Number(e.target.value))}
                      style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: '4px' }}
                    />
                  </div>
                )}
              </div>
            )}

            {/* Validation Split Slider */}
            <div>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                Validation Split Ratio: {(valSplit * 100).toFixed(0)}%
              </label>
              <input
                type="range"
                min={0.1}
                max={0.4}
                step={0.05}
                value={valSplit}
                onChange={e => setValSplit(Number(e.target.value))}
                style={{ width: '100%', maxWidth: '350px' }}
              />
            </div>
          </div>
        )}

        {/* STEP 2: FRAMEWORK & MODEL */}
        {step === 2 && (
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 650, marginBottom: '4px' }}>Step 2: Framework & Model Architecture</h2>
            <p style={{ color: 'var(--color-text-secondary)', fontSize: '14px', marginBottom: '24px' }}>
              Select either the PyTorch deep learning adapter or the pure NumPy reference implementation.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '24px' }}>
              <div
                onClick={() => { setFramework('pytorch'); setArchitecture('mlp'); }}
                style={{
                  padding: '20px',
                  borderRadius: '6px',
                  border: `2px solid ${framework === 'pytorch' ? 'var(--color-primary)' : 'var(--color-border)'}`,
                  backgroundColor: framework === 'pytorch' ? 'var(--color-bg)' : 'transparent',
                  cursor: 'pointer'
                }}
              >
                <h3 style={{ fontSize: '16px', fontWeight: 650, marginBottom: '6px' }}>PyTorch</h3>
                <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', lineHeight: 1.4 }}>
                  Automatic differentiation, PyTorch tensors, autograd, and modular neural networks.
                </p>
              </div>

              <div
                onClick={() => { setFramework('numpy'); setArchitecture('linear'); }}
                style={{
                  padding: '20px',
                  borderRadius: '6px',
                  border: `2px solid ${framework === 'numpy' ? 'var(--color-primary)' : 'var(--color-border)'}`,
                  backgroundColor: framework === 'numpy' ? 'var(--color-bg)' : 'transparent',
                  cursor: 'pointer'
                }}
              >
                <h3 style={{ fontSize: '16px', fontWeight: 650, marginBottom: '6px' }}>NumPy (From Scratch)</h3>
                <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)', lineHeight: 1.4 }}>
                  Raw mathematical gradient descent, manual backpropagation, float64 numerical stability checks.
                </p>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '20px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Architecture</label>
                <select
                  value={architecture}
                  onChange={e => setArchitecture(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: '4px' }}
                >
                  <option value="linear">Linear / Logistic Regression</option>
                  {framework === 'pytorch' && <option value="mlp">Multi-Layer Perceptron (MLP)</option>}
                </select>
              </div>

              {architecture === 'mlp' && (
                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Activation Function</label>
                  <select
                    value={activation}
                    onChange={e => setActivation(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: '4px' }}
                  >
                    <option value="relu">ReLU</option>
                    <option value="tanh">Tanh</option>
                    <option value="sigmoid">Sigmoid</option>
                  </select>
                </div>
              )}
            </div>

            {architecture === 'mlp' && (
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                  Hidden Layer Dimensions (comma separated)
                </label>
                <input
                  type="text"
                  value={hiddenDims}
                  onChange={e => setHiddenDims(e.target.value)}
                  placeholder="e.g. 64, 32"
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: '4px' }}
                />
              </div>
            )}
          </div>
        )}

        {/* STEP 3: HYPERPARAMETERS */}
        {step === 3 && (
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 650, marginBottom: '4px' }}>Step 3: Training Hyperparameters</h2>
            <p style={{ color: 'var(--color-text-secondary)', fontSize: '14px', marginBottom: '24px' }}>
              Define optimizer, iterations, batch size, and reproducible random seed.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '20px', marginBottom: '20px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Epochs</label>
                <input
                  type="number"
                  min={1}
                  max={500}
                  value={epochs}
                  onChange={e => setEpochs(Number(e.target.value))}
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: '4px' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Batch Size</label>
                <input
                  type="number"
                  min={1}
                  max={1024}
                  value={batchSize}
                  onChange={e => setBatchSize(Number(e.target.value))}
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: '4px' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Learning Rate</label>
                <input
                  type="number"
                  step="0.001"
                  min={0.00001}
                  max={2.0}
                  value={learningRate}
                  onChange={e => setLearningRate(Number(e.target.value))}
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: '4px' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Optimizer</label>
                <select
                  value={optimizer}
                  onChange={e => setOptimizer(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: '4px' }}
                >
                  <option value="adam">Adam</option>
                  <option value="sgd">SGD</option>
                  <option value="rmsprop">RMSprop</option>
                </select>
              </div>
            </div>

            <div style={{ maxWidth: '300px' }}>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>Random Seed (Deterministic)</label>
              <input
                type="number"
                value={seed}
                onChange={e => setSeed(Number(e.target.value))}
                style={{ width: '100%', padding: '8px 12px', border: '1px solid var(--color-border)', borderRadius: '4px' }}
              />
            </div>
          </div>
        )}

        {/* STEP 4: REVIEW & PROVENANCE */}
        {step === 4 && (
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 650, marginBottom: '4px' }}>Step 4: Review & Provenance Verification</h2>
            <p style={{ color: 'var(--color-text-secondary)', fontSize: '14px', marginBottom: '24px' }}>
              Review the immutable snapshot that will be hashed and persisted before execution.
            </p>

            <div style={{
              backgroundColor: 'var(--color-bg)',
              border: '1px solid var(--color-border)',
              borderRadius: '6px',
              padding: '20px',
              marginBottom: '24px'
            }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px', fontSize: '14px' }}>
                <div>
                  <span style={{ color: 'var(--color-text-muted)', fontSize: '12px', display: 'block' }}>EXPERIMENT NAME</span>
                  <strong>{runName}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--color-text-muted)', fontSize: '12px', display: 'block' }}>FRAMEWORK & TASK</span>
                  <strong>{framework.toUpperCase()} â€¢ {task.toUpperCase()}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--color-text-muted)', fontSize: '12px', display: 'block' }}>DATASET SOURCE</span>
                  <strong>
                    {datasetMode !== 'synthetic' && uploadedDataset
                      ? `${uploadedDataset.original_filename} (${uploadedDataset.row_count} rows, target: '${targetColumn}')`
                      : `Synthetic (${nSamples} samples, ${nFeatures} features)`}
                  </strong>
                </div>
                <div>
                  <span style={{ color: 'var(--color-text-muted)', fontSize: '12px', display: 'block' }}>MODEL ARCHITECTURE</span>
                  <strong>{architecture.toUpperCase()} {architecture === 'mlp' ? `(${hiddenDims})` : ''}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--color-text-muted)', fontSize: '12px', display: 'block' }}>HYPERPARAMETERS</span>
                  <strong>{epochs} epochs, lr={learningRate}, batch={batchSize}, opt={optimizer}</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--color-text-muted)', fontSize: '12px', display: 'block' }}>RANDOM SEED & DEVICE</span>
                  <strong>Seed {seed} â€¢ CPU</strong>
                </div>
              </div>
            </div>

            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '16px',
              backgroundColor: 'var(--color-info-bg)',
              border: '1px solid #A5F3FC',
              borderRadius: '6px',
              color: 'var(--color-info)',
              fontSize: '13px'
            }}>
              <ShieldCheck size={24} />
              <div>
                <strong>Reproducibility Guarantee:</strong> TrainBench computes cryptographic SHA-256 fingerprints of your parameters, dataset, and package dependencies before starting worker execution.
              </div>
            </div>
          </div>
        )}

        {/* Navigation Buttons */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: '32px',
          borderTop: '1px solid var(--color-border-subtle)',
          paddingTop: '20px'
        }}>
          {step > 1 ? (
            <button
              onClick={() => setStep(step - 1)}
              style={{
                padding: '8px 16px',
                backgroundColor: 'transparent',
                border: '1px solid var(--color-border)',
                borderRadius: '4px',
                fontSize: '14px',
                fontWeight: 600
              }}
            >
              Back
            </button>
          ) : <div />}

          {step < 4 ? (
            <button
              onClick={() => setStep(step + 1)}
              disabled={step === 1 && !canContinueFromStep1()}
              style={{
                padding: '8px 20px',
                backgroundColor: (step === 1 && !canContinueFromStep1()) ? 'var(--color-border)' : 'var(--color-primary)',
                color: '#FFF',
                border: 'none',
                borderRadius: '4px',
                fontSize: '14px',
                fontWeight: 600,
                cursor: (step === 1 && !canContinueFromStep1()) ? 'not-allowed' : 'pointer'
              }}
            >
              Continue &rarr;
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={submitting}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 24px',
                backgroundColor: 'var(--color-primary)',
                color: '#FFF',
                border: 'none',
                borderRadius: '4px',
                fontSize: '15px',
                fontWeight: 700,
                cursor: submitting ? 'wait' : 'pointer'
              }}
            >
              <PlayCircle size={18} /> {submitting ? 'Starting Training Job...' : 'Start Benchmark Run'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
