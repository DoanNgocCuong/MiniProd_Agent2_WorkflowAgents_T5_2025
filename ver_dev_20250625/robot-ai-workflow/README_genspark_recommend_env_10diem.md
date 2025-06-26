Tôi sẽ hướng dẫn bạn cách test hệ thống Robot AI Workflow một cách chi tiết:

## 🚀 **1. Setup Environment**

### **Bước 1: Clone và chuẩn bị**
```bash
# Clone repository
git clone https://github.com/DoanNgocCuong/MiniProd_Agent2_WorkflowAgents_T5_2025.git
cd MiniProd_Agent2_WorkflowAgents_T5_2025/ver_dev_20250625/robot-ai-workflow

# Tạo file .env
touch .env
```

### **Bước 2: Cấu hình .env file**
```bash
# .env file
# Server Config
SERVER_PORT=9330
PORT=9330
HOST=0.0.0.0

# Database Config
MYSQL_HOST=robot-ai-workflow-mysql-master
MYSQL_PORT=3306
MYSQL_USERNAME=root
MYSQL_PASSWORD=123456aA@
MYSQL_ROOT_PASSWORD=123456aA@
MYSQL_DATABASE=callbot_llm

# Redis Config  
REDIS_HOST=robot-ai-workflow-redis-master
REDIS_PORT=6379
REDIS_PASSWORD=123456aA@

# RabbitMQ Config
RABBITMQ_HOST=robot-ai-workflow-rabbitmq-master
RABBITMQ_PORT=5672
RABBITMQ_USERNAME=admin
RABBITMQ_PASSWORD=123456aA@
RABBITMQ_EXCHANGE=robot_exchange
RABBITMQ_QUEUE=robot_queue

# LLM API Keys
OPENAI_API_KEY=your_openai_api_key_here
GROQ_API_KEY=your_groq_api_key_here  
GEMINI_API_KEY=your_gemini_api_key_here

# Other
TIMEZONE=Asia/Ho_Chi_Minh
PATH_FILE_CONFIG=config.yml
INTENT_FALLBACK=fallback
URL_WORKFLOW=http://robot-ai-workflow:9330/robot-ai-workflow/api/v1/bot
URL_AGENT=http://robot-ai-workflow:9330/robot-ai-workflow/api/v1/bot
URL_PROFILE=http://localhost:8080/api/v1
```

---

## 🐳 **2. Docker Setup và Build**

### **Bước 1: Tạo Docker network**
```bash
# Tạo external network
docker network create robot-ai-workflow-network-master
```

### **Bước 2: Build Docker images**
```bash
# Build main application
docker build -t robot-ai-workflow:v1.0.8 -f Dockerfile .

# Build worker
docker build -t robot-ai-workflow-worker:v1.0.8 -f Dockerfile.worker .

# Hoặc sử dụng script có sẵn
chmod +x build_docker.sh
./build_docker.sh
```

### **Bước 3: Khởi động services**
```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f robot-ai-workflow
docker-compose logs -f robot-ai-workflow-worker-1-master
```

---

## 📊 **3. Kiểm tra Services**

### **Health Check**
```bash
# Check main API
curl http://localhost:9330/robot-ai-workflow/api

# Expected response: {"status": "OK"}
```

### **Check Docker containers**
```bash
# List running containers
docker-compose ps

# Expected containers:
# - robot-ai-workflow-server-master
# - robot-ai-workflow-redis-master  
# - robot-ai-workflow-rabbitmq-master
# - robot-ai-workflow-worker-1-master (x10 replicas)
```

---

## 🧪 **4. Test APIs với Postman/cURL**

### **Test 1: Tạo Bot mới**
```bash
curl -X POST "http://localhost:9330/robot-ai-workflow/api/v1/database/insertBot" \
-H "Content-Type: application/json" \
-d '{
  "name": "Test Bot",
  "description": "Bot for testing",
  "provider_name": "openai",
  "generation_params": {
    "temperature": 0.7,
    "max_tokens": 1000
  },
  "system_prompt": "You are a helpful assistant",
  "system_extraction_variables": "",
  "system_prompt_generation": "",
  "system_extraction_profile": "",
  "start_message": "Hello! How can I help you today?",
  "data_excel": [
    {
      "intent_name": "greeting",
      "intent_description": "User greets the bot",
      "title": "Greeting Response",
      "response": ["Hi there!", "Hello!", "Welcome!"],
      "next_action": 1,
      "score": 10
    },
    {
      "intent_name": "fallback", 
      "intent_description": "Default response",
      "title": "Default Response",
      "response": ["I don'\''t understand. Can you rephrase?"],
      "next_action": 0,
      "score": 0
    }
  ]
}'
```

### **Test 2: List Bots**
```bash
curl -X GET "http://localhost:9330/robot-ai-workflow/api/v1/database/listBot"
```

### **Test 3: Khởi tạo Conversation**
```bash
# Lấy bot_id từ response trước
curl -X POST "http://localhost:9330/robot-ai-workflow/api/v1/bot/initConversation" \
-H "Content-Type: application/json" \
-d '{
  "bot_id": 1,
  "conversation_id": "test-conv-001",
  "user_id": "user-123",
  "input_slots": {
    "USER_NAME": "John",
    "LANGUAGE": "en"
  }
}'
```

