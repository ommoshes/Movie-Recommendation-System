from flask import Flask, render_template, request, redirect, url_for, flash, session,jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from collections import Counter
from pyecharts.charts import Bar, Radar
from pyecharts import options as opts
from pyecharts.commons.utils import JsCode

app = Flask(__name__)
app.secret_key = 'yzt1256448150'  # 必须设置，用于加密session和flash消息

# 配置 Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # 如果未登录访问受保护页面，自动跳转到login路由

# 配置 MySQL 数据库连接
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'yzt123456789',  # 替换为你的密码
    'database': 'movies_db'
}

# 创建数据库连接的辅助函数
def get_db():
    return mysql.connector.connect(**db_config)

# 定义用户类（Flask-Login要求）
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

# Flask-Login 加载用户的回调函数
@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    c = conn.cursor(dictionary=True) # dictionary=True 让查询结果变成字典，方便通过列名取值
    c.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user_data = c.fetchone()
    conn.close()
    if user_data:
        return User(user_data['id'], user_data['username'])
    return None


@app.route('/')
def index():
    conn = get_db()
    c = conn.cursor(dictionary=True)

    # 优化后的SQL：先在ratings表里算分，再和movies表关联，避免对text字段做GROUP BY
    c.execute("""
              SELECT m.movieId, m.title, m.genres, r_agg.avg_rating, r_agg.rating_count
              FROM movies m
                       INNER JOIN (SELECT movieId, AVG(rating) as avg_rating, COUNT(rating) as rating_count
                                   FROM ratings
                                   GROUP BY movieId) r_agg ON m.movieId = r_agg.movieId
              ORDER BY r_agg.rating_count DESC LIMIT 10
              """)
    movies = c.fetchall()
    conn.close()

    # 根据登录状态渲染页面
    if current_user.is_authenticated:
        return render_template('index.html', movies=movies, user=current_user)
    else:
        return render_template('index.html', movies=movies, user=None)


# 注册路由（显示页面 + 处理表单提交）
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db()
        c = conn.cursor(dictionary=True)

        # 检查用户名是否已存在
        c.execute("SELECT * FROM users WHERE username = %s", (username,))
        if c.fetchone():
            flash('用户名已存在，请更换一个！')
            conn.close()
            return redirect(url_for('register'))

        # 密码加密（绝不能明文存储！）
        hashed_password = generate_password_hash(password)

        # 插入新用户
        c.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
        conn.commit()
        conn.close()

        flash('注册成功，请登录！')
        return redirect(url_for('login'))

    # GET请求：直接渲染注册页面
    return render_template('register.html')


# 登录路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = 'remember' in request.form  # 新增

        conn = get_db()
        c = conn.cursor(dictionary=True)
        c.execute("SELECT * FROM users WHERE username = %s", (username,))
        user_data = c.fetchone()
        conn.close()

        # 验证用户名存在，且密码正确
        if user_data and check_password_hash(user_data['password'], password):
            user = User(user_data['id'], user_data['username'])
            login_user(user,remember=remember)  # Flask-Login 登录操作
            flash('登录成功！','success')
            return redirect(url_for('index'))
        else:
            flash('用户名或密码错误！','error')

    return render_template('login.html')


