const express = require("express");
const cors = require("cors");

const app = express();

app.use(cors());
app.use(express.json());

const balloonRoutes = require("./routes/balloonRoutes");

app.use("/api/balloons", balloonRoutes);

const uploadRoutes = require("./routes/uploadRoutes");

app.use("/api/upload", uploadRoutes);
const path = require("path");

app.use("/files", express.static(path.join(__dirname, "..", "..", "storage", "uploads")));

app.get("/", (req, res) => {
    res.send("API Running...");
});

module.exports = app;