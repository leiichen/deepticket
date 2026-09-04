from __future__ import annotations

from deepticket.config.routing_schema import RouteConfig
from deepticket.layers.input.image_urls import normalize_image_urls
from deepticket.layers.input.ingress_models import IngressEvent
from deepticket.layers.input.models import TicketInput


class IngressAdapter:
    """外部事件 → 内部 TicketInput（仓库/MCP 由 project_id 在运行时注入）。"""

    @staticmethod
    def to_ticket(event: IngressEvent, route: RouteConfig) -> TicketInput:
        question = event.question.strip()
        if route.prompt_suffix.strip():
            question = f"{question}\n\n{route.prompt_suffix.strip()}"

        return TicketInput(
            ticket_id=event.external_id,
            title="",
            description=question,
            repo_ids=[],
            logs="",
            image_urls=normalize_image_urls(event.image_urls),
            metadata={
                "ingress_source": event.source,
                "ingress_project_id": event.project_id,
                "ingress_route_type": route.type,
            },
        )
