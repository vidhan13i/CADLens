import { Document, Page } from "react-pdf";
import { useState } from "react";
import BalloonLayer from "./BalloonLayer";

export default function PDFViewer({ fileUrl }) {
    const [numPages, setNumPages] = useState(null);
    const [pageNumber, setPageNumber] = useState(1);

    function onDocumentLoadSuccess({ numPages }) {
        setNumPages(numPages);
    }

    return (
        <div>
            <h3>PDF Viewer</h3>
            <div
                style={{
                    position: "relative",
                    display: "inline-block",
                }}
            >
                <Document file={fileUrl} onLoadSuccess={onDocumentLoadSuccess}>
                    <Page
                        pageNumber={pageNumber}
                        width={1000}
                        renderTextLayer={false}   // ✅ THIS FIXES YOUR ISSUE
                        renderAnnotationLayer={false}
                    />
                </Document>
                <BalloonLayer fileUrl={fileUrl} />
            </div>
            <div style={{ marginTop: "10px" }}>
                <button
                    onClick={() => setPageNumber((p) => Math.max(p - 1, 1))}
                >
                    Prev
                </button>

                <span style={{ margin: "0 10px" }}>
                    Page {pageNumber} of {numPages}
                </span>

                <button
                    onClick={() =>
                        setPageNumber((p) =>
                            numPages ? Math.min(p + 1, numPages) : p
                        )
                    }
                >
                    Next
                </button>
            </div>
        </div>
    );
}
