from enum import Enum


class MediaType(str, Enum):
    image = "image"
    video = "video"


class MediaStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    converting = "converting"
    ready = "ready"
    failed = "failed"
