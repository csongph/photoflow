/**
 * CS.BXXM STUDIO - Real-Time Photo Booth Gallery Script
 * High-performance mobile viewer, Web Share API, and 1-Tap Downloads.
 */

const params = new URLSearchParams(location.search);
const configuredApi = window.MOMENTLINK_API_URL || "";
const API = (params.get("api") || configuredApi || location.origin).replace(/\/$/, "");
const pathPublicId = location.pathname.split("/").filter(Boolean).pop() || "";
const publicId = params.get("event") || (pathPublicId === "gallery" || pathPublicId === "index.html" ? "" : pathPublicId);

let knownPhotoCount = 0;
let loadingPhotos = false;
let galleryRefreshTimer = null;
let galleryUrl = location.href.split("#")[0];
let galleryMeta = {
  eventName: "CS.BXXM Gallery",
  creditText: "Photo Booth Experience by CS.BXXM STUDIO",
  reportContact: ""
};

let galleryPhotos = [];
let currentFilter = "all"; // "all" | "recent"
let currentPhotoIndex = -1;
let touchStartX = 0;
let touchStartY = 0;
let selectionMode = false;
const selectedPhotoIds = new Set();
let sessionStartTime = Date.now();

// Utility Toast
function showToast(message, type = "info") {
  const container = document.querySelector("#toastContainer") || document.body;
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span class="toast-dot"></span><span>${escapeHtml(message)}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(-6px)";
    setTimeout(() => toast.remove(), 250);
  }, 3200);
}

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

// -------------------------------------------------------------------------
// INITIALIZATION
// -------------------------------------------------------------------------

async function initGallery() {
  if (!publicId) {
    const controls = document.querySelector(".gallery-controls");
    const shareCard = document.querySelector(".qr-share-card");
    const statusBar = document.querySelector(".bar-status");
    if (controls) controls.style.display = "none";
    if (shareCard) shareCard.style.display = "none";
    if (statusBar) statusBar.style.display = "none";
    document.querySelector("#grid").innerHTML = `
      <div class="empty-gallery">
        <span class="empty-icon">📷</span>
        <h4>ยังไม่ได้ระบุ Gallery</h4>
        <p>กรุณาสแกน QR Code จากหน้างานโฟโต้บูทใหม่อีกครั้ง</p>
      </div>`;
    return;
  }

  try {
    setupScreenQr();
    const meta = await getJson(`${API}/api/gallery/${publicId}`);
    
    // Page Title & Header
    const eventName = meta.event?.name || "CS.BXXM Gallery";
    document.title = `${eventName} · CS.BXXM STUDIO`;
    const eventTitleEl = document.querySelector("#eventTitle");
    if (eventTitleEl) eventTitleEl.textContent = eventName;
    
    galleryUrl = meta.event?.gallery_url || galleryUrl;
    const brandHome = document.querySelector("#brandHome");
    if (brandHome) brandHome.href = galleryUrl;

    // Gallery settings
    const s = meta.settings || {};
    galleryMeta = {
      eventName,
      creditText: s.credit_text || "Photo Booth Experience by CS.BXXM STUDIO",
      reportContact: s.report_contact || ""
    };

    renderGalleryInfo();

    const dateEl = document.querySelector("#eventDate");
    if (dateEl) dateEl.textContent = meta.event?.event_date || "LIVE PHOTO BOOTH";

    knownPhotoCount = meta.event?.photo_count || 0;
    updatePhotoCountUI(knownPhotoCount);

    const allowDl = s.allow_download && !s.locked;
    const dlBtn = document.querySelector("#downloadLinks");
    if (dlBtn) dlBtn.style.display = allowDl ? "inline-flex" : "none";

    const pinPanel = document.querySelector("#pinPanel");
    if (pinPanel) pinPanel.style.display = s.locked ? "flex" : "none";

    if (!s.locked) {
      await loadPhotos(true);
    }

    clearInterval(galleryRefreshTimer);
    if (!s.locked) {
      galleryRefreshTimer = setInterval(() => {
        if (!document.hidden) loadPhotos(false);
      }, 8000);
    }
  } catch (err) {
    console.error(err);
    document.querySelector("#grid").innerHTML = `
      <div class="empty-gallery">
        <span class="empty-icon">⚠️</span>
        <h4>ไม่สามารถเปิด Gallery ได้</h4>
        <p>กรุณาตรวจสอบการเชื่อมต่ออินเทอร์เน็ต หรือลองรีเฟรชหน้านี้ใหม่อีกครั้ง</p>
      </div>`;
  }
}

