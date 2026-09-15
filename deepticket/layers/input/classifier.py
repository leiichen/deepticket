"""Ingress 事件分类器：根据 source / 关键词匹配路由规则。"""

from __future__ import annotations

from deepticket.config.routing_schema import RouteConfig, RoutingConfig
from deepticket.layers.input.ingress_models import IngressEvent


def classify_ingress_event(
    event: IngressEvent,
    routing: RoutingConfig,
) -> RouteConfig:
    """按 source（及可选 question 关键词）匹配路由，未命中则走 default。"""
    question_lower = event.question.lower()
    source_lower = event.source.lower()

    for route in routing.routes:
        if route.match.default:
            continue
        match_cfg = route.match
        if match_cfg.sources and source_lower not in {
            item.lower() for item in match_cfg.sources
        }:
            continue
        if match_cfg.title_keywords and not any(
            kw.lower() in question_lower for kw in match_cfg.title_keywords
        ):
            continue
        if match_cfg.body_keywords and not any(
            kw.lower() in question_lower for kw in match_cfg.body_keywords
        ):
            continue
        return route

    default_route = routing.default_route()
    if default_route is None:
        raise ValueError("routing 配置为空，无法分类")
    return default_route
