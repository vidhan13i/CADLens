import { useEffect, useRef, useState, useCallback } from 'react';
import axios from 'axios';
import { API } from '../api';  // P17 fix: centralized URL

const BALLOON_R = 14; // radius in canvas pixels for the drawn circle
const LEADER_LEN = 24;

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
  onBalloonMoved,   // P19: new prop — called after drag-commit
}) {
  const containerRef = useRef(null);
  const canvasRef    = useRef(null);
  const [imgSrc, setImgSrc] = useState(null);

  // P19 fix: drag state
  const dragRef = useRef(null); // { id, type:'balloon'|'feature', startImgX, startImgY, origX, origY, origFx, origFy }

  // ── Load page image ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!documentId) return;
    setImgSrc(`${API}/document/${documentId}/image/${currentPage}?t=${Date.now()}`);
  }, [documentId, currentPage]);

  const canvasW = pageWidth  * zoom;
  const canvasH = pageHeight * zoom;

  // ── Draw balloons on canvas ──────────────────────────────────────────────
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !pageWidth || !pageHeight) return;
    const ctx = canvas.getContext('2d');

    canvas.width  = canvasW;
    canvas.height = canvasH;
    ctx.clearRect(0, 0, canvasW, canvasH);

    balloons.forEach((b) => {
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

        // Arrowhead at feature point
        const angle = Math.atan2(dy, dx);
        ctx.beginPath();
        ctx.moveTo(fx, fy);
        ctx.lineTo(fx - 8 * Math.cos(angle - Math.PI / 6), fy - 8 * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(fx - 8 * Math.cos(angle + Math.PI / 6), fy - 8 * Math.sin(angle + Math.PI / 6));
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

      // P19: feature point handle — small circle, only when selected
      if (isSelected && dist > BALLOON_R + 2) {
        ctx.beginPath();
        ctx.arc(fx, fy, 5, 0, Math.PI * 2);
        ctx.fillStyle = '#facc15';
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
    });
  }, [balloons, selectedBalloonId, zoom, canvasW, canvasH, pageWidth, pageHeight]);

  useEffect(() => { draw(); }, [draw]);

  // ── P19: drag helpers ────────────────────────────────────────────────────

  const hitTestBalloon = (imgX, imgY) => {
    const hitR = (BALLOON_R + 4) / zoom;
    for (const b of balloons) {
      if (Math.hypot(imgX - b.x, imgY - b.y) <= hitR) return { b, part: 'balloon' };
    }
    return null;
  };

  const hitTestFeature = (imgX, imgY) => {
    const hitR = 8 / zoom;
    for (const b of balloons) {
      if (b.id === selectedBalloonId && Math.hypot(imgX - b.feature_x, imgY - b.feature_y) <= hitR) {
        return { b, part: 'feature' };
      }
    }
    return null;
  };

  const handleMouseDown = (e) => {
    const imgX = e.nativeEvent.offsetX / zoom;
    const imgY = e.nativeEvent.offsetY / zoom;

    // Check feature point drag first (only visible when selected)
    const fHit = hitTestFeature(imgX, imgY);
    if (fHit) {
      dragRef.current = {
        id: fHit.b.id, part: 'feature',
        origX: fHit.b.x, origY: fHit.b.y,
        origFx: fHit.b.feature_x, origFy: fHit.b.feature_y,
        startImgX: imgX, startImgY: imgY,
      };
      return;
    }

    // Check balloon body drag
    const bHit = hitTestBalloon(imgX, imgY);
    if (bHit) {
      dragRef.current = {
        id: bHit.b.id, part: 'balloon',
        origX: bHit.b.x, origY: bHit.b.y,
        origFx: bHit.b.feature_x, origFy: bHit.b.feature_y,
        startImgX: imgX, startImgY: imgY,
      };
      setSelectedBalloonId(bHit.b.id);
      return;
    }

    // Not on any balloon — manual placement or deselect
    if (mode === 'manual') {
      setSelectedBalloonId(null);
      axios.post(`${API}/balloons`, {
        document_id: documentId,
        x: imgX, y: imgY,
        feature_x: imgX, feature_y: imgY,
        page: currentPage,
        text: '?', type: 'Note',
      }).then(({ data }) => {
        onBalloonAdded(data);
        setSelectedBalloonId(data.id);
      }).catch((err) => console.error('Failed to add balloon', err));
    } else {
      setSelectedBalloonId(null);
    }
  };

  const handleMouseMove = useCallback((e) => {
    if (!dragRef.current) return;
    const imgX = e.nativeEvent.offsetX / zoom;
    const imgY = e.nativeEvent.offsetY / zoom;
    const d = dragRef.current;
    const dx = imgX - d.startImgX;
    const dy = imgY - d.startImgY;

    // Live-update the balloon visually (optimistic update)
    const updated = balloons.map((b) => {
      if (b.id !== d.id) return b;
      if (d.part === 'balloon') {
        return { ...b, x: d.origX + dx, y: d.origY + dy, feature_x: d.origFx + dx, feature_y: d.origFy + dy };
      }
      return { ...b, feature_x: d.origFx + dx, feature_y: d.origFy + dy };
    });
    // Redraw with updated positions
    const canvas = canvasRef.current;
    if (!canvas || !pageWidth || !pageHeight) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvasW, canvasH);
    // Re-use draw logic inline (simplified for performance)
    updated.forEach((b) => {
      const cx = b.x * zoom, cy = b.y * zoom;
      const fx = b.feature_x * zoom, fy = b.feature_y * zoom;
      const isSelected = b.id === selectedBalloonId;
      const dv = Math.hypot(fx - cx, fy - cy);
      if (dv > BALLOON_R + 2) {
        const ang = Math.atan2(fy - cy, fx - cx);
        ctx.beginPath(); ctx.moveTo(cx + (fx-cx)/dv*BALLOON_R, cy + (fy-cy)/dv*BALLOON_R);
        ctx.lineTo(fx, fy);
        ctx.strokeStyle = isSelected ? '#facc15' : 'rgba(239,68,68,0.9)'; ctx.lineWidth = 1.5; ctx.stroke();
        ctx.beginPath(); ctx.moveTo(fx, fy);
        ctx.lineTo(fx - 8*Math.cos(ang-Math.PI/6), fy - 8*Math.sin(ang-Math.PI/6));
        ctx.lineTo(fx - 8*Math.cos(ang+Math.PI/6), fy - 8*Math.sin(ang+Math.PI/6));
        ctx.closePath(); ctx.fillStyle = isSelected ? '#facc15' : 'rgba(239,68,68,0.9)'; ctx.fill();
      }
      ctx.beginPath(); ctx.arc(cx, cy, BALLOON_R, 0, Math.PI*2);
      ctx.fillStyle = isSelected ? '#facc15' : 'rgba(255,68,68,0.92)'; ctx.fill();
      ctx.strokeStyle = isSelected ? '#fff' : 'rgba(255,255,255,0.85)'; ctx.lineWidth = isSelected ? 2.5 : 1.5; ctx.stroke();
      ctx.fillStyle = '#fff'; ctx.font = `bold ${BALLOON_R * 0.95}px Inter, sans-serif`;
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(String(b.balloon_no), cx, cy);
    });
  }, [balloons, selectedBalloonId, zoom, canvasW, canvasH, pageWidth, pageHeight]);

  const handleMouseUp = useCallback(async (e) => {
    if (!dragRef.current) return;
    const imgX = e.nativeEvent.offsetX / zoom;
    const imgY = e.nativeEvent.offsetY / zoom;
    const d = dragRef.current;
    dragRef.current = null;

    const dx = imgX - d.startImgX;
    const dy = imgY - d.startImgY;
    if (Math.hypot(dx, dy) < 2) return; // tiny move = just a click, not a drag

    const payload = d.part === 'balloon'
      ? { x: d.origX + dx, y: d.origY + dy, feature_x: d.origFx + dx, feature_y: d.origFy + dy }
      : { feature_x: d.origFx + dx, feature_y: d.origFy + dy };

    try {
      const { data } = await axios.put(`${API}/balloons/${d.id}`, payload);
      onBalloonMoved && onBalloonMoved(data);
    } catch (err) {
      console.error('Failed to move balloon', err);
    }
  }, [zoom, onBalloonMoved]);

  return (
    <div
      ref={containerRef}
      style={{ overflow: 'auto', width: '100%', height: '100%' }}
    >
      {imgSrc ? (
        <div style={{ position: 'relative', width: `${canvasW}px`, display: 'inline-block' }}>
          <img
            src={imgSrc}
            alt={`Page ${currentPage}`}
            draggable={false}
            style={{ width: `${canvasW}px`, height: `${canvasH}px`, display: 'block' }}
          />
          <canvas
            ref={canvasRef}
            id="balloon-canvas"
            className={mode === 'manual' ? 'cursor-crosshair' : 'cursor-pointer'}
            width={canvasW}
            height={canvasH}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'auto' }}
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
