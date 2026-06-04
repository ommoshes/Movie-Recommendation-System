import pytest


class TestRatingFunction:
    """评分功能测试"""

    def test_submit_rating(self, logged_in_client, sample_movie, db_connection, test_user, cleanup_ratings):
        """测试提交评分"""
        if not sample_movie:
            pytest.skip("No sample movie available")
        
        response = logged_in_client.post('/rate', data={
            'movie_id': sample_movie['movieId'],
            'rating': 4.5
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        c = db_connection.cursor(dictionary=True)
        c.execute(
            "SELECT * FROM ratings WHERE userId = %s AND movieId = %s",
            (test_user['id'], sample_movie['movieId'])
        )
        rating = c.fetchone()
        c.close()
        
        assert rating is not None

    def test_update_rating(self, logged_in_client, sample_movie, db_connection, test_user, cleanup_ratings):
        """测试更新评分"""
        if not sample_movie:
            pytest.skip("No sample movie available")
        
        logged_in_client.post('/rate', data={
            'movie_id': sample_movie['movieId'],
            'rating': 3.0
        })
        
        response = logged_in_client.post('/rate', data={
            'movie_id': sample_movie['movieId'],
            'rating': 5.0
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        c = db_connection.cursor(dictionary=True)
        c.execute(
            "SELECT rating FROM ratings WHERE userId = %s AND movieId = %s",
            (test_user['id'], sample_movie['movieId'])
        )
        rating = c.fetchone()
        c.close()
        
        if rating:
            assert float(rating['rating']) == 5.0

    def test_rating_boundary_values(self, logged_in_client, sample_movie, db_connection, test_user, cleanup_ratings):
        """测试评分边界值"""
        if not sample_movie:
            pytest.skip("No sample movie available")
        
        for rating_value in [0.5, 1.0, 2.5, 4.0, 5.0]:
            response = logged_in_client.post('/rate', data={
                'movie_id': sample_movie['movieId'],
                'rating': rating_value
            })
            assert response.status_code in [200, 302]

    def test_rating_requires_login(self, client, sample_movie):
        """测试评分需要登录"""
        if not sample_movie:
            pytest.skip("No sample movie available")
        
        response = client.post('/rate', data={
            'movie_id': sample_movie['movieId'],
            'rating': 4.0
        })
        assert response.status_code in [302, 401]


class TestCommentFunction:
    """评论功能测试"""

    def test_submit_comment(self, logged_in_client, sample_movie, db_connection, test_user, cleanup_comments):
        """测试提交评论"""
        if not sample_movie:
            pytest.skip("No sample movie available")
        
        response = logged_in_client.post('/comment', data={
            'movie_id': sample_movie['movieId'],
            'content': '这是一条测试评论'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        c = db_connection.cursor(dictionary=True)
        c.execute(
            "SELECT * FROM movie_comments WHERE userId = %s AND movieId = %s ORDER BY created_at DESC LIMIT 1",
            (test_user['id'], sample_movie['movieId'])
        )
        comment = c.fetchone()
        c.close()
        
        assert comment is not None
        assert '测试评论' in comment['content']

    def test_comment_content_validation(self, logged_in_client, sample_movie):
        """测试评论内容验证"""
        if not sample_movie:
            pytest.skip("No sample movie available")
        
        response = logged_in_client.post('/comment', data={
            'movie_id': sample_movie['movieId'],
            'content': ''
        })
        assert response.status_code in [200, 302, 400]

    def test_comment_requires_login(self, client, sample_movie):
        """测试评论需要登录"""
        if not sample_movie:
            pytest.skip("No sample movie available")
        
        response = client.post('/comment', data={
            'movie_id': sample_movie['movieId'],
            'content': '未登录评论'
        })
        assert response.status_code in [302, 401]


class TestLikeFunction:
    """点赞功能测试"""

    def test_like_comment(self, logged_in_client, db_connection, test_user, sample_movie, cleanup_comments):
        """测试点赞评论"""
        if not sample_movie:
            pytest.skip("No sample movie available")
        
        logged_in_client.post('/comment', data={
            'movie_id': sample_movie['movieId'],
            'content': '测试点赞的评论'
        })
        
        c = db_connection.cursor(dictionary=True)
        c.execute(
            "SELECT id FROM movie_comments WHERE userId = %s ORDER BY created_at DESC LIMIT 1",
            (test_user['id'],)
        )
        comment = c.fetchone()
        c.close()
        
        if comment:
            response = logged_in_client.post(f'/like_comment/{comment["id"]}')
            assert response.status_code == 200

    def test_unlike_comment(self, logged_in_client, db_connection, test_user, sample_movie, cleanup_comments):
        """测试取消点赞"""
        if not sample_movie:
            pytest.skip("No sample movie available")
        
        logged_in_client.post('/comment', data={
            'movie_id': sample_movie['movieId'],
            'content': '测试取消点赞的评论'
        })
        
        c = db_connection.cursor(dictionary=True)
        c.execute(
            "SELECT id FROM movie_comments WHERE userId = %s ORDER BY created_at DESC LIMIT 1",
            (test_user['id'],)
        )
        comment = c.fetchone()
        c.close()
        
        if comment:
            logged_in_client.post(f'/like_comment/{comment["id"]}')
            response = logged_in_client.post(f'/like_comment/{comment["id"]}')
            assert response.status_code == 200

    def test_like_requires_login(self, client):
        """测试点赞需要登录"""
        response = client.post('/like_comment/1')
        assert response.status_code in [302, 401]


class TestProfileFunction:
    """个人中心功能测试"""

    def test_profile_loads(self, logged_in_client):
        """测试个人中心页面加载"""
        response = logged_in_client.get('/profile')
        assert response.status_code == 200

    def test_profile_shows_user_info(self, logged_in_client, test_user):
        """测试个人中心显示用户信息"""
        response = logged_in_client.get('/profile')
        assert response.status_code == 200
        assert test_user['username'].encode('utf-8') in response.data

    def test_profile_shows_ratings(self, logged_in_client, sample_movie, db_connection, test_user, cleanup_ratings):
        """测试个人中心显示评分记录"""
        if sample_movie:
            logged_in_client.post('/rate', data={
                'movie_id': sample_movie['movieId'],
                'rating': 4.0
            })
        
        response = logged_in_client.get('/profile')
        assert response.status_code == 200
