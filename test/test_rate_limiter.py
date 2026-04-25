import unittest
import threading
from unittest.mock import patch
from src.spider import RateLimiter


class MockClock:
    """模拟时钟，用于控制 RateLimiter 中的 time() 和 sleep() 调用，避免真实延迟"""

    def __init__(self, start=1000.0):
        self._time = start
        self.sleep_calls = []

    def time_func(self):
        return self._time

    def sleep_func(self, seconds):
        self.sleep_calls.append(seconds)
        self._time += seconds

    def advance(self, seconds):
        """手动推进模拟时间"""
        self._time += seconds


class TestRateLimiterBasicFunctionality(unittest.TestCase):
    """测试 RateLimiter 基础功能（不依赖时间）"""

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


class _MockedTimeTestCase(unittest.TestCase):
    """使用模拟时钟的测试基类"""

    def setUp(self):
        self.clock = MockClock()
        self.time_patcher = patch('src.spider.time', side_effect=self.clock.time_func)
        self.sleep_patcher = patch('src.spider.sleep', side_effect=self.clock.sleep_func)
        self.time_patcher.start()
        self.sleep_patcher.start()

    def tearDown(self):
        self.time_patcher.stop()
        self.sleep_patcher.stop()


class TestRateLimiterTokenRefill(_MockedTimeTestCase):
    """测试令牌恢复机制"""

    def test_tokens_refill_over_time(self):
        """令牌应随时间恢复"""
        limiter = RateLimiter(rate=10.0, capacity=5)

        # 消耗所有令牌
        for _ in range(5):
            limiter.acquire()
        self.assertLessEqual(limiter.tokens, 0.001)

        # 推进模拟时间 0.25 秒，应恢复约 2.5 个令牌
        self.clock.advance(0.25)
        limiter.acquire()

        # 恢复 2.5 - 消耗 1 = 1.5
        self.assertGreater(limiter.tokens, 1.4)
        self.assertLess(limiter.tokens, 1.6)

    def test_tokens_not_exceed_capacity(self):
        """令牌数不应超过容量"""
        limiter = RateLimiter(rate=10.0, capacity=3)

        # 消耗一些令牌
        limiter.acquire()
        self.assertEqual(limiter.tokens, 2)

        # 推进足够时间让令牌恢复
        self.clock.advance(1)
        limiter.acquire()

        # 令牌不应超过容量
        self.assertLessEqual(limiter.tokens, 3)

    def test_slow_refill_rate(self):
        """测试低速率恢复"""
        limiter = RateLimiter(rate=1.0, capacity=5)

        # 消耗所有令牌
        for _ in range(5):
            limiter.acquire()

        # 推进模拟时间 1.1 秒，应恢复约 1.1 个令牌
        self.clock.advance(1.1)
        limiter.acquire()

        # 恢复 1.1 - 消耗 1 = 0.1
        self.assertGreater(limiter.tokens, 0.05)
        self.assertLess(limiter.tokens, 0.2)


class TestRateLimiterRateLimiting(_MockedTimeTestCase):
    """测试限流行为"""

    def test_waiting_when_exhausted(self):
        """令牌不足时应通过 sleep 等待"""
        limiter = RateLimiter(rate=2.0, capacity=1)

        # 消耗所有令牌
        limiter.acquire()
        self.clock.sleep_calls.clear()

        # 再次获取，需要等待约 0.5 秒（1令牌 / 2令牌/秒）
        limiter.acquire()

        # 验证 sleep 被调用了正确的等待时间
        self.assertTrue(len(self.clock.sleep_calls) > 0)
        self.assertAlmostEqual(self.clock.sleep_calls[-1], 0.5, places=1)

    def test_continuous_rate_limiting(self):
        """测试持续限流"""
        limiter = RateLimiter(rate=5.0, capacity=5)

        # 消耗容量
        for _ in range(5):
            limiter.acquire()
        self.clock.sleep_calls.clear()

        # 尝试获取 3 个额外令牌（其中 2 次需要 sleep）
        for _ in range(3):
            limiter.acquire()

        # 总等待时间应约为 0.4 秒（2 次 sleep 各约 0.2 秒）
        total_sleep = sum(self.clock.sleep_calls)
        self.assertGreater(total_sleep, 0.3)
        self.assertLess(total_sleep, 1.0)


class TestRateLimiterEdgeCases(_MockedTimeTestCase):
    """测试边界条件"""

    def test_capacity_of_one(self):
        """容量为1的情况"""
        limiter = RateLimiter(rate=1.0, capacity=1)
        self.assertEqual(limiter.tokens, 1)

    def test_very_low_rate(self):
        """非常低的速率"""
        limiter = RateLimiter(rate=0.1, capacity=1)

        limiter.acquire()
        self.assertEqual(limiter.tokens, 0)

    def test_high_rate_high_capacity(self):
        """高速率高容量"""
        limiter = RateLimiter(rate=100.0, capacity=100)
        self.assertEqual(limiter.tokens, 100)

    def test_zero_time_elapsed(self):
        """模拟时间不流逝时令牌精确减少"""
        limiter = RateLimiter(rate=10.0, capacity=5)

        limiter.acquire()
        tokens_after = limiter.tokens

        # 模拟时间未推进，令牌精确减少 1
        limiter.acquire()

        self.assertAlmostEqual(limiter.tokens, tokens_after - 1, places=5)

    def test_small_capacity_fractional_rate(self):
        """小容量和小数速率"""
        limiter = RateLimiter(rate=0.5, capacity=2)
        self.assertEqual(limiter.tokens, 2)


class TestRateLimiterConcurrency(_MockedTimeTestCase):
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

        # 最终令牌数应该在有效范围内
        self.assertGreaterEqual(limiter.tokens, 0)
        self.assertLessEqual(limiter.tokens, 5)


class TestRateLimiterRealWorldScenarios(_MockedTimeTestCase):
    """测试真实场景"""

    def test_spider_rate_limiting_scenario(self):
        """模拟爬虫限流场景：0.3 req/s"""
        limiter = RateLimiter(rate=0.3, capacity=3)

        # 消耗容量
        for _ in range(3):
            limiter.acquire()
        self.clock.sleep_calls.clear()

        # 获取第 4 个令牌，应等待约 3.3 秒
        limiter.acquire()

        self.assertTrue(len(self.clock.sleep_calls) > 0)
        self.assertAlmostEqual(self.clock.sleep_calls[-1], 1 / 0.3, places=1)

    def test_burst_then_steady(self):
        """突发请求后稳定速率"""
        limiter = RateLimiter(rate=2.0, capacity=5)

        # 突发：消耗容量
        for _ in range(5):
            limiter.acquire()
        self.assertLessEqual(limiter.tokens, 0.001)
        self.clock.sleep_calls.clear()

        # 稳定速率：继续请求，应有 sleep 调用
        for _ in range(3):
            limiter.acquire()

        total_sleep = sum(self.clock.sleep_calls)
        self.assertGreater(total_sleep, 0)


if __name__ == '__main__':
    unittest.main()
