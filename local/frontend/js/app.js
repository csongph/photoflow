const $ = (q) => document.querySelector(q);
let kioskState = null;
function showToast(message, tone = "info") {
  let toast = document.querySelector("#appToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "appToast";
    document.body.appendChild(toast);
  }
  toast.className = `app-toast ${tone}`;
  toast.textContent = message;
  clearTimeout(window.__csbxxmToastTimer);
  window.__csbxxmToastTimer = setTimeout(() => toast.remove(), 4200);
}
window.addEventListener("unhandledrejection", event => {
  console.error(event.reason);
  showToast("เชื่อมต่อระบบไม่สำเร็จ กรุณาลองใหม่อีกครั้ง", "error");
});
const jsArg = (value) => JSON.stringify(String(value ?? ""))
  .replaceAll("&", "\\u0026")
  .replaceAll("'", "\\u0027")
  .replaceAll("<", "\\u003c")
  .replaceAll(">", "\\u003e");
const html = (value) => String(value ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[ch]));
const publicGalleryExample = (baseUrl) => {
  try {
    const url = new URL(baseUrl || "https://your-domain.com/");
    url.searchParams.set("event", "EVENT_ID");
    return url.toString();
  } catch {
    return `${String(baseUrl || "https://your-domain.com").replace(/\/$/, "")}/EVENT_ID`;
  }
};
const api = (url, opts = {}) => fetch(url, { headers: { "Content-Type": "application/json" }, ...opts }).then(async r => {
  if (r.status === 401) {
    location.href = "/login";
    throw new Error("Admin login required");
  }
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json();
});
const checkLabels = {
  incoming_folder: "โฟลเดอร์ INCOMING",
  incoming_writable: "สิทธิ์เขียน INCOMING",
  disk_space: "พื้นที่ดิสก์",
  public_gallery_url: "ลิงก์แกลเลอรี่",
  google_drive: "Google Drive"
};
function nav(active) {
  return `<aside class="nav">
    <a class="brand" href="/" aria-label="CS.BXXM STUDIO หน้าหลัก">
      <span class="brand-mark">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" class="brand-svg">
          <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
          <circle cx="12" cy="13" r="4"></circle>
        </svg>
      </span>
      <span class="brand-copy">
        <span class="brand-name">CS.BXXM <span class="brand-tag">BOOTH</span></span>
        <small class="brand-sub">STUDIO CONTROL</small>
      </span>
    </a>
    <p class="nav-caption">เมนูหลัก</p>
    <a class="${active === "dashboard" ? "active" : ""}" href="/">แดชบอร์ด</a>
    <a class="${active === "setup" ? "active" : ""}" href="/setup">เตรียมความพร้อม</a>
    <a class="${active === "events" ? "active" : ""}" href="/events">งานถ่ายภาพ</a>
    <a class="${active === "gallery" ? "active" : ""}" href="/gallery/local-preview">ตัวอย่างแกลเลอรี</a>
    <a class="${active === "archive" ? "active" : ""}" href="/archive">คลังงาน</a>
    <a class="${active === "diagnostics" ? "active" : ""}" href="/diagnostics">ตรวจระบบ</a>
    <a class="${active === "settings" ? "active" : ""}" href="/settings">ตั้งค่า</a>
    <div class="nav-spacer"></div>
    <a class="nav-logout" href="#" onclick="logoutAdmin(event)">ออกจากระบบ</a>
  </aside>`;
}

async function logoutAdmin(ev) {
  ev.preventDefault();
  await fetch("/api/auth/logout", { method: "POST" });
  location.href = "/login";
}

function layout(active, content) {
  document.body.innerHTML = `<div class="shell">${nav(active)}<main class="main ${active === "gallery" ? "main-gallery" : ""}">${content}</main></div>`;
}

async function loadDashboard() {
  layout("dashboard", `<div class="top hero-panel"><div><p class="kicker">CS.BXXM STUDIO · PHOTO BOOTH</p><h1>ภาพรวมงานถ่าย</h1><p class="hero-note">ดูสถานะรูป จัดการกรอบ และเปิดแกลเลอรีให้ผู้ร่วมงานจากที่เดียว</p></div><div class="row hero-actions-admin"><a class="button secondary" href="/setup">ตรวจความพร้อม</a><button class="secondary" onclick="loadDashboard()">รีเฟรชข้อมูล</button><div class="status pill"><span class="dot"></span><span id="live">กำลังโหลด</span></div></div></div>
  <div class="grid">
    <section class="panel span-8 main-card"><div class="section-heading"><div><p class="section-eyebrow">กำลังดำเนินการ</p><h2>งานที่กำลังทำ</h2></div></div><div id="active"></div></section>
    <section class="panel span-4"><div class="section-heading"><div><p class="section-eyebrow">ภาพรวม</p><h2>สถานะระบบ</h2></div></div><div id="health"></div></section>
    <section class="panel span-12"><div class="section-heading"><div><p class="section-eyebrow">เช็กก่อนเริ่ม</p><h2>ความพร้อมของงาน</h2></div></div><div id="preflight"></div></section>
    <section class="panel span-7"><div class="section-heading"><div><p class="section-eyebrow">อัปเดตล่าสุด</p><h2>รูปภาพล่าสุด</h2></div></div><div class="thumbs" id="thumbs"></div></section>
    <section class="panel span-5"><div class="section-heading"><div><p class="section-eyebrow">งานเบื้องหลัง</p><h2>คิวการทำงาน</h2></div></div><div id="queues"></div></section>
  </div>`);
  const data = await api("/api/dashboard");
  if (!data.active_event) {
    $("#live").textContent = "ยังไม่มีงานที่เริ่มอยู่";
    $("#active").innerHTML = `<div class="empty-state dashboard-empty"><span class="empty-icon">＋</span><b>พร้อมเริ่มงานถ่ายภาพใหม่</b><span>สร้างงานเพื่อกำหนดแกลเลอรีและโฟลเดอร์รับรูป</span><a class="button" href="/events">สร้างงานถ่ายภาพ</a></div>`;
    return;
  }
  $("#live").textContent = data.active_event.status;
  const c = data.counts;
  const metricLabels = { captured: "รับรูปแล้ว", processed: "ประมวลผลแล้ว", uploaded: "อัปโหลดแล้ว", published: "แสดงในแกลเลอรี", review: "รอตรวจ", queue: "รอประมวลผล", failed: "ผิดพลาด" };
  $("#active").innerHTML = `<div class="event-title"><h1>${html(data.active_event.name)}</h1><span class="status pill"><span class="dot"></span>${html(data.active_event.status)}</span></div>
    <div class="metrics">
      ${["captured","processed","uploaded","published","review","queue","failed"].map(k => `<div class="metric"><span class="muted">${metricLabels[k]}</span><b>${c[k] ?? 0}</b></div>`).join("")}
    </div>
    <p class="muted">INCOMING Folder</p><div class="pathbox">${html(data.active_event.incoming_path)}</div>
    <div class="row" style="margin-top:14px">
      <button onclick='navigator.clipboard.writeText(${jsArg(data.active_event.incoming_path)})'>Copy Path</button>
      <button class="secondary" onclick='openFolder(${jsArg(data.active_event.id)})'>Open Folder</button>
      <button class="secondary" onclick='showQr(${jsArg(data.active_event.id)}, ${jsArg(data.active_event.gallery_url)}, ${jsArg(data.active_event.name)})'>Show QR</button>
      <button class="secondary" onclick='openKioskPage(${jsArg(data.active_event.gallery_url)})'>📺 เปิดสไลด์โชว์บนจอใหญ่</button>
      <button class="secondary" onclick='shareGallery(${jsArg(data.active_event.gallery_url)}, ${jsArg(data.active_event.name)})'>Share Gallery</button>
      <button class="secondary" onclick='rebuildPhotos(${jsArg(data.active_event.id)})'>Rebuild Gallery Files</button>
      <button class="warn" onclick='pause(${jsArg(data.active_event.id)})'>${data.active_event.publishing_paused ? "Resume Publishing" : "Pause Publishing"}</button>
      <button class="bad" onclick='endEvent(${jsArg(data.active_event.id)})'>End Event</button>
      <button class="bad" onclick='deleteEvent(${jsArg(data.active_event.id)}, ${jsArg(data.active_event.name)}, true, "dashboard")'>Delete Event</button>
    </div><div id="qrslot"></div>`;
  $("#health").innerHTML = Object.entries(data.health).map(([k,v]) => `<div class="queue-line"><span>${k}</span><b>${v}</b></div>`).join("");
  $("#queues").innerHTML = Object.entries(data.queues).map(([k,v]) => `<div class="queue-line"><span>${k}</span><b>${v}</b></div>`).join("") + `<div id="failedJobs"></div>`;
  $("#thumbs").innerHTML = data.latest_photos.length ? data.latest_photos.map(p => `<div class="thumb">${p.thumb ? `<img src="${p.thumb}" alt="${html(p.filename)}">` : html(p.status)}<span class="thumb-status ${p.published && !p.hidden ? "ok" : p.hidden ? "bad" : ""}">${html(p.hidden ? "HIDDEN" : p.status)}</span></div>`).join("") : `<div class="thumb">No photos yet</div>`;
  loadPreflight(data.active_event.id);
  loadFailedJobs(data.active_event.id);
}

