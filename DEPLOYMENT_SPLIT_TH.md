# MomentLink - แยกส่วนที่ต้อง Deploy กับส่วนที่รันในเครื่อง

เอกสารนี้คือคำตอบสั้น ๆ ว่าไฟล์ไหนใช้รันในเครื่อง และไฟล์ไหนต้องเอาขึ้น server/cloud

## สรุป

ระบบนี้ควรแยกเป็น 3 ส่วน:

1. **Local Agent / Admin Console** - รันในเครื่องช่างภาพหรือเครื่องโรงเรียน
2. **Cloud API** - deploy ขึ้น server เพื่อให้ Gallery public ดึงข้อมูลจริง
3. **Public Gallery** - deploy เป็นหน้าเว็บที่นักเรียน/ผู้ใช้สแกน QR เข้าได้

## 1. รันในเครื่องเท่านั้น

โฟลเดอร์:

```text
local/
```

ไฟล์เปิดระบบ:

```text
Start-MomentLink.bat
Start-MomentLink.ps1
```

หน้าที่:

- รับรูปจากโฟลเดอร์ `INCOMING`
- แต่งรูป
- สร้าง `FINISHED`, `THUMBNAILS`, `PREVIEWS`
- คุมงานผ่าน Dashboard
- เช็ก Setup ก่อนเริ่มงาน
- อัปโหลด Google Drive
- sync metadata ไป Cloud API ในอนาคต

ใช้เปิดในเครื่อง:

```powershell
cd "D:\personal project\photoflow"
.\Start-MomentLink.bat
```

หรือ:

```powershell
cd "D:\personal project\photoflow"
.venv\Scripts\python.exe -m uvicorn local.app.main:app --host 0.0.0.0 --port 8000
```

หน้า local:

```text
http://127.0.0.1:8000/setup
http://127.0.0.1:8000/
http://127.0.0.1:8000/events
http://127.0.0.1:8000/settings
```

ส่วนนี้ **ไม่ควร deploy public** เพราะเป็นตัวแต่งรูปและเข้าถึงไฟล์ในเครื่องจริง

## 2. ต้อง Deploy: Cloud API

โฟลเดอร์:

```text
cloud/
```

หน้าที่:

- เก็บข้อมูล event/photo
- รับ sync จาก `local/`
- ส่งข้อมูลให้ Public Gallery
- เป็น backend กลางที่เปิดจากอินเทอร์เน็ตได้

ตัวอย่าง URL หลัง deploy:

```text
https://momentlink-api.your-school.com
```

แนะนำ deploy ที่:

- Render
- Railway
- Fly.io
- Google Cloud Run
- VPS ของโรงเรียน

ส่วนนี้ต้องมี database จริง เช่น:

```text
PostgreSQL
```

## 3. ต้อง Deploy: Public Gallery

โฟลเดอร์:

```text
gallery/
```

หน้าที่:

- หน้าเว็บที่ผู้ใช้สแกน QR เข้า
- ดูรูป
- โหลดรูป
- แชร์ลิงก์

ตัวอย่าง URL หลัง deploy:

```text
https://gallery.your-school.com
```

แนะนำ deploy ที่:

- Cloudflare Pages
- Vercel
- Netlify
- Static hosting ของโรงเรียน

Gallery ต้องชี้ API ไปที่ Cloud API ไม่ใช่ `127.0.0.1`

## 4. Storage รูปจริง

ควรใช้หนึ่งในนี้:

```text
Google Drive
Cloudflare R2
AWS S3
Google Cloud Storage
```

ตอนนี้แนวทางที่เหมาะกับโรงเรียนที่สุด:

```text
Local Agent -> Google Drive -> Cloud API -> Public Gallery
```

## Flow ใช้งานจริง

```text
1. ช่างภาพเปิด Start-MomentLink.bat ในเครื่อง
2. เข้า /setup เช็กทุกอย่างให้พร้อม
3. สร้าง Event
4. วางรูปเข้า INCOMING
5. Local Agent แต่งรูปและอัปโหลด Google Drive
6. Local Agent ส่ง metadata ไป Cloud API
7. Public Gallery แสดงรูปจากข้อมูล Cloud API
8. ผู้ใช้สแกน QR จาก URL public
```

## ตอนนี้สถานะโปรเจกต์

มีแล้ว:

- `local/` สำหรับรันในเครื่อง
- `gallery/` สำหรับหน้า Gallery
- `cloud/` สำหรับ Cloud API เบื้องต้น
- `Start-MomentLink.bat` สำหรับเปิด local
- `/setup` สำหรับเช็กก่อนเริ่มงาน

ยังควรทำต่อ:

- เชื่อม sync จาก `local/` ไป `cloud/` ให้ครบ
- ปรับ `gallery/` ให้ใช้ Cloud API URL ตอน deploy
- เพิ่ม deploy config สำหรับ Render/Cloudflare
- ตั้งค่า production environment

## สรุปสุดท้าย

```text
รันในเครื่อง:
- local/
- Start-MomentLink.bat
- Start-MomentLink.ps1

Deploy:
- cloud/
- gallery/

Storage:
- Google Drive หรือ Cloud Storage
```

