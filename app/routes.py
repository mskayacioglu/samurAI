from container import AppContainer


def register_routes(app, container: AppContainer):
    controller = container.build_news_controller()

    @app.get("/")
    def index():
        return controller.index()

    @app.get("/api/news")
    def api_news():
        return controller.api_news()

    @app.get("/api/ingest/status")
    def api_ingest_status():
        return controller.api_ingest_status()

    @app.post("/api/ingest/run")
    def api_ingest_run():
        return controller.api_ingest_trigger()
