import redis

class RedisClient:
    def __init__(
        self,
        host: str,
        port: int,
        password: str,
    ):
        self.redis_client = redis.StrictRedis(
            host=host,  # Tên container redis trong mạng Docker
            port=port,     # Port mặc định của Redis
            password=password,  # Mật khẩu đã đặt trong Redis
            decode_responses=True
        )

    def set(self, key, value, expire_time: int = 60*30, pre_fix: str = None):
        if isinstance(pre_fix, str):
            key = f"{pre_fix}-{key}"
        self.redis_client.set(key, value, ex=expire_time)

    def get(self, key, pre_fix: str = None):
        if isinstance(pre_fix, str):
            key = f"{pre_fix}-{key}"
        return self.redis_client.get(key)
    
    def delete(self, key, pre_fix: str = None):
        if isinstance(pre_fix, str):
            key = f"{pre_fix}-{key}"
        self.redis_client.delete(key)