function updatePhotoCountUI(count) {
  const countEl = document.querySelector("#count");
  if (countEl) countEl.textContent = `${count} รูป`;
  const subEl = document.querySelector("#heroSub");
  if (subEl) {
    subEl.textContent = count > 0 
      ? `รูปภาพในงานพร้อมดาวน์โหลดความละเอียดสูง ${count} รูป`
      : "รูปภาพจากโฟโต้บูทจะปรากฏที่นี่ทันทีหลังการถ่ายภาพ";
  }
}

function setupScreenQr() {
  const mobileQr = document.querySelector("#mobileQr");
  const qrUrl = `${API}/api/gallery/${publicId}/qr.png`;
  if (mobileQr) mobileQr.src = qrUrl;
}

function renderGalleryInfo() {
  const creditEl = document.querySelector("#creditFooter");
  if (creditEl) creditEl.textContent = galleryMeta.creditText;

  const reportEl = document.querySelector("#reportFooter");
  if (reportEl) {
    reportEl.textContent = galleryMeta.reportContact
      ? `พบปัญหารูปภาพหรือติดต่อทีมงาน: ${galleryMeta.reportContact}`
      : "พบปัญหารูปภาพหรือดาวน์โหลดไม่ได้ กด “แจ้งปัญหา” เพื่อส่งรายละเอียดให้ทีมงาน";
  }
}

// -------------------------------------------------------------------------
// INTERACTIONS & COPY
// -------------------------------------------------------------------------

async function copyShareText() {
  const text = `เปิดดูรูปถ่ายและดาวน์โหลดความคมชัดสูงจากงาน ${galleryMeta.eventName}:\n${galleryUrl}`;
  try {
    await navigator.clipboard.writeText(text);
    showToast("คัดลอกลิงก์แกลเลอรีเรียบร้อยแล้ว", "success");
  } catch (err) {
    console.error(err);
  }
}

async function shareGalleryNative() {
  if (navigator.share) {
    try {
      await navigator.share({
        title: `${galleryMeta.eventName} · CS.BXXM STUDIO`,
        text: `ชมและดาวน์โหลดรูปถ่ายจากงาน ${galleryMeta.eventName} ที่นี่:`,
        url: galleryUrl
      });
      return;
    } catch (err) {
      if (err.name !== "AbortError") copyShareText();
    }
  } else {
    copyShareText();
  }
}

async function copyDownloadLinks() {
  try {
    const data = await getJson(`${API}/api/gallery/${publicId}/downloads`);
    if (!data.links || !data.links.length) {
      showToast("ยังไม่มีรูปให้ดาวน์โหลด", "info");
      return;
    }
    if (data.links.length > 40) {
      showToast("สามารถดาวน์โหลดพร้อมกันได้สูงสุดครั้งละ 40 รูป กรุณาเลือกเฉพาะรูปที่ต้องการ", "info");
      toggleSelectionMode();
      return;
    }
    showToast(`กำลังเริ่มดาวน์โหลด ${data.links.length} รูป...`, "success");
    await Promise.all(data.links.map(item => fetchDownload(new URL(item.url, API).toString(), item.filename)));
  } catch (err) {
    console.error(err);
    showToast("เกิดข้อผิดพลาดในการดาวน์โหลด", "error");
  }
}

async function reportIssue() {
  const text = [
    "แจ้งปัญหา Photo Booth Gallery (CS.BXXM STUDIO)",
    `งาน: ${galleryMeta.eventName}`,
    `ลิงก์: ${galleryUrl}`,
    galleryMeta.reportContact ? `ทีมงาน: ${galleryMeta.reportContact}` : "",
    "รายละเอียดปัญหา: "
  ].filter(Boolean).join("\n");
  try {
    await navigator.clipboard.writeText(text);
    showToast("คัดลอกข้อความแจ้งปัญหาแล้ว นำไปส่งให้ทีมงานได้เลยครับ", "success");
  } catch (err) {
    alert(text);
  }
}

