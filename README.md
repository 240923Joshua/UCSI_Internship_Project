# Internship Management System

## 📌 Project Overview

The **Internship Management System** is a web-based application built using **Flask** that streamlines the interaction between **interns** and **supervisors**. It enables structured weekly reporting, attendance tracking, skill evaluation, and performance monitoring throughout an internship period.

This system was developed as part of an academic internship project to demonstrate full-stack development, database design, and role-based access control.

---

## 🎯 Objectives

* Digitize internship progress tracking
* Enable supervisors to monitor intern performance effectively
* Provide interns with structured weekly reporting
* Ensure secure authentication and role-based access

---

## 👥 User Roles

### 👨‍🎓 Intern

* Login & profile management
* Submit weekly reports
* View report history
* Track internship progress
* View attendance percentage
* Manage skills and self-evaluations

### 👨‍🏫 Supervisor

* Login & profile management
* View assigned interns
* Review weekly reports
* Provide feedback
* Monitor intern performance analytics

---

## 🧱 Tech Stack

### Backend

* Python
* Flask
* SQLite3

### Frontend

* HTML5
* CSS3
* Jinja2 Templates

### Security

* Password hashing
* Flask sessions
* Role-based routing

### Additional Modules

* AI / ML modules for extensibility (`llm.py`, `ml_prediction.py`)

---

## 🗂️ Project Structure

```
UCSI_Internship_Project/
│── app.py                  # Main Flask application
│── db.py                   # Database connection handler
│── finalschema.sql         # Database schema
│── hasher.py               # Password hashing utilities
│── requirements.txt        # Project dependencies
│── README.md               # Project documentation
│
├── static/                 # Static assets
│   ├── ai/                 # AI avatar images/videos
│   └── css/js/images
│
├── templates/
│   ├── intern/             # Intern-related templates
│   └── supervisor/         # Supervisor-related templates
```

---

## 🗄️ Database Design

* Normalized relational schema
* Foreign key relationships
* Weekly report uniqueness per intern per week
* Attendance and performance tracking

Schema file: `finalschema.sql`

---

## ▶️ How to Run the Project

### 1️⃣ Clone the Repository

```bash
git clone <repository-url>
cd UCSI_Internship_Project
```

### 2️⃣ Create Virtual Environment (Optional but Recommended)

```bash
python -m venv venv
venv\Scripts\activate   # Windows
source venv/bin/activate # macOS/Linux
```

### 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Initialize Database

```bash
sqlite3 internship.db < finalschema.sql
```

### 5️⃣ Run the Application

```bash
python app.py
```

Open browser and navigate to:

```
http://127.0.0.1:5000/
```

---

## 🔐 Security Considerations

* Passwords are securely hashed before storage
* Session-based authentication
* Role-based access prevents unauthorized page access

---

## 🚀 Future Enhancements

* Modular routing using Flask Blueprints
* Deployment using Docker
* Replace SQLite with PostgreSQL/MySQL
* Advanced analytics dashboards
* Expanded AI-based performance insights

---

## 📌 Notes

* SQLite database file (`.db`) is intentionally excluded from version control
* AI modules are included as enhancements and are not core dependencies

---

## ✅ Conclusion

This project demonstrates a complete end-to-end internship management workflow with clean architecture, secure authentication, and practical feature implementation suitable for academic evaluation and future scalability.

---

**Project Type:** Academic / Internship Project
