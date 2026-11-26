# Lab 14 — Deployment

- **Nền tảng** Render Free
- **URL public** [lab14-agent-vn6b.onrender.com](https://lab14-agent-vn6b.onrender.com/health)
- **Trạng thái** Đã deploy và kiểm tra public ngày 26/11/2026 (GMT+7).
- **Bằng chứng** [Render web service](https://dashboard.render.com/web/srv-dc3u83ei0phs738jd690) · [Blueprint sync](https://dashboard.render.com/blueprint/exs-dc3u7rmi0phs738jc9rg/sync/exe-dc3u7sei0phs738jccig)

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

| Kiểm tra qua URL public | HTTP quan sát được |
| --- | ---: |
| `GET /health` | 200 |
| `GET /ready` | 200 |
| `POST /ask` với body hợp lệ, thiếu key | 401 |
| `POST /ask` với body hợp lệ, đúng key | 200 |

[Ảnh Render Events](screenshots/dashboard.png) · [Ảnh endpoint /health](screenshots/running.png) · [Kết quả bốn phép kiểm HTTP](screenshots/test.png)
