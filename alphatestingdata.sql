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
CREATE UNIQUE INDEX uniq_attendance
ON attendance(user_id, internship_id, date);

-- Dumping data for table internship.attendance: -1 rows
/*!40000 ALTER TABLE "attendance" DISABLE KEYS */;
INSERT INTO "attendance" ("attendance_id", "user_id", "internship_id", "date", "status") VALUES
	(1, 100001, 1, '2025-01-01', 'Present'),
	(2, 100001, 1, '2025-01-02', 'Present'),
	(3, 100001, 1, '2025-01-03', 'Absent'),
	(4, 100001, 1, '2025-01-04', 'Present'),
	(5, 100001, 1, '2025-01-05', 'Present'),
	(6, 100002, 2, '2025-01-01', 'Absent'),
	(7, 100002, 2, '2025-01-02', 'Present'),
	(8, 100002, 2, '2025-01-03', 'Absent'),
	(9, 100002, 2, '2025-01-04', 'Absent'),
	(10, 100002, 2, '2025-01-05', 'Present'),
	(11, 100001, 3, '2025-01-01', 'Present'),
	(12, 100001, 3, '2025-01-02', 'Present'),
	(13, 100001, 3, '2025-01-03', 'Present'),
	(14, 100001, 3, '2025-01-04', 'Absent'),
	(15, 100001, 3, '2025-01-05', 'Absent'),
	(26, 100001, 4, '2025-12-01', 'Present'),
	(27, 100001, 4, '2025-12-02', 'Present'),
	(28, 100001, 4, '2025-12-03', 'Present'),
	(29, 100001, 4, '2025-12-04', 'Absent'),
	(30, 100001, 4, '2025-12-05', 'Present'),
	(31, 100001, 4, '2025-12-08', 'Present'),
	(32, 100001, 4, '2025-12-09', 'Present'),
	(33, 100001, 4, '2025-12-10', 'Present'),
	(34, 100001, 4, '2025-12-11', 'Present'),
	(35, 100001, 4, '2025-12-12', 'Absent'),
	(36, 100001, 4, '2025-12-15', 'Present'),
	(37, 100001, 4, '2025-12-16', 'Present'),
	(38, 100001, 4, '2025-12-17', 'Present'),
	(39, 100001, 4, '2025-12-18', 'Present'),
	(40, 100001, 4, '2025-12-19', 'Present'),
	(41, 100001, 4, '2025-12-22', 'Present'),
	(42, 100001, 4, '2025-12-23', 'Present'),
	(43, 100001, 4, '2025-12-24', 'Absent'),
	(44, 100001, 4, '2025-12-26', 'Present'),
	(45, 100001, 4, '2025-12-29', 'Present'),
	(46, 100001, 4, '2025-12-30', 'Present'),
	(47, 100001, 4, '2025-12-31', 'Absent'),
	(48, 100001, 4, '2026-01-01', 'Absent'),
	(49, 100001, 4, '2026-01-02', 'Present'),
	(50, 100001, 4, '2026-01-03', 'Absent'),
	(51, 100001, 4, '2026-01-04', 'Absent'),
	(53, 100001, 3, '2026-01-05', 'Present'),
	(54, 100001, 4, '2026-01-05', 'Present'),
	(55, 100001, 1, '2025-12-10', 'Present'),
	(56, 100001, 1, '2025-12-11', 'Present'),
	(57, 100001, 1, '2025-12-12', 'Present'),
	(58, 100001, 1, '2025-12-13', 'Absent'),
	(59, 100001, 1, '2025-12-14', 'Present'),
	(60, 100001, 1, '2025-12-15', 'Present'),
	(61, 100001, 1, '2025-12-16', 'Present'),
	(62, 100001, 3, '2026-01-06', 'Present'),
	(63, 100001, 4, '2026-01-06', 'Present');
/*!40000 ALTER TABLE "attendance" ENABLE KEYS */;

-- Dumping structure for table internship.domain_skills
CREATE TABLE IF NOT EXISTS domain_skills (
    domain TEXT NOT NULL,
    skill_id INTEGER NOT NULL,
    FOREIGN KEY (skill_id) REFERENCES skills(skill_id),
    UNIQUE(domain, skill_id)
);
;

-- Dumping data for table internship.domain_skills: -1 rows
/*!40000 ALTER TABLE "domain_skills" DISABLE KEYS */;
INSERT INTO "domain_skills" ("domain", "skill_id") VALUES
	('AI', 1),
	('Backend Development', 1),
	('Backend Development', 2),
	('Backend Development', 3),
	('Web Development', 7);
/*!40000 ALTER TABLE "domain_skills" ENABLE KEYS */;

-- Dumping structure for table internship.evidence_attachments
CREATE TABLE IF NOT EXISTS evidence_attachments (
    attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (report_id) REFERENCES weekly_reports(report_id) ON DELETE CASCADE
);

