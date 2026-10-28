import asyncio
import contextlib
import aiohttp
import aiofiles
from typing import List, Dict, Optional
from aioimmich import Immich
from .media_provider import MediaProvider
import logging

logger = logging.getLogger(__name__)

class ImmichProvider(MediaProvider):
    def __init__(self, api_key: str, host: str, port: int = 443):
        self.api_key = api_key
        self.host = host
        self.port = port

    @contextlib.asynccontextmanager
    async def _client(self):
        """An Immich client whose HTTP session is closed even when a call fails."""
        async with aiohttp.ClientSession() as session:
            yield Immich(session, self.api_key, self.host, port=self.port)

    async def get_albums(self) -> List[Dict]:
        async with self._client() as immich:
            albums = await immich.albums.async_get_all_albums()
        return [
            {
                "id": album.album_id,
                "name": album.album_name,
                "asset_count": album.asset_count
            } for album in albums
        ]

    async def download_image_by_id(self, image_id: str, dest_path: str, size: str = "fullsize"):
        """Download an image by Immich asset ID and save to dest_path using aioimmich."""
        async with self._client() as immich:
            asset_bytes = await immich.assets.async_view_asset(image_id, size=size)
        async with aiofiles.open(dest_path, "wb") as f:
            await f.write(asset_bytes)
            logger.info("download complete")

    def download_image_by_id_sync(self, image_id: str, dest_path: str, size: str = "fullsize"):
        """Sync wrapper for download_image_by_id for use in sync code."""
        import asyncio
        asyncio.run(self.download_image_by_id(image_id, dest_path, size))

    async def get_album_images(self, album_id: str) -> List[Dict]:
        async with self._client() as immich:
            album = await immich.albums.async_get_album_info(album_id, without_assests=False)
        return [
            {
            "id": asset.asset_id,
            "filename": asset.original_file_name,
            "thumbhash": asset.thumbhash,
            "has_metadata": asset.has_metadata
            } for asset in album.assets
        ]

    async def stream_image(self, image_id: str, size: str = "fullsize") -> Optional[bytes]:
        allowed_sizes = {"original", "fullsize", "preview", "thumbnail"}
        # Validate size, fallback to 'fullsize' if invalid
        if size not in allowed_sizes:
            size = "fullsize"
        async with self._client() as immich:
            return await immich.assets.async_view_asset(image_id, size=size)

    async def get_image_metadata(self, image_id: str) -> Dict:
        async with self._client() as immich:
            asset = await immich.assets.async_get_asset(image_id)
        return asset.metadata
