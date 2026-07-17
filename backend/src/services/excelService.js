const ExcelJS = require("exceljs");

const generateExcel = async (balloons) => {
    const workbook = new ExcelJS.Workbook();
    const sheet = workbook.addWorksheet("Balloons");

    sheet.columns = [
        { header: "Balloon No", key: "number" },
        { header: "Type", key: "type" },
        { header: "Description", key: "description" },
        { header: "Remarks", key: "remarks" },
        { header: "Page", key: "page" },
    ];

    balloons.forEach((b) => sheet.addRow(b));

    return workbook;
};

module.exports = generateExcel;