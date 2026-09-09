const params = new URLSearchParams(location.search);
const configuredApi = window.MOMENTLINK_API_URL || "";
const API = (params.get("api") || configuredApi || location.origin).replace(/\/$/, "");
const pathPublicId = location.pathname.split("/").filter(Boolean).pop() || "";
const publicId = params.get("event") || (pathPublicId === "gallery" || pathPublicId === "index.html" ? "" : pathPublicId);
let knownPhotoCount = 0;
let loadingPhotos = false;
let galleryUrl = location.href.split("#")[0];
let galleryPin = sessionStorage.getItem(`momentlink-pin-${publicId}`) || "";
let galleryMeta = { eventName: "", creditText: "ถ่ายภาพโดยทีมโสตโรงเรียน", reportContact: "" };
let galleryPhotos = [];
let currentPhotoIndex = -1;
let touchStartX = 0;
let touchStartY = 0;

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[ch]);
}

async function getJson(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function initGallery() {
  if (!publicId) {
    document.body.innerHTML = "<main class='wrap'><div class='empty'>ยังไม่ได้เลือก Gallery</div></main>";
    return;
  }
  try {
    setupScreenQr();
    const meta = await getJson(withPin(`${API}/api/gallery/${publicId}`));
    document.querySelector("h1").textContent = meta.event.name;
    document.title = `${meta.event.name} · MomentLink`;
    galleryUrl = meta.event.gallery_url || galleryUrl;
    galleryMeta = {
      eventName: meta.event.name || "",
      creditText: meta.settings.credit_text || "ถ่ายภาพโดยทีมโสตโรงเรียน",
      reportContact: meta.settings.report_contact || ""
    };
    renderGalleryInfo();
    document.querySelector("#eventDate").textContent = meta.event.event_date || "Event Gallery";
    knownPhotoCount = meta.event.photo_count || 0;
    document.querySelector("#heroSub").textContent = meta.event.photo_count
      ? `${meta.event.photo_count} รูปพร้อมให้ชม ดาวน์โหลด และแชร์จากอุปกรณ์ของคุณ`
      : "รูปภาพจะเริ่มปรากฏทันทีหลังทีมถ่ายภาพเผยแพร่ภาพจากงาน";
    document.querySelector("#count").textContent = `${knownPhotoCount} รูป`;
    document.querySelector("#statPhotos").textContent = knownPhotoCount;
    document.querySelector("#statMode").textContent = meta.settings.allow_download ? "Download" : "View";
    document.querySelector("#downloadLinks").style.display = meta.settings.allow_download && !meta.settings.locked ? "inline-flex" : "none";
    document.querySelector("#pinPanel").style.display = meta.settings.locked ? "grid" : "none";
    if (!meta.settings.locked) await loadPhotos(true);
    setInterval(() => {
      if (!document.hidden) loadPhotos(currentPhotoIndex < 0);
    }, 20000);
  } catch (err) {
    document.querySelector("#grid").innerHTML = `<div class="empty"><div><b>เปิด Gallery ไม่ได้</b><br>ตรวจสอบลิงก์ QR หรือสถานะ event จากหน้า Dashboard</div></div>`;
    console.error(err);
  }
}

function withPin(url) {
  const next = new URL(url, location.origin);
  if (galleryPin) next.searchParams.set("pin", galleryPin);
  return next.toString();
}

function setupScreenQr() {
  const qr = document.querySelector("#screenQr");
  const mobileQr = document.querySelector("#mobileQr");
  const qrUrl = `${API}/api/gallery/${publicId}/qr.png`;
  if (qr) qr.src = qrUrl;
  if (mobileQr) mobileQr.src = qrUrl;
  const copyQr = async () => {
    try {
      await navigator.clipboard.writeText(galleryUrl);
      const label = document.querySelector(".screen-qr-copy span");
      if (label) label.textContent = "Copied link";
    } catch (err) {
      console.error(err);
    }
  };
  if (qr) qr.onclick = copyQr;
  if (mobileQr) mobileQr.onclick = copyQr;
}

function renderGalleryInfo() {
  const credit = galleryMeta.creditText;
  document.querySelector("#creditHero").textContent = credit;
  document.querySelector("#creditFooter").textContent = credit;
  document.querySelector("#mobileGalleryUrl").textContent = galleryUrl;
  const footer = document.querySelector("#reportFooter");
  footer.textContent = galleryMeta.reportContact
    ? `พบปัญหารูปเสียหรือดาวน์โหลดไม่ได้ แจ้งทีมงานได้ที่ ${galleryMeta.reportContact}`
    : "พบปัญหารูปเสียหรือดาวน์โหลดไม่ได้ กด “แจ้งปัญหา” เพื่อคัดลอกรายละเอียดให้ทีมงาน";
}

async function unlockGallery(ev) {
  ev.preventDefault();
  galleryPin = document.querySelector("#galleryPin").value.trim();
  sessionStorage.setItem(`momentlink-pin-${publicId}`, galleryPin);
  await initGallery();
}

async function copyShareText() {
  const text = `เปิด MomentLink Gallery และดาวน์โหลดรูปได้ที่:\n${galleryUrl}`;
  await navigator.clipboard.writeText(text);
  document.querySelector("#shareJump").textContent = "คัดลอกแล้ว";
}

async function copyDownloadLinks() {
  const data = await getJson(withPin(`${API}/api/gallery/${publicId}/downloads`));
  const lines = data.links.map(item => `${item.filename}\n${new URL(item.url, location.origin).toString()}`);
  await navigator.clipboard.writeText(`ลิงก์ดาวน์โหลดรูป ${data.event}\n${data.gallery_url}\n\n${lines.join("\n\n")}`);
  document.querySelector("#downloadLinks").textContent = `คัดลอก ${data.links.length} ลิงก์แล้ว`;
}

async function reportIssue() {
  const text = [
    "แจ้งปัญหา MomentLink Gallery",
    `งาน: ${galleryMeta.eventName || document.title}`,
    `ลิงก์: ${galleryUrl}`,
    galleryMeta.reportContact ? `ช่องทางติดต่อทีมงาน: ${galleryMeta.reportContact}` : "",
    "ปัญหาที่พบ: "
  ].filter(Boolean).join("\n");
  try {
    await navigator.clipboard.writeText(text);
    document.querySelector("#reportHero").textContent = "คัดลอกข้อความแล้ว";
    alert("คัดลอกข้อความแจ้งปัญหาแล้ว ส่งให้ทีมงานได้เลย");
  } catch (err) {
    alert(text);
  }
}

async function loadPhotos(reset = false) {
  if (loadingPhotos) return;
  loadingPhotos = true;
  try {
    document.querySelector("#syncState").textContent = "กำลังอัปเดต";
    const photos = [];
    let requestPage = 1;
    let batch = [];
    do {
      batch = await getJson(withPin(`${API}/api/gallery/${publicId}/photos?page=${requestPage}&page_size=100`));
      photos.push(...batch);
      requestPage += 1;
    } while (reset && batch.length === 100 && requestPage <= 50);
    const grid = document.querySelector("#grid");
    if (reset) {
      grid.innerHTML = "";
      galleryPhotos = [];
      currentPhotoIndex = -1;
    }
    if (!photos.length && !grid.children.length) {
      grid.innerHTML = "<div class='empty'><div><b>กำลังรอรูปจากทีมถ่ายภาพ</b><br>เมื่อรูปถูก publish แล้วจะขึ้นที่นี่อัตโนมัติ คุณเปิดหน้านี้ทิ้งไว้ได้เลย</div></div>";
      document.querySelector("#syncState").textContent = "ยังไม่มีรูปเผยแพร่";
      return;
    }
    for (const photo of photos) {
      if (document.querySelector(`[data-id='${photo.id}']`)) continue;
      const thumb = photo.variants?.find(v => v.kind === "thumbnail")?.url || "";
      const preview = photo.variants?.find(v => v.kind === "preview")?.url || thumb;
      const finished = photo.variants?.find(v => v.kind === "finished")?.url || preview;
      const index = galleryPhotos.push({ id: photo.id, filename: photo.filename, thumb, preview, finished }) - 1;
      if (thumb && !document.querySelector("#hero").classList.contains("has-image")) {
        document.querySelector("#hero").style.backgroundImage = `linear-gradient(180deg, rgba(13, 16, 19, .30), rgba(13, 16, 19, .74)), url('${preview}')`;
        document.querySelector("#hero").classList.add("has-image");
      }
      const el = document.createElement("button");
      el.className = "photo";
      el.dataset.id = photo.id;
      const safeName = escapeHtml(photo.filename);
      el.innerHTML = thumb ? `<img src="${thumb}" alt="${safeName}" loading="lazy"><span>${safeName}</span>` : `<div class="empty">${safeName}</div>`;
      el.onclick = () => openLightbox(index);
      grid.appendChild(el);
    }
    knownPhotoCount = Math.max(knownPhotoCount, document.querySelectorAll(".photo").length);
    document.querySelector("#count").textContent = `${knownPhotoCount} รูป`;
    document.querySelector("#statPhotos").textContent = knownPhotoCount;
    document.querySelector("#syncState").textContent = "อัปเดตล่าสุดเมื่อสักครู่";
  } catch (err) {
    document.querySelector("#syncState").textContent = "อัปเดตไม่สำเร็จ";
    console.error(err);
  } finally {
    loadingPhotos = false;
  }
}

function openLightbox(index) {
  const photo = galleryPhotos[index];
  if (!photo) return;
  currentPhotoIndex = index;
  const modal = document.querySelector("#lightbox");
  const safeName = escapeHtml(photo.filename);
  const position = `${index + 1} / ${galleryPhotos.length}`;
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const saveLabel = ios ? "บันทึกลงรูปภาพ" : "ดาวน์โหลดรูปนี้";
  modal.innerHTML = `<div class="lightbox"><div class="lightbox-top"><div><div class="lightbox-title">${safeName}</div><div class="lightbox-count">${position}</div></div><button class="button secondary" onclick="closeLightbox()">ปิด</button></div><div class="lightbox-stage"><button class="nav-photo prev" onclick="moveLightbox(-1)" aria-label="รูปก่อนหน้า">‹</button><img src="${photo.preview}" alt="${safeName}"><button class="nav-photo next" onclick="moveLightbox(1)" aria-label="รูปถัดไป">›</button></div><div class="actions"><button id="savePhotoButton" class="button" onclick="savePhoto(${index})">${saveLabel}</button><button class="button secondary" onclick="reportIssue()">แจ้งรูปเสีย</button></div></div>`;
  modal.classList.add("open");
}

async function savePhoto(index) {
  const photo = galleryPhotos[index];
  if (!photo) return;
  const button = document.querySelector("#savePhotoButton");
  const originalLabel = button?.textContent || "ดาวน์โหลดรูปนี้";
  if (button) {
    button.disabled = true;
    button.textContent = "กำลังเตรียมรูป...";
  }
  try {
    const response = await fetch(photo.finished);
    if (!response.ok) throw new Error(await response.text());
    const blob = await response.blob();
    const file = new File([blob], photo.filename, { type: blob.type || "image/jpeg" });
    if (navigator.share && (!navigator.canShare || navigator.canShare({ files: [file] }))) {
      await navigator.share({ files: [file], title: photo.filename });
      return;
    }
    downloadBlob(blob, photo.filename);
  } catch (err) {
    if (err?.name !== "AbortError") {
      console.error(err);
      window.location.href = photo.finished;
    }
  } finally {
    if (button?.isConnected) {
      button.disabled = false;
      button.textContent = originalLabel;
    }
  }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function moveLightbox(delta) {
  if (!galleryPhotos.length || currentPhotoIndex < 0) return;
  const next = (currentPhotoIndex + delta + galleryPhotos.length) % galleryPhotos.length;
  openLightbox(next);
}

function closeLightbox() {
  document.querySelector("#lightbox").classList.remove("open");
  currentPhotoIndex = -1;
}

document.addEventListener("keydown", ev => {
  if (currentPhotoIndex < 0) return;
  if (ev.key === "ArrowLeft") moveLightbox(-1);
  if (ev.key === "ArrowRight") moveLightbox(1);
  if (ev.key === "Escape") closeLightbox();
});

document.addEventListener("touchstart", ev => {
  if (currentPhotoIndex < 0 || !ev.changedTouches.length) return;
  touchStartX = ev.changedTouches[0].clientX;
  touchStartY = ev.changedTouches[0].clientY;
}, { passive: true });

document.addEventListener("touchend", ev => {
  if (currentPhotoIndex < 0 || !ev.changedTouches.length) return;
  const dx = ev.changedTouches[0].clientX - touchStartX;
  const dy = ev.changedTouches[0].clientY - touchStartY;
  if (Math.abs(dx) > 56 && Math.abs(dx) > Math.abs(dy) * 1.35) {
    moveLightbox(dx < 0 ? 1 : -1);
  }
}, { passive: true });
