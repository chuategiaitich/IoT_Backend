# IoT Backend Project

Hệ thống Backend cho dự án IoT sử dụng FastAPI, MQTT và WebSockets.

## 🚀 Cấu trúc hệ thống

- **API chính**: FastAPI (chạy tại cổng `10000`)
- **MQTT Broker**: Sử dụng cho việc nhận dữ liệu từ cảm biến và gửi lệnh tới thiết bị.
- **WebSocket**: Cập nhật dữ liệu thời gian thực cho Frontend.

---

## Hướng dẫn cho Device (Phần cứng)

Các thiết bị IoT (ESP32, Arduino, v.v.) sẽ giao tiếp qua giao thức **MQTT**.

*Lưu ý: `{device_id}` là UUID của thiết bị đã được đăng ký trong hệ thống.*
### Ví dụ UID tham khảo có sẵn:
- **Feed for Jack**:  499250b5-99b9-438e-84ba-e0517fa2f3f8
- **Jack'bowl**: 2450d9da-acfa-494a-b1db-3ceadad09aaa

### 1. Gửi dữ liệu cảm biến (Publish)
Thiết bị cần gửi dữ liệu định kỳ tới topic sau:
- **Topic**: `iot/devices/{device_id}/data`
Ví dụ publish topic: `iot/devices/499250b5-99b9-438e-84ba-e0517fa2f3f8/data`
- **Payload (JSON)**:
```json
{
  "temperature": 25.5,
  "humidity": 60,
  "weight": 150.2
}
```
### 2. Nhận lệnh điều khiển (Subscribe)
Thiết bị cần lắng nghe (subscribe) topic sau để nhận lệnh từ người dùng:
- **Topic**: `iot/devices/{device_id}/command`
Ví dụ subscribe topic: `iot/devices/499250b5-99b9-438e-84ba-e0517fa2f3f8/command`
- **Payload (JSON)**:
```json
{
  "action": "dispense_food",
  "weight": "50"
}
```

---

## Hướng dẫn cho Frontend

Frontend giao tiếp với hệ thống qua **REST API** (để quản lý/lấy dữ liệu lịch sử) và **WebSocket** (để nhận dữ liệu trực tiếp).

### 1. REST API
- **Endpoint**: `POST /register` - Đăng ký để nhập danh sách user cho hệ thống.
- **Endpoint**: `POST /login` - Đăng nhập để lấy Token.
- **Endpoint**: `GET /users/me` - Lấy thông tin user hiện tại (cài đặt header `Authorization: Bearer <token>`).
- **Endpoint**: `GET /devices` - Danh sách thiết bị của User.
- **Endpoint**: `POST /commands` - Gửi lệnh tới thiết bị.
- **Tài liệu đầy đủ**: Truy cập `http://nmtue.dpdns.org/docs` để xem Swagger UI.

### 2. WebSocket (Realtime Data)
Kết nối WebSocket để nhận dữ liệu từ tất cả thiết bị của user theo thời gian thực.
- **URL**: `ws://nmtue.dpdns.org/ws/sensor_data`
- **Dữ liệu giả định nhận được theo format sau**:
```json
{
  "device_id": "uuid-cua-thiet-bi",
  "data": {
    "temperature": 25.5,
    "humidity": 60,
    "weight": 150.2
  },
  "timestamp": "2026-01-14T..."
}
```

---

## 🗄 Cơ sở dữ liệu
Xem tài liệu chi tiết về cấu trúc bảng tại: `http://nmtue.dpdns.org/docs/table`
