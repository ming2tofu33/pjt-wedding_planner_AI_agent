PRAGMA foreign_keys = ON;

-- 업체(벤더)
CREATE TABLE IF NOT EXISTS vendor (
  vendor_id   INTEGER PRIMARY KEY AUTOINCREMENT, -- 내부 식별자
  type        TEXT NOT NULL,                     -- hall|studio|dress|makeup
  name        TEXT NOT NULL,                     -- 업체/브랜드명(엑셀 conm 매핑)
  region      TEXT,                              -- 지역(엑셀 subway 매핑 가능)
  notes       TEXT
);

-- 상품/패키지(롱 포맷)
CREATE TABLE IF NOT EXISTS offering (
  offering_id  INTEGER PRIMARY KEY AUTOINCREMENT,
  vendor_id    INTEGER NOT NULL REFERENCES vendor(vendor_id) ON DELETE CASCADE,
  category     TEXT NOT NULL,                    -- hall_package|studio_shoot|...
  package_name TEXT,                             -- ex) allday|manager|meal_expense
  price        INTEGER,                          -- KRW 정수
  meta_json    TEXT                              -- 옵션/부가정보(JSON)
);

CREATE INDEX IF NOT EXISTS idx_vendor_type   ON vendor(type);
CREATE INDEX IF NOT EXISTS idx_offering_vndr ON offering(vendor_id);
CREATE INDEX IF NOT EXISTS idx_offering_cat  ON offering(category);
