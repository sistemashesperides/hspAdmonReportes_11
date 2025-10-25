import os
import json
from flask import Flask, redirect, url_for
from app.admin.routes import admin_bp
from app.daily_summary.routes import daily_summary_bp # <-- 1. IMPORT THE BLUEPRINT
from app.admin.services import init_db
from core.scheduler_service import scheduler, schedule_all_jobs_on_startup

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'una-clave-secreta-muy-dificil-de-adivinar'
    project_root_path = os.path.dirname(os.path.abspath(__file__))
    app.config['PROJECT_ROOT'] = project_root_path

    # Custom filter for Jinja
    def from_json_filter(value):
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return [] # Return empty list if value is None or invalid JSON
    app.jinja_env.filters['fromjson'] = from_json_filter

    # Register blueprints
    app.register_blueprint(admin_bp)
    app.register_blueprint(daily_summary_bp) # <-- 2. REGISTER THE BLUEPRINT

    with app.app_context():
        init_db()
        
    return app

app = create_app()

@app.route('/')
def index():
    return redirect(url_for('admin.login'))

if __name__ == '__main__':
    scheduler.init_app(app)
    scheduler.start()
    print("Programador de tareas iniciado.")
    schedule_all_jobs_on_startup(app)
    app.run(debug=True, use_reloader=False)