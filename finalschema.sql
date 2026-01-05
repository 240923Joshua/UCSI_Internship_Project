-- --------------------------------------------------------
-- Host:                         E:\UCSI Internship\project\UCSI_Internship_Project\internship.db
-- Server version:               3.51.0
-- Server OS:                    
-- HeidiSQL Version:             12.14.0.7165
-- --------------------------------------------------------

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES  */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


-- Dumping database structure for internship
CREATE DATABASE IF NOT EXISTS "internship";
;

-- Dumping structure for table internship.attendance
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

-- Data exporting was unselected.

-- Dumping structure for table internship.domain_skills
CREATE TABLE IF NOT EXISTS domain_skills (
    domain TEXT NOT NULL,
    skill_id INTEGER NOT NULL,
    FOREIGN KEY (skill_id) REFERENCES skills(skill_id),
    UNIQUE(domain, skill_id)
);
;

-- Data exporting was unselected.

-- Dumping structure for table internship.evidence_attachments
CREATE TABLE IF NOT EXISTS evidence_attachments (
    attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (report_id) REFERENCES weekly_reports(report_id) ON DELETE CASCADE
);

-- Data exporting was unselected.

-- Dumping structure for table internship.internship
CREATE TABLE IF NOT EXISTS internship (
    internship_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    domain TEXT NOT NULL,
    weeks INTEGER NOT NULL, --include stipend???
    start_date TEXT,   -- YYYY-MM-DD
    end_date TEXT, supervisor_id INTEGER
REFERENCES users(user_id), location_name TEXT, location_type TEXT, supervisor_title TEXT, supervisor_department TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Data exporting was unselected.

-- Dumping structure for table internship.ml_results
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

-- Data exporting was unselected.

-- Dumping structure for table internship.skills
CREATE TABLE IF NOT EXISTS skills (
    skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
;

-- Data exporting was unselected.

-- Dumping structure for table internship.user_details
CREATE TABLE IF NOT EXISTS user_details (
    user_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone_number TEXT, "department" TEXT NULL DEFAULT NULL, avatar_url TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
;

-- Data exporting was unselected.

-- Dumping structure for table internship.users
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    password TEXT NOT NULL,
    role TEXT NOT NULL
        CHECK (role IN ('intern', 'supervisor'))
, password_updated_at DATE);

-- Data exporting was unselected.

-- Dumping structure for table internship.weekly_reports
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

    submitted_at TEXT DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'submitted', supervisor_feedback TEXT, reviewed_at TEXT,

    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (internship_id) REFERENCES internship(internship_id) ON DELETE CASCADE,

    UNIQUE (user_id, internship_id, week_number)
);
;

-- Data exporting was unselected.

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
