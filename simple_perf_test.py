"""
简化版性能测试
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, get_db


def test_response_times():
    """测试接口响应时间"""
    app.config['TESTING'] = True
    client = app.test_client()
    
    print("=" * 60)
    print("电影推荐系统 - 简化性能测试")
    print("=" * 60)
    
    # 测试首页
    print("\n【1. 首页响应时间】")
    times = []
    for i in range(10):
        start = time.time()
        response = client.get('/')
        end = time.time()
        times.append((end - start) * 1000)
    avg_time = sum(times) / len(times)
    print(f"  平均: {avg_time:.2f}ms")
    print(f"  范围: {min(times):.2f}ms - {max(times):.2f}ms")
    
    # 评价
    if avg_time < 100:
        eval_result = "优秀"
    elif avg_time < 300:
        eval_result = "良好"
    elif avg_time < 500:
        eval_result = "一般"
    else:
        eval_result = "需优化"
    print(f"  评价: {eval_result}")
    
    # 测试搜索
    print("\n【2. 搜索响应时间】")
    times = []
    for i in range(10):
        start = time.time()
        response = client.get('/search?q=action')
        end = time.time()
        times.append((end - start) * 1000)
    avg_time = sum(times) / len(times)
    print(f"  平均: {avg_time:.2f}ms")
    print(f"  范围: {min(times):.2f}ms - {max(times):.2f}ms")
    
    if avg_time < 100:
        eval_result = "优秀"
    elif avg_time < 300:
        eval_result = "良好"
    elif avg_time < 500:
        eval_result = "一般"
    else:
        eval_result = "需优化"
    print(f"  评价: {eval_result}")
    
    # 测试数据库查询
    print("\n【3. 数据库查询性能】")
    conn = get_db()
    c = conn.cursor()
    
    queries = [
        ("简单查询", "SELECT * FROM movies LIMIT 10"),
        ("聚合查询", "SELECT m.movieId, AVG(r.rating) FROM movies m LEFT JOIN ratings r ON m.movieId = r.movieId GROUP BY m.movieId LIMIT 10"),
        ("搜索查询", "SELECT * FROM movies WHERE title LIKE '%action%' LIMIT 40")
    ]
    
    for name, query in queries:
        times = []
        for _ in range(5):
            start = time.time()
            c.execute(query)
            c.fetchall()
            end = time.time()
            times.append((end - start) * 1000)
        avg = sum(times) / len(times)
        print(f"  {name}: {avg:.2f}ms")
    
    c.close()
    conn.close()
    
    print("\n【4. 性能评估标准】")
    print("  响应时间:")
    print("    < 100ms  - 优秀")
    print("    100-300ms - 良好")
    print("    300-500ms - 一般")
    print("    > 500ms   - 需优化")
    
    print("\n" + "=" * 60)
    print("性能测试完成")
    print("=" * 60)


if __name__ == '__main__':
    test_response_times()