@app.route('/search')
def search():
    # 获取用户在搜索框输入的关键词
    query = request.args.get('q', '')
    # 可选的类型过滤参数
    selected_genre = request.args.get('genre', '').strip()
    # 分页参数
    try:
        page = int(request.args.get('page', 1))
        if page < 1:
            page = 1
    except Exception:
        page = 1
    PER_PAGE = 40

    conn = get_db()
    c = conn.cursor(dictionary=True)
    # 先读取所有电影的 genres 字段并拆分，生成可用的类型按钮列表（不修改数据库）
    c.execute("SELECT genres FROM movies WHERE genres IS NOT NULL")
    all_genres_rows = c.fetchall()
    genres_set = set()
    for row in all_genres_rows:
        gs = row.get('genres')
        if not gs:
            continue
        # 支持多种分隔符的情况（| 或 , 或 / 或 ;）
        parts = []
        if '|' in gs:
            parts = gs.split('|')
        elif ',' in gs:
            parts = gs.split(',')
        elif '/' in gs:
            parts = gs.split('/')
        elif ';' in gs:
            parts = gs.split(';')
        else:
            parts = [gs]
        for g in parts:
            g = g.strip()
            if g:
                genres_set.add(g)
    genres = sorted(genres_set)

    # 计算每个类型的匹配数量（用于调试/显示），使用正则按 token 匹配（支持多种分隔符）
    import re
    genre_counts = {}
    for g in genres:
        # 构造正则，匹配分隔符前后或字符串边界： (^|[|,;/])GENRE($|[|,;/])
        pat = r'(^|[\\|,;/])' + re.escape(g) + r'($|[\\|,;/])'
        c.execute("SELECT COUNT(*) as cnt FROM movies WHERE genres REGEXP %s", (pat,))
        row = c.fetchone()
        genre_counts[g] = int(row['cnt']) if row and 'cnt' in row and row['cnt'] is not None else 0

    # 根据查询关键字和选中类型组合查询（支持分页）
    offset = (page - 1) * PER_PAGE

    # 先计算总数，再查询当前页数据
    if query and selected_genre:
        pat = r'(^|[\\|,;/])' + selected_genre.replace("'", "''") + r'($|[\\|,;/])'
        c.execute("SELECT COUNT(*) as cnt FROM movies WHERE title LIKE %s AND genres REGEXP %s", (f'%{query}%', pat))
        total_count = int(c.fetchone()['cnt'] or 0)
        c.execute("""
                  SELECT movieId, title, genres
                  FROM movies
                  WHERE title LIKE %s AND genres REGEXP %s
                  ORDER BY title
                  LIMIT %s OFFSET %s
                  """, (f'%{query}%', pat, PER_PAGE, offset))
    elif query:
        c.execute("SELECT COUNT(*) as cnt FROM movies WHERE title LIKE %s", (f'%{query}%',))
        total_count = int(c.fetchone()['cnt'] or 0)
        c.execute("""
                  SELECT movieId, title, genres
                  FROM movies
                  WHERE title LIKE %s
                  ORDER BY title
                  LIMIT %s OFFSET %s
                  """, (f'%{query}%', PER_PAGE, offset))
    elif selected_genre:
        pat = r'(^|[\\|,;/])' + selected_genre.replace("'", "''") + r'($|[\\|,;/])'
        c.execute("SELECT COUNT(*) as cnt FROM movies WHERE genres REGEXP %s", (pat,))
        total_count = int(c.fetchone()['cnt'] or 0)
        c.execute("""
                  SELECT movieId, title, genres
                  FROM movies
                  WHERE genres REGEXP %s
                  ORDER BY title
                  LIMIT %s OFFSET %s
                  """, (pat, PER_PAGE, offset))
    else:
        c.execute("SELECT COUNT(*) as cnt FROM movies")
        total_count = int(c.fetchone()['cnt'] or 0)
        c.execute("""
                  SELECT movieId, title, genres
                  FROM movies
                  ORDER BY title
                  LIMIT %s OFFSET %s
                  """, (PER_PAGE, offset))

    movies = c.fetchall()
    conn.close()

    # 渲染页面，把搜索结果、搜索关键词、类型列表、选中类型和用户状态传过去
    # 计算分页总页数
    total_pages = (total_count + PER_PAGE - 1) // PER_PAGE if total_count > 0 else 1

    template_params = {
        'movies': movies,
        'query': query,
        'genres': genres,
        'selected_genre': selected_genre,
        'genre_counts': genre_counts,
        'page': page,
        'per_page': PER_PAGE,
        'total_count': total_count,
        'total_pages': total_pages
    }
    if current_user.is_authenticated:
        template_params['user'] = current_user
    else:
        template_params['user'] = None

    return render_template('search.html', **template_params)


