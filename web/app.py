import os
from flask import Flask, render_template
from flask_cors import CORS
from core.state import state
from web.routes.auth_routes import auth_bp
from web.routes.live_routes import live_bp
from web.routes.profile_routes import profile_bp
from web.routes.stream_routes import stream_bp
from web.routes.group_routes import group_bp

def create_app():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(base_dir, "templates")
    static_dir = os.path.join(base_dir, "static")

    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    CORS(app, resources={r"/api/*": {"origins": "*", "methods": ["POST", "GET", "DELETE", "OPTIONS"], "allow_headers": ["Content-Type"]}})

    # Đăng ký các Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(live_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(stream_bp)
    app.register_blueprint(group_bp)

    @app.route('/')
    def index():
        return render_template("index.html", is_authorized=state.is_authorized)

    return app
