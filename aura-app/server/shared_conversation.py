"""One reviewed, invited contribution: no store, history, tools, or identity claims."""
from brain.llm_provider import LLMProvider
from readiness import brain_readiness


def shared_contribution(message, consent, *, generate=None):
    if consent is not True:
        raise ValueError('Participant agreement is required')
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= 4000:
        raise ValueError('Invalid shared question')
    readiness = brain_readiness()
    provider = readiness['provider']
    response = None
    if readiness['state'] == 'configured_unverified':
        prompt = (
            'You are AURA, an AI invited to answer one reviewed shared question. '
            'You have no private memory or knowledge of participant identities. '
            'Use only the question below; do not infer who is speaking, their emotions, '
            'or relationships. Do not claim you observed the room. No tools or web '
            'lookup are available: say when a claim needs checking and never invent '
            'sources. Do not claim emergency monitoring or medical certainty. '
            'Keep the contribution concise and leave room for people to continue.\n'
            'Reviewed participant question:\n' + message.strip()
        )
        try:
            response = (generate or LLMProvider(provider_name=provider).generate)(prompt)
        except Exception:
            response = None
    if not isinstance(response, str) or not response.strip():
        return {'response': 'Thanks for inviting me. A language-model reply is unavailable right now; I have not checked online sources. You can configure and test a provider in Setup.',
                'provider': 'local', 'saved': False, 'online_verified': False}
    return {'response': response.strip()[:8000], 'provider': provider,
            'saved': False, 'online_verified': False}
