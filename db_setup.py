"""
Database initialization and seed script for JobPost Aggregator.
Using MySQL (MariaDB) and PyMySQL.
"""
import pymysql
import json
import os
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

DB_CONFIG = {
    'host': 'localhost',
    'user': 'jobuser',
    'password': 'jobpass123',
    'database': 'jobpost_aggregator',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db_connection():
    return pymysql.connect(**DB_CONFIG)

def setup_database():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Users table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(150) NOT NULL,
                email VARCHAR(191) NOT NULL UNIQUE,
                phone VARCHAR(50),
                password_hash VARCHAR(255) NOT NULL,
                location VARCHAR(150),
                role ENUM('USER', 'ADMIN') DEFAULT 'USER',
                headline VARCHAR(255),
                bio TEXT,
                skills TEXT,
                experience_level VARCHAR(50) DEFAULT 'Fresher',
                resume_filename VARCHAR(255),
                status ENUM('ACTIVE', 'SUSPENDED') DEFAULT 'ACTIVE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # 2. Job Sources table (aggregators / platforms)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_sources (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                code VARCHAR(50) NOT NULL UNIQUE,
                base_url VARCHAR(255) NOT NULL,
                logo_icon VARCHAR(50) DEFAULT 'globe',
                color_hex VARCHAR(20) DEFAULT '#2563eb',
                is_active BOOLEAN DEFAULT TRUE,
                sync_frequency VARCHAR(50) DEFAULT 'Hourly',
                last_synced_at TIMESTAMP NULL,
                total_jobs_count INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # 3. Categories table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                slug VARCHAR(100) NOT NULL UNIQUE,
                icon VARCHAR(50) DEFAULT 'briefcase',
                job_count INT DEFAULT 0
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # 4. Companies table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(150) NOT NULL UNIQUE,
                slug VARCHAR(150) NOT NULL UNIQUE,
                logo_url VARCHAR(255),
                website VARCHAR(255),
                industry VARCHAR(100),
                location VARCHAR(150),
                description TEXT,
                company_size VARCHAR(50) DEFAULT '100-500 employees',
                rating DECIMAL(2, 1) DEFAULT 4.5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # 5. Jobs table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                slug VARCHAR(220) NOT NULL,
                company_id INT NOT NULL,
                source_id INT NOT NULL,
                category_id INT NOT NULL,
                description MEDIUMTEXT NOT NULL,
                requirements MEDIUMTEXT,
                benefits TEXT,
                skills_required VARCHAR(255),
                job_type ENUM('Full-time', 'Part-time', 'Internship', 'Contract', 'Freelance') DEFAULT 'Full-time',
                experience_level ENUM('Fresher', '1-3 years', '3-5 years', '5+ years', 'Executive') DEFAULT 'Fresher',
                work_mode ENUM('On-site', 'Remote', 'Hybrid') DEFAULT 'On-site',
                location VARCHAR(150) NOT NULL,
                salary_min INT DEFAULT NULL,
                salary_max INT DEFAULT NULL,
                salary_currency VARCHAR(10) DEFAULT 'USD',
                original_url VARCHAR(500) NOT NULL,
                is_featured BOOLEAN DEFAULT FALSE,
                is_remote BOOLEAN DEFAULT FALSE,
                is_fresher BOOLEAN DEFAULT FALSE,
                is_internship BOOLEAN DEFAULT FALSE,
                status ENUM('ACTIVE', 'EXPIRED', 'ARCHIVED') DEFAULT 'ACTIVE',
                duplicate_cluster_id INT DEFAULT NULL,
                views_count INT DEFAULT 0,
                application_count INT DEFAULT 0,
                expires_at DATE,
                posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
                FOREIGN KEY (source_id) REFERENCES job_sources(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
                INDEX idx_title (title),
                INDEX idx_location (location),
                INDEX idx_status (status),
                INDEX idx_remote (is_remote),
                INDEX idx_fresher (is_fresher),
                INDEX idx_internship (is_internship)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # 6. Saved Jobs
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS saved_jobs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                job_id INT NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_user_job (user_id, job_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # 7. Job Applications tracking
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_applications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                job_id INT NOT NULL,
                status ENUM('Applied', 'Reviewing', 'Interviewing', 'Offered', 'Rejected') DEFAULT 'Applied',
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                interview_date DATE DEFAULT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY unique_user_application (user_id, job_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # 8. Job Alerts
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_alerts (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                title VARCHAR(150) NOT NULL,
                keyword VARCHAR(150),
                location VARCHAR(150),
                category_id INT DEFAULT NULL,
                frequency ENUM('Instant', 'Daily', 'Weekly') DEFAULT 'Daily',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # 9. Job Reports
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_reports (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT DEFAULT NULL,
                job_id INT NOT NULL,
                reason VARCHAR(100) NOT NULL,
                details TEXT,
                status ENUM('Pending', 'Reviewed', 'Dismissed', 'Action_Taken') DEFAULT 'Pending',
                admin_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # 10. Notifications
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                title VARCHAR(200) NOT NULL,
                message TEXT NOT NULL,
                link VARCHAR(255) DEFAULT '/dashboard',
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # 11. Search History
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT DEFAULT NULL,
                search_term VARCHAR(200) NOT NULL,
                location VARCHAR(150),
                results_count INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            # 12. Source Sync Logs
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                source_id INT NOT NULL,
                status ENUM('SUCCESS', 'FAILED', 'PARTIAL') DEFAULT 'SUCCESS',
                jobs_fetched INT DEFAULT 0,
                new_jobs_added INT DEFAULT 0,
                duplicates_detected INT DEFAULT 0,
                message TEXT,
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES job_sources(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            conn.commit()
            print("All MySQL tables verified and created successfully.")

    finally:
        conn.close()

def seed_database():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check if already seeded
            cursor.execute("SELECT COUNT(*) AS cnt FROM users;")
            if cursor.fetchone()['cnt'] > 0:
                print("Database already seeded. Skipping initial seed.")
                return

            print("Seeding initial data into MySQL...")

            # 1. Seed Users (1 Admin, 2 Regular Users)
            admin_pwd = generate_password_hash("admin123")
            user_pwd = generate_password_hash("user123")

            cursor.execute("""
            INSERT INTO users (full_name, email, phone, password_hash, location, role, headline, bio, skills, experience_level, status)
            VALUES 
            ('Administrator', 'admin@jobpost.com', '+1 (555) 019-2834', %s, 'San Francisco, CA', 'ADMIN', 'Senior System Administrator', 'Managing JobPost Aggregator system and integrations.', 'System Administration, Python, MySQL, Security', 'Executive', 'ACTIVE'),
            ('Alex Morgan', 'alex.morgan@example.com', '+1 (555) 234-5678', %s, 'New York, NY', 'USER', 'Full-Stack Software Engineer', 'Passionate developer looking for new opportunities in Python and JavaScript.', 'Python, JavaScript, React, SQL, Flask', '1-3 years', 'ACTIVE'),
            ('Sarah Chen', 'sarah.chen@example.com', '+1 (555) 876-5432', %s, 'Seattle, WA', 'USER', 'Computer Science Graduate', 'Recent graduate actively seeking entry-level software developer roles and internships.', 'Python, Java, Data Structures, Git, Algorithms', 'Fresher', 'ACTIVE');
            """, (admin_pwd, user_pwd, user_pwd))

            # 2. Seed Job Sources
            cursor.execute("""
            INSERT INTO job_sources (name, code, base_url, logo_icon, color_hex, is_active, sync_frequency, total_jobs_count, last_synced_at)
            VALUES 
            ('TechCareers Global', 'techcareers', 'https://techcareers.example.com', 'code', '#2563eb', TRUE, 'Every 30 mins', 8, NOW()),
            ('RemoteHub Network', 'remotehub', 'https://remotehub.example.com', 'wifi', '#10b981', TRUE, 'Hourly', 6, NOW()),
            ('CampusHire Campus & Fresher', 'campushire', 'https://campushire.example.com', 'graduation-cap', '#f59e0b', TRUE, 'Daily', 5, NOW()),
            ('DevJobs Direct', 'devjobs', 'https://devjobs.example.com', 'terminal', '#8b5cf6', TRUE, 'Every 2 hours', 6, NOW()),
            ('TalentWire Aggregator', 'talentwire', 'https://talentwire.example.com', 'briefcase', '#ec4899', TRUE, 'Hourly', 5, NOW());
            """)

            # 3. Seed Categories
            cursor.execute("""
            INSERT INTO categories (name, slug, icon, job_count)
            VALUES 
            ('Software Engineering', 'software-engineering', 'code', 10),
            ('Data Science & Analytics', 'data-science-analytics', 'bar-chart', 5),
            ('Design & Creative (UI/UX)', 'design-creative', 'pen-tool', 4),
            ('DevOps & Cloud Infrastructure', 'devops-cloud', 'cloud', 3),
            ('Product & Project Management', 'product-management', 'layout', 3),
            ('Quality Assurance & Testing', 'qa-testing', 'check-circle', 2),
            ('Cybersecurity', 'cybersecurity', 'shield', 2),
            ('Marketing & Content', 'marketing-content', 'trending-up', 1);
            """)

            # 4. Seed Companies
            cursor.execute("""
            INSERT INTO companies (name, slug, logo_url, website, industry, location, description, company_size, rating)
            VALUES 
            ('TechWave Systems', 'techwave-systems', 'https://images.unsplash.com/photo-1549923746-c502d488b3ea?auto=format&fit=crop&w=120&h=120&q=80', 'https://techwave.example.com', 'Information Technology', 'San Francisco, CA', 'TechWave is an innovative enterprise software company developing AI and cloud data workflows.', '500-1000 employees', 4.8),
            ('CloudScale Labs', 'cloudscale-labs', 'https://images.unsplash.com/photo-1572021335469-31706a17aaef?auto=format&fit=crop&w=120&h=120&q=80', 'https://cloudscale.example.com', 'Cloud Infrastructure', 'Austin, TX', 'Next-generation distributed infrastructure and cloud scalability solutions.', '200-500 employees', 4.6),
            ('Nexus Data Technologies', 'nexus-data', 'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=120&h=120&q=80', 'https://nexusdata.example.com', 'Big Data & AI', 'New York, NY', 'Transforming high-frequency financial and operational data into actionable intelligence.', '100-250 employees', 4.7),
            ('PixelCraft Interactive', 'pixelcraft', 'https://images.unsplash.com/photo-1507238691740-187a5b1d37b8?auto=format&fit=crop&w=120&h=120&q=80', 'https://pixelcraft.example.com', 'Design & Digital Media', 'Los Angeles, CA', 'Award-winning digital product studio focused on human-centric mobile and web experiences.', '50-100 employees', 4.9),
            ('Apex Financial Tech', 'apex-fintech', 'https://images.unsplash.com/photo-1551836022-d5d88e9218df?auto=format&fit=crop&w=120&h=120&q=80', 'https://apexfintech.example.com', 'FinTech & Banking', 'Chicago, IL', 'Empowering global payments and secure algorithmic transaction processing.', '1000+ employees', 4.5),
            ('BioHealth AI', 'biohealth-ai', 'https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?auto=format&fit=crop&w=120&h=120&q=80', 'https://biohealth.example.com', 'HealthTech', 'Boston, MA', 'Machine learning applications accelerating clinical diagnostics and genetic data discovery.', '150-300 employees', 4.7),
            ('Starlight Robotics', 'starlight-robotics', 'https://images.unsplash.com/photo-1485827404703-89b55fcc595e?auto=format&fit=crop&w=120&h=120&q=80', 'https://starlight.example.com', 'Robotics & Hardware', 'Seattle, WA', 'Building autonomous service robots for modern logistics and warehouse operations.', '300-600 employees', 4.8);
            """)

            # 5. Seed Jobs (Rich varied dataset covering Internships, Fresher, Remote, Full-time, etc.)
            now = datetime.now()
            expires_30 = (now + timedelta(days=30)).strftime('%Y-%m-%d')
            expires_15 = (now + timedelta(days=15)).strftime('%Y-%m-%d')
            expires_60 = (now + timedelta(days=60)).strftime('%Y-%m-%d')
            past_date = (now - timedelta(days=5)).strftime('%Y-%m-%d')

            jobs_data = [
                (
                    "Python Developer (Backend & Microservices)",
                    "python-developer-backend-microservices",
                    1, 1, 1, # TechWave, TechCareers, Software Engineering
                    "We are looking for a skilled Python Developer to build high-performance backend microservices. You will architect REST and GraphQL APIs, integrate with MySQL databases, and deploy cloud containers. You will collaborate with cross-functional product teams to deliver resilient software.",
                    "Strong experience with Python, Flask, or FastAPI. Solid understanding of relational databases (MySQL/PostgreSQL), RESTful API design, and asynchronous job queues (Celery/Redis). Excellent communication skills.",
                    "Health, Dental & Vision Insurance, 401(k) matching with immediate vesting, $2,000 annual learning stipend, Flexible hybrid schedule.",
                    "Python, Flask, MySQL, Docker, REST API",
                    "Full-time", "1-3 years", "Hybrid", "San Francisco, CA",
                    95000, 125000, "USD",
                    "https://techcareers.example.com/jobs/python-dev-101",
                    True, False, False, False, "ACTIVE", expires_30
                ),
                (
                    "Python Software Engineer Intern (Summer 2026)",
                    "python-software-engineer-intern-summer-2026",
                    1, 3, 1, # TechWave, CampusHire, Software Engineering
                    "Join our engineering team for an intensive, high-impact summer internship! Work alongside senior mentors to build production features using Python, automated unit tests, and MySQL data pipelines. Ideal for enrolled computer science students.",
                    "Currently pursuing a Bachelor's or Master's in Computer Science or related field. Proficiency in Python. Understanding of data structures, basic algorithms, and web fundamentals.",
                    "Competitive hourly compensation ($45/hr), Housing assistance, 1-on-1 mentorship, Potential return offer for full-time graduate role.",
                    "Python, Git, SQL, Problem Solving, Web Basics",
                    "Internship", "Fresher", "On-site", "San Francisco, CA",
                    50000, 65000, "USD",
                    "https://campushire.example.com/internships/python-techwave-2026",
                    True, False, True, True, "ACTIVE", expires_60
                ),
                (
                    "Senior Remote Python & Cloud Architect",
                    "senior-remote-python-cloud-architect",
                    2, 2, 1, # CloudScale, RemoteHub, Software Engineering
                    "CloudScale Labs is seeking an experienced Python Developer to lead backend services for our globally distributed multi-region cloud platform. Fully remote role with asynchronous team collaboration.",
                    "5+ years professional experience building distributed systems in Python. Deep mastery of MySQL tuning, concurrency, cloud microservices, and CI/CD pipelines.",
                    "100% remote anywhere in North America / Europe, Unlimited PTO, Home office equipment reimbursement ($1,500), Comprehensive medical coverage.",
                    "Python, Distributed Systems, MySQL, Kubernetes, AWS",
                    "Full-time", "5+ years", "Remote", "Remote - Worldwide",
                    145000, 185000, "USD",
                    "https://remotehub.example.com/jobs/remote-python-architect",
                    True, True, False, False, "ACTIVE", expires_30
                ),
                (
                    "Junior Web Developer (Fresher Friendly)",
                    "junior-web-developer-fresher-friendly",
                    4, 3, 1, # PixelCraft, CampusHire, Software Engineering
                    "Exciting entry-level opportunity for recent graduates and self-taught developers! Assist in building clean, responsive web user interfaces using HTML, CSS, JavaScript, and connecting with backend Python APIs.",
                    "Knowledge of HTML5, CSS3, JavaScript (ES6+). Familiarity with basic backend concepts (Python/Flask or Node). Strong willingness to learn and creative attention to UI detail.",
                    "Comprehensive onboarding mentorship, Wellness allowance, Flexible work hours, Rapid career advancement opportunities.",
                    "HTML5, CSS3, JavaScript, Responsive Design, Python",
                    "Full-time", "Fresher", "On-site", "Los Angeles, CA",
                    60000, 75000, "USD",
                    "https://campushire.example.com/jobs/junior-web-dev-pixelcraft",
                    False, False, True, False, "ACTIVE", expires_30
                ),
                (
                    "UI/UX Product Designer",
                    "ui-ux-product-designer",
                    4, 5, 3, # PixelCraft, TalentWire, Design & Creative
                    "PixelCraft Interactive is looking for a creative UI/UX Designer to craft beautiful, intuitive web and mobile experiences. You will design user flows, wireframes, interactive prototypes, and collaborate directly with engineers.",
                    "2+ years of UI/UX design experience. High proficiency in Figma, design systems, usability testing, and responsive grid layouts. Understanding of modern HTML/CSS constraints.",
                    "Competitive base salary + equity options, 4 weeks paid vacation, Apple hardware setup of your choice, Conference travel budget.",
                    "Figma, UI Design, Wireframing, UX Research, Design Systems",
                    "Full-time", "1-3 years", "Hybrid", "Los Angeles, CA",
                    85000, 115000, "USD",
                    "https://talentwire.example.com/design/ui-ux-pixelcraft",
                    True, False, False, False, "ACTIVE", expires_15
                ),
                (
                    "Data Analyst - Business Intelligence",
                    "data-analyst-business-intelligence",
                    3, 1, 2, # Nexus Data, TechCareers, Data Science
                    "Nexus Data Technologies is hiring a Data Analyst to analyze large-scale business metrics, build interactive dashboards, execute complex SQL queries, and deliver strategic recommendations to leadership.",
                    "Bachelor's degree in Analytics, Statistics, or CS. Proficiency in SQL (MySQL/PostgreSQL), Python (Pandas), and visualization tools (Tableau, PowerBI). Strong analytical mindset.",
                    "Annual performance bonus, 401k with 5% match, Medical/Dental/Vision, Professional certification sponsorship.",
                    "SQL, Python, Data Visualization, Excel, Statistics",
                    "Full-time", "1-3 years", "Hybrid", "New York, NY",
                    80000, 105000, "USD",
                    "https://techcareers.example.com/jobs/data-analyst-nexus",
                    False, False, False, False, "ACTIVE", expires_30
                ),
                (
                    "Data Science Intern (Remote)",
                    "data-science-intern-remote",
                    6, 2, 2, # BioHealth AI, RemoteHub, Data Science
                    "BioHealth AI has an open internship for aspiring data scientists. Work on machine learning exploratory data analysis, clean biomedical datasets, and evaluate predictive model metrics.",
                    "Current student or recent graduate in STEM. Solid foundations in Python, NumPy, Pandas, Scikit-learn, and basic machine learning concepts.",
                    "Monthly stipend of $4,000, flexible remote hours, direct mentorship by Ph.D. research scientists.",
                    "Python, Machine Learning, Pandas, Scikit-learn, SQL",
                    "Internship", "Fresher", "Remote", "Remote - US/Canada",
                    48000, 55000, "USD",
                    "https://remotehub.example.com/internships/data-science-biohealth",
                    True, True, True, True, "ACTIVE", expires_60
                ),
                (
                    "Java Backend Engineer",
                    "java-backend-engineer",
                    5, 4, 1, # Apex FinTech, DevJobs, Software Engineering
                    "Apex Financial Tech is seeking an experienced Java Backend Engineer to develop high-throughput transaction processing microservices and fraud detection engines.",
                    "3+ years experience with Java 17+, Spring Boot, Hibernate, MySQL, and Kafka. Experience with high-reliability financial systems is a huge plus.",
                    "Target bonus of 15%, 25 days paid time off, comprehensive family healthcare, tuition reimbursement.",
                    "Java, Spring Boot, MySQL, Kafka, Microservices",
                    "Full-time", "3-5 years", "On-site", "Chicago, IL",
                    120000, 150000, "USD",
                    "https://devjobs.example.com/jobs/java-engineer-apex",
                    False, False, False, False, "ACTIVE", expires_30
                ),
                (
                    "DevOps & Site Reliability Engineer (Remote)",
                    "devops-site-reliability-engineer-remote",
                    2, 2, 4, # CloudScale, RemoteHub, DevOps
                    "Help us scale infrastructure reliability across tens of thousands of container nodes. Manage Kubernetes clusters, Terraform infrastructure-as-code, and automated observability.",
                    "Strong background with Linux, Docker, Kubernetes, Terraform, and Python or Bash scripting. Experience with MySQL replication and backup automation.",
                    "Full remote flexibility, $3,000 workspace budget, quarterly company retreats, comprehensive insurance.",
                    "Kubernetes, Docker, Terraform, CI/CD, Linux, Python",
                    "Full-time", "3-5 years", "Remote", "Remote - Global",
                    130000, 165000, "USD",
                    "https://remotehub.example.com/jobs/devops-sre-cloudscale",
                    True, True, False, False, "ACTIVE", expires_30
                ),
                (
                    "Robotics Software Engineer (Fresher / Graduate)",
                    "robotics-software-engineer-fresher-graduate",
                    7, 3, 1, # Starlight Robotics, CampusHire, Software Engineering
                    "Kickstart your career in autonomous robotics! Starlight Robotics is seeking eager graduate engineers to develop path planning algorithms and robot operating system nodes.",
                    "Degree in Robotics, Mechatronics, or Computer Science. Proficiency in C++ or Python. Familiarity with ROS (Robot Operating System) and Linux.",
                    "Full healthcare, relocation assistance, generous stock options, catered daily lunches.",
                    "Python, C++, ROS, Linux, Computer Vision",
                    "Full-time", "Fresher", "On-site", "Seattle, WA",
                    90000, 110000, "USD",
                    "https://campushire.example.com/jobs/robotics-fresher-starlight",
                    False, False, True, False, "ACTIVE", expires_30
                ),
                (
                    "QA Automation Engineer",
                    "qa-automation-engineer",
                    5, 4, 6, # Apex FinTech, DevJobs, QA Testing
                    "Build automated end-to-end and regression test suites for critical banking APIs and web portals. Write maintainable test scripts using Python and Selenium/Playwright.",
                    "2+ years experience in automated testing. Experience with Python, PyTest, Selenium, API testing (Postman), and MySQL database verification.",
                    "Competitive salary, annual bonus, flexible hybrid working schedule, comprehensive health insurance.",
                    "Python, Selenium, PyTest, API Testing, MySQL",
                    "Full-time", "1-3 years", "Hybrid", "Chicago, IL",
                    85000, 105000, "USD",
                    "https://devjobs.example.com/jobs/qa-automation-apex",
                    False, False, False, False, "ACTIVE", expires_30
                ),
                (
                    "Product Manager - Cloud Platforms",
                    "product-manager-cloud-platforms",
                    2, 5, 5, # CloudScale, TalentWire, Product Management
                    "Drive the product vision and roadmap for developer platform tooling. Partner with engineering leads to define specifications, analyze developer metrics, and launch cloud features.",
                    "3+ years in technical product management for software or cloud developer tools. Excellent data-driven decision making and stakeholder leadership.",
                    "Competitive base + equity, annual performance bonus, top-tier healthcare, remote work support.",
                    "Product Management, Agile, User Stories, Roadmap, Cloud Tech",
                    "Full-time", "3-5 years", "Hybrid", "Austin, TX",
                    125000, 160000, "USD",
                    "https://talentwire.example.com/product/pm-cloud-scale",
                    False, False, False, False, "ACTIVE", expires_30
                ),
                (
                    "Duplicate Demo: Python Backend Engineer",
                    "duplicate-demo-python-backend-engineer",
                    1, 5, 1, # TechWave, TalentWire, Software Engineering
                    "TechWave is looking for a skilled Python Developer to build high-performance backend microservices. You will architect REST and GraphQL APIs, integrate with MySQL databases, and deploy cloud containers.",
                    "Strong experience with Python, Flask, or FastAPI. Solid understanding of relational databases (MySQL/PostgreSQL), RESTful API design.",
                    "Health, Dental & Vision Insurance, 401(k) matching.",
                    "Python, Flask, MySQL, Docker, REST API",
                    "Full-time", "1-3 years", "Hybrid", "San Francisco, CA",
                    95000, 125000, "USD",
                    "https://talentwire.example.com/jobs/python-dev-cross-post",
                    False, False, False, False, "ACTIVE", expires_30
                )
            ]

            for job in jobs_data:
                cursor.execute("""
                INSERT INTO jobs (
                    title, slug, company_id, source_id, category_id, description, requirements, benefits,
                    skills_required, job_type, experience_level, work_mode, location, salary_min, salary_max,
                    salary_currency, original_url, is_featured, is_remote, is_fresher, is_internship,
                    status, expires_at, posted_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, NOW()
                )
                """, job)

            # Update duplicate cluster for demo
            # Job 1 and Job 13 are duplicate cross-posts from different sources
            cursor.execute("UPDATE jobs SET duplicate_cluster_id = 1 WHERE id IN (1, 13);")

            # Update source total job counts
            cursor.execute("""
            UPDATE job_sources js 
            SET total_jobs_count = (SELECT COUNT(*) FROM jobs j WHERE j.source_id = js.id);
            """)

            # Update category job counts
            cursor.execute("""
            UPDATE categories c 
            SET job_count = (SELECT COUNT(*) FROM jobs j WHERE j.category_id = c.id);
            """)

            # 6. Seed User Sample Saved Job & Application for Alex Morgan (user_id = 2)
            cursor.execute("""
            INSERT INTO saved_jobs (user_id, job_id, notes)
            VALUES (2, 1, 'Applied via original source page. Follow up next Monday.');
            """)

            cursor.execute("""
            INSERT INTO job_applications (user_id, job_id, status, notes)
            VALUES (2, 1, 'Interviewing', 'Initial technical phone screen scheduled for Thursday.');
            """)

            # 7. Seed Job Alert for Alex
            cursor.execute("""
            INSERT INTO job_alerts (user_id, title, keyword, location, category_id, frequency)
            VALUES (2, 'Python Remote Jobs', 'Python', 'Remote', 1, 'Daily');
            """)

            # 8. Seed Notification for Alex
            cursor.execute("""
            INSERT INTO notifications (user_id, title, message, link)
            VALUES 
            (2, 'Welcome to JobPost Aggregator', 'Discover aggregated jobs across top sources and set up career alerts.', '/dashboard'),
            (2, 'New Job Match Found', '3 new Python Developer positions matched your alert criteria.', '/jobs?q=Python');
            """)

            # 9. Seed Search History
            cursor.execute("""
            INSERT INTO search_history (user_id, search_term, location, results_count)
            VALUES 
            (2, 'Python Developer', 'San Francisco', 4),
            (2, 'Remote Python', 'Remote', 3),
            (3, 'Internship', 'Seattle', 2);
            """)

            # 10. Seed Sync Logs
            cursor.execute("""
            INSERT INTO sync_logs (source_id, status, jobs_fetched, new_jobs_added, duplicates_detected, message)
            VALUES 
            (1, 'SUCCESS', 15, 8, 1, 'Completed synchronization from TechCareers REST endpoint.'),
            (2, 'SUCCESS', 12, 6, 0, 'Fetched remote positions successfully.'),
            (3, 'SUCCESS', 8, 5, 0, 'Campus job feeds synchronized successfully.');
            """)

            conn.commit()
            print("Database seeding completed successfully!")

    finally:
        conn.close()

if __name__ == '__main__':
    setup_database()
    seed_database()
