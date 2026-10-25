const params = new URLSearchParams(location.search);
const configuredApi = window.MOMENTLINK_API_URL || "";
const API = (params.get("api") || configuredApi || location.origin).replace(/\/$/, "");
const pathPublicId = location.pathname.split("/").filter(Boolean).pop() || "";
const publicId = params.get("event") || (pathPublicId === "gallery" || pathPublicId === "index.html" ? "" : pathPublicId);
let knownPhotoCount = 0;
let loadingPhotos = false;
let galleryRefreshTimer = null;
let galleryUrl = location.href.split("#")[0];
let galleryMeta = { eventName: "", creditText: "ถ่ายภาพโดยทีมโสตโรงเรียน", reportContact: "" };
let galleryPhotos = [];
let currentPhotoIndex = -1;
let touchStartX = 0;
let touchStartY = 0;
let selectionMode = false;
const selectedPhotoIds = new Set();

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
  const r = await fetch(url, { cache: "no-store", credentials: "include" });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

async function fetchDownload(url, filename) {
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) throw new Error("ดาวน์โหลดไม่สำเร็จ");
  const objectUrl = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
}

async function initGallery() {
  if (!publicId) {
    document.body.innerHTML = "<main class='wrap'><div class='empty'>ยังไม่ได้เลือก Gallery</div></main>";
    return;
  }
  try {
    setupScreenQr();
    const meta = await getJson(`${API}/api/gallery/${publicId}`);
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
    clearInterval(galleryRefreshTimer);
    if (!meta.settings.locked) {
      galleryRefreshTimer = setInterval(() => {
        if (!document.hidden) loadPhotos(false);
      }, 10000);
    }
  } catch (err) {
    document.querySelector("#grid").innerHTML = `<div class="empty"><div><b>เปิด Gallery ไม่ได้</b><br>ตรวจสอบลิงก์ QR หรือสถานะ event จากหน้า Dashboard</div></div>`;
    console.error(err);
  }
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
  const pin = document.querySelector("#galleryPin").value.trim();
  const response = await fetch(`${API}/api/gallery/${publicId}/unlock`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ pin })
  });
  document.querySelector("#galleryPin").value = "";
  if (!response.ok) {
    if (response.status === 429) alert("ลองใส่ PIN ผิดหลายครั้ง กรุณารอสักครู่แล้วลองใหม่");
    else alert("PIN ไม่ถูกต้อง");
    return;
  }
  await initGallery();
}

async function copyShareText() {
  const text = `เปิด MomentLink Gallery และดาวน์โหลดรูปได้ที่:\n${galleryUrl}`;
  await navigator.clipboard.writeText(text);
  document.querySelector("#shareJump").textContent = "คัดลอกแล้ว";
}

