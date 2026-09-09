# Deploy แบบ Vercel + Supabase + Render

## ภาพรวม

- `gallery` -> Vercel frontend สำหรับผู้ใช้/QR
- `cloud` -> Render backend API
- Supabase -> PostgreSQL database
- `local` -> รันบนเครื่องโรงเรียน ไม่ deploy public

## 1. Deploy Backend บน Render

ใช้ root ของ repo นี้ แล้ว Render จะอ่าน `render.yaml`

ตั้ง Environment Variables:

```env
DATABASE_URL=<Supabase connection string>
PUBLIC_GALLERY_BASE_URL=https://your-vercel-project.vercel.app
CLOUD_SYNC_TOKEN=<สุ่มยาวๆ หรือใช้ค่าที่ Render generate>
```

## 2. Deploy Frontend บน Vercel

สร้าง Vercel project จาก repo เดียวกัน แต่ตั้ง:

```text
Root Directory: gallery
```

ตั้ง Environment Variables:

```env
MOMENTLINK_API_URL=https://your-render-backend.onrender.com
```

Vercel จะใช้ `gallery/api/config.js` ส่งค่า backend URL ให้หน้าเว็บ

## 3. ตั้งค่าเครื่องโรงเรียน

ใน `.env` ฝั่ง local:

```env
CLOUD_API_URL=https://your-render-backend.onrender.com
PUBLIC_GALLERY_BASE_URL=https://your-vercel-project.vercel.app
CLOUD_SYNC_TOKEN=<ค่าเดียวกับ Render>
```

หลังแก้แล้ว restart MomentLink local

## 4. ลิงก์ QR

QR จะใช้:

```text
https://your-vercel-project.vercel.app/?event={public_id}
```

หน้า Vercel จะเรียก API ไป Render และ Render จะอ่านข้อมูลจาก Supabase
