# MomentLink V1

MomentLink คือระบบส่งมอบภาพถ่ายงานอีเวนต์แบบ local-first สำหรับ Windows 10/11 ระบบจะเฝ้าดูโฟลเดอร์ `INCOMING` ของแต่ละงาน เก็บไฟล์ต้นฉบับอย่างปลอดภัย สร้างไฟล์สำหรับแสดงผล จัดคิวอัปโหลด อัปเดตแกลเลอรีอัตโนมัติ สร้าง QR และเปิด dashboard ให้ช่างภาพใช้งาน

Workflow หลักของช่างภาพคือ:

```text
run.bat -> Create Event -> Copy INCOMING path -> ตั้งค่า tether software ให้เซฟลงโฟลเดอร์นั้น -> ถ่ายภาพ
```

หลังจากกล้องหรือ tether software เขียนไฟล์เข้ามา MomentLink จะจัดการ backup, สร้างไฟล์แสดงผล, อัปโหลด Google Drive, publish และ sync ไปยังแกลเลอรีให้เอง

## สิ่งที่ต้องมี

- Windows 10/11
- Python 3.11 ขึ้นไป
- โปรแกรม tether ที่เซฟไฟล์ลงโฟลเดอร์ได้ เช่น Canon EOS Utility, digiCamControl, Nikon NX Tether, Sony software, Capture One, Lightroom Tether หรือการ copy จาก SD card

## เริ่มใช้งานเร็ว

1. ดับเบิลคลิก `setup.bat`
2. ดับเบิลคลิก `run.bat`
3. Browser จะเปิดที่ `http://127.0.0.1:8000`
4. เปิดหน้า `Events` สร้าง event แล้ว copy path ของ `INCOMING`
5. ตั้งค่า tether software ให้เซฟไฟล์ลง path นั้น
6. กด `Start Event`
7. ถ่ายภาพจริง แล้วตรวจสถานะรูปและคิวจากหน้า Event

## โครงสร้างระบบ

- `local/`: FastAPI app สำหรับ UI, SQLite, watcher, processing, queue, recovery และ QR
- `cloud/`: FastAPI API สำหรับ deploy เพื่อเก็บ metadata ของ event/photo/gallery บน PostgreSQL
- `gallery/`: public gallery แบบ static สำหรับมือถือ ใช้ HTML/CSS/JS ปกติ

## Feature ฝั่ง Local ที่ทำงานแล้ว

- SQLite schema: events, photos, jobs, presets, uploads, settings, sync_state
- Watchdog folder watcher พร้อมรอไฟล์นิ่งก่อนอ่าน
- ป้องกันรูปซ้ำด้วย SHA-256
- เก็บไฟล์ต้นฉบับลง `ORIGINAL` โดยไม่แก้ไฟล์ต้นฉบับ
- Persistent worker queue พร้อม retry/recovery
- แปลงไฟล์เป็น JPEG สำหรับส่งมอบโดยไม่ปรับแต่งสีหรือผิวอัตโนมัติ
- รองรับ JPEG, PNG, TIFF ส่วน RAW จะถูกเก็บรักษาไว้ แต่การ process ต้องมี `rawpy` ที่ compatible หรือมี JPEG pair
- สร้าง finished JPEG, preview และ thumbnail
- สร้าง QR code
- Capture/processing แบบ offline-safe ถ้ายังไม่มี storage credentials ไฟล์จะอยู่ในสถานะ `READY_TO_UPLOAD`

## Google Drive

MomentLink มี storage-provider abstraction และมีโครงสำหรับ Google Drive provider ให้ใส่ OAuth credentials ใน `.env`:

```env
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/api/google/callback
```

V1 ไม่เก็บ secret ใน frontend code ถ้ายังไม่มี credentials การ capture และ processing ในเครื่องยังทำงานต่อได้ และไฟล์สำหรับ upload จะถูกเก็บในคิวอย่างปลอดภัย

## Gallery

ดู local preview ได้จาก dashboard ส่วน production gallery สามารถ deploy โฟลเดอร์ `gallery/` ไปที่ Vercel หรือ static host อื่น แล้วตั้งค่า:

```env
PUBLIC_GALLERY_BASE_URL=https://your-gallery.example.com
CLOUD_API_URL=https://your-cloud-api.example.com
```

เมื่อกำหนด `CLOUD_API_URL` และ `CLOUD_SYNC_TOKEN` แล้ว Local จะตรวจรายการ Event บน Cloud ทุก 60 วินาที และ mirror Event/สถานะรูปเข้าฐานข้อมูลในเครื่องโดยอัตโนมัติ ปรับช่วงเวลาได้ด้วย `CLOUD_EVENT_POLL_SECONDS` (อย่างน้อย 30 วินาที) การ mirror นี้นำเข้า metadata เท่านั้น ไฟล์ภาพเต็มยังเก็บใน Google Drive ตามเดิม

## แก้ปัญหาเบื้องต้น

- Port 8000 ถูกใช้อยู่: ปิด app อื่น หรือแก้ `LOCAL_PORT` และปรับ `run.bat`
- ไม่พบ Python: ติดตั้ง Python 3.11+ แล้วรัน `setup.bat` ใหม่
- Google Drive ใช้ไม่ได้: รูปจะยังถูกเก็บในคิวอย่างปลอดภัย
- RAW ไม่รองรับ: original จะถูกเก็บไว้ ให้ติดตั้ง `rawpy` ที่ compatible หรือถ่าย RAW+JPEG
- พื้นที่ disk เหลือน้อย: ย้าย `EVENT_ROOT_DIR` ไป drive ที่ใหญ่กว่าใน `.env`
