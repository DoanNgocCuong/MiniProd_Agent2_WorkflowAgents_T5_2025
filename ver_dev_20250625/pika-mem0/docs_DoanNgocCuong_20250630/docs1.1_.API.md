# Pika-Mem0 API Testing Guide

## Base URL
```
http://localhost:6699
```

## 1. Health Check

### GET /health
Kiểm tra trạng thái sức khỏe của API

```bash
curl -X GET "http://localhost:6699/health" \
  -H "accept: application/json"
```

**Output Example:**
```json
{
  "status": "healthy"
}
```

## 2. Production Endpoints

### POST /extract_facts
Trích xuất thông tin từ cuộc hội thoại và lưu vào database

```bash
curl -X POST "http://localhost:6699/extract_facts" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user123",
    "conversation_id": "conv456",
    "conversation": [
      {
        "role": "user",
        "content": "Tôi tên là Nguyễn Văn A, 25 tuổi, làm việc tại công ty ABC"
      },
      {
        "role": "assistant", 
        "content": "Chào bạn Nguyễn Văn A! Rất vui được biết bạn."
      },
      {
        "role": "user",
        "content": "Tôi thích ăn pizza và xem phim hành động"
      }
    ],
    "mode": "milvus_only"
  }'
```

**Output Example:**
```json
{
  "status": "ok",
  "time_response": 2.45,
  "facts": [
    {
      "id": "fact_001",
      "source": "conversation",
      "user_id": "user123",
      "conversation_id": "conv456",
      "fact_type": "entity",
      "fact_value": "Tên người dùng là Nguyễn Văn A",
      "metadata": {},
      "operation": "ADD",
      "score": 0
    },
    {
      "id": "fact_002", 
      "source": "conversation",
      "user_id": "user123",
      "conversation_id": "conv456",
      "fact_type": "attribute",
      "fact_value": "25 tuổi",
      "metadata": {},
      "operation": "ADD",
      "score": 0
    },
    {
      "id": "fact_003",
      "source": "conversation", 
      "user_id": "user123",
      "conversation_id": "conv456",
      "fact_type": "relation",
      "fact_value": "Làm việc tại công ty ABC",
      "metadata": {},
      "operation": "ADD",
      "score": 0
    },
    {
      "id": "fact_004",
      "source": "conversation",
      "user_id": "user123", 
      "conversation_id": "conv456",
      "fact_type": "attribute",
      "fact_value": "Thích ăn pizza và xem phim hành động",
      "metadata": {},
      "operation": "ADD",
      "score": 0
    }
  ]
}
```

### POST /search_facts
Tìm kiếm thông tin dựa trên query

```bash
curl -X POST "http://localhost:6699/search_facts" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "thông tin về người dùng",
    "user_id": "user123",
    "conversation_id": "conv456",
    "limit": 5
  }'
```

**Output Example:**
```json
{
  "status": "ok",
  "time_response": 1.23,
  "facts": [
    {
      "id": "fact_001",
      "source": "conversation",
      "user_id": "user123",
      "conversation_id": "conv456",
      "fact_type": "entity",
      "fact_value": "Tên người dùng là Nguyễn Văn A",
      "score": 0.95,
      "metadata": {
        "created_at": "2025-06-20T10:30:00Z",
        "updated_at": "2025-06-20T10:30:00Z"
      }
    },
    {
      "id": "fact_002",
      "source": "conversation", 
      "user_id": "user123",
      "conversation_id": "conv456",
      "fact_type": "attribute",
      "fact_value": "25 tuổi",
      "score": 0.87,
      "metadata": {
        "created_at": "2025-06-20T10:30:00Z",
        "updated_at": "2025-06-20T10:30:00Z"
      }
    },
    {
      "id": "fact_003",
      "source": "conversation",
      "user_id": "user123", 
      "conversation_id": "conv456",
      "fact_type": "relation",
      "fact_value": "Làm việc tại công ty ABC",
      "score": 0.82,
      "metadata": {
        "created_at": "2025-06-20T10:30:00Z",
        "updated_at": "2025-06-20T10:30:00Z"
      }
    }
  ]
}
```

