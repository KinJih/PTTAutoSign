import os
import requests
from PyPtt import PTT
from datetime import datetime, timezone, timedelta
import logging
import sys
from base64 import b64encode
from git import Repo
from nacl import encoding, public

tz = timezone(timedelta(hours=+8))
today = datetime.now(tz)
logger = logging.getLogger(__name__)
logging.basicConfig(level='INFO',
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

GH_REPO = os.getenv('GH_REPO')
GH_TOKEN = os.getenv('GH_TOKEN')
PTT_ID = os.getenv('PTT_ID')
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')


# RUN_PERIOD = os.getenv('RUN_PERIOD', None)


class Bot:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f'https://api.telegram.org/bot{self.token}'

    def sendMessage(self, text: str):
        r = requests.post(self.api_url + '/sendMessage',
                          json={
                              'chat_id': self.chat_id,
                              'text': text,
                              'parse_mode': 'html'
                          })


def update_secret(keys: str, value: str):
    base_url = f'https://api.github.com/repos/{GH_REPO}/actions/secrets'
    headers = {'Accept': 'application/vnd.github.v3+json', 'Authorization': f'token {GH_TOKEN}'}
    resp = requests.get(base_url + '/public-key', headers=headers)
    if 'key' not in resp.json():
        logger.critical('讀取 GH 公鑰失敗')
        sys.exit(1)
    public_key = resp.json()['key']
    key_id = resp.json()['key_id']

    public_key = public.PublicKey(public_key.encode('utf-8'), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = b64encode(
        sealed_box.encrypt(value.encode('utf-8'))).decode('utf-8')

    data = {'encrypted_value': encrypted, 'key_id': key_id}
    resp = requests.put(
        base_url + f'/{keys}',
        headers=headers,
        json=data)
    if resp.status_code in [201, 204]:
        logger.info('上傳 SECRET 成功')
    else:
        logger.critical('上傳 SECRET 失敗。')


def run_daily_login(ptt_id: str, ptt_passwd: str, bot: Bot):
    try:
        ptt.login(
            ptt_id,
            ptt_passwd,
            kick_other_login=True)
    except PTT.exceptions.NoSuchUser:
        bot.sendMessage('PTT 登入失敗！\n找不到使用者')
    except (PTT.exceptions.WrongIDorPassword, PTT.exceptions.WrongPassword):
        bot.sendMessage('PTT 登入失敗！\n帳號密碼錯誤')
    except PTT.exceptions.LoginTooOften:
        bot.sendMessage('PTT 登入失敗！\n登入太頻繁')
    except PTT.exceptions.UseTooManyResources:
        bot.sendMessage('PTT 登入失敗！\n使用過多 PTT 資源，請稍等一段時間並增加操作之間的時間間隔')
    else:
        try:
            check_mail = ptt.has_new_mail()
        except PTT.exceptions.UnregisteredUser:
            bot.sendMessage(f'{ptt_id} 未註冊使用者')
        else:
            user = ptt.get_user(ptt_id)
            text = f'✅ PTT {ptt_id} 已成功簽到\n'
            text += f'📆 已登入 {user.login_time} 天\n'
            if check_mail:
                text += '👀 你有新信件！\n'
            now: datetime = datetime.now(tz)
            text += f'#ptt #{now.strftime("%Y%m%d")}'
            bot.sendMessage(text)
        ptt.logout()


def run_check(check: bool = True, flags: bool = False) -> bool:
    repo = Repo('./')
    branches = repo.refs
    format = '%Y.%m.%d'
    today_date = today.strftime(format)

    if check:
        result = list(filter(lambda x: x.name == f'origin/{today_date}', list(branches)))
        logger.info(branches)
        logger.info(result)
        ## Checking step is moved to github action job
        # if result:
        #     logger.info('今天已經執行過。')
        #     return False
        # if today.hour == 23 and not result:
        #     return True
        # if not result and bool(getrandbits(1)):
        #     return True
        # return False
        return True
    if flags:
        ## branch creation and deletion are moved to github action job
        # new_branch = repo.create_head(today_date)
        # yesterday = today - timedelta(days=1)
        # yesterday_date = yesterday.strftime(format)

        # refspec = [f'{today_date}']
        # for branch in branches:
        #     if branch.name == f'origin/{yesterday_date}':
        #         # repo.delete_head(branch)
        #         refspec.append(f':{yesterday_date}')

        # # switch branch
        # repo.head.reference = new_branch
        # open(today_date, 'wb').close()
        # repo.index.add([today_date])
        # repo.index.commit(today_date)
        # repo.remotes.origin.push(refspec=tuple(refspec))
        return True


if __name__ == '__main__':
    if run_check(check=True):
        if not os.getenv('PTT_ID'):
            print('未輸入帳號資料')
            os.exit(1)

        bot = Bot(BOT_TOKEN, CHAT_ID)
        ptt = PTT.API()
        ptt_id, ptt_passwd = PTT_ID.split(',')
        
        run_daily_login(ptt_id, ptt_passwd, bot)
        run_check(check=False, flags=True)
    
