#!/usr/bin/env python3
"""
Bigode 3.0 — Servidor HTTP para novo frontend
Serve na porta 8000 com suporte a Web Components
"""

import http.server
import socketserver
import os

PORT = 8000
DIRECTORY = "/home/user/Bigode-IA/web"

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        # CORS para permitir requests do cérebro agente
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def log_message(self, format, *args):
        # Log mais legível
        if '200' in str(args):
            print(f'✅ {args[0]}')
        elif '404' in str(args):
            print(f'❌ 404: {args[0]}')
        else:
            print(f'📡 {args[0]}')

if __name__ == '__main__':
    os.chdir(DIRECTORY)

    print("=" * 60)
    print("  🚀 BIGODE 3.0 — NOVO FRONTEND")
    print("=" * 60)
    print(f"  Servidor: http://localhost:{PORT}")
    print(f"  Diretório: {DIRECTORY}")
    print("  Liquid Glass: ✅ Ativo")
    print("  Web Components: ✅ 8 componentes")
    print("")
    print("  Ctrl+C para parar")
    print("=" * 60)
    print("")

    try:
        with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
            print(f"Servindo HTTP na porta {PORT}...\n")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\n✅ Servidor encerrado")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