async function copyDownloadLinks() {
  const data = await getJson(`${API}/api/gallery/${publicId}/downloads`);
  if (data.links.length > 40) {
    alert("ดาวน์โหลดทั้งหมดได้ครั้งละไม่เกิน 40 รูป กรุณาเลือกภาพจากรายการ");
    return;
  }
  await Promise.all(data.links.map(item => fetchDownload(new URL(item.url, API).toString(), item.filename)));
  document.querySelector("#downloadLinks").textContent = `เริ่มดาวน์โหลด ${data.links.length} รูปแล้ว`;
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
      batch = await getJson(`${API}/api/gallery/${publicId}/photos?page=${requestPage}&page_size=100`);
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
    if (photos.length) grid.querySelectorAll(".empty").forEach(item => item.remove());
    const newPhotos = photos.filter(photo => !document.querySelector(`[data-id='${photo.id}']`));
    const placeAtTop = currentPhotoIndex < 0;
    if (placeAtTop) newPhotos.reverse();
    for (const photo of newPhotos) {
      const thumb = photo.variants?.find(v => v.kind === "thumbnail")?.url || "";
      const preview = photo.variants?.find(v => v.kind === "preview")?.url || thumb;
      const finished = photo.variants?.find(v => v.kind === "finished")?.url || preview;
      const galleryPhoto = { id: photo.id, filename: photo.filename, thumb, preview, finished };
      if (placeAtTop) galleryPhotos.unshift(galleryPhoto);
      else galleryPhotos.push(galleryPhoto);
      if (thumb && !document.querySelector("#hero").classList.contains("has-image")) {
        document.querySelector("#hero").style.backgroundImage = `linear-gradient(180deg, rgba(13, 16, 19, .30), rgba(13, 16, 19, .74)), url('${preview}')`;
        document.querySelector("#hero").classList.add("has-image");
      }
      const el = document.createElement("button");
      el.className = "photo";
      el.dataset.id = photo.id;
      el.setAttribute("aria-pressed", selectedPhotoIds.has(photo.id) ? "true" : "false");
      if (selectedPhotoIds.has(photo.id)) el.classList.add("selected");
      const safeName = escapeHtml(photo.filename);
      el.innerHTML = `${thumb ? `<img src="${thumb}" alt="${safeName}" loading="lazy"><span>${safeName}</span>` : `<div class="empty">${safeName}</div>`}<i class="photo-select-mark" aria-hidden="true">✓</i>`;
      el.onclick = () => selectionMode ? togglePhotoSelection(photo.id, el) : openLightbox(galleryPhotos.findIndex(item => item.id === photo.id));
      if (placeAtTop) grid.prepend(el);
      else grid.appendChild(el);
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
  modal.innerHTML = `<div class="lightbox"><div class="lightbox-top"><div><div class="lightbox-title">${safeName}</div><div class="lightbox-count">${position}</div></div><button class="button secondary" onclick="closeLightbox()">ปิด</button></div><div class="lightbox-stage"><button class="nav-photo prev" onclick="moveLightbox(-1)" aria-label="รูปก่อนหน้า">‹</button><img src="${photo.preview}" alt="${safeName}"><button class="nav-photo next" onclick="moveLightbox(1)" aria-label="รูปถัดไป">›</button></div><div class="actions"><button id="savePhotoButton" class="button" onclick="savePhoto(${index})">ดาวน์โหลดไฟล์นี้</button><button class="button secondary" onclick="reportIssue()">แจ้งรูปเสีย</button></div></div>`;
  modal.classList.add("open");
}

async function savePhoto(index) {
  const photo = galleryPhotos[index];
  if (!photo) return;
  const button = document.querySelector("#savePhotoButton");
  const originalLabel = button?.textContent || "ดาวน์โหลดรูปนี้";
  if (button) {
    button.disabled = true;
    button.textContent = "กำลังดาวน์โหลด...";
  }
  fetchDownload(photo.finished, photo.filename).catch(err => alert(err.message));
  window.setTimeout(() => {
    if (button?.isConnected) {
      button.disabled = false;
      button.textContent = originalLabel;
    }
  }, 1600);
}

document.addEventListener("visibilitychange", () => {
  if (!document.hidden && publicId) loadPhotos(false);
});

function triggerFileDownload(url) {
  const photo = galleryPhotos.find(item => item.finished === url);
  fetchDownload(url, photo?.filename || url.split("/").pop() || "momentlink-photo.jpg").catch(err => alert(err.message));
}

function toggleSelectionMode() {
  selectionMode = !selectionMode;
  if (!selectionMode) selectedPhotoIds.clear();
  document.querySelector("#selectModeBtn").textContent = selectionMode ? "ยกเลิกการเลือก" : "เลือกหลายรูป";
  document.querySelector("#selectModeBtn").setAttribute("aria-pressed", String(selectionMode));
  document.querySelector("#selectedCount").hidden = !selectionMode;
  document.querySelector("#downloadSelectedBtn").hidden = !selectionMode;
  document.querySelectorAll(".photo").forEach(card => {
    const selected = selectedPhotoIds.has(card.dataset.id);
    card.classList.toggle("selected", selected);
    card.setAttribute("aria-pressed", String(selected));
  });
  updateSelectionControls();
}

function togglePhotoSelection(photoId, card) {
  if (selectedPhotoIds.has(photoId)) selectedPhotoIds.delete(photoId);
  else selectedPhotoIds.add(photoId);
  const selected = selectedPhotoIds.has(photoId);
  card.classList.toggle("selected", selected);
  card.setAttribute("aria-pressed", String(selected));
  updateSelectionControls();
}

function updateSelectionControls() {
  const count = selectedPhotoIds.size;
  const countLabel = document.querySelector("#selectedCount");
  const downloadButton = document.querySelector("#downloadSelectedBtn");
  if (!countLabel || !downloadButton) return;
  countLabel.textContent = `เลือก ${count} รูป`;
  downloadButton.disabled = count === 0;
  downloadButton.textContent = count > 1 ? `ดาวน์โหลด ${count} รูป` : "ดาวน์โหลดรูปที่เลือก";
}

function downloadSelectedPhotos() {
  const photos = [...selectedPhotoIds];
  if (!photos.length) return;
  if (photos.length === 1) {
    const photo = galleryPhotos.find(item => item.id === photos[0]);
    if (photo) triggerFileDownload(photo.finished);
    return;
  }
  if (photos.length > 40) {
    alert("เลือกดาวน์โหลดได้ครั้งละไม่เกิน 40 รูป");
    return;
  }
  const url = new URL(`${API}/api/gallery/${publicId}/downloads.zip`);
  photos.forEach(id => url.searchParams.append("photo_id", id));
  fetch(url, { credentials: "include" }).then(async response => {
    if (!response.ok) throw new Error("ดาวน์โหลดไม่สำเร็จ");
    const blob = await response.blob();
    const link = document.createElement("a");
    const objectUrl = URL.createObjectURL(blob);
    link.href = objectUrl;
    link.download = "momentlink-photos.zip";
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
  }).catch(err => alert(err.message));
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
