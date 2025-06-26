**Tóm tắt Gợi ý Video/Bài học về Redis và RabbitMQ trong Lộ Trình LLMOps/RAG**

---

**1. Redis: Học ở đâu, học gì?**

Redis là thành phần quan trọng trong các hệ thống AI/ML hiện đại, thường được dùng làm cache, lưu session, trạng thái hội thoại, hoặc làm storage cho feature store, agent.

- **Module 2:**  
  - Xem lại video phần **Feature Store** (ưu tiên nếu bạn cần thực hành, vì hướng dẫn setup Redis thực tế)  
  - Xem video phần **Storage** (nắm lý thuyết về các loại lưu trữ, vị trí Redis trong hệ thống dữ liệu)

- **Module 5:**  
  - Tập trung vào bài **“RAG: Storage & caching layers”**:  
    - Lý thuyết: Tại sao caching quan trọng, các chiến lược cache, best practice khi dùng cache (Redis), cách tránh stale data, đo lường hiệu suất.
    - Lab: Thực hành tích hợp Redis vào pipeline RAG để tối ưu tốc độ và giảm trùng lặp xử lý.

**=> Nếu chỉ có thời gian xem lại nhanh, hãy chọn “RAG: Storage & caching layers” (Module 5) và Feature Store (Module 2), vì đây là nơi sâu nhất về ứng dụng Redis.**

---

**2. RabbitMQ: Học ở đâu, học gì?**

RabbitMQ là message broker, thường dùng cho các bài toán background task, phân phối tác vụ, xây dựng pipeline ingestion, hoặc orchestrate workflow.

- **Module 2:**  
  - Xem lại video phần **Source Systems**, tập trung vào **Message Broker Models**:  
    - Lý thuyết về các loại message broker, mô hình hoạt động, RabbitMQ và Kafka.
    - Thực hành: Nếu có phần CDC với Kafka, hãy chú ý cách tích hợp broker vào pipeline.

- **Module 5:**  
  - Tập trung vào các phần về **ingestion pipeline**, **orchestration** hoặc **background task** (Airflow/streaming lab):
    - Dù không trực tiếp dạy RabbitMQ, các mô hình task queue, orchestration này sẽ giúp bạn hình dung vai trò và cách tích hợp RabbitMQ.
    - Đặc biệt xem kỹ bài **Orchestrate data ingestion workflow using Airflow** – thường liên hệ đến message queue, có thể lấy RabbitMQ làm ví dụ thực tế.

**=> Nếu bạn cần học nhanh, hãy ưu tiên phần Source Systems (Module 2) và các bài ingestion/orchestration (Module 5).**

---

**3. Tổng hợp Quick Lookup**

- **Muốn học/ôn lại về Redis:**  
  - **Module 2:** Feature Store, Storage  
  - **Module 5:** RAG: Storage & caching layers (ưu tiên cao nhất)

- **Muốn học/ôn lại về RabbitMQ:**  
  - **Module 2:** Source Systems (Message Broker Models)  
  - **Module 5:** Ingestion pipeline, orchestration, background task (Airflow/streaming)

---

**4. Gợi ý khi xem lại video/bài học**

- Ưu tiên các đoạn có chủ đề: "Redis", "cache", "message broker", "RabbitMQ", "background task", "ingestion", "orchestration".
- Nếu có timestamp/mục lục, hãy tra cứu từ khóa trên để tiết kiệm thời gian.
- Nếu học thực hành, hãy thử setup Redis/RabbitMQ trên local/lab để hiểu rõ luồng dữ liệu.

---

**Kết luận:**  
Redis và RabbitMQ là hai thành phần then chốt cho hệ thống AI/LLMOps hiện đại. Để hiểu và ứng dụng tốt, bạn nên xem lại bài học tại các vị trí đã gợi ý trên, ưu tiên các phần hướng dẫn thực hành, tích hợp vào pipeline thực tế.

**Chúc bạn học và vận hành Redis & RabbitMQ thành công!**