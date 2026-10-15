import { useState, useCallback } from 'react';
import axios from 'axios';
import { Upload, Loader2, FileText } from 'lucide-react';
import Toolbar from './components/Toolbar';
import DrawingCanvas from './components/DrawingCanvas';
import BalloonList from './components/BalloonList';
import './App.css';

import { API } from './api';


export default function App() {
  const [view, setView] = useState('upload'); // 'upload' | 'annotate'
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [documentId, setDocumentId] = useState(null);
  const [pageCount, setPageCount] = useState(1);
  const [pageWidth, setPageWidth] = useState(0);
  const [pageHeight, setPageHeight] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [balloons, setBalloons] = useState([]);
  const [selectedBalloonId, setSelectedBalloonId] = useState(null);
  const [selectedForExport, setSelectedForExport] = useState(new Set());
  const [exporting, setExporting] = useState(false);
  const [mode, setMode] = useState('auto'); // 'auto' | 'manual'
  const [zoom, setZoom] = useState(1.0); // 1.0 = 100%, 1.5 = 150%, etc.
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [error, setError] = useState(null);

  const handleUpload = useCallback(async (file) => {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please upload a valid PDF file.');
      return;
    }
    setError(null);
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const { data } = await axios.post(`${API}/upload`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setDocumentId(data.document_id);
      setPageCount(data.page_count);
      setPageWidth(data.page_width);
      setPageHeight(data.page_height);
      setBalloons(data.balloons);
      setSelectedForExport(new Set());
      setCurrentPage(1);
      setView('annotate');
    } catch (err) {
      setError(err?.response?.data?.detail || 'Upload failed. Is the backend running?');
    } finally {
      setUploading(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      handleUpload(file);
    },
    [handleUpload]
  );

  const handleFileInput = (e) => handleUpload(e.target.files[0]);

  // Balloon state updaters passed down to children
  const addBalloon = (b) => setBalloons((prev) => [...prev, b]);
  const updateBalloon = (updated) =>
    setBalloons((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
  const removeBalloon = (id) => {
    setBalloons((prev) => prev.filter((b) => b.id !== id));
    setSelectedForExport((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  };

  const toggleSelectForExport = useCallback((id) => {
    setSelectedForExport((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAllForExport = useCallback(() => {
    // Select all balloons on the current page
    setSelectedForExport((prev) => {
      const next = new Set(prev);
      balloons.filter((b) => b.page === currentPage).forEach((b) => next.add(b.id));
      return next;
    });
  }, [balloons, currentPage]);

  const deselectAllForExport = useCallback(() => {
    setSelectedForExport(new Set());
  }, []);

  // Shared Excel Export Handler (All vs Selected)
  const handleExport = useCallback(async (isManualSelected = false) => {
    if (!documentId || exporting) return;
    const ids = isManualSelected ? Array.from(selectedForExport) : [];
    if (isManualSelected && ids.length === 0) {
      alert('Please select at least one balloon using the checkboxes in the sidebar.');
      return;
    }

    setExporting(true);
    try {
      let response;
      if (isManualSelected) {
        response = await axios.post(`${API}/export/${documentId}/selected`, {
          balloon_ids: ids,
        }, {
          responseType: 'blob',
        });
      } else {
        response = await axios.get(`${API}/export/${documentId}`, {
          responseType: 'blob',
        });
      }

      const filename = isManualSelected
        ? `balloons_${documentId}_selected.xlsx`
        : `balloons_${documentId}.xlsx`;

      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      }, 1500);
    } catch (err) {
      console.warn('Axios blob export failed, falling back to direct navigation...', err);
      if (isManualSelected) {
        window.location.href = `${API}/export/${documentId}?balloon_ids=${ids.join(',')}`;
      } else {
        window.location.href = `${API}/export/${documentId}`;
      }
    } finally {
      setExporting(false);
    }
  }, [documentId, exporting, selectedForExport]);

  if (view === 'upload') {
    return (
      <div className="upload-screen">
        <div className="upload-hero">
          <div className="logo-mark">
            <span>CAD</span><span className="logo-accent">Lens</span>
          </div>
          <p className="upload-subtitle">
            AI-powered CAD drawing annotation — detect, label & export balloons instantly.
          </p>
        </div>

        <div
          className={`drop-zone glass-panel ${dragOver ? 'drop-zone--active' : ''} ${uploading ? 'drop-zone--loading' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => !uploading && document.getElementById('pdf-input').click()}
        >
          <input id="pdf-input" type="file" accept=".pdf" onChange={handleFileInput} />
          {uploading ? (
            <div className="upload-loading">
              <Loader2 size={48} className="spin" />
              <p>Processing your drawing…</p>
              <span className="upload-hint">Running OCR & annotation detection</span>
            </div>
          ) : (
            <div className="upload-idle">
              <div className="upload-icon-wrap">
                <Upload size={40} />
              </div>
              <p className="upload-cta">Drop your PDF here</p>
              <span className="upload-hint">or click to browse — PDF only</span>
            </div>
          )}
        </div>

        {error && <div className="error-banner">{error}</div>}

        <div className="feature-grid">
          {[
            { icon: '🔍', title: 'Smart OCR', desc: 'Full-page pytesseract extracts all text & coordinates' },
            { icon: '⚙️', title: 'CV Detection', desc: 'HoughLines + contour analysis finds dimensions & GD&T' },
            { icon: '📊', title: 'Excel Export', desc: 'One-click export with formatted annotation table' },
          ].map((f) => (
            <div key={f.title} className="feature-card glass-panel">
              <span className="feature-icon">{f.icon}</span>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // ── Annotate view ────────────────────────────────────────────────────────
  const pageBalloons = balloons.filter((b) => b.page === currentPage);

  return (
    <div className="annotate-screen">
      <Toolbar
        documentId={documentId}
        mode={mode}
        setMode={setMode}
        zoom={zoom}
        setZoom={setZoom}
        onNewUpload={() => {
          setView('upload');
          setDocumentId(null);
          setBalloons([]);
          setSelectedForExport(new Set());
        }}
        onExportAll={() => handleExport(false)}
        onExportSelected={() => handleExport(true)}
        selectedCount={selectedForExport.size}
        totalCount={balloons.length}
        exporting={exporting}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
      />
      <div className={`annotate-body ${!sidebarOpen ? 'sidebar-collapsed' : ''}`}>
        <div className="canvas-area">
          <DrawingCanvas
            documentId={documentId}
            currentPage={currentPage}
            pageCount={pageCount}
            pageWidth={pageWidth}
            pageHeight={pageHeight}
            balloons={pageBalloons}
            selectedBalloonId={selectedBalloonId}
            setSelectedBalloonId={setSelectedBalloonId}
            selectedForExport={selectedForExport}
            toggleSelectForExport={toggleSelectForExport}
            mode={mode}
            zoom={zoom}
            onBalloonAdded={addBalloon}
            onBalloonMoved={updateBalloon}
            onBalloonClick={(id) => setSelectedBalloonId(id)}
          />
          {pageCount > 1 && (
            <div className="page-nav">
              <button
                className="btn-secondary page-btn"
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage((p) => p - 1)}
              >
                ← Prev
              </button>
              <span className="page-indicator">
                Page {currentPage} / {pageCount}
              </span>
              <button
                className="btn-secondary page-btn"
                disabled={currentPage >= pageCount}
                onClick={() => setCurrentPage((p) => p + 1)}
              >
                Next →
              </button>
            </div>
          )}
        </div>
        {sidebarOpen && (
          <BalloonList
            balloons={pageBalloons}
            selectedBalloonId={selectedBalloonId}
            setSelectedBalloonId={setSelectedBalloonId}
            selectedForExport={selectedForExport}
            toggleSelectForExport={toggleSelectForExport}
            selectAllForExport={selectAllForExport}
            deselectAllForExport={deselectAllForExport}
            onExportSelected={() => handleExport(true)}
            onUpdate={updateBalloon}
            onDelete={removeBalloon}
            onClose={() => setSidebarOpen(false)}
          />
        )}
      </div>
    </div>
  );
}
