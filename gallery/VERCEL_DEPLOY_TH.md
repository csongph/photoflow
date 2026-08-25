# Deploy Guest Gallery บน Vercel

## Project Root

ตอนสร้างโปรเจกต์ใน Vercel ให้ตั้ง Root Directory เป็น:

```text
gallery
```

## Environment Variables

ตั้งค่าใน Vercel Project Settings:

```env
MOMENTLINK_API_URL=https://your-backend.onrender.com
```

ค่านี้คือ URL ของ backend `cloud` ที่รันอยู่บน Render หรือ server อื่น

## URL หลัง deploy

ถ้า Vercel ได้โดเมน:

```text
https://momentlink-gallery.vercel.app
```

ลิงก์แกลเลอรี่จริงจะเป็น:

```text
https://momentlink-gallery.vercel.app/gallery/{public_id}
```

ดังนั้นฝั่ง backend และ local ควรตั้ง:

```env
PUBLIC_GALLERY_BASE_URL=https://momentlink-gallery.vercel.app/gallery
```
