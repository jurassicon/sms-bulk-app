import datetime
import http
import json
import logging
import os
from logging.handlers import RotatingFileHandler

import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

LOG_FILE_PATH = '/var/www/sms_bulk_app/sms_bulk_app.log'
TOKEN_FILE_PATH = '/var/www/token.json'

file_handler = RotatingFileHandler(
    LOG_FILE_PATH,
    maxBytes=1048576,
    backupCount=10
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
)
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)

API_KEY = os.getenv('API_KEY')
MOYKLASS_API_URL = os.getenv('MOYKLASS_API_URL')
SMS_API_URL = os.getenv('SMS_API_URL')
SMS_USERNAME = os.getenv('SMS_USERNAME')
SMS_PASSWORD = os.getenv('SMS_PASSWORD')

REQUIRED_ENV = [
    'API_KEY', 'MOYKLASS_API_URL', 'SMS_API_URL',
    'SMS_USERNAME', 'SMS_PASSWORD'
]

for env in REQUIRED_ENV:
    if not os.getenv(env):
        app.logger.critical(f'Missing required environment variable: {env}')
        raise SystemExit(f'Environment variable {env} is not set')


def get_saved_token():
    try:
        with open(TOKEN_FILE_PATH, 'r') as token_file:
            data = json.load(token_file)
            if 'accessToken' in data and 'expiresAt' in data:
                expires_at = datetime.datetime.fromtimestamp(data['expiresAt'])
                if expires_at > datetime.datetime.now():
                    return data['accessToken']
            app.logger.info('Saved token expired or invalid.')
    except FileNotFoundError:
        app.logger.info('Token file not found; requesting new token.')
    except (json.JSONDecodeError, KeyError) as e:
        app.logger.error(f'Error reading token file: {str(e)}')
    return None


def save_token(token, expires_at):
    with open(TOKEN_FILE_PATH, 'w') as token_file:
        json.dump({'accessToken': token, 'expiresAt': expires_at}, token_file)
    app.logger.info('Token saved successfully.')


def get_token():
    saved_token = get_saved_token()
    if saved_token:
        return saved_token

    url = f'{MOYKLASS_API_URL}/company/auth/getToken'
    headers = {'Content-Type': 'application/json'}
    payload = {'apiKey': API_KEY}
    app.logger.info('Requesting new token')
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == http.HTTPStatus.OK:
        token_data = response.json()
        token = token_data['accessToken']
        expires_at = datetime.datetime.strptime(
            token_data['expiresAt'], '%Y-%m-%dT%H:%M:%S%z'
        ).timestamp()
        save_token(token, expires_at)
        return token
    else:
        app.logger.error(
            f'Failed to obtain token: {response.status_code}'
            f' - {response.text}'
        )
    return None


def mask_phone_number(phone):
    return phone[:3] + '*' * (len(phone) - 5) + phone[-2:]


def fetch_user_phone(user_id):
    token = get_token()
    if not token:
        app.logger.error('Failed to obtain token.')
        return None

    headers = {'x-access-token': token}
    url = f'{MOYKLASS_API_URL}/company/users/{user_id}'
    response = requests.get(url, headers=headers)
    if response.status_code == http.HTTPStatus.OK:
        user_data = response.json()
        return user_data.get('phone')
    else:
        app.logger.error(
            f'Failed to fetch user data: {response.status_code}'
            f' - {response.text}'
        )
    return None


@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    app.logger.info(f'Received data: {data}')
    user_id = data.get('object', {}).get('userId')
    if not user_id:
        app.logger.error('No user ID provided.')
        return jsonify(
            {'status': 'error', 'message': 'No user ID provided'}
        ), http.HTTPStatus.BAD_REQUEST

    phone_number = fetch_user_phone(user_id)
    if not phone_number:
        app.logger.error('No phone number available for user.')
        return jsonify(
            {'status': 'error', 'message': 'No phone number available'}
        ), http.HTTPStatus.NOT_FOUND

    message = (
        'Podsecamo vas da imate jos dva uplacena casa srpskog jezika. '
        'Da biste nastavili sa casovima, mozete nam se javiti za uplatu'
        ' i termine. Radujemo se vasem napretku!'
    )
    sms_payload = {
        'sender': 'SmartLab',
        'message': message,
        'phone': phone_number
    }
    headers = {
        'Content-type': 'application/json; charset=utf-8',
        'username': SMS_USERNAME,
        'pwd': SMS_PASSWORD,
        'Host': 'sms.oneclick.rs'
    }
    try:
        sms_response = requests.post(
            SMS_API_URL, json=sms_payload, headers=headers
        )
        if sms_response.status_code == http.HTTPStatus.OK:
            app.logger.info(
                f'Message sent to {mask_phone_number(phone_number)}'
            )
            return jsonify({'status': 'success'}), http.HTTPStatus.OK
        else:
            app.logger.error(
                f'Failed to send message to {mask_phone_number(phone_number)}:'
                f' {sms_response.text}'
            )
            return jsonify(
                {'status': 'error', 'message': 'Failed to send SMS'}
            ), http.HTTPStatus.INTERNAL_SERVER_ERROR
    except requests.exceptions.RequestException as e:
        app.logger.error(f'Connection error while sending SMS: {str(e)}')
        return jsonify(
            {'status': 'error', 'message': 'SMS service unavailable'}
        ), http.HTTPStatus.INTERNAL_SERVER_ERROR


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
