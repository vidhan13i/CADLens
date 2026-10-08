import { useState } from 'react';
import axios from 'axios';
import { Upload, Download, Cpu, PencilLine, Loader2 } from 'lucide-react';

import { API } from '../api';


export default function Toolbar({ documentId, mode, setMode, zoom, setZoom, onNewUpload }) {
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    if (!documentId || exporting) return;
    setExporting(true);
    try {
      const response = await axios.get(`${API}/export/${documentId}`, {
        responseType: 'blob',
      });
      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = `balloons_${documentId}.xlsx`;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      }, 1500);
    } catch (err) {
      console.warn('Axios blob export failed, falling back to direct download link...', err);
      // Fallback: direct browser navigation to download attachment
      window.location.href = `${API}/export/${documentId}`;
    } finally {
      setExporting(false);
    }
  };

  return (
    <header className="toolbar glass-panel">
      <div className="toolbar-brand">
        <div className="logo-mark-sm">
          CAD<span className="logo-accent">Lens</span>
        </div>
      </div>

      <div className="toolbar-actions">
        {/* Zoom controls */}
        <div className="zoom-controls">
          <button
            className="zoom-btn"
            onClick={() => setZoom(z => Math.max(0.5, z - 0.25))}
            title="Zoom Out"
          >
            -
          </button>
          <span className="zoom-display">{Math.round(zoom * 100)}%</span>
          <button
            className="zoom-btn"
            onClick={() => setZoom(z => Math.min(3.0, z + 0.25))}
            title="Zoom In"
          >
            +
          </button>
        </div>

        {/* Mode toggle */}
        <div className="mode-toggle">
          <button
            id="btn-auto-mode"
            className={`mode-btn ${mode === 'auto' ? 'mode-btn--active' : ''}`}
            onClick={() => setMode('auto')}
            title="Auto mode — detection only"
          >
            <Cpu size={15} />
            Auto
          </button>
          <button
            id="btn-manual-mode"
            className={`mode-btn ${mode === 'manual' ? 'mode-btn--active' : ''}`}
            onClick={() => setMode('manual')}
            title="Manual mode — click to place balloons"
          >
            <PencilLine size={15} />
            Manual
          </button>
        </div>

        <button
          id="btn-export"
          className="toolbar-btn btn-success"
          onClick={handleExport}
          disabled={!documentId || exporting}
          title="Export balloon table to Excel"
        >
          {exporting ? (
            <>
              <Loader2 size={16} className="spin" />
              Exporting...
            </>
          ) : (
            <>
              <Download size={16} />
              Export Excel
            </>
          )}
        </button>

        <button
          id="btn-new-upload"
          className="toolbar-btn btn-secondary"
          onClick={onNewUpload}
          title="Upload a new PDF"
        >
          <Upload size={16} />
          New PDF
        </button>
      </div>
    </header>
  );
}
