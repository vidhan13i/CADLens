const generateExcel = require("../services/excelService");

router.get("/export/:fileUrl", async (req, res) => {
    const balloons = await Balloon.find({
        fileUrl: req.params.fileUrl,
    });

    const workbook = await generateExcel(balloons);

    res.setHeader(
        "Content-Type",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    );

    res.setHeader(
        "Content-Disposition",
        "attachment; filename=balloons.xlsx"
    );

    await workbook.xlsx.write(res);
    res.end();
});