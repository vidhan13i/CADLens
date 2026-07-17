const mongoose = require("mongoose");

const balloonSchema = new mongoose.Schema({
    fileUrl: String,
    number: Number,
    x: Number,
    y: Number,
    page: Number,

    // NEW FIELDS
    type: { type: String, default: "dimension" },
    description: { type: String, default: "" },
    remarks: { type: String, default: "" },
});

module.exports = mongoose.model("Balloon", balloonSchema);