PRAGMA foreign_keys = ON;

-- user profile (1행 사용 권장)
CREATE TABLE IF NOT EXISTS user_profile (
  user_id   INTEGER PRIMARY KEY,
  name      TEXT,
  region    TEXT,
  contact   TEXT,
  notes     TEXT
);

-- 카테고리별 예산(만원) + 확정 여부
CREATE TABLE IF NOT EXISTS budget_pref (
  budget_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id     INTEGER NOT NULL REFERENCES user_profile(user_id),
  category    TEXT NOT NULL,              -- hall|studio|dress|makeup...
  min_manwon  INTEGER,
  max_manwon  INTEGER,
  locked      INTEGER NOT NULL DEFAULT 0, -- 1=확정
  notes       TEXT,
  UNIQUE(user_id, category)
);

-- 이벤트(예식/촬영 등)
CREATE TABLE IF NOT EXISTS event (
  event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER NOT NULL REFERENCES user_profile(user_id),
  type          TEXT NOT NULL,    -- wedding|prewedding|meeting|honeymoon...
  title         TEXT,
  date          TEXT,             -- YYYY-MM-DD
  time          TEXT,             -- HH:MM
  location      TEXT,
  budget_manwon INTEGER,
  memo          TEXT
);

-- 대화 요약(히스토리), 최신본 latest=1
CREATE TABLE IF NOT EXISTS conversation_summary (
  summary_id  INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id     INTEGER NOT NULL REFERENCES user_profile(user_id),
  latest      INTEGER NOT NULL DEFAULT 1,
  content     TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

-- 마일스톤(체크리스트)
CREATE TABLE IF NOT EXISTS milestone (
  ms_id     INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id   INTEGER NOT NULL REFERENCES user_profile(user_id),
  title     TEXT NOT NULL,
  due_date  TEXT NOT NULL,        -- YYYY-MM-DD
  completed INTEGER NOT NULL DEFAULT 0,
  source    TEXT,
  notes     TEXT
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_budget_pref_user_cat ON budget_pref(user_id, category);
CREATE INDEX IF NOT EXISTS idx_event_user_date      ON event(user_id, date);
CREATE INDEX IF NOT EXISTS idx_summary_user_latest  ON conversation_summary(user_id, latest);
CREATE INDEX IF NOT EXISTS idx_ms_user_date         ON milestone(user_id, due_date);