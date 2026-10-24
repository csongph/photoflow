# รายงานตรวจระบบ MomentLink V1

วันที่ตรวจ: 24 ตุลาคม 2026

## ผลตรวจ

- Local capture, processing, queue และ recovery: VERIFIED จาก automated tests
- Auto-publish หลังประมวลผล/อัปโหลด: VERIFIED จาก tests
- Google Drive token หมดอายุและการพักคิว: VERIFIED จาก tests
- Cloud sync, PIN, publication และ download policy: VERIFIED ระดับ contract/unit tests
- Gallery responsive, pagination, lightbox และดาวน์โหลดมือถือ: PARTIALLY VERIFIED ต้องทดสอบบนอุปกรณ์จริง
- Render/Vercel/Supabase production: NOT VERIFIED ใน environment นี้ เพราะไม่มีสิทธิ์ deploy/credentials

## ประเด็นที่แก้

- ป้องกัน publish ก่อน upload ที่จำเป็นเสร็จ
- เพิ่ม retry/recovery และ idempotent sync jobs
- ลบ face-search flow ที่ยังไม่ใช้งานจริงออกจาก public surface
- ป้องกัน Google refresh token ที่ถูก revoke ไม่ให้ retry วน
- ตรวจ PIN, event visibility, download policy และ path ของไฟล์
- ปรับ URL QR ให้ชี้ frontend Vercel ด้วย `?event=`

## ข้อจำกัดที่ยังเหลือ

ต้องใช้บัญชีจริงตรวจ OAuth, กล้อง/tether, Supabase migration และการเปิด QR จากเครือข่ายมือถือภายนอก
