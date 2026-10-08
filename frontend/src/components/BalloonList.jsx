import { useState, useEffect } from 'react';
import axios from 'axios';
import { Trash2, ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';
import { API } from '../api';  // P17 fix: centralized URL

const TYPE_COLORS = {
  Dimension:       '#3b82f6',
  Tolerance:       '#f59e0b',
  'Surface Finish':'#10b981',
  'GD&T':          '#8b5cf6',
  Note:            '#6b7280',
  balloon:         '#ef4444',
};

// Fields shown per annotation type in the expanded detail panel
const TYPE_FIELDS = {
  Dimension: [
    { key: 'nominal_value',   label: 'Nominal Value',   placeholder: 'e.g. 39, 100' },
    { key: 'tolerance_upper', label: 'Upper Tolerance',  placeholder: 'e.g. +0.039' },
    { key: 'tolerance_lower', label: 'Lower Tolerance',  placeholder: 'e.g. -0.000' },
    { key: 'surface_finish',  label: 'Surface Finish',   placeholder: 'e.g. Ra 1.6' },
    { key: 'process',         label: 'Process',          placeholder: 'e.g. Drilling, Turning' },
    { key: 'description',     label: 'Description',      placeholder: 'Feature description' },
    { key: 'remarks',         label: 'Remarks',          placeholder: 'Additional notes' },
  ],
  Tolerance: [
    { key: 'nominal_value',   label: 'Nominal Value',   placeholder: 'e.g. 0.150' },
    { key: 'tolerance_upper', label: 'Upper Tolerance',  placeholder: 'e.g. +0.050' },
    { key: 'tolerance_lower', label: 'Lower Tolerance',  placeholder: 'e.g. -0.050' },
    { key: 'description',     label: 'Applies To',       placeholder: 'Feature this tolerance applies to' },
    { key: 'remarks',         label: 'Remarks',          placeholder: 'Additional notes' },
  ],
  'Surface Finish': [
    { key: 'nominal_value',   label: 'Ra / Rz Value',   placeholder: 'e.g. 1.6, 6.3' },
    { key: 'process',         label: 'Process',          placeholder: 'e.g. Grinding, Milling' },
    { key: 'description',     label: 'Surface Area',     placeholder: 'Which surface' },
    { key: 'remarks',         label: 'Remarks',          placeholder: 'Additional notes' },
  ],
  'GD&T': [
    { key: 'tolerance_zone',  label: 'Tolerance Zone',  placeholder: 'e.g. 0.05, Ø0.1' },
    { key: 'datum_ref',       label: 'Datum Reference',  placeholder: 'e.g. A, A-B' },
    { key: 'description',     label: 'Feature',          placeholder: 'Controlled feature' },
    { key: 'remarks',         label: 'Remarks',          placeholder: 'Additional notes' },
  ],
  Note: [
    { key: 'quantity',    label: 'Quantity',     placeholder: 'e.g. 62 Nos.' },
    { key: 'material',    label: 'Material',     placeholder: 'e.g. C45 Steel' },
    { key: 'description', label: 'Description',  placeholder: 'Expanded note text' },
    { key: 'remarks',     label: 'Remarks',      placeholder: 'Additional notes' },
  ],
  balloon: [
    { key: 'description', label: 'Description', placeholder: 'What this balloon references' },
    { key: 'remarks',     label: 'Remarks',     placeholder: 'Additional notes' },
  ],
};

const ALL_TYPES = ['Dimension', 'Tolerance', 'Surface Finish', 'GD&T', 'Note'];

// ── Single inline input ───────────────────────────────────────────────────────
function DetailField({ label, value, placeholder, onSave }) {
  const [draft, setDraft] = useState(value || '');
  const [active, setActive] = useState(false);

  // P21 fix: sync draft when the parent balloon changes (different balloon selected)
  useEffect(() => {
    if (!active) setDraft(value || '');
  }, [value, active]);

  const commit = () => {
    setActive(false);
    if (draft !== (value || '')) onSave(draft);
  };

  return (
    <div className="detail-field">
      <label className="detail-label">{label}</label>
      <input
        className={`detail-input ${active ? 'detail-input--active' : ''}`}
        value={draft}
        placeholder={placeholder}
        onFocus={() => setActive(true)}
        onChange={e => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={e => { if (e.key === 'Enter') commit(); }}
      />
    </div>
  );
}

// ── Type selector ─────────────────────────────────────────────────────────────
function TypeSelect({ value, onSave }) {
  return (
    <select
      className="type-select"
      value={value}
      onChange={e => onSave(e.target.value)}
    >
      {ALL_TYPES.map(t => (
        <option key={t} value={t}>{t}</option>
      ))}
    </select>
  );
}

// ── Expanded detail panel ─────────────────────────────────────────────────────
function DetailPanel({ balloon, onUpdate }) {
  const fields = TYPE_FIELDS[balloon.type] || TYPE_FIELDS['Note'];

  const save = async (field, value) => {
    try {
      const { data } = await axios.put(`${API}/balloons/${balloon.id}`, { [field]: value });
      onUpdate(data);
    } catch (err) {
      console.error(`Failed to save ${field}`, err);
    }
  };

  return (
    <div className="detail-panel">
      {/* Type selector */}
      <div className="detail-field">
        <label className="detail-label">Type</label>
        <TypeSelect value={balloon.type} onSave={v => save('type', v)} />
      </div>

      {/* Drawing reference (text) */}
      <DetailField
        label="Drawing Reference"
        value={balloon.text}
        placeholder="Annotation text from drawing"
        onSave={v => save('text', v)}
      />

      {/* Type-specific fields */}
      {fields.map(f => (
        <DetailField
          key={`${balloon.id}-${f.key}`}
          label={f.label}
          value={balloon[f.key] || ''}
          placeholder={f.placeholder}
          onSave={v => save(f.key, v)}
        />
      ))}
    </div>
  );
}

// ── P22: Styled in-app confirmation dialog (replaces window.confirm) ───────────
function ConfirmDialog({ balloon, onConfirm, onCancel }) {
  if (!balloon) return null;
  return (
    <div className="confirm-overlay" onClick={onCancel}>
      <div
        className="confirm-dialog glass-panel"
        onClick={e => e.stopPropagation()}
        id="confirm-delete-dialog"
      >
        <div className="confirm-icon">
          <AlertTriangle size={24} color="#ef4444" />
        </div>
        <p className="confirm-title">Delete Balloon #{balloon.balloon_no}?</p>
        <p className="confirm-body">
          This will permanently remove annotation&nbsp;
          <strong>"{balloon.text}"</strong> from this drawing.
        </p>
        <div className="confirm-actions">
          <button
            id="confirm-delete-cancel"
            className="btn-secondary"
            onClick={onCancel}
          >
            Cancel
          </button>
          <button
            id="confirm-delete-ok"
            className="btn-danger"
            onClick={onConfirm}
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function BalloonList({
  balloons,
  selectedBalloonId,
  setSelectedBalloonId,
  onUpdate,
  onDelete,
}) {
  const [expandedId, setExpandedId] = useState(null);
  const [confirmBalloon, setConfirmBalloon] = useState(null);

  // Auto-expand and scroll-to when selection changes (e.g. user clicked on canvas)
  useEffect(() => {
    if (!selectedBalloonId) return;
    setExpandedId(selectedBalloonId);
    // Scroll the card into view
    const card = document.getElementById(`balloon-row-${selectedBalloonId}`);
    if (card) {
      card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [selectedBalloonId]);

  const toggleExpand = (id) => {
    setExpandedId(prev => (prev === id ? null : id));
  };

  const handleRowClick = (id) => {
    setSelectedBalloonId(id === selectedBalloonId ? null : id);
    toggleExpand(id);
  };

  // P22 fix: show styled dialog instead of window.confirm
  const handleDeleteClick = (e, balloon) => {
    e.stopPropagation();
    setConfirmBalloon(balloon);
  };

  const confirmDelete = async () => {
    const balloon = confirmBalloon;
    setConfirmBalloon(null);
    try {
      await axios.delete(`${API}/balloons/${balloon.id}`);
      onDelete(balloon.id);
      if (selectedBalloonId === balloon.id) setSelectedBalloonId(null);
      if (expandedId === balloon.id) setExpandedId(null);
    } catch (err) {
      console.error('Failed to delete balloon', err);
    }
  };

  const sorted = [...balloons].sort((a, b) => a.balloon_no - b.balloon_no);

  return (
    <aside className="balloon-sidebar glass-panel">
      {/* P22: styled confirm dialog */}
      <ConfirmDialog
        balloon={confirmBalloon}
        onConfirm={confirmDelete}
        onCancel={() => setConfirmBalloon(null)}
      />

      <div className="sidebar-header">
        <h2 className="sidebar-title">Annotations</h2>
        <span className="balloon-count">{balloons.length} items</span>
      </div>

      {sorted.length === 0 ? (
        <div className="sidebar-empty">
          <p>No annotations detected on this page.</p>
          <p className="muted-text">Switch to Manual mode and click to add balloons.</p>
        </div>
      ) : (
        <div className="balloon-list-wrap">
          {sorted.map(b => {
            const isSelected = b.id === selectedBalloonId;
            const isExpanded = b.id === expandedId;
            return (
              <div
                key={b.id}
                id={`balloon-row-${b.id}`}
                className={`balloon-card ${isSelected ? 'balloon-card--selected' : ''}`}
              >
                {/* ── Summary row ── */}
                <div
                  className="balloon-summary"
                  onClick={() => handleRowClick(b.id)}
                >
                  <span className="balloon-badge" style={{ background: TYPE_COLORS[b.type] || '#6b7280' }}>
                    {b.balloon_no}
                  </span>

                  <div className="summary-info">
                    <span className="summary-text" title={b.text}>{b.text}</span>
                    <span
                      className="type-chip"
                      style={{ background: TYPE_COLORS[b.type] || '#6b7280' }}
                    >
                      {b.type}
                    </span>
                  </div>

                  <div className="summary-actions">
                    <button
                      id={`delete-balloon-${b.id}`}
                      className="delete-btn"
                      onClick={e => handleDeleteClick(e, b)}
                      title="Delete"
                    >
                      <Trash2 size={13} />
                    </button>
                    <span className="expand-icon">
                      {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                    </span>
                  </div>
                </div>

                {/* ── Expanded detail panel ── */}
                {isExpanded && (
                  <DetailPanel balloon={b} onUpdate={onUpdate} />
                )}
              </div>
            );
          })}
        </div>
      )}
    </aside>
  );
}
