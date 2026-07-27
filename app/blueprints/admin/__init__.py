"""Admin blueprint."""

from flask import Blueprint

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

from app.blueprints.admin import analytics  # noqa: E402, F401
from app.blueprints.admin import articles  # noqa: E402, F401
from app.blueprints.admin import comments  # noqa: E402, F401
from app.blueprints.admin import media  # noqa: E402, F401
from app.blueprints.admin import newsletters  # noqa: E402, F401
from app.blueprints.admin import projects  # noqa: E402, F401
from app.blueprints.admin import routes  # noqa: E402, F401
from app.blueprints.admin import settings  # noqa: E402, F401
from app.blueprints.admin import subscribers  # noqa: E402, F401
from app.blueprints.admin import taxonomy  # noqa: E402, F401
from app.blueprints.admin import users  # noqa: E402, F401

