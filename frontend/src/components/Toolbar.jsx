import { CheckSquare, Cpu, Download, Loader2, PencilLine, Upload, PanelRightClose, PanelRightOpen } from 'lucide-react';

const ZOOM_OPTIONS = [25, 50, 75, 100, 125, 150, 200, 300];

export default function Toolbar({
  documentId,
  mode,
  setMode,
  zoom,
  setZoom,
  onNewUpload,
  onExportAll,
  onExportSelected,
  selectedCount = 0,
  exporting = false,
  sidebarOpen = true,
  onToggleSidebar,
}) {
  const currentZoomPercent = Math.round(zoom * 100);

  const handleZoomChange = (e) => {
    const val = Number(e.target.value);
    if (!isNaN(val)) {
      setZoom(val / 100);
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
            onClick={() => setZoom(z => Math.max(0.25, parseFloat((z - 0.25).toFixed(2))))}
            disabled={zoom <= 0.25}
            title="Zoom Out (min 25%)"
          >
            -
          </button>
          <div className="zoom-select-wrapper">
            <select
              className="zoom-select"
              value={currentZoomPercent}
              onChange={handleZoomChange}
              title="Select Zoom Percentage"
            >
              {!ZOOM_OPTIONS.includes(currentZoomPercent) && (
                <option value={currentZoomPercent}>{currentZoomPercent}%</option>
              )}
              {ZOOM_OPTIONS.map((val) => (
                <option key={val} value={val}>
                  {val}%
                </option>
              ))}
            </select>
          </div>
          <button
            className="zoom-btn"
            onClick={() => setZoom(z => Math.min(3.0, parseFloat((z + 0.25).toFixed(2))))}
            disabled={zoom >= 3.0}
            title="Zoom In (max 300%)"
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

        {/* Excel Export Controls — Both All and Selected Options */}
        <div className="export-controls-group">
          <button
            id="btn-export-all"
            className="toolbar-btn btn-success"
            onClick={onExportAll}
            disabled={!documentId || exporting}
            title="Export all balloons in drawing to Excel"
          >
            {exporting ? (
              <>
                <Loader2 size={15} className="spin" />
                Exporting...
              </>
            ) : (
              <>
                <Download size={15} />
                Export All
              </>
            )}
          </button>

          <button
            id="btn-export-selected"
            className={`toolbar-btn ${selectedCount > 0 ? 'btn-export-selected' : 'btn-secondary btn-export-disabled'}`}
            onClick={onExportSelected}
            disabled={!documentId || exporting || selectedCount === 0}
            title={
              selectedCount > 0
                ? `Export ${selectedCount} selected balloon(s) to Excel`
                : 'Select balloons in sidebar or with Shift-click to export'
            }
          >
            <CheckSquare size={15} />
            Export Selected {selectedCount > 0 ? `(${selectedCount})` : ''}
          </button>
        </div>

        <button
          id="btn-new-upload"
          className="toolbar-btn btn-secondary"
          onClick={onNewUpload}
          title="Upload a new PDF"
        >
          <Upload size={15} />
          New PDF
        </button>

        {onToggleSidebar && (
          <button
            id="btn-toggle-sidebar"
            className={`toolbar-btn ${sidebarOpen ? 'btn-secondary btn-sidebar-active' : 'btn-primary'}`}
            onClick={onToggleSidebar}
            title={sidebarOpen ? "Hide Detected Balloons Sidebar" : "Show Detected Balloons Sidebar"}
          >
            {sidebarOpen ? <PanelRightClose size={15} /> : <PanelRightOpen size={15} />}
            <span>{sidebarOpen ? "Hide Sidebar" : "Show Sidebar"}</span>
          </button>
        )}
      </div>
    </header>
  );
}
