import redis
from blueprints.confidential import REDIS_HOST, REDIS_PADDWORD, REDIS_URI

r = redis.Redis(
  host=REDIS_HOST,
  port=12013,
  password=REDIS_PADDWORD)
