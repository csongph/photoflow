# คู่มือทดสอบ

รันชุดทดสอบโดยไม่แตะฐานข้อมูลจริง:

```powershell
$env:PHOTOFLOW_TEST_DB = "$env:TEMP\momentlink-test.db"
$env:PHOTOFLOW_TEST_EVENTS = "$env:TEMP\momentlink-test-events"
python -m pytest -q --basetemp="$env:TEMP\momentlink-pytest"
```

ชุดทดสอบครอบคลุม file stability, image processing, duplicate handling, queue recovery, auto-publish, retry, Google token expiry, gallery policy และ cloud contracts

การทดสอบที่ต้องทำด้วยมือ: กล้อง/tether จริง, OAuth Google จริง, เปิด QR จากมือถือภายนอก และ Render/Supabase production
