# ไฟล์ Database สำหรับ Supabase

ไฟล์ที่ใช้คือ:

```text
supabase/schema.sql
```

วิธีใช้:

1. เข้า Supabase Project
2. ไปที่ SQL Editor
3. New query
4. เปิดไฟล์ `supabase/schema.sql`
5. Copy ทั้งไฟล์ไปวาง
6. กด Run

หมายเหตุ:

- ไม่ต้องเอาไฟล์ `local/data/photoflow.db` ไปใส่ Supabase
- ถ้า deploy backend บน Render แล้ว backend จะรัน Alembic migration ให้อัตโนมัติได้เหมือนกัน
- ใช้ `schema.sql` เมื่อต้องการสร้างตารางเองใน Supabase ก่อน deploy หรือเพื่อเช็ก schema
