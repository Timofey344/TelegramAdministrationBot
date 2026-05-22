from flask import Flask, render_template, jsonify
import asyncio
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Подключение к Supabase
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

@app.route('/')
def dashboard():
    """Главная страница дашборда"""
    return render_template('index.html')

@app.route('/api/stats')
def get_stats():
    """Статистика системы"""
    # Пользователи
    users = supabase.table("profiles").select("*", count="exact").execute()
    # Транзакции
    transactions = supabase.table("transactions").select("*", count="exact").execute()
    # Игры
    games = supabase.table("transactions").select("*").eq("type", "game_win").execute()
    
    return jsonify({
        "users": users.count or 0,
        "transactions": transactions.count or 0,
        "total_games": len(games.data) if games.data else 0,
        "system_status": "✅ Работает"
    })

@app.route('/api/users')
def get_users():
    """Список пользователей"""
    response = supabase.table("profiles").select("*").order("created_at", desc=True).limit(10).execute()
    return jsonify(response.data or [])

@app.route('/api/games')
def get_games():
    """История игр"""
    response = supabase.table("transactions").select("*").eq("type", "game_win").order("created_at", desc=True).limit(10).execute()
    return jsonify(response.data or [])

if __name__ == '__main__':
    print(" Дашборд доступен: http://localhost:5000")
    app.run(debug=True, port=5000)