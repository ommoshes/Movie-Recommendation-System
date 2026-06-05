import pandas as pd
from sqlalchemy import create_engine, text

# 创建MySQL引擎（替换为你的MySQL配置）
engine = create_engine('mysql+mysqlconnector://root:**********@localhost/movies_db')

# 读取movies.csv（确保文件在项目文件夹中）
# movies = pd.read_csv('movies.csv')
ratings=pd.read_csv('ratings.csv')
# 将DataFrame插入movies表（if_exists='replace'会覆盖现有表）
# movies.to_sql('movies', engine, if_exists='replace', index=False)
ratings.to_sql('ratings', engine, if_exists='replace', index=False)
# print("电影数据导入成功！")
print("评分数据导入成功！")