// -------------------------------------------------------------------------
// PHOTO LOADING & RENDERING
// -------------------------------------------------------------------------

async function loadPhotos(reset = false) {
  if (loadingPhotos) return;
  loadingPhotos = true;

  const syncText = document.querySelector("#syncStateText");
  if (syncText) syncText.textContent = "SYNCING...";

  try {
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
      grid.innerHTML = `
        <div class="empty-gallery">
          <span class="empty-icon">⏳</span>
          <h4>กำลังรอรูปภาพจากโฟโต้บูท</h4>
          <p>เมื่อถ่ายรูปแล้ว รูปจะเด้งขึ้นที่นี่อัตโนมัติ คุณสามารถเปิดหน้านี้รอได้เลยครับ</p>
        </div>`;
      if (syncText) syncText.textContent = "STANDBY";
      return;
    }

    // Remove empty state / initial skeletons if real photos arrive
    if (photos.length) {
      grid.querySelectorAll(".empty-gallery, .skeleton-card").forEach(el => el.remove());
    }

    const newPhotos = photos.filter(photo => !document.querySelector(`[data-id='${photo.id}']`));
    const isInitial = galleryPhotos.length === 0;

    // Photos arrive newest first
    for (const photo of newPhotos) {
      const thumb = photo.variants?.find(v => v.kind === "thumbnail")?.url || "";
      const preview = photo.variants?.find(v => v.kind === "preview")?.url || thumb;
      const finished = photo.variants?.find(v => v.kind === "finished")?.url || preview;
      const isRecent = (Date.now() - sessionStartTime < 300000) || !isInitial;

      const galleryPhoto = { 
        id: photo.id, 
        filename: photo.filename, 
        thumb, 
        preview, 
        finished,
        isRecent
      };

      galleryPhotos.unshift(galleryPhoto);
      const card = createPhotoCard(galleryPhoto);
      grid.prepend(card);
    }

    knownPhotoCount = Math.max(knownPhotoCount, galleryPhotos.length);
    updatePhotoCountUI(knownPhotoCount);
    updateRecentCount();

    if (syncText) syncText.textContent = "LIVE SYNC";
  } catch (err) {
    console.error(err);
    if (syncText) syncText.textContent = "OFFLINE";
  } finally {
    loadingPhotos = false;
  }
}

function createPhotoCard(photo) {
  const card = document.createElement("div");
  card.className = "photo-card";
  card.dataset.id = photo.id;
  card.dataset.recent = photo.isRecent ? "true" : "false";

  const safeName = escapeHtml(photo.filename);
  
  card.innerHTML = `
    ${photo.isRecent ? `<span class="photo-badge-new">NEW</span>` : ""}
    <img src="${photo.thumb || photo.preview}" alt="${safeName}" loading="lazy">
    <button class="card-quick-download" title="ดาวน์โหลดรูปนี้ทันที" onclick="event.stopPropagation(); triggerFileDownload('${photo.finished}', '${photo.filename}')">
      ↓
    </button>
    <div class="photo-select-mark" aria-hidden="true">✓</div>
  `;

  card.onclick = () => {
    if (selectionMode) {
      togglePhotoSelection(photo.id, card);
    } else {
      const idx = galleryPhotos.findIndex(item => item.id === photo.id);
      openLightbox(idx);
    }
  };

  return card;
}

function setPhotoFilter(filter) {
  currentFilter = filter;
  document.querySelector("#filterAll")?.classList.toggle("active", filter === "all");
  document.querySelector("#filterRecent")?.classList.toggle("active", filter === "recent");

  const cards = document.querySelectorAll(".photo-card");
  cards.forEach(card => {
    if (filter === "recent") {
      card.style.display = card.dataset.recent === "true" ? "block" : "none";
    } else {
      card.style.display = "block";
    }
  });
}

function updateRecentCount() {
  const recentPhotos = galleryPhotos.filter(p => p.isRecent);
  const countBadge = document.querySelector("#recentCount");
  if (countBadge) {
    if (recentPhotos.length > 0) {
      countBadge.textContent = recentPhotos.length;
      countBadge.style.display = "inline-block";
    } else {
      countBadge.style.display = "none";
    }
  }
}

