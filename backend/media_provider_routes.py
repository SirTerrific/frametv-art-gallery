import asyncio
import logging
from collections import OrderedDict

from flask import Blueprint, Response, jsonify, request

from models import ProviderConfig

logger = logging.getLogger(__name__)

media_provider_routes = Blueprint('media_provider', __name__)

# Recently viewed images, so scrolling back does not hit the server again. Bounded: a
# full-size photo is several MB, and every gunicorn worker keeps its own copy.
_IMAGE_CACHE_SIZE = 32
_image_cache: "OrderedDict[str, bytes]" = OrderedDict()


def get_media_provider():
    """Build the Immich provider from the saved settings, or None when it is off.

    Read on every call, so saving or removing the settings takes effect at once in
    every worker, without a restart.
    """
    config = ProviderConfig.query.filter_by(provider='immich', enabled=True).first()
    if not (config and config.api_key and config.host):
        return None
    from utils.immich_provider import ImmichProvider
    return ImmichProvider(config.api_key, config.host, config.port or 443)


def _call_provider(method_name, *args, **kwargs):
    """Run one provider call. Returns (result, None) or (None, error response)."""
    provider = get_media_provider()
    if not provider:
        return None, (jsonify({"error": "No external provider configured"}), 404)
    try:
        return asyncio.run(getattr(provider, method_name)(*args, **kwargs)), None
    except Exception:
        logger.exception("Immich call %s failed", method_name)
        return None, (jsonify({"error": "Could not reach the Immich server"}), 502)


@media_provider_routes.route('/api/provider/albums', methods=['GET'])
def api_provider_albums():
    albums, error = _call_provider('get_albums')
    return error or jsonify({"albums": albums})


@media_provider_routes.route('/api/provider/albums/<album_id>/images', methods=['GET'])
def api_provider_album_images(album_id):
    images, error = _call_provider('get_album_images', album_id)
    return error or jsonify({"images": images})


@media_provider_routes.route('/api/provider/images/<image_id>/stream', methods=['GET'])
def api_provider_stream_image(image_id):
    size = request.args.get("size", "fullsize")
    cache_key = f"{image_id}:{size}"
    image_bytes = _image_cache.get(cache_key)
    if image_bytes is None:
        image_bytes, error = _call_provider('stream_image', image_id=image_id, size=size)
        if error:
            return error
        if image_bytes:
            _image_cache[cache_key] = image_bytes
            while len(_image_cache) > _IMAGE_CACHE_SIZE:
                _image_cache.popitem(last=False)
    else:
        _image_cache.move_to_end(cache_key)
    if not image_bytes:
        return jsonify({"error": "Image not found"}), 404
    return Response(image_bytes, mimetype="image/jpeg")


@media_provider_routes.route('/api/provider/images/<image_id>/metadata', methods=['GET'])
def api_provider_image_metadata(image_id):
    metadata, error = _call_provider('get_image_metadata', image_id)
    return error or jsonify({"metadata": metadata})