async function openKioskModal(name, qrSrc, eventId) {
  closeKioskModal(false);
  let modal = document.querySelector("#kioskModal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "kioskModal";
    modal.className = "kiosk-modal";
    document.body.appendChild(modal);
  }
  modal.innerHTML = `
    <div class="kiosk-screen" id="kioskScreen">
      <div class="kiosk-stage" id="kioskStage" data-transition="fade" data-motion="kenburns">
        <img class="kiosk-slide active" id="kioskSlideA" alt="ภาพจากงาน">
        <img class="kiosk-slide" id="kioskSlideB" alt="ภาพจากงาน" aria-hidden="true">
        <div class="kiosk-empty" id="kioskEmpty"><span class="kiosk-empty-mark">LIVE GALLERY</span><b>กำลังเตรียมภาพจากงานนี้</b><span>รูปภาพจะแสดงที่นี่โดยอัตโนมัติ</span></div>
      </div>
      <div class="kiosk-heading"><span>CS.BXXM STUDIO</span><b>${html(name || "Photo Booth Live Gallery")}</b></div>
      <aside class="kiosk-floating-qr">
        <div class="kiosk-qr-wrap"><img src="${qrSrc}" alt="QR Code สำหรับเปิดรูปภาพทั้งหมดของงาน"></div>
        <strong>สแกน QR Code เพื่อดาวน์โหลดรูปภาพ</strong>
      </aside>
      <div class="kiosk-controls">
        <button onclick="closeKioskModal()">ปิดจอ</button>
        <button onclick="toggleKioskPlayback()" id="kioskPlayButton">พักภาพ</button>
        <button onclick="stepKiosk(-1)" aria-label="ภาพก่อนหน้า">‹ ก่อนหน้า</button>
        <button onclick="stepKiosk(1)" aria-label="ภาพถัดไป">ถัดไป ›</button>
        <label>เปลี่ยนภาพ
          <select onchange="setKioskTransition(this.value)"><option value="fade">Fade</option><option value="slide">Slide</option><option value="dissolve">Dissolve</option></select>
        </label>
        <label>การเคลื่อนไหว
          <select onchange="setKioskMotion(this.value)"><option value="kenburns" selected>ซูมช้า ๆ</option><option value="still">ภาพนิ่ง</option></select>
        </label>
        <label>ความเร็ว
          <select onchange="setKioskInterval(this.value)"><option value="4000">4 วินาที</option><option value="6000" selected>6 วินาที</option><option value="8000">8 วินาที</option><option value="10000">10 วินาที</option></select>
        </label>
        <label>ขนาด QR
          <select onchange="setKioskQrSize(this.value)"><option value="small">เล็ก</option><option value="medium" selected>ปกติ</option><option value="large">ใหญ่</option></select>
        </label>
        <button onclick="toggleKioskFullscreen()" id="kioskFullscreenButton">เต็มจอ</button>
      </div>
    </div>
  `;
  const state = { eventId, photos: [], index: 0, paused: false, transition: "fade", motion: "kenburns", qrSize: "medium", interval: 6000, refreshTimer: null, slideTimer: null, loading: false, sequence: 0 };
  kioskState = state;
  document.body.style.overflow = "hidden";
  await refreshKioskPhotos();
  if (kioskState === state) {
    state.refreshTimer = setInterval(refreshKioskPhotos, 15000);
    state.slideTimer = setInterval(() => { if (kioskState === state && !state.paused) stepKiosk(1); }, 6000);
  setKioskMotion(state.motion);
  setKioskQrSize(state.qrSize);
  }
}

function openKioskPage(galleryUrl) {
  let url;
  try {
    url = new URL(galleryUrl, location.origin);
    url.searchParams.set("slideshow", "1");
  } catch (error) {
    console.error("Unable to open event slideshow", error);
    showToast("เปิดหน้าแกลเลอรีไม่สำเร็จ ตรวจสอบลิงก์แกลเลอรีของงาน", "error");
    return;
  }

  // Open synchronously from the user's click so popup blockers allow it.
  const slideshowWindow = window.open("about:blank", "_blank", "popup=yes,width=1280,height=800");
  if (!slideshowWindow) {
    showToast("เบราว์เซอร์บล็อกหน้าต่างสไลด์โชว์ อนุญาต Pop-ups สำหรับเว็บนี้แล้วลองอีกครั้ง", "error");
    return;
  }

  try {
    slideshowWindow.document.title = "กำลังเตรียมสไลด์โชว์";
    slideshowWindow.document.body.textContent = "กำลังเตรียมหน้าจอสำหรับสไลด์โชว์…";
  } catch { /* The blank popup may not expose its initial document in some browsers. */ }

  void (async () => {
    let movedToDisplay = false;
    try {
      if (typeof window.getScreenDetails === "function") {
        const displays = await window.getScreenDetails();
        const external = displays.screens.find(display => display !== displays.currentScreen);
        if (external && !slideshowWindow.closed) {
          slideshowWindow.moveTo(external.availLeft, external.availTop);
          slideshowWindow.resizeTo(external.availWidth, external.availHeight);
          movedToDisplay = true;
        }
      }
    } catch (error) {
      // Permission denied or unsupported: continue with a normal slideshow window.
      console.info("Secondary display placement unavailable; using a regular slideshow window", error);
    }
    if (slideshowWindow.closed) return;
    slideshowWindow.opener = null;
    slideshowWindow.location.replace(url.toString());
    slideshowWindow.focus();
    showToast(movedToDisplay
      ? "เปิดสไลด์โชว์บนจอเสริมแล้ว กด “เต็มจอ” ในหน้าสไลด์ได้เลย"
      : "เปิดสไลด์โชว์แล้ว หากใช้จอเสริมให้ลากหน้าต่างไปจอทีวีแล้วกด “เต็มจอ”", "info");
  })();
}

function closeKioskModal(restoreScroll = true) {
  if (kioskState) {
    clearInterval(kioskState.refreshTimer);
    clearInterval(kioskState.slideTimer);
    kioskState = null;
  }
  const modal = document.querySelector("#kioskModal");
  if (modal) modal.remove();
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  if (restoreScroll) document.body.style.overflow = "";
}

async function refreshKioskPhotos() {
  if (!kioskState || kioskState.loading) return;
  kioskState.loading = true;
  const eventId = kioskState.eventId;
  try {
    const photos = [];
    let page = 1;
    let rows = [];
    do {
      rows = await api(`/api/events/${eventId}/gallery-photos?page=${page}&page_size=100`);
      if (!kioskState || kioskState.eventId !== eventId) return;
      photos.push(...rows);
      page += 1;
    } while (rows.length === 100);
    const previousId = kioskState.photos[kioskState.index]?.id;
    kioskState.photos = photos;
    const existing = photos.findIndex(photo => photo.id === previousId);
    kioskState.index = existing >= 0 ? existing : 0;
    const empty = $("#kioskEmpty");
    if (photos.length) {
      if (empty) empty.hidden = true;
      const activePhoto = photos[kioskState.index];
      const activeSlide = document.querySelector(".kiosk-slide.active");
      if (activeSlide?.dataset.photoId !== activePhoto.id) await showKioskPhoto(kioskState.index);
    } else if (empty) {
      empty.hidden = false;
      empty.innerHTML = '<span class="kiosk-empty-mark">LIVE GALLERY</span><b>พร้อมฉายภาพความทรงจำ</b><span>ภาพใหม่จากงานจะแสดงที่นี่โดยอัตโนมัติ</span>';
    }
  } catch (error) {
    console.error("Could not refresh Kiosk slideshow", error);
    const empty = $("#kioskEmpty");
    if (empty && !kioskState?.photos.length) {
      empty.hidden = false;
      empty.innerHTML = '<span class="kiosk-empty-mark">กำลังเชื่อมต่อ</span><b>กำลังโหลดภาพจากงาน</b><span>ระบบจะลองเชื่อมต่อให้อีกครั้งโดยอัตโนมัติ</span>';
    }
  } finally {
    if (kioskState?.eventId === eventId) kioskState.loading = false;
  }
}

async function showKioskPhoto(index) {
  if (!kioskState?.photos.length) return;
  const state = kioskState;
  const sequence = ++state.sequence;
  let photo = null;
  let source = "";
  for (let offset = 0; offset < state.photos.length; offset += 1) {
    const candidate = state.photos[(index + offset + state.photos.length) % state.photos.length];
    const candidateSource = candidate.preview || candidate.finished;
    const preload = new Image();
    preload.src = candidateSource;
    try {
      await preload.decode();
      photo = candidate;
      source = candidateSource;
      break;
    } catch {
      console.warn("Skipping unavailable Kiosk photo", candidate.id);
    }
  }
  if (!photo) {
    const empty = $("#kioskEmpty");
    if (empty) {
      empty.hidden = false;
      empty.innerHTML = '<span class="kiosk-empty-mark">LIVE GALLERY</span><b>กำลังรอภาพที่พร้อมแสดง</b><span>ภาพใหม่จะปรากฏที่นี่โดยอัตโนมัติ</span>';
    }
    return;
  }
  if (!kioskState || kioskState.sequence !== sequence) return;
  const empty = $("#kioskEmpty");
  if (empty) empty.hidden = true;
  const stage = $("#kioskStage");
  const active = stage?.querySelector(".kiosk-slide.active");
  const next = active?.id === "kioskSlideA" ? $("#kioskSlideB") : $("#kioskSlideA");
  if (!next || !active) return;
  next.src = source;
  next.dataset.photoId = photo.id;
  next.alt = photo.filename || "ภาพจากงาน";
  next.classList.add("active");
  active.classList.remove("active");
  stage.dataset.transition = state.transition;
  stage.dataset.motion = state.motion;
  stage.style.setProperty("--kiosk-slide-duration", `${state.interval}ms`);
  const direction = state.sequence % 4;
  next.style.setProperty("--kenburn-x", direction % 2 ? "-1.5%" : "1.5%");
  next.style.setProperty("--kenburn-y", direction > 1 ? "-1.5%" : "1.5%");
  state.index = state.photos.findIndex(item => item.id === photo.id);
  const following = state.photos[(state.index + 1) % state.photos.length];
  if (following) { const image = new Image(); image.src = following.preview || following.finished; }
}

function stepKiosk(direction) {
  if (!kioskState?.photos.length) return;
  showKioskPhoto(kioskState.index + direction);
}

function toggleKioskPlayback() {
  if (!kioskState) return;
  kioskState.paused = !kioskState.paused;
  const button = $("#kioskPlayButton");
  if (button) button.textContent = kioskState.paused ? "เล่นต่อ" : "พักภาพ";
}

function setKioskTransition(value) {
  if (!kioskState || !["fade", "slide", "dissolve"].includes(value)) return;
  kioskState.transition = value;
  const stage = $("#kioskStage");
  if (stage) stage.dataset.transition = value;
}

function setKioskMotion(value) {
  if (!kioskState || !["kenburns", "still"].includes(value)) return;
  kioskState.motion = value;
  const stage = $("#kioskStage");
  if (stage) stage.dataset.motion = value;
}

function setKioskQrSize(value) {
  if (!kioskState || !["small", "medium", "large"].includes(value)) return;
  kioskState.qrSize = value;
  const screen = $("#kioskScreen");
  if (screen) screen.dataset.qrSize = value;
}

function setKioskInterval(value) {
  if (!kioskState) return;
  const milliseconds = Number(value);
  if (![4000, 6000, 8000, 10000].includes(milliseconds)) return;
  kioskState.interval = milliseconds;
  $("#kioskStage")?.style.setProperty("--kiosk-slide-duration", `${milliseconds}ms`);
  clearInterval(kioskState.slideTimer);
  kioskState.slideTimer = setInterval(() => {
    if (kioskState && !kioskState.paused) stepKiosk(1);
  }, milliseconds);
}