### POST /generate_response
Tạo phản hồi dựa trên context và memory

```bash
curl -X POST "http://localhost:6699/generate_response" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "Bạn có nhớ tôi thích ăn gì không?"
      }
    ],
    "user_id": "user123",
    "conversation_id": "conv456",
    "mode": "milvus_only"
  }'
```

**Output Example:**
```json
{
  "status": "ok",
  "time_response": 3.12,
  "response": {
    "content": "Có, tôi nhớ bạn thích ăn pizza và xem phim hành động. Đây là những sở thích mà bạn đã chia sẻ với tôi trước đó.",
    "context_used": [
      {
        "fact": "Thích ăn pizza và xem phim hành động",
        "relevance_score": 0.92
      }
    ],
    "memory_retrieved": 1
  }
}
```

## 3. Test Endpoints

### POST /test/test_extract_facts
Test trích xuất thông tin không lưu vào database

```bash
curl -X POST "http://localhost:6699/test/test_extract_facts" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "conversation": [
      {
        "role": "user",
        "content": "Tôi là một lập trình viên Python, thích uống cà phê vào buổi sáng"
      },
      {
        "role": "assistant",
        "content": "Thật tuyệt! Python là một ngôn ngữ lập trình rất mạnh mẽ."
      }
    ],
    "prompt": "Trích xuất thông tin cá nhân từ cuộc hội thoại",
    "user_id": "test_user",
    "conversation_id": "test_conversation"
  }'
```

**Output Example:**
```json
{
  "status": "ok",
  "time_response": 1.87,
  "facts": [
    "Người dùng là lập trình viên Python",
    "Thích uống cà phê vào buổi sáng",
    "Có kiến thức về ngôn ngữ lập trình Python"
  ]
}
```

### POST /test/test_check_facts
Kiểm tra thông tin với prompt tùy chỉnh

```bash
curl -X POST "http://localhost:6699/test/test_check_facts" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "raw_facts": [
      "Người dùng tên Nguyễn Văn A",
      "25 tuổi", 
      "Làm việc tại công ty ABC",
      "Thích ăn pizza"
    ],
    "prompt": "Kiểm tra và phân loại các thông tin sau đây",
    "user_id": "test_user",
    "conversation_id": "test_conv"
  }'
```

**Output Example:**
```json
{
  "status": "ok",
  "time_response": 2.34,
  "results": {
    "memory": [
      {
        "id": "1",
        "text": "Người dùng tên Nguyễn Văn A",
        "event": "ADD"
      },
      {
        "id": "2", 
        "text": "25 tuổi",
        "event": "ADD"
      },
      {
        "id": "3",
        "text": "Làm việc tại công ty ABC",
        "event": "ADD"
      },
      {
        "id": "4",
        "text": "Thích ăn pizza",
        "event": "ADD"
      }
    ]
  }
}
```

### POST /test/test_check_facts (với raw_facts dạng string)
```bash
curl -X POST "http://localhost:6699/test/test_check_facts" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "raw_facts": "Người dùng tên John, 30 tuổi, sống ở Hà Nội, thích đọc sách",
    "user_id": "test_user"
  }'
```

**Output Example:**
```json
{
  "status": "ok",
  "time_response": 1.98,
  "results": {
    "memory": [
      {
        "id": "1",
        "text": "Người dùng tên John",
        "event": "ADD"
      },
      {
        "id": "2",
        "text": "30 tuổi",
        "event": "ADD"
      },
      {
        "id": "3", 
        "text": "Sống ở Hà Nội",
        "event": "ADD"
      },
      {
        "id": "4",
        "text": "Thích đọc sách",
        "event": "ADD"
      }
    ]
  }
}
```

### GET /test/default_checking_prompt
Lấy prompt mặc định cho việc kiểm tra thông tin

