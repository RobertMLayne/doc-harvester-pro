// filename: scraper-service.ts  (bonus)
import express from "express";
import {chromium} from "playwright";
const app = express(); app.use(express.json());

app.post("/render", async (req, res) => {
  const {url} = req.body;
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage();
  await page.goto(url);
  const html = await page.$eval("main, body", el => el.outerHTML);
  await browser.close();
  res.send({html});
});

if (require.main === module) app.listen(8080);
export default app;