-- Dumping data for table internship.evidence_attachments: -1 rows
/*!40000 ALTER TABLE "evidence_attachments" DISABLE KEYS */;
/*!40000 ALTER TABLE "evidence_attachments" ENABLE KEYS */;

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

-- Dumping data for table internship.internship: -1 rows
/*!40000 ALTER TABLE "internship" DISABLE KEYS */;
INSERT INTO "internship" ("internship_id", "user_id", "title", "domain", "weeks", "start_date", "end_date", "supervisor_id", "location_name", "location_type", "supervisor_title", "supervisor_department") VALUES
	(1, 100001, 'Web Development Intern', 'Web Development', 11, '2025-10-01', '2025-12-15', 100003, 'TechHub Innovation Center', 'San Francisco, CA (Hybrid)', 'Senior Software Engineer', 'Web Engineering'),
	(2, 100002, 'Data Science Intern', 'Data Science', 11, '2025-10-01', '2025-12-15', 100004, 'DataLabs HQ', 'New York, NY (Onsite)', 'Senior Data Scientist', 'Data Analytics'),
	(3, 100001, 'Artifical Intelligence Intern', 'AI', 11, '2025-12-01', '2026-02-15', 100004, 'AI Research Campus', 'Remote (Global)', 'Research Scientist', 'AI Research'),
	(4, 100001, 'Backend Systems Intern', 'Backend Development', 9, '2025-12-01', '2026-02-02', 100004, 'Backend Systems Office', 'Austin, TX (Hybrid)', 'Senior Backend Engineer', 'Platform Engineering');
/*!40000 ALTER TABLE "internship" ENABLE KEYS */;

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

-- Dumping data for table internship.ml_results: -1 rows
/*!40000 ALTER TABLE "ml_results" DISABLE KEYS */;
INSERT INTO "ml_results" ("result_id", "user_id", "internship_id", "predicted_score", "risk_level", "recommendation", "created_at") VALUES
	(5, 100001, 4, 57.71, 'Medium', 'Needs improvement', '2026-01-05 14:15:12');
/*!40000 ALTER TABLE "ml_results" ENABLE KEYS */;