async function toggleKioskFullscreen() {
  const screen = $("#kioskScreen");
  try {
    if (!document.fullscreenElement) await screen?.requestFullscreen();
    else await document.exitFullscreen();
  } catch (error) {
    showToast("เบราว์เซอร์ไม่อนุญาตโหมดเต็มจอ กด F11 เพื่อขยายหน้าต่าง", "info");
  }
}

document.addEventListener("keydown", event => {
  if (!kioskState) return;
  if (event.key === "Escape") closeKioskModal();
  else if (event.key === "ArrowRight") stepKiosk(1);
  else if (event.key === "ArrowLeft") stepKiosk(-1);
  else if (event.code === "Space") { event.preventDefault(); toggleKioskPlayback(); }
});

async function showQr(id, url, name = "") {
  $("#qrslot").innerHTML = `<div class="qr-card"><div><p class="kicker">Guest Gallery QR</p><h2>ให้แขกสแกนเพื่อเปิดแกลเลอรี</h2><p class="muted">ลิงก์นี้คือหน้าที่ผู้ใช้ปลายทางเห็นจริง ใช้ทดสอบบนมือถือหรือส่งให้ทีมงานลองดาวน์โหลดรูปได้</p><div class="pathbox">${url}</div><div class="row" style="margin-top:12px"><a class="button" href="${url}" target="_blank">Open Gallery</a><button class="button secondary" onclick='openKioskPage(${jsArg(url)})'>📺 เปิดสไลด์โชว์</button><a class="button secondary" href="/api/events/${id}/qr.png" download>Save QR PNG</a><button class="secondary" onclick="navigator.clipboard.writeText('${url}')">Copy Link</button><button class="secondary" onclick="shareGallery('${url}', '${name || "CS.BXXM Gallery"}')">Copy LINE Text</button><button class="secondary" onclick="window.print()">Print</button></div></div><img class="qr" src="/api/events/${id}/qr.png" alt="Gallery QR"></div>`;
}
async function loadPreflight(id) {
  const data = await api(`/api/events/${id}/preflight`);
  const driveFix = data.failed.some(c => c.key === "google_drive") ? `<div class="row" style="margin-top:12px"><a class="button secondary" href="/settings">Connect Google Drive</a><button class="secondary" onclick='disableDriveRequirement(${jsArg(id)})'>Start without Google Drive</button></div>` : "";
  $("#preflight").innerHTML = `<div class="preflight-grid">${data.checks.map(c => `<div class="preflight-item ${c.ok ? "ok" : "fail"}"><b>${c.ok ? "PASS" : "FIX"}</b><span>${checkLabels[c.key] || c.key.replaceAll("_"," ")}</span><small>${c.message}</small></div>`).join("")}</div>${driveFix}`;
}
async function shareGallery(url, name) {
  const text = `รูปภาพงาน ${name}\nเปิด Gallery และดาวน์โหลดรูปได้ที่:\n${url}`;
  await navigator.clipboard.writeText(text);
  alert("คัดลอกข้อความสำหรับส่งต่อแล้ว");
}
async function rebuildPhotos(id) {
  if (!confirm("สร้างรูป Gallery ใหม่จากไฟล์ต้นฉบับทั้งหมดหรือไม่? รูปที่ประมวลผลแล้วจะถูกจัดคิวใหม่และอาจใช้เวลาสักครู่")) return;
  const result = await api(`/api/events/${id}/photos/reprocess`, { method: "POST" });
  alert(`เข้าคิวสร้างรูปใหม่ ${result.queued} รูปแล้ว`);
  if (location.pathname.includes("gallery")) loadGalleryPreview();
  else loadDashboard();
}
async function pause(id) { await api(`/api/events/${id}/pause-publishing`, { method: "POST" }); loadDashboard(); }
async function openFolder(id) { await api(`/api/events/${id}/open-folder`, { method: "POST" }); }
async function endEvent(id) { if (confirm("End this event and stop watching INCOMING?")) { await api(`/api/events/${id}/end`, { method: "POST" }); loadDashboard(); } }
async function deleteEvent(id, name, allowFiles = true, returnTo = "events") {
  if (!confirm(`ลบอีเวนต์ "${name}" ออกจากฐานข้อมูล?\n\nรูปและโฟลเดอร์งานจะยังอยู่ในเครื่อง ถ้ายังไม่เลือกขั้นถัดไป`)) return;
  const deleteFiles = allowFiles && confirm("ต้องการลบโฟลเดอร์รูปของอีเวนต์นี้ออกจากเครื่องด้วยไหม?\n\nกด Cancel ถ้าต้องการลบเฉพาะข้อมูลในระบบ แต่เก็บไฟล์รูปไว้");
  const result = await api(`/api/events/${id}?delete_files=${deleteFiles ? "true" : "false"}`, { method: "DELETE" });
  const detail = result.warning ? `\n\n${result.warning}` : deleteFiles ? "\n\nลบโฟลเดอร์งานแล้ว" : "\n\nเก็บโฟลเดอร์รูปไว้ในเครื่อง";
  alert(`ลบอีเวนต์แล้ว${detail}`);
  if (returnTo === "dashboard") location.href = "/";
  else if (returnTo === "archive") loadArchive();
  else renderEvents();
}
async function loadFailedJobs(id) {
  const jobs = await api(`/api/events/${id}/failed-jobs`);
  if (!jobs.length) return;
  $("#failedJobs").innerHTML = `<hr><h2>Failed Jobs</h2><button class="secondary" onclick="retryAll('${id}')">Retry All</button>` + jobs.map(j => `<div class="queue-line"><span><b>${j.stage}</b><br><small class="muted">${j.error || "No error"} · attempts ${j.attempts}</small></span><button onclick="retryJob('${id}','${j.id}')">Retry</button></div>`).join("");
}
async function retryJob(eventId, jobId) { await api(`/api/events/${eventId}/failed-jobs/${jobId}/retry`, { method: "POST" }); loadDashboard(); }
async function retryAll(eventId) { await api(`/api/events/${eventId}/failed-jobs/retry-all`, { method: "POST" }); loadDashboard(); }

async function loadEvents() {
  window.activePhotoboothFrames = {};
  window.frameSelectionLoading = false;
  layout("events", `<div class="top hero-panel"><div><p class="kicker">CS.BXXM STUDIO · PHOTO BOOTH</p><h1>สร้างงานถ่ายภาพ</h1><p class="hero-note">ตั้งค่าวันงาน กรอบธีม และแกลเลอรีสำหรับผู้ร่วมงาน</p></div></div>
  <div class="grid"><form id="eventForm" class="panel span-7">
    <label><span>ชื่องาน</span><input name="name" required placeholder="งานเลี้ยงรุ่น 2026"></label>
    <label><span>รายละเอียดเพิ่มเติม</span><textarea name="description"></textarea></label>
    <label><span>วันที่จัดงาน</span><input name="event_date" type="date"></label>
    <div class="empty-state" style="min-height:auto;padding:18px;text-align:left;place-items:start"><b>เก็บไฟล์ต้นฉบับไว้เสมอ</b><br><span>ระบบสร้าง FINISHED/PREVIEW/THUMBNAIL สำหรับแกลเลอรี ส่วนการปรับสีหรือแสงจะไม่ทำอัตโนมัติ</span></div>
    <section class="frame-setup"><p class="kicker">CUSTOM PHOTO FRAME</p><h2>อัปโหลดกรอบของคุณ</h2><p class="muted">เลือกไฟล์แยกตามช่อง ระบบจะบันทึกกรอบแต่ละแนวลงในอีเวนต์นี้โดยตรง และใช้เฉพาะไฟล์ที่อัปโหลดไว้กับงานนี้</p><label class="check"><input type="checkbox" name="photobooth_frame_enabled">ใช้กรอบกับรูปอัตโนมัติ</label><label><span>กรอบแนวตั้ง (PNG โปร่งใส ไม่เกิน 20 MB)</span><input id="photoboothFramePortrait" data-orientation="portrait" type="file" accept="image/png,.png"></label><label><span>กรอบแนวนอน (PNG โปร่งใส ไม่เกิน 20 MB)</span><input id="photoboothFrameLandscape" data-orientation="landscape" type="file" accept="image/png,.png"></label><p id="frameAutoStatus" class="muted frame-auto-status" aria-live="polite">เลือกกรอบแนวตั้งและแนวนอนแยกกัน</p><label><span>เลือกรูปจริงเพื่อทดลองจัดกรอบ (ไม่บังคับ)</span><input id="framePreviewPhoto" type="file" accept="image/*"></label><details class="frame-advanced"><summary>ปรับตำแหน่งเพิ่มเติม</summary><div class="frame-adjustments"><label><span>ขนาดกรอบ <output id="frameScaleValue">100%</output></span><input id="frameScale" name="frameScale" type="range" min="70" max="135" value="100"></label><label><span>เลื่อนแนวนอน <output id="frameXValue">0%</output></span><input id="frameOffsetX" name="frameOffsetX" type="range" min="-15" max="15" value="0"></label><label><span>เลื่อนแนวตั้ง <output id="frameYValue">0%</output></span><input id="frameOffsetY" name="frameOffsetY" type="range" min="-15" max="15" value="0"></label></div></details><div class="frame-simulator"><div class="frame-sample" id="frameSample"><span>PHOTO<br>BOOTH</span><small>ตัวอย่างงาน · 2026</small><img id="framePhotoPreviewImage" alt="ภาพตัวอย่าง" hidden><img id="frameOverlayPreview" alt="ตัวอย่างกรอบบนภาพ" hidden></div><div><b>ทดลองกรอบกับรูปจริง</b><p id="framePreviewMessage" class="muted">อัปโหลดกรอบและเลือกรูปตัวอย่างเพื่อดูผลก่อนเริ่มงาน</p></div></div><div id="frameUploadResult"></div></section>
    <h2>แกลเลอรีสำหรับผู้ร่วมงาน</h2><div class="checks"><label class="check"><input type="checkbox" name="enable_gallery" checked>เปิดแกลเลอรี</label><label class="check"><input type="checkbox" name="allow_download" checked>อนุญาตให้ดาวน์โหลด</label><label class="check"><input type="checkbox" name="instant_publish" checked disabled>แสดงรูปอัตโนมัติ</label></div>
    <label><span>รหัส PIN (ไม่บังคับ)</span><input name="optional_pin"></label>
    <label><span>เครดิตหรือชื่อสตูดิโอ</span><input name="credit_text" value="Photo Booth Experience by CS.BXXM STUDIO"></label>
    <label><span>ช่องทางติดต่อของคุณ</span><input name="report_contact" placeholder="Instagram, LINE, อีเมล หรือเว็บไซต์"></label>
    <h2>สำรองรูปด้วย Google Drive</h2><div class="checks"><label class="check"><input type="checkbox" name="upload_finished_photos" checked>อัปโหลดรูปพร้อมดาวน์โหลดก่อนเผยแพร่</label><label class="check"><input type="checkbox" name="upload_originals">สำรองไฟล์ต้นฉบับ</label></div>
    <button>สร้างงานถ่ายภาพ</button>
  </form><section class="panel span-5"><div class="preview-head"><div><h2>งานในระบบ</h2><p class="muted">ข้อมูลจากฐานข้อมูลและโฟลเดอร์งานจริงในเครื่อง</p></div><button type="button" class="secondary" onclick="loadImportableEvents()">ค้นหางานจากโฟลเดอร์</button></div><div id="eventsList"></div><div id="importableList"></div><div id="created"></div></section></div>`);
  $("#eventForm").addEventListener("submit", createEvent);
  $("#photoboothFramePortrait").addEventListener("change", previewPhotoboothFrame);
  $("#photoboothFrameLandscape").addEventListener("change", previewPhotoboothFrame);
  $("#framePreviewPhoto").addEventListener("change", previewFramePhoto);
  ["frameScale", "frameOffsetX", "frameOffsetY"].forEach(id => $("#" + id).addEventListener("input", updateFramePreviewTransform));
  renderEvents();
}