```bash
curl -X GET "http://localhost:6699/test/default_checking_prompt" \
  -H "accept: application/json"
```

**Output Example:**
```json
{
  "status": "ok",
  "prompt": "You are a smart memory manager which controls the memory of a system.\n\nYou can perform four operations: (1) add into the memory, (2) update the memory, (3) delete from the memory, and (4) no change.\n\nBased on the above four operations, the memory will change.\n\nCompare newly retrieved facts with the existing memory. For each new fact, decide whether to:\n\n- ADD: Add it to the memory as a new element\n- UPDATE: Update an existing memory element\n- DELETE: Delete an existing memory element\n- NONE: Make no change (if the fact is already present or irrelevant)\n\n[...full prompt text...]"
}
```

### GET /test/get_facts
Lấy tất cả thông tin của một user

```bash
curl -X GET "http://localhost:6699/test/get_facts?user_id=user123&limit=100" \
  -H "accept: application/json"
```

**Output Example:**
```json
{
  "status": "ok",
  "facts": [
    {
      "id": "fact_001",
      "user_id": "user123",
      "fact": "Tên người dùng là Nguyễn Văn A",
      "conversation_id": "conv456"
    },
    {
      "id": "fact_002",
      "user_id": "user123", 
      "fact": "25 tuổi",
      "conversation_id": "conv456"
    },
    {
      "id": "fact_003",
      "user_id": "user123",
      "fact": "Làm việc tại công ty ABC",
      "conversation_id": "conv456"
    },
    {
      "id": "fact_004",
      "user_id": "user123",
      "fact": "Thích ăn pizza và xem phim hành động",
      "conversation_id": "conv456"
    }
  ]
}
```

## 4. Advanced Test Cases

### Test với conversation phức tạp
```bash
curl -X POST "http://localhost:6699/extract_facts" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "advanced_user",
    "conversation_id": "complex_conv",
    "conversation": [
      {
        "role": "user",
        "content": "Xin chào, tôi là Trần Thị B, hiện đang làm Data Scientist tại công ty XYZ"
      },
      {
        "role": "assistant",
        "content": "Chào bạn Trần Thị B! Data Science là một lĩnh vực rất thú vị."
      },
      {
        "role": "user", 
        "content": "Tôi có 3 năm kinh nghiệm với Python và Machine Learning. Sở thích của tôi là đi du lịch và chụp ảnh"
      },
      {
        "role": "assistant",
        "content": "Kinh nghiệm 3 năm với Python và ML rất ấn tượng! Du lịch và chụp ảnh cũng là những sở thích tuyệt vời."
      },
      {
        "role": "user",
        "content": "Tôi đang học thêm về Deep Learning và muốn chuyển sang làm AI Engineer"
      }
    ]
  }'
```

### Test search với query tiếng Việt
```bash
curl -X POST "http://localhost:6699/search_facts" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "kinh nghiệm lập trình",
    "user_id": "advanced_user",
    "conversation_id": "complex_conv",
    "limit": 10
  }'
```

### Test với custom prompt extraction
```bash
curl -X POST "http://localhost:6699/test/test_extract_facts" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "conversation": [
      {
        "role": "user",
        "content": "Tôi sinh ngày 15/03/1995 tại Hà Nội, tốt nghiệp Đại học Bách Khoa"
      }
    ],
    "prompt": "Trích xuất thông tin về ngày sinh, nơi sinh và học vấn từ cuộc hội thoại. Định dạng kết quả dưới dạng JSON với các trường: birth_date, birth_place, education",
    "user_id": "detail_user",
    "conversation_id": "detail_conv"
  }'
```

## 5. Error Testing

### Test với dữ liệu không hợp lệ
```bash
curl -X POST "http://localhost:6699/extract_facts" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "",
    "conversation_id": "",
    "conversation": []
  }'
```

### Test với user_id không tồn tại
```bash
curl -X GET "http://localhost:6699/test/get_facts?user_id=nonexistent_user&limit=10" \
  -H "accept: application/json"
```

