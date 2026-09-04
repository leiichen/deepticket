import pytest

from deepticket.config.routing_schema import RoutingConfig
from deepticket.layers.input.classifier import classify_ingress_event
from deepticket.layers.input.ingress_models import IngressEvent


@pytest.fixture
def routing() -> RoutingConfig:
    return RoutingConfig.model_validate(
        {
            "routes": [
                {
                    "type": "incident",
                    "match": {
                        "sources": ["monitor"],
                        "title_keywords": ["500"],
                    },
                    "outbound": {"method": "webhook"},
                },
                {
                    "type": "default",
                    "match": {"default": True},
                    "outbound": {"method": "store_only"},
                },
            ]
        }
    )


def test_classify_by_source_and_keyword(routing: RoutingConfig):
    event = IngressEvent(
        source="monitor",
        project_id="default",
        external_id="a1",
        question="API 500 spike, error rate high",
    )
    route = classify_ingress_event(event, routing)
    assert route.type == "incident"


def test_classify_source_without_keyword_falls_back_to_default(routing: RoutingConfig):
    event = IngressEvent(
        source="monitor",
        project_id="default",
        external_id="a2",
        question="latency increased",
    )
    route = classify_ingress_event(event, routing)
    assert route.type == "default"


def test_classify_fallback_default(routing: RoutingConfig):
    event = IngressEvent(
        source="email",
        project_id="default",
        external_id="a4",
        question="weekly report stats attached",
    )
    route = classify_ingress_event(event, routing)
    assert route.type == "default"
