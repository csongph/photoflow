from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from urllib.parse import parse_qs, quote

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response


COOKIE_NAME = "momentlink_admin"
SESSION_TTL_SECONDS = 12 * 60 * 60


def admin_password() -> str:
    return (os.getenv("ADMIN_PIN", "") or os.getenv("ADMIN_PASSWORD", "")).strip()


def auth_enabled() -> bool:
    return bool(admin_password())


def _secret() -> bytes:
    material = os.getenv("ADMIN_SESSION_SECRET", "") or os.getenv("JWT_SECRET_KEY", "") or admin_password()
    return hashlib.sha256(material.encode("utf-8")).digest()


def _sign(value: str) -> str:
    return hmac.new(_secret(), value.encode("utf-8"), hashlib.sha256).hexdigest()


def make_session() -> str:
    expires = str(int(time.time()) + SESSION_TTL_SECONDS)
    payload = f"admin:{expires}"
    token = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
    return f"{token}.{_sign(token)}"


def valid_session(token: str) -> bool:
    try:
        encoded, signature = token.split(".", 1)
        if not hmac.compare_digest(signature, _sign(encoded)):
            return False
        payload = base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8")
        user, expires = payload.split(":", 1)
        return user == "admin" and int(expires) >= int(time.time())
    except Exception:
        return False


def is_public_path(path: str) -> bool:
    if path in {"/login", "/api/auth/login", "/api/auth/logout", "/api/auth/status", "/healthz"}:
        return True
    if path.startswith(("/api/gallery/", "/gallery/", "/media/", "/css/", "/js/", "/static/")):
        return path != "/gallery/local-preview"
    return False


def wants_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "")


async def require_admin(request: Request, call_next):
    if not auth_enabled() or is_public_path(request.url.path):
        return await call_next(request)
    if valid_session(request.cookies.get(COOKIE_NAME, "")):
        return await call_next(request)
    if wants_html(request) and request.method == "GET":
        return RedirectResponse(f"/login?next={quote(str(request.url.path))}", status_code=303)
    return JSONResponse({"detail": "Admin login required"}, status_code=401)


