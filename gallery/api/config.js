export default function handler(req, res) {
  res.setHeader("Content-Type", "application/javascript; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  // API calls use the same-origin Vercel rewrite proxy. This also keeps the
  // gallery PIN cookie first-party and avoids browser CORS restrictions.
  res.status(200).send("window.MOMENTLINK_API_URL=\"\";");
}
