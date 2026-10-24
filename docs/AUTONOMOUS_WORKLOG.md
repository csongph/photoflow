# บันทึกการทำงานอัตโนมัติ

## 24 ตุลาคม 2026

- ตรวจ branch `main` และสถานะ repository เดิม
- รัน regression suite โดยแยกฐานข้อมูลทดสอบไปยังไฟล์ชั่วคราว
- ตรวจและแก้ Google Drive `invalid_grant` ให้ตัดการเชื่อมต่อและพัก upload อย่างปลอดภัย
- เพิ่มข้อความแจ้ง reconnect และเพิ่ม cache-busting ให้หน้า Studio
- ปรับ test harness ให้กำหนด `PHOTOFLOW_TEST_DB` และ `PHOTOFLOW_TEST_EVENTS` ได้
- ตรวจ migration head และ deployment configuration

ผลล่าสุด: `34 passed`
