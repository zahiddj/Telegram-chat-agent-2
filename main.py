from app import app
import routes
import bot

if __name__ == '__main__':
    bot.start_bot(app)
    app.run(host='0.0.0.0', port=5000, debug=False)