function setFrameAutoStatus(message, isError = false) {
  const status = $("#frameAutoStatus");
  if (!status) return;
  status.textContent = message;
  status.classList.toggle("frame-auto-error", isError);
  status.classList.toggle("frame-auto-ready", !isError);
}

async function inspectPhotoboothFrame(file) {
  if (file.size > 20 * 1024 * 1024) throw new Error(`${file.name}: ไฟล์ใหญ่เกิน 20 MB`);
  if (!file.name.toLowerCase().endsWith(".png")) throw new Error(`${file.name}: ชื่อไฟล์ต้องลงท้ายด้วย .png`);
  const signature = new Uint8Array(await file.slice(0, 8).arrayBuffer());
  if (signature.length !== 8 || signature.some((byte, index) => byte !== [137, 80, 78, 71, 13, 10, 26, 10][index])) {
    throw new Error(`${file.name}: ไฟล์นี้ไม่ใช่ PNG ที่ถูกต้อง`);
  }
  const bitmap = await createImageBitmap(file);
  try {
    if (Math.min(bitmap.width, bitmap.height) < 300 || Math.max(bitmap.width, bitmap.height) > 8000) {
      throw new Error(`${file.name}: ขนาดภาพต้องอยู่ระหว่าง 300 ถึง 8,000 พิกเซลต่อด้าน`);
    }
    const canvas = document.createElement("canvas");
    canvas.width = 96;
    canvas.height = 96;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    context.clearRect(0, 0, 96, 96);
    context.drawImage(bitmap, 0, 0, 96, 96);
    const pixels = context.getImageData(0, 0, 96, 96).data;
    let transparentSamples = 0;
    for (let index = 3; index < pixels.length; index += 4) if (pixels[index] < 250) transparentSamples += 1;
    if (!transparentSamples) throw new Error(`${file.name}: ไม่พบช่องโปร่งใส กรุณาใช้ PNG ที่เจาะช่องกลางไว้`);
    return { file, width: bitmap.width, height: bitmap.height, orientation: bitmap.width >= bitmap.height ? "landscape" : "portrait" };
  } finally {
    bitmap.close();
  }
}

async function inspectCardTemplate(file) {
  if (file.size > 8 * 1024 * 1024) throw new Error("เทมเพลตต้องมีขนาดไม่เกิน 8 MB");
  if (file.size < 24) throw new Error("ไฟล์เทมเพลต PNG ไม่สมบูรณ์");
  if (!file.name.toLowerCase().endsWith(".png")) throw new Error("เทมเพลตต้องเป็นไฟล์ PNG");
  const signature = new Uint8Array(await file.slice(0, 8).arrayBuffer());
  if (signature.length !== 8 || signature.some((byte, index) => byte !== [137,80,78,71,13,10,26,10][index])) throw new Error("ไฟล์นี้ไม่ใช่ PNG ที่ถูกต้อง");
  const header = new DataView(await file.slice(16, 24).arrayBuffer());
  const declaredWidth = header.getUint32(0);
  const declaredHeight = header.getUint32(4);
  if (declaredWidth < 300 || declaredHeight < 300 || declaredWidth > 5000 || declaredHeight > 5000 || declaredWidth >= declaredHeight) {
    throw new Error("เทมเพลตต้องเป็นแนวตั้ง ขนาด 300–5,000 พิกเซล และสูงกว่ากว้าง");
  }
  const bitmap = await createImageBitmap(file);
  try {
    if (Math.min(bitmap.width, bitmap.height) < 300 || Math.max(bitmap.width, bitmap.height) > 5000 || bitmap.width >= bitmap.height) {
      throw new Error("เทมเพลตต้องเป็นแนวตั้ง ขนาด 300–5,000 พิกเซล และสูงกว่ากว้าง");
    }
    const canvas = document.createElement("canvas");
    canvas.width = 100; canvas.height = 100;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    ctx.clearRect(0, 0, 100, 100); ctx.drawImage(bitmap, 0, 0, 100, 100);
    const data = ctx.getImageData(0, 0, 100, 100).data;
    let visible = 0; let designPixels = 0;
    for (let i = 0; i < data.length; i += 4) {
      if (data[i + 3] > 10) visible++;
      if (data[i + 3] > 10 && Math.min(data[i], data[i + 1], data[i + 2]) < 248) designPixels++;
    }
    if (!visible || designPixels < 30) throw new Error("เทมเพลตต้องมีลายตกแต่งและช่องว่างสำหรับภาพ");
    const transparentSlots = []; const whiteSlots = [];
    for (const cy of [.2425,.4325,.6225,.8125]) {
      const x0 = 35, x1 = 65;
      const y0 = Math.round((cy-.05)*100), y1 = Math.round((cy+.05)*100);
      let clear = 0;
      let white = 0;
      for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) {
        const i = (y*100+x)*4;
        if (data[i+3] < 40) clear++;
        if (data[i+3] >= 240 && Math.min(data[i],data[i+1],data[i+2]) >= 248) white++;
      }
      const area = (x1-x0)*(y1-y0);
      transparentSlots.push(clear >= area*.6);
      whiteSlots.push(white >= area*.6);
    }
    if (!transparentSlots.every(Boolean) && !whiteSlots.every(Boolean)) throw new Error("เทมเพลตต้องมีช่องภาพ 4 ช่องเรียงลงมาตรงกลาง หรือช่องสีขาวที่ระบบจะตัดให้");
    return { width: bitmap.width, height: bitmap.height };
  } finally { bitmap.close(); }
}

function releaseFramePreviewUrls() {
  (window.__framePreviewUrls || []).forEach(url => URL.revokeObjectURL(url));
  window.__framePreviewUrls = [];
  if (window.__frameOverlayPreviewUrl) URL.revokeObjectURL(window.__frameOverlayPreviewUrl);
  window.__frameOverlayPreviewFile = null;
  window.__frameOverlayPreviewUrl = null;
}

async function previewPhotoboothFrame(ev) {
  const input = ev.currentTarget;
  const token = (window.__frameSelectionToken || 0) + 1;
  window.__frameSelectionToken = token;
  window.frameSelectionLoading = true;
  const orientation = input.dataset.orientation;
  const file = input.files?.[0];
  const frames = window.activePhotoboothFrames || {};
  delete frames[orientation];
  window.activePhotoboothFrames = frames;
  try {
    if (file) {
      const metadata = await inspectPhotoboothFrame(file);
      if (window.__frameSelectionToken !== token) return;
      if (metadata.orientation !== orientation) {
        input.value = "";
        throw new Error(`ไฟล์ ${file.name} เป็นกรอบ${metadata.orientation === "landscape" ? "แนวนอน" : "แนวตั้ง"} กรุณาเลือกไฟล์ให้ตรงกับช่อง${orientation === "landscape" ? "แนวนอน" : "แนวตั้ง"}`);
      }
      frames[orientation] = metadata;
    }
    window.activePhotoboothFrames = frames;
    window.frameSelectionLoading = false;
    $("[name=photobooth_frame_enabled]").checked = Object.keys(frames).length > 0;
    const labels = ["portrait", "landscape"].map(key => {
      const item = frames[key];
      return `${key === "portrait" ? "แนวตั้ง" : "แนวนอน"}: ${item ? `${item.file.name} (${item.width} × ${item.height})` : "ยังไม่ได้เลือก"}`;
    });
    setFrameAutoStatus(labels.join(" · "), !frames.portrait || !frames.landscape);
    refreshPhotoboothFramePreview();
  } catch (error) {
    if (window.__frameSelectionToken !== token) return;
    window.frameSelectionLoading = false;
    window.activePhotoboothFrames = frames;
    setFrameAutoStatus(error.message || "ตรวจสอบกรอบไม่สำเร็จ", true);
    refreshPhotoboothFramePreview();
  }
}

function previewFramePhoto(ev) {
  const file = ev.currentTarget.files?.[0];
  const preview = $("#framePhotoPreviewImage");
  if (window.__framePhotoPreviewUrl) URL.revokeObjectURL(window.__framePhotoPreviewUrl);
  window.__framePhotoPreviewUrl = null;
  if (!file) {
    preview.hidden = true;
    preview.removeAttribute("src");
    preview.style.cssText = "";
    refreshPhotoboothFramePreview();
    return;
  }
  window.__framePhotoPreviewUrl = URL.createObjectURL(file);
  preview.onload = () => {
    const frames = window.activePhotoboothFrames || {};
    const orientation = preview.naturalWidth >= preview.naturalHeight ? "landscape" : "portrait";
    if (!frames[orientation]) $("#frameSample").style.aspectRatio = `${preview.naturalWidth} / ${preview.naturalHeight}`;
    refreshPhotoboothFramePreview();
  };
  preview.onerror = () => setFrameAutoStatus("เปิดภาพตัวอย่างไม่ได้ กรุณาเลือกไฟล์รูปอื่น", true);
  preview.src = window.__framePhotoPreviewUrl;
  preview.hidden = false;
}

