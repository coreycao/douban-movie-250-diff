import unittest
import time
import threading
from src.spider import RateLimiter


class TestRateLimiterBasicFunctionality(unittest.TestCase):
    """测试 RateLimiter 基础功能"""

    def test_initial_tokens_equal_capacity(self):
        """初始令牌数应等于容量"""
        limiter = RateLimiter(rate=1.0, capacity=5)
        self.assertEqual(limiter.tokens, 5)

    def test_single_acquire_reduces_tokens(self):
        """单次获取应减少一个令牌"""
        limiter = RateLimiter(rate=1.0, capacity=5)
        limiter.acquire()
        self.assertEqual(limiter.tokens, 4)

    def test_consume_all_tokens(self):
        """消耗所有令牌"""
        limiter = RateLimiter(rate=1.0, capacity=3)
        limiter.acquire()
        limiter.acquire()
        limiter.acquire()
        # 允许微小浮点误差
        self.assertLessEqual(limiter.tokens, 0.001)

    def test_rate_and_capacity_parameters(self):
        """验证参数正确设置"""
        rate = 2.5
        capacity = 10
        limiter = RateLimiter(rate=rate, capacity=capacity)
        self.assertEqual(limiter.rate, rate)
        self.assertEqual(limiter.capacity, capacity)


class TestRateLimiterTokenRefill(unittest.TestCase):
    """测试令牌恢复机制"""

    def test_tokens_refill_over_time(self):
        """令牌应随时间恢复"""
        limiter = RateLimiter(rate=10.0, capacity=5)  # 每秒10个令牌

        # 消耗所有令牌
        for _ in range(5):
            limiter.acquire()
        self.assertLessEqual(limiter.tokens, 0.001)

        # 等待0.25秒，应恢复约2.5个令牌
        time.sleep(0.25)
        limiter.acquire()  # 触发令牌计算

        # tokens 应该在 1.5-2.5 之间（允许一些误差）
        self.assertGreater(limiter.tokens, 1.5)
        self.assertLess(limiter.tokens, 2.5)

    def test_tokens_not_exceed_capacity(self):
        """令牌数不应超过容量"""
        limiter = RateLimiter(rate=10.0, capacity=3)

        # 消耗一些令牌
        limiter.acquire()
        self.assertEqual(limiter.tokens, 2)

        # 等待足够时间让令牌恢复
        time.sleep(1)

        # 获取令牌触发计算
        limiter.acquire()

        # 令牌不应超过容量
        self.assertLessEqual(limiter.tokens, 3)

    def test_slow_refill_rate(self):
        """测试低速率恢复"""
        limiter = RateLimiter(rate=1.0, capacity=5)  # 每秒1个令牌

        # 消耗所有令牌
        for _ in range(5):
            limiter.acquire()

        # 等待1.1秒，应恢复约1.1个令牌
        time.sleep(1.1)
        limiter.acquire()

        # 减去刚消耗的1个令牌，应该还有约0.1个
        self.assertGreater(limiter.tokens, 0.05)
        self.assertLess(limiter.tokens, 0.2)


class TestRateLimiterRateLimiting(unittest.TestCase):
    """测试限流行为"""

    def test_waiting_when_exhausted(self):
        """令牌不足时应等待"""
        limiter = RateLimiter(rate=2.0, capacity=1)  # 每秒2个令牌，容量1

        start_time = time.time()

        # 消耗所有令牌
        limiter.acquire()

        # 再次获取，需要等待约0.5秒（1令牌 / 2令牌/秒）
        limiter.acquire()

        elapsed = time.time() - start_time

        # 应该等待了至少0.3秒（允许误差）
        self.assertGreater(elapsed, 0.3)

    def test_continuous_rate_limiting(self):
        """测试持续限流"""
        limiter = RateLimiter(rate=5.0, capacity=5)

        # 消耗容量
        for _ in range(5):
            limiter.acquire()

        start_time = time.time()

        # 尝试获取3个额外令牌
        for _ in range(3):
            limiter.acquire()

        elapsed = time.time() - start_time

        # 应该等待约0.6秒（3令牌 / 5令牌/秒），放宽下限到0.4
        self.assertGreater(elapsed, 0.4)
        self.assertLess(elapsed, 0.8)


