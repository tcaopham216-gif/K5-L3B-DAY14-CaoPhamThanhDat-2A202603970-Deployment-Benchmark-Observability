# Benchmark & Observability Report — Day 14

**Họ tên** Cao Phạm Thành Đạt — 2A202603970

**Ngày chạy** 26/11/2026 (GMT+7)

**Môi trường** Windows, Python 3.14 cho local benchmark, Docker Desktop Linux cho observability. Agent dùng mock LLM. Trong lượt chạy Docker, Nginx nhận request từ ứng dụng kiểm thử qua localhost, còn Locust đi qua Nginx trong mạng Compose. Dockerfile của agent observability đặt home của user `agent` tại `/home/agent` để Python nạp được thư viện ở `.local`.

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

Sau lượt scale 3, Prometheus đo p95 là 293.8 ms và trung bình là 232.4 ms trong cửa sổ 1 phút. Khoảng cách này phản ánh các request ở đuôi phân phối có độ trễ cao hơn. Nginx chia tải gần đều qua ba replica, lần lượt 20.65, 20.64 và 20.42 request/s. Tốc độ xử lý là 4759.5 token đầu vào/s và 2501.7 token đầu ra/s. Prompt gồm system message, câu hỏi và tài liệu truy xuất nên thường dài hơn câu trả lời. Nginx trả HTTP 404 cho `/metrics`. Prometheus scrape trực tiếp từng agent trong mạng Compose.

- [grafana-dashboard.png](screenshots/grafana-dashboard.png)
- [jaeger-slow-trace.png](screenshots/jaeger-slow-trace.png)
- [jaeger-error-trace.png](screenshots/jaeger-error-trace.png)
- [prometheus-alert-firing.png](screenshots/prometheus-alert-firing.png)

### 4.2 Fault injection

Lệnh `promtool test rules /p/alert_rules_test.yml` báo `SUCCESS`.

| # | Cấu hình | Alert | Thời gian đến firing |
| --- | --- | --- | --- |
| A | `MOCK_ERROR_RATE=0.2` (cùng B) | `AgentHighErrorRate` | 99.8 s |
| B | `MOCK_SLOW_RATE=0.3` (cùng A) | `AgentHighLatencyP95` | 163.2 s |

Panel phản ánh A là Error Rate và panel phản ánh B là Latency p95. Thời gian được tính từ lúc bắt đầu cập nhật Compose đến lần đọc đầu tiên thấy `firing`. Cảnh báo chi phí trong ảnh đã kích hoạt khi chạy tải và không thuộc hai phép đo A, B. Với kịch bản E (hạ phiên bản), có thể phát hiện suy giảm chất lượng bằng eval trên canary và theo dõi tỷ lệ câu đạt trên bộ câu hỏi kiểm soát. Health, latency và error rate có thể vẫn trong ngưỡng khi câu trả lời sai.

### 4.3 Traces và log

**Trace chậm** `fd8680633246716e7fadfcea9cde01b5`, tổng thời gian 1711.566 ms. Span xử lý LLM `chat mock-llm-small` chiếm 1693.236 ms (98.9%).

```json
{"ts": "2026-11-26T09:08:09.157850+00:00", "level": "INFO", "service": "observable-agent", "instance": "d2e0e7969fe9", "event": "llm_call", "trace_id": "fd8680633246716e7fadfcea9cde01b5", "span_id": "b75fa1a012ee7754", "request_id": "174baf4b8651", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 66, "output_tokens": 38, "cost_usd": 3.3e-05, "llm_ms": 1693.1}
```

**Trace lỗi** `8cb06a41f7ab1229c69641b433d3de95` được thu trong lần tái hiện cùng cấu hình mô phỏng lỗi. Tổng thời gian là 574.970 ms. Span `chat mock-llm-small` chiếm 109.289 ms (19.0%) và ghi event `exception` với lỗi upstream 503.

```json
{"ts": "2026-11-26T12:47:37.906606+00:00", "level": "INFO", "service": "observable-agent", "instance": "337b4b7669e0", "event": "llm_error", "trace_id": "8cb06a41f7ab1229c69641b433d3de95", "span_id": "c53575ea920f4854", "request_id": "fce2ca6680b6", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```


## 5. Scaling

Locust headless chạy 100 user, spawn rate 10 user/s, thời lượng 2 phút mỗi cấu hình. Bảng lấy hàng `Aggregated` trong CSV. Dùng `docker compose run --no-deps` để giữ số replica đã đặt bằng `--scale`. Xác nhận các target Prometheus đều up trước và sau mỗi lượt.

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 65.49 | 190 | 320 | 1700 | 72 |
| 3 | 65.96 | 190 | 250 | 1700 | 61 |

p95 giảm 70 ms khi tăng từ 1 lên 3 replica, còn thông lượng chỉ tăng 0.47 request/s và p99 giữ ở 1700 ms. Với 100 user cố định có thời gian chờ giữa các request, tải đã nằm trong khả năng của một replica. Độ trễ nhân tạo của mock LLM vẫn chi phối p99, còn phân phối lỗi và request chậm trong từng lượt có thể ảnh hưởng đến p95. Cần lặp lại benchmark để ước lượng độ ổn định của chênh lệch p95.

## 6. Kết luận

1. Theo dõi percentile để thấy phần trăm request gặp độ trễ đột biến.
2. Dùng chất lượng và cost / câu đúng cùng với latency để đánh giá phiên bản.
3. Đối chiếu `trace_id` giữa trace và log để xác định thời gian nằm ở retrieval hay bước gọi LLM.

Với dịch vụ thật, bổ sung tỉ lệ LLM timeout theo nhà cung cấp và tỉ lệ đạt eval trên canary. Báo động dựa trên các cửa sổ thời gian đủ dài để phân biệt lỗi thoáng qua với xu hướng kéo dài.
