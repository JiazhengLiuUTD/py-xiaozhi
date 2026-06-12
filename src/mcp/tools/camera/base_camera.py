"""
Base camera implementation.
"""

import threading
from abc import ABC, abstractmethod
from typing import Any

from src.logging import get_logger
from src.utils.config_manager import ConfigManager

logger = get_logger()


class BaseCamera(ABC):
    """
    基础摄像头类，定义接口.
    """

    _instances = {}  # 存储各子类的单例实例
    _lock = threading.Lock()

    def __init__(self):
        """
        初始化基础摄像头.
        """
        self.jpeg_data = {"buf": b"", "len": 0}  # 图像的JPEG字节数据  # 字节数据长度

        # 从配置中读取相机参数
        config = ConfigManager.get_instance()
        self.camera_index = config.get_config("CAMERA.camera_index", 0)
        self.frame_width = config.get_config("CAMERA.frame_width", 640)
        self.frame_height = config.get_config("CAMERA.frame_height", 480)

        # 保持摄像头长连接：首次 open 后不再 release()，复用同一 cap 实例
        # 避免每次拍照都重新初始化 DirectShow 子系统（~18s 延迟）
        self._cap = None
        self._cap_lock = threading.Lock()

        # EventBus 引用（由 McpPlugin 注入）
        self._event_bus = None

    @classmethod
    def get_instance(cls):
        """
        获取单例实例（所有子类共享此方法）.
        """
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    cls._instances[cls] = cls()
        return cls._instances[cls]

    def _do_cv2_capture(self) -> bool:
        """
        在独立线程中执行 cv2 捕获操作（内部实现）.

        摄像头以长连接方式持有：首次 open 后不再 release()，
        后续拍照直接复用同一 cap 实例，避免每次都重新初始化 DirectShow。
        """
        try:
            import cv2

            with self._cap_lock:
                # 首次或被释放后重新打开
                if self._cap is None or not self._cap.isOpened():
                    logger.info("Accessing camera (first open)...")
                    self._cap = cv2.VideoCapture(self.camera_index)
                    if not self._cap.isOpened():
                        logger.error(
                            f"Cannot open camera at index {self.camera_index}"
                        )
                        self._cap = None
                        return False
                    # 设置摄像头参数
                    self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
                    self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
                    # 首次 open 抛一帧出来（丢弃），让自动曝光/AWB 收敛
                    self._cap.read()

                # 读取图像（不 release，保留长连接）
                ret, frame = self._cap.read()

            if not ret:
                logger.error("Failed to capture image")
                # 读帧失败通常意味着连接断了，重置 cap
                with self._cap_lock:
                    if self._cap is not None:
                        self._cap.release()
                        self._cap = None
                return False

            # 获取原始图像尺寸
            height, width = frame.shape[:2]

            # 计算缩放比例，使最长边为320
            max_dim = max(height, width)
            scale = 320 / max_dim if max_dim > 320 else 1.0

            # 等比例缩放图像
            if scale < 1.0:
                new_width = int(width * scale)
                new_height = int(height * scale)
                frame = cv2.resize(
                    frame, (new_width, new_height), interpolation=cv2.INTER_AREA
                )

            # 直接将图像编码为JPEG字节流
            success, jpeg_data = cv2.imencode(".jpg", frame)

            if not success:
                logger.error("Failed to encode image to JPEG")
                return False

            # 保存字节数据
            self.set_jpeg_data(jpeg_data.tobytes())
            logger.info(
                f"Image captured successfully (size: {self.jpeg_data['len']} bytes)"
            )
            return True

        except Exception as e:
            logger.error(f"Exception during capture: {e}", exc_info=True)
            return False

    def capture_with_cv2(self) -> bool:
        """
        使用 OpenCV 捕获图像的通用实现（带超时保护）.

        cv2.VideoCapture 在摄像头被占用或故障时可能长时间挂起，
        通过 ThreadPoolExecutor 包装超时保护。

        Returns:
            成功返回 True，失败返回 False
        """
        import concurrent.futures

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(self._do_cv2_capture)
            return future.result(timeout=10.0)
        except concurrent.futures.TimeoutError:
            logger.error(
                f"Camera capture timed out after 10s (index={self.camera_index})"
            )
            return False
        finally:
            # 超时后不等待慢速线程（wait=False），避免长时间阻塞调用者
            executor.shutdown(wait=False)

    def set_explain_url(self, url: str):  # noqa: B027
        """设置视觉服务 URL（子类按需覆写）."""

    def set_explain_token(self, token: str):  # noqa: B027
        """设置视觉服务 token（子类按需覆写）."""

    @abstractmethod
    def capture(self) -> bool:
        """
        捕获图像.
        """

    @abstractmethod
    def analyze(self, question: str, image_data: bytes | None = None) -> str:
        """分析图像.

        Args:
            question: 用户问题
            image_data: 可选的外部图像数据，为 None 时使用 self.jpeg_data
        """

    def get_jpeg_data(self) -> dict[str, Any]:
        """
        获取JPEG数据.
        """
        return self.jpeg_data

    def set_jpeg_data(self, data_bytes: bytes):
        """
        设置JPEG数据.
        """
        self.jpeg_data["buf"] = data_bytes
        self.jpeg_data["len"] = len(data_bytes)

    def prewarm_async(self) -> None:
        """异步预热摄像头.

        在后台线程中执行一次 open+read，把首次初始化（~18s）的开销
        提前到应用启动阶段。注意：不 release()，让 cap 保持长连接，
        下次拍照直接复用。
        """
        def _prewarm():
            try:
                import cv2
                import time

                logger.info(f"后台预热摄像头 index={self.camera_index}...")
                start = time.time()
                with self._cap_lock:
                    if self._cap is None or not self._cap.isOpened():
                        self._cap = cv2.VideoCapture(self.camera_index)
                        if self._cap.isOpened():
                            self._cap.set(
                                cv2.CAP_PROP_FRAME_WIDTH, self.frame_width
                            )
                            self._cap.set(
                                cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height
                            )
                            self._cap.read()  # 抛首帧
                logger.info(
                    f"摄像头预热完成，耗时 {time.time() - start:.1f}s"
                )
            except Exception as e:
                logger.warning(f"摄像头预热失败: {e}")

        import threading

        threading.Thread(
            target=_prewarm, daemon=True, name="camera-prewarm"
        ).start()

    def close(self) -> None:
        """释放长连接的摄像头资源."""
        with self._cap_lock:
            if self._cap is not None:
                try:
                    self._cap.release()
                except Exception as e:
                    logger.debug(f"释放摄像头异常: {e}")
                self._cap = None

    def set_event_bus(self, event_bus) -> None:
        """设置事件总线引用.

        Args:
            event_bus: EventBus 实例
        """
        self._event_bus = event_bus
        logger.info("BaseCamera 已连接到 EventBus")

    async def _emit_photo_captured(self, photo_url: str) -> None:
        """发射拍照完成事件.

        Args:
            photo_url: 照片的本地文件 URL（file:// 格式）
        """
        if not self._event_bus:
            logger.debug("EventBus 未设置，跳过发射 PHOTO_CAPTURED 事件")
            return

        try:
            from src.core.event_bus import Events
            from src.mcp.tools.camera.events import PhotoCaptureData

            data = PhotoCaptureData(photo_url=photo_url)
            await self._event_bus.emit(Events.PHOTO_CAPTURED, data)
            logger.info(f"已发射 PHOTO_CAPTURED 事件: {photo_url}")
        except Exception as e:
            logger.error(f"发射 PHOTO_CAPTURED 事件失败: {e}")