class TestRateLimiterEdgeCases(unittest.TestCase):
    """测试边界条件"""

    def test_capacity_of_one(self):
        """容量为1的情况"""
        limiter = RateLimiter(rate=1.0, capacity=1)
        self.assertEqual(limiter.tokens, 1)

    def test_very_low_rate(self):
        """非常低的速率"""
        limiter = RateLimiter(rate=0.1, capacity=1)  # 每10秒1个令牌

        limiter.acquire()
        self.assertEqual(limiter.tokens, 0)

    def test_high_rate_high_capacity(self):
        """高速率高容量"""
        limiter = RateLimiter(rate=100.0, capacity=100)
        self.assertEqual(limiter.tokens, 100)

    def test_zero_time_elapsed(self):
        """时间零流逝时不应恢复令牌（恢复极小）"""
        limiter = RateLimiter(rate=10.0, capacity=5)

        limiter.acquire()
        tokens_after = limiter.tokens

        # 立即再次获取（时间流逝极小）
        limiter.acquire()

        # 令牌应该减少约1，可能有微小的恢复（< 0.1）
        self.assertLess(limiter.tokens, tokens_after - 0.9)

    def test_small_capacity_fractional_rate(self):
        """小容量和小数速率"""
        limiter = RateLimiter(rate=0.5, capacity=2)
        self.assertEqual(limiter.tokens, 2)


class TestRateLimiterConcurrency(unittest.TestCase):
    """测试并发安全性"""

    def test_concurrent_acquire(self):
        """多线程并发获取令牌"""
        limiter = RateLimiter(rate=10.0, capacity=10)
        results = []
        errors = []

        def worker():
            try:
                for _ in range(5):
                    limiter.acquire()
                    results.append(threading.current_thread().name)
            except Exception as e:
                errors.append(e)

        # 创建多个线程
        threads = []
        for i in range(3):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 不应该有错误
        self.assertEqual(len(errors), 0)
        # 应该处理了所有请求
        self.assertEqual(len(results), 15)

    def test_no_race_condition(self):
        """测试无竞态条件"""
        limiter = RateLimiter(rate=1.0, capacity=5)

        def rapid_acquires():
            for _ in range(10):
                limiter.acquire()

        threads = []
        for _ in range(3):
            t = threading.Thread(target=rapid_acquires)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 最终令牌数应该是正确的
        # 30次获取，容量5，速率1，所以应该大约等待25秒
        # 令牌应该接近0
        self.assertGreaterEqual(limiter.tokens, 0)
        self.assertLessEqual(limiter.tokens, 5)


class TestRateLimiterRealWorldScenarios(unittest.TestCase):
    """测试真实场景"""

    def test_spider_rate_limiting_scenario(self):
        """模拟爬虫限流场景：0.3 req/s"""
        limiter = RateLimiter(rate=0.3, capacity=3)

        # 消耗容量
        for _ in range(3):
            limiter.acquire()

        start_time = time.time()

        # 获取第4个令牌
        limiter.acquire()

        elapsed = time.time() - start_time

        # 应该等待约3.3秒（1令牌 / 0.3令牌/秒）
        self.assertGreater(elapsed, 3.0)
        self.assertLess(elapsed, 3.6)

    def test_burst_then_steady(self):
        """突发请求后稳定速率"""
        limiter = RateLimiter(rate=2.0, capacity=5)

        # 突发：消耗容量
        for _ in range(5):
            limiter.acquire()
        self.assertLessEqual(limiter.tokens, 0.001)

        # 稳定速率：每0.5秒一个请求
        start_time = time.time()
        for _ in range(3):
            limiter.acquire()
        elapsed = time.time() - start_time

        # 应该等待约1秒（因为令牌在等待期间也在恢复）
        # 实际时间会少于理论值，因为令牌在等待期间恢复
        self.assertGreater(elapsed, 0.9)
        self.assertLess(elapsed, 1.3)


if __name__ == '__main__':
    unittest.main()