## 6. Performance Testing

### Test với conversation dài
```bash
curl -X POST "http://localhost:6699/extract_facts" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "perf_user",
    "conversation_id": "long_conv",
    "conversation": [
      {"role": "user", "content": "Tôi tên là Performance Test User"},
      {"role": "assistant", "content": "Chào bạn!"},
      {"role": "user", "content": "Tôi làm việc trong lĩnh vực công nghệ thông tin"},
      {"role": "assistant", "content": "IT là một lĩnh vực rất phát triển"},
      {"role": "user", "content": "Tôi có kinh nghiệm 5 năm với Java và Spring Boot"},
      {"role": "assistant", "content": "Java và Spring Boot là những công nghệ rất mạnh"},
      {"role": "user", "content": "Hiện tại tôi đang học thêm về Microservices và Docker"},
      {"role": "assistant", "content": "Microservices và Docker rất quan trọng trong kiến trúc hiện đại"},
      {"role": "user", "content": "Sở thích của tôi là đọc sách kỹ thuật và chơi game"},
      {"role": "assistant", "content": "Đọc sách kỹ thuật giúp cập nhật kiến thức mới"}
    ]
  }'
```

### Test search với limit cao
```bash
curl -X GET "http://localhost:6699/test/get_facts?user_id=perf_user&limit=1000" \
  -H "accept: application/json"
```

## 7. Batch Testing Script

### Script để test tất cả endpoints
```bash
#!/bin/bash

BASE_URL="http://localhost:6699"

echo "=== Testing Health Check ==="
curl -X GET "$BASE_URL/health"

echo -e "\n\n=== Testing Extract Facts ==="
curl -X POST "$BASE_URL/extract_facts" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "batch_user",
    "conversation_id": "batch_conv",
    "conversation": [
      {"role": "user", "content": "Tôi là batch test user"}
    ]
  }'

echo -e "\n\n=== Testing Search Facts ==="
curl -X POST "$BASE_URL/search_facts" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "batch test",
    "user_id": "batch_user", 
    "conversation_id": "batch_conv",
    "limit": 5
  }'

echo -e "\n\n=== Testing Get Facts ==="
curl -X GET "$BASE_URL/test/get_facts?user_id=batch_user&limit=10"

echo -e "\n\n=== Testing Default Prompt ==="
curl -X GET "$BASE_URL/test/default_checking_prompt"

echo -e "\n\nAll tests completed!"
```

## 8. Environment Variables for Testing

### Development Environment
```bash
export API_BASE_URL="http://localhost:6699"
export TEST_USER_ID="test_user_$(date +%s)"
export TEST_CONV_ID="test_conv_$(date +%s)"
```

### Production Environment  
```bash
export API_BASE_URL="https://your-production-domain.com"
export TEST_USER_ID="prod_test_user"
export TEST_CONV_ID="prod_test_conv"
```

## 9. Error Response Examples

### Timeout Error
```json
{
  "detail": "Fact extraction is taking longer than expected. Please try again later."
}
```

### Validation Error
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "user_id"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

### Server Error
```json
{
  "detail": "Internal server error occurred during fact extraction"
}
```

### Empty Results
```json
{
  "status": "ok",
  "time_response": 0.45,
  "facts": []
}
```

## 10. Notes for Postman Import

Để import vào Postman:
1. Tạo một Collection mới tên "Pika-Mem0 API"
2. Tạo Environment với variables:
   - `base_url`: http://localhost:6699
   - `user_id`: test_user
   - `conversation_id`: test_conv
3. Copy từng CURL command và convert sang Postman request
4. Sử dụng variables trong requests: `{{base_url}}/health`

## 11. Load Testing với Apache Bench

```bash
# Test health endpoint
ab -n 1000 -c 10 http://localhost:6699/health

# Test extract facts endpoint (cần tạo file data.json)
ab -n 100 -c 5 -p data.json -T application/json http://localhost:6699/extract_facts
```





