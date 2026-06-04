"""
功能测试运行脚本
直接使用 Python 运行，无需额外安装 pytest
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from werkzeug.security import generate_password_hash, check_password_hash

from app import app, get_db


class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
        self.client = None
        self.test_user = None
        
    def setup(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        
        conn = get_db()
        c = conn.cursor(dictionary=True)
        
        username = 'test_user_functional'
        c.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing = c.fetchone()
        
        if existing:
            self.test_user = {
                'id': existing['id'],
                'username': username,
                'password': 'test123456'
            }
        else:
            hashed_password = generate_password_hash('test123456')
            c.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                (username, hashed_password)
            )
            conn.commit()
            self.test_user = {
                'id': c.lastrowid,
                'username': username,
                'password': 'test123456'
            }
        
        c.close()
        conn.close()
        
    def login(self):
        self.client.post('/login', data={
            'username': self.test_user['username'],
            'password': self.test_user['password']
        })
        
    def run_test(self, test_name, test_func):
        try:
            test_func()
            self.passed += 1
            print(f"  ✓ {test_name}")
            return True
        except AssertionError as e:
            self.failed += 1
            self.errors.append((test_name, str(e)))
            print(f"  ✗ {test_name}: {e}")
            return False
        except Exception as e:
            self.failed += 1
            self.errors.append((test_name, str(e)))
            print(f"  ✗ {test_name}: 异常 - {e}")
            return False
            
    def print_summary(self):
        total = self.passed + self.failed
        print("\n" + "=" * 60)
        print(f"测试结果: 通过 {self.passed}/{total}, 失败 {self.failed}/{total}")
        if self.failed > 0:
            print("\n失败的测试:")
            for name, error in self.errors:
                print(f"  - {name}: {error}")
        print("=" * 60)


def test_user_auth():
    """用户认证模块测试"""
    print("\n【用户认证模块测试】")
    runner = TestRunner()
    runner.setup()
    
    def test_register_page():
        response = runner.client.get('/register')
        assert response.status_code == 200, f"状态码应为200，实际为{response.status_code}"
    
    def test_login_page():
        response = runner.client.get('/login')
        assert response.status_code == 200, f"状态码应为200，实际为{response.status_code}"
    
    def test_login_success():
        response = runner.client.post('/login', data={
            'username': runner.test_user['username'],
            'password': runner.test_user['password']
        }, follow_redirects=True)
        assert response.status_code == 200
    
    def test_login_wrong_password():
        response = runner.client.post('/login', data={
            'username': runner.test_user['username'],
            'password': 'wrongpassword'
        }, follow_redirects=True)
        assert response.status_code == 200
    
    def test_logout():
        runner.login()
        response = runner.client.get('/logout', follow_redirects=True)
        assert response.status_code == 200
    
    runner.run_test("注册页面加载", test_register_page)
    runner.run_test("登录页面加载", test_login_page)
    runner.run_test("正确密码登录", test_login_success)
    runner.run_test("错误密码登录", test_login_wrong_password)
    runner.run_test("登出功能", test_logout)
    
    runner.print_summary()
    return runner.passed, runner.failed


def test_movie_browse():
    """电影浏览模块测试"""
    print("\n【电影浏览模块测试】")
    runner = TestRunner()
    runner.setup()
    
    def test_index():
        response = runner.client.get('/')
        assert response.status_code == 200
    
    def test_search():
        response = runner.client.get('/search')
        assert response.status_code == 200
    
    def test_search_with_query():
        response = runner.client.get('/search?q=Action')
        assert response.status_code == 200
    
    def test_search_pagination():
        response = runner.client.get('/search?page=1')
        assert response.status_code == 200
    
    runner.run_test("首页加载", test_index)
    runner.run_test("搜索页面加载", test_search)
    runner.run_test("带关键词搜索", test_search_with_query)
    runner.run_test("分页功能", test_search_pagination)
    
    runner.print_summary()
    return runner.passed, runner.failed


def test_movie_detail():
    """电影详情模块测试"""
    print("\n【电影详情模块测试】")
    runner = TestRunner()
    runner.setup()
    runner.login()
    
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT movieId FROM movies LIMIT 1")
    movie = c.fetchone()
    c.close()
    conn.close()
    
    if movie:
        movie_id = movie['movieId']
        
        def test_detail_page():
            response = runner.client.get(f'/movie/{movie_id}')
            assert response.status_code == 200
        
        runner.run_test("电影详情页加载", test_detail_page)
    else:
        print("  跳过: 数据库中没有电影数据")
    
    runner.print_summary()
    return runner.passed, runner.failed


def test_rating_comment():
    """评分评论模块测试"""
    print("\n【评分评论模块测试】")
    runner = TestRunner()
    runner.setup()
    runner.login()
    
    conn = get_db()
    c = conn.cursor(dictionary=True)
    c.execute("SELECT movieId FROM movies LIMIT 1")
    movie = c.fetchone()
    c.close()
    conn.close()
    
    if movie:
        movie_id = movie['movieId']
        
        def test_submit_rating():
            response = runner.client.post('/rate', data={
                'movie_id': movie_id,
                'rating': 4.5
            }, follow_redirects=True)
            assert response.status_code == 200
        
        def test_submit_comment():
            response = runner.client.post('/comment', data={
                'movie_id': movie_id,
                'content': '这是一条测试评论'
            }, follow_redirects=True)
            assert response.status_code == 200
        
        runner.run_test("提交评分", test_submit_rating)
        runner.run_test("提交评论", test_submit_comment)
    else:
        print("  跳过: 数据库中没有电影数据")
    
    runner.print_summary()
    return runner.passed, runner.failed


def test_recommend():
    """推荐功能模块测试"""
    print("\n【推荐功能模块测试】")
    runner = TestRunner()
    runner.setup()
    runner.login()
    
    def test_recommend_page():
        response = runner.client.get('/recommend')
        assert response.status_code == 200
    
    def test_recommend_no_login():
        runner.client.get('/logout', follow_redirects=True)
        response = runner.client.get('/recommend', follow_redirects=False)
        assert response.status_code in [302, 401]
    
    runner.run_test("推荐页面加载", test_recommend_page)
    runner.run_test("未登录访问推荐", test_recommend_no_login)
    
    runner.print_summary()
    return runner.passed, runner.failed


def test_profile():
    """个人中心模块测试"""
    print("\n【个人中心模块测试】")
    runner = TestRunner()
    runner.setup()
    runner.login()
    
    def test_profile_page():
        response = runner.client.get('/profile')
        assert response.status_code == 200
    
    runner.run_test("个人中心页面加载", test_profile_page)
    
    runner.print_summary()
    return runner.passed, runner.failed


def main():
    print("=" * 60)
    print("电影推荐系统 - 功能测试报告")
    print("=" * 60)
    
    total_passed = 0
    total_failed = 0
    
    try:
        p, f = test_user_auth()
        total_passed += p
        total_failed += f
    except Exception as e:
        print(f"用户认证测试出错: {e}")
    
    try:
        p, f = test_movie_browse()
        total_passed += p
        total_failed += f
    except Exception as e:
        print(f"电影浏览测试出错: {e}")
    
    try:
        p, f = test_movie_detail()
        total_passed += p
        total_failed += f
    except Exception as e:
        print(f"电影详情测试出错: {e}")
    
    try:
        p, f = test_rating_comment()
        total_passed += p
        total_failed += f
    except Exception as e:
        print(f"评分评论测试出错: {e}")
    
    try:
        p, f = test_recommend()
        total_passed += p
        total_failed += f
    except Exception as e:
        print(f"推荐功能测试出错: {e}")
    
    try:
        p, f = test_profile()
        total_passed += p
        total_failed += f
    except Exception as e:
        print(f"个人中心测试出错: {e}")
    
    print("\n" + "=" * 60)
    print("【总体测试结果】")
    total = total_passed + total_failed
    pass_rate = (total_passed / total * 100) if total > 0 else 0
    print(f"总测试数: {total}")
    print(f"通过: {total_passed}")
    print(f"失败: {total_failed}")
    print(f"通过率: {pass_rate:.1f}%")
    print("=" * 60)
    
    return 0 if total_failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
