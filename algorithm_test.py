"""
算法效果测试脚本
评估协同过滤推荐算法的质量
"""
import sys
import os
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import get_db
from collections import Counter


class AlgorithmEvaluator:
    def __init__(self, train_ratio=0.8):
        self.train_ratio = train_ratio
        self.train_ratings = []
        self.test_ratings = []
        self.all_users = set()
        self.all_movies = set()
        self.user_train_ratings = defaultdict(list)
        self.user_test_ratings = defaultdict(list)
        
    def load_and_split_data(self):
        """加载数据并划分为训练集和测试集"""
        print("📊 加载评分数据...")
        conn = get_db()
        c = conn.cursor(dictionary=True)
        c.execute("""
            SELECT userId, movieId, rating, timestamp 
            FROM ratings 
            ORDER BY userId, timestamp
        """)
        all_ratings = c.fetchall()
        c.close()
        conn.close()
        
        print(f"   总评分记录: {len(all_ratings)}")
        
        ratings_by_user = defaultdict(list)
        for r in all_ratings:
            ratings_by_user[r['userId']].append(r)
        
        for user_id, ratings in ratings_by_user.items():
            self.all_users.add(user_id)
            split_idx = int(len(ratings) * self.train_ratio)
            
            for i, rating in enumerate(ratings[:split_idx]):
                self.user_train_ratings[user_id].append(rating)
                self.train_ratings.append(rating)
                
            for rating in ratings[split_idx:]:
                self.user_test_ratings[user_id].append(rating)
                self.test_ratings.append(rating)
            
            for r in ratings:
                self.all_movies.add(r['movieId'])
        
        print(f"   训练集评分: {len(self.train_ratings)}")
        print(f"   测试集评分: {len(self.test_ratings)}")
        print(f"   用户数: {len(self.all_users)}")
        print(f"   电影数: {len(self.all_movies)}")
        
    def collaborative_filtering_recommend(self, user_id, top_n=10):
        """基于用户的协同过滤推荐"""
        if user_id not in self.user_train_ratings:
            return []
        
        user_rated = set(m['movieId'] for m in self.user_train_ratings[user_id])
        user_positive = set(m['movieId'] for m in self.user_train_ratings[user_id] if m['rating'] >= 4)
        
        if not user_positive:
            return []
        
        similar_users = []
        for other_user in self.all_users:
            if other_user == user_id:
                continue
            
            other_positive = set(m['movieId'] for m in self.user_train_ratings[other_user] if m['rating'] >= 4)
            common = len(user_positive & other_positive)
            
            if common > 0:
                similar_users.append((other_user, common))
        
        similar_users.sort(key=lambda x: -x[1])
        similar_users = similar_users[:10]
        
        movie_scores = Counter()
        for other_user, _ in similar_users:
            for rating in self.user_train_ratings[other_user]:
                if rating['rating'] >= 4 and rating['movieId'] not in user_rated:
                    movie_scores[rating['movieId']] += 1
        
        return [m[0] for m in movie_scores.most_common(top_n)]
    
    def popularity_based_recommend(self, top_n=10):
        """基于热度的推荐（作为基线）"""
        movie_counts = Counter()
        for r in self.train_ratings:
            movie_counts[r['movieId']] += 1
        return [m[0] for m in movie_counts.most_common(top_n)]
    
    def calculate_precision_recall(self, recommendations, test_movies):
        """计算精确率和召回率"""
        if not recommendations:
            return 0.0, 0.0
        
        hit = len(set(recommendations) & set(test_movies))
        precision = hit / len(recommendations)
        recall = hit / len(test_movies) if test_movies else 0.0
        
        return precision, recall
    
    def calculate_coverage(self, recommendations):
        """计算覆盖率"""
        if not recommendations:
            return 0.0
        return len(set(recommendations)) / len(self.all_movies)
    
    def calculate_diversity(self, recommendations):
        """计算推荐多样性（类型覆盖）"""
        if not recommendations:
            return 0.0
        
        conn = get_db()
        c = conn.cursor()
        
        movie_ids = ','.join(['%s'] * len(recommendations))
        c.execute(f"SELECT genres FROM movies WHERE movieId IN ({movie_ids})", tuple(recommendations))
        genres_list = c.fetchall()
        c.close()
        conn.close()
        
        all_genres = set()
        for (genres,) in genres_list:
            if genres:
                for g in genres.split('|'):
                    all_genres.add(g)
        
        return len(all_genres)
    
    def evaluate_algorithm(self, algorithm_name, recommend_func):
        """评估指定算法"""
        print(f"\n🔍 评估 {algorithm_name}...")
        
        precisions = []
        recalls = []
        all_recommendations = []
        
        # 采样300个有测试集的用户，平衡计算速度和数据代表性
        valid_users = [u for u in self.all_users if u in self.user_test_ratings and self.user_test_ratings[u]]
        sample_users = valid_users[:300] if len(valid_users) > 300 else valid_users
        
        print(f"   评估用户数: {len(sample_users)}")
        
        for user_id in sample_users:
            test_movies = [m['movieId'] for m in self.user_test_ratings[user_id]]
            
            if algorithm_name == "协同过滤":
                recs = recommend_func(user_id, top_n=10)
            else:
                recs = recommend_func(top_n=10)
            
            all_recommendations.extend(recs)
            
            precision, recall = self.calculate_precision_recall(recs, test_movies)
            precisions.append(precision)
            recalls.append(recall)
        
        avg_precision = sum(precisions) / len(precisions) if precisions else 0
        avg_recall = sum(recalls) / len(recalls) if recalls else 0
        f1_score = 2 * avg_precision * avg_recall / (avg_precision + avg_recall) if (avg_precision + avg_recall) > 0 else 0
        coverage = self.calculate_coverage(all_recommendations)
        diversity = self.calculate_diversity(all_recommendations)
        
        print(f"   平均精确率: {avg_precision:.4f}")
        print(f"   平均召回率: {avg_recall:.4f}")
        print(f"   F1 分数: {f1_score:.4f}")
        print(f"   覆盖率: {coverage:.4f}")
        print(f"   推荐多样性: {diversity} 种类型")
        
        return {
            'precision': avg_precision,
            'recall': avg_recall,
            'f1': f1_score,
            'coverage': coverage,
            'diversity': diversity
        }
    
    def run_evaluation(self):
        """运行完整评估"""
        print("=" * 60)
        print("电影推荐系统 - 算法效果测试")
        print("=" * 60)
        
        self.load_and_split_data()
        
        cf_results = self.evaluate_algorithm(
            "协同过滤",
            self.collaborative_filtering_recommend
        )
        
        pop_results = self.evaluate_algorithm(
            "热门推荐(基线)",
            self.popularity_based_recommend
        )
        
        print("\n" + "=" * 60)
        print("【对比分析】")
        print("=" * 60)
        print(f"{'指标':<15} {'协同过滤':<15} {'热门推荐':<15} {'提升':<15}")
        print("-" * 60)
        
        for key in ['precision', 'recall', 'f1', 'coverage']:
            cf_val = cf_results[key]
            pop_val = pop_results[key]
            improve = ((cf_val - pop_val) / pop_val * 100) if pop_val > 0 else 0
            improve_str = f"+{improve:.1f}%" if improve > 0 else f"{improve:.1f}%"
            print(f"{key:<15} {cf_val:<15.4f} {pop_val:<15.4f} {improve_str:<15}")
        
        print("=" * 60)
        
        return cf_results, pop_results


