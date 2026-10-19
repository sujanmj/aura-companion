"""Configuration checks only: no network calls, keys, private paths or memories."""
import os


def brain_readiness(env=None):
    env = os.environ if env is None else env
    provider = (env.get('AURA_BRAIN_PROVIDER') or 'local').lower()
    requirements = {
        'claude': ('ANTHROPIC_API_KEY', 'ANTHROPIC_MODEL'),
        'openai': ('OPENAI_API_KEY',),
        'ollama': (),
    }
    if provider == 'local':
        return {'provider': 'local', 'state': 'local_only', 'model': '', 'missing': []}
    if provider not in requirements:
        return {'provider': 'unsupported', 'state': 'unavailable', 'model': '', 'missing': []}
    missing = [key for key in requirements[provider] if not env.get(key, '').strip()]
    model = (env.get('ANTHROPIC_MODEL', '') if provider == 'claude' else
             env.get('OPENAI_MODEL', 'gpt-4.1-mini') if provider == 'openai' else 'llama3.1')
    return {'provider': provider, 'state': 'missing_configuration' if missing else 'configured_unverified',
            'model': model, 'missing': missing}
