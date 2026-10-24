# Deploy Cloud บน Render และ Supabase

## Render แบบ Dockerfile จาก root

ใช้ `render.yaml` หรือ Dockerfile ที่ root repository ได้เลย ระบบจะรัน `alembic upgrade head` ก่อนเปิด Uvicorn

## Render ที่ตั้ง Root Directory เป็น `cloud`

```text
Build Command: pip install -r requirements.txt
Start Command: alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health Check Path: /healthz
```

Environment variables ที่ต้องมี:

```text
DATABASE_URL=<Supabase PostgreSQL connection string>
CLOUD_SYNC_TOKEN=<ค่าเดียวกับ Local>
PUBLIC_GALLERY_BASE_URL=https://your-vercel-project.vercel.app
```

ห้ามใช้ SQLite บน Render เป็นฐานข้อมูล production และห้ามใส่ค่า secret ลง Git
