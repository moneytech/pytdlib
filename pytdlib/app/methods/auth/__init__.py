import os
import re
import logging
from getpass import getpass

from pytdlib.utils import AuthorizationStats
from pytdlib.api import functions, types

from .check_bot_token import CheckBotToken
from .check_darabase_key import CheckDatabaseKey
from .set_database_key import SetDatabaseKey
from .send_code_request import SendCodeRequest
from .set_tdlib_parameters import SetTdlibParameters
from .sign_in import SignIn
from .sign_up import SignUp
from .close import Close

log = logging.getLogger(__name__)


class Auth(CheckBotToken,
           CheckDatabaseKey,
           SetDatabaseKey,
           SendCodeRequest,
           SetTdlibParameters,
           SignIn,
           SignUp,
           Close):

    def authorization(self, final_state: AuthorizationStats = AuthorizationStats(6)):

        def set_tdlib_params(_data: types.AuthorizationStateWaitTdlibParameters):
            dd = self.tdlib_parameters['database_directory'] or os.path.join(self.tdlib_parameters['work_dir'], 'database')
            fd = self.tdlib_parameters['files_directory'] or os.path.join(self.tdlib_parameters['work_dir'], 'files')

            return self.set_tdlib_parameters(
                use_test_dc=self.tdlib_parameters['test_mode'],
                database_directory=dd,
                files_directory=fd,
                use_file_database=self.tdlib_parameters['use_file_db'],
                use_chat_info_database=self.tdlib_parameters['use_chat_db'],
                use_message_database=self.tdlib_parameters['use_message_db'],
                use_secret_chats=self.tdlib_parameters['allow_secret_chat'],
                api_id=self.tdlib_parameters['api_id'],
                api_hash=self.tdlib_parameters['api_hash'],
                system_language_code=self.tdlib_parameters['lang_code'],
                device_model=self.tdlib_parameters['device_model'],
                system_version=self.tdlib_parameters['system_version'],
                application_version=self.tdlib_parameters['app_version'],
                enable_storage_optimizer=self.tdlib_parameters['storage_optimizer'],
                ignore_file_names=(not self.tdlib_parameters['file_readable_names'])
            )

        def check_encryption_key(data: types.AuthorizationStateWaitEncryptionKey):
            if data.is_encrypted:
                func = self.check_db_key
            else:
                func = self.set_db_key
            return func(self.encryption_key)

        def authorize(_data: types.AuthorizationStateWaitPhoneNumber):
            phone_number, bot_token = self.phone_number, self.bot_token
            if not any([phone_number, bot_token]):

                login_key = input("Enter phone number or bot token-key: ")

                while True:
                    confirm = input("Is \"{}\" correct? (y/n): ".format(login_key)).lower()

                    if confirm in ("y", "1"):
                        break
                    elif confirm in ("n", "2"):
                        login_key = input("Enter phone number or bot token-key: ")

                if re.search("(\d+):(\S+)", login_key):
                    bot_token = login_key
                else:
                    phone_number = login_key

            if bot_token:
                self.check_bot_token(bot_token)
            else:
                self.send_code_request(phone_number)

        def authorize_user(data: types.AuthorizationStateWaitCode):
            if data.terms_of_service is not None:
                print(data.terms_of_service)

            if self.phone_code is callable:
                code = self.phone_code()
            elif self.phone_code:
                code = self.phone_code
            else:
                code = ""
                while not code:
                    code = input("Enter phone code: ").strip().rstrip()

            if data.is_registered:
                return self.sign_in(code=code)
            else:
                self.first_name = self.first_name if self.first_name is not None else input("First name: ")
                self.last_name = self.last_name if self.last_name is not None else input("last name: ")

                return self.sign_up(code=code, first_name=self.first_name, last_name=self.last_name)

        def check_password(data: types.AuthorizationStateWaitPassword):
            text = "Two Factor Authorization!\n"
            if data.password_hint:
                text += "Password Hint: {}\n".format(data.password_hint)
            text += "Enter password: "
            password = getpass(prompt=text)
            return self.sign_in(password=password)

        stats = [
            set_tdlib_params,
            check_encryption_key,
            authorize,
            authorize_user,
            check_password,
            lambda u: setattr(self, "_authorized", True)
        ]
        while self._is_connected:
            last_state = self.send(functions.GetAuthorizationState())
            last_state_number = AuthorizationStats.get_step(last_state)
            log.info('Last Authorization Stats: %s' % last_state_number)
            try:
                stats[last_state_number](last_state)
            except IndexError:
                return
            if last_state_number >= final_state:
                break
