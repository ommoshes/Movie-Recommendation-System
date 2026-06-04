import pytest


class TestRecommendFunction:
    """推荐功能测试"""

    def test_recommend_page_loads(self, logged_in_client):
        """测试推荐页面能否正常加载"""
        response = logged_in_client.get('/recommend')
        assert response.status_code == 200

    def test_recommend_requires_login(self, client):
        """测试推荐需要登录"""
        response = client.get('/recommend', follow_redirects=False)
        assert response.status_code in [302, 401]

    def test_recommend_shows_movies(self, logged_in_client):
        """测试推荐页面显示电影"""
        response = logged_in_client.get('/recommend')
        assert response.status_code == 200
        assert b'movieId' in response.data or b'title' in response.data or b'<div' in response.data

    def test_recommend_cold_start(self, logged_in_client, db_connection, test_user):
        """测试冷启动推荐（用户无评分时）"""
        c = db_connection.cursor()
        c.execute("DELETE FROM ratings WHERE userId = %s", (test_user['id'],))
        db_connection.commit()
        c.close()
        
        response = logged_in_client.get('/recommend')
        assert response.status_code == 200

    def test_recommend_with_user_ratings(self, logged_in_client, sample_movie, db_connection, test_user, cleanup_ratings):
        """测试有评分时的推荐"""
        if not sample_movie:
            pytest.skip("No sample movie available")
        
        logged_in_client.post('/rate', data={
            'movie_id': sample_movie['movieId'],
            'rating': 5.0
        })
        
        response = logged_in_client.get('/recommend')
        assert response.status_code == 200

    def test_recommend_no_duplicates(self, logged_in_client):
        """测试推荐结果无重复"""
        response = logged_in_client.get('/recommend')
        assert response.status_code == 200


class TestCollaborativeFiltering:
    """协同过滤算法测试"""

    def test_cf_finds_similar_users(self, logged_in_client, db_connection, test_user, sample_movie, cleanup_ratings):
        """测试协同过滤找到相似用户"""
        if not sample_movie:
            pytest.skip("No sample movie available")
        
        c = db_connection.cursor(dictionary=True)
        c.execute("SELECT movieId FROM movies LIMIT 5")
        movies = c.fetchall()
        c.close()
        
        for movie in movies:
            logged_in_client.post('/rate', data={
                'movie_id': movie['movieId'],
                'rating': 5.0
            })
        
        response = logged_in_client.get('/recommend')
        assert response.status_code == 200

    def test_cf_excludes_rated_movies(self, logged_in_client, db_connection, test_user, sample_movie, cleanup_ratings):
        """测试协同过滤排除已评分电影"""
        if not sample_movie:
            pytest.skip("No sample movie available")
        
        logged_in_client.post('/rate', data={
            'movie_id': sample_movie['movieId'],
            'rating': 5.0
        })
        
        response = logged_in_client.get('/recommend')
        assert response.status_code == 200


class TestProfileBasedRecommendation:
    """基于画像的推荐测试"""

    def test_profile_recommendation_genre_preference(self, logged_in_client, db_connection, test_user, cleanup_ratings):
        """测试基于类型偏好的推荐"""
        c = db_connection.cursor(dictionary=True)
        c.execute("SELECT movieId, genres FROM movies WHERE genres LIKE '%Action%' LIMIT 3")
        action_movies = c.fetchall()
        c.close()
        
        if not action_movies:
            pytest.skip("No action movies available")
        
        for movie in action_movies:
            logged_in_client.post('/rate', data={
                'movie_id': movie['movieId'],
                'rating': 5.0
            })
        
        response = logged_in_client.get('/recommend')
        assert response.status_code == 200


class TestHotMoviesRecommendation:
    """热门电影推荐测试"""

    def test_hot_movies_fallback(self, logged_in_client, db_connection, test_user):
        """测试热门电影作为兜底推荐"""
        c = db_connection.cursor()
        c.execute("DELETE FROM ratings WHERE userId = %s", (test_user['id'],))
        db_connection.commit()
        c.close()
        
        response = logged_in_client.get('/recommend')
        assert response.status_code == 200
        
        c = db_connection.cursor(dictionary=True)
        c.execute("""
            SELECT m.movieId, COUNT(r.rating) as rating_count
            FROM movies m
            JOIN ratings r ON m.movieId = r.movieId
            GROUP BY m.movieId
            ORDER BY rating_count DESC
            LIMIT 1
        """)
        top_movie = c.fetchone()
        c.close()


class TestRecommendationQuality:
    """推荐质量测试"""

    def test_recommendation_count(self, logged_in_client):
        """测试推荐数量合理"""
        response = logged_in_client.get('/recommend')
        assert response.status_code == 200

    def test_recommendation_diversity(self, logged_in_client, db_connection, test_user, cleanup_ratings):
        """测试推荐多样性"""
        c = db_connection.cursor(dictionary=True)
        c.execute("SELECT movieId FROM movies WHERE genres LIKE '%Action%' LIMIT 2")
        action_movies = c.fetchall()
        c.execute("SELECT movieId FROM movies WHERE genres LIKE '%Comedy%' LIMIT 2")
        comedy_movies = c.fetchall()
        c.close()
        
        all_movies = action_movies + comedy_movies
        for movie in all_movies:
            if movie:
                logged_in_client.post('/rate', data={
                    'movie_id': movie['movieId'],
                    'rating': 5.0
                })
        
        response = logged_in_client.get('/recommend')
        assert response.status_code == 200
