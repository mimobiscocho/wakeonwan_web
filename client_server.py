from flask import Flask, request, send_from_directory, jsonify
import os
app = Flask(__name__)


@app.route('/sleep')
def sleep():
    os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")  
    return "PC en veille"

# Route pour éteindre le PC
@app.route('/shutdown', methods=['GET'])
def shutdown():
    os.system("shutdown /s /f /t 0")  
    return "PC eteint"

# Route pour redémarrer le PC
@app.route('/restart', methods=['GET'])
def restart():
    os.system("shutdown /r /f /t 0")  
    return "PC redemarre"

if __name__ == '__main__':
    # Écoute sur 0.0.0.0 pour accepter les requêtes LAN
    app.run(host='0.0.0.0', port=5000, debug=False)
