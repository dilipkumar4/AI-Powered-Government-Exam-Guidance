
Schema · SQL
-- =========================================================
-- Module 2: Student Profile - Database Schema
-- Links to the users table created in Module 1
-- =========================================================
 
CREATE DATABASE IF NOT EXISTS puducherry_portal;
USE puducherry_portal;
 
-- Module 1 table (reference only - assumed already created)
-- CREATE TABLE users (
--     user_id INT AUTO_INCREMENT PRIMARY KEY,
--     name VARCHAR(100),
--     email VARCHAR(150) UNIQUE,
--     mobile VARCHAR(15),
--     password VARCHAR(255),
--     date_of_birth DATE,
--     qualification VARCHAR(100)
-- );
 
-- Module 2: Student Profile table
CREATE TABLE IF NOT EXISTS student_profile (
    profile_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    age INT,
    qualification VARCHAR(100),
    skills VARCHAR(255),
    preferred_department VARCHAR(100),
    preferred_job_type VARCHAR(50),
    available_study_hours DECIMAL(4,1),
    target_recruitment VARCHAR(150),
    preparation_level ENUM('Beginner', 'Intermediate', 'Advanced') DEFAULT 'Beginner',
    preferred_language VARCHAR(50) DEFAULT 'English',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
 
