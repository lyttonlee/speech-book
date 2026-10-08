"""统一存储层：本地文件（POC 默认） / MinIO 对象存储（生产）。

对外只暴露四个函数，上层（合成、导出、文件路由）无需关心数据落在磁盘还是对象存储：

    save_bytes(rel, data) -> str   写对象，返回相对路径
    public_url(rel) -> str         取播放/下载用 URL
    read_bytes(rel) -> bytes       读对象
    serve(rel)                     给 HTTP 路由用（FileResponse 或 302 直链）

选哪个后端由 ``SB_STORAGE_BACKEND`` 决定：
    local → ``SB_STORAGE_DIR`` 目录，经 ``/files/{path}`` 由后端反代；
    minio → MinIO 桶，音频直连下载，省一层代理。

即使后端选了 minio，客户端导入失败也会降级到 local 并打日志，保证服务还能起。
"""
from __future__ import annotations

import io
import logging
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from fastapi.responses import FileResponse, RedirectResponse

from app.core.config import settings
from app.core.errors import NotFound

logger = logging.getLogger(__name__)

# 预签名直链有效期：足够一次音频加载，又不至于长期泄露私有文件。
# minio-py 的 expires 参数只吃 timedelta，
# 直接用 int 会在 presign 时抛 "'int' object has no attribute 'total_seconds'"。
_PREURL_TTL = timedelta(seconds=6 * 3600)


# ---------------------------------------------------------------- 本地磁盘实现
class LocalStorage:
    """POC 存储：进程本地目录，走 FastAPI StaticFiles 反代出。"""

    def __init__(self, root: str = settings.storage_dir) -> None:
        self.root = Path(root)

    def _safe(self, rel: str) -> Path:
        """把相对路径解析成绝对路径，并挡住 ../ 越权访问。"""
        target = (self.root / rel).resolve()
        if not str(target).startswith(str(self.root.resolve())):
            raise ValueError("invalid storage path")
        return target

    def save_bytes(self, rel: str, data: bytes) -> str:
        target = self._safe(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return rel

    def public_url(self, rel: str) -> str:
        return f"/files/{quote(rel)}"

    def read_bytes(self, rel: str) -> bytes:
        return self._safe(rel).read_bytes()

    def serve(self, rel: str):
        target = self._safe(rel)
        if not target.exists():
            raise NotFound("文件不存在")
        # media_type 交给 FileResponse 猜，mp3/wav/mp4 都能对上
        return FileResponse(target)

    async def ensure_bucket(self) -> None:
        """本地目录无需初始化，保留同名方法让上层调用统一。"""
        return None


# --------------------------------------------------------------- MinIO 实现
class MinioStorage:
    """生产存储：S3 兼容对象存储（MinIO / AWS S3 / 云厂商对象存储通用）。"""

    def __init__(self) -> None:
        from minio import Minio  # 延迟导入：本地模式不付导入开销

        secure = settings.minio_secure
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=secure,
        )
        self.bucket = settings.minio_bucket
        logger.info("storage: minio endpoint=%s bucket=%s secure=%s",
                    settings.minio_endpoint, self.bucket, secure)

    def _rel(self, rel: str) -> str:
        """对象 key 统一去掉前导斜杠，MinIO 里 key 不能有 /xxx。"""
        return rel.lstrip("/")

    def save_bytes(self, rel: str, data: bytes) -> str:
        key = self._rel(rel)
        self.client.put_object(
            self.bucket,
            key,
            data=io.BytesIO(data),
            length=len(data),
            content_type="application/octet-stream",
        )
        return key

    def public_url(self, rel: str) -> str:
        """优先返回配置的直链前缀；没配就退回后端 /files/ 反代。"""
        base = settings.minio_public_base_url.rstrip("/")
        if base:
            return f"{base}/{self._rel(rel)}"
        return f"/files/{quote(self._rel(rel))}"

    def read_bytes(self, rel: str) -> bytes:
        resp = self.client.get_object(self.bucket, self._rel(rel))
        with resp:
            return resp.read()

    def serve(self, rel: str):
        """下载走临时签名直链：302 给浏览器，音频可拖进度条。"""
        try:
            url = self.client.presigned_get_object(
                self.bucket, self._rel(rel), expires=_PREURL_TTL
            )
        except Exception as exc:  # 对象不存在 / 无权限，收敛成 404
            logger.warning("minio presign failed: %s", exc)
            raise NotFound("文件不存在") from exc
        return RedirectResponse(url=url, status_code=302)

    async def ensure_bucket(self) -> None:
        """首次启动建桶，避免 PUT 时 404 NoSuchBucket。"""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info("storage: bucket created -> %s", self.bucket)
        except Exception as exc:
            # 建桶失败不阻断启动：交给调用方（lifespan）决定要不要继续
            logger.error("storage: ensure_bucket failed: %s", exc)


def _build() -> LocalStorage | MinioStorage:
    """按配置挑存储后端；minio 客户端不可用则降级本地。"""
    if settings.storage_backend == "minio":
        try:
            return MinioStorage()
        except Exception as exc:
            logger.warning(
                "storage_backend=minio 但初始化失败(%s)，降级为 local", exc
            )
    return LocalStorage()


storage = _build()

# 下面四个是模块级门面，保持与旧代码一致的调用方式
# （synth_service / export_service / routers/files.py 都在用）


def save_bytes(rel: str, data: bytes) -> str:
    return storage.save_bytes(rel, data)


def public_url(rel: str) -> str:
    return storage.public_url(rel)


def read_bytes(rel: str) -> bytes:
    return storage.read_bytes(rel)


def serve(rel: str):
    return storage.serve(rel)
