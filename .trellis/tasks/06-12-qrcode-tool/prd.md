# 添加二维码识别 MCP 工具

## Goal

为小智 AI 添加一个二维码识别 MCP 工具。用户可以通过语音触发，工具会调用摄像头拍照，然后使用 OpenCV 的 WeChatQRCode 模型识别图中的二维码，并返回识别结果。

## What I already know

* 工具应参考现有 `BaseCamera` 与 `VLCamera` 类实现
* OpenCV WeChatQRCode 模型位于 `models/opencv_3rdparty/`
* 模型文件包括：`detect.prototxt`、`detect.caffemodel`、`sr.prototxt`、`sr.caffemodel`
* 现有 `take_photo` 工具已支持拍照后通过 EventBus 显示照片到 GUI
* MCP 工具通过 `@mcp_tool` 装饰器注册

## Assumptions (temporary)

* 二维码工具会复用 BaseCamera 的拍照能力
* 工具会拍照后识别，而不是接受外部图片
* 识别失败时返回友好的错误信息

## Open Questions

*（已解决）*

## Requirements (evolving)

* 新建 `src/mcp/tools/qrcode/` 独立工具包
* 使用 OpenCV WeChatQRCode 识别二维码
* 模型路径从 `models/opencv_3rdparty` 读取
* 通过 MCP 工具 `scan_qrcode` 暴露给小智 AI
* 支持中文语音触发（二维码、扫二维码、扫码、扫一扫、识别二维码、读取二维码、QR码、qr code）
* 支持英文语音触发（qrcode, QR code, scan QR code, read QR code）
* 返回结构化 JSON，支持多张二维码识别结果
* 拍照后像 `take_photo` 一样在 GUI 显示照片
* 未检测到二维码时直接返回失败 JSON，不回退到 VL

## Acceptance Criteria (evolving)

* [ ] 工具 `scan_qrcode` 能被 MCP 正确注册和调用
* [ ] 调用工具后能成功拍照并识别二维码
* [ ] 识别结果以 JSON 格式正确返回给服务端
* [ ] 无二维码时返回 `{"success": false, "message": "..."}`
* [ ] 拍照后 GUI 上显示拍摄的照片
* [ ] 语法检查通过

## Definition of Done (team quality bar)

* 代码与项目风格一致
* 语法检查通过
* 工具描述清晰，LLM 能正确触发

## Out of Scope (explicit)

* 批量识别本地图片文件
* 生成二维码
* 复杂的二维码解码格式处理（如名片、WIFI 等结构化解析）
* 未检测到二维码时回退到 VL 模型

## Technical Approach

1. 新建 `src/mcp/tools/qrcode/__init__.py`，注册 `scan_qrcode` MCP 工具
2. 新建 `src/mcp/tools/qrcode/qr_camera.py`，实现 `QRCamera` 类继承 `BaseCamera`
3. `QRCamera` 初始化时加载 `models/opencv_3rdparty/` 下的 WeChatQRCode 模型
4. `scan_qrcode()` 函数：
   - 调用 `QRCamera.capture()` 拍照（复用线程池超时保护）
   - 保存照片到缓存并发射 `PHOTO_CAPTURED` 事件显示照片
   - 调用 `QRCamera.detect_and_decode()` 识别二维码
   - 返回 JSON：`{"success": true, "codes": [...]}` 或 `{"success": false, "message": "..."}`
5. 在 `src/plugins/mcp.py` 中为 `QRCamera` 单例注入 EventBus

## Decision (ADR-lite)

**Context**: 需要新增二维码识别工具，且要求参考 BaseCamera/VLCamera 模式。
**Decision**: 
- 采用独立 `src/mcp/tools/qrcode/` 包
- 返回结构化 JSON，支持多张二维码
- 拍照后通过 `PHOTO_CAPTURED` 事件显示照片
- 无二维码时直接返回失败 JSON，不回退 VL
**后果**: 实现清晰，与现有 camera 工具解耦；无二维码时用户体验较简单，但避免 VL 超时风险。

## Technical Notes

* `BaseCamera` 位于 `src/mcp/tools/camera/base_camera.py`
* `VLCamera` 位于 `src/mcp/tools/camera/vl_camera.py`
* MCP 工具注册装饰器位于 `src/mcp/decorators.py`
* WeChatQRCode 模型位于 `models/opencv_3rdparty/`
* 现有 `take_photo` 工具位于 `src/mcp/tools/camera/__init__.py`
