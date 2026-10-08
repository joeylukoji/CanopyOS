import json

import httpx
import numpy as np

from app.schemas import Action
from app.services.metrics import calculate_metrics
from app.services.providers import decide, explain, fallback_decision


def metrics():
    return calculate_metrics(np.array([[6] * 7 + [13] * 2 + [4]]))


def test_fallback_is_not_disguised_as_jev_confidence():
    decision = fallback_decision(metrics())
    assert decision.source == 'rules_fallback'
    assert decision.confidence is None
    assert decision.recommended_action == Action.PLANT_TREES


def test_jev_receives_only_structured_state():
    def handler(request):
        body = json.loads(request.content)
        assert isinstance(body['state'], dict)
        assert 'image' not in body['state']
        assert body['questions']['intervention']['type'] == 'choice'
        probs = dict.fromkeys(Action, 0.0)
        probs['PLANT_TREES'] = .85
        probs['HUMAN_REVIEW'] = .15
        return httpx.Response(200, json={'answers': {'intervention': {
            'choice': 'PLANT_TREES', 'confidence': .7, 'probabilities': probs}}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = decide(metrics(), 'urban_open_space', 'test-key', 'jev-latest', client)
    assert result.source == 'jev'
    assert result.confidence == .7


def test_provider_error_falls_back():
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))) as client:
        assert decide(metrics(), 'street', 'test-key', 'jev-latest', client).source == 'rules_fallback'


def test_unapproved_llm_text_cannot_escape_the_evidence_contract():
    def handler(request):
        return httpx.Response(200, json={'message': {'content': json.dumps({
            'summary': 'Cooling by 20 degrees guaranteed.', 'main_reasons': [],
            'possible_benefits': [], 'disclaimer': 'Certified.'})}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = explain(metrics(), fallback_decision(metrics()), 'http://localhost:11434', '', 'gemma3:1b', client)
    assert result.source == 'template_fallback'
    assert '20 degrees' not in result.summary
