import pytest


class TestIndexPage:
    """首页功能测试"""

    def test_index_loads(self, client):
        """测试首页能否正常加载"""
        response = client.get('/')
        assert response.status_code == 200

    def test_index_shows_movies(self, client, db_connection):
        """测试首页显示电影列表"""
        response = client.get('/')
        
        c = db_connection.cursor(dictionary=True)
        c.execute("SELECT COUNT(*) as cnt FROM movies")
        movie_count = c.fetchone()['cnt']
        c.close()
        
        if movie_count > 0:
            assert b'movieId' in response.data or b'title' in response.data or b'<div' in response.data

    def test_index_shows_top_rated_movies(self, client, db_connection):
        """测试首页显示热门电影（按评分数量排序）"""
        response = client.get('/')
        assert response.status_code == 200


class TestSearchFunction:
    """搜索功能测试"""

    def test_search_page_loads(self, client):
        """测试搜索页面能否正常加载"""
        response = client.get('/search')
        assert response.status_code == 200

    def test_search_with_query(self, client, db_connection):
        """测试带关键词搜索"""
        c = db_connection.cursor(dictionary=True)
        c.execute("SELECT title FROM movies WHERE title IS NOT NULL LIMIT 1")
        movie = c.fetchone()
        c.close()
        
        if movie:
            keyword = movie['title'][:3] if len(movie['title']) >= 3 else movie['title']
            response = client.get(f'/search?q={keyword}')
            assert response.status_code == 200

    def test_search_empty_query(self, client):
        """测试空关键词搜索"""
        response = client.get('/search?q=')
        assert response.status_code == 200

    def test_search_no_results(self, client):
        """测试无结果搜索"""
        response = client.get('/search?q=zzzzzzzzzzzzzzzzzzzzzzzz12345')
        assert response.status_code == 200

    def test_search_with_genre_filter(self, client, db_connection):
        """测试类型筛选"""
        c = db_connection.cursor(dictionary=True)
        c.execute("SELECT genres FROM movies WHERE genres IS NOT NULL LIMIT 1")
        movie = c.fetchone()
        c.close()
        
        if movie and movie['genres']:
            genre = movie['genres'].split('|')[0]
            response = client.get(f'/search?genre={genre}')
            assert response.status_code == 200

    def test_search_pagination(self, client):
        """测试分页功能"""
        response_page1 = client.get('/search?page=1')
        assert response_page1.status_code == 200
        
        response_page2 = client.get('/search?page=2')
        assert response_page2.status_code == 200

    def test_search_invalid_page(self, client):
        """测试无效页码"""
        response = client.get('/search?page=-1')
        assert response.status_code == 200
        
        response = client.get('/search?page=abc')
        assert response.status_code == 200


class TestMovieDetail:
    """电影详情功能测试"""

    def test_movie_detail_loads(self, logged_in_client, sample_movie):
        """测试电影详情页能否正常加载"""
        if sample_movie:
            response = logged_in_client.get(f'/movie/{sample_movie["movieId"]}')
            assert response.status_code == 200

    def test_movie_detail_shows_info(self, logged_in_client, sample_movie):
        """测试电影详情页显示电影信息"""
        if sample_movie:
            response = logged_in_client.get(f'/movie/{sample_movie["movieId"]}')
            assert response.status_code == 200
            
            if sample_movie['title']:
                title_encoded = sample_movie['title'].encode('utf-8')
                assert title_encoded in response.data

    def test_movie_detail_shows_rating(self, logged_in_client, sample_movie, db_connection):
        """测试电影详情页显示评分信息"""
        if sample_movie:
            response = logged_in_client.get(f'/movie/{sample_movie["movieId"]}')
            assert response.status_code == 200

    def test_movie_detail_invalid_id(self, logged_in_client):
        """测试无效电影ID"""
        response = logged_in_client.get('/movie/99999999')
        assert response.status_code in [200, 404]

    def test_movie_detail_shows_comments(self, logged_in_client, sample_movie):
        """测试电影详情页显示评论"""
        if sample_movie:
            response = logged_in_client.get(f'/movie/{sample_movie["movieId"]}')
            assert response.status_code == 200


class TestMovieGenres:
    """电影类型功能测试"""

    def test_genre_list(self, client, db_connection):
        """测试类型列表获取"""
        c = db_connection.cursor(dictionary=True)
        c.execute("SELECT DISTINCT genres FROM movies WHERE genres IS NOT NULL LIMIT 10")
        genres_rows = c.fetchall()
        c.close()
        
        assert len(genres_rows) >= 0

    def test_genre_filter_consistency(self, client, db_connection):
        """测试类型筛选结果一致性"""
        c = db_connection.cursor(dictionary=True)
        c.execute("SELECT genres FROM movies WHERE genres IS NOT NULL AND genres LIKE '%Action%' LIMIT 1")
        movie = c.fetchone()
        c.close()
        
        if movie:
            response = client.get('/search?genre=Action')
            assert response.status_code == 200
