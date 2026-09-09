# เช็กลิสต์ทดสอบ MomentLink V1 กับกล้องจริง

ใช้เช็กลิสต์นี้บน Windows notebook ที่มี tether application และกล้องจริง

## Local Startup

- [ ] รัน `setup.bat` จาก fresh clone
- [ ] ใส่ค่าที่จำเป็นใน `.env`
- [ ] รัน `run.bat`
- [ ] เปิด `/diagnostics`
- [ ] ตรวจว่า required checks เป็น OK
- [ ] ตรวจว่า optional Google Drive/cloud checks เป็น connected หรือแสดง `NEEDS MANUAL CREDENTIAL`

## Event และ Tether Capture

- [ ] Create Event
- [ ] เลือก preset
- [ ] Start Event
- [ ] Copy INCOMING path
- [ ] เปิด tether software
- [ ] ตั้ง capture destination เป็น INCOMING
- [ ] Capture JPEG 1 รูป
- [ ] ตรวจว่า detect ได้
- [ ] ตรวจว่า original อยู่ใน `ORIGINAL`
- [ ] ตรวจว่า finished JPEG อยู่ใน `FINISHED`
- [ ] ตรวจว่า preview อยู่ใน `PREVIEWS`
- [ ] ตรวจว่า thumbnail อยู่ใน `THUMBNAILS`
- [ ] ตรวจว่า gallery preview แสดง thumbnail
- [ ] Capture JPEG ต่อเนื่อง 10 รูป
- [ ] ตรวจว่าไม่มี duplicate photo records
- [ ] ตรวจว่าไม่มี original ถูก overwrite

## RAW+JPEG

- [ ] เปิด RAW+JPEG ในกล้อง
- [ ] Capture 1 เฟรม
- [ ] ตรวจว่า JPEG process ได้
- [ ] ตรวจว่า RAW ถูก preserve
- [ ] ตรวจว่า RAW ไม่ทำให้ queue crash
- [ ] บันทึก naming/pairing behavior จริงของ tether software

## Offline Flow

- [ ] ตัดอินเทอร์เน็ต
- [ ] Capture JPEG 10 รูป
- [ ] ตรวจว่า originals ยังถูก preserve
- [ ] ตรวจว่า processing ยังทำงาน
- [ ] ตรวจว่า upload variants อยู่ใน queued/ready state
- [ ] ต่ออินเทอร์เน็ตกลับ
- [ ] ถ้า Google/cloud credentials configured แล้ว ตรวจว่า upload resume ได้

## QR และ Gallery

- [ ] Show QR
- [ ] Save QR PNG
- [ ] Copy gallery link
- [ ] Print QR
- [ ] Scan QR จากมือถือ
- [ ] ตรวจว่า gallery URL เปิดได้
- [ ] ตรวจว่า thumbnails โหลดได้
- [ ] เปิด preview/lightbox
- [ ] Download image ถ้าเปิด allow download

## Final Hardware Status

- [ ] ยังถือว่า `NEEDS REAL HARDWARE TEST` จนกว่าจะทดสอบทุกข้อด้านบนกับกล้อง/tether setup จริงครบ
