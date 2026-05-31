const axios = require("axios");

const processPDF = async (filePath) => {
  const res = await axios.post("http://localhost:8000/process", {
    file_path: filePath,
  });

  return res.data;
};

module.exports = processPDF;