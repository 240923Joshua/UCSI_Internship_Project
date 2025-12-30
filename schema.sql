PRAGMA foreign_keys = ON;

-- =========================
-- USERS (AUTH & ROLE)
-- =========================
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    password TEXT NOT NULL,
    role TEXT NOT NULL
        CHECK (role IN ('intern', 'supervisor'))
);

-- =========================
-- USER DETAILS (PROFILE)
-- =========================
CREATE TABLE IF NOT EXISTS user_details (
    user_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone_number TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- =========================
-- INTERNSHIP 
-- =========================
CREATE TABLE IF NOT EXISTS internship (
    internship_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,          -- intern
    supervisor_id INTEGER NOT NULL,    -- supervisor
    title TEXT NOT NULL,
    domain TEXT NOT NULL, --include stipend???
    weeks INTEGER NOT NULL,
    start_date TEXT,
    end_date TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (supervisor_id) REFERENCES users(user_id)
);


-- =========================
-- ATTENDANCE
-- =========================
CREATE TABLE IF NOT EXISTS attendance (
    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    internship_id INTEGER NOT NULL,
    date TEXT NOT NULL,  -- YYYY-MM-DD
    status TEXT NOT NULL
        CHECK (status IN ('Present', 'Absent', 'Leave')),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (internship_id) REFERENCES internship(internship_id) ON DELETE CASCADE
);

-- =========================
-- WEEKLY REPORTS
-- =========================
CREATE TABLE IF NOT EXISTS weekly_reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_id INTEGER NOT NULL,
    internship_id INTEGER NOT NULL,

    week_number INTEGER NOT NULL,

    attendance_percentage INTEGER
        CHECK (attendance_percentage BETWEEN 0 AND 100),

    task_description TEXT NOT NULL,

    focus_skill TEXT NOT NULL,

    skill_rating INTEGER
        CHECK (skill_rating BETWEEN 1 AND 10),

    stress_level INTEGER
        CHECK (stress_level BETWEEN 1 AND 5),

    self_evaluation TEXT,

    challenges TEXT,

    next_week_priorities TEXT,

    evidence_link TEXT,

    submitted_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (internship_id) REFERENCES internship(internship_id) ON DELETE CASCADE,

    UNIQUE (user_id, internship_id, week_number)
);


-- =========================
-- EVIDENCE ATTACHMENTS
-- =========================
CREATE TABLE IF NOT EXISTS evidence_attachments (
    attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (report_id) REFERENCES weekly_reports(report_id) ON DELETE CASCADE
);

-- =========================
-- ML RESULTS (PREDICTIONS)
-- =========================
CREATE TABLE IF NOT EXISTS ml_results (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    internship_id INTEGER NOT NULL,
    predicted_score REAL
        CHECK (predicted_score >= 0 AND predicted_score <= 100),
    risk_level TEXT NOT NULL
        CHECK (risk_level IN ('Low', 'Medium', 'High')),
    recommendation TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (internship_id) REFERENCES internship(internship_id) ON DELETE CASCADE
);
