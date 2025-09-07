# Import Flask Server
from flask import Flask

# Import Blueprints
from routes.home import bp as home_bp
from routes.about import bp as about_bp
from routes.user import bp as user_bp



# Create Flask app and tell it where templates/static live
app = Flask(
    __name__, 
    template_folder="templates", 
    static_folder="static",
)

# Register all the routes to webpage blueprints
app.register_blueprint(home_bp)
app.register_blueprint(about_bp)
app.register_blueprint(user_bp)



# Start the server
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
