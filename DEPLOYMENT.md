# Lab 14 — Deployment

**Nền tảng chọn:** Render
**Trạng thái:** Đã chuẩn bị Blueprint và Dockerfile. Chưa provision dịch vụ cloud, nên chưa có URL public hoặc ảnh dashboard deploy.

## Blueprint

Dùng [06-lab-complete/render.yaml](06-lab-complete/render.yaml) làm Blueprint Path. Blueprint tạo một Docker web service và một Render Key Value Free, cùng vùng mặc định. Key Value nhận kết nối nội bộ. [Hướng dẫn Blueprint](https://render.com/docs/infrastructure-as-code)

| Biến | Nguồn |
| --- | --- |
| `PORT` | Render cấp khi chạy container. Dockerfile đọc biến này và mặc định 8000 ở local. |
| `ENVIRONMENT` | `production` trong Blueprint. |
| `AGENT_API_KEY` | Render sinh ngẫu nhiên qua `generateValue`. Lấy giá trị từ biến môi trường của service khi tự kiểm. |
| `REDIS_URL` | URL riêng của Render Key Value, tham chiếu bằng `fromService.connectionString`. |
| `RATE_LIMIT_PER_MINUTE` | 10 request/phút/API key. |
| `DAILY_BUDGET_USD` | 1 USD giả lập/ngày UTC. |

## Kiểm tra cloud

Đặt `BASE` là URL thật và nạp `AGENT_API_KEY` vào môi trường shell trước khi chạy.

```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
```

Kỳ vọng lần lượt 200, 200, 401, 200. Ba ảnh cần bổ sung sau khi lên cloud là `screenshots/dashboard.png`, `screenshots/running.png` và `screenshots/test.png`.
