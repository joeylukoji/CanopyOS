import json
import logging

import httpx
from pydantic import ValidationError

from app.schemas import Action, Alternative, Decision, Explanation, Metrics

log = logging.getLogger(__name__)
DISCLAIMER = "Exploratory estimate, not an environmental assessment. A site survey is required before any intervention."
ACTIONS = {
    Action.PLANT_TREES: (
        "Plant more trees",
        "Consider trees where soil, utilities and access permit.",
        ["Potential shade as trees mature.", "More vegetation and habitat opportunities."],
    ),
    Action.GREEN_WALL: (
        "Explore a green wall",
        "Explore facade planting after checking structure, irrigation and ownership.",
        ["Potential additional vegetation.", "Potential habitat opportunities."],
    ),
    Action.PERMEABLE_PAVEMENT: (
        "Rethink the pavement",
        "Assess permeable paving after checking drainage, soil and traffic requirements.",
        ["Potentially improved infiltration.", "Potentially less surface runoff."],
    ),
    Action.BIOSWALE: (
        "Explore a bioswale",
        "Assess a planted drainage feature only after a drainage and soil survey.",
        ["Potential runoff management.", "Potential additional vegetation."],
    ),
    Action.SOLAR_SHADE_CANOPY: (
        "Explore a shade canopy",
        "Assess a solar shade canopy after checking sunlight, structure and access.",
        ["Potential shade.", "Potential space for solar generation."],
    ),
    Action.NO_INTERVENTION: (
        "Protect what is growing",
        "Prioritize maintaining existing vegetation before adding an intervention.",
        ["Preservation of existing vegetation.", "Avoidance of unnecessary disturbance."],
    ),
    Action.HUMAN_REVIEW: (
        "Take a closer look",
        "Seek a site review before choosing an intervention.",
        ["Better context for a site-specific decision."],
    ),
}


def fallback_decision(metrics: Metrics) -> Decision:
    if metrics.vegetation_percentage >= 0.65:
        action = Action.NO_INTERVENTION
    elif metrics.vegetation_percentage < 0.35 and metrics.open_ground_percentage >= 0.12:
        action = Action.PLANT_TREES
    elif metrics.hard_surface_percentage >= 0.60:
        action = Action.PERMEABLE_PAVEMENT
    elif metrics.building_percentage >= 0.45:
        action = Action.GREEN_WALL
    else:
        action = Action.HUMAN_REVIEW
    return Decision(
        recommended_action=action,
        source="rules_fallback",
        note="Deterministic MVP rules; Jev was not used. Confidence is not available.",
    )


def decide(
    metrics: Metrics, area_type: str, key: str, model: str, client: httpx.Client
) -> Decision:
    if not key:
        return fallback_decision(metrics)
    try:
        response = client.post(
            "https://api.typesafe.ai/v1/systemone",
            timeout=3,
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": model,
                "state": {
                    **metrics.model_dump(),
                    "area_type": area_type,
                    "shade_level": "unknown",
                    "drainage": "unknown",
                    "feasibility": "requires site survey",
                },
                "questions": {
                    "intervention": {
                        "type": "choice",
                        "instructions": "Choose one exploratory urban greening intervention. Ratios are image pixels, not land area. Do not infer drainage or engineering feasibility. Choose HUMAN_REVIEW if context is insufficient.",
                        "criteria": {action: info[1] for action, info in ACTIONS.items()},
                    }
                },
            },
        )
        response.raise_for_status()
        answer = response.json()["answers"]["intervention"]
        chosen = Action(answer["choice"])
        probabilities = answer["probabilities"]
        if set(probabilities) != set(Action):
            raise ValueError("Incomplete decision distribution")
        alternatives = [Alternative(action=k, score=v) for k, v in probabilities.items()]
        if abs(sum(a.score for a in alternatives) - 1) > 0.02:
            raise ValueError("Invalid decision distribution")
        result = Decision(
            recommended_action=chosen,
            confidence=answer["confidence"],
            alternatives=sorted(
                [a for a in alternatives if a.action != chosen], key=lambda a: a.score, reverse=True
            )[:2],
            source="jev",
            note="Jev model confidence is not a guarantee of site feasibility.",
        )
        if result.confidence is None:
            raise ValueError("Missing model confidence")
        if result.confidence < 0.45:
            result.recommended_action = Action.HUMAN_REVIEW
            result.note = "Low Jev confidence: routed to human review. Confidence refers to the original model choice."
        return result
    except (httpx.HTTPError, KeyError, ValueError, TypeError, ValidationError):
        log.warning("Jev unavailable or invalid; using labelled rules fallback")
        return fallback_decision(metrics)


def explain(
    metrics: Metrics, decision: Decision, endpoint: str, key: str, model: str, client: httpx.Client
) -> Explanation:
    facts = [
        f"Vegetation represents {metrics.vegetation_percentage:.0%} of classified pixels.",
        f"Hard surfaces represent {metrics.hard_surface_percentage:.0%} of classified pixels.",
        f"Buildings represent {metrics.building_percentage:.0%} of classified pixels.",
        f"Open ground represents {metrics.open_ground_percentage:.0%} of classified pixels.",
    ]
    _, advice, benefits = ACTIONS[decision.recommended_action]
    summary = f"{facts[0]} {facts[1]} {advice}"
    fallback = Explanation(
        summary=summary,
        main_reasons=facts[:2],
        possible_benefits=benefits,
        disclaimer=DISCLAIMER,
        source="template_fallback",
    )
    if not endpoint:
        return fallback
    # Constrained evidence assembly prevents new numerical or causal claims.
    allowed_summaries = [summary, f"{facts[2]} {facts[3]} {advice}"]
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "main_reasons", "possible_benefits", "disclaimer"],
        "properties": {
            "summary": {"type": "string", "enum": allowed_summaries},
            "main_reasons": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "uniqueItems": True,
                "items": {"type": "string", "enum": facts},
            },
            "possible_benefits": {
                "type": "array",
                "maxItems": 2,
                "items": {"type": "string", "enum": benefits},
            },
            "disclaimer": {"type": "string", "const": DISCLAIMER},
        },
    }
    try:
        response = client.post(
            endpoint.rstrip("/") + "/api/chat",
            timeout=8,
            headers={"Authorization": f"Bearer {key}"} if key else {},
            json={
                "model": model,
                "stream": False,
                "format": schema,
                "options": {"temperature": 0, "num_predict": 400},
                "messages": [
                    {
                        "role": "system",
                        "content": "Assemble an English explanation using only the allowed evidence in the JSON schema. Do not change the decision or introduce any new claims.",
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "metrics": metrics.model_dump(),
                                "decision": decision.model_dump(),
                                "allowed_output": schema,
                            }
                        ),
                    },
                ],
            },
        )
        response.raise_for_status()
        output = json.loads(response.json()["message"]["content"])
        candidate = Explanation(**output, source="gemma")
        if (
            candidate.summary not in allowed_summaries
            or not candidate.main_reasons
            or any(f not in facts for f in candidate.main_reasons)
            or any(b not in benefits for b in candidate.possible_benefits)
            or candidate.disclaimer != DISCLAIMER
        ):
            raise ValueError("Ungrounded explanation")
        return candidate
    except (httpx.HTTPError, KeyError, ValueError, TypeError, ValidationError):
        log.warning("Gemma unavailable or invalid; using labelled template fallback")
        return fallback
