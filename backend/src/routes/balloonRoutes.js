const express = require("express");
const path = require("path");
const router = express.Router();
const Balloon = require("../models/Balloon");
const generateExcel = require("../services/excelService");
const processPDF = require("../services/processingService");

// 🔹 AUTO DETECT
router.post("/auto", async (req, res) => {
  try {
    let { filePath } = req.body;
    
    if (filePath) {
      const fileName = path.basename(filePath);
      filePath = path.resolve(__dirname, "..", "..", "..", "storage", "uploads", fileName);
    }

    const data = await processPDF(filePath);

    res.json(data);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Auto detection failed" });
  }
});

// 🔹 SAVE balloons
router.post("/", async (req, res) => {
    const { balloons, fileUrl } = req.body;

    await Balloon.deleteMany({ fileUrl });

    const saved = await Balloon.insertMany(
        balloons.map((b, i) => ({
            ...b,
            fileUrl,
            number: i + 1,
        }))
    );

    res.json(saved);
});
// 🔥 EXPORT EXCEL (ADD THIS HERE)
router.get("/export/:fileUrl", async (req, res) => {
    const fileUrl = decodeURIComponent(req.params.fileUrl);

    const balloons = await Balloon.find({ fileUrl });

    const workbook = await generateExcel(balloons);

    res.setHeader(
        "Content-Type",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    );

    res.setHeader(
        "Content-Disposition",
        "attachment; filename=balloons.xlsx"
    );
    console.log("EXPORT HIT", req.params.fileUrl);
    await workbook.xlsx.write(res);
    res.end();
});

// 🔹 GET balloons
router.get("/:fileUrl", async (req, res) => {
    const fileUrl = decodeURIComponent(req.params.fileUrl);

    const balloons = await Balloon.find({ fileUrl });

    res.json(balloons);
});



module.exports = router;