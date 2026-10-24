# Production Readiness

สถานะรวม: PARTIALLY VERIFIED

## ผ่านการตรวจใน environment นี้

- `34 passed` automated tests
- Python compile และ JavaScript syntax ผ่าน
- Alembic มี migration head `0003_disable_face_search`
- Git diff ตรวจด้วย `git diff --check`
- ไม่มีการใช้ข้อมูลภาพจริงใน stress/test flow

## ต้องตรวจด้วยมือก่อนใช้งานจริง

- Render deploy สำเร็จและ `/healthz` ตอบ 200
- Supabase migration ทำงานครบ
- `CLOUD_SYNC_TOKEN` ฝั่ง Local/Render ตรงกัน
- Google OAuth redirect URI ตรงกับ URL จริง
- Vercel frontend เรียก Render API ได้
- QR เปิดได้จาก 4G/5G และดาวน์โหลด JPEG บน iPhone/Android
- สำรอง Local Event Root และ Supabase แล้ว

ถ้าข้อใดด้านบนยังไม่ผ่าน ให้ถือว่ายังไม่พร้อมสำหรับงานจริง แม้ automated tests จะผ่าน
