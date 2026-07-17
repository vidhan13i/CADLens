import { X } from "lucide-react";

export default function BalloonEditor({ selected, updateBalloon, onClose }) {
    if (!selected) return null;

    const handleChange = (field, value) => {
        updateBalloon({
            ...selected,
            [field]: value,
        });
    };

    return (
        <div style={{ padding: "24px" }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
                <div>
                    <h4 style={{ margin: 0, fontSize: '18px', color: 'var(--text-main)' }}>Balloon {selected.number} details</h4>
                    {selected.confidence && (
                        <div style={{ 
                            fontSize: '12px', 
                            color: 'var(--accent)', 
                            marginTop: '4px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px'
                        }}>
                            <span style={{ 
                                display: 'inline-block', 
                                width: '6px', 
                                height: '6px', 
                                borderRadius: '50%', 
                                background: 'var(--success)' 
                            }}></span>
                            YOLO Conf: {selected.confidence}%
                        </div>
                    )}
                </div>
                <button 
                    onClick={onClose} 
                    style={{ background: 'transparent', color: 'var(--text-muted)', padding: '4px' }}
                >
                    <X size={18} />
                </button>
            </div>

            <div style={{ marginBottom: '16px' }}>
                <label style={styles.label}>Type Classification</label>
                <select
                    value={selected.type || "balloon"}
                    onChange={(e) => handleChange("type", e.target.value)}
                    style={styles.input}
                >
                    <option value="balloon">Balloon Annotation</option>
                    <option value="dimension">Dimension Reference</option>
                    <option value="note">Drawing Note</option>
                    <option value="tolerance">Tolerance Value</option>
                </select>
            </div>

            <div style={{ marginBottom: '16px' }}>
                <label style={styles.label}>Recognized Text (OCR)</label>
                <input
                    value={selected.text || selected.description || ""}
                    onChange={(e) => handleChange("text", e.target.value)}
                    style={styles.input}
                    placeholder="e.g. A12"
                />
                {selected.ocr_confidence && (
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px', textAlign: 'right' }}>
                        OCR Conf: {selected.ocr_confidence}%
                    </div>
                )}
            </div>

            <div style={{ marginBottom: '8px' }}>
                <label style={styles.label}>Inspector Remarks</label>
                <textarea
                    value={selected.remarks || ""}
                    onChange={(e) => handleChange("remarks", e.target.value)}
                    style={{ ...styles.input, minHeight: '80px', resize: 'vertical' }}
                    placeholder="Add manual verification notes..."
                />
            </div>
        </div>
    );
}

const styles = {
    label: {
        display: "block",
        fontSize: "13px",
        fontWeight: "600",
        color: "var(--text-muted)",
        marginBottom: "6px",
        textTransform: "uppercase",
        letterSpacing: "0.5px"
    },
    input: {
        width: "100%",
        padding: "10px 14px",
        background: "var(--bg-panel)",
        border: "1px solid var(--border)",
        borderRadius: "8px",
        color: "var(--text-main)",
        fontSize: "14px",
        boxSizing: "border-box",
        fontFamily: "'Inter', sans-serif",
        outline: "none",
        transition: "border-color 0.2s"
    }
};