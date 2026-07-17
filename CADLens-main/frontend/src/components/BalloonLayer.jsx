import { useState, useEffect } from "react";
import axios from "axios";
import BalloonEditor from "./BalloonEditor";

export default function BalloonLayer({ fileUrl }) {
    const [balloons, setBalloons] = useState([]);
    const [selected, setSelected] = useState(null); // ✅ FIXED

    // 🔹 LOAD balloons
    useEffect(() => {
        if (!fileUrl) return;

        axios
            .get(`http://localhost:5000/api/balloons/${encodeURIComponent(fileUrl)}`)
            .then((res) => {
                const data = res.data.map((b) => ({
                    ...b,
                    id: b._id || b.id,
                }));
                setBalloons(data);
            })
            .catch(console.error);
    }, [fileUrl]);

    // 🔹 ADD balloon
    const handleClick = (e) => {
        if (e.target !== e.currentTarget) return;

        const rect = e.currentTarget.getBoundingClientRect();

        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        const newBalloon = {
            id: Date.now(),
            x,
            y,
            number: balloons.length + 1,
            type: "dimension",
            description: "",
            remarks: "",
        };

        setBalloons((prev) => [...prev, newBalloon]);
    };

    // 🔹 UPDATE balloon (for editor)
    const updateBalloon = (updated) => {
        setBalloons((prev) =>
            prev.map((b) => (b.id === updated.id ? updated : b))
        );

        setSelected(updated);
    };

    // 🔹 SAVE balloons
    const saveBalloons = async () => {
        try {
            await axios.post("http://localhost:5000/api/balloons", {
                fileUrl,
                balloons,
            });
            alert("Saved!");
        } catch (err) {
            console.error(err);
            alert("Save failed");
        }
    };

    return (
        <div
            onClick={handleClick}
            style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: "100%",
                cursor: "crosshair",
            }}
        >
            <button
                className="btn-primary"
                onClick={(e) => {
                    e.stopPropagation();
                    saveBalloons();
                }}
                style={{
                    position: "absolute",
                    top: 16,
                    right: 16,
                    zIndex: 1000,
                    padding: "8px 16px",
                    fontSize: "14px",
                    boxShadow: "0 4px 10px rgba(0,0,0,0.3)"
                }}
            >
                Save
            </button>

            {balloons.map((b) => (
                <div
                    key={b.id}
                    draggable
                    onClick={(e) => {
                        e.stopPropagation();
                        setSelected(b);
                    }}
                    onDragEnd={(e) => {
                        const rect = e.currentTarget.parentElement.getBoundingClientRect();
                        const newX = e.clientX - rect.left;
                        const newY = e.clientY - rect.top;

                        setBalloons((prev) =>
                            prev.map((item) =>
                                item.id === b.id
                                    ? { ...item, x: newX, y: newY }
                                    : item
                            )
                        );
                    }}
                    style={{
                        position: "absolute",
                        left: b.x,
                        top: b.y,
                        transform: `translate(-50%, -50%) ${selected?.id === b.id ? 'scale(1.2)' : 'scale(1)'}`,
                        width: "32px",
                        height: "32px",
                        borderRadius: "50%",
                        background: selected?.id === b.id ? "var(--primary)" : "var(--accent)",
                        boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
                        border: "2px solid rgba(255,255,255,0.8)",
                        color: "white",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontWeight: "700",
                        fontSize: "14px",
                        cursor: "grab",
                        transition: "transform 0.2s ease"
                    }}
                >
                    {b.number}
                </div>
            ))}

            {selected && (
                <div
                    className="glass-panel"
                    onClick={(e) => e.stopPropagation()}
                    style={{
                        position: "fixed",
                        top: "90px",
                        right: "32px",
                        width: "320px",
                        borderRadius: "16px",
                        zIndex: 1000,
                        boxShadow: "0 10px 40px rgba(0,0,0,0.5)",
                        animation: "fade-in 0.2s ease-out"
                    }}
                >
                    <BalloonEditor
                        selected={selected}
                        updateBalloon={updateBalloon}
                        onClose={() => setSelected(null)}
                    />
                </div>
            )}
        </div>
    );
}