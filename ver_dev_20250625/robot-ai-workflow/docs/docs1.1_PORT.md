Dựa vào nội dung file docker-compose.yml của thư mục robot-ai-workflow, service chính robot-ai-workflow sẽ chạy ở port được định nghĩa bởi biến môi trường:

```yaml
ports:
  - "${SERVER_PORT}:${PORT}"
```

Điều này nghĩa là:
- Port trên máy host là giá trị của biến SERVER_PORT
- Port trong container là giá trị của biến PORT

Để biết chính xác đang chạy ở port bao nhiêu, bạn cần kiểm tra file .env trong cùng thư mục để xem giá trị của SERVER_PORT (và PORT) là gì. Nếu chưa có file .env hoặc các biến này chưa được set, thì port sẽ không được ánh xạ cụ thể.

Tóm lại: Port chạy sẽ là giá trị của SERVER_PORT trong file .env. Nếu bạn muốn biết con số cụ thể, hãy mở file .env và xem giá trị của biến này.