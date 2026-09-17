"""Adapter factory: selection keyed off ADAPTER_MODE, not scattered code branches."""
from app.adapters.base import VerificationAdapter
from app.adapters.debarment import DebarmentAdapter
from app.adapters.epfo_esic import EpfoEsicAdapter
from app.adapters.gstn import GstnAdapter
from app.adapters.mca21 import Mca21Adapter
from app.adapters.mii_local_content import MiiLocalContentAdapter
from app.adapters.nsic import NsicAdapter
from app.adapters.pan import PanAdapter
from app.adapters.startup_india import StartupIndiaAdapter
from app.adapters.udyam import UdyamAdapter

_ADAPTER_CLASSES: dict[str, type[VerificationAdapter]] = {
    "udyam": UdyamAdapter,
    "gstn": GstnAdapter,
    "pan": PanAdapter,
    "mca21": Mca21Adapter,
    "epfo_esic": EpfoEsicAdapter,
    "startup_india": StartupIndiaAdapter,
    "nsic": NsicAdapter,
    "debarment": DebarmentAdapter,
    "mii_local_content": MiiLocalContentAdapter,
}


def get_adapter(source_name: str) -> VerificationAdapter:
    try:
        adapter_cls = _ADAPTER_CLASSES[source_name]
    except KeyError:
        raise ValueError(f"Unknown verification source: {source_name!r}") from None
    return adapter_cls()


def all_source_names() -> tuple[str, ...]:
    return tuple(_ADAPTER_CLASSES.keys())
