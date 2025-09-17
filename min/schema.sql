PRAGMA foreign_keys = ON;

-- 업체
CREATE TABLE IF NOT EXISTS vendor (
  vendor_id   INTEGER PRIMARY KEY AUTOINCREMENT, -- 내부 ID
  type        TEXT NOT NULL,                     -- hall|studio|dress|makeup
  name        TEXT NOT NULL,                     -- 업체명(conm)
  region      TEXT,                              -- 지역/역명(subway)
  min_price   INTEGER,                           -- 최소가(원), CSV min_fee 환산 저장
  notes       TEXT
);

-- 상품/패키지(롱 포맷)
CREATE TABLE IF NOT EXISTS offering (
  offering_id  INTEGER PRIMARY KEY AUTOINCREMENT,
  vendor_id    INTEGER NOT NULL REFERENCES vendor(vendor_id) ON DELETE CASCADE,
  category     TEXT NOT NULL,                    -- hall_package|studio_shoot|dress_rental|makeup_package
  package_name TEXT,                             -- ex) allday|manager|meal_expense...
  price        INTEGER,                          -- 원(KRW)
  meta_json    TEXT                              -- 옵션/부가정보(JSON)
);

-- 조회용 인덱스
CREATE INDEX IF NOT EXISTS idx_vendor_type       ON vendor(type);
CREATE INDEX IF NOT EXISTS idx_vendor_min_price  ON vendor(min_price);
CREATE INDEX IF NOT EXISTS idx_offering_vendor   ON offering(vendor_id);
CREATE INDEX IF NOT EXISTS idx_offering_cat      ON offering(category);

