import { useState, useCallback } from 'react';
import axios from 'axios';
import { Upload, Loader2, FileText } from 'lucide-react';
import Toolbar from './components/Toolbar';
import DrawingCanvas from './components/DrawingCanvas';
import BalloonList from './components/BalloonList';
import './App.css';

const API = 'http://localhost:8000';

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
  const [mode, setMode] = useState('auto'); // 'auto' | 'manual'
  const [zoom, setZoom] = useState(1.0); // 1.0 = 100%, 1.5 = 150%, etc.
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
  const removeBalloon = (id) =>
    setBalloons((prev) => prev.filter((b) => b.id !== id));

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
        onNewUpload={() => { setView('upload'); setDocumentId(null); setBalloons([]); }}
      />
      <div className="annotate-body">
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
            mode={mode}
            zoom={zoom}
            onBalloonAdded={addBalloon}
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
        <BalloonList
          balloons={pageBalloons}
          selectedBalloonId={selectedBalloonId}
          setSelectedBalloonId={setSelectedBalloonId}
          onUpdate={updateBalloon}
          onDelete={removeBalloon}
        />
      </div>
    </div>
  );
}