def generate_test_report(cf_results, pop_results):
    """生成测试报告"""
    report = f"""# 算法效果测试报告

## 测试概述

| 项目 | 内容 |
|-----|------|
| 测试日期 | 2026-05-21 |
| 测试类型 | 离线评估 |
| 评估方法 | 训练集/测试集划分（80%/20%）|

## 测试指标说明

| 指标 | 说明 | 理想值 |
|-----|------|-------|
| 精确率 (Precision) | 推荐的电影中用户实际喜欢的比例 | 越高越好 |
| 召回率 (Recall) | 用户喜欢的电影中被推荐的比例 | 越高越好 |
| F1 分数 | 精确率和召回率的调和平均 | 越高越好 |
| 覆盖率 (Coverage) | 推荐结果覆盖的电影比例 | 越高越好 |
| 多样性 (Diversity) | 推荐列表中电影类型的丰富程度 | 越高越好 |

## 测试结果

### 协同过滤推荐算法

| 指标 | 数值 |
|-----|------|
| 精确率 | {cf_results['precision']:.4f} |
| 召回率 | {cf_results['recall']:.4f} |
| F1 分数 | {cf_results['f1']:.4f} |
| 覆盖率 | {cf_results['coverage']:.4f} |
| 多样性 | {cf_results['diversity']} 种类型 |

### 热门推荐算法（基线）

| 指标 | 数值 |
|-----|------|
| 精确率 | {pop_results['precision']:.4f} |
| 召回率 | {pop_results['recall']:.4f} |
| F1 分数 | {pop_results['f1']:.4f} |
| 覆盖率 | {pop_results['coverage']:.4f} |
| 多样性 | {pop_results['diversity']} 种类型 |

### 算法对比

| 指标 | 协同过滤 | 热门推荐 | 提升幅度 |
|-----|---------|---------|---------|
| 精确率 | {cf_results['precision']:.4f} | {pop_results['precision']:.4f} | {((cf_results['precision'] - pop_results['precision']) / pop_results['precision'] * 100) if pop_results['precision'] > 0 else 0:+.1f}% |
| 召回率 | {cf_results['recall']:.4f} | {pop_results['recall']:.4f} | {((cf_results['recall'] - pop_results['recall']) / pop_results['recall'] * 100) if pop_results['recall'] > 0 else 0:+.1f}% |
| F1 分数 | {cf_results['f1']:.4f} | {pop_results['f1']:.4f} | {((cf_results['f1'] - pop_results['f1']) / pop_results['f1'] * 100) if pop_results['f1'] > 0 else 0:+.1f}% |

## 结论

1. **协同过滤算法**在精确率和召回率上{"优于" if cf_results['precision'] > pop_results['precision'] else "劣于"}热门推荐基线
2. F1 分数为 {cf_results['f1']:.4f}，{"表明算法具有良好的综合性能" if cf_results['f1'] > 0.1 else "表明算法仍有优化空间"}
3. 推荐覆盖率为 {cf_results['coverage']:.2%}，{"能够覆盖较多电影" if cf_results['coverage'] > 0.1 else "覆盖范围有限"}

## 测试方法

1. 将所有评分数据按 80%/20% 划分为训练集和测试集
2. 使用训练集数据生成推荐列表
3. 在测试集上计算各项评估指标
4. 对比协同过滤算法与热门推荐基线的表现
"""
    
    with open('算法效果测试报告.md', 'w', encoding='utf-8') as f:
        f.write(report)
    
    print("📄 报告已生成: 算法效果测试报告.md")


def main():
    evaluator = AlgorithmEvaluator(train_ratio=0.8)
    cf_results, pop_results = evaluator.run_evaluation()
    generate_test_report(cf_results, pop_results)


if __name__ == '__main__':
    main()
