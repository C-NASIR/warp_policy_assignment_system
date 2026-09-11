from app.database import Base
from app.main import app


def test_learning_analytics_are_not_exposed_or_modeled():
    paths = {route.path for route in app.routes if hasattr(route, "path")}

    assert "/learning-events" not in paths
    assert "/learning-insights" not in paths
    assert "learning_events" not in Base.metadata.tables
