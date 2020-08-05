from flask import Flask, request
import telegram
from telebot.credentials import TOKEN, HEROKU_DEPLOY_DOMAIN, NGROK_DEPLOY_DOMAIN
from telebot.mastermind import *
from telebot.settings import DEBUG, PORT, SERVER_IP

bot = telegram.Bot(token=TOKEN)
app = Flask(__name__)


@app.route('/setwebhook', methods=['GET', 'POST'])
def set_webhook():
    if DEBUG:
        s = bot.setWebhook(f'{NGROK_DEPLOY_DOMAIN}/{TOKEN}')
    else:
        s = bot.setWebhook(f'{HEROKU_DEPLOY_DOMAIN}/{TOKEN}')

    if s:
        return "webhook setup ok"
    else:
        return "webhook setup failed"


set_webhook()


@app.route(f'/{TOKEN}', methods=['POST'])
def respond():
    # retrieve the message in JSON and then transform it to Telegram object
    update = telegram.Update.de_json(request.get_json(force=True), bot)

    chat_id = update.message.chat.id
    msg_id = update.message.message_id

    # Telegram understands UTF-8, so encode text for unicode compatibility
    text = update.message.text.encode('utf-8').decode()
    print("got text message :", text)

    if text == '/start':
        first_name = update.message.chat.first_name
        response = start_command(first_name)
    elif text == '/help':
        response = help_command()
    else:
        response = get_response(text)
        # temp_dict = response
        # response = temp_dict['current_temperature']
        # photo_src = temp_dict['photo_src']

    bot.sendMessage(chat_id=chat_id, text=response, )
    # photo_src = 'https://uraloved.ru/images/mesta/perm-krai/kama/kama-1.jpg'
    # bot.sendPhoto(chat_id=chat_id, photo=photo_src)
    return 'ok'


if __name__ == '__main__':
    app.run(threaded=True, host=SERVER_IP, port=PORT, debug=DEBUG)
