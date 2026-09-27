-- harmwatch: table `detections` (written by harmwatch/analyze.py, read by the platform).
-- Percentages are 0-100 integers. NULL = not computed (item not judged, restricted, or not applicable).
CREATE TABLE IF NOT EXISTS detections (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at        TEXT NOT NULL,                 -- UTC, ISO 8601
    source            TEXT,                          -- who sent the item: telegram | volunteer | extension | cli ...
    url               TEXT,                          -- where the item was seen (never the media itself)
    modality          TEXT NOT NULL CHECK (modality IN ('text', 'image', 'meme', 'video')),
    media_hash        TEXT NOT NULL,                 -- sha256 of the file (or of the text)
    filter_score      REAL,                          -- fast pre-filter P(sexual), 0-1; NULL for text (no filter)
    filter_passed     INTEGER CHECK (filter_passed IN (0, 1)),
    sexual_violence   INTEGER CHECK (sexual_violence BETWEEN 0 AND 100),
    sexual_harassment INTEGER CHECK (sexual_harassment BETWEEN 0 AND 100),
    hate              INTEGER CHECK (hate BETWEEN 0 AND 100),
    misogyny          INTEGER CHECK (misogyny BETWEEN 0 AND 100),
    other_violence    INTEGER CHECK (other_violence BETWEEN 0 AND 100),
    sexual            INTEGER CHECK (sexual IN (0, 1)),   -- decision of the AI judge
    category          TEXT,                          -- e.g. sexualised_insult, threat_incitement, none
    primary_relation  TEXT,                          -- SV-REL-1..5 (policy/core.md) or NULL
    route             TEXT NOT NULL,                 -- see docs/platform/README.md
    priority          TEXT NOT NULL CHECK (priority IN ('urgent', 'high', 'standard', 'none')),
    flagged_start_s   REAL,                          -- video: start of the flagged passage (seconds)
    flagged_end_s     REAL,                          -- video: end of the flagged passage (seconds)
    summary           TEXT,                          -- one neutral, non-graphic sentence
    explicit_alert    INTEGER NOT NULL DEFAULT 0 CHECK (explicit_alert IN (0, 1)),
    possible_minor    INTEGER NOT NULL DEFAULT 0 CHECK (possible_minor IN (0, 1)),
    restricted        INTEGER NOT NULL DEFAULT 0 CHECK (restricted IN (0, 1)),
    model             TEXT,                          -- what took the decision (judge model, pre-filter or safety filter)
    prompt_version    TEXT,                          -- frozen prompt of the judge, e.g. sv_prompt_v3
    region            TEXT NOT NULL,
    latency_ms        INTEGER,
    full_result_json  TEXT,                          -- details (no media, no raw text; reduced when restricted)
    -- CH-5: a possible minor is always restricted, and a restricted row carries no content.
    CHECK (possible_minor = 0 OR restricted = 1),
    CHECK (restricted = 0 OR (sexual_violence IS NULL AND sexual_harassment IS NULL AND hate IS NULL
                              AND misogyny IS NULL AND other_violence IS NULL AND sexual IS NULL
                              AND category IS NULL AND primary_relation IS NULL AND summary IS NULL
                              AND flagged_start_s IS NULL AND flagged_end_s IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_detections_created_at ON detections (created_at);
CREATE INDEX IF NOT EXISTS idx_detections_priority ON detections (priority);
CREATE INDEX IF NOT EXISTS idx_detections_sexual ON detections (sexual);
