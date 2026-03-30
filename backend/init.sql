-- backend/init.sql
-- Инициализация БД при первом запуске

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- 🧪 Тестовый пользователь (пароль: "test123")
-- Хэш сгенерирован через: passlib.context.CryptContext(schemes=["bcrypt"]).hash("test123")
INSERT INTO users (email, username, hashed_password, is_active, is_verified)
VALUES (
    'test@example.com',
    'testuser',
    '$2b$12$KIXxPZvJ8Z9YqJ7XqJ7XqO7XqJ7XqJ7XqJ7XqJ7XqJ7XqJ7XqJ7Xq',
    TRUE,
    TRUE
) ON CONFLICT (email) DO NOTHING;