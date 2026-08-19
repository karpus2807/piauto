from os import path

from .modules import assemble
from .products import PRODUCT_DEFINITIONS


def _detect_variant_key():
    variant_path = "/opt/pironman5/.variant"
    if path.exists(variant_path):
        with open(variant_path, "r") as f:
            variant = f.read().strip()
            if variant:
                return variant
    return "base"


def _custom_modules():
    custom_path = "/opt/pironman5/.custom_module"
    if not path.exists(custom_path):
        return []
    with open(custom_path) as f:
        modules = [
            line.strip() for line in f
            if line.strip() and not line.strip().startswith("#")
        ]
    return modules


# --- Assembly ---

_variant_key = _detect_variant_key()
_product = PRODUCT_DEFINITIONS.get(_variant_key, PRODUCT_DEFINITIONS["base"])

_module_names = list(_product["modules"])
_custom = _custom_modules()
for m in _custom:
    if m not in _module_names:
        _module_names.append(m)
_assembled = assemble(_module_names)

_config = dict(_assembled["default_config"])
_config.update(_product.get("config_overrides", {}))

if "event_map_replace" in _product:
    _event_map = dict(_product["event_map_replace"])
else:
    _event_map = dict(_assembled["event_map"])
    _event_map.update(_product.get("event_map_overrides", {}))

# --- Exports (same names as before) ---

NAME = _product["name"]
ID = _product["id"]
PRODUCT_VERSION = _product["product_version"]
PERIPHERALS = list(_assembled["peripherals"])
SYSTEM_DEFAULT_CONFIG = _config
EVENT_MAP = _event_map
DT_OVERLAYS = _product["dt_overlays"]
VARIENT = _variant_key
