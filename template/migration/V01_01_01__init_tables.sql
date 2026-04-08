-- Create admin table
CREATE TABLE IF NOT EXISTS `tbl_admin` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(100) NOT NULL,
  `nickname` varchar(100) NOT NULL,
  `passwordHash` varchar(255) NOT NULL,
  `email` varchar(255) DEFAULT NULL,
  `isActive` tinyint(1) NOT NULL DEFAULT '1',
  `createTime` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updateTime` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert a default admin user (username: admin, password: admin123)
-- Password hash for 'admin123' using bcrypt
INSERT INTO `tbl_admin` (`username`, `nickname`, `passwordHash`, `email`, `isActive`)
VALUES ('admin', 'admin', '$2b$12$v6chAeyP1IGcSNezreG/cuuyH412zxkaxOtXwMI.t7/npPzDR1EiG', 'admin@example.com', 1);
