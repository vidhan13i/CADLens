import { useEffect, useRef, useState, useCallback } from 'react';
import axios from 'axios';

const API = 'http://localhost:8000';
const BALLOON_R = 14; // radius in canvas pixels for the drawn circle
const LEADER_LEN = 24; // length of leader line from circle edge to feature point (min)

export default function DrawingCanvas({
  documentId,
  currentPage,
  pageCount,
  pageWidth,
  pageHeight,
  balloons,
  selectedBalloonId,
  setSelectedBalloonId,
  mode,
  zoom,
  onBalloonAdded,
}) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const [imgSrc, setImgSrc] = useState(null);

  // ── Load page image ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!documentId) return;
    setImgSrc(`${API}/document/${documentId}/image/${currentPage}?t=${Date.now()}`);
  }, [documentId, currentPage]);

  // ── Pixel dimensions of the canvas at current zoom ─────────────────────────
  const canvasW = pageWidth  * zoom;
  const canvasH = pageHeight * zoom;

  // ── Draw balloons on canvas ────────────────────────────────────────────────
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !pageWidth || !pageHeight) return;
    const ctx = canvas.getContext('2d');

    // Canvas element resolution must match its CSS/layout size to avoid blurring
    canvas.width  = canvasW;
    canvas.height = canvasH;
    ctx.clearRect(0, 0, canvasW, canvasH);

    balloons.forEach((b) => {
      // Balloon coords are stored in original image space → scale by zoom
      const cx = b.x         * zoom;
      const cy = b.y         * zoom;
      const fx = b.feature_x * zoom;
      const fy = b.feature_y * zoom;
      const isSelected = b.id === selectedBalloonId;

      // Leader line
      const dx = fx - cx;
      const dy = fy - cy;
      const dist = Math.hypot(dx, dy);
      if (dist > BALLOON_R + 2) {
        const startX = cx + (dx / dist) * BALLOON_R;
        const startY = cy + (dy / dist) * BALLOON_R;
        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(fx, fy);
        ctx.strokeStyle = isSelected ? '#facc15' : 'rgba(239,68,68,0.9)';
        ctx.lineWidth = isSelected ? 2 : 1.5;
        ctx.stroke();
      }

      // Arrowhead at feature point
      if (dist > BALLOON_R + 2) {
        const angle = Math.atan2(dy, dx);
        ctx.beginPath();
        ctx.moveTo(fx, fy);
        ctx.lineTo(
          fx - 8 * Math.cos(angle - Math.PI / 6),
          fy - 8 * Math.sin(angle - Math.PI / 6)
        );
        ctx.lineTo(
          fx - 8 * Math.cos(angle + Math.PI / 6),
          fy - 8 * Math.sin(angle + Math.PI / 6)
        );
        ctx.closePath();
        ctx.fillStyle = isSelected ? '#facc15' : 'rgba(239,68,68,0.9)';
        ctx.fill();
      }

      // Circle
      ctx.beginPath();
      ctx.arc(cx, cy, BALLOON_R, 0, Math.PI * 2);
      ctx.fillStyle = isSelected ? '#facc15' : 'rgba(255, 68, 68, 0.92)';
      ctx.fill();
      ctx.strokeStyle = isSelected ? '#fff' : 'rgba(255,255,255,0.85)';
      ctx.lineWidth = isSelected ? 2.5 : 1.5;
      ctx.stroke();

      // Number label
      ctx.fillStyle = '#fff';
      ctx.font = `bold ${BALLOON_R * 0.95}px Inter, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(b.balloon_no), cx, cy);
    });
  }, [balloons, selectedBalloonId, zoom, canvasW, canvasH, pageWidth, pageHeight]);

  useEffect(() => {
    draw();
  }, [draw]);

  // ── Handle canvas click ────────────────────────────────────────────────────
  const handleCanvasClick = async (e) => {
    // offsetX/Y are already relative to the canvas element
    // Divide by zoom to convert back to original image coordinate space
    const imgX = e.nativeEvent.offsetX / zoom;
    const imgY = e.nativeEvent.offsetY / zoom;

    // Hit-test in original image space (BALLOON_R px tolerance at current zoom)
    const hitRadius = BALLOON_R / zoom;
    for (const b of balloons) {
      if (Math.hypot(imgX - b.x, imgY - b.y) <= hitRadius) {
        setSelectedBalloonId(b.id);
        return;
      }
    }

    // Manual mode → create new balloon at clicked position
    if (mode === 'manual') {
      setSelectedBalloonId(null);
      try {
        const { data } = await axios.post(`${API}/balloons`, {
          document_id: documentId,
          x: imgX,
          y: imgY,
          feature_x: imgX,
          feature_y: imgY,
          page: currentPage,
          text: '?',
          type: 'Note',
        });
        onBalloonAdded(data);
        setSelectedBalloonId(data.id);
      } catch (err) {
        console.error('Failed to add balloon', err);
      }
    } else {
      setSelectedBalloonId(null);
    }
  };

  return (
    // Outer div: scrolls both axes so any zoom level is fully reachable
    <div
      ref={containerRef}
      style={{
        overflow: 'auto',
        width: '100%',
        height: '100%',
      }}
    >
      {imgSrc ? (
        // Inner div: sized exactly to the zoomed image so nothing gets clipped
        <div
          style={{
            position: 'relative',
            width: `${canvasW}px`,
            display: 'inline-block',  // shrink-wraps to content width
          }}
        >
          <img
            src={imgSrc}
            alt={`Page ${currentPage}`}
            draggable={false}
            style={{
              width:   `${canvasW}px`,
              height:  `${canvasH}px`,
              display: 'block',
            }}
          />
          <canvas
            ref={canvasRef}
            id="balloon-canvas"
            className={mode === 'manual' ? 'cursor-crosshair' : 'cursor-pointer'}
            width={canvasW}
            height={canvasH}
            onClick={handleCanvasClick}
            style={{
              position:      'absolute',
              top:           0,
              left:          0,
              pointerEvents: 'auto',
            }}
          />
        </div>
      ) : (
        <div className="canvas-placeholder glass-panel">
          <p>Loading page image…</p>
        </div>
      )}
    </div>
  );
}
