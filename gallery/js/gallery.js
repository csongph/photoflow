/**
 * CS.BXXM STUDIO - Real-Time Photo Booth Gallery Script
 * High-performance mobile viewer, Web Share API, and 1-Tap Downloads.
 */

const params = new URLSearchParams(location.search);
const configuredApi = window.MOMENTLINK_API_URL || "";
const API = (params.get("api") || configuredApi || location.origin).replace(/\/$/, "");
const pathPublicId = location.pathname.split("/").filter(Boolean).pop() || "";
const publicId = params.get("event") || (pathPublicId === "gallery" || pathPublicId === "index.html" ? "" : pathPublicId);
const slideshowOnOpen = params.get("slideshow") === "1";

let knownPhotoCount = 0;
let loadingPhotos = false;
let galleryRefreshTimer = null;
let galleryRetryTimer = null;
let galleryInitializing = false;
let galleryInitialized = false;
let galleryRetryDelay = 3000;
let galleryUrl = location.href.split("#")[0];
let galleryMeta = {
  eventName: "CS.BXXM Gallery",
  creditText: "Photo Booth Experience by CS.BXXM STUDIO",
  reportContact: "",
  allowDownload: true
};

let galleryPhotos = [];
let currentFilter = "all"; // "all" | "recent"
let photoSearchQuery = "";
let photoTimeFilter = "all";
let currentPhotoIndex = -1;
let touchStartX = 0;
let touchStartY = 0;
let selectionMode = false;
const selectedPhotoIds = new Set();
const preparedFiles = new Map();
const preparingPhotoIds = new Set();
const failedPreparationIds = new Set();
const preparationControllers = new Map();
let fallbackObjectUrls = [];
const MAX_SHARE_SELECTION = 10;
let publicSlideshowState = null;
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

function freshDownloadUrl(url) {
  const result = new URL(url, API);
  result.searchParams.set("_download", `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`);
  return result.toString();
}

function isAppleMobileDevice() {
  return /iPhone|iPad|iPod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
}

// -------------------------------------------------------------------------
// INITIALIZATION
// -------------------------------------------------------------------------

