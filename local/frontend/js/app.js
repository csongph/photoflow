const $ = (q) => document.querySelector(q);
const jsArg = (value) => JSON.stringify(String(value ?? ""));
const html = (value) => String(value ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[ch]));
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
    <div class="brand"><span>MomentLink</span><small>V1 Local</small></div>
    <a class="${active === "dashboard" ? "active" : ""}" href="/">Dashboard</a>
    <a class="${active === "setup" ? "active" : ""}" href="/setup">Setup</a>
    <a class="${active === "events" ? "active" : ""}" href="/events">Events</a>
    <a class="${active === "gallery" ? "active" : ""}" href="/gallery/local-preview">Guest Preview</a>
    <a class="${active === "archive" ? "active" : ""}" href="/archive">Archive</a>
    <a class="${active === "diagnostics" ? "active" : ""}" href="/diagnostics">System Check</a>
    <a class="${active === "settings" ? "active" : ""}" href="/settings">Settings</a>
    <a href="#" onclick="logoutAdmin(event)">Logout</a>
  </aside>`;
}

async function logoutAdmin(ev) {
  ev.preventDefault();
  await fetch("/api/auth/logout", { method: "POST" });
  location.href = "/login";
}

function layout(active, content) {
  document.body.innerHTML = `<div class="shell">${nav(active)}<main class="main">${content}</main></div>`;
}

async function loadDashboard() {
  layout("dashboard", `<div class="top hero-panel"><div><p class="kicker">Live Capture Console</p><h1>MomentLink</h1><p class="hero-note">ควบคุมงานถ่ายภาพ ดู queue จริง และเปิดแกลเลอรีให้แขกทดสอบได้จากจุดเดียว</p></div><div class="row hero-actions-admin"><a class="button secondary" href="/setup">Setup Check</a><button class="secondary" onclick="loadDashboard()">Refresh</button><div class="status pill"><span class="dot"></span><span id="live">Loading</span></div></div></div>
  <div class="grid">
    <section class="panel span-8 main-card"><h2>Active Event</h2><div id="active"></div></section>
    <section class="panel span-4"><h2>Health Monitor</h2><div id="health"></div></section>
    <section class="panel span-12"><h2>Preflight</h2><div id="preflight"></div></section>
    <section class="panel span-7"><h2>Latest Photos</h2><div class="thumbs" id="thumbs"></div></section>
    <section class="panel span-5"><h2>Export Queues</h2><div id="queues"></div></section>
  </div>`);
  const data = await api("/api/dashboard");
  if (!data.active_event) {
    $("#live").textContent = "No active event";
    $("#active").innerHTML = `<p class="muted">Create an event to begin.</p><a class="button" href="/events">Create Event</a>`;
    return;
  }
  $("#live").textContent = data.active_event.status;
  const c = data.counts;
  const metricLabels = { captured: "เข้าระบบ", processed: "พร้อมแสดง", uploaded: "อัปโหลด", published: "เผยแพร่", review: "รอตรวจ", queue: "คิวรอ", failed: "ผิดพลาด" };
  $("#active").innerHTML = `<div class="event-title"><h1>${data.active_event.name}</h1><span class="status pill"><span class="dot"></span>${data.active_event.status}</span></div>
    <div class="metrics">
      ${["captured","processed","uploaded","published","review","queue","failed"].map(k => `<div class="metric"><span class="muted">${metricLabels[k]}</span><b>${c[k] ?? 0}</b></div>`).join("")}
    </div>
    <p class="muted">INCOMING Folder</p><div class="pathbox">${data.active_event.incoming_path}</div>
    <div class="row" style="margin-top:14px">
      <button onclick="navigator.clipboard.writeText('${data.active_event.incoming_path.replaceAll("\\", "\\\\")}')">Copy Path</button>
      <button class="secondary" onclick="openFolder('${data.active_event.id}')">Open Folder</button>
      <button class="secondary" onclick="showQr('${data.active_event.id}', '${data.active_event.gallery_url}')">Show QR</button>
      <button class="secondary" onclick="shareGallery('${data.active_event.gallery_url}', '${data.active_event.name}')">Share Gallery</button>
      <button class="secondary" onclick="simulate('${data.active_event.id}')">Simulate Photo</button>
      <button class="secondary" onclick="rebuildPhotos('${data.active_event.id}')">Rebuild Gallery Files</button>
      <button class="warn" onclick="pause('${data.active_event.id}')">${data.active_event.publishing_paused ? "Resume Publishing" : "Pause Publishing"}</button>
      <button class="bad" onclick="endEvent('${data.active_event.id}')">End Event</button>
      <button class="bad" onclick='deleteEvent(${jsArg(data.active_event.id)}, ${jsArg(data.active_event.name)}, true, "dashboard")'>Delete Event</button>
    </div><div id="qrslot"></div>`;
  $("#health").innerHTML = Object.entries(data.health).map(([k,v]) => `<div class="queue-line"><span>${k}</span><b>${v}</b></div>`).join("");
  $("#queues").innerHTML = Object.entries(data.queues).map(([k,v]) => `<div class="queue-line"><span>${k}</span><b>${v}</b></div>`).join("") + `<div id="failedJobs"></div>`;
  $("#thumbs").innerHTML = data.latest_photos.length ? data.latest_photos.map(p => `<div class="thumb">${p.thumb ? `<img src="${p.thumb}" alt="${html(p.filename)}">` : html(p.status)}<span class="thumb-status ${p.published && !p.hidden ? "ok" : p.hidden ? "bad" : ""}">${html(p.hidden ? "HIDDEN" : p.status)}</span></div>`).join("") : `<div class="thumb">No photos yet</div>`;
  loadPreflight(data.active_event.id);
  loadFailedJobs(data.active_event.id);
}

async function showQr(id, url) {
  $("#qrslot").innerHTML = `<div class="qr-card"><div><p class="kicker">Guest Gallery QR</p><h2>ให้แขกสแกนเพื่อเปิดแกลเลอรี</h2><p class="muted">ลิงก์นี้คือหน้าที่ผู้ใช้ปลายทางเห็นจริง ใช้ทดสอบบนมือถือหรือส่งให้ทีมงานลองดาวน์โหลดรูปได้</p><div class="pathbox">${url}</div><div class="row" style="margin-top:12px"><a class="button" href="${url}" target="_blank">Open Gallery</a><a class="button secondary" href="/api/events/${id}/qr.png" download>Save QR PNG</a><button class="secondary" onclick="navigator.clipboard.writeText('${url}')">Copy Link</button><button class="secondary" onclick="shareGallery('${url}', 'MomentLink Gallery')">Copy LINE Text</button><button class="secondary" onclick="window.print()">Print</button></div></div><img class="qr" src="/api/events/${id}/qr.png" alt="Gallery QR"></div>`;
}
async function loadPreflight(id) {
  const data = await api(`/api/events/${id}/preflight`);
  const driveFix = data.failed.some(c => c.key === "google_drive") ? `<div class="row" style="margin-top:12px"><a class="button secondary" href="/settings">Connect Google Drive</a><button class="secondary" onclick='disableDriveRequirement(${jsArg(id)})'>Start without Google Drive</button></div>` : "";
  $("#preflight").innerHTML = `<div class="preflight-grid">${data.checks.map(c => `<div class="preflight-item ${c.ok ? "ok" : "fail"}"><b>${c.ok ? "PASS" : "FIX"}</b><span>${checkLabels[c.key] || c.key.replaceAll("_"," ")}</span><small>${c.message}</small></div>`).join("")}</div>${driveFix}`;
}
async function shareGallery(url, name) {
  const text = `รูปภาพงาน ${name}\nเปิด Gallery และดาวน์โหลดรูปได้ที่:\n${url}`;
  await navigator.clipboard.writeText(text);
  alert("คัดลอกข้อความสำหรับส่ง LINE/กลุ่มโรงเรียนแล้ว");
}
async function simulate(id) { await api(`/api/events/${id}/simulate-photo`, { method: "POST" }); setTimeout(loadDashboard, 1200); }
async function rebuildPhotos(id) {
  if (!confirm("สร้างไฟล์ Gallery ใหม่จาก ORIGINAL ทั้งหมด?")) return;
  const result = await api(`/api/events/${id}/photos/reprocess`, { method: "POST" });
  alert(`Queued ${result.queued} photo(s) for rebuilding.`);
  loadDashboard();
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
  layout("events", `<div class="top hero-panel"><div><p class="kicker">Event Setup</p><h1>Create Event</h1></div></div>
  <div class="grid"><form id="eventForm" class="panel span-7">
    <label><span>Event Name</span><input name="name" required placeholder="Freshy 2026"></label>
    <label><span>Description</span><textarea name="description"></textarea></label>
    <label><span>Date</span><input name="event_date" type="date"></label>
    <div class="empty-state" style="min-height:auto;padding:18px;text-align:left;place-items:start"><b>ระบบไม่แต่งรูปอัตโนมัติ</b><br><span>รูปจะถูกสำรองเป็น ORIGINAL แล้ว export เป็น FINISHED/PREVIEW/THUMBNAIL สำหรับ Gallery และ Google Drive โดยไม่ปรับสีหรือแสง</span></div>
    <h2>Gallery</h2><div class="checks">${["enable_gallery","allow_download","find_my_photos"].map(k => `<label class="check"><input type="checkbox" name="${k}" checked>${k.replaceAll("_"," ")}</label>`).join("")}<label class="check"><input type="checkbox" name="instant_publish" checked disabled>auto publish</label></div>
    <label><span>Optional PIN</span><input name="optional_pin"></label>
    <label><span>Gallery Credit</span><input name="credit_text" value="ถ่ายภาพโดยทีมโสตโรงเรียน"></label>
    <label><span>Report Contact</span><input name="report_contact" placeholder="LINE @school-av หรืออีเมลทีมงาน"></label>
    <h2>Google Drive</h2><div class="checks"><label class="check"><input type="checkbox" name="upload_finished_photos" checked>Upload Finished Photos Before Gallery</label><label class="check"><input type="checkbox" name="upload_originals">Upload Originals</label></div>
    <button>Create Event</button>
  </form><section class="panel span-5"><div class="preview-head"><div><h2>Events</h2><p class="muted">ข้อมูลจากฐานข้อมูลและโฟลเดอร์งานจริงในเครื่อง</p></div><button type="button" class="secondary" onclick="loadImportableEvents()">Scan Local Folders</button></div><div id="eventsList"></div><div id="importableList"></div><div id="created"></div></section></div>`);
  $("#eventForm").addEventListener("submit", createEvent);
  renderEvents();
}

async function renderEvents() {
  const events = await api("/api/events");
  $("#eventsList").innerHTML = events.map(e => `<div class="queue-line"><span>${e.name}<br><small class="muted">${e.status}</small></span><span class="row"><button class="secondary" onclick='checkPreflightFromList(${jsArg(e.id)})'>Check</button><button onclick='startEvent(${jsArg(e.id)})'>Start</button><button class="bad" onclick='deleteEvent(${jsArg(e.id)}, ${jsArg(e.name)}, true, "events")'>Delete</button></span></div>`).join("") || `<div class="empty-state"><b>ยังไม่มีอีเวนต์ในฐานข้อมูล</b><br><span>กด Import Local Events เพื่อดึงงานจากโฟลเดอร์ในเครื่องกลับเข้าระบบ</span></div>`;
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
  alert(data.ok ? "Preflight ผ่าน พร้อมเริ่มงาน" : `ยังไม่พร้อม: ${data.failed.map(x => x.key).join(", ")}`);
}

async function createEvent(ev) {
  ev.preventDefault();
  const f = new FormData(ev.target);
  const checked = (k) => f.get(k) === "on";
  const payload = {
    name: f.get("name"), description: f.get("description"), event_date: f.get("event_date"),
    gallery: Object.assign(Object.fromEntries(["enable_gallery","allow_download","find_my_photos"].map(k => [k, checked(k)])), { instant_publish: true, review_before_publish: false, optional_pin: f.get("optional_pin") || "", credit_text: f.get("credit_text") || "ถ่ายภาพโดยทีมโสตโรงเรียน", report_contact: f.get("report_contact") || "" }),
    drive: { upload_finished_photos: checked("upload_finished_photos"), upload_originals: checked("upload_originals") }
  };
  const event = await api("/api/events", { method: "POST", body: JSON.stringify(payload) });
  $("#created").innerHTML = `<hr><h2>INCOMING Folder</h2><div class="pathbox">${event.incoming_path}</div><div class="row" style="margin-top:14px"><button onclick="navigator.clipboard.writeText('${event.incoming_path.replaceAll("\\", "\\\\")}')">Copy Path</button><button onclick="startEvent('${event.id}')">Start Event</button></div>`;
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
      <label><span>Public Gallery Base URL</span><input name="public_gallery_base_url" value="${html(publicUrl)}" placeholder="https://photo.school.ac.th/gallery"></label>
      <div class="pathbox">ตัวอย่างลิงก์งาน: ${html((publicUrl || "https://your-domain.com/gallery").replace(/\/$/, ""))}/EVENT_ID</div>
      <p class="settings-hint">ทดสอบใน Wi-Fi ใช้ LAN IP ได้ แต่ใช้งานผ่านอินเทอร์เน็ตต้องเป็นโดเมนที่เปิดจากมือถือภายนอกได้</p>
    </section>

    <section class="panel settings-card span-5">
      <div class="settings-card-head"><div><p class="kicker">Downloads</p><h2>Google Drive</h2><p class="muted">ใช้เก็บไฟล์ finished สำหรับให้ผู้ใช้ดาวน์โหลดจริง</p></div><span class="status pill">${google.connected ? "CONNECTED" : "NOT CONNECTED"}</span></div>
      <label><span>Drive Root Folder</span><input name="drive_root" value="${html(google.root_folder || "MomentLink Events")}"></label>
      <div class="settings-list">
        <div><span>OAuth Config</span><b>${google.configured ? "READY" : "MISSING"}</b></div>
        <div><span>Ready Uploads</span><b>${google.ready_to_upload}</b></div>
        <div><span>Uploaded</span><b>${google.uploaded}</b></div>
      </div>
      <p class="muted">Redirect URI: ${html(google.redirect_uri || "not set")}</p>
      <div class="row"><a class="button" href="/api/google/connect">Connect</a><button type="button" class="secondary" onclick="retryGoogleUploads()">Retry Uploads</button><button type="button" class="bad" onclick="disconnectGoogle()">Disconnect</button></div>
      ${google.configured ? "" : `<p class="settings-hint badtext">ใส่ GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET และ GOOGLE_REDIRECT_URI ใน .env แล้ว restart MomentLink ก่อนเชื่อมต่อ</p>`}
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
  const name = prompt("ตั้งชื่อโฟลเดอร์ใหม่", "MomentLink Events");
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
  if (!confirm("Disconnect Google Drive from this local MomentLink?")) return;
  await api("/api/google/disconnect", { method: "POST" });
  loadSettings();
}

function loadGalleryPreview() {
  layout("gallery", `<div class="top hero-panel"><div><p class="kicker">Photo Review</p><h1>Gallery Control</h1><p class="hero-note">คัดรูปจากข้อมูลจริงในเครื่องก่อนให้แขกเห็น: publish, hide/show และ rebuild ไฟล์ Gallery ได้จากหน้านี้</p></div><div class="row hero-actions-admin"><a id="openGuest" class="button secondary" href="#">Open Guest Gallery</a><button class="secondary" onclick="loadGalleryPreview()">Refresh</button></div></div><section class="panel"><div class="preview-head"><div><h2>Guest Page Settings</h2><p class="muted">ข้อความเครดิตและช่องทางแจ้งปัญหาจะแสดงในฝั่งผู้ใช้</p></div></div><form id="guestSettingsForm" class="inline-form"><label><span>Gallery Credit</span><input name="credit_text"></label><label><span>Report Contact</span><input name="report_contact" placeholder="LINE @school-av หรืออีเมลทีมงาน"></label><button type="submit">Save Guest Text</button></form></section><section class="panel" style="margin-top:16px"><div class="preview-head"><div><h2>Review Queue</h2><p class="muted">รูปที่ Publish แล้วและไม่ถูกซ่อนเท่านั้นที่จะเห็นในฝั่งผู้ใช้</p></div><div class="row"><button id="publishAllBtn" type="button">Publish All Ready</button></div></div><div id="gallerySummary" class="review-summary"></div><div id="gallery" class="review-grid"></div></section>`);
  api("/api/dashboard").then(d => {
    if (!d.active_event) {
      $("#publishAllBtn").disabled = true;
      return { event: null, photos: [] };
    }
    $("#openGuest").href = d.active_event.gallery_url;
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
  form.credit_text.value = settings.credit_text || "";
  form.report_contact.value = settings.report_contact || "";
  form.onsubmit = async (ev) => {
    ev.preventDefault();
    await api(`/api/events/${eventId}/gallery-settings`, { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(form))) });
    alert("บันทึกข้อความฝั่งผู้ใช้แล้ว");
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
  $("#gallery").innerHTML = photos.map(p => photoReviewCard(event.id, p)).join("") || `<div class="empty-state"><b>ยังไม่มีรูปในระบบ</b><br><span>วางรูปจริงใน INCOMING หรือกด Simulate Photo แล้วรอ queue ประมวลผล</span></div>`;
}

function photoReviewCard(eventId, p) {
  const ready = p.thumbnail && p.preview;
  const visible = p.published && !p.hidden;
  const status = p.hidden ? "HIDDEN" : p.published ? "PUBLISHED" : p.status;
  const img = ready ? `<a href="${p.preview}" target="_blank"><img src="${p.thumbnail}" alt="${html(p.filename)}"></a>` : `<div class="review-placeholder">${html(p.status || "WAITING")}</div>`;
  const publish = ready && !visible ? `<button type="button" onclick='publishPhoto(${jsArg(eventId)}, ${jsArg(p.id)})'>Publish</button>` : "";
  const hideLabel = p.hidden ? "Show" : "Hide";
  const hide = ready ? `<button type="button" class="secondary" onclick='setPhotoHidden(${jsArg(eventId)}, ${jsArg(p.id)}, ${p.hidden ? "false" : "true"})'>${hideLabel}</button>` : "";
  const retry = `<button type="button" class="secondary" onclick='rebuildOnePhoto(${jsArg(eventId)}, ${jsArg(p.id)})'>Rebuild</button>`;
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
  layout("archive", `<div class="top hero-panel"><div><p class="kicker">School Archive</p><h1>Event Archive</h1><p class="hero-note">รวมประวัติงานถ่ายทั้งหมด ค้นงานเก่า เปิด Gallery และคัดลอกลิงก์ส่งต่อได้</p></div></div><section class="panel"><div class="preview-head"><div><h2>All Events</h2><p class="muted">แสดงงานทั้งหมดจากฐานข้อมูลในเครื่อง</p></div><button class="secondary" onclick="loadArchive()">Refresh</button></div><div id="archiveList"></div></section>`);
  const events = await api("/api/events");
  $("#archiveList").innerHTML = events.map(e => `<div class="queue-line"><span><b>${e.name}</b><br><small class="muted">${e.status} · ${e.root_path}</small></span><span class="row"><a class="button secondary" href="${e.gallery_url}" target="_blank">Gallery</a><button class="secondary" onclick='shareGallery(${jsArg(e.gallery_url)}, ${jsArg(e.name)})'>Share</button><button onclick='startEvent(${jsArg(e.id)})'>Start</button><button class="bad" onclick='deleteEvent(${jsArg(e.id)}, ${jsArg(e.name)}, true, "archive")'>Delete</button></span></div>`).join("") || `<p class="muted">ยังไม่มีงานใน Archive</p>`;
}

async function loadDiagnostics() {
  layout("diagnostics", `<div class="top hero-panel"><div><p class="kicker">Readiness</p><h1>Diagnostics</h1></div><button onclick="runSystemTest()">Run System Test</button></div><div class="grid"><section class="panel span-8"><h2>System Checks</h2><div id="checks"></div></section><section class="panel span-4"><h2>Queues</h2><div id="diagQueues"></div></section><section class="panel span-4"><h2>Real Database</h2><div id="diagDb"></div></section></div>`);
  const data = await api("/api/diagnostics");
  renderDiagnostics(data);
}
function renderDiagnostics(data) {
  $("#checks").innerHTML = Object.entries(data.checks).map(([k,v]) => {
    const label = k.replace(/^package_/, "package: ").replaceAll("_"," ");
    const tone = v.status === "FAIL" ? "badtext" : v.status === "WARN" ? "warntext" : v.status === "OPTIONAL" ? "optionaltext" : "";
    const required = v.required ? "Required" : "Optional";
    return `<div class="queue-line diag-line"><span><b>${label}</b><br><small class="muted">${html(v.message)}</small></span><span class="diag-status"><small>${required}</small><b class="${tone}">${v.status}</b></span></div>`;
  }).join("");
  $("#diagQueues").innerHTML = Object.entries(data.queues).map(([k,v]) => `<div class="queue-line"><span>${k.replaceAll("_"," ")}</span><b>${v}</b></div>`).join("");
  $("#diagDb").innerHTML = Object.entries(data.database || {}).map(([k,v]) => `<div class="queue-line"><span>${k.replaceAll("_"," ")}</span><b>${v}</b></div>`).join("");
}
async function runSystemTest() {
  const data = await api("/api/diagnostics/system-test", { method: "POST" });
  renderDiagnostics(data);
  alert(data.ok ? "System test passed required checks." : `Required checks failed: ${data.failed_required.join(", ")}`);
}
