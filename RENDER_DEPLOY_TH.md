# Deploy MomentLink บน Render

## โฟลเดอร์ที่ใช้บน Render

Render ใช้เป็น backend API หลัก โดย deploy จาก root ของโปรเจกต์นี้ได้เลย `Dockerfile` จะ copy:

- `cloud`
- `gallery` เป็น fallback/static copy เฉยๆ แต่ public frontend หลักจะอยู่บน Vercel

ไฟล์ `.dockerignore` กัน `local`, `.env`, `.venv`, database, log และโฟลเดอร์รูปจริงไม่ให้ขึ้น server

## วิธี deploy

1. Push โปรเจกต์ขึ้น GitHub
2. เข้า Render
3. New > Blueprint
4. เลือก repo นี้
5. Render จะอ่าน `render.yaml` แล้วสร้าง Web service: `momentlink-cloud`
6. Deploy

## Environment variables บน Render

`render.yaml` ตั้งให้แล้ว:

```env
DATABASE_URL=<Supabase Postgres connection string>
CLOUD_SYNC_TOKEN=<Render generate ให้อัตโนมัติ>
PUBLIC_GALLERY_BASE_URL=<URL ของ Vercel gallery>
```

หลัง deploy frontend บน Vercel แล้ว ให้ดูโดเมนเช่น:

```text
https://momentlink-gallery.vercel.app
```

แล้วตั้ง:

```env
PUBLIC_GALLERY_BASE_URL=https://momentlink-gallery.vercel.app/gallery
```

จากนั้น redeploy อีกครั้ง

## ตั้งค่าเครื่องโรงเรียนหลัง cloud deploy

ในเครื่อง local ให้ตั้งค่าให้ตรงกับ Render:

```env
CLOUD_API_URL=https://momentlink-cloud.onrender.com
PUBLIC_GALLERY_BASE_URL=https://momentlink-gallery.vercel.app/gallery
CLOUD_SYNC_TOKEN=<ค่าเดียวกับบน Render>
```

แล้ว restart MomentLink local

## URL สำคัญ

- Health check: `https://momentlink-cloud.onrender.com/healthz`
- Guest gallery: `https://momentlink-gallery.vercel.app/gallery/{public_id}`
- Gallery API: `https://momentlink-cloud.onrender.com/api/gallery/{public_id}`

## หมายเหตุ

Render web service ต้อง bind ที่ `0.0.0.0` และใช้ `$PORT` ซึ่ง `Dockerfile` ตั้งไว้แล้ว
