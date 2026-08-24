# แผนทดสอบ MomentLink V1

## ทดสอบการใช้งานจริงแบบ Local

```text
Create Event
ตั้งค่า INCOMING
Copy JPEG เข้า INCOMING
MomentLink detect
Backup original
Process
Apply preset
สร้าง thumbnail
เก็บ upload queue
แสดง gallery preview
สร้าง QR
Download
```

## ทดสอบ Offline

1. Start Event
2. ตัดอินเทอร์เน็ต
3. Capture หรือ simulate 20 รูป
4. ตรวจว่า Detect, Backup, Process, Export และ Queue ยังทำงาน
5. ต่ออินเทอร์เน็ตกลับ
6. เมื่อ storage configured แล้ว ตรวจว่า upload jobs resume ได้

## ทดสอบ Crash/Restart

1. Capture หรือ simulate รูปหลายรูป
2. Force close MomentLink
3. รัน `run.bat`
4. ตรวจว่า live event โหลดกลับมา watcher resume, queue resume และไม่มี duplicate originals

## ทดสอบ Stress

1. Copy JPEG จำนวน 2,000 รูปเข้า `INCOMING`
2. รวม burst 50 ไฟล์ในช่วงสั้น
3. Restart ระหว่าง processing
4. ตรวจว่าไม่มี lost originals, ไม่มี corrupted originals, ไม่มี duplicate jobs, queue persist และจำนวน workers ยัง bounded

สามารถใช้ script:

```text
.venv\Scripts\python.exe tools\stress_test.py --count 50
```

สำหรับ smoke stress ที่เร็วกว่า

## Automated Tests

หลัง setup แล้ว รันจากโฟลเดอร์ `photoflow/`:

```text
.venv\Scripts\python.exe -m pytest -m "not google_drive and not cloud and not face_engine"
```

หรือ:

```text
test_all.bat
```
