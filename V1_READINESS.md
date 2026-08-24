# รายงานความพร้อม MomentLink V1

วันที่รายงาน: 2026-08-24

## ส่วนที่ทำงานแล้ว

- `setup.bat` สร้าง `.venv`, ติดตั้ง pinned local dependencies, initialize SQLite และ seed presets ได้
- Local FastAPI app start ได้ และ `/healthz` ตอบ OK
- `/api/diagnostics` รายงานว่าไม่มี required failures
- Event creation สร้าง DB records, folders, `event.json`, QR PNG และ INCOMING path
- Watcher preserve originals และ queue processing หลัง stable-file checks
- Processing สร้าง finished JPEG, preview และ thumbnail โดยไม่แก้ original
- Failed-job UI และ diagnostics page เชื่อมแล้ว
- QR save/copy/print actions เชื่อมแล้ว
- Local smoke E2E ผ่าน
- Stress test 50 รูปผ่านหลัง harden upload queue

## สิ่งที่ต้องตั้งค่าภายนอก

- Google OAuth credentials
- Google Drive provider connection และ live upload verification
- Cloud deployment URL
- PostgreSQL `DATABASE_URL`
- Public gallery domain/base URL
- Cloud/gallery integration tests กับ deployment จริง

## สิ่งที่ต้องยืนยันกับ Hardware จริง

- Windows notebook พร้อม tether software
- Capture จากกล้องจริงเข้า INCOMING
- Burst capture behavior
- RAW+JPEG tether naming/pairing
- Internet disconnect/reconnect ระหว่าง capture จริง
- QR scan จากมือถือของ guest ใน network/สถานที่จริง

## ข้อจำกัดที่ทราบ

- Google Drive upload provider ยังไม่ได้เชื่อมครบ ถ้าไม่มี credentials/provider setup variants จะอยู่ที่ `READY_TO_UPLOAD`
- Face search ยังไม่มี embedding/vector matching จริง
- Cloud gallery photo endpoint ยังไม่ได้คืน variant URLs ครบ
- `run.bat` browser auto-open ยังไม่ได้ verify ในรอบนี้ แต่ direct uvicorn startup และ health ตรวจแล้ว
- Stress test ขนาด 500/2,000 รูปยังไม่ได้รันในรอบนี้

## ผลการทดสอบ

- Automated local tests: 10 passed
- Skipped tests: 1 cloud/PostgreSQL test skipped
- Failed tests: 0 หลังแก้
- Setup verification: ผ่าน เมื่ออนุญาต network สำหรับ download dependencies
- Startup verification: ผ่านด้วย direct uvicorn run
- Diagnostics: zero required failures
- E2E local smoke: passed
- Stress 50: passed, failed jobs 0 และ lost originals 0

## สถานะสุดท้าย

READY FOR LOCAL TESTING

MomentLink V1 ยังไม่พร้อมเป็น limited event pilot จนกว่าจะตั้งค่า Google Drive/cloud และทดสอบ real camera/tether hardware ครบ
