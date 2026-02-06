"""Legacy receipt template data module.

Deprecated in ColorfulMe pivot. Kept as a lightweight compatibility stub so
older imports do not crash during transition.
"""

TEMPLATES = []
CATEGORIES = ['All']
CATEGORY_HUBS = {}


def get_hub_by_slug(_slug):
    return None


def get_all_hubs():
    return []


def get_template_by_slug(_slug):
    return None


def get_templates_by_category(_category):
    return []