async function initGallery() {
  if (galleryInitializing) return;
  if (!publicId) {
    const controls = document.querySelector(".gallery-controls");
    const shareCard = document.querySelector(".qr-share-card");
    const statusBar = document.querySelector(".bar-status");
    if (controls) controls.style.display = "none";
    if (shareCard) shareCard.style.display = "none";
    if (statusBar) statusBar.style.display = "none";
    const floatingQr = document.querySelector("#floatingGalleryQr");
    if (floatingQr) floatingQr.hidden = true;
    document.querySelector("#grid").innerHTML = `
      <div class="empty-gallery">
        <span class="empty-icon">📷</span>
        <h4>ยังไม่ได้ระบุ Gallery</h4>
        <p>กรุณาสแกน QR Code จากหน้างานโฟโต้บูทใหม่อีกครั้ง</p>
      </div>`;
    return;
  }

  galleryInitializing = true;
  clearTimeout(galleryRetryTimer);
  try {
    setupScreenQr();
    const meta = await getJson(`${API}/api/gallery/${publicId}`);
    
    // Page Title & Header
    const eventName = meta.event?.name || "CS.BXXM Gallery";
    document.title = `${eventName} · CS.BXXM STUDIO`;
    const eventTitleEl = document.querySelector("#eventTitle");
    if (eventTitleEl) eventTitleEl.textContent = eventName;
    
    galleryUrl = meta.event?.gallery_url || galleryUrl;
    galleryInitialized = true;
    galleryRetryDelay = 3000;
    const brandHome = document.querySelector("#brandHome");
    if (brandHome) brandHome.href = galleryUrl;

    // Gallery settings
    const s = meta.settings || {};
    galleryMeta = {
      eventName,
      creditText: s.credit_text || "Photo Booth Experience by CS.BXXM STUDIO",
      reportContact: s.report_contact || "",
      allowDownload: Boolean(s.allow_download)
    };

    renderGalleryInfo();

    const dateEl = document.querySelector("#eventDate");
    if (dateEl) dateEl.textContent = meta.event?.event_date || "LIVE PHOTO BOOTH";

    knownPhotoCount = meta.event?.photo_count || 0;
    updatePhotoCountUI(knownPhotoCount);

    const allowDl = s.allow_download && !s.locked;
    const dlBtn = document.querySelector("#downloadLinks");
    if (dlBtn) dlBtn.style.display = allowDl ? "inline-flex" : "none";
    const selectModeBtn = document.querySelector("#selectModeBtn");
    if (selectModeBtn) selectModeBtn.style.display = allowDl ? "inline-flex" : "none";

    const pinPanel = document.querySelector("#pinPanel");
    if (pinPanel) pinPanel.style.display = s.locked ? "flex" : "none";
    const floatingQr = document.querySelector("#floatingGalleryQr");
    if (floatingQr) floatingQr.hidden = Boolean(s.locked);

    if (!s.locked) {
      await loadPhotos(true);
      if (slideshowOnOpen) startEventSlideshow();
    }

    clearInterval(galleryRefreshTimer);
    if (!s.locked) {
      galleryRefreshTimer = setInterval(() => {
        if (!document.hidden) loadPhotos(false);
      }, 3000);
    }
  } catch (err) {
    console.error(err);
    document.querySelector("#grid").innerHTML = `
      <div class="empty-gallery">
        <span class="empty-icon">⚠️</span>
        <h4>ไม่สามารถเปิด Gallery ได้</h4>
        <p>กำลังลองเชื่อมต่อใหม่อัตโนมัติ…</p>
      </div>`;
    galleryRetryTimer = setTimeout(() => {
      galleryRetryTimer = null;
      initGallery();
    }, galleryRetryDelay);
    galleryRetryDelay = Math.min(galleryRetryDelay * 2, 30000);
  } finally {
    galleryInitializing = false;
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
  const floatingQr = document.querySelector("#floatingQrImage");
  if (floatingQr) floatingQr.src = qrUrl;
  const largeQr = document.querySelector("#largeQrImage");
  if (largeQr) largeQr.src = qrUrl;
}

function openGalleryQrDialog() {
  const dialog = document.querySelector("#galleryQrDialog");
  if (dialog && !dialog.open) dialog.showModal();
}

function closeGalleryQrDialog() {
  const dialog = document.querySelector("#galleryQrDialog");
  if (dialog?.open) dialog.close();
}

function renderGalleryInfo() {
  const creditEl = document.querySelector("#creditFooter");
  if (creditEl) creditEl.textContent = galleryMeta.creditText;

  const reportEl = document.querySelector("#reportFooter");
  const contactEl = document.querySelector("#contactOwner");
  const contactUrl = normalizeContactUrl(galleryMeta.reportContact);
  if (contactEl && contactUrl) {
    contactEl.href = contactUrl;
    contactEl.target = "_blank";
    contactEl.rel = "noopener noreferrer";
    contactEl.hidden = false;
  }
  if (reportEl) reportEl.textContent = galleryMeta.reportContact ? "ติดต่อฉันผ่านช่องทางด้านบนได้เลย" : "แชร์แกลเลอรีนี้ให้เพื่อน แล้วดาวน์โหลดรูปที่ชอบได้ทันที";
}

function normalizeContactUrl(value) {
  const contact = String(value || "").trim();
  if (!contact) return "";
  if (/^(https?:\/\/|mailto:|tel:)/i.test(contact)) return contact;
  if (/^[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}$/.test(contact)) return `mailto:${contact}`;
  if (/^\+?[\d\s().-]{7,}$/.test(contact)) return `tel:${contact.replace(/[^+\d]/g, "")}`;
  if (/^@?[\w.-]{2,}$/.test(contact)) {
    return contact.startsWith("@")
      ? `https://line.me/R/ti/p/~${encodeURIComponent(contact.slice(1))}`
      : `https://instagram.com/${contact}`;
  }
  return `https://line.me/R/ti/p/~${encodeURIComponent(contact)}`;
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

    // The API returns newest first. Keep that order in both the data model
    // and the DOM so customers see the latest event photos at the top.
    const addedPhotos = newPhotos.map(photo => {
      const thumb = photo.variants?.find(v => v.kind === "thumbnail")?.url || "";
      const preview = photo.variants?.find(v => v.kind === "preview")?.url || thumb;
      const finished = photo.variants?.find(v => v.kind === "finished")?.url || "";
      const isRecent = (Date.now() - sessionStartTime < 300000) || !isInitial;

      return {
        id: photo.id, 
        filename: photo.filename,
        createdAt: photo.created_at || "",
        thumb, 
        preview, 
        finished,
        download: `/api/gallery/${publicId}/photos/${photo.id}/download`,
        isRecent
      };
    });
    if (addedPhotos.length) {
      galleryPhotos = [...addedPhotos, ...galleryPhotos];
      [...addedPhotos].reverse().forEach(photo => grid.prepend(createPhotoCard(photo)));
    }

    knownPhotoCount = Math.max(knownPhotoCount, galleryPhotos.length);
    updatePhotoCountUI(knownPhotoCount);
    updateRecentCount();
    applyPhotoFilters();

    if (syncText) syncText.textContent = "LIVE SYNC";
    if (publicSlideshowState) {
      const currentIndex = galleryPhotos.findIndex(photo => photo.id === publicSlideshowState.photoId);
      if (currentIndex >= 0) publicSlideshowState.index = currentIndex;
      else showPublicSlideshowPhoto(publicSlideshowState.index);
    }
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
  card.dataset.filename = String(photo.filename || "").toLocaleLowerCase();
  card.dataset.createdAt = photo.createdAt || "";

  const safeName = escapeHtml(photo.filename);
  const timeLabel = formatGalleryPhotoTime(photo.createdAt);
  
  card.innerHTML = `
    ${photo.isRecent ? `<span class="photo-badge-new">NEW</span>` : ""}
    <img src="${photo.thumb || photo.preview}" alt="${safeName}" loading="lazy">
    ${timeLabel.short ? `<time class="photo-card-time" datetime="${escapeHtml(photo.createdAt)}" title="เพิ่มในแกลเลอรี: ${escapeHtml(timeLabel.full)}">${escapeHtml(timeLabel.short)}</time>` : ""}
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

function formatGalleryPhotoTime(value) {
  const date = new Date(value);
  if (!value || !Number.isFinite(date.getTime())) return { short: "", full: "" };
  const short = new Intl.DateTimeFormat("th-TH", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"
  }).format(date);
  const full = new Intl.DateTimeFormat("th-TH", {
    dateStyle: "long", timeStyle: "short"
  }).format(date);
  return { short, full };
}

function filterGalleryPhotos(value) {
  photoSearchQuery = String(value || "").trim().toLocaleLowerCase();
  applyPhotoFilters();
}

function clearGallerySearch() {
  const input = document.querySelector("#gallerySearch");
  if (input) input.value = "";
  photoSearchQuery = "";
  applyPhotoFilters();
  input?.focus();
}

function applyPhotoFilters() {
  const cards = [...document.querySelectorAll(".photo-card")];
  let visibleCount = 0;
  cards.forEach(card => {
    const matchesRecent = currentFilter !== "recent" || card.dataset.recent === "true";
    const matchesSearch = !photoSearchQuery || (card.dataset.filename || "").includes(photoSearchQuery);
    const photoTime = Date.parse(card.dataset.createdAt || "");
    let matchesTime = photoTimeFilter === "all";
    if (photoTimeFilter === "today") {
      const todayStart = new Date();
      todayStart.setHours(0, 0, 0, 0);
      matchesTime = Number.isFinite(photoTime) && photoTime >= todayStart.getTime() && photoTime <= Date.now();
    } else if (photoTimeFilter !== "all") {
      const limits = { "15m": 15 * 60 * 1000, "1h": 60 * 60 * 1000, "3h": 3 * 60 * 60 * 1000 };
      const duration = limits[photoTimeFilter];
      matchesTime = Number.isFinite(photoTime) && duration !== undefined && photoTime >= Date.now() - duration && photoTime <= Date.now();
    }
    const visible = matchesRecent && matchesSearch && matchesTime;
    card.style.display = visible ? "" : "none";
    if (visible) visibleCount += 1;
  });

  let empty = document.querySelector("#searchEmptyState");
  const hasActiveFilter = Boolean(photoSearchQuery) || photoTimeFilter !== "all" || currentFilter === "recent";
  if (hasActiveFilter && cards.length && visibleCount === 0) {
    if (!empty) {
      empty = document.createElement("div");
      empty.id = "searchEmptyState";
      empty.className = "search-empty";
      document.querySelector("#grid")?.appendChild(empty);
    }
    empty.textContent = photoSearchQuery ? "ไม่พบรูปที่ตรงกับชื่อไฟล์นี้" : "ไม่พบรูปในช่วงเวลาที่เลือก";
  } else {
    empty?.remove();
  }

  const status = document.querySelector("#searchStatus");
  if (status) status.textContent = hasActiveFilter
    ? "พบ " + visibleCount + " จาก " + cards.length + " รูป"
    : "";
}

function setPhotoTimeFilter(value) {
  photoTimeFilter = ["all", "15m", "1h", "3h", "today"].includes(value) ? value : "all";
  document.querySelector(".time-filter")?.classList.toggle("is-active", photoTimeFilter !== "all");
  applyPhotoFilters();
}

function setPhotoFilter(filter) {
  currentFilter = filter === "recent" ? "recent" : "all";
  document.querySelector("#filterAll")?.classList.toggle("active", currentFilter === "all");
  document.querySelector("#filterRecent")?.classList.toggle("active", currentFilter === "recent");
  applyPhotoFilters();
}

function startEventSlideshow() {
  if (!publicId) {
    showToast("ลิงก์นี้ยังไม่ได้เลือกแกลเลอรีของงาน", "error");
    return;
  }
  if (publicSlideshowState) return;
  const overlay = document.createElement("section");
  overlay.id = "publicSlideshow";
  overlay.className = "public-slideshow";
  overlay.innerHTML = `
    <div class="public-slideshow-stage" id="publicSlideshowStage">
      <img class="public-slideshow-image is-active" id="publicSlideshowImageA" alt="ภาพจากงาน">
      <img class="public-slideshow-image" id="publicSlideshowImageB" alt="ภาพจากงาน" aria-hidden="true">
      <div class="public-slideshow-empty" id="publicSlideshowEmpty">กำลังรอรูปภาพจากงานนี้…</div>
    </div>
    <header class="public-slideshow-heading"><span>CS.BXXM STUDIO</span><strong>${escapeHtml(galleryMeta.eventName)}</strong></header>
    <aside class="public-slideshow-qr"><img src="${escapeHtml(`${API}/api/gallery/${publicId}/qr.png`)}" alt="QR Code เปิดแกลเลอรีงานนี้"><b>สแกน QR Code เพื่อดาวน์โหลดรูปภาพ</b></aside>
    <div class="public-slideshow-controls" id="publicSlideshowControls">
      <button type="button" onclick="closeEventSlideshow()">กลับแกลเลอรี</button>
      <button type="button" onclick="togglePublicSlideshowPlayback()" id="publicSlideshowPlay">พักภาพ</button>
      <button type="button" onclick="stepPublicSlideshow(-1)" aria-label="ภาพก่อนหน้า">‹ ก่อนหน้า</button>
      <button type="button" onclick="stepPublicSlideshow(1)" aria-label="ภาพถัดไป">ถัดไป ›</button>
      <label>เปลี่ยนภาพ<select onchange="setPublicSlideshowTransition(this.value)"><option value="fade">Fade</option><option value="slide">Slide</option><option value="dissolve">Dissolve</option></select></label>
      <label>ความเร็ว<select onchange="setPublicSlideshowInterval(this.value)"><option value="4000">4 วินาที</option><option value="6000" selected>6 วินาที</option><option value="8000">8 วินาที</option><option value="10000">10 วินาที</option></select></label>
      <button type="button" onclick="togglePublicSlideshowFullscreen()">เต็มจอ</button>
    </div>
  `;
  document.body.appendChild(overlay);
  const floatingQr = document.querySelector("#floatingGalleryQr");
  if (floatingQr) floatingQr.hidden = true;
  document.body.classList.add("slideshow-is-open");
  const state = { index: 0, photoId: "", paused: false, transition: "fade", interval: 6000, slideTimer: null, hideTimer: null, sequence: 0, failedUrls: new Set() };
  publicSlideshowState = state;
  state.slideTimer = setInterval(() => { if (publicSlideshowState === state && !state.paused) stepPublicSlideshow(1); }, state.interval);
  const reveal = () => revealPublicSlideshowControls();
  overlay.addEventListener("pointermove", reveal, { passive: true });
  overlay.addEventListener("touchstart", reveal, { passive: true });
  let touchX = 0;
  let touchY = 0;
  overlay.addEventListener("touchstart", event => {
    touchX = event.changedTouches[0]?.clientX || 0;
    touchY = event.changedTouches[0]?.clientY || 0;
  }, { passive: true });
  overlay.addEventListener("touchend", event => {
    const dx = (event.changedTouches[0]?.clientX || touchX) - touchX;
    const dy = (event.changedTouches[0]?.clientY || touchY) - touchY;
    if (Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.3) stepPublicSlideshow(dx < 0 ? 1 : -1);
  }, { passive: true });
  overlay.addEventListener("click", event => {
    if (event.target.id === "publicSlideshowStage" || event.target.classList.contains("public-slideshow-image")) reveal();
  });
  if (galleryPhotos.length) showPublicSlideshowPhoto(0);
  reveal();
}

function revealPublicSlideshowControls() {
  if (!publicSlideshowState) return;
  const overlay = document.querySelector("#publicSlideshow");
  if (!overlay) return;
  overlay.classList.remove("controls-hidden");
  clearTimeout(publicSlideshowState.hideTimer);
  publicSlideshowState.hideTimer = setTimeout(() => overlay.classList.add("controls-hidden"), 3200);
}

function closeEventSlideshow() {
  if (publicSlideshowState) {
    clearInterval(publicSlideshowState.slideTimer);
    clearTimeout(publicSlideshowState.hideTimer);
    publicSlideshowState = null;
  }
  document.querySelector("#publicSlideshow")?.remove();
  document.body.classList.remove("slideshow-is-open");
  const floatingQr = document.querySelector("#floatingGalleryQr");
  if (floatingQr) floatingQr.hidden = false;
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  const url = new URL(location.href);
  url.searchParams.delete("slideshow");
  history.replaceState({}, "", url);
}

async function showPublicSlideshowPhoto(index) {
  if (!publicSlideshowState || !galleryPhotos.length) return;
  const state = publicSlideshowState;
  const sequence = ++state.sequence;
  let photo = null;
  let imageUrl = "";
  for (let offset = 0; offset < galleryPhotos.length; offset += 1) {
    const candidate = galleryPhotos[(index + offset + galleryPhotos.length) % galleryPhotos.length];
    const candidateUrl = candidate.preview || candidate.thumb;
    if (!candidateUrl || state.failedUrls.has(candidateUrl)) continue;
    const preload = new Image();
    preload.src = candidateUrl;
    try {
      await preload.decode();
      photo = candidate;
      imageUrl = candidateUrl;
      break;
    } catch {
      state.failedUrls.add(candidateUrl);
      console.warn("Skipping unavailable slideshow photo", candidate.id);
    }
  }
  if (publicSlideshowState !== state || state.sequence !== sequence) return;
  if (!photo) {
    const empty = document.querySelector("#publicSlideshowEmpty");
    if (empty) { empty.hidden = false; empty.textContent = "ยังไม่มีรูปภาพที่แสดงได้"; }
    return;
  }
  const stage = document.querySelector("#publicSlideshowStage");
  const active = stage?.querySelector(".public-slideshow-image.is-active");
  const next = active?.id === "publicSlideshowImageA" ? document.querySelector("#publicSlideshowImageB") : document.querySelector("#publicSlideshowImageA");
  if (!stage || !active || !next) return;
  next.src = imageUrl;
  next.alt = photo.filename || "ภาพจากงาน";
  next.dataset.photoId = photo.id;
  next.classList.add("is-active");
  active.classList.remove("is-active");
  stage.dataset.transition = state.transition;
  state.index = galleryPhotos.findIndex(item => item.id === photo.id);
  state.photoId = photo.id;
  const empty = document.querySelector("#publicSlideshowEmpty");
  if (empty) empty.hidden = true;
}

function stepPublicSlideshow(direction) {
  if (!publicSlideshowState || !galleryPhotos.length) return;
  showPublicSlideshowPhoto(publicSlideshowState.index + direction);
}

function togglePublicSlideshowPlayback() {
  if (!publicSlideshowState) return;
  publicSlideshowState.paused = !publicSlideshowState.paused;
  const button = document.querySelector("#publicSlideshowPlay");
  if (button) button.textContent = publicSlideshowState.paused ? "เล่นต่อ" : "พักภาพ";
}

function setPublicSlideshowTransition(value) {
  if (!publicSlideshowState || !["fade", "slide", "dissolve"].includes(value)) return;
  publicSlideshowState.transition = value;
  const stage = document.querySelector("#publicSlideshowStage");
  if (stage) stage.dataset.transition = value;
}

function setPublicSlideshowInterval(value) {
  if (!publicSlideshowState) return;
  const milliseconds = Number(value);
  if (![4000, 6000, 8000, 10000].includes(milliseconds)) return;
  const state = publicSlideshowState;
  clearInterval(state.slideTimer);
  state.interval = milliseconds;
  state.slideTimer = setInterval(() => { if (publicSlideshowState === state && !state.paused) stepPublicSlideshow(1); }, milliseconds);
}

async function togglePublicSlideshowFullscreen() {
  const screen = document.querySelector("#publicSlideshow");
  try {
    if (!document.fullscreenElement) await screen?.requestFullscreen();
    else await document.exitFullscreen();
  } catch (error) {
    showToast("กด F11 เพื่อขยายหน้าต่างเต็มจอ", "info");
  }
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
  if (!selectionMode) {
    preparationControllers.forEach(controller => controller.abort());
    preparationControllers.clear();
    preparingPhotoIds.clear();
    selectedPhotoIds.clear();
    preparedFiles.clear();
    failedPreparationIds.clear();
  }

  const normalDock = document.querySelector("#normalDock");
  const selectionDock = document.querySelector("#selectionDock");
  const selectModeBtn = document.querySelector("#selectModeBtn");

  if (normalDock) normalDock.style.display = selectionMode ? "none" : "flex";
  if (selectionDock) selectionDock.style.display = selectionMode ? "flex" : "none";

  if (selectModeBtn) {
    selectModeBtn.classList.toggle("active", selectionMode);
    selectModeBtn.innerHTML = selectionMode 
      ? `<span class="btn-icon">✕</span> ยกเลิกการเลือก` 
      : `<span class="btn-icon">✓</span> เลือกเพื่อบันทึก`;
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
    preparedFiles.delete(photoId);
    failedPreparationIds.delete(photoId);
    preparationControllers.get(photoId)?.abort();
    card.classList.remove("selected");
  } else {
    if (selectedPhotoIds.size >= MAX_SHARE_SELECTION) {
      showToast(`เลือกได้สูงสุด ${MAX_SHARE_SELECTION} รูปต่อครั้ง เพื่อบันทึกได้เสถียร`, "info");
      return;
    }
    selectedPhotoIds.add(photoId);
    card.classList.add("selected");
    if (isAppleMobileDevice()) prepareSelectedPhoto(photoId);
  }
  updateSelectionControls();
}

async function prepareSelectedPhoto(photoId) {
  const photo = galleryPhotos.find(item => item.id === photoId);
  if (!photo || preparedFiles.has(photoId) || preparingPhotoIds.has(photoId)) return;
  preparingPhotoIds.add(photoId);
  failedPreparationIds.delete(photoId);
  const controller = new AbortController();
  preparationControllers.set(photoId, controller);
  updateSelectionControls();
  try {
    const response = await fetch(freshDownloadUrl(photo.download), { credentials: "include", cache: "no-store", signal: controller.signal });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const blob = await response.blob();
    if (!blob.type.startsWith("image/") || !blob.size || blob.size > 40 * 1024 * 1024) throw new Error("ไฟล์รูปใหญ่เกินไปหรือไม่ใช่รูปภาพ");
    if (selectedPhotoIds.has(photoId)) preparedFiles.set(photoId, new File([blob], photo.filename, { type: blob.type }));
  } catch (error) {
    if (error.name !== "AbortError") {
      console.error("Unable to prepare selected photo", photoId, error);
      if (selectedPhotoIds.has(photoId)) failedPreparationIds.add(photoId);
    }
  } finally {
    if (preparationControllers.get(photoId) === controller) preparationControllers.delete(photoId);
    preparingPhotoIds.delete(photoId);
    updateSelectionControls();
  }
}

function selectAllPhotos() {
  if (!selectionMode) toggleSelectionMode();
  const cards = [...document.querySelectorAll(".photo-card")];
  const visibleCards = cards.filter(card => card.offsetParent !== null);
  const available = visibleCards.filter(card => !selectedPhotoIds.has(card.dataset.id));
  const room = MAX_SHARE_SELECTION - selectedPhotoIds.size;
  for (const card of available.slice(0, room)) {
    selectedPhotoIds.add(card.dataset.id);
    card.classList.add("selected");
    if (isAppleMobileDevice()) prepareSelectedPhoto(card.dataset.id);
  }
  if (available.length > room) showToast(`เลือกเพิ่มได้ ${room} รูป · สูงสุด ${MAX_SHARE_SELECTION} รูปต่อครั้ง`, "info");
  updateSelectionControls();
}

function clearPhotoSelection() {
  preparationControllers.forEach(controller => controller.abort());
  preparationControllers.clear();
  preparingPhotoIds.clear();
  selectedPhotoIds.clear();
  preparedFiles.clear();
  failedPreparationIds.clear();
  document.querySelectorAll(".photo-card.selected").forEach(card => card.classList.remove("selected"));
  updateSelectionControls();
}

function updateSelectionControls() {
  const count = selectedPhotoIds.size;
  const ready = [...selectedPhotoIds].filter(id => preparedFiles.has(id)).length;
  const preparing = [...selectedPhotoIds].filter(id => preparingPhotoIds.has(id)).length;
  const failed = [...selectedPhotoIds].filter(id => failedPreparationIds.has(id)).length;
  const needsPreparedFiles = isAppleMobileDevice();
  const countLabel = document.querySelector("#selectedCount");
  const downloadButton = document.querySelector("#downloadSelectedBtn");

  if (countLabel) countLabel.textContent = preparing ? `เตรียมรูป ${ready}/${count}` : `เลือก ${count} รูป`;
  if (downloadButton) {
    downloadButton.disabled = count === 0 || (needsPreparedFiles && (preparing > 0 || (ready !== count && failed === 0)));
    const readyLabel = needsPreparedFiles ? `บันทึกลง Photos ${count} รูป` : `ดาวน์โหลด ${count} รูป`;
    downloadButton.innerHTML = `<span class="btn-icon">${preparing ? "…" : "↓"}</span> ${preparing ? `เตรียมรูป ${ready}/${count}` : failed ? `ดาวน์โหลดแยก ${count} รูป` : readyLabel}`;
  }
}

function downloadSelectedPhotos(event) {
  event.preventDefault();
  const photos = [...selectedPhotoIds];
  if (!photos.length) return;
  if (!isAppleMobileDevice()) {
    showDownloadFallback(photos, true);
    return;
  }
  if (photos.some(id => !preparedFiles.has(id))) {
    showDownloadFallback(photos);
    return;
  }
  const files = photos.map(id => preparedFiles.get(id)).filter(Boolean);
  if (!files.length || files.length !== photos.length) {
    showDownloadFallback(photos);
    return;
  }
  if (navigator.share && navigator.canShare?.({ files })) {
    showToast("ในเมนูแชร์ เลือก Photos หรือ Gallery เพื่อบันทึกรูป", "info");
    navigator.share({ files, title: galleryMeta.eventName, text: `รูปจากงาน ${galleryMeta.eventName}` })
      .then(() => showToast("ส่งรูปไปยังแอปที่เลือกแล้ว", "success"))
      .catch(error => {
        if (error.name !== "AbortError") {
          console.error("Share sheet failed", error);
          showDownloadFallback(photos, true);
        }
      });
    return;
  }
  showDownloadFallback(photos, true);
}

function showDownloadFallback(photoIds, startDownloads = false) {
  const dialog = document.querySelector("#downloadFallbackDialog");
  const list = document.querySelector("#downloadFallbackLinks");
  if (!dialog || !list) return;
  fallbackObjectUrls.forEach(url => URL.revokeObjectURL(url));
  fallbackObjectUrls = [];
  const availableIds = photoIds.filter(id => galleryPhotos.some(item => item.id === id));
  list.innerHTML = availableIds.map(id => {
    const photo = galleryPhotos.find(item => item.id === id);
    if (!photo) return "";
    const file = preparedFiles.get(id);
    const preparedUrl = file ? URL.createObjectURL(file) : "";
    if (preparedUrl) fallbackObjectUrls.push(preparedUrl);
    const href = preparedUrl || freshDownloadUrl(photo.download);
    return `<a class="btn btn-primary download-fallback-link" href="${escapeHtml(href)}" download="${escapeHtml(photo.filename)}" rel="noopener"><span>↓</span>${escapeHtml(photo.filename)}</a>`;
  }).join("");
  if (!dialog.open) dialog.showModal();
  const message = document.querySelector("#downloadFallbackMessage");
  if (message) message.textContent = isAppleMobileDevice()
    ? "หากส่งหลายรูปไม่สำเร็จ ให้ลองเลือกรูปจำนวนน้อยลงแล้วกดบันทึกอีกครั้ง หากยังไม่ได้ แตะชื่อไฟล์เพื่อดาวน์โหลดแยก"
    : startDownloads
      ? "กำลังดาวน์โหลดรูปแยกไฟล์ลงโฟลเดอร์ Downloads หากเบราว์เซอร์ถาม ให้กดยืนยันอนุญาตดาวน์โหลดหลายไฟล์ หากถูกบล็อกให้แตะชื่อไฟล์ทีละรูป"
      : "แตะชื่อรูปเพื่อดาวน์โหลดแยกไฟล์ ระบบไม่สามารถยืนยันการบันทึกลงเครื่องแทนเบราว์เซอร์ได้";
  if (startDownloads) {
    window.setTimeout(() => {
      if (!dialog.open) return;
      list.querySelectorAll("a").forEach((link, index) => {
        window.setTimeout(() => link.click(), index * 700);
      });
    }, 150);
    showToast("กำลังเริ่มดาวน์โหลดรูปแยกไฟล์ หากเบราว์เซอร์บล็อก ให้แตะชื่อรูปในรายการ", "info");
  } else {
    showToast("แตะชื่อรูปเพื่อดาวน์โหลดแยกไฟล์", "info");
  }
}

document.querySelector("#downloadFallbackDialog")?.addEventListener("close", () => {
  fallbackObjectUrls.forEach(url => URL.revokeObjectURL(url));
  fallbackObjectUrls = [];
});

// -------------------------------------------------------------------------
// LIGHTBOX VIEW
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

      ${galleryMeta.allowDownload ? `<div class="lightbox-actions"><button type="button" class="btn btn-primary" id="selectExpandedPhoto"><span class="btn-icon">✓</span> เลือกรูปเพื่อบันทึก</button></div>` : ""}
    </div>
  `;

  modal.querySelector("#selectExpandedPhoto")?.addEventListener("click", () => selectPhotoForSaving(photo.id));
  modal.classList.add("open");
  document.body.style.overflow = "hidden";
}

function selectPhotoForSaving(photoId) {
  closeLightbox();
  if (!selectionMode) toggleSelectionMode();
  const card = [...document.querySelectorAll(".photo-card")].find(item => item.dataset.id === photoId);
  if (card && !selectedPhotoIds.has(photoId)) togglePhotoSelection(photoId, card);
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
  if (!document.hidden && publicId) {
    if (galleryInitialized) loadPhotos(false);
    else initGallery();
  }
});

document.addEventListener("keydown", ev => {
  if (publicSlideshowState) {
    if (ev.target instanceof HTMLElement && /^(INPUT|SELECT|TEXTAREA|BUTTON)$/.test(ev.target.tagName)) return;
    if (ev.key === "ArrowLeft") { stepPublicSlideshow(-1); revealPublicSlideshowControls(); }
    else if (ev.key === "ArrowRight") { stepPublicSlideshow(1); revealPublicSlideshowControls(); }
    else if (ev.code === "Space") { ev.preventDefault(); togglePublicSlideshowPlayback(); revealPublicSlideshowControls(); }
    else if (ev.key === "Escape") closeEventSlideshow();
    return;
  }
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