def login_page(error: str = "") -> HTMLResponse:
    error_html = f"<p class='error'>{error}</p>" if error else ""
    return HTMLResponse(f"""<!doctype html>
<html lang="th">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Login · MomentLink</title>
  <style>
    * {{ box-sizing: border-box; }}
    :root {{
      --ink: #fffaf1;
      --muted: rgba(255,250,241,.68);
      --deep: #101412;
      --panel: rgba(17, 21, 19, .78);
      --line: rgba(255,250,241,.14);
      --accent: #36c49b;
      --accent-dark: #12876d;
      --paper: #fffaf1;
    }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 26px;
      font-family: Inter, Segoe UI, Arial, sans-serif;
      background:
        linear-gradient(180deg, rgba(5,7,6,.20), rgba(5,7,6,.78)),
        #121612;
      color: var(--ink);
      overflow-x: hidden;
    }}
    main {{
      position: relative;
      width: min(1080px, 100%);
      min-height: 640px;
      display: grid;
      align-items: end;
      padding: 24px;
      overflow: hidden;
      border: 1px solid rgba(255,250,241,.12);
      border-radius: 8px;
      background:
        linear-gradient(180deg, rgba(12,15,13,.08), rgba(12,15,13,.88)),
        #171b18;
      box-shadow: 0 34px 100px rgba(0,0,0,.38);
    }}
    .contact-sheet {{
      position: relative;
      position: absolute;
      inset: -64px -38px 130px;
      display: grid;
      grid-template-columns: repeat(6, minmax(130px, 1fr));
      gap: 14px;
      transform: rotate(-4deg);
      opacity: .78;
    }}
    .shot {{
      min-height: 170px;
      display: grid;
      align-content: end;
      padding: 12px;
      border: 1px solid rgba(255,255,255,.13);
      border-radius: 8px;
      background:
        linear-gradient(180deg, transparent 42%, rgba(0,0,0,.66)),
        linear-gradient(135deg, rgba(54,196,155,.34), rgba(255,250,241,.11));
      box-shadow: inset 0 1px 0 rgba(255,255,255,.12), 0 22px 48px rgba(0,0,0,.22);
      color: rgba(255,250,241,.80);
      font-size: 11px;
      font-weight: 900;
      letter-spacing: 0;
    }}
    .shot:nth-child(2n) {{
      min-height: 210px;
      background:
        linear-gradient(180deg, transparent 38%, rgba(0,0,0,.70)),
        linear-gradient(135deg, rgba(185,72,103,.32), rgba(255,250,241,.10));
    }}
    .shot:nth-child(3n) {{
      min-height: 150px;
      background:
        linear-gradient(180deg, transparent 45%, rgba(0,0,0,.70)),
        linear-gradient(135deg, rgba(217,152,47,.28), rgba(54,196,155,.18));
    }}
    .topbar {{
      position: absolute;
      z-index: 2;
      top: 24px;
      left: 24px;
      right: 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
    }}
    .identity {{
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px 12px;
      border: 1px solid rgba(255,250,241,.12);
      border-radius: 8px;
      background: rgba(7,10,9,.34);
      backdrop-filter: blur(14px);
    }}
    .mark {{
      width: 38px;
      height: 38px;
      display: grid;
      place-items: center;
      border-radius: 7px;
      background:
        linear-gradient(135deg, var(--accent), var(--accent-dark));
      color: #fff;
      font-weight: 950;
      font-size: 19px;
    }}
    .identity b {{
      display: block;
      color: #fffaf1;
      font-size: 15px;
      line-height: 1.1;
    }}
    .identity span {{
      color: rgba(255,250,241,.58);
      font-size: 12px;
      font-weight: 760;
    }}
    .admin-chip {{
      padding: 10px 13px;
      border: 1px solid rgba(255,250,241,.14);
      border-radius: 8px;
      background: rgba(7,10,9,.34);
      backdrop-filter: blur(14px);
      color: rgba(255,250,241,.78);
      font-size: 12px;
      font-weight: 900;
    }}
    .login-panel {{
      position: relative;
      z-index: 2;
      width: min(520px, 100%);
      margin-left: auto;
      padding: 24px;
      border: 1px solid rgba(255,250,241,.16);
      border-radius: 8px;
      background: var(--panel);
      backdrop-filter: blur(22px);
      box-shadow: 0 24px 70px rgba(0,0,0,.42);
    }}
    .panel-head {{
      display: grid;
      gap: 9px;
      margin-bottom: 24px;
    }}
    .kicker {{
      margin: 0;
      color: var(--accent);
      font-size: 12px;
      font-weight: 950;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 0;
      color: #fffaf1;
      font-size: clamp(34px, 5vw, 54px);
      line-height: .96;
    }}
    p {{
      color: var(--muted);
      line-height: 1.58;
      margin: 0;
    }}
    form {{ margin-top: 0; }}
    .pin-label {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
      color: rgba(255,250,241,.70);
      font-size: 13px;
      font-weight: 850;
    }}
    .pin-grid {{
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 10px;
      margin-bottom: 18px;
    }}
    .pin {{
      width: 100%;
      aspect-ratio: 1;
      min-height: 60px;
      border: 1px solid rgba(255,250,241,.18);
      border-radius: 8px;
      text-align: center;
      font: 900 26px/1 Inter, Segoe UI, Arial, sans-serif;
      background: rgba(255,250,241,.10);
      color: #fffaf1;
      outline: none;
      box-shadow: inset 0 1px 0 rgba(255,255,255,.10);
      transition: border-color .16s ease, box-shadow .16s ease, background .16s ease, transform .16s ease;
    }}
    .pin:focus {{
      border-color: var(--accent);
      background: rgba(255,250,241,.16);
      box-shadow: 0 0 0 4px rgba(54,196,155,.18), inset 0 1px 0 rgba(255,255,255,.16);
      transform: translateY(-1px);
    }}
    button {{
      width: 100%;
      border: 0;
      border-radius: 8px;
      padding: 14px;
      min-height: 52px;
      font-weight: 950;
      cursor: pointer;
      background: linear-gradient(135deg, var(--accent), var(--accent-dark));
      color: #fff;
      box-shadow: 0 18px 36px rgba(18,135,109,.30);
      transition: transform .16s ease, box-shadow .16s ease;
    }}
    button:hover {{
      transform: translateY(-1px);
      box-shadow: 0 22px 42px rgba(18,135,109,.36);
    }}
    .error {{
      margin: 0 0 16px;
      padding: 12px;
      border-radius: 8px;
      background: rgba(217,87,87,.16);
      color: #ffd4d4;
      font-weight: 850;
      border: 1px solid rgba(217,87,87,.28);
    }}
    .hint {{
      margin-top: 14px;
      padding: 11px 12px;
      border: 1px solid rgba(255,250,241,.11);
      border-radius: 8px;
      background: rgba(255,250,241,.06);
      font-size: 13px;
      text-align: center;
    }}
    @media (max-width: 760px) {{
      body {{ padding: 14px; }}
      main {{
        min-height: calc(100vh - 28px);
        padding: 18px;
        align-items: center;
      }}
      .contact-sheet {{
        inset: -30px -80px 100px;
        grid-template-columns: repeat(4, minmax(120px, 1fr));
        gap: 10px;
        opacity: .48;
      }}
      .topbar {{
        top: 18px;
        left: 18px;
        right: 18px;
      }}
      .admin-chip {{ display: none; }}
      .login-panel {{
        margin: 110px auto 0;
        padding: 20px;
      }}
      h1 {{ font-size: 38px; }}
    }}
    @media (max-width: 420px) {{
      .identity span {{ display: none; }}
      .contact-sheet {{ grid-template-columns: repeat(3, minmax(110px, 1fr)); }}
      .pin-grid {{ gap: 6px; }}
      .pin {{ min-height: 46px; font-size: 22px; }}
    }}
  </style>
</head>
<body>
  <main>
    <div class="contact-sheet" aria-hidden="true">
      <div class="shot">IMG_2401.JPG</div><div class="shot">DSC_0959.JPG</div><div class="shot">AV_TEAM.JPG</div>
      <div class="shot">SCHOOL_DAY.JPG</div><div class="shot">GALLERY.JPG</div><div class="shot">EXPORT.JPG</div>
      <div class="shot">EVENT_01.JPG</div><div class="shot">QR_READY.JPG</div><div class="shot">DRIVE.JPG</div>
      <div class="shot">PHOTO_SET.JPG</div><div class="shot">FINISHED.JPG</div><div class="shot">LIVE.JPG</div>
    </div>
    <div class="topbar">
      <div class="identity"><div class="mark">M</div><div><b>MomentLink</b><span>Local Photo Console</span></div></div>
      <div class="admin-chip">Admin PIN Required</div>
    </div>
    <section class="login-panel" aria-label="Admin login">
      <div class="panel-head">
        <p class="kicker">Secure Access</p>
        <h1>เข้าสู่ระบบ</h1>
        <p>กรอก PIN 6 หลักเพื่อเปิดแผงควบคุมงานถ่ายภาพของทีมงาน</p>
      </div>
      {error_html}
      <form id="pinForm" method="post" action="/api/auth/login">
        <input type="hidden" name="next" value="/">
        <input id="password" name="password" type="hidden">
        <div class="pin-label"><span>Admin PIN</span><span>6 digits</span></div>
        <div class="pin-grid" aria-label="Admin PIN">
          <input class="pin" inputmode="numeric" maxlength="1" autocomplete="one-time-code" autofocus>
          <input class="pin" inputmode="numeric" maxlength="1">
          <input class="pin" inputmode="numeric" maxlength="1">
          <input class="pin" inputmode="numeric" maxlength="1">
          <input class="pin" inputmode="numeric" maxlength="1">
          <input class="pin" inputmode="numeric" maxlength="1">
        </div>
        <button>เข้าสู่ระบบ</button>
        <p class="hint">หน้านี้ล็อกเฉพาะฝั่งแอดมิน ฝั่ง Gallery ผู้ใช้ยังเปิดได้ตามลิงก์งาน</p>
      </form>
    </section>
  </main>
  <script>
    const boxes = [...document.querySelectorAll(".pin")];
    const hidden = document.querySelector("#password");
    const form = document.querySelector("#pinForm");
    function sync() {{ hidden.value = boxes.map(box => box.value).join(""); }}
    boxes.forEach((box, index) => {{
      box.addEventListener("input", () => {{
        box.value = box.value.replace(/\\D/g, "").slice(0, 1);
        sync();
        if (box.value && boxes[index + 1]) boxes[index + 1].focus();
      }});
      box.addEventListener("keydown", ev => {{
        if (ev.key === "Backspace" && !box.value && boxes[index - 1]) boxes[index - 1].focus();
      }});
      box.addEventListener("paste", ev => {{
        ev.preventDefault();
        const digits = (ev.clipboardData.getData("text") || "").replace(/\\D/g, "").slice(0, 6);
        digits.split("").forEach((digit, i) => {{ if (boxes[i]) boxes[i].value = digit; }});
        sync();
        boxes[Math.min(digits.length, 5)]?.focus();
      }});
    }});
    form.addEventListener("submit", ev => {{
      sync();
      if (!/^\\d{{6}}$/.test(hidden.value)) {{
        ev.preventDefault();
        boxes.find(box => !box.value)?.focus();
      }}
    }});
  </script>
</body>
</html>""")


async def login(request: Request) -> Response:
    body = (await request.body()).decode("utf-8", errors="ignore")
    form = parse_qs(body)
    password = form.get("password", [""])[0]
    next_path = form.get("next", ["/"])[0]
    if not hmac.compare_digest(password, admin_password()):
        return login_page("รหัสผ่านไม่ถูกต้อง")
    response = RedirectResponse(next_path if next_path.startswith("/") else "/", status_code=303)
    response.set_cookie(COOKIE_NAME, make_session(), httponly=True, samesite="lax", max_age=SESSION_TTL_SECONDS)
    return response


def logout() -> Response:
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response
