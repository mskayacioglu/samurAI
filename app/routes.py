"""Route registration for the Flask news application."""

from container import AppContainer


def register_routes(app, container: AppContainer):
    """Attach page, news API, and ingest API routes to the Flask app."""
    controller = container.build_news_controller()

    @app.get("/")
    def index():
        """Render the main news page."""
        return controller.index()

    @app.get("/api/news")
    def api_news():
        """Return news summaries as JSON."""
        return controller.api_news()

    @app.get("/api/ingest/status")
    def api_ingest_status():
        """Return background ingest status as JSON."""
        return controller.api_ingest_status()

    @app.post("/api/ingest/run")
    def api_ingest_run():
        """Queue an immediate background ingest run."""
        return controller.api_ingest_trigger()
