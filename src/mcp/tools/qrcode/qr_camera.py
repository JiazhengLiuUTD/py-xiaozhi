"""二维码识别摄像头实现.

基于 OpenCV WeChatQRCode 实现二维码检测和解码。
"""

import json
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from src.logging import get_logger
from src.mcp.tools.camera.base_camera import BaseCamera
from src.utils.resource_finder import get_models_dir

logger = get_logger()


class QRCamera(BaseCamera):
    """二维码识别摄像头.

    使用 OpenCV 的 WeChatQRCode 模块识别图片中的二维码。
    """

    _instance: Optional["QRCamera"] = None

    def __init__(self):
        """初始化二维码识别摄像头.

        WeChatQRCode 检测器采用懒加载，延迟到首次调用 detect_and_decode()
        时才导入 cv2 并加载模型，避免应用启动时在主线程过早初始化
        OpenCV 导致后续 cv2.VideoCapture 性能下降。
        """
        super().__init__()
        self._qr_detector = None
        self._model_loaded = False

    @classmethod
    def get_instance(cls) -> "QRCamera":
        """获取 QRCamera 单例实例."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_qr_detector(self) -> bool:
        """初始化 WeChatQRCode 检测器.

        Returns:
            bool: 初始化是否成功
        """
        try:
            import cv2

            # 检查 cv2 是否包含 wechat_qrcode 模块
            if not hasattr(cv2, "wechat_qrcode_WeChatQRCode"):
                logger.error(
                    "当前 OpenCV 版本未包含 wechat_qrcode 模块，"
                    "请安装包含 wechat_qrcode 的 opencv-contrib-python"
                )
                return False

            model_dir = get_models_dir() / "opencv_3rdparty"
            detector_proto = model_dir / "detect.prototxt"
            detector_model = model_dir / "detect.caffemodel"
            sr_proto = model_dir / "sr.prototxt"
            sr_model = model_dir / "sr.caffemodel"

            # 检查模型文件是否存在
            missing_files = [
                str(f) for f in [detector_proto, detector_model, sr_proto, sr_model]
                if not f.exists()
            ]
            if missing_files:
                logger.error(f"WeChatQRCode 模型文件缺失: {missing_files}")
                return False

            self._qr_detector = cv2.wechat_qrcode_WeChatQRCode(
                str(detector_proto),
                str(detector_model),
                str(sr_proto),
                str(sr_model),
            )
            self._model_loaded = True
            logger.info("WeChatQRCode 检测器初始化成功")
            return True

        except Exception as e:
            logger.error(f"WeChatQRCode 检测器初始化失败: {e}", exc_info=True)
            self._model_loaded = False
            return False

    def capture(self) -> bool:
        """捕获图像.

        复用基类的 OpenCV 拍照实现。

        Returns:
            bool: 是否成功
        """
        return self.capture_with_cv2()

    def _ensure_detector(self) -> bool:
        """确保 WeChatQRCode 检测器已初始化（懒加载）.

        Returns:
            bool: 检测器是否可用
        """
        if self._model_loaded and self._qr_detector is not None:
            return True
        return self._init_qr_detector()

    def detect_and_decode(self, image_data: Optional[bytes] = None) -> Tuple[List[str], bool]:
        """检测并解码二维码.

        Args:
            image_data: 可选的外部 JPEG 数据，为 None 时使用 self.jpeg_data

        Returns:
            Tuple[List[str], bool]: (识别结果列表, 是否成功执行检测)
        """
        if not self._ensure_detector():
            logger.error("WeChatQRCode 检测器未初始化")
            return [], False

        buf = image_data if image_data is not None else self.jpeg_data.get("buf", b"")
        if not buf:
            logger.warning("无图像数据，无法识别二维码")
            return [], False

        try:
            import cv2

            # 将 JPEG 字节解码为 numpy 数组
            nparr = np.frombuffer(buf, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if image is None:
                logger.error("无法解码图像数据")
                return [], False

            # WeChatQRCode 返回 (results, points)
            results, points = self._qr_detector.detectAndDecode(image)

            # results 是 tuple，转换为 list
            codes = [r for r in results if r]
            logger.info(f"二维码识别完成，检测到 {len(codes)} 个二维码")
            return codes, True

        except Exception as e:
            logger.error(f"二维码识别失败: {e}", exc_info=True)
            return [], False

    def analyze(self, question: str, image_data: bytes | None = None) -> str:
        """分析图像中的二维码.

        Args:
            question: 用户问题（二维码工具中可忽略）
            image_data: 可选的外部图像数据

        Returns:
            str: JSON 格式的识别结果
        """
        codes, success = self.detect_and_decode(image_data)

        if not success:
            return json.dumps(
                {"success": False, "message": "二维码识别失败，检测器未初始化"}
            )

        if not codes:
            return json.dumps(
                {"success": False, "message": "未检测到二维码"}
            )

        return json.dumps(
            {"success": True, "codes": codes}, ensure_ascii=False
        )
