# รายงานตรวจสอบ MomentLink V1

วันที่ตรวจสอบ: 2026-08-24

## ทำงานครบแล้ว

- Local FastAPI startup, static frontend routing, SQLite initialization และ system preset seeding ทำงานแล้ว
- Create Event สร้าง UUID, sanitize event folder, สร้าง directory structure, database row, `event.json`, gallery public ID, QR PNG และ INCOMING path
- Local watcher รองรับไฟล์ภาพที่ support: stable check, checksum, duplicate detection, preserve original, register job และส่งเข้า processing queue
- Processing pipeline สำหรับ JPEG/PNG/TIFF: decode, EXIF transpose, guarded auto correction, preset, finished JPEG, preview และ thumbnail
- System presets ครบ: Neutral, Event Natural, Indoor Clean, Outdoor Portrait, Studio Portrait, Stage / Concert, Warm Portrait, Clean Skin
- XMP import parser มี partial-support warning สำหรับ Lightroom/Adobe feature ที่ยังไม่รองรับ
- Diagnostics API และ UI แสดง required/optional checks, queues, Google Drive credential state และ safe system test
- Error recovery UI สำหรับ failed jobs พร้อม retry และ retry-all
- QR actions: show, save PNG, copy link และ print
- Local smoke E2E: create event, start, simulate photo, preserve original, create finished/preview/thumbnail ผ่านแล้ว
- Stress test 50 รูป: captured 50, processed 50, originals 50, failed jobs 0 หลัง harden upload queue

## ทำงานบางส่วน

- Upload queue จะเก็บ variants เป็น `READY_TO_UPLOAD` เมื่อ storage ยังไม่ configured ส่วน Google Drive upload/resume จริงต้องมี credentials และ provider implementation เพิ่ม
- Settings UI เก็บ operator settings ได้ แต่บาง runtime settings ยังต้อง restart หรือใช้ `.env`
- Public gallery static app มี grid/lightbox/find-my-photos request flow แต่ cloud API ยังไม่ได้ส่ง variant URLs ครบ
- Cloud sync endpoints มี contract สำหรับ event/photo แต่ยังต้อง verify กับ PostgreSQL deployment จริงและ idempotency แบบครบถ้วน
- Face search มี consent และ upload validation ใน cloud API แต่ embedding/vector matching จริงยังไม่พร้อมใน V1 local

## เสียหรือมีปัญหา

- หลังแก้รอบนี้ยังไม่พบ P0/P1 defect ฝั่ง local capture
- Cloud test ถูก skip ใน local run เพราะ PostgreSQL/psycopg เป็น external setup requirement

## ยังขาด

- Google Drive OAuth connect/disconnect/refresh/upload implementation แบบใช้งานจริง
- Full local-to-cloud upload provider implementation
- Real face detection embeddings/vector index/search results
- Browser/mobile visual QA สำหรับ public gallery ที่ deploy จริง
- RAW+JPEG pairing behavior นอกเหนือจากการ preserve RAW และแจ้งสถานะ

## ยังไม่ได้เชื่อมต่อ

- Local upload processing ยังไม่ได้เรียก Google Drive provider ที่ configured จริง
- Cloud gallery endpoint `/api/gallery/{public_id}/photos` ยังไม่คืน `PhotoVariant` URLs ครบ
- Find My Photos UI เรียก cloud endpoint ได้ แต่ backend ยังตอบเป็น pending/manual-configuration response ไม่ใช่ผล match จริง

## ต้องตั้งค่า Credential เอง

- Google OAuth client ID/secret และ redirect URI
- Cloud API URL/deployment
- PostgreSQL `DATABASE_URL` สำหรับ cloud
- Public gallery base URL/domain

## ต้องทดสอบกับ Hardware จริง

- Windows notebook พร้อม tether software
- กล้อง Canon/กล้องจริงและ tether destination behavior
- Sequential capture burst จาก tether software จริง
- RAW+JPEG tether pairing
- Internet disconnect/reconnect ระหว่างถ่ายจริง

## สิ่งที่แก้ในรอบนี้

- ป้องกัน capture ชื่อซ้ำ overwrite original เดิม
- เพิ่ม watcher in-process de-duplication สำหรับ create/modify event storm
- แก้ upload job payload ให้มี persisted upload ID จริง
- เพิ่ม in-process SQLite job claim lock เพื่อกัน worker สองตัว claim job เดียวกัน
- เปลี่ยน unconfigured storage จาก retry/fail storm เป็น persistent `READY_TO_UPLOAD`
- เพิ่ม isolated test database เพื่อไม่ให้ test pollute local operator DB
- เพิ่ม diagnostics page/API, failed-job UI actions, End Event, Open Folder, QR copy/print
- เพิ่ม `tools/e2e_smoke.py`, `tools/stress_test.py`, `test_all.bat` และ pytest markers
