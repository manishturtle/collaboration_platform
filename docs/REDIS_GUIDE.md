# Redis Guide for Collaboration Platform

## Table of Contents
- [Redis Setup](#redis-setup)
- [Configuration](#configuration)
- [Usage in Django](#usage-in-django)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Common Operations](#common-operations)
- [Performance Tuning](#performance-tuning)
- [Backup and Recovery](#backup-and-recovery)

## Redis Setup

### Installation on Windows
1. Download Redis for Windows from: https://github.com/microsoftarchive/redis/releases
2. Run the installer (Redis-x64-3.0.504.msi or newer)
3. Check "Add the Redis installation folder to the PATH" during installation
4. Complete the installation

### Verify Installation
```bash
redis-cli ping
# Should return: PONG
```

### Running Redis Server
```bash
# Start Redis server
redis-server

# Run as a service (Windows)
sc start redis
```

## Configuration

### Redis Configuration File
Location: `C:\\Program Files\\Redis\\redis.windows-service.conf`

Key configurations to check:
```ini
bind 127.0.0.1
port 6379
timeout 0
tcp-keepalive 60
loglevel notice
logfile ""
databases 16
maxmemory 256mb
maxmemory-policy allkeys-lru
```

### Django Settings
In `settings.py`:

```python
# Channel layers configuration
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}
```

## Usage in Django

### Importing Redis Client
```python
from apps.common.redis import redis_client
```

### Basic Operations
```python
# Set a value
redis_client.set('key', 'value', ex=3600)  # expires in 1 hour

# Get a value
value = redis_client.get('key')

# Delete a key
redis_client.delete('key')


# Set expiry
redis_client.expire('key', 3600)  # 1 hour

# Increment a counter
redis_client.incr('counter')
```

## Monitoring

### 1. Command Line Interface (CLI)

#### Basic Redis CLI
```bash
# Connect to Redis
redis-cli

# Test connection
PING  # Should return "PONG"

# Get detailed server information
INFO

# Monitor all commands in real-time
MONITOR

# Get memory usage
INFO memory

# List all keys (use with caution in production)
SCAN 0 COUNT 100  # First 100 keys
KEYS *           # All keys (use with caution)

# Check connected clients
CLIENT LIST

# Get server statistics
INFO stats

# Check replication status
INFO replication

# Monitor memory usage in real-time
redis-cli --stat
```

### 2. Web-Based Interfaces

#### Option 1: Redis Commander
A lightweight web-based management tool.

```bash
# Install globally
npm install -g redis-commander

# Start Redis Commander
redis-commander

# Access at: http://localhost:8081
```

#### Option 2: RedisInsight (Official GUI)
A powerful GUI from Redis Labs with advanced features.

1. Download from: https://redis.com/redis-enterprise/redis-insight/
2. Install and launch
3. Connect to `localhost:6379`

### 3. Python Testing Script

Create a file `test_redis.py` with the following content:

```python
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
```

Run the script:
```bash
python test_redis.py
```

### 4. Real-time Monitoring Commands

```bash
# Monitor all Redis commands in real-time
redis-cli monitor

# Monitor memory usage
redis-cli --stat

# Monitor clients in real-time
watch -n 1 'redis-cli client list | wc -l'

# Monitor memory usage over time
watch -n 1 'redis-cli info memory | grep used_memory_human'
```

### 5. Checking Redis Server Status

#### On Windows:
```bash
# Check if Redis service is running
sc query redis

# Start Redis service
net start redis

# Stop Redis service
net stop redis
```

#### On Linux/Mac:
```bash
# Check Redis server status
sudo systemctl status redis

# Or using Redis CLI
redis-cli info server
```

### 6. Performance Monitoring

```bash
# Get latency statistics
redis-cli --latency

# Get latency samples
redis-cli --latency-history

# Get memory usage breakdown
redis-cli info memory

# Get key statistics
redis-cli info keyspace

# Get client connections info
redis-cli info clients

# Get persistence information
redis-cli info persistence
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Check if Redis server is running: `redis-cli ping`
   - Check if port 6379 is not blocked by firewall

2. **Max Clients Reached**
   ```bash
   # Check current connections
   redis-cli info clients
   
   # Increase max clients in redis.conf
   maxclients 10000
   ```

### Checking Logs
```bash
# Windows Event Viewer
# Look for Redis logs in Windows Event Viewer under:
# Windows Logs > Application
```

## Common Operations

### Flush Database
```bash
# Delete all keys in the current database
redis-cli flushdb

# Delete all keys in all databases
redis-cli flushall
```

## Performance Tuning

1. **Enable AOF (Append Only File) for durability**
   ```ini
   appendonly yes
   appendfsync everysec
   ```

2. **Configure maxmemory policy**
   ```ini
   maxmemory 1gb
   maxmemory-policy allkeys-lru
   ```

## Backup and Recovery

### Manual Backup
1. Stop Redis server
2. Copy `dump.rdb` from Redis installation directory
3. Restart Redis server

### Automated Backup (Windows Task Scheduler)
1. Create a batch file `backup_redis.bat`:
   ```batch
   @echo off
   set REDIS_DIR="C:\Program Files\Redis"
   set BACKUP_DIR="C:\RedisBackups"
   
   if not exist %BACKUP_DIR% mkdir %BACKUP_DIR%
   copy "%REDIS_DIR%\dump.rdb" "%BACKUP_DIR%\dump_%date:~-4,4%%date:~-10,2%%date:~-7,2%.rdb"
   ```

## Security

1. **Set a password** in `redis.windows.conf`:
   ```ini
   requirepass your_secure_password
   ```

2. **Bind to localhost** if not using network access:
   ```ini
   bind 127.0.0.1
   ```

## Useful Resources

- [Redis Documentation](https://redis.io/documentation)
- [Redis Commands](https://redis.io/commands)
- [Django Channels Documentation](https://channels.readthedocs.io/)
- [Redis Windows GitHub](https://github.com/microsoftarchive/redis)
