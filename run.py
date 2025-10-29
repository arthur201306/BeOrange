# run.py

import os
# import webview
from app import create_app

config_name = os.getenv('FLASK_CONFIG') or 'default'
app = create_app(config_name)

if __name__ == '__main__':
    # webview.create_window("CRM - ByteVision", app, width=1200, height=800, resizable=True)
    # webview.start()
    app.run(debug=True)