# 根据电影类型生成文艺伪简介
def generate_fake_summary(genres_str):
    if not genres_str:
        return "一段不可错过的光影之旅，在起承转合中，寻找属于自己的共鸣与回响。"

    genres = genres_str.split('|')

    if 'Comedy' in genres:
        return "在欢笑与泪水中，品味生活的荒诞与温情，这是一部让你嘴角上扬的轻松之作。"
    elif 'Drama' in genres:
        return "深入骨髓的情感刻画，跌宕起伏的命运交响，在光影中照见最真实的人性。"
    elif 'Action' in genres:
        return "肾上腺素飙升的视觉盛宴，拳拳到肉的激烈交锋，正义与勇气的极致碰撞。"
    elif 'Sci-Fi' in genres:
        return "跨越时空的想象力边界，在浩瀚宇宙与未知维度中，探寻人类文明的终极命运。"
    elif 'Romance' in genres:
        return "一场不期而遇的邂逅，一段刻骨铭心的爱恋，在时光流转中诠释爱的千百种模样。"
    elif 'Horror' in genres:
        return "步步惊心的窒息氛围，直击灵魂的深层恐惧，挑战你的心理承受极限。"
    elif 'Thriller' in genres:
        return "错综复杂的迷局，险象环生的追踪，真相往往隐藏在最不可疑的角落。"
    elif 'Animation' in genres:
        return "用绚烂的色彩勾勒奇想世界，无论大人还是孩子，都能在这里找回纯真的梦。"
    else:
        return "一段不可错过的光影之旅，在起承转合中，寻找属于自己的共鸣与回响。"


@app.route('/movie/<int:movie_id>')
@login_required
def movie_detail(movie_id):
    conn = get_db()
    c = conn.cursor(dictionary=True, buffered=True)

    # 1. 获取电影信息 + 实时计算平均评分和评分人数
    c.execute("""
              SELECT m.*,
                     IFNULL(AVG(r.rating), 0) as avg_rating,
                     COUNT(r.rating)          as rating_count
              FROM movies m
                       LEFT JOIN ratings r ON m.movieId = r.movieId
              WHERE m.movieId = %s
              GROUP BY m.movieId
              """, (movie_id,))
    movie = c.fetchone()


    if not movie:
        conn.close()
        return "Movie not found", 404

    # 2. 生成文艺伪简介
    summary = generate_fake_summary(movie.get('genres', ''))

    # 3. 获取当前用户的评分
    c.execute("SELECT rating FROM ratings WHERE userId = %s AND movieId = %s", (current_user.id, movie_id))
    user_rating_row = c.fetchone()
    user_rating = user_rating_row['rating'] if user_rating_row else 0

    # 4. 获取热门评论（连带查询评论者的评分 和 当前用户的点赞状态）
    c.execute("""
              SELECT mc.id,
                     mc.userId,
                     mc.content,
                     mc.likes_count,
                     mc.created_at,
                     u.username,
                     r.rating                     as user_score,
                     EXISTS(SELECT 1
                            FROM comment_interactions ci
                            WHERE ci.comment_id = mc.id
                              AND ci.userId = %s) as is_liked
              FROM movie_comments mc
                       JOIN users u ON mc.userId = u.id
                       LEFT JOIN ratings r ON mc.userId = r.userId AND mc.movieId = r.movieId
              WHERE mc.movieId = %s
                AND mc.is_deleted = 0
              ORDER BY mc.likes_count DESC, mc.created_at DESC
              """, (current_user.id, movie_id))
    comments = c.fetchall()

    conn.close()

    return render_template('movie_detail.html',
                           movie=movie,
                           user_rating=user_rating,
                           summary=summary,
                           comments=comments,
                           user=current_user)


@app.route('/rate', methods=['POST'])
@login_required  # 这个装饰器确保只有登录的用户才能打分
def rate():
    # 获取前端传过来的 JSON 数据
    data = request.get_json()
    movie_id = data.get('movie_id')
    score = data.get('score')

    # 简单的防御：如果数据不全，返回错误
    if not movie_id or not score:
        return jsonify({'status': 'error', 'message': '数据不完整'}), 400

    conn = get_db()
    c = conn.cursor()

    try:
        # 将评分存入数据库
        # ON DUPLICATE KEY UPDATE 的意思是：
        # 如果这个用户已经给这部电影打过分了，就更新他的分数；如果没有，就插入新记录。
        c.execute("""
                  INSERT INTO ratings (userId, movieId, rating, timestamp)
                  VALUES (%s, %s, %s, UNIX_TIMESTAMP()) ON DUPLICATE KEY
                  UPDATE rating =
                  VALUES (rating), timestamp =
                  VALUES (timestamp)
                  """, (current_user.id, movie_id, score))

        conn.commit()
        return jsonify({'status': 'success', 'message': '评分成功'})

    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': '服务器开小差了'}), 500

    finally:
        conn.close()