function refreshPhotoboothFramePreview() {
  const sample = $("#frameSample");
  const photo = $("#framePhotoPreviewImage");
  const overlay = $("#frameOverlayPreview");
  const frames = window.activePhotoboothFrames || {};
  let orientation;
  if (photo?.naturalWidth && !photo.hidden) {
    orientation = photo.naturalWidth >= photo.naturalHeight ? "landscape" : "portrait";
  } else {
    orientation = frames.landscape ? "landscape" : frames.portrait ? "portrait" : "landscape";
    if (frames[orientation]) sample.style.aspectRatio = `${frames[orientation].width} / ${frames[orientation].height}`;
    else sample.style.aspectRatio = "4 / 3";
  }
  const frame = frames[orientation];
  if (!frame) {
    overlay.hidden = true;
    overlay.removeAttribute("src");
    if (photo) {
      photo.style.cssText = "";
      if (photo.naturalWidth && !photo.hidden) sample.style.aspectRatio = `${photo.naturalWidth} / ${photo.naturalHeight}`;
    }
    const label = orientation === "landscape" ? "แนวนอน" : "แนวตั้ง";
    const other = orientation === "landscape" ? "แนวตั้ง" : "แนวนอน";
    const status = frames[orientation === "landscape" ? "portrait" : "landscape"]
      ? `ภาพตัวอย่างเป็น${label} แต่ยังไม่มีกรอบ${label} · เพิ่มกรอบ${label}เพื่อให้พอดีกับภาพ`
      : `ภาพตัวอย่างเป็น${label} · กรอบ${other}จะไม่ถูกยืดหรือครอปมาใช้ผิดแนว`;
    const message = $("#framePreviewMessage");
    if (message) message.textContent = status;
    return;
  }
  sample.style.aspectRatio = photo?.naturalWidth && !photo.hidden
    ? `${photo.naturalWidth} / ${photo.naturalHeight}`
    : `${frame.width} / ${frame.height}`;
  if (window.__frameOverlayPreviewFile !== frame.file) {
    if (window.__frameOverlayPreviewUrl) URL.revokeObjectURL(window.__frameOverlayPreviewUrl);
    window.__frameOverlayPreviewFile = frame.file;
    window.__frameOverlayPreviewUrl = URL.createObjectURL(frame.file);
  }
  overlay.src = window.__frameOverlayPreviewUrl;
  overlay.hidden = false;
  const message = $("#framePreviewMessage");
  if (message) message.textContent = photo?.naturalWidth && !photo.hidden
    ? `ตัวอย่างภาพ${orientation === "landscape" ? "แนวนอน" : "แนวตั้ง"} · ระบบเลือกกรอบที่ตรงแนวให้อัตโนมัติ`
    : `ตัวอย่างกรอบ${orientation === "landscape" ? "แนวนอน" : "แนวตั้ง"} · เลือกรูปจริงเพื่อดูการจัดวางกับภาพของคุณ`;
  updateFramePreviewTransform();
}

function updateFramePreviewTransform() {
  const scale = Number($("#frameScale").value) / 100;
  const x = Number($("#frameOffsetX").value);
  const y = Number($("#frameOffsetY").value);
  $("#frameScaleValue").value = `${Math.round(scale * 100)}%`;
  $("#frameXValue").value = `${x}%`;
  $("#frameYValue").value = `${y}%`;
  $("#frameOverlayPreview").style.transform = `translate(${x}%, ${y}%) scale(${scale})`;
}

async function uploadPhotoboothFrame(eventId, file, orientation) {
  const data = new FormData();
  data.append("frame", file, file.name);
  return api(`/api/events/${eventId}/photobooth-frame?orientation=${orientation}`, { method: "POST", body: data, headers: {} });
}

async function uploadSelectedPhotoboothFrames(eventId, frameFiles) {
  const selected = new Set(frameFiles.map(([orientation]) => orientation));
  if (!selected.has("portrait") || !selected.has("landscape")) {
    throw new Error("ต้องเลือกกรอบแนวตั้งและแนวนอนแยกกันให้ครบก่อนอัปโหลด");
  }
  const results = [];
  for (const [orientation, file] of frameFiles) {
    const result = await uploadPhotoboothFrame(eventId, file, orientation);
    if (!result.ok || result.orientation !== orientation || !result.filename) {
      throw new Error(`เซิร์ฟเวอร์ยืนยันการบันทึกกรอบ${orientation === "portrait" ? "แนวตั้ง" : "แนวนอน"}ไม่ได้`);
    }
    results.push(result);
  }
  const preflight = await api(`/api/events/${eventId}/preflight`);
  const frameChecks = preflight.checks.filter(check => check.key.startsWith("photobooth_frame_"));
  const failed = frameChecks.filter(check => !check.ok);
  if (frameChecks.length !== 2 || failed.length) {
    throw new Error(failed.map(check => check.message).join(" · ") || "ยืนยันไฟล์กรอบที่อัปโหลดไม่ครบ");
  }
  return results;
}

async function retryPhotoboothFrame(eventId) {
  const files = Object.entries(window.activePhotoboothFrames || {}).map(([orientation, meta]) => [orientation, meta.file]);
  if (!files.length) return alert("เลือกกรอบ PNG ก่อนลองอีกครั้ง");
  const status = $("#frameUploadResult");
  status.textContent = "กำลังอัปโหลดกรอบ...";
  try {
    const results = await uploadSelectedPhotoboothFrames(eventId, files);
    const reprocessed = await api(`/api/events/${eventId}/photos/reprocess`, { method: "POST" });
    const orientationNote = results.length === 1 ? " · รูปอีกแนวจะแสดงโดยไม่ใส่กรอบเพื่อรักษาสัดส่วน" : "";
    status.innerHTML = `<div class="frame-upload-success">อัปโหลดกรอบ${results.map(item => `${item.orientation} ${item.width} × ${item.height} px`).join(" และ ")} สำเร็จ · ส่งรูปเก่า ${reprocessed.queued} รูปกลับไปประมวลผลแล้ว${orientationNote}</div>`;
  } catch (err) {
    status.innerHTML = `<div class="frame-upload-error">อัปโหลดไม่สำเร็จ: ${html(err.message)} <button type="button" class="secondary" onclick='retryPhotoboothFrame(${jsArg(eventId)})'>ลองอีกครั้ง</button></div>`;
  }
}

async function renderEvents() {
  const events = await api("/api/events");
  $("#eventsList").innerHTML = events.map(e => `<div class="queue-line"><span>${html(e.name)}<br><small class="muted">${html(e.status)}</small></span><span class="row"><button class="secondary" onclick='uploadFrameToExistingEvent(${jsArg(e.id)})'>อัปโหลดกรอบ</button><button class="secondary" onclick='checkPreflightFromList(${jsArg(e.id)})'>Check</button><button onclick='startEvent(${jsArg(e.id)})'>เริ่มงาน</button><button class="bad" onclick='deleteEvent(${jsArg(e.id)}, ${jsArg(e.name)}, true, "events")'>Delete</button></span></div>`).join("") || `<div class="empty-state"><b>ยังไม่มีอีเวนต์ในฐานข้อมูล</b><br><span>กด Import Local Events เพื่อดึงงานจากโฟลเดอร์ในเครื่องกลับเข้าระบบ</span></div>`;
}

async function loadImportableEvents() {
  const data = await api("/api/events/importable");
  const rows = data.events.filter(e => !e.exists);
  $("#importableList").innerHTML = `<hr><h2>Import From Local Folders</h2><p class="muted">Root: ${data.root_path}</p>` + (rows.map(e => `<div class="queue-line"><span><b>${e.name}</b><br><small class="muted">${e.finished_photos} finished photo(s) · ${e.path}</small></span><button type="button" onclick='importLocalEvent(${jsArg(e.path)})'>Import</button></div>`).join("") || `<p class="muted">ไม่มีงานใหม่ให้ import จากโฟลเดอร์นี้</p>`);
}

async function importLocalEvent(eventFolder, returnTo = "events") {
  const result = await api("/api/events/import-local", { method: "POST", body: JSON.stringify({ event_folder: eventFolder }) });
  const total = result.imported.length;
  const photos = result.imported.reduce((sum, item) => sum + (item.photos || 0), 0);
  alert(`นำเข้างานจากเครื่องแล้ว ${total} งาน / ${photos} รูป`);
  if (returnTo === "archive") loadArchive();
  else {
    await renderEvents();
    await loadImportableEvents();
  }
}

async function checkPreflightFromList(id) {
  const data = await api(`/api/events/${id}/preflight`);
  alert(data.ok ? "ตรวจครบแล้ว พร้อมเริ่มงาน" : `ยังไม่พร้อม:\n\n${data.failed.map(x => `- ${checkLabels[x.key] || x.key}: ${x.message}`).join("\n")}`);
}

async function uploadFrameToExistingEvent(eventId) {
  const picker = document.createElement("input");
  picker.type = "file";
  picker.accept = "image/png,.png";
  picker.onchange = async () => {
    const file = picker.files?.[0];
    if (!file) return;
    try {
      const frame = await inspectPhotoboothFrame(file);
      const result = await uploadPhotoboothFrame(eventId, file, frame.orientation);
      if (!result.ok || result.orientation !== frame.orientation) throw new Error("เซิร์ฟเวอร์ยืนยันการบันทึกกรอบไม่ได้");
      const preflight = await api(`/api/events/${eventId}/preflight`);
      const frameChecks = preflight.checks.filter(check => check.key.startsWith("photobooth_frame_"));
      const failed = frameChecks.filter(check => !check.ok);
      const reprocessed = failed.length === 0
        ? await api(`/api/events/${eventId}/photos/reprocess`, { method: "POST" })
        : null;
      await renderEvents();
      const savedOrientation = frame.orientation === "portrait" ? "แนวตั้ง" : "แนวนอน";
      alert(`อัปโหลดกรอบ${savedOrientation} "${file.name}" เข้าอีเวนต์นี้แล้ว${failed.length ? `\n\nยังต้องอัปโหลดเพิ่ม:\n${failed.map(check => `- ${check.message}`).join("\n")}` : `\n\nกรอบครบทั้งสองแนวแล้ว ส่งรูปเดิม ${reprocessed.queued} รูปไปประมวลผลใหม่`}`);
    } catch (error) {
      alert(`อัปโหลดกรอบไม่สำเร็จ\n\n${error.message || error}`);
    }
  };
  picker.click();
}

