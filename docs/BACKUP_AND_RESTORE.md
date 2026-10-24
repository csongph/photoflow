# Backup และ Restore

## Local

สำรองทั้งโฟลเดอร์ `local/data/` และ Event Root ที่ตั้งไว้ เพราะ SQLite เก็บ metadata ส่วน Event Root เก็บภาพจริง

ก่อน backup ให้หยุด MomentLink เพื่อไม่ให้มีการเขียนฐานข้อมูลระหว่างคัดลอก

## Cloud

ใช้ Supabase Point-in-Time Recovery หรือ database backup ของ project และเก็บค่าการตั้งค่า Render แยกจาก repository

การลบ Event จาก Studio จะลบ metadata ใน Cloud ตาม contract แต่ไม่ลบไฟล์ต้นฉบับในเครื่องโดยอัตโนมัติ
