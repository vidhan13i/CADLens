import { Target, Layers, Cpu, Code2 } from 'lucide-react';

export default function AboutPage() {
  return (
    <div className="about-container animation-fade-in" style={styles.container}>
      <div className="hero-section text-center" style={styles.hero}>
        <div style={styles.badge}>Vision AI</div>
        <h1 style={styles.title}>AI-Powered CAD Balloon Detection</h1>
        <p style={styles.subtitle}>
          Automate your engineering drawing review process with our state-of-the-art computer vision pipeline. Extract references, dimensions, and annotations instantly.
        </p>
      </div>

      <div style={styles.grid}>
        <div className="glass-panel" style={styles.card}>
          <div style={{...styles.iconWrapper, color: '#3b82f6'}}>
            <Target size={32} />
          </div>
          <h3 style={styles.cardTitle}>Precision Detection</h3>
          <p style={styles.cardText}>Utilizes a custom-trained YOLOv8 object detection model specifically for CAD balloons, backed by a highly-tuned OpenCV Hough Transform fallback.</p>
        </div>

        <div className="glass-panel" style={styles.card}>
          <div style={{...styles.iconWrapper, color: '#8b5cf6'}}>
            <Layers size={32} />
          </div>
          <h3 style={styles.cardTitle}>Layer Separation</h3>
          <p style={styles.cardText}>Isolates annotations from geometric drawings ensuring minimal OCR interference and high confidence character recognition.</p>
        </div>

        <div className="glass-panel" style={styles.card}>
          <div style={{...styles.iconWrapper, color: '#2dd4bf'}}>
            <Cpu size={32} />
          </div>
          <h3 style={styles.cardTitle}>Strict OCR Pipeline</h3>
          <p style={styles.cardText}>Tesseract OCR is strictly constrained to YOLO bounding boxes and filtered with aggressive Regex (`^[A-Z0-9]{1,4}$`) to guarantee near-zero false positives.</p>
        </div>

        <div className="glass-panel" style={styles.card}>
          <div style={{...styles.iconWrapper, color: '#f43f5e'}}>
            <Code2 size={32} />
          </div>
          <h3 style={styles.cardTitle}>Modern Stack</h3>
          <p style={styles.cardText}>Built on a highly concurrent FastAPI backend with a React + Vite frontend for lightning-fast real-time processing and rendering.</p>
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: {
    maxWidth: '1000px',
    margin: '0 auto',
    padding: '40px 0',
  },
  hero: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    textAlign: 'center',
    marginBottom: '64px',
  },
  badge: {
    background: 'rgba(59, 130, 246, 0.2)',
    color: '#60a5fa',
    padding: '6px 16px',
    borderRadius: '24px',
    fontSize: '14px',
    fontWeight: '600',
    marginBottom: '24px',
    border: '1px solid rgba(59, 130, 246, 0.3)'
  },
  title: {
    fontSize: '48px',
    fontWeight: '800',
    marginBottom: '24px',
    background: 'linear-gradient(to right, #fff, #9ca3af)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    letterSpacing: '-1px'
  },
  subtitle: {
    fontSize: '18px',
    color: '#9ca3af',
    maxWidth: '600px',
    lineHeight: '1.6'
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
    gap: '24px',
  },
  card: {
    padding: '32px',
    borderRadius: '16px',
    transition: 'transform 0.2s',
    cursor: 'default'
  },
  iconWrapper: {
    marginBottom: '20px',
    background: 'rgba(255, 255, 255, 0.05)',
    display: 'inline-flex',
    padding: '16px',
    borderRadius: '12px'
  },
  cardTitle: {
    fontSize: '20px',
    marginBottom: '12px',
    color: '#fff'
  },
  cardText: {
    color: '#9ca3af',
    lineHeight: '1.6',
    fontSize: '15px'
  }
};