// -------------------------------------------------------------------------
// SELECTION MODE & DOCK
// -------------------------------------------------------------------------

function toggleSelectionMode() {
  selectionMode = !selectionMode;
  if (!selectionMode) selectedPhotoIds.clear();

  const normalDock = document.querySelector("#normalDock");
  const selectionDock = document.querySelector("#selectionDock");
  const selectModeBtn = document.querySelector("#selectModeBtn");

  if (normalDock) normalDock.style.display = selectionMode ? "none" : "flex";
  if (selectionDock) selectionDock.style.display = selectionMode ? "flex" : "none";

  if (selectModeBtn) {
    selectModeBtn.classList.toggle("active", selectionMode);
    selectModeBtn.innerHTML = selectionMode 
      ? `<span class="btn-icon">✕</span> ยกเลิกการเลือก` 
      : `<span class="btn-icon">✓</span> เลือกหลายรูป`;
  }

  document.querySelectorAll(".photo-card").forEach(card => {
    const isSelected = selectedPhotoIds.has(card.dataset.id);
    card.classList.toggle("selected", isSelected);
  });

  updateSelectionControls();
}

function togglePhotoSelection(photoId, card) {
  if (selectedPhotoIds.has(photoId)) {
    selectedPhotoIds.delete(photoId);
    card.classList.remove("selected");
  } else {
    selectedPhotoIds.add(photoId);
    card.classList.add("selected");
  }
  updateSelectionControls();
}

function updateSelectionControls() {
  const count = selectedPhotoIds.size;
  const countLabel = document.querySelector("#selectedCount");
  const downloadButton = document.querySelector("#downloadSelectedBtn");

  if (countLabel) countLabel.textContent = `เลือก ${count} รูป`;
  if (downloadButton) {
    downloadButton.disabled = count === 0;
    downloadButton.innerHTML = `<span class="btn-icon">↓</span> ดาวน์โหลด ${count} รูป`;
  }
}

function downloadSelectedPhotos() {
  const photos = [...selectedPhotoIds];
  if (!photos.length) return;

  if (photos.length === 1) {
    const photo = galleryPhotos.find(item => item.id === photos[0]);
    if (photo) triggerFileDownload(photo.finished, photo.filename);
    return;
  }

  if (photos.length > 40) {
    showToast("สามารถเลือกดาวน์โหลดได้ครั้งละไม่เกิน 40 รูป", "info");
    return;
  }

  showToast(`กำลังเตรียมไฟล์ ZIP ${photos.length} รูป...`, "info");
  const url = new URL(`${API}/api/gallery/${publicId}/downloads.zip`);
  photos.forEach(id => url.searchParams.append("photo_id", id));

  fetch(url, { credentials: "include" })
    .then(async response => {
      if (!response.ok) throw new Error("ดาวน์โหลดไม่สำเร็จ");
      const blob = await response.blob();
      const link = document.createElement("a");
      const objectUrl = URL.createObjectURL(blob);
      link.href = objectUrl;
      link.download = `${galleryMeta.eventName.replace(/\s+/g, "_")}_photos.zip`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
      showToast("ดาวน์โหลดไฟล์ ZIP เรียบร้อยแล้ว", "success");
    })
    .catch(err => {
      console.error(err);
      showToast("ดาวน์โหลดไฟล์ ZIP ไม่สำเร็จ", "error");
    });
}

function triggerFileDownload(url, filename) {
  showToast("กำลังดาวน์โหลดรูปภาพ...", "info");
  fetchDownload(url, filename || "csbxxm-photo.jpg")
    .then(() => showToast("บันทึกรูปภาพเรียบร้อยแล้ว", "success"))
    .catch(err => showToast(err.message || "เกิดข้อผิดพลาดในการดาวน์โหลด", "error"));
}

// -------------------------------------------------------------------------
// LIGHTBOX & MOBILE SHARING
// -------------------------------------------------------------------------

