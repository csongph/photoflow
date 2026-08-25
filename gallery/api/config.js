export default function handler(req, res) {
  const apiUrl = process.env.MOMENTLINK_API_URL || "";
  res.setHeader("Content-Type", "application/javascript; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.status(200).send(`window.MOMENTLINK_API_URL=${JSON.stringify(apiUrl)};`);
}
