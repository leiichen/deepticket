"""Investigation 包：Run 实体、状态机、持久化。

对外主要导出 ``InvestigationRunStore`` 与 ``RunStatus``；治理/事件在子模块。
``__all__`` 控制 ``from deepticket.investigation import *`` 的公开符号（类似 Java package-info）。
"""
from deepticket.investigation.models import InvestigationRun, RunSource, RunStatus
from deepticket.investigation.store import InvestigationRunStore
from deepticket.investigation.transitions import RunTransitionError, validate_transition

__all__ = [
    "InvestigationRun",
    "InvestigationRunStore",
    "RunSource",
    "RunStatus",
    "RunTransitionError",
    "validate_transition",
]
