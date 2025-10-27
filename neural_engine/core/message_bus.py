import redis
import uuid
import json
import os

class MessageBus:
    def __init__(self):
        host = os.environ.get("REDIS_HOST", "127.0.0.1")
        self.redis = redis.Redis(host=host, port=6379, db=0, decode_responses=True)

    def get_new_goal_id(self):
        return str(uuid.uuid4())

    def add_message(self, goal_id, message_type, message):
        key = f"goal_{goal_id}:{message_type}"
        if isinstance(message, (list, dict)):
            message = json.dumps(message)
        self.redis.lpush(key, message)

    def get_message(self, goal_id, message_type):
        key = f"goal_{goal_id}:{message_type}"
        message = self.redis.rpop(key)
        try:
            return json.loads(message)
        except (json.JSONDecodeError, TypeError):
            return message

    def get_all_messages(self, goal_id):
        """Get all messages for a goal_id across all message types.
        
        Returns a list of message dictionaries with metadata about each step.
        """
        # Pattern to match all keys for this goal
        pattern = f"goal_{goal_id}:*"
        keys = self.redis.keys(pattern)
        
        all_messages = []
        for key in keys:
            # Extract message_type from key
            message_type = key.split(":", 1)[1] if ":" in key else ""
            
            # Get all messages from this key (it's a list)
            messages = self.redis.lrange(key, 0, -1)
            
            for msg_str in messages:
                try:
                    msg = json.loads(msg_str)
                    # Ensure message has required metadata
                    if isinstance(msg, dict):
                        if "goal_id" not in msg:
                            msg["goal_id"] = goal_id
                        if "message_type" not in msg:
                            msg["message_type"] = message_type
                        all_messages.append(msg)
                    else:
                        # Wrap non-dict messages
                        all_messages.append({
                            "goal_id": goal_id,
                            "message_type": message_type,
                            "data": msg
                        })
                except (json.JSONDecodeError, TypeError):
                    # Handle non-JSON messages
                    all_messages.append({
                        "goal_id": goal_id,
                        "message_type": message_type,
                        "data": msg_str
                    })
        
        # Sort by timestamp if available
        def get_timestamp(msg):
            if isinstance(msg, dict) and "timestamp" in msg:
                return msg["timestamp"]
            return 0
        
        all_messages.sort(key=get_timestamp)
        return all_messages
