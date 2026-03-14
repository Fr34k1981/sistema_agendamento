#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para iniciar o Sistema de Agendamento
"""
from app import app, inicializar_banco
import sys

if __name__ == '__main__':
    inicializar_banco()
    
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    
    print(f"🚀 Iniciando em http://localhost:{porta}")
    app.run(debug=True, host='0.0.0.0', port=porta)