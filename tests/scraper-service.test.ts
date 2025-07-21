// filename: scraper-service.test.ts
import request from "supertest";
import app from "./scraper-service";

describe("renderer", () => {
  it("returns html", async () => {
    const res = await request(app).post("/render").send({url: "https://example.com"});
    expect(res.status).toBe(200);
    expect(res.body.html).toContain("<html");
  });
});
