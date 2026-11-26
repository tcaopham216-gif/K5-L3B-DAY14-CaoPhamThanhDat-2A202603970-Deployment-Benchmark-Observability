# Benchmark & Observability Report — Day 14

**Họ tên** Cao Phạm Thành Đạt — 2A202603970
**Ngày chạy** 26/11/2026 (GMT+7)
**Môi trường** Windows, Python 3.14 cho local benchmark, Docker Desktop Linux cho observability. Agent dùng mock LLM.

## 1. SLO và quality gate

| SLI | Ngưỡng | Lý do |
| --- | --- | --- |
| p95 latency `/ask` | ≤ 500 ms | Buộc ít nhất 95% request phản hồi trong nửa giây. |
| Error rate `/ask` | ≤ 2% | Phát hiện lần chạy vượt mức lỗi chấp nhận của kịch bản mô phỏng. |
| Accuracy trên golden dataset | 100%, 0 regression sau sửa | Bộ câu hỏi nhỏ và xác định nên từng câu phải tiếp tục đạt. |

## 2. Hiệu năng agent v2

### 2.1 Concurrency

Mỗi lần gửi 300 request. Giữ `MOCK_SLOW_RATE=0.03` và `MOCK_ERROR_RATE=0.01`.

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 3.94 | 214.7 | 243.6 | 1705.1 | 0.33% | PASS |
| 10 | 36.22 | 201.6 | 240.8 | 1722.7 | 0.33% | PASS |
| 50 | 97.48 | 225.6 | 328.3 | 1723.9 | 1.33% | PASS |
| 100 | 40.52 | 1114.9 | 5249.5 | 5521.2 | 0.67% | FAIL |

RPS tăng đến concurrency 50 rồi giảm ở 100, trong khi cả p50 lẫn p95 tăng mạnh. Concurrency cao hơn có thể làm client hoặc server cục bộ tốn thêm thời gian điều phối và chờ. Một lần đo trên cùng máy chưa đủ để quy kết nút thắt cụ thể.

### 2.2 Tail latency

Mỗi lượt gửi 300 request ở concurrency 20. Giữ `MOCK_ERROR_RATE=0.01`.

| `MOCK_SLOW_RATE` | Avg (ms) | p95 (ms) | p99 (ms) |
| ---: | ---: | ---: | ---: |
| 0 | 209.9 | 238.9 | 250.4 |
| 0.03 | 250.6 | 242.0 | 1727.8 |
| 0.1 | 322.3 | 1691.3 | 1727.1 |

p99 phản ứng sớm nhất. Ngay ở tỷ lệ chậm 3%, p99 đã vào nhóm request chậm trong khi p95 chủ yếu còn ở nhóm thông thường. Ở 10%, p95 vượt một giây. Average gộp cả đuôi chậm vào nhiều request nhanh nên tăng ít hơn.

## 3. Chất lượng

Dùng cùng golden dataset 23 câu. Tắt lỗi và độ trễ đột biến ngẫu nhiên khi chạy eval để so sánh tri thức giữa các phiên bản.

| Chỉ số | v1 | v2 trước sửa | v2 sau sửa |
| --- | ---: | ---: | ---: |
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.3 | 108.8 | 113.7 |
| Tổng chi phí mô phỏng (USD) | 0.00040800 | 0.00075800 | 0.00079100 |
| Chi phí / câu đúng (USD) | 0.00040755 | 0.00003607 | 0.00003439 |
| p95 (ms) | 201.2 | 235.6 | 230.2 |
| Quality gate | FAIL | PASS | PASS |

| Câu | Keyword thiếu ở baseline v2 | Thay đổi tài liệu truy xuất |
| --- | --- | --- |
| `security-02` | token, hết hạn, chữ ký | Thêm tài liệu JWT giải thích kiểm tra chữ ký và trường `exp`. |
| `scaling-03` | CPU, memory, custom metrics | Thêm tài liệu autoscaling và Kubernetes HPA, gồm các tín hiệu có thể dùng để scale. |

V2 dùng nhiều token hơn vì thêm context truy xuất. Tổng chi phí và p95 eval cao hơn v1, trong khi chi phí trên mỗi câu đúng giảm do có thêm nhiều câu đạt. Sau cập nhật knowledge base, cả hai câu từng sai đều đạt và không có regression.

**Quality gate trong CI**. Khởi động candidate và đợi `/health` trả 200. Chạy `python eval/run_eval.py --url "$BASE" --min-accuracy 1.0 --baseline reports/eval_v2.json --out reports/eval_ci.json` từ thư mục develop. Dùng exit code của script làm kết quả job. Đặt job làm required status check để chặn merge khi accuracy thấp hoặc câu trước đó đúng bị sai.

### 3.1 Metrics cục bộ

Trong lần eval sau sửa, `http_requests_total{method="POST",route="/ask",status="200"} 23.0` là counter, `agent_in_flight_requests 0.0` là gauge và `agent_question_length_chars_count 23.0` thuộc histogram độ dài câu hỏi. Dùng route template làm label và gom URL lạ vào `unmatched` giúp giới hạn số time series. Label theo URL đầy đủ có thể tạo hàng nghìn time series, kéo theo chi phí lưu trữ và truy vấn.

## 4. Observability stack

### 4.1 Grafana và metrics

Chưa có mẫu truy vấn Prometheus trong lần thu dữ liệu. Nginx cấu hình trả 404 cho `/metrics` và Prometheus scrape trực tiếp các agent. Input token gồm system prompt, tài liệu truy xuất và câu hỏi nên thường nhiều hơn output token.


### 4.2 Fault injection

| # | Cấu hình | Alert | Thời gian đến firing |
| --- | --- | --- | --- |
| A | `MOCK_ERROR_RATE=0.2` (cùng B) | Chưa thu bằng chứng | Chưa đo |
| B | `MOCK_SLOW_RATE=0.3` (cùng A) | Chưa thu bằng chứng | Chưa đo |

Panel phản ánh A là Error Rate và panel phản ánh B là Latency p95. Timing được tính từ lúc bắt đầu cập nhật Compose đến lần poll đầu tiên thấy `firing`. C (model lớn), D (pause instance) và E (hạ phiên bản) là các kịch bản bổ sung. Để phát hiện kiểu giảm chất lượng E, có thể chạy eval trên canary và theo dõi tỷ lệ câu đạt trên một tập câu hỏi kiểm soát. Health, latency và error rate có thể vẫn trong ngưỡng khi câu trả lời sai.

### 4.3 Traces và log

Chưa có mẫu Jaeger khớp với log JSON trong đợt thu bằng chứng.

## 5. Scaling

Locust headless chạy 100 user, spawn rate 10 user/s, thời lượng 2 phút mỗi cấu hình. Bảng lấy hàng `Aggregated` trong CSV.

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | Chưa đo | — | — | — | — |
| 3 | Chưa đo | — | — | — | — |

## 6. Kết luận

1. Theo dõi percentile để thấy phần trăm request gặp độ trễ đột biến.
2. Dùng chất lượng và cost / câu đúng cùng với latency để đánh giá phiên bản.
3. Đối chiếu `trace_id` giữa trace và log để xác định thời gian nằm ở retrieval hay bước gọi LLM.

Với dịch vụ thật, bổ sung tỉ lệ LLM timeout theo nhà cung cấp và tỉ lệ đạt eval trên canary. Báo động dựa trên các cửa sổ thời gian đủ dài để phân biệt lỗi thoáng qua với xu hướng kéo dài.
