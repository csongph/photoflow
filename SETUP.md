# คู่มือติดตั้ง MomentLink บน Windows

## 1. ติดตั้ง Python

ติดตั้ง Python 3.11 ขึ้นไปจาก:

```text
https://www.python.org/downloads/windows/
```

ตอนติดตั้งให้เลือก `Add python.exe to PATH`

## 2. รัน Setup

ดับเบิลคลิก:

```text
setup.bat
```

สคริปต์จะทำงานเหล่านี้:

- ตรวจว่าเครื่องมี Python
- ตรวจ version ของ Python
- สร้าง `.venv`
- ติดตั้ง dependencies
- initialize SQLite
- สร้างโฟลเดอร์พื้นฐาน
- seed system presets
- สร้าง `.env` จาก `.env.example` ถ้ายังไม่มี

ถ้า setup fail หน้าต่างจะค้างไว้และแสดง error ให้ดู

## 3. เปิด MomentLink

ดับเบิลคลิก:

```text
run.bat
```

Browser จะเปิด:

```text
http://127.0.0.1:8000
```

## 4. สร้าง Event

1. เปิดหน้า `Events`
2. ใส่ชื่อ event, วันที่, preset และ processing settings
3. กด `Create Event`
4. Copy path ใหญ่ของ `INCOMING`
5. กด `Start Event`

## 5. ใช้กับ Canon EOS Utility

MomentLink ไม่ได้ควบคุมกล้อง Canon โดยตรง แต่จะ watch โฟลเดอร์ที่ EOS Utility เซฟไฟล์

1. ต่อกล้องกับเครื่อง
2. เปิด Canon EOS Utility
3. เลือก Remote Shooting
4. ตั้ง Destination Folder เป็นโฟลเดอร์ `INCOMING` ของ event ใน MomentLink
5. กด Start Event ใน MomentLink
6. ถ่ายภาพทดสอบ 1 รูป
7. ตรวจว่า MomentLink detect, backup, process และแสดงรูปได้

## 6. Demo Mode

บน Dashboard กด:

```text
Simulate Photo
```

ปุ่มนี้จะเขียนไฟล์ JPEG ทดสอบลง `INCOMING` และใช้ watcher/processing pipeline เดียวกับการถ่ายจากกล้องจริง

## 7. Cloud และ Gallery

Local capture ไม่ต้องใช้อินเทอร์เน็ต

ถ้าต้องการใช้งาน public delivery:

1. Deploy `cloud/` ไป Render, Railway, VPS หรือ platform ที่เหมาะสม
2. ใช้ PostgreSQL หรือ Supabase PostgreSQL
3. Deploy `gallery/` ไป Vercel หรือ static hosting
4. ตั้งค่า `CLOUD_API_URL` และ `PUBLIC_GALLERY_BASE_URL` ใน `.env`