function openLightbox(index) {
  const photo = galleryPhotos[index];
  if (!photo) return;
  currentPhotoIndex = index;

  const modal = document.querySelector("#lightbox");
  const safeName = escapeHtml(photo.filename);
  const position = `${index + 1} / ${galleryPhotos.length}`;

  modal.innerHTML = `
    <div class="lightbox-content">
      <div class="lightbox-header">
        <div class="lightbox-title-box">
          <span class="lightbox-title">${safeName}</span>
          <span class="lightbox-counter">${position}</span>
          <span class="hd-badge">HD</span>
        </div>
        <button class="btn btn-ghost" onclick="closeLightbox()">ปิด ✕</button>
      </div>

      <div class="lightbox-stage">
        <button class="stage-nav prev" onclick="moveLightbox(-1)" aria-label="รูปก่อนหน้า">‹</button>
        <img src="${photo.preview}" alt="${safeName}">
        <button class="stage-nav next" onclick="moveLightbox(1)" aria-label="รูปถัดไป">›</button>
      </div>

      <div class="lightbox-actions">
        <button class="btn btn-primary" onclick="triggerFileDownload('${photo.finished}', '${photo.filename}')">
          <span class="btn-icon">↓</span> บันทึกรูปภาพนี้
        </button>
        <button class="btn btn-secondary" onclick="sharePhotoNative(${index})">
          <span class="btn-icon">↗</span> แชร์รูปนี้ (LINE / IG)
        </button>
      </div>
    </div>
  `;

  modal.classList.add("open");
  document.body.style.overflow = "hidden";
}

async function sharePhotoNative(index) {
  const photo = galleryPhotos[index];
  if (!photo) return;

  if (navigator.share) {
    try {
      // Try sharing as file if supported
      const response = await fetch(photo.preview);
      const blob = await response.blob();
      const file = new File([blob], photo.filename, { type: blob.type });

      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share({
          files: [file],
          title: galleryMeta.eventName,
          text: `รูปถ่ายจากงาน ${galleryMeta.eventName} · CS.BXXM STUDIO`
        });
        return;
      }
    } catch (e) {
      console.warn("Share files failed, fallback to url", e);
    }

    try {
      await navigator.share({
        title: galleryMeta.eventName,
        text: `ดูรูปของฉันจากงาน ${galleryMeta.eventName}:`,
        url: photo.finished || galleryUrl
      });
    } catch (e) {
      // User cancelled
    }
  } else {
    copyShareText();
  }
}

function closeLightbox() {
  const modal = document.querySelector("#lightbox");
  if (modal) modal.classList.remove("open");
  currentPhotoIndex = -1;
  document.body.style.overflow = "";
}

function moveLightbox(delta) {
  if (!galleryPhotos.length || currentPhotoIndex < 0) return;
  const next = (currentPhotoIndex + delta + galleryPhotos.length) % galleryPhotos.length;
  openLightbox(next);
}

// -------------------------------------------------------------------------
// PRIVATE GALLERY PIN
// -------------------------------------------------------------------------

async function unlockGallery(ev) {
  ev.preventDefault();
  const pinInput = document.querySelector("#galleryPin");
  const pin = pinInput ? pinInput.value.trim() : "";
  if (!pin) return;

  try {
    const response = await fetch(`${API}/api/gallery/${publicId}/unlock`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ pin })
    });

    if (pinInput) pinInput.value = "";

    if (!response.ok) {
      if (response.status === 429) {
        showToast("ใส่รหัสผิดหลายครั้ง กรุณารอสักครู่แล้วลองใหม่", "error");
      } else {
        showToast("รหัส PIN ไม่ถูกต้อง กรุณาลองใหม่", "error");
      }
      return;
    }

    showToast("ปลดล็อกแกลเลอรีสำเร็จ ยินดีต้อนรับครับ!", "success");
    await initGallery();
  } catch (err) {
    console.error(err);
    showToast("เกิดข้อผิดพลาดในการตรวจสอบรหัส", "error");
  }
}

// -------------------------------------------------------------------------
// EVENT LISTENERS & GESTURES
// -------------------------------------------------------------------------

document.addEventListener("visibilitychange", () => {
  if (!document.hidden && publicId) loadPhotos(false);
});

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
  if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.3) {
    moveLightbox(dx < 0 ? 1 : -1);
  }
}, { passive: true });
