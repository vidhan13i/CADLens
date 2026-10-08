import { useEffect, useRef, useState, useCallback } from 'react';
import axios from 'axios';
import { API } from '../api';

const BALLOON_R = 14; // radius in canvas pixels for the drawn circle

export default function DrawingCanvas({
  documentId,
  currentPage,
  pageWidth,
  pageHeight,
  balloons,
  selectedBalloonId,
  setSelectedBalloonId,
  mode,
  zoom,
  onBalloonAdded,
  onBalloonMoved,
  onBalloonClick,   // NEW: called when user clicks a balloon → parent scrolls + expands sidebar row
}) {
  const containerRef = useRef(null);
  const canvasRef    = useRef(null);
  const [imgSrc, setImgSrc] = useState(null);

  // drag state: { id, part:'balloon'|'feature', startImgX, startImgY, origX, origY, origFx, origFy, moved }
  const dragRef = useRef(null);

  // ── Load page image ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!documentId) return;
    setImgSrc(`${API}/document/${documentId}/image/${currentPage}?t=${Date.now()}`);
  }, [documentId, currentPage]);

  const canvasW = pageWidth  * zoom;
  const canvasH = pageHeight * zoom;

  // ── Draw balloons ────────────────────────────────────────────────────────
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

        ctx.save();
        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(fx, fy);
        ctx.strokeStyle = isSelected ? '#3b82f6' : '#ef4444';
        ctx.lineWidth   = isSelected ? 2.5 : 1.8;
        ctx.stroke();

        // Arrowhead at feature point
        const angle = Math.atan2(dy, dx);
        ctx.beginPath();
        ctx.moveTo(fx, fy);
        ctx.lineTo(fx - 9 * Math.cos(angle - Math.PI / 6), fy - 9 * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(fx - 9 * Math.cos(angle + Math.PI / 6), fy - 9 * Math.sin(angle + Math.PI / 6));
        ctx.closePath();
        ctx.fillStyle = isSelected ? '#3b82f6' : '#ef4444';
        ctx.fill();
        ctx.restore();
      }

      // Balloon circle with drop-shadow
      ctx.save();
      ctx.shadowColor   = 'rgba(0,0,0,0.45)';
      ctx.shadowBlur    = 6;
      ctx.shadowOffsetY = 2;

      ctx.beginPath();
      ctx.arc(cx, cy, BALLOON_R, 0, Math.PI * 2);
      ctx.fillStyle = isSelected ? '#2563eb' : '#ef4444';
      ctx.fill();

      ctx.shadowColor = 'transparent';
      ctx.shadowBlur  = 0;
      ctx.shadowOffsetY = 0;

      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth   = isSelected ? 2.5 : 1.8;
      ctx.stroke();

      // Number label
      ctx.fillStyle    = '#ffffff';
      ctx.font         = '700 11px Inter, -apple-system, sans-serif';
      ctx.textAlign    = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(b.balloon_no), cx, cy);

      // Feature-point drag handle (only when selected + has leader)
      if (isSelected && dist > BALLOON_R + 2) {
        ctx.beginPath();
        ctx.arc(fx, fy, 4.5, 0, Math.PI * 2);
        ctx.fillStyle   = '#3b82f6';
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth   = 1.5;
        ctx.stroke();
      }
      ctx.restore();
    });
  }, [balloons, selectedBalloonId, zoom, canvasW, canvasH, pageWidth, pageHeight]);

  useEffect(() => { draw(); }, [draw]);

  // ── Hit tests ────────────────────────────────────────────────────────────
  const hitBalloon = (imgX, imgY) => {
    const hitR = (BALLOON_R + 4) / zoom;
    for (const b of balloons) {
      if (Math.hypot(imgX - b.x, imgY - b.y) <= hitR) return b;
    }
    return null;
  };

  const hitFeature = (imgX, imgY) => {
    const hitR = 8 / zoom;
    for (const b of balloons) {
      if (b.id === selectedBalloonId &&
          Math.hypot(imgX - b.feature_x, imgY - b.feature_y) <= hitR) return b;
    }
    return null;
  };

  // ── Mouse down ───────────────────────────────────────────────────────────
  const handleMouseDown = (e) => {
    const imgX = e.nativeEvent.offsetX / zoom;
    const imgY = e.nativeEvent.offsetY / zoom;

    // Feature point drag (only when a balloon is selected)
    const fHit = hitFeature(imgX, imgY);
    if (fHit) {
      dragRef.current = {
        id: fHit.id, part: 'feature',
        origX: fHit.x,         origY: fHit.y,
        origFx: fHit.feature_x, origFy: fHit.feature_y,
        startImgX: imgX,        startImgY: imgY,
        moved: false,
      };
      return;
    }

    // Balloon body drag / click
    const bHit = hitBalloon(imgX, imgY);
    if (bHit) {
      dragRef.current = {
        id: bHit.id, part: 'balloon',
        origX: bHit.x,          origY: bHit.y,
        origFx: bHit.feature_x, origFy: bHit.feature_y,
        startImgX: imgX,         startImgY: imgY,
        moved: false,
      };
      setSelectedBalloonId(bHit.id);
      return;
    }

    // Blank area click
    if (mode === 'manual') {
      setSelectedBalloonId(null);
      axios.post(`${API}/balloons`, {
        document_id: documentId,
        x: imgX + 60, y: imgY - 60,
        feature_x: imgX, feature_y: imgY,
        page: currentPage,
        text: '?', type: 'Note',
      }).then(({ data }) => {
        onBalloonAdded(data);
        setSelectedBalloonId(data.id);
        onBalloonClick && onBalloonClick(data.id);
      }).catch(console.error);
    } else {
      setSelectedBalloonId(null);
    }
  };

  // ── Mouse move — live redraw during drag ────────────────────────────────
  const handleMouseMove = useCallback((e) => {
    if (!dragRef.current) return;
    const imgX = e.nativeEvent.offsetX / zoom;
    const imgY = e.nativeEvent.offsetY / zoom;
    const d = dragRef.current;
    const dx = imgX - d.startImgX;
    const dy = imgY - d.startImgY;

    if (Math.hypot(dx, dy) > 2) dragRef.current.moved = true;
    if (!dragRef.current.moved) return;

    // C1 FIX: dragging the balloon body moves ONLY the badge (x,y).
    // The leader tip (feature_x, feature_y) stays pinned to the drawing geometry.
    const updated = balloons.map((b) => {
      if (b.id !== d.id) return b;
      if (d.part === 'balloon') {
        return { ...b, x: d.origX + dx, y: d.origY + dy };  // leader TIP stays put
      }
      return { ...b, feature_x: d.origFx + dx, feature_y: d.origFy + dy };
    });

    // Lightweight redraw
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvasW, canvasH);

    updated.forEach((b) => {
      const cx = b.x * zoom, cy = b.y * zoom;
      const fx = b.feature_x * zoom, fy = b.feature_y * zoom;
      const isSelected = b.id === selectedBalloonId;
      const dv = Math.hypot(fx - cx, fy - cy);

      if (dv > BALLOON_R + 2) {
        const ang = Math.atan2(fy - cy, fx - cx);
        ctx.beginPath();
        ctx.moveTo(cx + (fx - cx) / dv * BALLOON_R, cy + (fy - cy) / dv * BALLOON_R);
        ctx.lineTo(fx, fy);
        ctx.strokeStyle = isSelected ? '#3b82f6' : '#ef4444';
        ctx.lineWidth = 1.8;
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(fx, fy);
        ctx.lineTo(fx - 8 * Math.cos(ang - Math.PI / 6), fy - 8 * Math.sin(ang - Math.PI / 6));
        ctx.lineTo(fx - 8 * Math.cos(ang + Math.PI / 6), fy - 8 * Math.sin(ang + Math.PI / 6));
        ctx.closePath();
        ctx.fillStyle = isSelected ? '#3b82f6' : '#ef4444';
        ctx.fill();
      }

      ctx.beginPath();
      ctx.arc(cx, cy, BALLOON_R, 0, Math.PI * 2);
      ctx.fillStyle = isSelected ? '#2563eb' : '#ef4444';
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = isSelected ? 2.5 : 1.8;
      ctx.stroke();

      ctx.fillStyle    = '#ffffff';
      ctx.font         = '700 11px Inter, sans-serif';
      ctx.textAlign    = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(b.balloon_no), cx, cy);
    });
  }, [balloons, selectedBalloonId, zoom, canvasW, canvasH]);

  // ── Mouse up — commit drag or register click ─────────────────────────────
  // C2 FIX: listen on window so releasing outside canvas always terminates drag
  useEffect(() => {
    const handleMouseUp = async (e) => {
      const d = dragRef.current;
      if (!d) return;
      dragRef.current = null;

      if (!d.moved) {
        // Pure click — open details for this balloon in the sidebar
        if (d.part === 'balloon' || d.part === 'feature') {
          onBalloonClick && onBalloonClick(d.id);
        }
        return;
      }

      // Commit moved position to backend
      let payload;
      // For canvas coords: we need the final image coords
      // They were computed in mousemove from d.orig* + dx/dy.
      // We get the latest position from the canvas event offset if available.
      const canvasEl = canvasRef.current;
      if (!canvasEl) return;

      const rect = canvasEl.getBoundingClientRect();
      const rawX = (e.clientX - rect.left) / zoom;
      const rawY = (e.clientY - rect.top)  / zoom;
      const dx = rawX - d.startImgX;
      const dy = rawY - d.startImgY;

      if (d.part === 'balloon') {
        // C1 FIX: only update badge position, NOT the leader tip
        payload = { x: d.origX + dx, y: d.origY + dy };
      } else {
        payload = { feature_x: d.origFx + dx, feature_y: d.origFy + dy };
      }

      try {
        const { data } = await axios.put(`${API}/balloons/${d.id}`, payload);
        onBalloonMoved && onBalloonMoved(data);
      } catch (err) {
        console.error('Failed to move balloon', err);
      }
    };

    window.addEventListener('mouseup', handleMouseUp);
    return () => window.removeEventListener('mouseup', handleMouseUp);
  }, [zoom, onBalloonMoved, onBalloonClick]);

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
            style={{
              position: 'absolute',
              top: 0, left: 0,
              pointerEvents: 'all',
            }}
          />
        </div>
      ) : (
        <div className="canvas-placeholder glass-panel">
          <p>Upload a PDF to start annotating</p>
        </div>
      )}
    </div>
  );
}
