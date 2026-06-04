import mysql.connector

# 连接MySQL
conn = mysql.connector.connect(
    host="localhost",    
    user="root",           
    password="************",    
    database="movies_db"
)

c = conn.cursor()

# c.execute("CREATE DATABASE `movies_db`")
# c.execute("show databases;")
# records=c.fetchall()
# for record in records:
#     print(record)

# 1. 用户表
# c.execute('''CREATE TABLE `users` (
#     id INT AUTO_INCREMENT PRIMARY KEY,
#     username VARCHAR(50) UNIQUE NOT NULL,
#     password VARCHAR(50) NOT NULL
# )''')
#
# # 2. 电影表
# c.execute('''CREATE TABLE movies (
#     movieId INT AUTO_INCREMENT PRIMARY KEY,
#     title VARCHAR(255) NOT NULL,
#     genres VARCHAR(100) NOT NULL
# )''')

# 3. 评分表
c.execute('''CREATE TABLE `rating` (
    user_id INT NOT NULL,
    movie_id INT NOT NULL,
    rating INT NOT NULL,  -- 用户评分（1-5星）
    timestamp BIGINT NOT NULL,  -- 评分时间戳（MovieLens 数据格式）
    PRIMARY KEY (user_id, movie_id),  -- 联合主键（用户对同一电影的评分唯一）
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (movie_id) REFERENCES movies(movieId)
)''')

conn.commit()
conn.close()

