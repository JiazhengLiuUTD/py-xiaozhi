"""
QR Code tool for MCP.
"""

import asyncio
import json
from pathlib import Path

from src.logging import get_logger
from src.mcp.decorators import Prop, PropType, mcp_tool
from src.utils.resource_finder import get_user_cache_dir

from .qr_camera import QRCamera

logger = get_logger()


def get_qr_camera_instance():
    """获取二维码摄像头实例."""
    return QRCamera.get_instance()


@mcp_tool(
    name="scan_qrcode",
    description=(
        "【二维码识别】当用户提到：二维码、扫二维码、扫码、扫一扫、识别二维码、读取二维码、"
        "QR码、qrcode、QR code、scan QR code、read QR code 时调用本工具。\n"
        "功能：调用摄像头拍照，识别图片中的二维码，返回二维码内容。\n"
        "使用场景：\n"
        "1. 用户要求扫描二维码 (例如: '扫一下这个二维码', '识别二维码', '扫码')\n"
        "2. 读取二维码内容 ('这个二维码是什么', '二维码里有什么')\n\n"
        "参数说明：\n"
        "- question: 字符串类型，用户关于二维码的问题（可选）\n\n"
        "返回：JSON 对象。\n"
        "成功示例: {\"success\": true, \"codes\": [\"https://example.com\"]}\n"
        "失败示例: {\"success\": false, \"message\": \"未检测到二维码\"}\n"
        "English: Scan a QR code from camera and return its content. "
        "Use this tool when the user asks to scan/read a QR code."
    ),
    props=[Prop("question", PropType.STR)],
)
async def scan_qrcode(arguments: dict) -> str:
    """扫描二维码并返回结果的工具函数."""
    camera = get_qr_camera_instance()
    logger.info(f"Using QR camera implementation: {camera.__class__.__name__}")

    question = arguments.get("question", "")
    logger.info(f"Scanning QR code with question: {question}")

    # 拍照（cv2 阻塞操作，放线程池避免卡 GUI）
    success = await asyncio.to_thread(camera.capture)
    if not success:
        logger.error("Failed to capture photo for QR code scanning")
        return json.dumps(
            {"success": False, "message": "Failed to capture photo"}
        )

    # 拍照成功后，保存到缓存并通知界面显示照片
    await _save_and_notify_photo(camera)

    # 识别二维码（cv2 阻塞操作，放线程池避免卡 GUI）
    logger.info("Photo captured, starting QR code detection...")
    return await asyncio.to_thread(camera.analyze, question)


async def _save_and_notify_photo(camera: "QRCamera") -> None:
    """将拍摄的照片保存到缓存并通知界面显示.

    复用 take_photo 的照片显示机制。

    Args:
        camera: 二维码摄像头实例
    """
    jpeg_buf = camera.jpeg_data.get("buf", b"")
    if not jpeg_buf:
        logger.warning("拍照成功但无图像数据，跳过界面通知")
        return

    try:
        import time

        # 保存 JPEG 到缓存目录，使用唯一文件名
        cache_dir = get_user_cache_dir() / "photos"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # 清理旧照片（保留最近 10 张）
        _cleanup_old_photos(cache_dir, keep_count=10)

        photo_path = cache_dir / f"photo_{int(time.time() * 1000)}.jpg"
        photo_path.write_bytes(jpeg_buf)
        logger.info(f"照片已保存到: {photo_path}")

        # 生成 file:// URL
        try:
            from PySide6.QtCore import QUrl

            photo_url = QUrl.fromLocalFile(str(photo_path)).toString()
        except ImportError:
            # 无 GUI 环境，使用简单 file:// URL
            photo_url = f"file:///{photo_path}".replace("\\", "/")

        # 发射 PHOTO_CAPTURED 事件
        await camera._emit_photo_captured(photo_url)

    except Exception as e:
        logger.error(f"保存/通知照片失败: {e}", exc_info=True)


def _cleanup_old_photos(cache_dir: Path, keep_count: int = 10) -> None:
    """清理旧照片文件，只保留最近的几张.

    Args:
        cache_dir: 照片缓存目录
        keep_count: 保留的最新照片数量
    """
    try:
        photo_files = sorted(
            [f for f in cache_dir.iterdir() if f.suffix.lower() == ".jpg"],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        for old_file in photo_files[keep_count:]:
            try:
                old_file.unlink()
                logger.debug(f"清理旧照片: {old_file}")
            except Exception as e:
                logger.debug(f"清理旧照片失败 {old_file}: {e}")
    except Exception as e:
        logger.debug(f"扫描旧照片失败: {e}")
