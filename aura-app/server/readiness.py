"""Configuration-only readiness and explicit, memory-free provider checks."""
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
             env.get('OPENAI_MODEL', 'gpt-4.1-mini') if provider == 'openai' else env.get('OLLAMA_MODEL', 'llama3.1'))
    return {'provider': provider, 'state': 'missing_configuration' if missing else 'configured_unverified',
            'model': model, 'missing': missing}


def test_provider_connection(env=None, generate=None):
    """Run a user-requested, memory-free provider check without retaining its output."""
    env = os.environ if env is None else env
    readiness = brain_readiness(env)
    provider = readiness['provider']
    if readiness['state'] != 'configured_unverified':
        return {'provider': provider, 'state': readiness['state'], 'verified': False}

    if generate is None:
        from brain.llm_provider import LLMProvider
        generate = LLMProvider(provider_name=provider).generate
    # This fixed text contains no user prompt, account data, or saved memory.
    response = generate('Reply with exactly: AURA connection confirmed.')
    return {
        'provider': provider,
        'state': 'live_verified' if isinstance(response, str) and response.strip() else 'test_failed',
        'verified': isinstance(response, str) and bool(response.strip()),
    }