async function createEvent(ev) {
  ev.preventDefault();
  if (window.frameSelectionLoading) {
    showToast("รอให้ระบบตรวจสอบกรอบเสร็จก่อน แล้วค่อยสร้างงาน", "info");
    return;
  }
  const f = new FormData(ev.target);
  const checked = (k) => f.get(k) === "on";
  let frameFiles = Object.entries(window.activePhotoboothFrames || {}).map(([orientation, meta]) => [orientation, meta.file]);
  const selectedFrameOrientations = new Set(frameFiles.map(([orientation]) => orientation));
  const frameEnabled = checked("photobooth_frame_enabled");
  if (frameEnabled && (!selectedFrameOrientations.has("portrait") || !selectedFrameOrientations.has("landscape"))) {
    setFrameAutoStatus("ต้องเลือกกรอบ PNG ให้ครบทั้งแนวตั้งและแนวนอนก่อนสร้างงาน", true);
    alert("กรุณาเลือกกรอบ PNG ให้ครบ 2 แนว: แนวตั้ง 1 ไฟล์และแนวนอน 1 ไฟล์");
    return;
  }
  try {
    for (const [orientation, file] of frameFiles) {
      const inspected = await inspectPhotoboothFrame(file);
      if (inspected.orientation !== orientation) throw new Error(`${file.name}: ทิศทางกรอบเปลี่ยน กรุณาเลือกไฟล์อีกครั้ง`);
    }
  } catch (error) {
    setFrameAutoStatus(error.message || "ตรวจสอบกรอบไม่สำเร็จ", true);
    showToast(error.message || "ตรวจสอบกรอบไม่สำเร็จ", "error");
    return;
  }
  const payload = {
    name: f.get("name"), description: f.get("description"), event_date: f.get("event_date"),
    gallery: Object.assign(Object.fromEntries(["enable_gallery","allow_download"].map(k => [k, checked(k)])), { find_my_photos: false, instant_publish: true, review_before_publish: false, optional_pin: f.get("optional_pin") || "", credit_text: f.get("credit_text") || "Photo Booth Experience by CS.BXXM STUDIO", report_contact: f.get("report_contact") || "", photobooth_frame_scale: Number(f.get("frameScale") || 100) / 100, photobooth_frame_x: Number(f.get("frameOffsetX") || 0) / 100, photobooth_frame_y: Number(f.get("frameOffsetY") || 0) / 100 }),
    drive: { upload_finished_photos: checked("upload_finished_photos"), upload_originals: checked("upload_originals") }
  };
  const event = await api("/api/events", { method: "POST", body: JSON.stringify(payload) });
  let frameStatus = "";
  if (frameEnabled) {
    try {
      const results = await uploadSelectedPhotoboothFrames(event.id, frameFiles);
      const reprocessed = await api(`/api/events/${event.id}/photos/reprocess`, { method: "POST" });
      frameStatus = `<div class="frame-upload-success">อัปโหลดกรอบครบสองแนว (${results.map(item => `${item.orientation} ${item.width} × ${item.height} px`).join(" และ ")}) สำเร็จ · ส่งรูปเดิม ${reprocessed.queued} รูปไปใส่กรอบแล้ว</div>`;
    } catch (err) {
      frameStatus = `<div id="frameUploadResult" class="frame-upload-error">สร้างงานแล้ว แต่บันทึกกรอบไม่สำเร็จ: ${html(err.message)} <button type="button" class="secondary" onclick='retryPhotoboothFrame(${jsArg(event.id)})'>ลองอัปโหลดอีกครั้ง</button></div>`;
    }
  }
  $("#created").innerHTML = `${frameStatus}<hr><h2>INCOMING Folder</h2><div class="pathbox">${html(event.incoming_path)}</div><div class="row" style="margin-top:14px"><button onclick='navigator.clipboard.writeText(${jsArg(event.incoming_path)})'>Copy Path</button><button onclick='startEvent(${jsArg(event.id)})'>Start Event</button></div>`;
  renderEvents();
}
async function startEvent(id) {
  try {
    await api(`/api/events/${id}/start`, { method: "POST" });
    location.href = "/";
  } catch (err) {
    alert(formatStartError(err.message));
  }
}

function formatStartError(message) {
  try {
    const parsed = JSON.parse(message);
    const detail = parsed.detail || parsed;
    const checks = detail.checks || [];
    const failed = checks.filter(c => c.required && !c.ok);
    if (failed.length) {
      return "Start Event ไม่สำเร็จ\n\nต้องแก้รายการนี้ก่อน:\n" + failed.map(c => `- ${checkLabels[c.key] || c.key}: ${c.message}`).join("\n") + "\n\nถ้ายังไม่ต้องการใช้ Google Drive ให้กด Start without Google Drive ในกล่อง Preflight";
    }
    if (detail.message) return `Start Event ไม่สำเร็จ\n\n${detail.message}`;
  } catch (_) {}
  return `Start Event ไม่สำเร็จ\n\n${message}`;
}

async function disableDriveRequirement(id) {
  if (!confirm("เริ่มงานโดยไม่บังคับอัปโหลด Google Drive ก่อนโชว์ใน Gallery?\n\nรูปจะยังถูกเก็บในเครื่องและแสดงผ่านเซิร์ฟเวอร์ local ได้ แต่ Google Drive download จะยังไม่ใช้งานจนกว่าจะเชื่อมต่อภายหลัง")) return;
  await api(`/api/events/${id}/drive-requirement`, { method: "POST", body: JSON.stringify({ upload_finished_photos: false }) });
  await loadPreflight(id);
  await startEvent(id);
}

async function loadSettings() {
  const settings = await api("/api/settings");
  const google = await api("/api/google/status");
  const rootOptions = await api("/api/settings/event-root-options");
  const publicUrl = settings.public_gallery_base_url || "";
  const urlMode = publicUrl.includes("127.0.0.1") || publicUrl.includes("localhost")
    ? "Local only"
    : publicUrl.startsWith("http://192.168.") || publicUrl.startsWith("http://10.") || publicUrl.startsWith("http://172.")
      ? "LAN"
      : "Public";
  layout("settings", `<div class="top hero-panel"><div><p class="kicker">System Configuration</p><h1>Settings</h1><p class="hero-note">ตั้งค่าก่อนเริ่มงานจริง: โฟลเดอร์เก็บรูป, QR/แกลเลอรี่, Google Drive และกำลังประมวลผล</p></div><div class="row hero-actions-admin"><a class="button secondary" href="/setup">Ready Check</a><button class="secondary" onclick="loadSettings()">Refresh</button></div></div>
  <form id="settingsForm" class="settings-page">
    <section class="settings-summary span-12">
      <div class="summary-tile"><span>Event Root</span><b>${html(settings.event_root || "ยังไม่ได้ตั้งค่า")}</b><small>ที่เก็บงานใหม่ในเครื่อง</small></div>
      <div class="summary-tile"><span>Gallery URL</span><b>${urlMode}</b><small>${html(publicUrl || "ยังไม่ได้ตั้งค่า")}</small></div>
      <div class="summary-tile"><span>Google Drive</span><b>${google.connected ? "Connected" : google.configured ? "Ready" : "Missing"}</b><small>${google.connected ? "พร้อมอัปโหลดไฟล์ดาวน์โหลด" : "เชื่อมต่อเพื่อให้ผู้ใช้โหลดรูปได้จริง"}</small></div>
      <div class="summary-tile"><span>Export</span><b>Q${settings.jpeg_quality || 90}</b><small>${settings.worker_count || 2} worker(s)</small></div>
    </section>

    <section class="panel settings-card span-7">
      <div class="settings-card-head"><div><p class="kicker">Storage</p><h2>โฟลเดอร์เก็บงาน</h2><p class="muted">อีเวนต์ใหม่จะสร้าง INCOMING, ORIGINAL, PREVIEWS, THUMBNAILS และ FINISHED ใต้โฟลเดอร์นี้</p></div><button type="button" class="secondary" onclick="chooseEventRoot()">Browse</button></div>
      <label><span>Event Root</span><input id="eventRootInput" name="event_root" value="${html(settings.event_root || "")}"></label>
      <div class="row"><button type="button" onclick="verifyEventRoot()">Verify & Save Folder</button><button type="button" class="secondary" onclick="loadLocalFolders('')">Browse in Page</button></div>
      <p id="eventRootStatus" class="settings-hint">เลือกโฟลเดอร์ที่มีสิทธิ์เขียน แล้วกด Verify & Save Folder</p>
      <div class="folder-options">${rootOptions.options.map(o => `<button type="button" class="${o.recommended ? "" : "secondary"} ${o.writable ? "" : "disabled"}" ${o.writable ? `onclick='setEventRootOption(${jsArg(o.path)})'` : "disabled"}><span>${html(o.label)}</span><small>${html(o.path)}${o.writable ? "" : " · ใช้ไม่ได้: ไม่มีสิทธิ์สร้าง/เขียน"}</small></button>`).join("")}</div>
      <div class="local-browser"><div class="preview-head"><div><h2>Local Folder Browser</h2><p class="muted">เลือก drive หรือโฟลเดอร์จากเครื่องนี้จริง</p></div><button type="button" class="secondary" onclick="loadLocalFolders('')">Drives</button></div><div id="localFolderBrowser"></div></div>
    </section>

    <section class="panel settings-card span-5">
      <div class="settings-card-head"><div><p class="kicker">Guest Access</p><h2>ลิงก์แกลเลอรี่ / QR</h2><p class="muted">QR ทุกงานจะใช้ค่า Base URL นี้ ถ้าดีพรอยให้ใส่โดเมนจริง</p></div><span class="status pill">${urlMode}</span></div>
      <label><span>Public Gallery Base URL</span><input name="public_gallery_base_url" value="${html(publicUrl)}" placeholder="https://photo.school.ac.th/"></label>
      <div class="pathbox">ตัวอย่างลิงก์งาน: ${html(publicGalleryExample(publicUrl))}</div>
      <p class="settings-hint">ทดสอบใน Wi-Fi ใช้ LAN IP ได้ แต่ใช้งานผ่านอินเทอร์เน็ตต้องเป็นโดเมนที่เปิดจากมือถือภายนอกได้</p>
    </section>

    <section class="panel settings-card span-5">
      <div class="settings-card-head"><div><p class="kicker">Downloads</p><h2>สำรองรูปด้วย Google Drive</h2><p class="muted">ใช้เก็บไฟล์ finished สำหรับให้ผู้ใช้ดาวน์โหลดจริง</p></div><span class="status pill">${google.connected ? "CONNECTED" : "NOT CONNECTED"}</span></div>
      <label><span>Drive Root Folder</span><input name="drive_root" value="${html(google.root_folder || "CS.BXXM Events")}"></label>
      <div class="settings-list">
        <div><span>OAuth Config</span><b>${google.configured ? "READY" : "MISSING"}</b></div>
        <div><span>Ready Uploads</span><b>${google.ready_to_upload}</b></div>
        <div><span>Uploaded</span><b>${google.uploaded}</b></div>
      </div>
      <p class="muted">Redirect URI: ${html(google.redirect_uri || "not set")}</p>
      ${google.needs_reconnect ? `<p class="settings-hint badtext">สิทธิ์ Google Drive หมดอายุหรือยังไม่ได้เชื่อมต่อ กรุณากด Connect แล้วกด Retry Uploads เพื่อส่งรูปที่ค้าง</p>` : ""}
      <div class="row"><a class="button" href="/api/google/connect">Connect</a><button type="button" class="secondary" onclick="retryGoogleUploads()">Retry Uploads</button><button type="button" class="bad" onclick="disconnectGoogle()">Disconnect</button></div>
      ${google.configured ? "" : `<p class="settings-hint badtext">ใส่ GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET และ GOOGLE_REDIRECT_URI ใน .env แล้ว restart CS.BXXM Studio ก่อนเชื่อมต่อ</p>`}
    </section>

    <section class="panel settings-card span-7">
      <div class="settings-card-head"><div><p class="kicker">Performance</p><h2>Export & Worker</h2><p class="muted">ระบบไม่แต่งรูปอัตโนมัติ ส่วนนี้ควบคุมคุณภาพ JPEG และจำนวนงานที่ทำพร้อมกัน</p></div></div>
      <div class="settings-fields">
        <label><span>JPEG Quality</span><input name="jpeg_quality" type="number" min="70" max="98" value="${settings.jpeg_quality || 90}"></label>
        <label><span>Worker Count</span><input name="worker_count" type="number" min="1" max="6" value="${settings.worker_count || 2}"></label>
      </div>
      <label><span>Cloud API URL</span><input name="cloud_api_url" value="${html(settings.cloud_api_url || "")}" placeholder="เว้นว่างได้ถ้ายังไม่ใช้ cloud worker"></label>
      <p class="settings-hint">แนะนำเริ่มที่ JPEG 90 และ 2 workers ถ้าเครื่องเริ่มหน่วงค่อยลด worker ลง</p>
    </section>

    <section class="panel settings-save span-12">
      <div><h2>บันทึกการตั้งค่า</h2><p class="muted">บันทึกค่าทั้งหมดในหน้านี้ อีเวนต์ใหม่จะใช้ค่าล่าสุดทันที</p></div>
      <button>Save All Settings</button>
    </section>
  </form>`);
  $("#settingsForm").addEventListener("submit", async e => {
    e.preventDefault();
    await api("/api/settings", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(e.target))) });
    $("#eventRootStatus").textContent = `บันทึกแล้ว อีเวนต์ใหม่จะถูกสร้างใน: ${$("#eventRootInput").value}`;
    alert("Saved");
  });
  loadLocalFolders(settings.event_root || "");
}

