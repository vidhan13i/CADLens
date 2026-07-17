import { useState, useRef } from "react";
import axios from "axios";
import PDFViewer from "../components/PDFViewer";
import { UploadCloud, File, Play, FileSpreadsheet } from "lucide-react";

export default function UploadPage() {
    const [file, setFile] = useState(null);
    const [uploadedUrl, setUploadedUrl] = useState("");
    const [isUploading, setIsUploading] = useState(false);
    const [isDetecting, setIsDetecting] = useState(false);
    const [renderKey, setRenderKey] = useState(0);
    const fileInputRef = useRef(null);

    const handleFileChange = (e) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
        }
    };

    const handleUpload = async () => {
        if (!file) return;

        setIsUploading(true);
        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await axios.post(
                "http://localhost:5000/api/upload",
                formData
            );
            setUploadedUrl(res.data.fileUrl);
        } catch (err) {
            console.error(err);
            alert("Upload failed");
        }
        setIsUploading(false);
    };

    const handleAutoDetect = async () => {
        setIsDetecting(true);
        try {
            const fileName = uploadedUrl.split("/").pop();
            const res = await axios.post(
                "http://localhost:5000/api/balloons/auto",
                {
                    filePath: fileName,
                }
            );

            const autoBalloons = res.data.map((d, i) => ({
                id: Date.now() + i,
                x: d.x,
                y: d.y,
                number: i + 1,
                type: d.type,
                description: d.text,
                remarks: "",
            }));

            await axios.post("http://localhost:5000/api/balloons", {
                balloons: autoBalloons,
                fileUrl: uploadedUrl
            });
            
            setRenderKey(prev => prev + 1);
        } catch (err) {
            console.error(err);
            alert("Auto Detect failed");
        }
        setIsDetecting(false);
    };

    const exportExcel = () => {
        window.open(`http://localhost:5000/api/balloons/export/${encodeURIComponent(uploadedUrl)}`);
    };

    return (
        <div style={styles.container}>
            <div style={styles.header}>
                <h2 style={styles.title}>Project Workspace</h2>
                <p style={styles.subtitle}>Upload your CAD drawings to automatically extract dimensional balloons and annotations.</p>
            </div>

            {!uploadedUrl ? (
                <div style={styles.uploadSection}>
                    <div 
                        className="glass-panel" 
                        style={styles.dropZone}
                        onClick={() => fileInputRef.current?.click()}
                    >
                        <input
                            type="file"
                            accept="application/pdf"
                            onChange={handleFileChange}
                            ref={fileInputRef}
                        />
                        <div style={styles.uploadIcon}>
                            <UploadCloud size={48} color="var(--primary)" />
                        </div>
                        <h3 style={styles.dropTitle}>
                            {file ? file.name : "Drag & Drop your PDF here"}
                        </h3>
                        <p style={styles.dropText}>
                            {file ? "Click Upload to continue" : "Or click to browse from your computer"}
                        </p>
                        
                        {file && (
                            <button 
                                className="btn-primary" 
                                style={{ marginTop: '24px' }}
                                onClick={(e) => { e.stopPropagation(); handleUpload(); }}
                                disabled={isUploading}
                            >
                                {isUploading ? "Uploading..." : "Upload Document"}
                            </button>
                        )}
                    </div>
                </div>
            ) : (
                <div style={styles.workspace}>
                    <div style={styles.toolbar} className="glass-panel">
                        <div style={styles.fileInfo}>
                            <File size={20} color="var(--accent)" />
                            <span>{file?.name || "Uploaded Document"}</span>
                        </div>
                        <div style={styles.actions}>
                            <button 
                                className="btn-primary" 
                                onClick={handleAutoDetect} 
                                disabled={isDetecting}
                                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
                            >
                                <Play size={16} />
                                {isDetecting ? "Processing..." : "Auto Detect Balloons"}
                            </button>
                            <button 
                                className="btn-secondary" 
                                onClick={exportExcel}
                                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
                            >
                                <FileSpreadsheet size={16} />
                                Export Excel
                            </button>
                        </div>
                    </div>

                    <div style={styles.viewerContainer} className="glass-panel">
                        <PDFViewer key={renderKey} fileUrl={uploadedUrl} />
                    </div>
                </div>
            )}
        </div>
    );
}

const styles = {
    container: {
        maxWidth: '1200px',
        margin: '0 auto',
        width: '100%'
    },
    header: {
        marginBottom: '40px'
    },
    title: {
        fontSize: '32px',
        fontWeight: '700',
        marginBottom: '12px',
        color: 'var(--text-main)'
    },
    subtitle: {
        fontSize: '16px',
        color: 'var(--text-muted)'
    },
    uploadSection: {
        display: 'flex',
        justifyContent: 'center',
        paddingTop: '20px'
    },
    dropZone: {
        width: '100%',
        maxWidth: '600px',
        padding: '64px 32px',
        borderRadius: '16px',
        border: '2px dashed rgba(59, 130, 246, 0.3)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        cursor: 'pointer',
        transition: 'all 0.2s',
        textAlign: 'center'
    },
    uploadIcon: {
        background: 'rgba(59, 130, 246, 0.1)',
        padding: '24px',
        borderRadius: '50%',
        marginBottom: '24px'
    },
    dropTitle: {
        fontSize: '20px',
        fontWeight: '600',
        marginBottom: '8px',
        color: '#fff'
    },
    dropText: {
        color: 'var(--text-muted)'
    },
    workspace: {
        display: 'flex',
        flexDirection: 'column',
        gap: '24px'
    },
    toolbar: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '16px 24px',
        borderRadius: '12px'
    },
    fileInfo: {
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        fontWeight: '500'
    },
    actions: {
        display: 'flex',
        gap: '12px'
    },
    viewerContainer: {
        padding: '24px',
        borderRadius: '12px',
        display: 'flex',
        justifyContent: 'center',
        overflow: 'auto',
        maxHeight: 'calc(100vh - 250px)'
    }
};