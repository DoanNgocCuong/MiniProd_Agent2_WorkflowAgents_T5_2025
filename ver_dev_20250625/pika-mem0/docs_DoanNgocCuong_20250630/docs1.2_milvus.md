https://min.io/docs/minio/linux/index.html?ref=con

```bash
version: '3.5'

services:
  etcd:
    container_name: milvus-etcd
    image: quay.io/coreos/etcd:v3.5.5
    restart: unless-stopped
    environment:
      - ETCD_AUTO_COMPACTION_MODE=revision
      - ETCD_AUTO_COMPACTION_RETENTION=1000
      - ETCD_QUOTA_BACKEND_BYTES=4294967296
      - ETCD_SNAPSHOT_COUNT=50000
    volumes:
      - ${DOCKER_VOLUME_DIRECTORY:-.}/volumes/etcd:/etcd
    command: etcd -advertise-client-urls=http://127.0.0.1:2379 -listen-client-urls http://0.0.0.0:2379 --data-dir /etcd
    healthcheck:
      test: ["CMD", "etcdctl", "endpoint", "health"]
      interval: 30s
      timeout: 20s
      retries: 3

  minio:
    container_name: milvus-minio
    image: minio/minio:RELEASE.2023-03-20T20-16-18Z
    restart: unless-stopped
    environment:
      MINIO_ACCESS_KEY: minioadmin
      MINIO_SECRET_KEY: minioadmin
    ports:
      - "9001:9001"
      - "9000:9000"
    volumes:
      - ${DOCKER_VOLUME_DIRECTORY:-.}/volumes/minio:/minio_data
    command: minio server /minio_data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3

  standalone:
    container_name: milvus-standalone
    image: milvusdb/milvus:v2.4.15
    restart: unless-stopped
    command: ["milvus", "run", "standalone"]
    security_opt:
    - seccomp:unconfined
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
    volumes:
      - ${DOCKER_VOLUME_DIRECTORY:-.}/volumes/milvus:/var/lib/milvus
    # healthcheck:
    #   test: ["CMD", "curl", "-f", "http://localhost:9091/healthz"]
    #   interval: 30s
    #   start_period: 90s
    #   timeout: 20s
    #   retries: 3
    ports:
      - "19530:19530"
      - "9091:9091"
      # - "127.0.0.1:19530:19530"
      # - "127.0.0.1:9091:9091"
    depends_on:
      - "etcd"
      - "minio"

networks:
  default:
    name: milvus

```
MinIO xem tại: /////
http://103.253.20.30:9001/

---
Milvus lắng nghe ở port 19530 (gRPC) và 9091 (REST API/Healthcheck) trên host.
Port 19530 là port để client kết nối làm việc với Milvus.
Port 9091 là port cho REST API và kiểm tra sức khỏe dịch vụ.

---

# Giao diện để xem Milvus: 
Tóm lại:
1. Milvus không có giao diện web quản trị mặc định.
2. Bạn có thể dùng Attu – một dashboard open source cho Milvus.
3. MinIO chỉ là giao diện quản lý lưu trữ, không phải để thao tác với vector database Milvus.
4. Để thao tác với Milvus, bạn nên sử dụng SDK (Python, Java, v.v.) hoặc thử Attu để có giao diện trực quan.

Ví dụ kết nối Attu tới Milvus:
Chạy Attu:
```bash
docker run -d -p 8000:3000 zilliz/attu
```
- Mở trình duyệt tới http://localhost:8000
- Nhập địa chỉ Milvus: localhost:19530
- Bấm "Connect" để bắt đầu sử dụng giao diện quản trị Milvus.