import redis
import uuid
import json
import os

class MessageBus:
    def __init__(self, port=6379, db=0):
        host = os.environ.get("REDIS_HOST", "127.0.0.1")
        self.redis = redis.Redis(host=host, port=port, db=db, decode_responses=True)

    def get_new_goal_id(self):
        return str(uuid.uuid4())

    def add_message(self, goal_id, message_type, message):
        key = f"goal_{goal_id}:{message_type}"
        if isinstance(message, list):
            message = json.dumps(message)
        self.redis.lpush(key, message)

    def get_message(self, goal_id, message_type):
        key = f"goal_{goal_id}:{message_type}"
        message = self.redis.rpop(key)
        try:
            return json.loads(message)
        except (json.JSONDecodeError, TypeError):
            return message

    def set_data(self, key, data):
        if isinstance(data, (dict, list)):
            data = json.dumps(data)
        self.redis.set(key, data)

    def get_data(self, key):
        data = self.redis.get(key)
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return data
