import pytest
from werkzeug.security import generate_password_hash


class TestUserRegistration:
    """用户注册功能测试"""

    def test_register_page_loads(self, client):
        """测试注册页面能否正常加载"""
        response = client.get('/register')
        assert response.status_code == 200
        assert b'register' in response.data.lower() or b'\xe6\xb3\xa8\xe5\x86\x8c' in response.data

    def test_register_new_user(self, client, db_connection):
        """测试注册新用户"""
        import random
        username = f'new_test_user_{random.randint(10000, 99999)}'
        password = 'Test123456'
        
        response = client.post('/register', data={
            'username': username,
            'password': password
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        c = db_connection.cursor(dictionary=True)
        c.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = c.fetchone()
        c.close()
        
        assert user is not None
        assert user['username'] == username

    def test_register_duplicate_username(self, client, test_user):
        """测试注册重复用户名"""
        response = client.post('/register', data={
            'username': test_user['username'],
            'password': 'another_password'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'\xe5\xb7\xb2\xe5\xad\x98\xe5\x9c\xa8' in response.data or b'exist' in response.data.lower()


class TestUserLogin:
    """用户登录功能测试"""

    def test_login_page_loads(self, client):
        """测试登录页面能否正常加载"""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'login' in response.data.lower() or b'\xe7\x99\xbb\xe5\xbd\x95' in response.data

    def test_login_success(self, client, test_user):
        """测试正确用户名密码登录"""
        response = client.post('/login', data={
            'username': test_user['username'],
            'password': test_user['password']
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'\xe7\x99\xbb\xe5\xbd\x95\xe6\x88\x90\xe5\x8a\x9f' in response.data or b'success' in response.data.lower()

    def test_login_wrong_password(self, client, test_user):
        """测试错误密码登录"""
        response = client.post('/login', data={
            'username': test_user['username'],
            'password': 'wrongpassword'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'\xe9\x94\x99\xe8\xaf\xaf' in response.data or b'error' in response.data.lower()

    def test_login_nonexistent_user(self, client):
        """测试不存在的用户登录"""
        response = client.post('/login', data={
            'username': 'nonexistent_user_xyz',
            'password': 'somepassword'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'\xe9\x94\x99\xe8\xaf\xaf' in response.data or b'error' in response.data.lower()

    def test_login_remember_me(self, client, test_user):
        """测试记住登录功能"""
        response = client.post('/login', data={
            'username': test_user['username'],
            'password': test_user['password'],
            'remember': 'on'
        }, follow_redirects=True)
        
        assert response.status_code == 200


class TestUserLogout:
    """用户登出功能测试"""

    def test_logout(self, logged_in_client):
        """测试登出功能"""
        response = logged_in_client.get('/logout', follow_redirects=True)
        assert response.status_code == 200

    def test_logout_redirect_to_index(self, logged_in_client):
        """测试登出后重定向到首页"""
        response = logged_in_client.get('/logout', follow_redirects=False)
        assert response.status_code == 302


class TestAuthenticationRequired:
    """认证保护测试"""

    def test_movie_detail_requires_login(self, client, sample_movie):
        """测试电影详情页需要登录"""
        if sample_movie:
            response = client.get(f'/movie/{sample_movie["movieId"]}', follow_redirects=False)
            assert response.status_code == 302 or response.status_code == 401

    def test_recommend_requires_login(self, client):
        """测试推荐页面需要登录"""
        response = client.get('/recommend', follow_redirects=False)
        assert response.status_code == 302 or response.status_code == 401

    def test_profile_requires_login(self, client):
        """测试个人中心需要登录"""
        response = client.get('/profile', follow_redirects=False)
        assert response.status_code == 302 or response.status_code == 401