async function loadSetup() {
  layout("setup", `<div class="top hero-panel"><div><p class="kicker">Pre-Event Setup</p><h1>Ready Check</h1><p class="hero-note">เช็กสิ่งที่ต้องพร้อมก่อนเริ่มงาน: โฟลเดอร์จริง, Public Gallery URL/QR, Google Drive, database และ INCOMING ล่าสุด</p></div><button class="secondary" onclick="loadSetup()">Refresh</button></div>
  <div class="grid">
    <section class="panel span-8"><div class="preview-head"><div><h2>Readiness</h2><p class="muted">แก้จากรายการที่ขึ้น FIX ก่อนเริ่มงานจริง</p></div><div id="setupStatus" class="status pill">Loading</div></div><div id="setupSteps"></div></section>
    <section class="panel span-4"><h2>Quick Actions</h2><div class="setup-actions"><a class="button" href="/settings">Settings</a><a class="button secondary" href="/events">Events</a><a class="button secondary" href="/diagnostics">System Check</a><button class="secondary" onclick="copyGalleryBaseUrl()">Copy Gallery Base URL</button></div><div id="setupSummary" style="margin-top:14px"></div></section>
  </div>`);
  const data = await api("/api/diagnostics/readiness");
  $("#setupStatus").textContent = data.ok ? "READY" : "NEEDS FIX";
  $("#setupSteps").innerHTML = data.steps.map(step => `<div class="queue-line"><span><b>${step.label}</b><br><small class="muted">${step.message}</small></span><span class="row"><b class="${step.ok ? "" : "badtext"}">${step.ok ? "PASS" : "FIX"}</b><a class="button secondary" href="${step.fix_url}">Open</a></span></div>`).join("");
  $("#setupSummary").innerHTML = `<div class="pathbox">LAN IP: ${data.lan_ip || "not detected"}<br>Public Gallery Base: ${data.public_gallery_base_url}<br>Event Root: ${data.event_root}</div>${data.active_event ? `<p class="muted">Latest: ${data.active_event.event_name}<br>${data.active_event.gallery_url}</p>` : `<p class="muted">ยังไม่มีอีเวนต์ล่าสุด</p>`}`;
}

async function copyGalleryBaseUrl() {
  const data = await api("/api/diagnostics/readiness");
  await navigator.clipboard.writeText(data.public_gallery_base_url);
  alert("คัดลอก Gallery Base URL แล้ว");
}

async function retryGoogleUploads() {
  const result = await api("/api/google/retry-ready", { method: "POST" });
  alert(`Queued ${result.queued} upload(s)`);
  loadSettings();
}

async function chooseEventRoot() {
  $("#eventRootStatus").textContent = "กำลังเปิดหน้าต่างเลือกโฟลเดอร์...";
  try {
    const result = await api("/api/settings/choose-event-root", { method: "POST", body: JSON.stringify({}) });
    if (result.event_root) $("#eventRootInput").value = result.event_root;
    $("#eventRootStatus").textContent = result.cancelled ? "ยกเลิกการเลือกโฟลเดอร์" : `เลือกและบันทึกแล้ว อีเวนต์ใหม่จะลงที่: ${result.event_root}`;
  } catch (err) {
    $("#eventRootStatus").textContent = `เปิดตัวเลือกโฟลเดอร์ไม่ได้: ${err.message}`;
    alert(`เปิดตัวเลือกโฟลเดอร์ไม่ได้\n\nให้พิมพ์หรือวาง path ในช่อง Event Root แล้วกด Create / Verify Folder\n\n${err.message}`);
  }
}

async function setEventRootOption(path) {
  $("#eventRootInput").value = path;
  await verifyEventRoot();
}

async function loadLocalFolders(path = "") {
  const target = path || "";
  const data = await api(`/api/settings/local-folders${target ? `?path=${encodeURIComponent(target)}` : ""}`);
  const current = data.current || "Computer";
  $("#localFolderBrowser").innerHTML = `<div class="pathbox">${current}</div>
    <div class="row" style="margin:10px 0 12px">
      ${data.parent ? `<button type="button" class="secondary" onclick='loadLocalFolders(${jsArg(data.parent)})'>Up</button>` : ""}
      ${data.current && data.writable ? `<button type="button" onclick='setEventRootOption(${jsArg(data.current)})'>Use Current Folder</button>` : ""}
      ${data.current && data.can_create_child ? `<button type="button" class="secondary" onclick='createLocalFolder(${jsArg(data.current)})'>New Folder</button>` : ""}
      <span class="muted">${data.writable ? "เขียนไฟล์ได้" : data.current ? "โฟลเดอร์นี้ไม่มีสิทธิ์เขียน ให้เลือกโฟลเดอร์ย่อยหรือ Documents/Pictures แทน" : "เลือก drive หรือโฟลเดอร์ก่อน"}</span>
    </div>
    <div class="folder-list">${data.folders.map(f => `<button type="button" class="folder-row" onclick='loadLocalFolders(${jsArg(f.path)})'><span>${f.name}</span><small>${f.path}</small></button>`).join("") || `<p class="muted">ไม่มีโฟลเดอร์ย่อย หรือระบบไม่มีสิทธิ์อ่าน</p>`}</div>`;
}

async function createLocalFolder(parent) {
  const name = prompt("ตั้งชื่อโฟลเดอร์ใหม่", "CS.BXXM Events");
  if (!name) return;
  try {
    const result = await api("/api/settings/local-folders", { method: "POST", body: JSON.stringify({ parent, name }) });
    await loadLocalFolders(result.path);
    $("#eventRootInput").value = result.path;
    $("#eventRootStatus").textContent = `สร้างโฟลเดอร์แล้ว กด Use This Folder หรือใช้ปุ่ม Use Current Folder เพื่อบันทึก: ${result.path}`;
  } catch (err) {
    alert(`สร้างโฟลเดอร์ไม่ได้\n\n${err.message}`);
  }
}

async function verifyEventRoot() {
  const eventRoot = $("#eventRootInput").value;
  try {
    const result = await api("/api/settings/verify-event-root", { method: "POST", body: JSON.stringify({ event_root: eventRoot }) });
    $("#eventRootInput").value = result.event_root;
    $("#eventRootStatus").textContent = `บันทึกแล้ว อีเวนต์ใหม่จะถูกสร้างใน: ${result.event_root}`;
  } catch (err) {
    $("#eventRootStatus").textContent = `ใช้โฟลเดอร์นี้ไม่ได้: ${err.message}`;
    alert(`ใช้โฟลเดอร์นี้ไม่ได้\n\n${err.message}`);
  }
}

async function disconnectGoogle() {
  if (!confirm("Disconnect Google Drive from this local CS.BXXM Studio?")) return;
  await api("/api/google/disconnect", { method: "POST" });
  loadSettings();
}

