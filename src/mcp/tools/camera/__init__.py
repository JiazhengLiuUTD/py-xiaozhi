"""
Camera tool for MCP.
"""

import asyncio
import json
from pathlib import Path

from src.logging import get_logger
from src.mcp.decorators import Prop, PropType, mcp_tool
from src.utils.config_manager import ConfigManager
from src.utils.resource_finder import get_user_cache_dir

from .base_camera import BaseCamera
from .normal_camera import NormalCamera
from .vl_camera import VLCamera

logger = get_logger()


def get_camera_instance():
    """
    根据配置返回对应的摄像头实现.
    """
    config = ConfigManager.get_instance()

    # 检查是否配置了智普AI
    vl_key = config.get_config("CAMERA.VLapi_key")
    vl_url = config.get_config("CAMERA.Local_VL_url")

    if vl_key and vl_url:
        logger.info(f"Initializing VL Camera with URL: {vl_url}")
        return VLCamera.get_instance()

    logger.info("VL configuration not found, using normal Camera implementation")
    return NormalCamera.get_instance()


@mcp_tool(
    name="take_photo",
    description=(
        "【拍照识图】当用户提到：拍照、拍张照、照张相、看一下、看看、帮我看、这是什么、识别、"
        "识图、看图、图片、照片、帮我瞧瞧 时调用本工具。\n"
        "功能：拍照并分析图片内容，回答用户关于图片的问题。\n"
        "使用场景：\n"
        "1. 用户要求拍照看东西 (例如: '帮我看看这是什么', '拍个照', '看看前面是什么')\n"
        "2. 物体/场景识别 ('这是什么东西', '帮我认一下', '识别一下')\n"
        "3. 文字识别OCR ('读一下上面的字', '提取文字', '这上面写的什么')\n"
        "4. 图片问答 ('图里有几个人', '这个是什么颜色', '上面有什么内容')\n\n"
        "参数说明：\n"
        "- question: 字符串类型，用户想了解的关于图片的问题\n\n"
        "使用提示：当用户说'看'、'看看'、'这是什么'等模糊表达时，优先使用本工具进行拍照识别。\n"
        "English: Take a photo and explain it. Use this tool after the user asks you to see something.\n"
        "Args: `question` - The question that you want to ask about the photo.\n"
        "Return: A JSON object that provides the photo information.\n"
        "Examples: '帮我看看这是什么', '拍个照', '看看前面', 'take a photo', 'what is this'."
    ),
    props=[Prop("question", PropType.STR)],
)
async def take_photo(arguments: dict) -> str:
    """
    拍照并分析的工具函数.
    """
    camera = get_camera_instance()
    logger.info(f"Using camera implementation: {camera.__class__.__name__}")

    question = arguments.get("question", "")
    logger.info(f"Taking photo with question: {question}")

    # 拍照（cv2 阻塞操作，放线程池避免卡 GUI）
    success = await asyncio.to_thread(camera.capture)
    if not success:
        logger.error("Failed to capture photo")
        return json.dumps(
            {"success": False, "message": "Failed to capture photo"}
        )

    # 拍照成功后，保存到缓存并通知界面显示照片
    await _save_and_notify_photo(camera)

    # 分析图片（requests 阻塞操作，放线程池避免卡 GUI）
    logger.info("Photo captured, starting analysis...")
    return await asyncio.to_thread(camera.analyze, question)


async def _save_and_notify_photo(camera: BaseCamera) -> None:
    """将拍摄的照片保存到缓存并通知界面显示.

    每次拍照使用唯一文件名，避免 QML Image 因 URL 相同而缓存旧照片。

    Args:
        camera: 摄像头实例
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

        # 清理旧照片（保留最近 10 张，避免缓存目录无限增长）
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
