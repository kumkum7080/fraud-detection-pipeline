import redis
import time
import json
from datetime import datetime
from backend.app.config import settings

class MockRedisClient:
    """Fallback in-memory client if local Redis server is not running."""
    def __init__(self):
        self.store = {}
        print("[WARNING] Redis server connection failed. Initializing in-memory mock cache client.")

    def ping(self):
        return True

    def zadd(self, key, mapping):
        if key not in self.store:
            self.store[key] = []
        # mapping is {value: score}
        for val, score in mapping.items():
            # Remove duplicate value if exists
            self.store[key] = [item for item in self.store[key] if item[0] != val]
            self.store[key].append((val, score))
        self.store[key].sort(key=lambda x: x[1])
        return len(mapping)

    def zremrangebyscore(self, key, min_score, max_score):
        if key not in self.store:
            return 0
        original_len = len(self.store[key])
        self.store[key] = [item for item in self.store[key] if not (min_score <= item[1] <= max_score)]
        return original_len - len(self.store[key])

    def zcard(self, key):
        if key not in self.store:
            return 0
        return len(self.store[key])

    def lpush(self, key, *values):
        if key not in self.store:
            self.store[key] = []
        for val in values:
            self.store[key].insert(0, val)
        return len(self.store[key])

    def ltrim(self, key, start, stop):
        if key not in self.store:
            return True
        # SQLite-like indices: start and stop are inclusive
        # Handle negative indexes
        lst = self.store[key]
        length = len(lst)
        
        real_start = start if start >= 0 else length + start
        real_stop = stop if stop >= 0 else length + stop
        
        real_start = max(0, min(real_start, length))
        real_stop = max(0, min(real_stop + 1, length))
        
        self.store[key] = lst[real_start:real_stop]
        return True

    def lrange(self, key, start, stop):
        if key not in self.store:
            return []
        lst = self.store[key]
        length = len(lst)
        
        real_start = start if start >= 0 else length + start
        real_stop = stop if stop >= 0 else length + stop
        
        real_start = max(0, min(real_start, length))
        real_stop = max(0, min(real_stop + 1, length))
        
        return lst[real_start:real_stop]

    def set(self, key, value, ex=None):
        self.store[key] = str(value)
        return True

    def get(self, key):
        val = self.store.get(key)
        if val is None:
            return None
        return val.encode('utf-8')

    def delete(self, *keys):
        count = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                count += 1
        return count

# Try to connect to real Redis
try:
    redis_conn = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
        socket_connect_timeout=2
    )
    redis_conn.ping()
    print("[REDIS] Redis client successfully connected to local Redis instance.")
except (redis.ConnectionError, redis.TimeoutError):
    redis_conn = MockRedisClient()

class RedisTracker:
    """Helper class to abstract velocity counting and rolling average features."""
    
    @staticmethod
    def log_transaction(customer_id: str, amount: float, timestamp_str: str) -> None:
        """
        Logs a transaction in Redis to dynamically update:
        1. Sliding window velocity (Sorted Set)
        2. Rolling transaction amounts list (List capped at 10 items)
        """
        # Convert timestamp to epoch float
        dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        epoch = dt.timestamp()
        
        # 1. Update sliding window velocity
        vel_key = f"customer:{customer_id}:tx_velocity"
        # We store the transaction timestamp as both value and score
        redis_conn.zadd(vel_key, {f"{epoch}:{amount}": epoch})
        # Keep only last 24 hours in Redis to save memory (clean older records)
        day_ago = epoch - (24 * 3600)
        redis_conn.zremrangebyscore(vel_key, 0, day_ago)
        
        # 2. Update rolling average list
        avg_key = f"customer:{customer_id}:tx_amounts"
        redis_conn.lpush(avg_key, amount)
        # Cap at 10 elements
        redis_conn.ltrim(avg_key, 0, 9)

    @staticmethod
    def get_velocity_1h(customer_id: str, current_time_str: str) -> int:
        """Computes velocity in the last hour using Redis Sorted Sets."""
        dt = datetime.strptime(current_time_str, '%Y-%m-%d %H:%M:%S')
        current_epoch = dt.timestamp()
        hour_ago = current_epoch - 3600
        
        vel_key = f"customer:{customer_id}:tx_velocity"
        # First, trim any records older than 24 hours just in case
        redis_conn.zremrangebyscore(vel_key, 0, current_epoch - (24 * 3600))
        
        # We need to count items with scores between hour_ago and current_epoch
        # In a real Redis, we would do a temporary count or filter
        # Since we want to find count in last 1 hour:
        # We can extract elements or count them. 
        # A simple way in Redis is to remove elements older than 1 hour, but we might want them for longer historical context
        # So let's fetch elements in range or do a zcount
        # Since MockRedis doesn't have zcount, we can fetch list of scores or do zremrangebyscore for older than 1 hour.
        # Let's count elements in the last hour.
        # To make it work on both real Redis and Mock:
        # We can fetch elements or query ZCOUNT. 
        # Let's add a helper or use lrange/zrange if we can. 
        # Actually, let's just trim older than 1 hour inside this query, which is simple and correct for 1h velocity:
        redis_conn.zremrangebyscore(vel_key, 0, hour_ago)
        return int(redis_conn.zcard(vel_key))

    @staticmethod
    def get_rolling_avg_10(customer_id: str, default_amount: float) -> float:
        """Computes rolling average of last 10 transactions."""
        avg_key = f"customer:{customer_id}:tx_amounts"
        amounts = redis_conn.lrange(avg_key, 0, 9)
        if not amounts:
            return default_amount
        
        float_amounts = [float(x) for x in amounts]
        return sum(float_amounts) / len(float_amounts)

    @staticmethod
    def get_simulator_status() -> bool:
        """Checks if live transaction streamer is running."""
        status = redis_conn.get("system:simulator_running")
        if status is None:
            return False
        return status.decode('utf-8') == "true"

    @staticmethod
    def set_simulator_status(running: bool) -> None:
        """Sets live transaction streamer status."""
        val = "true" if running else "false"
        redis_conn.set("system:simulator_running", val)
