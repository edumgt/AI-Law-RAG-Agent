require("dotenv").config();
const fs = require("fs");
const path = require("path");

const p = process.env.SQLITE_PATH || "./data/app.db";
const abs = path.isAbsolute(p) ? p : path.join(process.cwd(), p);

if (fs.existsSync(abs)) {
  fs.unlinkSync(abs);
  console.log("deleted:", abs);
} else {
  console.log("not found:", abs);
}