function loadGalleryPreview() {
  layout("gallery", `<div class="top hero-panel"><div><p class="kicker">Gallery Monitor</p><h1>จัดการแกลเลอรี</h1><p class="hero-note">รูปใหม่จะแสดงอัตโนมัติเมื่อพร้อม คุณสามารถซ่อน กู้คืน หรือประมวลผลรูปใหม่ได้จากหน้านี้</p></div><div class="row hero-actions-admin"><a id="openGuest" class="button secondary" href="#">เปิดแกลเลอรีผู้ชม</a><button id="rebuildGalleryBtn" class="secondary" type="button">สร้างรูปใหม่จากต้นฉบับ</button><button class="secondary" onclick="loadGalleryPreview()">รีเฟรช</button></div></div><section class="panel"><div class="preview-head"><div><h2>ข้อมูลที่ผู้เข้าชมเห็น</h2><p class="muted">ตั้งชื่อที่แสดงและช่องทางติดต่อของคุณบนหน้าแกลเลอรี</p></div></div><form id="guestSettingsForm" class="inline-form"><label><span>เครดิตหรือชื่อสตูดิโอ</span><input name="credit_text" placeholder="Photo Booth Experience by CS.BXXM STUDIO"></label><label><span>ช่องทางติดต่อของคุณ</span><input name="report_contact" placeholder="Instagram, LINE, อีเมล หรือเว็บไซต์"></label><button type="submit">บันทึกข้อมูล</button></form><div id="galleryFeatureSettings" class="gallery-feature-settings"></div></section><section class="panel" style="margin-top:16px"><div class="preview-head"><div><h2>สถานะรูปภาพ</h2><p class="muted">รูปใหม่จะแสดงในแกลเลอรีอัตโนมัติเมื่อพร้อม</p></div><div class="row"><button id="publishAllBtn" class="secondary" type="button">กู้คืนรูปที่ค้าง</button></div></div><div id="gallerySummary" class="review-summary"></div><div id="gallery" class="review-grid"></div></section>`);
  api("/api/dashboard").then(d => {
    if (!d.active_event) {
      $("#publishAllBtn").disabled = true;
      return { event: null, photos: [] };
    }
    $("#openGuest").href = d.active_event.gallery_url;
    $("#rebuildGalleryBtn").onclick = () => rebuildPhotos(d.active_event.id);
    loadGuestSettings(d.active_event.id);
    $("#publishAllBtn").onclick = () => publishAllPhotos(d.active_event.id);
    return api(`/api/events/${d.active_event.id}/photos`).then(photos => ({ event: d.active_event, photos }));
  }).then(({ event, photos }) => {
    renderPhotoReview(event, photos);
  });
}

async function loadGuestSettings(eventId) {
  const settings = await api(`/api/events/${eventId}/gallery-settings`);
  const form = $("#guestSettingsForm");
  for (const field of ["credit_text", "report_contact"]) {
    form.elements[field].value = settings[field] || "";
  }
  form.onsubmit = async (ev) => {
    ev.preventDefault();
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    try {
      const values = Object.fromEntries(new FormData(form));
      await api(`/api/events/${eventId}/gallery-settings`, { method: "POST", body: JSON.stringify(values) });
      alert("บันทึกข้อมูลแกลเลอรีแล้ว");
    } catch (err) {
      alert(`บันทึกไม่สำเร็จ\n\n${err.message}`);
    } finally {
      submit.disabled = false;
    }
  };
}

function renderPhotoReview(event, photos) {
  if (!event) {
    $("#gallerySummary").innerHTML = "";
    $("#gallery").innerHTML = `<div class="empty-state"><b>ยังไม่มีอีเวนต์</b><br><span>สร้างหรือ Start Event ก่อน แล้วรูปจะเข้ามาให้คัดจากโฟลเดอร์ INCOMING</span></div>`;
    return;
  }
  const ready = photos.filter(p => p.thumbnail && p.preview);
  const published = ready.filter(p => p.published && !p.hidden).length;
  const review = ready.filter(p => !p.published && !p.hidden).length;
  const hidden = ready.filter(p => p.hidden).length;
  $("#gallerySummary").innerHTML = `<div class="mini-metrics"><div><b>${ready.length}</b><span>พร้อมดู</span></div><div><b>${published}</b><span>ผู้ใช้เห็น</span></div><div><b>${review}</b><span>รอตรวจ</span></div><div><b>${hidden}</b><span>ซ่อน</span></div></div>`;
  $("#gallery").innerHTML = photos.map(p => photoReviewCard(event.id, p)).join("") || `<div class="empty-state"><b>ยังไม่มีรูปในระบบ</b><br><span>วางรูปจริงใน INCOMING แล้วระบบจะประมวลผล อัปโหลด และเผยแพร่ให้อัตโนมัติ</span></div>`;
}

function photoReviewCard(eventId, p) {
  const ready = p.thumbnail && p.preview;
  const visible = p.published && !p.hidden;
  const status = p.hidden ? "HIDDEN" : p.published ? "PUBLISHED" : p.status;
  const img = ready ? `<a href="${p.preview}" target="_blank"><img src="${p.thumbnail}" alt="${html(p.filename)}"></a>` : `<div class="review-placeholder">${html(p.status || "WAITING")}</div>`;
  const publish = ready && !visible ? `<button type="button" onclick='publishPhoto(${jsArg(eventId)}, ${jsArg(p.id)})'>เผยแพร่</button>` : "";
  const hideLabel = p.hidden ? "แสดงรูป" : "ซ่อนรูป";
  const hide = ready ? `<button type="button" class="secondary" onclick='setPhotoHidden(${jsArg(eventId)}, ${jsArg(p.id)}, ${p.hidden ? "false" : "true"})'>${hideLabel}</button>` : "";
  const retry = `<button type="button" class="secondary" onclick='rebuildOnePhoto(${jsArg(eventId)}, ${jsArg(p.id)})'>ทำรูปใหม่</button>`;
  return `<article class="review-card ${visible ? "is-live" : p.hidden ? "is-hidden" : ""}">
    <div class="review-media">${img}<span class="review-badge">${html(status)}</span></div>
    <div class="review-body"><b>${html(p.filename)}</b>${p.error ? `<small class="badtext">${html(p.error)}</small>` : `<small class="muted">${visible ? "กำลังแสดงในฝั่งผู้ใช้" : p.hidden ? "ซ่อนจากฝั่งผู้ใช้" : "ยังไม่แสดงในฝั่งผู้ใช้"}</small>`}<div class="row">${publish}${hide}${retry}</div></div>
  </article>`;
}

async function publishPhoto(eventId, photoId) {
  try {
    await api(`/api/events/${eventId}/photos/${photoId}/publish`, { method: "POST" });
    loadGalleryPreview();
  } catch (err) {
    alert(`Publish ไม่สำเร็จ\n\n${err.message}`);
  }
}

async function publishAllPhotos(eventId) {
  if (!confirm("Publish รูปที่พร้อมทั้งหมดให้ผู้ใช้เห็นใน Gallery?")) return;
  const result = await api(`/api/events/${eventId}/photos/publish-all`, { method: "POST" });
  alert(`Publish แล้ว ${result.published} รูป${result.blocked ? `\nข้าม ${result.blocked} รูปที่ยังไม่พร้อมหรือยังไม่ขึ้น Google Drive` : ""}`);
  loadGalleryPreview();
}

async function setPhotoHidden(eventId, photoId, hidden) {
  await api(`/api/events/${eventId}/photos/${photoId}/visibility`, { method: "POST", body: JSON.stringify({ hidden }) });
  loadGalleryPreview();
}

async function rebuildOnePhoto(eventId, photoId) {
  if (!confirm("สร้างไฟล์ Gallery ของรูปนี้ใหม่จาก ORIGINAL?")) return;
  try {
    await api(`/api/events/${eventId}/photos/${photoId}/reprocess`, { method: "POST" });
    loadGalleryPreview();
  } catch (err) {
    alert(`Rebuild ไม่สำเร็จ\n\n${err.message}`);
  }
}

async function loadArchive() {
  layout("archive", `<div class="top hero-panel"><div><p class="kicker">CS.BXXM STUDIO</p><h1>คลังงานถ่ายภาพ</h1><p class="hero-note">รวมงานถ่ายที่ผ่านมา เปิดแกลเลอรี และแชร์ลิงก์ได้</p></div></div><section class="panel"><div class="preview-head"><div><h2>งานทั้งหมด</h2><p class="muted">แสดงงานทั้งหมดจากฐานข้อมูลในเครื่อง</p></div><button class="secondary" onclick="loadArchive()">รีเฟรช</button></div><div id="archiveList"></div></section>`);
  const events = await api("/api/events");
  $("#archiveList").innerHTML = events.map(e => `<div class="queue-line"><span><b>${e.name}</b><br><small class="muted">${e.status} · ${e.root_path}</small></span><span class="row"><a class="button secondary" href="${e.gallery_url}" target="_blank">เปิดแกลเลอรี</a><button class="secondary" onclick='shareGallery(${jsArg(e.gallery_url)}, ${jsArg(e.name)})'>แชร์</button><button onclick='startEvent(${jsArg(e.id)})'>เริ่มงาน</button><button class="bad" onclick='deleteEvent(${jsArg(e.id)}, ${jsArg(e.name)}, true, "archive")'>ลบงาน</button></span></div>`).join("") || `<p class="muted">ยังไม่มีงานในคลัง</p>`;
}

async function loadDiagnostics() {
  layout("diagnostics", `<div class="top hero-panel"><div><p class="kicker">CS.BXXM STUDIO</p><h1>ตรวจสอบระบบ</h1></div><button onclick="runSystemTest()">ตรวจระบบตอนนี้</button></div><div class="grid"><section class="panel span-8"><h2>รายการตรวจสอบ</h2><div id="checks"></div></section><section class="panel span-4"><h2>คิวงาน</h2><div id="diagQueues"></div></section><section class="panel span-4"><h2>ฐานข้อมูล</h2><div id="diagDb"></div></section></div>`);
  const data = await api("/api/diagnostics");
  renderDiagnostics(data);
}
function renderDiagnostics(data) {
  $("#checks").innerHTML = Object.entries(data.checks).map(([k,v]) => {
    const label = k.replace(/^package_/, "package: ").replaceAll("_"," ");
    const tone = v.status === "FAIL" ? "badtext" : v.status === "WARN" ? "warntext" : v.status === "OPTIONAL" ? "optionaltext" : "";
    const required = v.required ? "จำเป็น" : "ไม่บังคับ";
    return `<div class="queue-line diag-line"><span><b>${label}</b><br><small class="muted">${html(v.message)}</small></span><span class="diag-status"><small>${required}</small><b class="${tone}">${v.status}</b></span></div>`;
  }).join("");
  $("#diagQueues").innerHTML = Object.entries(data.queues).map(([k,v]) => `<div class="queue-line"><span>${k.replaceAll("_"," ")}</span><b>${v}</b></div>`).join("");
  $("#diagDb").innerHTML = Object.entries(data.database || {}).map(([k,v]) => `<div class="queue-line"><span>${k.replaceAll("_"," ")}</span><b>${v}</b></div>`).join("");
}
async function runSystemTest() {
  const data = await api("/api/diagnostics/system-test", { method: "POST" });
  renderDiagnostics(data);
  alert(data.ok ? "ตรวจรายการที่จำเป็นผ่านแล้ว" : `ตรวจไม่ผ่าน: ${data.failed_required.join(", ")}`);
}
