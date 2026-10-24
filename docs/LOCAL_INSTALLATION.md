# ติดตั้ง MomentLink Local

## สิ่งที่ต้องมี

- Windows 10/11
- Python 3.11 ขึ้นไป
- โปรแกรม tether ที่บันทึกไฟล์ลงโฟลเดอร์ได้

## เริ่มระบบ

```powershell
cd "D:\personal project\photoflow"
.\setup.bat
.\run.bat
```

เปิด `http://127.0.0.1:8000` แล้วเข้า Settings/Ready Check ก่อนสร้างงาน

## ลำดับใช้งาน

1. ตั้ง Event Root ที่มีสิทธิ์เขียน
2. สร้าง Event และกด Start Event
3. ตั้งโปรแกรมกล้องให้บันทึกเข้าโฟลเดอร์ `INCOMING` ของ Event
4. ตั้งค่า Public Gallery Base URL เป็นโดเมน Vercel จริง
5. เชื่อม Google Drive จาก Settings ถ้าต้องการให้ผู้ใช้ดาวน์โหลดผ่าน Cloud
6. QR ของ Event จะชี้ไป `https://โดเมน-vercel/?event=PUBLIC_ID`

ไฟล์ต้นฉบับจะไม่ถูกเขียนทับและไม่ถูกลบอัตโนมัติ
