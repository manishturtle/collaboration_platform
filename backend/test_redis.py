import redis
import time

def test_redis_operations():
    try:
        # Connect to Redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        
        # Test connection
        print(f"PING: {r.ping()}")
        
        # Set a key
        r.set('test_key', 'Hello, Redis!')
        
        # Get the key
        value = r.get('test_key')
        print(f"GET test_key: {value}")
        
        # Test pub/sub
        pubsub = r.pubsub()
        pubsub.subscribe('test_channel')
        
        def message_handler(message):
            print(f"Received: {message['data']}")
        
        pubsub.subscribe(**{'test_channel': message_handler})
        
        # Publish a message
        r.publish('test_channel', 'Test message')
        
        # Process messages for 1 second
        start_time = time.time()
        while time.time() - start_time < 1:
            message = pubsub.get_message()
            if message:
                print(f"Message: {message}")
            time.sleep(0.1)
            
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    print("Testing Redis connection and operations...")
    if test_redis_operations():
        print("\n✅ Redis is working correctly!")
    else:
        print("\n❌ Redis test failed")