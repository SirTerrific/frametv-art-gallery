from flask import Blueprint, request

from models import ProviderConfig, db

provider_config_routes = Blueprint('provider_config', __name__)


# The API key is write-only: the app has no login, so handing it back would give it to
# anyone who can reach the API. Responses only say whether one is stored.
@provider_config_routes.route('/api/providers', methods=['GET'])
def api_list_providers():
    configs = ProviderConfig.query.all()
    return {'providers': [c.as_dict() for c in configs]}


@provider_config_routes.route('/api/providers/<provider>', methods=['GET'])
def api_get_provider(provider):
    config = ProviderConfig.query.filter_by(provider=provider).first()
    if not config:
        return {'error': 'Provider not found'}, 404
    return config.as_dict()


@provider_config_routes.route('/api/providers/<provider>', methods=['POST', 'PUT'])
def api_set_provider(provider):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return {'error': 'A JSON body is required'}, 400
    config = ProviderConfig.query.filter_by(provider=provider).first()
    if not config:
        config = ProviderConfig(provider=provider)
        db.session.add(config)
    # Only the fields that were sent change, so a partial save cannot erase the key.
    if 'host' in data:
        config.host = data['host']
    if 'port' in data:
        config.port = data['port']
    if data.get('api_key'):
        config.api_key = data['api_key']
    if 'enabled' in data:
        config.enabled = bool(data['enabled'])
    db.session.commit()
    return config.as_dict()


@provider_config_routes.route('/api/providers/<provider>', methods=['DELETE'])
def api_delete_provider(provider):
    config = ProviderConfig.query.filter_by(provider=provider).first()
    if not config:
        return {'error': 'Provider not found'}, 404
    db.session.delete(config)
    db.session.commit()
    return {'success': True}
