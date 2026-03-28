from container import AppContainer


def register_routes(app):
    container = AppContainer()
    controller = container.build_news_controller()

    @app.get("/")
    def index():
        return controller.index()

    @app.get("/api/news")
    def api_news():
        return controller.api_news(app)
