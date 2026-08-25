# ตั้งค่า Supabase เป็น Database

## ใช้ connection string ไหน

สำหรับ backend ที่รันเป็น web service บน Render ให้ใช้ Supabase connection string แบบใดแบบหนึ่ง:

- แนะนำ: Session pooler port `5432` ถ้า Render ต่อ direct IPv6 ไม่ได้
- ใช้ได้: Direct connection port `5432` ถ้า network รองรับ

หลีกเลี่ยง Transaction pooler port `6543` ถ้าไม่จำเป็น เพราะบาง driver/ORM อาจมีข้อจำกัดเรื่อง prepared statements

## ตั้งบน Render

ใน Render service `momentlink-cloud` ให้ตั้ง:

```env
DATABASE_URL=postgresql://postgres.xxxxx:[PASSWORD]@aws-xxxxx.pooler.supabase.com:5432/postgres
```

ระบบจะแปลง `postgresql://` เป็น `postgresql+psycopg://` ให้อัตโนมัติใน backend

## Migration

ตอน Render start ระบบจะรัน:

```sh
alembic -c cloud/alembic.ini upgrade head
```

ดังนั้นตารางใน Supabase จะถูกสร้าง/อัปเดตอัตโนมัติ