@app.route('/comment', methods=['POST'])
@login_required
def add_comment():
    movie_id = request.form.get('movie_id')
    content = request.form.get('content', '').strip()

    conn = get_db()
    c = conn.cursor(dictionary=True, buffered=True)

    # ====== 新增：检查是否评分 ======
    c.execute("SELECT rating FROM ratings WHERE userId = %s AND movieId = %s", (current_user.id, movie_id))
    if not c.fetchone():
        conn.close()
        # 如果没评分就直接发评论，直接打回原形（实际前端也会拦截，这是双保险）
        return redirect(url_for('movie_detail', movie_id=movie_id))
    # =================================

    if content:
        c.execute("""
                  INSERT INTO movie_comments (movieId, userId, content)
                  VALUES (%s, %s, %s)
                  """, (movie_id, current_user.id, content))
        conn.commit()

    conn.close()
    return redirect(url_for('movie_detail', movie_id=movie_id))


@app.route('/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    conn = get_db()
    c = conn.cursor(dictionary=True, buffered=True)
    
    c.execute("SELECT userId, movieId FROM movie_comments WHERE id = %s", (comment_id,))
    comment = c.fetchone()
    
    if not comment:
        conn.close()
        return jsonify({'success': False, 'message': '评论不存在'})
    
    if comment['userId'] != current_user.id:
        conn.close()
        return jsonify({'success': False, 'message': '无权删除'})
    
    c.execute("DELETE FROM comment_interactions WHERE comment_id = %s", (comment_id,))
    c.execute("DELETE FROM movie_comments WHERE id = %s", (comment_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})


@app.route('/profile')
@login_required
def profile():
    conn = get_db()
    c = conn.cursor(dictionary=True, buffered=True)

    # 1. 查询基本统计：评分总数、平均分
    c.execute("""
              SELECT COUNT(*) as total_ratings, AVG(rating) as avg_rating
              FROM ratings
              WHERE userId = %s
              """, (current_user.id,))
    stats = c.fetchone()

    # 2. 查询评分历史（按时间降序，最新评分在前面）
    c.execute("""
              SELECT m.title, m.genres, r.rating, r.timestamp
              FROM ratings r
                       JOIN movies m ON r.movieId = m.movieId
              WHERE r.userId = %s
              ORDER BY r.timestamp DESC LIMIT 50
              """, (current_user.id,))
    rated_movies = c.fetchall()

    # 3. 计算偏好类型（只统计评分 >= 4 星的电影类型）—— 保留给你原来的标签云用
    genre_counter = Counter()
    for movie in rated_movies:
        if movie['genres'] and movie['rating'] >= 4.0:
            for genre in movie['genres'].split('|'):
                genre_counter[genre] += 1

    top_genres = genre_counter.most_common(5)  # 取前5个最喜欢的类型

    # ================= 新增：生成 Pyecharts 图表 =================

    # 图表1：全站评分分布（柱状图）
    c.execute("SELECT rating, COUNT(*) as count FROM ratings GROUP BY rating ORDER BY rating")
    dist_data = c.fetchall()

    bar = (
        Bar(init_opts=opts.InitOpts(width="100%", height="400px", bg_color="rgba(0,0,0,0)"))
        .add_xaxis([str(round(float(d['rating']), 1)) for d in dist_data])
        .add_yaxis(
            "评分人次",
            [d['count'] for d in dist_data],
            itemstyle_opts=opts.ItemStyleOpts(
                color=JsCode(
                    "new echarts.graphic.LinearGradient(0, 0, 0, 1, "
                    "[{offset: 0, color: '#722f37'}, {offset: 1, color: '#cba052'}])"
                )
            )
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(title="全站评分分布",
                                      title_textstyle_opts=opts.TextStyleOpts(color="#3a2e26", font_weight="normal")),
            xaxis_opts=opts.AxisOpts(name="星级", axislabel_opts=opts.LabelOpts(color="#8b796d")),
            yaxis_opts=opts.AxisOpts(name="评分人次", axislabel_opts=opts.LabelOpts(color="#8b796d")),
            tooltip_opts=opts.TooltipOpts(trigger="axis")
        )
    )
    rating_chart_html = bar.render_embed()  # 生成图表1的 HTML 片段

    # 图表2：个人口味雷达图
    # 注意：为了准确算平均分，这里重新查一次该用户所有评分记录，不受 LIMIT 50 限制
    c.execute("""
              SELECT r.rating, m.genres
              FROM ratings r
                       JOIN movies m ON r.movieId = m.movieId
              WHERE r.userId = %s
              """, (current_user.id,))
    genre_data = c.fetchall()

    radar_chart_html = ""
    has_radar = False
    if genre_data:
        radar_genre_stats = {}
        for row in genre_data:
            rating = float(row['rating'])
            genres_str = row['genres'] if row['genres'] else ''
            for genre in genres_str.split('|'):
                if not genre: continue
                if genre not in radar_genre_stats:
                    radar_genre_stats[genre] = {'total': 0, 'count': 0}
                radar_genre_stats[genre]['total'] += rating
                radar_genre_stats[genre]['count'] += 1

        # 取评分次数最多的前6个类型画雷达图
        top_radar_genres = sorted(radar_genre_stats.keys(), key=lambda g: radar_genre_stats[g]['count'], reverse=True)[
            :6]

        if top_radar_genres:
            has_radar = True
            labels = top_radar_genres
            scores = [round(radar_genre_stats[g]['total'] / radar_genre_stats[g]['count'], 2) for g in labels]

            radar = (
                Radar(init_opts=opts.InitOpts(width="100%", height="400px", bg_color="rgba(0,0,0,0)"))
                .add_schema(
                    schema=[opts.RadarIndicatorItem(name=label, max_=5.0) for label in labels],
                    axislabel_opt=opts.LabelOpts(color="#8b796d"),
                    shape="circle"
                )
                .add(
                    "平均评分",
                    [scores],
                    areastyle_opts=opts.AreaStyleOpts(opacity=0.3, color="#722f37"),
                    linestyle_opts=opts.LineStyleOpts(color="#722f37")  # 注意上面去掉了逗号
                )

                .set_global_opts(
                    title_opts=opts.TitleOpts(title="我的口味雷达",
                                              title_textstyle_opts=opts.TextStyleOpts(color="#3a2e26",
                                                                                      font_weight="normal"))

                )
            )
            radar_chart_html = radar.render_embed()  # 生成图表2的 HTML 片段

    # ============================================================

    conn.close()

    # 把图表 HTML 传给前端
    return render_template('profile.html',
                           user=current_user,
                           stats=stats,
                           rated_movies=rated_movies,
                           top_genres=top_genres,
                           rating_chart_html=rating_chart_html,
                           radar_chart_html=radar_chart_html,
                           has_radar=has_radar)


@app.route('/recommend')
@login_required
def recommend():
    conn = get_db()
    c = conn.cursor(dictionary=True)

    final_movies = []
    seen_movie_ids = set()

    # 1. 获取用户已看过的电影ID集合
    c.execute("SELECT movieId FROM ratings WHERE userId = %s", (current_user.id,))
    rated_ids = [int(row['movieId']) for row in c.fetchall()]

    # ------------------------------------------
    # 策略 A：基于用户的协同过滤（仅当用户有评分时执行）
    # ------------------------------------------
    if rated_ids:
        c.execute("SELECT movieId FROM ratings WHERE userId = %s AND rating >= 4", (current_user.id,))
        liked_movies = [int(row['movieId']) for row in c.fetchall()]

        if liked_movies:
            liked_placeholders = ','.join(['%s'] * len(liked_movies))

            # 找到与当前用户有共同喜好的其他用户
            query_similar_users = (
                "SELECT DISTINCT r2.userId, COUNT(*) as common_count "
                "FROM ratings r1 "
                "JOIN ratings r2 ON r1.userId != r2.userId AND r1.movieId = r2.movieId "
                "WHERE r1.userId = %s AND r1.rating >= 4 AND r2.rating >= 4 "
                "AND r1.movieId IN (" + liked_placeholders + ") "
                "GROUP BY r2.userId "
                "ORDER BY common_count DESC "
                "LIMIT 10"
            )
            c.execute(query_similar_users, tuple([current_user.id] + liked_movies))
            similar_users = [int(row['userId']) for row in c.fetchall()]

            if similar_users:
                # 找到这些相似用户喜欢但当前用户没看过的电影
                users_placeholders = ','.join(['%s'] * len(similar_users))
                liked_placeholders = ','.join(['%s'] * len(liked_movies))

                query_cf = (
                    "SELECT r.movieId, m.title, m.genres, "
                    "AVG(r.rating) as avg_rating, "
                    "COUNT(*) as recommend_count "
                    "FROM ratings r "
                    "JOIN movies m ON r.movieId = m.movieId "
                    "WHERE r.userId IN (" + users_placeholders + ") "
                    "AND r.rating >= 4 "
                    "AND r.movieId NOT IN (" + liked_placeholders + ") "
                    "GROUP BY r.movieId, m.title, m.genres "
                    "ORDER BY recommend_count DESC, avg_rating DESC "
                    "LIMIT 8"
                )
                c.execute(query_cf, tuple(similar_users + liked_movies))
                cf_movies = c.fetchall()

                for m in cf_movies:
                    mid = int(m['movieId'])
                    if mid not in seen_movie_ids:
                        m['rec_source'] = '协同过滤'
                        final_movies.append(m)
                        seen_movie_ids.add(mid)

    # ------------------------------------------
    # 策略 B：基于用户画像的偏好补充（仅当用户有评分且结果不足20时执行）
    # ------------------------------------------
    top_genres = []
    if rated_ids and len(final_movies) < 20:
        c.execute(
            "SELECT m.genres FROM ratings r JOIN movies m ON r.movieId = m.movieId WHERE r.userId = %s AND r.rating >= 4",
            (current_user.id,)
        )
        genre_rows = c.fetchall()

        genre_counter = Counter()
        for row in genre_rows:
            if row['genres']:
                for genre in row['genres'].split('|'):
                    genre_counter[genre] += 1
        top_genres = [g[0] for g in genre_counter.most_common(3)]

        if top_genres:
            # 构建类型匹配条件：genres LIKE '%Action%' OR genres LIKE '%Comedy%' ...
            genre_conditions = ' OR '.join(["m.genres LIKE %s" for _ in top_genres])
            genre_params = [f'%{g}%' for g in top_genres]

            if seen_movie_ids:
                exclude_placeholders = ','.join(['%s'] * len(seen_movie_ids))
                query_profile = (
                    "SELECT m.movieId, m.title, m.genres, AVG(r.rating) as avg_rating, COUNT(r.rating) as rating_count "
                    "FROM movies m "
                    "JOIN ratings r ON m.movieId = r.movieId "
                    "WHERE (" + genre_conditions + ") "
                    "AND m.movieId NOT IN (" + exclude_placeholders + ") "
                    "GROUP BY m.movieId "
                    "ORDER BY avg_rating DESC, rating_count DESC "
                    "LIMIT 6"
                )
                c.execute(query_profile, tuple(genre_params + list(seen_movie_ids)))
            else:
                query_profile = (
                    "SELECT m.movieId, m.title, m.genres, AVG(r.rating) as avg_rating, COUNT(r.rating) as rating_count "
                    "FROM movies m "
                    "JOIN ratings r ON m.movieId = r.movieId "
                    "WHERE (" + genre_conditions + ") "
                    "GROUP BY m.movieId "
                    "ORDER BY avg_rating DESC, rating_count DESC "
                    "LIMIT 6"
                )
                c.execute(query_profile, tuple(genre_params))

            profile_movies = c.fetchall()

            for m in profile_movies:
                mid = int(m['movieId'])
                if mid not in seen_movie_ids:
                    m['rec_source'] = '画像偏好'
                    final_movies.append(m)
                    seen_movie_ids.add(mid)

    # ------------------------------------------
    # 策略 C：热门精选补充（限制最多6部）
    # ------------------------------------------
    if len(final_movies) < 20:
        # 简单查询：获取有评分的电影，按评分数量排序
        if seen_movie_ids:
            exclude_placeholders = ','.join(['%s'] * len(seen_movie_ids))
            query_hot = (
                "SELECT m.movieId, m.title, m.genres, AVG(r.rating) as avg_rating, COUNT(r.rating) as rating_count "
                "FROM movies m JOIN ratings r ON m.movieId = r.movieId "
                "WHERE m.movieId NOT IN (" + exclude_placeholders + ") "
                "GROUP BY m.movieId "
                "ORDER BY rating_count DESC, avg_rating DESC "
                "LIMIT 6"
            )
            c.execute(query_hot, tuple(list(seen_movie_ids)))
        else:
            query_hot = (
                "SELECT m.movieId, m.title, m.genres, AVG(r.rating) as avg_rating, COUNT(r.rating) as rating_count "
                "FROM movies m JOIN ratings r ON m.movieId = r.movieId "
                "GROUP BY m.movieId "
                "ORDER BY rating_count DESC, avg_rating DESC "
                "LIMIT 6"
            )
            c.execute(query_hot)

        hot_movies = c.fetchall()

        for m in hot_movies:
            mid = int(m['movieId'])
            if mid not in seen_movie_ids:
                m['rec_source'] = '热门精选'
                final_movies.append(m)
                seen_movie_ids.add(mid)

    # ------------------------------------------
    # 策略 D：冷启动兜底（用户完全没有评分时）
    # ------------------------------------------
    if not final_movies:
        c.execute(
            "SELECT m.movieId, m.title, m.genres, AVG(r.rating) as avg_rating, COUNT(r.rating) as rating_count "
            "FROM movies m JOIN ratings r ON m.movieId = r.movieId "
            "GROUP BY m.movieId "
            "ORDER BY rating_count DESC, avg_rating DESC "
            "LIMIT 20"
        )
        global_movies = c.fetchall()
        for m in global_movies:
            m['rec_source'] = '热门精选'
            final_movies.append(m)

    conn.close()

    return render_template('recommend.html', user=current_user, movies=final_movies, top_genres=top_genres)


@app.route('/like_comment/<int:comment_id>', methods=['POST'])
@login_required
def like_comment(comment_id):
    conn = get_db()
    c = conn.cursor(dictionary=True, buffered=True)

    # 查看当前用户是否已经点赞
    c.execute("""
              SELECT id
              FROM comment_interactions
              WHERE comment_id = %s
                AND userId = %s
              """, (comment_id, current_user.id))
    existing_like = c.fetchone()

    if existing_like:
        # 已经点赞 -> 取消点赞
        c.execute("DELETE FROM comment_interactions WHERE id = %s", (existing_like['id'],))
        c.execute("UPDATE movie_comments SET likes_count = likes_count - 1 WHERE id = %s", (comment_id,))
        is_liked = False
    else:
        # 未点赞 -> 点赞
        c.execute("""
                  INSERT INTO comment_interactions (comment_id, userId, interaction_type)
                  VALUES (%s, %s, 1)
                  """, (comment_id, current_user.id))
        c.execute("UPDATE movie_comments SET likes_count = likes_count + 1 WHERE id = %s", (comment_id,))
        is_liked = True

    conn.commit()

    # 获取最新的点赞数
    c.execute("SELECT likes_count FROM movie_comments WHERE id = %s", (comment_id,))
    likes_count = c.fetchone()['likes_count']
    conn.close()

    # 返回 JSON 给前端 JS 处理
    return jsonify({"is_liked": is_liked, "likes_count": likes_count})

# 登出路由
@app.route('/logout')
@login_required  # 必须登录才能访问
def logout():
    logout_user()
    flash('已退出登录！')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run()
