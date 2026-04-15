CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    first_name TEXT,
    last_name TEXT,
    phone TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_admin BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    concern TEXT,
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quizzes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT NOT NULL,
    questions TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS quiz_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    quiz_id INTEGER,
    answers TEXT NOT NULL,
    score INTEGER,
    results TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (quiz_id) REFERENCES quizzes (id)
);

CREATE TABLE IF NOT EXISTS user_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE,
    assessments_completed INTEGER DEFAULT 0,
    chat_sessions INTEGER DEFAULT 0,
    meditation_minutes INTEGER DEFAULT 0,
    last_login TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

-- Create a view for user profile data including stats
CREATE VIEW IF NOT EXISTS user_profiles AS
SELECT 
    u.id, u.username, u.email, u.first_name, u.last_name, u.phone, u.created_at,
    COALESCE(s.assessments_completed, 0) as assessments_completed,
    COALESCE(s.chat_sessions, 0) as chat_sessions,
    COALESCE(s.meditation_minutes, 0) as meditation_minutes,
    s.last_login
FROM users u
LEFT JOIN user_stats s ON u.id = s.user_id; 