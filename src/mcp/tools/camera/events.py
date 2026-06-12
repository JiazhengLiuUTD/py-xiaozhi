"""拍照事件数据类型定义.

用于 EventBus 事件通信的数据结构。
"""

from dataclasses import dataclass


@dataclass
class PhotoCaptureData:
    """拍照完成事件数据.

    Attributes:
        photo_url: 照片的本地文件 URL（file:// 格式），用于界面显示
    """

    photo_url: str
