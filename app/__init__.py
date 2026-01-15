from flask import Flask
import os

def create_app(test_config=None):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    
    # Configuration (mirrored from your app.py)
    app.config.from_mapping(
        SECRET_KEY="d2a0fc31b5ca9b05585d76fd607983601efe4bf8980e10c9a40f13e36a3cb2e3",
        UPLOAD_FOLDER=os.path.join(app.root_path, 'static', 'uploads', 'avatars'),
        ALLOWED_EXTENSIONS={'png', 'jpg', 'jpeg'}
    )

    if test_config is None:
        # Load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # Load the test config if passed in
        app.config.from_mapping(test_config)

    # Ensure the upload folder exists
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    except OSError:
        pass

    from .blueprints.auth import auth_bp
    from .blueprints.intern import intern_bp
    from .blueprints.supervisor import supervisor_bp
    from .blueprints.main import main_bp
    from .blueprints.avatar import avatar_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(intern_bp)
    app.register_blueprint(supervisor_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(avatar_bp)

    return app