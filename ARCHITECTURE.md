# สถาปัตยกรรม MomentLink V1

## Local Application

`local.app.main` คือ FastAPI process เดียวที่ทำหน้าที่:

- Serve UI ด้วย HTML/CSS/JS ปกติ
- เก็บ local state ใน SQLite
- Watch โฟลเดอร์ `INCOMING` ของ event ด้วย watchdog
- รอให้ไฟล์นิ่งก่อนอ่าน เพื่อไม่ process ไฟล์ที่ copy ยังไม่เสร็จ
- Copy capture ไปเก็บเป็น immutable original ใน `ORIGINAL`
- Deduplicate ด้วย SHA-256
- Persist jobs ใน SQLite
- Process รูปด้วย bounded workers
- Export thumbnail, preview และ finished JPEG
- Queue งาน upload/publish/face-index
- Recover processing jobs หลัง restart

## โฟลเดอร์ของ Event

```text
events/<event>_<id>/
  INCOMING/
  ORIGINAL/
  PROCESSING/
  FINISHED/
  THUMBNAILS/
  PREVIEWS/
  FAILED/
  CACHE/
  event.json
```

## Local Database

- `events`: config และ path ของ event
- `photos`: metadata ของ capture, path, status และ storage object IDs
- `jobs`: persistent queue พร้อม state และ retry timing
- `presets`: system/user presets
- `uploads`: upload queue และ provider state
- `settings`: local settings
- `sync_state`: marker สำหรับ cloud sync

## API Routes

Local:

- `GET /api/dashboard`
- `GET /api/diagnostics`
- `POST /api/diagnostics/system-test`
- `GET /api/events`
- `POST /api/events`
- `POST /api/events/{event_id}/start`
- `POST /api/events/{event_id}/end`
- `POST /api/events/{event_id}/open-folder`
- `POST /api/events/{event_id}/pause-publishing`
- `GET /api/events/{event_id}/photos`
- `GET /api/events/{event_id}/failed-jobs`
- `POST /api/events/{event_id}/failed-jobs/{job_id}/retry`
- `POST /api/events/{event_id}/failed-jobs/retry-all`
- `GET /api/events/{event_id}/qr.png`
- `GET /api/presets`
- `POST /api/presets/import-xmp`
- `GET/POST /api/settings`

Cloud:

- `POST /api/sync/event`
- `POST /api/sync/photo`
- `GET /api/gallery/{public_id}`
- `GET /api/gallery/{public_id}/photos`

## Security Notes

- ไม่มี secrets ใน frontend
- Gallery IDs เป็น random URL-safe tokens
- Local media serving ตรวจ event, variant, filename และ resolved path
- Original files ไม่ถูก process in-place
- Same-named captures จะถูกเปลี่ยนชื่อปลายทางเพื่อไม่ overwrite original เดิม

## Abstractions ที่เตรียมไว้

- `StorageProvider` รองรับ Google Drive ใน V1 และสามารถต่อยอดเป็น provider อื่นในอนาคต
- `FaceEngine` และ `FaceVectorStore` ยังต้องขยายก่อนใช้ production face search
- Gallery metadata ใช้ generic storage object IDs ไม่ผูก business logic กับ Google Drive โดยตรง