### **Test 4: Test Conversation**
```bash
curl -X POST "http://localhost:9330/robot-ai-workflow/api/v1/bot/webhook" \
-H "Content-Type: application/json" \
-d '{
  "conversation_id": "test-conv-001",
  "message": "Hello!"
}'
```

---

## 🛠️ **5. Test với Python Script**

Tạo file `test_bot.py`:

```python
import requests
import json
import time

BASE_URL = "http://localhost:9330/robot-ai-workflow/api/v1"

def test_complete_flow():
    print("🚀 Testing Complete Bot Flow...")
    
    # 1. Create Bot
    bot_data = {
        "name": "Test Chatbot",
        "description": "Testing bot functionality",
        "provider_name": "openai",
        "generation_params": {
            "temperature": 0.7,
            "max_tokens": 1000,
            "model": "gpt-4o-mini"
        },
        "system_prompt": "You are a helpful assistant for testing",
        "start_message": "Hi! I'm ready to chat.",
        "data_excel": [
            {
                "intent_name": "greeting",
                "intent_description": "User says hello",
                "title": "Greeting",
                "response": ["Hello! Nice to meet you!", "Hi there!"],
                "next_action": 1,
                "score": 10
            },
            {
                "intent_name": "goodbye",
                "intent_description": "User says goodbye", 
                "title": "Goodbye",
                "response": ["Goodbye! Take care!", "See you later!"],
                "next_action": "END",
                "score": 5
            },
            {
                "intent_name": "fallback",
                "intent_description": "Default response",
                "title": "Fallback",
                "response": ["I'm not sure I understand. Could you rephrase?"],
                "next_action": 0,
                "score": 0
            }
        ]
    }
    
    response = requests.post(f"{BASE_URL}/database/insertBot", json=bot_data)
    print(f"✅ Create Bot: {response.status_code}")
    if response.status_code == 200:
        bot_id = response.json().get("bot_id")
        print(f"   Bot ID: {bot_id}")
        
        # 2. Init Conversation
        conv_id = f"test-{int(time.time())}"
        init_data = {
            "bot_id": bot_id,
            "conversation_id": conv_id,
            "user_id": "test-user-123",
            "input_slots": {"USER_NAME": "Tester"}
        }
        
        response = requests.post(f"{BASE_URL}/bot/initConversation", json=init_data)
        print(f"✅ Init Conversation: {response.status_code}")
        
        if response.status_code == 200:
            # 3. Test Messages
            test_messages = [
                "Hello!",
                "How are you?", 
                "What can you do?",
                "Goodbye!"
            ]
            
            for msg in test_messages:
                webhook_data = {
                    "conversation_id": conv_id,
                    "message": msg
                }
                response = requests.post(f"{BASE_URL}/bot/webhook", json=webhook_data)
                print(f"📨 Message '{msg}': {response.status_code}")
                if response.status_code == 200:
                    result = response.json()
                    print(f"   🤖 Bot: {result.get('text', ['No response'])}")
                    print(f"   📊 Status: {result.get('status')}")
                    print(f"   ⏱️  Time: {result.get('process_time', 0):.2f}s")
                else:
                    print(f"   ❌ Error: {response.text}")
                print("-" * 50)
                time.sleep(1)
    
    else:
        print(f"❌ Failed to create bot: {response.text}")

if __name__ == "__main__":
    test_complete_flow()
```

Chạy test:
```bash
python test_bot.py
```

---

## 🔧 **6. Troubleshooting**

### **Common Issues:**

**1. Services không start được:**
```bash
# Check logs
docker-compose logs redis
docker-compose logs rabbitmq
docker-compose logs robot-ai-workflow

# Restart services
docker-compose down
docker-compose up -d
```

**2. API Key issues:**
```bash
# Check environment variables
docker-compose exec robot-ai-workflow env | grep API_KEY

# Update .env và restart
docker-compose restart robot-ai-workflow
```

**3. Database connection:**
```bash
# If using external MySQL, uncomment in docker-compose.yml
# và cập nhật connection settings
```

**4. Network issues:**
```bash
# Recreate network
docker network rm robot-ai-workflow-network-master
docker network create robot-ai-workflow-network-master
docker-compose up -d
```

---

## 📊 **7. Monitoring**

### **Check System Health:**
```bash
# API Health
curl http://localhost:9330/robot-ai-workflow/api

# Redis Health  
docker-compose exec redis redis-cli ping

# RabbitMQ Management UI
# http://localhost:15672 (nếu expose port)
# admin/123456aA@

# Check worker status
docker-compose exec robot-ai-workflow-worker-1-master ps aux
```

### **Performance Testing:**
```bash
# Simple load test với curl
for i in {1..10}; do
  curl -X POST "http://localhost:9330/robot-ai-workflow/api/v1/bot/webhook" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"test-'$i'","message":"Hello"}' &
done
wait
```

---

## ✅ **Expected Results**

Nếu setup thành công, bạn sẽ thấy:

1. **✅ Health check** trả về `{"status": "OK"}`
2. **✅ Bot creation** trả về `bot_id`
3. **✅ Conversation init** trả về success status
4. **✅ Message processing** trả về bot responses
5. **✅ All Docker containers** running healthy

Nếu gặp lỗi, hãy check logs và đảm bảo tất cả dependencies (API keys, network, etc.) đã được cấu hình đúng!

Bạn muốn tôi hướng dẫn chi tiết phần nào khác không?