-- Dumping structure for table internship.skills
CREATE TABLE IF NOT EXISTS skills (
    skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
;

-- Dumping data for table internship.skills: -1 rows
/*!40000 ALTER TABLE "skills" DISABLE KEYS */;
INSERT INTO "skills" ("skill_id", "name") VALUES
	(1, 'Python Programming'),
	(2, 'Backend Systems'),
	(3, 'System Design'),
	(4, 'Full Stack'),
	(5, 'Databases'),
	(6, 'Communication'),
	(7, 'Full Stack web development');
/*!40000 ALTER TABLE "skills" ENABLE KEYS */;

-- Dumping structure for table internship.supervisor_details
CREATE TABLE IF NOT EXISTS supervisor_details (
    user_id INTEGER PRIMARY KEY,
    employee_id TEXT,
    designation TEXT,
    department TEXT,
    organization TEXT, experience_years INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Dumping data for table internship.supervisor_details: -1 rows
/*!40000 ALTER TABLE "supervisor_details" DISABLE KEYS */;
INSERT INTO "supervisor_details" ("user_id", "employee_id", "designation", "department", "organization", "experience_years") VALUES
	(100003, 'SUP-1003', 'Senior AI Engineer', 'Artificial Intelligence & Data Science', 'TechNova Solutions', 10),
	(100004, 'SUP-1006', 'Company Supervisor', 'Engineering', 'Internal Training Division', 20);
/*!40000 ALTER TABLE "supervisor_details" ENABLE KEYS */;

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

-- Dumping data for table internship.user_details: -1 rows
/*!40000 ALTER TABLE "user_details" DISABLE KEYS */;
INSERT INTO "user_details" ("user_id", "first_name", "last_name", "email", "phone_number", "department", "avatar_url") VALUES
	(100001, 'Jane', 'Doe', 'abc@exmaple.com', '1234567890', 'Computer Science', 'http://localhost:5000/static/avatars/avatar2.png'),
	(100002, 'ghi', 'jkl', 'ghi@exmaple.com', '987564321', 'Artificial Intelligence & Data Science\', 'http://localhost:5000/static/avatars/avatar3.png'),
	(100003, 'mno', 'qrs', 'mno@example.com', '135792468', NULL, NULL),
	(100004, 'Test', 'Supervisor', 'test.supervisor@example.com', '987654321', NULL, 'http://localhost:5000/static/avatars/avatar6.png');
/*!40000 ALTER TABLE "user_details" ENABLE KEYS */;

-- Dumping structure for table internship.users
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    password TEXT NOT NULL,
    role TEXT NOT NULL
        CHECK (role IN ('intern', 'supervisor'))
, password_updated_at DATE);

-- Dumping data for table internship.users: -1 rows
/*!40000 ALTER TABLE "users" DISABLE KEYS */;
INSERT INTO "users" ("user_id", "password", "role", "password_updated_at") VALUES
	(100001, '$argon2id$v=19$m=65536,t=3,p=4$iekaSTrOEcLtMsTrd4mIQw$Yn6feFqmWHmBa1lIjQe/aRltux8ofedYwjmvu3bx3SM', 'intern', '2026-01-05'),
	(100002, '$argon2id$v=19$m=65536,t=3,p=4$s1LfJJQaVen3hz82xSQTjg$lm5SzHmvRifpO0+48Xy0K86E7x5LAEJ3R6qhuiSz5NM', 'intern', '2026-01-02'),
	(100003, '$argon2id$v=19$m=65536,t=3,p=4$tvX2mvQVMKIt9WPXIlw2og$U9N1vI1Su4DtUJP+lrk5eatAouO3LV95ulFVS8lYFAc', 'supervisor', '2026-01-02'),
	(100004, '$argon2id$v=19$m=65536,t=3,p=4$Hn1LXCqq8c+sZa6PXDiCFQ$IDW4FVx99yevAWXCYiM/zx90XF60dyOFPwCsDNLu8gY', 'supervisor', '2026-01-05');
/*!40000 ALTER TABLE "users" ENABLE KEYS */;

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

-- Dumping data for table internship.weekly_reports: -1 rows
/*!40000 ALTER TABLE "weekly_reports" DISABLE KEYS */;
INSERT INTO "weekly_reports" ("report_id", "user_id", "internship_id", "week_number", "attendance_percentage", "task_description", "focus_skill", "skill_rating", "stress_level", "self_evaluation", "challenges", "next_week_priorities", "evidence_link", "submitted_at", "status", "supervisor_feedback", "reviewed_at") VALUES
	(2, 100001, 4, 1, 75, 'Onboarding, environment setup, understanding project scope.', 'Python Programming', 6, 4, 'Getting familiar with tools and workflow.', 'Initial setup took longer than expected.', 'Complete setup and start first task.', NULL, '2025-12-30 03:58:46', 'submitted', NULL, NULL),
	(3, 100001, 4, 2, 80, 'Implemented basic CRUD features and fixed minor bugs.', 'Backend Systems', 7, 4, 'More confident with the backend stack.', 'Understanding legacy code.', 'Improve code quality and testing.', NULL, '2025-12-30 03:58:46', 'submitted', NULL, NULL),
	(4, 100001, 4, 3, 80, 'Worked on attendance module and optimized queries.', 'Databases', 7, 3, 'Productivity improved this week.', 'Handling edge cases.', 'Refactor attendance logic.', NULL, '2025-12-30 03:58:46', 'submitted', NULL, NULL),
	(5, 100001, 4, 4, 85, 'Integrated weekly report feature and fixed UI bugs.', 'Full Stack', 8, 3, 'Able to independently solve most issues.', 'Minor UI inconsistencies.', 'Polish UI and improve validation.', NULL, '2025-12-30 03:58:46', 'reviewed', 'Good', '2026-01-05 09:20:47'),
	(20, 100001, 1, 11, 86, 'Worked on building and refining the internship management system dashboard. Implemented responsive UI components using HTML, CSS, and Bootstrap. Integrated frontend forms with Flask backend routes and handled form validation. Fixed bugs related to weekly report submission, attendance calculation, and supervisor feedback rendering. Improved page loading performance by optimizing SQL queries and reducing redundant database calls.', 'Full Stack web development', 7, 3, 'I was able to complete most of the assigned tasks within the planned timeline. I gained better understanding of Flask routing, Jinja templating, and database relationships. I also improved my debugging skills by resolving backend logic and UI rendering issues. Overall, I feel more confident working independently on both frontend and backend tasks.', 'Faced difficulties in correctly calculating weekly attendance percentages and handling edge cases in SQL queries. Debugging template rendering issues in Jinja took additional time. Coordinating data flow between multiple tables also required careful testing and validation.', 'Finalize supervisor performance and analytics pages

Improve UI consistency across all dashboard pages

Add form validation and error handling for edge cases

Optimize database queries for better performance

Begin testing the system with dummy users and data', 'https://example.com', '2026-01-05 12:22:33', 'submitted', NULL, NULL),
	(28, 100001, 4, 5, 43, 'dgfhkjl;.', 'Backend Systems', 6, 3, 'dfhjkl', 'sdafgsdcxsdagferqwads', 'asfdrwasfas', 'https://example.com', '2026-01-05 14:39:38', 'submitted', NULL, NULL);
/*!40000 ALTER TABLE "weekly_reports" ENABLE KEYS */;

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
